"""MarketingCopilot — generates A/B copy variants."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from atlas_mercator.agents.base import AgentRunResult, BaseAgent
from atlas_mercator.prompts.marketing_copilot import MARKETING_COPILOT_SYSTEM_PROMPT


class MarketingVariant(BaseModel):
    model_config = {"protected_namespaces": ()}
    label: str = "A"
    angle: str = "benefit"
    body: str = Field(..., description="The marketing copy text.")
    image_prompt: str = ""
    rationale: str = ""


class MarketingOutput(BaseModel):
    thought: str = ""
    variants: list[MarketingVariant] = Field(default_factory=list, max_length=4)
    hashtags: list[str] = Field(default_factory=list)


class MarketingCopilot(BaseAgent):
    """Generate A/B marketing copy variants."""

    name = "MarketingCopilot"
    system_prompt = MARKETING_COPILOT_SYSTEM_PROMPT

    def draft(
        self,
        product: dict[str, Any],
        channel: str = "instagram",
        audience: str = "commuters 25-35",
    ) -> AgentRunResult:
        """Generate 3 marketing variants for a product + channel + audience."""
        request = (
            f"Please generate marketing copy.\n\n"
            f"Channel: {channel}\n"
            f"Target audience: {audience}\n"
        )
        return self.run(
            user_input=request,
            extra_context={"product": product},
            response_schema=MarketingOutput,
        )


__all__ = ["MarketingCopilot", "MarketingOutput", "MarketingVariant"]
