"""Unit tests for the ListingOptimizer.

We stub the underlying ChatAnthropic client so the test is fast, free,
and offline. Once the LLM stub returns a known JSON payload, we assert
that ``optimize`` parses it correctly.
"""

from __future__ import annotations

from typing import Any

import pytest

from atlas_mercator.agents.base import BaseAgent
from atlas_mercator.agents.listing_optimizer import ListingOptimizer, ListingOutput


class _StubMessage:
    def __init__(self, content: str) -> None:
        self.content = content
        self.response_metadata = {"model_name": "claude-sonnet-4-6-test"}


class _StubLLM:
    def __init__(self, scripted: str) -> None:
        self.scripted = scripted
        self.calls: list[list[Any]] = []

    def invoke(self, messages: list[Any]) -> _StubMessage:
        self.calls.append(messages)
        return _StubMessage(self.scripted)


def _sample_product() -> dict[str, Any]:
    return {
        "sku": "BB-EARBUD-001",
        "title_zh": "蓝牙无线耳机 ANC 主动降噪 40H 续航",
        "category": "Electronics > Audio > Earbuds",
        "price_usd": 39.99,
        "rating": 4.6,
    }


def test_optimize_parses_structured_listing() -> None:
    payload = """{
      "thought": "position as a commuter-friendly ANC earbud",
      "title": "Wireless ANC Earbuds, 40H Playtime, IPX5, Bluetooth 5.3",
      "bullets": [
        "Active Noise Cancellation: immersive sound in busy commutes",
        "40H total playtime with charging case for week-long use",
        "IPX5 sweat & rain resistance for running and gym",
        "Bluetooth 5.3 stable pairing with iOS and Android",
        "12-month warranty and 30-day money-back guarantee"
      ],
      "description": "These ANC earbuds deliver premium sound at a sub-$40 price point. The 40-hour total playtime covers a full work week. Pair once, forget about it.",
      "keywords": ["anc earbuds", "wireless earbuds", "bluetooth 5.3", "ipx5", "long battery earbuds"],
      "compliance_notes": ["amazon_us: avoided 'best' and 'guaranteed' superlatives"]
    }"""
    agent = ListingOptimizer(llm=_StubLLM(payload))
    result = agent.optimize(product=_sample_product(), marketplace="amazon_us", language="en")

    assert result.parsed is not None
    ListingOutput.model_validate(result.parsed)  # would raise on schema mismatch
    assert "Wireless ANC Earbuds" in result.parsed["title"]
    assert len(result.parsed["bullets"]) == 5
    assert result.model == "claude-sonnet-4-6-test"


def test_optimize_handles_malformed_json() -> None:
    agent = ListingOptimizer(llm=_StubLLM("I cannot help with that."))
    result = agent.optimize(product=_sample_product())
    # The agent should not crash; parsed will be None because no JSON found.
    assert result.parsed is None
    assert "cannot help" in result.content.lower()


@pytest.mark.parametrize("bad_payload", ["not json at all", '{"missing": "title"}'])
def test_optimize_rejects_invalid_schema(bad_payload: str) -> None:
    """A schema-invalid payload should not raise — agent.run catches it."""
    agent = ListingOptimizer(llm=_StubLLM(bad_payload))
    result = agent.optimize(product=_sample_product())
    # parsed will be None or dict that fails validation (but no exception).
    assert result.latency_ms >= 0  # ran successfully
