"""Tool I/O schemas — the wrappers around every tool call."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """A single tool invocation trace record."""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    thought: str = Field("", description="Why the agent decided to call this tool.")
    result_excerpt: str = Field("", description="Short, sanitised excerpt of the result.")
    error: str | None = None
    latency_ms: int = 0


class ToolResult(BaseModel):
    """A typed wrapper around a tool's return value."""

    name: str
    ok: bool = True
    data: Any = None
    error: str | None = None
