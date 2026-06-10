"""Tests for the LangGraph orchestrator (router + graph)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from atlas_mercator.orchestrator.router import _heuristic_intent, route


def test_heuristic_intent_listing() -> None:
    assert _heuristic_intent("为我的产品做 Amazon US 上架文案") == "listing"


def test_heuristic_intent_support() -> None:
    assert _heuristic_intent("客服，我的耳机不能开机") == "support"


def test_heuristic_intent_marketing() -> None:
    assert _heuristic_intent("Write 3 Instagram 文案 for my earbuds") == "marketing"


def test_heuristic_intent_intel() -> None:
    assert _heuristic_intent("分析 amazon_bestseller 的竞品卖点") == "intel"


def test_heuristic_intent_fallback() -> None:
    assert _heuristic_intent("Hello world") is None


def test_router_uses_llm_and_returns_plan() -> None:
    """End-to-end router test with the real LLM. Marked integration."""
    plan = route("为 BB-EARBUD-001 做 Amazon US 上架文案")
    assert plan.thought, "expected a non-empty thought"
    # The LLM sometimes returns no plan steps; the router should seed at least one.
    assert plan.plan, "expected at least one plan step (LLM or heuristic fallback)"


def test_router_fallback_when_llm_fails() -> None:
    """If the LLM raises, the router must still produce a usable plan."""
    with patch("atlas_mercator.orchestrator.router.get_default_llm") as mock_llm:
        from langchain_core.messages import AIMessage

        class _Boom:
            def invoke(self, messages):  # noqa: ARG002
                raise RuntimeError("simulated outage")

        mock_llm.return_value = _Boom()
        plan = route("做 Instagram 文案")
        assert plan.plan, "expected a fallback plan when LLM fails"
        assert any("marketing" in s.owner for s in plan.plan)
