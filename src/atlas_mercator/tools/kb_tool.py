"""Knowledge-base search tool — Chroma + sentence-transformers RAG.

This is a thin LangChain ``@tool`` wrapper around :class:`KBRetriever`.
The retriever is lazily instantiated on first call so unit tests that
mock the LLM do not pay the embedding-model load cost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from atlas_mercator.tools.base import tool

if TYPE_CHECKING:
    from atlas_mercator.rag.retriever import KBRetriever

_retriever: "KBRetriever | None" = None


def _get_retriever() -> "KBRetriever":
    global _retriever
    if _retriever is None:
        from atlas_mercator.rag.retriever import KBRetriever

        _retriever = KBRetriever()
    return _retriever


@tool(
    name="search_kb",
    description="Semantic search over the policy / FAQ / troubleshooting knowledge base.",
    tags=["rag", "read"],
)
def search_kb(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Return up to ``top_k`` KB chunks relevant to ``query``."""
    if not query or not query.strip():
        return []
    return _get_retriever().query(query, top_k=top_k)
