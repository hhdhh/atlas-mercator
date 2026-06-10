"""Shared pytest fixtures for Atlas Mercator tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so ``import atlas_mercator`` works
# when tests are run from any working directory.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(_ROOT))


@pytest.fixture(scope="session")
def project_root() -> Path:
    return _ROOT


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force a clean Settings instance for every test."""
    from atlas_mercator import config

    config.reset_settings()
    # Provide deterministic defaults so tests don't depend on a real .env
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    yield
    config.reset_settings()
