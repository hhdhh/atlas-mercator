"""Application configuration loaded from environment variables.

We use pydantic Settings so configuration is type-checked at boot and any
missing required value fails fast instead of producing cryptic errors deep
in a tool call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level runtime settings.

    Values are read from environment variables (and an optional ``.env`` file).
    The class is intentionally side-effect free; use :func:`get_settings` for
    a process-wide singleton.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="ATLAS_",
    )

    # --- LLM Provider (Anthropic / Claude) ---------------------------------
    # We read the upstream env vars directly because pydantic-settings' env
    # prefix is a single value. These mirror the names Claude tooling expects.
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key. Falls back to ANTHROPIC_API_KEY env.",
        validation_alias="ANTHROPIC_API_KEY",
    )
    anthropic_auth_token: str = Field(
        default="",
        description="Optional proxy bearer token. Falls back to ANTHROPIC_AUTH_TOKEN env.",
        validation_alias="ANTHROPIC_AUTH_TOKEN",
    )
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com",
        description="Anthropic base URL. Falls back to ANTHROPIC_BASE_URL env.",
        validation_alias="ANTHROPIC_BASE_URL",
    )

    model_default: str = Field(
        default="claude-sonnet-4-6",
        description="Default Claude model for the orchestrator and quality-critical agents.",
    )
    model_fast: str = Field(
        default="claude-haiku-4-5",
        description="Fast Claude model for translation / keyword extraction tools.",
    )
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)

    # --- Runtime ----------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    lang: Literal["zh-CN", "en-US"] = "zh-CN"

    # --- RAG ---------------------------------------------------------------
    chroma_dir: Path = Field(default=Path("./.chroma"))
    embed_model: str = Field(default="all-MiniLM-L6-v2")
    kb_top_k: int = Field(default=3, ge=1, le=10)
    rag_backend: Literal["auto", "sentence-transformers", "tfidf"] = Field(
        default="auto",
        description=(
            "RAG embedding backend. 'auto' tries sentence-transformers first "
            "and falls back to TF-IDF on failure; 'tfidf' skips the network "
            "load entirely."
        ),
    )

    # --- Project layout ----------------------------------------------------
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "data")


_settings_singleton: Settings | None = None


def get_settings() -> Settings:
    """Return a lazily-instantiated :class:`Settings` (singleton)."""
    global _settings_singleton
    if _settings_singleton is None:
        _settings_singleton = Settings()
    return _settings_singleton


def reset_settings() -> None:
    """Reset the singleton — useful in tests after monkey-patching env vars."""
    global _settings_singleton
    _settings_singleton = None
