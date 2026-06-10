"""Unit tests for product_tools.search_products / get_inventory."""

from __future__ import annotations

import pytest

from atlas_mercator.tools import ToolRegistry
from atlas_mercator.tools.product_tools import get_inventory, search_products


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Make sure each test gets a fresh load of the mock data."""
    search_products.func.__self__ if False else None  # type: ignore[attr-defined]  # noqa: E501
    from atlas_mercator.tools.product_tools import _load_products

    _load_products.cache_clear()  # type: ignore[attr-defined]


def test_search_products_finds_earbuds_by_query() -> None:
    results = search_products(query="蓝牙耳机")
    assert results, "Expected at least one match for '蓝牙耳机'"
    assert results[0]["sku"] == "BB-EARBUD-001"


def test_search_products_respects_category_filter() -> None:
    results = search_products(query="", category="Electronics > Audio")
    assert results
    assert all("Audio" in p["category"] for p in results)


def test_search_products_respects_limit() -> None:
    results = search_products(query="", category="", limit=3)
    assert len(results) == 3


def test_get_inventory_known_sku() -> None:
    inv = get_inventory("bb-earbud-001")  # case-insensitive
    assert inv["sku"] == "BB-EARBUD-001"
    assert inv["stock"] > 0
    assert inv["origin"] in {"Shenzhen", "Dongguan", "Foshan", "Zhongshan", "Hangzhou", "Ningbo", "Yongkang"}


def test_get_inventory_unknown_sku() -> None:
    inv = get_inventory("DOES-NOT-EXIST")
    assert inv["stock"] == 0


def test_tools_registered() -> None:
    assert ToolRegistry.get("search_products").name == "search_products"
    assert ToolRegistry.get("get_inventory").name == "get_inventory"
