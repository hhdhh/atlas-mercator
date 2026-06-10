"""Translation tool — real Claude call (Haiku model for cost)."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from atlas_mercator.llm import get_fast_llm
from atlas_mercator.tools.base import tool

SYSTEM = """You are a professional e-commerce copy translator.
Translate the user's input to the target language.
- Preserve marketing tone, benefit-led phrasing, and emoji.
- For Chinese source, never produce literal translations — adapt idioms.
- Return ONLY the translated text, no commentary, no quotes."""


def _strip_wrappers(text: str) -> str:
    """Remove ```json fences or leading/trailing quotes from LLM output."""
    text = text.strip()
    m = re.search(r"```(?:[a-zA-Z]+)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1]
    return text


@tool(
    name="translate_listing",
    description="Translate marketing copy (title, bullets, description) to a target language with native fluency.",
    tags=["llm", "i18n"],
)
def translate_listing(text: str, target_lang: str = "en") -> str:
    """Translate ``text`` to ``target_lang`` (e.g. 'en', 'de', 'ja')."""
    if not text or not text.strip():
        return ""
    llm = get_fast_llm()
    resp = llm.invoke(
        [
            SystemMessage(content=SYSTEM),
            HumanMessage(content=f"Target language: {target_lang}\n\n{text}"),
        ]
    )
    return _strip_wrappers(str(resp.content))
