"""Base abstractions for tools.

A *tool* in Atlas Mercator is a small callable that exposes:

* a stable name (used by agents to invoke it)
* a JSON-Schema-compatible argument spec
* a Pydantic output model (when the call is structured)
* timing + tracing hooks

The :func:`tool` decorator wires all of that in one place.
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, get_type_hints

from pydantic import BaseModel, Field, create_model


@dataclass
class BaseTool:
    """Runtime handle to a registered tool.

    This is what the orchestrator sees: a name, a description, the original
    callable, and the auto-generated Pydantic model for the arguments.
    """

    name: str
    description: str
    func: Callable[..., Any]
    args_schema: type[BaseModel]
    tags: list[str] = field(default_factory=list)
    call_count: int = 0
    total_latency_ms: int = 0

    def invoke(self, **kwargs: Any) -> Any:
        """Invoke the underlying function, tracking latency + call count.

        Argument validation is delegated to Pydantic when ``args_schema`` is
        provided. The result is returned as-is — agents are responsible for
        wrapping it in a :class:`ToolResult` if they need error handling.
        """
        validated = self.args_schema.model_validate(kwargs)
        start = time.perf_counter()
        try:
            result = self.func(**validated.model_dump())
        except Exception as exc:  # pragma: no cover - surfaced in agent logs
            self.call_count += 1
            self.total_latency_ms += int((time.perf_counter() - start) * 1000)
            raise
        self.call_count += 1
        self.total_latency_ms += int((time.perf_counter() - start) * 1000)
        return result


class ToolRegistry:
    """Process-wide registry of tools, keyed by name."""

    _tools: dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool_obj: BaseTool) -> BaseTool:
        cls._tools[tool_obj.name] = tool_obj
        return tool_obj

    @classmethod
    def get(cls, name: str) -> BaseTool:
        if name not in cls._tools:
            raise KeyError(f"Tool {name!r} not registered.")
        return cls._tools[name]

    @classmethod
    def all(cls) -> list[BaseTool]:
        return list(cls._tools.values())

    @classmethod
    def clear(cls) -> None:
        cls._tools.clear()

    @classmethod
    def as_langchain(cls) -> list[Any]:
        """Return LangChain ``StructuredTool`` instances for agent binding."""
        from langchain_core.tools import StructuredTool

        return [
            StructuredTool.from_function(
                func=t.func,
                name=t.name,
                description=t.description,
                args_schema=t.args_schema,
            )
            for t in cls.all()
        ]


def _build_args_schema(func: Callable[..., Any]) -> type[BaseModel]:
    """Build a Pydantic model from the function signature + type hints."""
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    fields: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        annotation = hints.get(name, param.annotation if param.annotation is not inspect._empty else Any)
        default = param.default if param.default is not inspect._empty else ...
        fields[name] = (annotation, Field(default))
    return create_model(f"{func.__name__.title()}Args", **fields)  # type: ignore[return-value]


def tool(
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> Callable[[Callable[..., Any]], BaseTool]:
    """Decorator that turns a function into a registered :class:`BaseTool`.

    Example::

        @tool(name="search_products", description="Look up products by query")
        def search_products(query: str, marketplace: str = "amazon_us") -> list[dict]:
            ...
    """

    def decorator(func: Callable[..., Any]) -> BaseTool:
        schema = _build_args_schema(func)
        tool_obj = BaseTool(
            name=name or func.__name__,
            description=description or (func.__doc__ or "").strip().splitlines()[0],
            func=func,
            args_schema=schema,
            tags=tags or [],
        )
        ToolRegistry.register(tool_obj)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover - passthrough
            # Bind positional args to their parameter names so we can pass
            # everything through as kwargs to the validated invoke().
            if args:
                bound = inspect.signature(func).bind_partial(*args, **kwargs)
                bound.apply_defaults()
                return tool_obj.invoke(**bound.arguments)
            return tool_obj.invoke(**kwargs)

        wrapper.__tool__ = tool_obj  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
