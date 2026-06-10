"""Lightweight in-process tracer.

A drop-in replacement for LangSmith/Langfuse during local development.
Each :meth:`Tracer.span` context manager records timing, inputs, and
arbitrary key/value pairs into an in-memory list. The Gradio demo
reads from the tracer to render the live tool-call trace table.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Span:
    name: str
    started_at: float
    finished_at: float = 0.0
    inputs: str = ""
    attributes: dict[str, object] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        if not self.finished_at:
            return 0
        return int((self.finished_at - self.started_at) * 1000)

    def set(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def log(self, message: str) -> None:
        self.attributes.setdefault("_log", []).append(message)  # type: ignore[arg-type]


class Tracer:
    """Collects :class:`Span` objects for the lifetime of the process."""

    def __init__(self) -> None:
        self.spans: list[Span] = []

    @contextmanager
    def span(self, name: str, inputs: str = "") -> Iterator[Span]:
        s = Span(name=name, started_at=time.perf_counter(), inputs=inputs)
        try:
            yield s
        finally:
            s.finished_at = time.perf_counter()
            self.spans.append(s)

    def clear(self) -> None:
        self.spans.clear()

    def as_dataframe_rows(self) -> list[dict[str, object]]:
        """Return a list of dicts ready to feed into ``gr.Dataframe``."""
        rows: list[dict[str, object]] = []
        for i, s in enumerate(self.spans, start=1):
            rows.append(
                {
                    "step": i,
                    "agent": s.name,
                    "thought": (s.inputs or "").replace("\n", " ")[:120],
                    "tool": s.attributes.get("tool", ""),
                    "latency_ms": s.duration_ms,
                    "model": s.attributes.get("model", ""),
                }
            )
        return rows
