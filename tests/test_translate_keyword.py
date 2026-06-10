"""Tests for LLM-backed translate + keyword tools (with stub LLM)."""

from __future__ import annotations

import pytest

from atlas_mercator.tools import ToolRegistry
from atlas_mercator.tools.keyword_tool import keyword_research
from atlas_mercator.tools.translate_tool import translate_listing


# -- translate_tool stub --------------------------------------------------
def test_translate_strips_code_fence() -> None:
    from langchain_core.messages import AIMessage

    from atlas_mercator.tools import translate_tool

    class _Stub:
        def invoke(self, messages):  # noqa: ARG002
            return AIMessage(content="```\nHola mundo\n```")

    monkeypatched = _Stub()
    out = translate_tool._strip_wrappers("```\nHola mundo\n```")
    assert out == "Hola mundo"

    translate_tool.get_fast_llm = lambda: monkeypatched  # type: ignore[assignment]
    assert translate_listing(text="Hello world", target_lang="es") == "Hola mundo"


def test_translate_handles_empty() -> None:
    assert translate_listing(text="", target_lang="en") == ""


# -- keyword_tool stub ----------------------------------------------------
def test_keyword_research_parses_fenced_array() -> None:
    from langchain_core.messages import AIMessage

    payload = '```json\n[{"keyword": "anc earbuds", "relevance": 0.9, "estimated_monthly_searches": 12000, "rationale": "high intent"}]\n```'

    class _Stub:
        def invoke(self, messages):  # noqa: ARG002
            return AIMessage(content=payload)

    from atlas_mercator.tools import keyword_tool

    keyword_tool.get_fast_llm = lambda: _Stub()  # type: ignore[assignment]
    rows = keyword_research(seed="anc earbuds", marketplace="amazon_us")
    assert len(rows) == 1
    assert rows[0]["keyword"] == "anc earbuds"
    assert rows[0]["relevance"] == pytest.approx(0.9)


def test_keyword_research_empty_seed() -> None:
    assert keyword_research(seed="", marketplace="amazon_us") == []


def test_keyword_research_handles_malformed_payload() -> None:
    class _Stub:
        def invoke(self, messages):  # noqa: ARG002
            from langchain_core.messages import AIMessage
            return AIMessage(content="not an array at all")

    from atlas_mercator.tools import keyword_tool

    keyword_tool.get_fast_llm = lambda: _Stub()  # type: ignore[assignment]
    assert keyword_research(seed="earbuds", marketplace="amazon_us") == []
