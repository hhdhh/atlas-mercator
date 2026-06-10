"""Tests for the KB retriever (TF-IDF backend)."""

from __future__ import annotations

import pytest

from atlas_mercator.rag.retriever import KBRetriever


@pytest.fixture(autouse=True)
def _fresh_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the retriever singleton between tests."""
    KBRetriever._instance = None
    yield
    KBRetriever._instance = None


def test_query_returns_top_k() -> None:
    r = KBRetriever()
    out = r.query("蓝牙耳机左声道没声音", top_k=3)
    assert len(out) == 3
    assert all("text" in h and "source" in h and "score" in h for h in out)


def test_query_top_hit_is_relevant() -> None:
    r = KBRetriever()
    out = r.query("蓝牙耳机左声道没声音", top_k=1)
    assert out
    # Top hit should mention earbud + reset.
    assert "蓝牙" in out[0]["text"]


def test_query_shipping_to_germany() -> None:
    r = KBRetriever()
    out = r.query("寄到德国要多久", top_k=1)
    assert out
    assert "德国" in out[0]["text"]


def test_query_empty_returns_empty() -> None:
    r = KBRetriever()
    assert r.query("", top_k=3) == []
    assert r.query("   ", top_k=3) == []


def test_query_respects_top_k() -> None:
    r = KBRetriever()
    assert len(r.query("policy", top_k=5)) <= 5
    assert len(r.query("policy", top_k=1)) == 1
