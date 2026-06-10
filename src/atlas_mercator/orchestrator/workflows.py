"""Pre-baked end-to-end workflows.

These are the two demo scenarios:

* ``new_market_launch`` — multi-step: intel → listing → (optional) translate.
* ``customer_escalation`` — multi-step: RAG diagnose → policy cite → ticket.

Each function returns the final graph state so the Gradio demo can
display the plan + step results.
"""

from __future__ import annotations

from typing import Any

from atlas_mercator.observability.tracer import Tracer
from atlas_mercator.orchestrator.graph import run as run_orchestrator


def new_market_launch(
    sku: str = "BB-EARBUD-001",
    marketplace: str = "amazon_us",
    extra_locales: list[str] | None = None,
    *,
    tracer: Tracer | None = None,
) -> dict[str, Any]:
    """End-to-end: scout → optimize → optional translation."""
    locales = ", ".join(extra_locales) if extra_locales else "(none)"
    request = (
        f"为 {sku} 做 {marketplace} 上架文案。先分析竞品，再写 Listing，"
        f"然后翻译到这些语种: {locales}。"
    )
    return run_orchestrator(request, tracer=tracer)


def customer_escalation(
    customer_id: str = "C1024",
    message: str = "我的蓝牙耳机左声道没声音了，怎么办？",
    *,
    tracer: Tracer | None = None,
) -> dict[str, Any]:
    """End-to-end: support agent triages the complaint, cites policy, opens a ticket."""
    request = (
        f"处理客户 {customer_id} 的客诉：{message}。"
        f"先查知识库找到答案，再决定是否需要建工单。"
    )
    return run_orchestrator(request, tracer=tracer)


def marketing_ab_test(
    sku: str = "BB-EARBUD-001",
    channel: str = "instagram",
    audience: str = "commuters 25-35",
    *,
    tracer: Tracer | None = None,
) -> dict[str, Any]:
    """Single-step: marketing copilot drafts variants."""
    request = f"为 {sku} 写 3 个 {channel} 文案，目标人群：{audience}。"
    return run_orchestrator(request, tracer=tracer)


def intel_scan(
    url: str = "amazon_bestseller_earbuds",
    *,
    tracer: Tracer | None = None,
) -> dict[str, Any]:
    """Single-step: intel scout digests a competitor page."""
    request = f"分析 {url} 的竞品卖点，提炼差异化要点。"
    return run_orchestrator(request, tracer=tracer)


__all__ = [
    "customer_escalation",
    "intel_scan",
    "marketing_ab_test",
    "new_market_launch",
]
