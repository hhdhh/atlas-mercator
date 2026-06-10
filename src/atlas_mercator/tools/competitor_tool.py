"""Competitor page scraper — parses a mock HTML dataset.

We keep the network call free: instead of fetching live pages, we
match a URL to a small built-in dataset. This is the same contract a
real scraper would expose, so swapping in a httpx + BeautifulSoup
implementation is a one-file change.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from atlas_mercator.tools.base import tool

_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "competitor_pages"

# Pre-baked URL aliases that map to the bundled mock files.
_MOCK_PAGES: dict[str, str] = {
    "amazon_bestseller_earbuds": "amazon_bestseller_earbuds.html",
    "ebay_deal_watch": "ebay_deal_watch.html",
    "shopify_niche_brand": "shopify_niche_brand.html",
}


class _ListingParser(HTMLParser):
    """Tiny HTML parser that extracts the first <article> / <section> block."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.in_block = False
        self.tag_stack: list[str] = []
        self.title: str = ""
        self.price: str = ""
        self.body_lines: list[str] = []
        self.bullets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        self.tag_stack.append(tag)
        if tag in ("article", "section") and not self.in_block:
            self.in_block = True
            self.depth = 1
            return
        if self.in_block:
            self.depth += 1
        if tag == "h2" and self.in_block:
            self._capture = "title"
            self._buf = ""

    def handle_endtag(self, tag: str) -> None:
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
        if self.in_block:
            self.depth -= 1
            if self.depth == 0:
                self.in_block = False

    def handle_data(self, data: str) -> None:
        if not self.in_block:
            return
        s = data.strip()
        if not s:
            return
        if self.tag_stack and self.tag_stack[-1] == "h2" and not self.title:
            self.title = s
        elif self.tag_stack and self.tag_stack[-1] == "p" and "price" in (s.lower()):
            pass
        if "class" not in (self.tag_stack[-1] if self.tag_stack else ""):
            self.body_lines.append(s)


def _parse(path: Path) -> dict[str, Any]:
    parser = _ListingParser()
    parser.feed(path.read_text(encoding="utf-8"))
    text = "\n".join(parser.body_lines)
    price_match = re.search(r"[\$€¥]\s*[\d,]+(?:\.\d+)?", text)
    return {
        "url": path.stem,
        "title": parser.title or path.stem,
        "price": price_match.group(0) if price_match else "unknown",
        "summary": text[:600],
        "source_file": path.name,
    }


@tool(
    name="fetch_competitor_page",
    description="Fetch a competitor product page (mock dataset) and return price + summary.",
    tags=["scraper", "read"],
)
def fetch_competitor_page(url: str) -> dict[str, Any]:
    """Return a parsed summary for ``url``.

    ``url`` can be:
    * a key from :data:`_MOCK_PAGES` (e.g. ``amazon_bestseller_earbuds``),
    * a substring of a file name (matched case-insensitively),
    * or a fake URL containing one of the above tokens.
    """
    if not url:
        return {"url": url, "error": "empty url"}
    needle = url.strip().lower()
    # 1. Exact key match.
    for key, fname in _MOCK_PAGES.items():
        if key in needle:
            path = _DATA_DIR / fname
            if path.exists():
                return _parse(path)
    # 2. Filename substring match.
    for fname in _MOCK_PAGES.values():
        if Path(fname).stem.split("_")[0] in needle:
            path = _DATA_DIR / fname
            if path.exists():
                return _parse(path)
    return {"url": url, "error": "no mock page matched"}
