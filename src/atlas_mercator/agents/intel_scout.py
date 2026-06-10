"""IntelScout — competitive intelligence digest."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from atlas_mercator.agents.base import AgentRunResult, BaseAgent
from atlas_mercator.prompts.intel_scout import INTEL_SCOUT_SYSTEM_PROMPT


class ThreatScore(BaseModel):
    price: int = 3
    quality: int = 3
    brand: int = 3


class Differentiator(BaseModel):
    us: str
    them: str
    angle: str = ""


class CompetitorSummary(BaseModel):
    title: str = ""
    price: str = ""
    rating: str = ""
    key_features: list[str] = Field(default_factory=list)


class IntelOutput(BaseModel):
    thought: str = ""
    competitor_summary: CompetitorSummary = CompetitorSummary()
    threat_score: ThreatScore = ThreatScore()
    differentiators: list[Differentiator] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class IntelScout(BaseAgent):
    """Distill a competitor page into actionable intelligence."""

    name = "IntelScout"
    system_prompt = INTEL_SCOUT_SYSTEM_PROMPT

    def scout(
        self,
        competitor_data: dict[str, Any],
        our_product: dict[str, Any] | None = None,
    ) -> AgentRunResult:
        """Run the agent with a competitor page payload + optional our-product spec."""
        ctx: dict[str, Any] = {"competitor": competitor_data}
        if our_product:
            ctx["our_product"] = our_product
        return self.run(
            user_input="Please produce an intel digest for this competitor.",
            extra_context=ctx,
            response_schema=IntelOutput,
        )


__all__ = ["IntelScout", "IntelOutput", "ThreatScore", "Differentiator", "CompetitorSummary"]
