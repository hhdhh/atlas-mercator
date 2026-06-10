"""BaseAgent — the runtime that all sub-agents share.

A sub-agent is, at minimum:

* a system prompt that defines its role and reasoning scaffold,
* a list of tools it is allowed to call (subset of :class:`ToolRegistry`),
* a method :meth:`run` that takes a user input and returns a structured result.

For the MVP we keep things simple: a sub-agent is a stateful object that
holds a configured :class:`ChatAnthropic` and a system message. It can be
invoked with a string (single-shot) or with messages (multi-turn). The
:class:`AtlasOrchestrator` composes several of these into a graph.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from atlas_mercator.llm import get_default_llm
from atlas_mercator.observability.tracer import Tracer
from atlas_mercator.tools.base import BaseTool, ToolRegistry


@dataclass
class AgentRunResult:
    """The structured output of a single :meth:`BaseAgent.run` call."""

    content: str
    parsed: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: int = 0
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "parsed": self.parsed,
            "tool_calls": self.tool_calls,
            "latency_ms": self.latency_ms,
            "model": self.model,
        }


class BaseAgent:
    """Reusable base for all sub-agents.

    Subclasses should set ``system_prompt`` and (optionally) override
    :meth:`run` to add tool-calling or RAG logic.
    """

    name: str = "BaseAgent"
    system_prompt: str = "You are a helpful assistant."

    def __init__(
        self,
        *,
        tools: Iterable[str | BaseTool] | None = None,
        llm=None,
        tracer: Tracer | None = None,
        temperature: float | None = None,
    ) -> None:
        self.llm = llm or get_default_llm()
        if temperature is not None:
            self.llm = self.llm.bind(temperature=temperature)
        self.tracer = tracer or Tracer()
        self.tools: list[BaseTool] = self._resolve_tools(tools)

    # -- Tool wiring --------------------------------------------------------
    def _resolve_tools(self, tools: Iterable[str | BaseTool] | None) -> list[BaseTool]:
        if not tools:
            return []
        resolved: list[BaseTool] = []
        for t in tools:
            if isinstance(t, BaseTool):
                resolved.append(t)
            else:
                resolved.append(ToolRegistry.get(t))
        return resolved

    # -- Public API ---------------------------------------------------------
    def run(
        self,
        user_input: str,
        *,
        extra_context: dict[str, Any] | None = None,
        response_schema: type[BaseModel] | None = None,
    ) -> AgentRunResult:
        """Single-shot invocation.

        The agent emits plain text. If ``response_schema`` is provided we
        attempt to parse the last JSON object in the reply into the
        schema; otherwise the raw text is returned.
        """
        messages: list[Any] = [SystemMessage(content=self.system_prompt)]
        if extra_context:
            messages.append(
                HumanMessage(
                    content="<context>\n"
                    + json.dumps(extra_context, ensure_ascii=False, indent=2)
                    + "\n</context>"
                )
            )
        messages.append(HumanMessage(content=user_input))

        start = time.perf_counter()
        with self.tracer.span(self.name, user_input) as span:
            resp = self.llm.invoke(messages)
            latency = int((time.perf_counter() - start) * 1000)
            content = str(resp.content)
            model_name = getattr(resp, "response_metadata", {}).get("model_name", "")

            parsed: dict[str, Any] | None = None
            if response_schema is not None:
                parsed = self._parse_json(content)
                if parsed is not None:
                    try:
                        response_schema.model_validate(parsed)
                    except Exception as exc:  # pragma: no cover - logged
                        span.log(f"schema validation failed: {exc}")

            span.set("model", model_name)
            span.set("latency_ms", latency)
            span.set("content_chars", len(content))

        return AgentRunResult(
            content=content,
            parsed=parsed,
            latency_ms=latency,
            model=model_name,
        )

    # -- Helpers ------------------------------------------------------------
    @staticmethod
    def _parse_json(text: str) -> dict[str, Any] | None:
        """Best-effort extraction of the first JSON object from ``text``."""
        if not text:
            return None
        # Try direct parse first
        try:
            return json.loads(text)
        except Exception:
            pass
        # Try fenced ```json blocks
        import re

        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # Try first {...} span
        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
        return None


__all__ = ["AgentRunResult", "BaseAgent"]


# Re-export for convenience
from atlas_mercator.observability.tracer import Tracer  # noqa: E402,F401
