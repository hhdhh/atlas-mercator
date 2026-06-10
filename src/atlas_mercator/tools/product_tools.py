"""Product-side tools — mock the PIM and WMS layers of an ERP.

These are read-only by design: the agent's job is to discover and shape
products, not to mutate the master record.  Returns are plain dicts so
the LLM can ingest them as JSON without further parsing.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from atlas_mercator.config import get_settings
from atlas_mercator.tools.base import tool

_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "products.json"


@lru_cache(maxsize=1)
def _load_products() -> list[dict[str, Any]]:
    """Read the mock product master into memory (cached for the process)."""
    if not _DATA_PATH.exists():
        return []
    with _DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _char_coverage(query: str, haystack: str) -> float:
    """Return the fraction of ``query`` characters that appear in ``haystack``.

    Works for Chinese (per-character), English (per-token), or mixed. A
    coverage of 1.0 means every token/char of the query was found in the
    haystack (in any order, even non-contiguously).
    """
    if not query:
        return 0.0
    # Split Chinese runs into characters; keep English words whole.
    tokens: list[str] = []
    buf = ""
    for ch in query:
        if "一" <= ch <= "鿿":  # CJK ideograph
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        elif ch.isspace():
            if buf:
                tokens.append(buf)
                buf = ""
        else:
            buf += ch
    if buf:
        tokens.append(buf)
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t and t in haystack)
    return hits / len(tokens)


@tool(
    name="search_products",
    description="Search the product master (PIM) by free-text query and optional category filter.",
    tags=["pim", "read"],
)
def search_products(query: str, category: str = "", limit: int = 5) -> list[dict[str, Any]]:
    """Return up to ``limit`` products matching ``query`` and optional ``category``.

    Args:
        query: Free-text query, matched against title (zh) and category.
        category: Optional category filter, e.g. "Electronics > Audio".
        limit: Maximum number of results (default 5, max 20).
    """
    products = _load_products()
    q = _norm(query)
    cat = _norm(category) if category else ""
    max_results = max(1, min(limit, 20))

    if not q and not cat:
        # No filter — return the first N products in stable SKU order.
        return sorted(products, key=lambda p: p["sku"])[:max_results]

    scored: list[tuple[float, dict[str, Any]]] = []
    for p in products:
        haystack = _norm(f"{p['title_zh']} {p['category']}")
        score = 0.0
        if q:
            score += _char_coverage(q, haystack) * 2.0
            if q in haystack:
                score += 1.0
        if cat and cat in _norm(p["category"]):
            score += 3.0
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1]["sku"]))
    return [p for _, p in scored[:max_results]]


@tool(
    name="get_inventory",
    description="Look up WMS stock and origin info for a single SKU.",
    tags=["wms", "read"],
)
def get_inventory(sku: str) -> dict[str, Any]:
    """Return stock, origin, weight, and lead-time mock for ``sku``."""
    sku_norm = sku.strip().upper()
    for p in _load_products():
        if p["sku"].upper() == sku_norm:
            return {
                "sku": p["sku"],
                "stock": p["stock"],
                "origin": p["origin"],
                "weight_g": p["weight_g"],
                "lead_time_days": 3 if p["origin"] in {"Shenzhen", "Dongguan", "Foshan"} else 5,
            }
    return {"sku": sku_norm, "stock": 0, "origin": "unknown", "weight_g": 0, "lead_time_days": 0}
