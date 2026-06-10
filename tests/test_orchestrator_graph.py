"""Smoke tests for the LangGraph orchestrator (no LLM calls).

We test the individual node functions and the graph assembly rather
than the full end-to-end flow, which requires real LLM credentials.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from atlas_mercator.orchestrator.graph import (
    OrchestratorState,
    _find_product,
    _first_sku,
    _node_dispatch,
    _node_synthesize,
    build_graph,
)
from atlas_mercator.schemas.intent import AgentStep, OrchestratorPlan


# -- Helpers / unit tests -----------------------------------------------
def test_first_sku_extracts() -> None:
    assert _first_sku("为 BB-EARBUD-001 做 Amazon US 上架") == "BB-EARBUD-001"
    assert _first_sku("没有 SKU 的请求") is None


def test_find_product_known_sku() -> None:
    p = _find_product("BB-EARBUD-001")
    assert p is not None
    assert p["sku"] == "BB-EARBUD-001"


def test_find_product_unknown_sku() -> None:
    assert _find_product("DOES-NOT-EXIST") is None


def test_build_graph_compiles() -> None:
    g = build_graph()
    assert g is not None


# -- Synthesize node -----------------------------------------------------
def test_synthesize_with_no_results() -> None:
    state: OrchestratorState = {
        "user_request": "x",
        "plan": OrchestratorPlan(thought="t", plan=[]),
        "step_results": [],
    }
    out = _node_synthesize(state)
    assert out["final_answer"] == "_no steps executed_"
    assert out["citations"] == []


def test_synthesize_with_listing_result() -> None:
    state: OrchestratorState = {
        "user_request": "x",
        "plan": OrchestratorPlan(thought="t", plan=[]),
        "step_results": [
            {
                "step": 1,
                "owner": "listing_optimizer:optimize",
                "action": "do",
                "parsed": {"title": "Test Product Title"},
                "raw": "",
                "latency_ms": 100,
            }
        ],
    }
    out = _node_synthesize(state)
    assert "Test Product Title" in out["final_answer"]
    assert "listing_optimizer" in out["final_answer"]


def test_synthesize_with_error() -> None:
    state: OrchestratorState = {
        "user_request": "x",
        "plan": OrchestratorPlan(thought="t", plan=[]),
        "step_results": [{"step": 1, "owner": "intel_scout:scout", "error": "boom"}],
    }
    out = _node_synthesize(state)
    assert "boom" in out["final_answer"]


# -- Dispatch node (with patched tools) ---------------------------------
def test_dispatch_handles_unknown_owner() -> None:
    state: OrchestratorState = {
        "user_request": "x",
        "plan": OrchestratorPlan(
            thought="t",
            plan=[AgentStep(step=1, owner="unknown_agent:do", action="x")],
        ),
    }
    out = _node_dispatch(state)
    assert out["step_results"][0]["error"]
