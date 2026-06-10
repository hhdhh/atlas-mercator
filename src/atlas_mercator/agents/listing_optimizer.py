"""ListingOptimizer — the first sub-agent we ship.

For the MVP it is a single-shot LLM call: the agent takes a product
JSON + marketplace, and returns a structured listing. In Phase B we
extend it to call :func:`search_products` and :func:`translate_listing`
so it can enrich and translate the result.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from atlas_mercator.agents.base import AgentRunResult, BaseAgent
from atlas_mercator.prompts.listing_optimizer import LISTING_OPTIMIZER_SYSTEM_PROMPT


class ListingOutput(BaseModel):
    """The structured output the ListingOptimizer must produce."""

    thought: str = ""
    title: str
    bullets: list[str] = Field(default_factory=list, max_length=5)
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    compliance_notes: list[str] = Field(default_factory=list)


class ListingOptimizer(BaseAgent):
    """Localize a product master into a marketplace-ready listing."""

    name = "ListingOptimizer"
    system_prompt = LISTING_OPTIMIZER_SYSTEM_PROMPT

    def optimize(
        self,
        product: dict[str, Any],
        marketplace: str = "amazon_us",
        language: str = "en",
    ) -> AgentRunResult:
        """Run the agent and parse its output as a :class:`ListingOutput`."""
        request = (
            "Please produce a listing for the following product.\n\n"
            f"Marketplace: {marketplace}\n"
            f"Target language: {language}\n"
        )
        return self.run(
            user_input=request,
            extra_context={"product": product},
            response_schema=ListingOutput,
        )


__all__ = ["ListingOptimizer", "ListingOutput"]
