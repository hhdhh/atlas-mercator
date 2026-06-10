"""Command-line interface for Atlas Mercator.

This is the main entry point registered as the ``atlas`` script in
``pyproject.toml``. It also serves as a smoke test for the LLM
connection — if ``atlas ping`` returns a Claude answer, the whole
stack is wired up correctly.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel

from atlas_mercator.config import get_settings

console = Console()


def _cmd_ping(args: argparse.Namespace) -> int:
    """Smoke-test the Claude connection.

    Uses a tiny fast-model call to confirm that the API key, base URL,
    and SDK compatibility are all healthy. A failure here is almost
    always a credential/URL issue, not a code issue.
    """
    from atlas_mercator.llm import quick_chat

    try:
        reply = quick_chat(
            system="You are a connectivity test. Reply with the single word PONG.",
            user="ping",
        )
    except Exception as exc:  # pragma: no cover - reported to user
        console.print(Panel(f"[red]LLM call failed:[/red] {exc}", title="Ping failed"))
        return 1

    if "PONG" not in reply.upper():
        console.print(
            Panel(
                f"[yellow]Unexpected reply:[/yellow] {reply!r}\n(Continuing, but "
                "check that you are pointing at a Claude-compatible endpoint.)",
                title="Ping",
            )
        )
        return 0

    console.print(Panel(f"[green]✓ LLM reachable[/green]\n\nReply: {reply}", title="Ping OK"))
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    """Print the effective runtime configuration (with secrets redacted)."""
    settings = get_settings()
    safe: dict[str, Any] = {
        "anthropic_api_key": "***" if settings.anthropic_api_key else "(unset)",
        "anthropic_auth_token": "***" if settings.anthropic_auth_token else "(unset)",
        "anthropic_base_url": settings.anthropic_base_url,
        "model_default": settings.model_default,
        "model_fast": settings.model_fast,
        "temperature": settings.temperature,
        "log_level": settings.log_level,
        "lang": settings.lang,
        "chroma_dir": str(settings.chroma_dir),
        "embed_model": settings.embed_model,
        "kb_top_k": settings.kb_top_k,
    }
    console.print_json(data=safe)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="Atlas Mercator — multi-agent control plane.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ping = sub.add_parser("ping", help="Verify the LLM connection is healthy.")
    p_ping.set_defaults(func=_cmd_ping)

    p_cfg = sub.add_parser("config", help="Print the effective configuration.")
    p_cfg.set_defaults(func=_cmd_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
