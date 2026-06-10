"""Unit tests for translate / keyword / competitor / support tools."""

from __future__ import annotations

import pytest

from atlas_mercator.tools import ToolRegistry
from atlas_mercator.tools.competitor_tool import fetch_competitor_page
from atlas_mercator.tools.support_tools import create_ticket, get_order, list_tickets


# -- competitor_tool -----------------------------------------------------
class _StubMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _StubLLM:
    def __init__(self, scripted: str) -> None:
        self.scripted = scripted
        self.calls: list[list] = []

    def invoke(self, messages: list) -> _StubMessage:
        self.calls.append(messages)
        return _StubMessage(self.scripted)


def test_competitor_preset_returns_parsed_block(monkeypatch: pytest.MonkeyPatch) -> None:
    out = fetch_competitor_page(url="amazon_bestseller_earbuds")
    assert "error" not in out
    assert out["price"] != "unknown"
    assert "title" in out


def test_competitor_unknown_url_returns_error() -> None:
    out = fetch_competitor_page(url="https://example.com/no-match")
    assert "error" in out


# -- support_tools --------------------------------------------------------
def test_get_order_by_customer_id() -> None:
    rows = get_order(customer_id="C1024")
    assert len(rows) >= 2  # ORD-20260417-001, ORD-20260502-002, ORD-20260605-005
    assert all(r["customer_id"] == "C1024" for r in rows)


def test_get_order_by_order_id() -> None:
    rows = get_order(order_id="ORD-20260601-004")
    assert len(rows) == 1
    assert rows[0]["sku"] == "PF-FEEDER-009"


def test_create_ticket_then_list() -> None:
    t = create_ticket(issue="earbud defective", customer_id="C1024", priority="high")
    assert t["ticket_id"].startswith("T-")
    assert t["priority"] == "high"
    rows = list_tickets(customer_id="C1024", limit=5)
    assert any(r["ticket_id"] == t["ticket_id"] for r in rows)


# -- Tool registry smoke ---------------------------------------------------
def test_all_business_tools_registered() -> None:
    names = {t.name for t in ToolRegistry.all()}
    for expected in {
        "search_products", "get_inventory", "translate_listing",
        "keyword_research", "fetch_competitor_page", "get_order",
        "create_ticket", "search_kb",
    }:
        assert expected in names, f"missing tool: {expected}"


# -- Tracer ---------------------------------------------------------------
def test_tracer_records_spans() -> None:
    from atlas_mercator.observability.tracer import Tracer

    t = Tracer()
    with t.span("a", inputs="hello") as s:
        s.set("foo", 1)
    with t.span("b", inputs="world") as s:
        s.set("bar", 2)
    assert len(t.spans) == 2
    rows = t.as_dataframe_rows()
    assert rows[0]["agent"] == "a" and rows[1]["agent"] == "b"


# -- Config ---------------------------------------------------------------
def test_config_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.com")
    monkeypatch.setenv("ATLAS_RAG_BACKEND", "tfidf")
    from atlas_mercator import config
    from atlas_mercator.config import get_settings

    config.reset_settings()
    s = get_settings()
    assert s.anthropic_base_url == "https://example.com"
    assert s.rag_backend == "tfidf"


# -- LangChain export ----------------------------------------------------
def test_tool_registry_langchain_export() -> None:
    from atlas_mercator.tools import ToolRegistry

    lc_tools = ToolRegistry.as_langchain()
    assert len(lc_tools) == len(ToolRegistry.all())
    assert all(hasattr(t, "name") for t in lc_tools)
