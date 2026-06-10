"""Intent and Orchestrator plan schemas — the brain of the multi-agent system."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Intent(BaseModel):
    """The orchestrator's parsed understanding of a user request."""

    raw: str = Field(..., description="The original user request, verbatim.")
    category: Literal[
        "listing",
        "support",
        "marketing",
        "intel",
        "mixed",
        "unknown",
    ]
    confidence: float = Field(..., ge=0.0, le=1.0)
    entities: dict[str, str] = Field(
        default_factory=dict,
        description="Extracted entities: sku, marketplace, customer_id, etc.",
    )
    rationale: str = ""


class AgentStep(BaseModel):
    """One ordered step in an orchestrator plan."""

    step: int = Field(..., ge=1)
    owner: str = Field(..., description="agent name or tool name")
    action: str = Field(..., description="What the owner is asked to do.")
    expected_output: str = ""


class OrchestratorPlan(BaseModel):
    """The full plan emitted by the orchestrator's THOUGHT→PLAN phase."""

    thought: str = Field(..., min_length=1, description="One-sentence goal restatement.")
    plan: list[AgentStep] = Field(default_factory=list, max_length=8)
    clarifying_question: str | None = None
    final_answer: str | None = None


class FinalAnswer(BaseModel):
    """The synthesised final answer with per-step citations."""

    summary: str
    citations: list[dict[str, str]] = Field(default_factory=list)
    raw_steps: list[dict[str, str]] = Field(default_factory=list)
