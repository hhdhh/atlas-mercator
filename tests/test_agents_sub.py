"""Tests for SupportAgent, MarketingCopilot, and IntelScout (stub LLM)."""

from __future__ import annotations

from typing import Any

import pytest

from atlas_mercator.agents.intel_scout import IntelScout
from atlas_mercator.agents.marketing_copilot import MarketingCopilot
from atlas_mercator.agents.support_agent import SupportAgent


class _StubMessage:
    def __init__(self, content: str) -> None:
        self.content = content
        self.response_metadata = {"model_name": "claude-stub"}


class _StubLLM:
    def __init__(self, scripted: str) -> None:
        self.scripted = scripted

    def invoke(self, messages: list[Any]) -> _StubMessage:
        return _StubMessage(self.scripted)


# -- SupportAgent ---------------------------------------------------------
def test_support_agent_parses_rag_answer() -> None:
    payload = """{
      "thought": "earbud is defective, needs troubleshooting",
      "intent": "defective",
      "answer": "请长按充电盒 10 秒重置配对。",
      "citations": [{"source": "troubleshoot/earbuds.md", "quote": "蓝牙耳机左声道没声音"}],
      "action_taken": "created_ticket",
      "ticket_id": null
    }"""
    agent = SupportAgent(llm=_StubLLM(payload))
    result = agent.handle("我的耳机左声道没声音", customer_id="C1024", order_id="ORD-20260417-001")
    assert result.parsed is not None
    assert result.parsed["intent"] == "defective"
    assert result.parsed["action_taken"] == "created_ticket"
    # Ticket should have been opened by the side-effect.
    assert result.parsed["ticket_id"] is not None
    assert result.parsed["ticket_id"].startswith("T-")


def test_support_agent_no_action_keeps_none() -> None:
    payload = """{
      "thought": "simple shipping question",
      "intent": "shipping",
      "answer": "标准物流 7-12 工作日",
      "citations": [{"source": "policy/shipping.md", "quote": "标准物流 7-12 工作日"}],
      "action_taken": "none",
      "ticket_id": null
    }"""
    agent = SupportAgent(llm=_StubLLM(payload))
    result = agent.handle("寄到美国要多久", customer_id="C1024")
    assert result.parsed["ticket_id"] is None


# -- MarketingCopilot -----------------------------------------------------
def test_marketing_copilot_returns_three_variants() -> None:
    payload = """{
      "thought": "targeting commuter pain point",
      "variants": [
        {"label": "A", "angle": "benefit", "body": "地铁里也能 0 噪音", "image_prompt": "earbuds in subway", "rationale": "commute = pain"},
        {"label": "B", "angle": "social_proof", "body": "5 万人都在用", "image_prompt": "crowd of users", "rationale": "FOMO"},
        {"label": "C", "angle": "urgency", "body": "今日特价", "image_prompt": "sale tag", "rationale": "conversion"}
      ],
      "hashtags": ["earbuds", "wireless", "anc", "amazonfinds"]
    }"""
    agent = MarketingCopilot(llm=_StubLLM(payload))
    result = agent.draft(product={"sku": "BB-EARBUD-001", "title_zh": "蓝牙耳机"}, channel="instagram", audience="commuters 25-35")
    assert result.parsed is not None
    assert len(result.parsed["variants"]) == 3
    assert len(result.parsed["hashtags"]) >= 3


# -- IntelScout -----------------------------------------------------------
def test_intel_scout_produces_threat_score() -> None:
    payload = """{
      "thought": "they're a major brand with strong pricing",
      "competitor_summary": {
        "title": "Soundcore Life P2 Mini",
        "price": "$24.99",
        "rating": "4.3",
        "key_features": ["32h playtime", "USB-C", "3 EQ modes"]
      },
      "threat_score": {"price": 4, "quality": 3, "brand": 4},
      "differentiators": [
        {"us": "40H playtime", "them": "32H playtime", "angle": "longer battery"},
        {"us": "ANC included", "them": "no ANC", "angle": "premium feature at entry price"}
      ],
      "recommended_actions": ["highlight 40H in title", "lead with ANC differentiator"]
    }"""
    agent = IntelScout(llm=_StubLLM(payload))
    result = agent.scout(
        competitor_data={"title": "Soundcore", "price": "$24.99"},
        our_product={"sku": "BB-EARBUD-001"},
    )
    assert result.parsed is not None
    assert result.parsed["threat_score"]["price"] == 4
    assert len(result.parsed["differentiators"]) == 2
