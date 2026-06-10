"""Tests for Pydantic schemas + CLI smoke test."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from atlas_mercator.schemas.intent import (
    AgentStep,
    FinalAnswer,
    Intent,
    OrchestratorPlan,
)
from atlas_mercator.schemas.order import Order, OrderStatus, Ticket
from atlas_mercator.schemas.product import Listing, Product
from atlas_mercator.schemas.tool_io import ToolCall, ToolResult


# -- Product / Listing -----------------------------------------------------
def test_product_validates() -> None:
    p = Product(
        sku="bb-earbud-001",  # case-insensitive
        title_zh="蓝牙耳机",
        category="Electronics",
        price_usd=39.99,
        cost_usd=10.0,
        weight_g=180,
        origin="Shenzhen",
        stock=100,
        rating=4.5,
    )
    assert p.sku == "BB-EARBUD-001"  # normalized uppercase


def test_product_invalid_rating() -> None:
    with pytest.raises(Exception):
        Product(
            sku="X", title_zh="x", category="x", price_usd=1, cost_usd=0,
            weight_g=1, origin="x", stock=0, rating=99.0,
        )


def test_listing_constraints() -> None:
    l = Listing(
        sku="BB-EARBUD-001",
        marketplace="amazon_us",
        language="en",
        title="A great product",
        bullets=["b1", "b2", "b3", "b4", "b5"],
        description="A description",
        keywords=["k1", "k2"],
    )
    assert l.marketplace == "amazon_us"


# -- Order / Ticket -------------------------------------------------------
def test_order_status_enum() -> None:
    assert OrderStatus.DELIVERED == "delivered"
    o = Order(
        order_id="O-1", customer_id="C1", sku="S", qty=1, total_usd=10.0,
        status="delivered", placed_at="2026-01-01T00:00:00Z", destination_country="US",
    )
    assert o.status == OrderStatus.DELIVERED


def test_ticket_defaults() -> None:
    t = Ticket(ticket_id="T-1", customer_id="C1", issue="x", created_at="2026-01-01T00:00:00Z")
    assert t.closed is False
    assert t.resolution is None


# -- Intent / Plan --------------------------------------------------------
def test_intent_validation() -> None:
    i = Intent(raw="hi", category="unknown", confidence=0.5)
    assert i.confidence == 0.5


def test_orchestrator_plan() -> None:
    p = OrchestratorPlan(
        thought="do it",
        plan=[AgentStep(step=1, owner="listing_optimizer", action="optimize", expected_output="listing")],
    )
    assert p.plan[0].owner == "listing_optimizer"


def test_final_answer() -> None:
    a = FinalAnswer(summary="ok", citations=[{"source": "kb", "quote": "x"}])
    assert a.citations[0]["source"] == "kb"


# -- ToolCall / ToolResult -----------------------------------------------
def test_tool_call_and_result() -> None:
    tc = ToolCall(name="search", args={"q": "x"})
    assert tc.error is None
    tr = ToolResult(name="search", ok=True, data=[{"sku": "X"}])
    assert tr.data[0]["sku"] == "X"


# -- CLI smoke test -------------------------------------------------------
def test_cli_config_runs() -> None:
    """The ``atlas config`` subcommand must not crash."""
    result = subprocess.run(
        [sys.executable, "-m", "atlas_mercator.cli", "config"],
        capture_output=True,
        text=True,
        env={"ATLAS_RAG_BACKEND": "tfidf", "ANTHROPIC_BASE_URL": "https://api.example.com"},
    )
    assert result.returncode == 0
    body = json.loads(result.stdout)
    assert "model_default" in body
    assert body["anthropic_base_url"] == "https://api.example.com"
