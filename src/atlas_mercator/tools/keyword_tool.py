"""Keyword research tool — real Claude call returning structured JSON."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from atlas_mercator.llm import get_fast_llm
from atlas_mercator.tools.base import tool

SYSTEM = """You are an SEO keyword research analyst for cross-border e-commerce.

Given a seed keyword + target marketplace, return a JSON array of
8-15 backend search terms ranked by estimated relevance.

Each item shape:
{
  "keyword": "string",
  "relevance": 0.0-1.0,
  "estimated_monthly_searches": int,
  "rationale": "string (one short sentence)"
}

Hard rules:
- Return ONLY the JSON array, no commentary, no markdown fences.
- Avoid trademarks of specific brands (AirPods, Bose, etc).
- Mix head terms and long-tails; never repeat a word more than twice across the list.
"""


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    # Fenced JSON
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # First [...] span
    s = text.find("[")
    e = text.rfind("]")
    if 0 <= s < e:
        return json.loads(text[s : e + 1])
    raise ValueError(f"Could not extract JSON array from: {text[:200]!r}")


@tool(
    name="keyword_research",
    description="Generate 8-15 SEO keywords for a seed + marketplace, with relevance scores and search-volume estimates.",
    tags=["llm", "seo"],
)
def keyword_research(seed: str, marketplace: str = "amazon_us") -> list[dict[str, Any]]:
    """Return a ranked list of SEO keywords for ``seed`` on ``marketplace``."""
    if not seed or not seed.strip():
        return []
    llm = get_fast_llm()
    resp = llm.invoke(
        [
            SystemMessage(content=SYSTEM),
            HumanMessage(
                content=f"Marketplace: {marketplace}\nSeed keyword: {seed}\n\nReturn the JSON array only."
            ),
        ]
    )
    try:
        data = _extract_json_array(str(resp.content))
        return [d for d in data if isinstance(d, dict) and "keyword" in d]
    except Exception:
        return []
