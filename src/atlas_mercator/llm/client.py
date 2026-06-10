"""LLM client factory.

This module hides the differences between:

* a direct Anthropic API call,
* a proxy like MiniMax that re-exports the Anthropic protocol.

The factory reads environment variables via :mod:`atlas_mercator.config` and
returns a :class:`langchain_anthropic.ChatAnthropic` ready to be used in
chains, agents, or directly.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from atlas_mercator.config import Settings, get_settings


def _build_client(model: str, settings: Settings, **overrides: Any) -> ChatAnthropic:
    """Build a :class:`ChatAnthropic` from settings + overrides.

    Authentication is handled in this order:

    1. ``ANTHROPIC_AUTH_TOKEN`` (proxy / MiniMax style bearer token)
    2. ``ANTHROPIC_API_KEY`` (official Anthropic key)
    """
    auth_token = settings.anthropic_auth_token or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": settings.temperature,
        "max_tokens": 4096,
        "anthropic_api_url": settings.anthropic_base_url,
    }
    if auth_token:
        kwargs["api_key"] = auth_token
    elif api_key:
        kwargs["api_key"] = api_key
    else:
        raise RuntimeError(
            "No Anthropic credentials found. Set ANTHROPIC_API_KEY "
            "(or ANTHROPIC_AUTH_TOKEN for proxies) in your environment."
        )

    kwargs.update(overrides)
    return ChatAnthropic(**kwargs)


def get_llm(model: str | None = None, **overrides: Any) -> ChatAnthropic:
    """Return a :class:`ChatAnthropic` for ``model`` (or default)."""
    settings = get_settings()
    return _build_client(model or settings.model_default, settings, **overrides)


def get_default_llm(**overrides: Any) -> ChatAnthropic:
    """Default LLM (high quality, used by orchestrator + sub-agents)."""
    return get_llm(**overrides)


def get_fast_llm(**overrides: Any) -> ChatAnthropic:
    """Fast/cheap LLM (used by translation/keyword tools)."""
    settings = get_settings()
    return _build_client(settings.model_fast, settings, **overrides)


def quick_chat(system: str, user: str, model: str | None = None) -> str:
    """One-shot chat convenience — useful in scripts and tests.

    >>> from atlas_mercator.llm.client import quick_chat
    >>> quick_chat("You are a JSON validator.", '{"a": 1}')  # doctest: +SKIP
    """
    llm = get_llm(model=model)
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return str(resp.content)
