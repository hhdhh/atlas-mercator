"""LangGraph orchestrator state machine.

We model the workflow as a small, explicit state graph:

```
            ┌──────────────────────┐
            │  start               │
            └─────────┬────────────┘
                      ▼
            ┌──────────────────────┐
            │  router              │  parse intent + plan
            └─────────┬────────────┘
                      ▼
            ┌──────────────────────┐
            │  dispatch            │  run sub-agents per plan step
            └─────────┬────────────┘
                      ▼
            ┌──────────────────────┐
            │  synthesize          │  write final answer w/ citations
            └─────────┬────────────┘
                      ▼
            ┌──────────────────────┐
            │  end                 │
            └──────────────────────┘
```

A real production graph would add retry / checkpoint nodes; for the
MVP we keep it small and easy to inspect.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from atlas_mercator.agents.intel_scout import IntelScout
from atlas_mercator.agents.listing_optimizer import ListingOptimizer
from atlas_mercator.agents.marketing_copilot import MarketingCopilot
from atlas_mercator.agents.support_agent import SupportAgent
from atlas_mercator.observability.tracer import Tracer
from atlas_mercator.orchestrator.router import route
from atlas_mercator.schemas.intent import OrchestratorPlan
from atlas_mercator.tools.product_tools import get_inventory, search_products


# -- Graph state ---------------------------------------------------------
class OrchestratorState(TypedDict, total=False):
    """Shared state that flows through the orchestrator graph."""

    user_request: str
    plan: OrchestratorPlan
    step_results: list[dict[str, Any]]
    final_answer: str
    citations: list[dict[str, str]]
    tracer: Annotated[Tracer, "ignore"]  # not serialised, but carried


# -- Sub-agent registry -------------------------------------------------
def _resolve_sub_agent(owner: str) -> Any:
    """Map an ``owner`` string like ``listing_optimizer:optimize`` to an instance."""
    name = owner.split(":", 1)[0].strip().lower()
    if "listing" in name:
        return ListingOptimizer(), "optimize"
    if "support" in name:
        return SupportAgent(), "handle"
    if "marketing" in name:
        return MarketingCopilot(), "draft"
    if "intel" in name:
        return IntelScout(), "scout"
    raise ValueError(f"Unknown sub-agent owner: {owner!r}")


# -- Graph nodes --------------------------------------------------------
def _node_router(state: OrchestratorState) -> OrchestratorState:
    tracer: Tracer = state.get("tracer") or Tracer()  # type: ignore[assignment]
    plan = route(state["user_request"], tracer=tracer)
    return {**state, "plan": plan, "tracer": tracer}


def _node_dispatch(state: OrchestratorState) -> OrchestratorState:
    tracer: Tracer = state.get("tracer") or Tracer()  # type: ignore[assignment]
    plan: OrchestratorPlan = state.get("plan")  # type: ignore[assignment]
    results: list[dict[str, Any]] = []
    if not plan or not plan.plan:
        return {**state, "step_results": results, "tracer": tracer}

    for step in plan.plan:
        owner = step.owner
        action = step.action
        with tracer.span(f"dispatch:{owner}", action) as span:
            try:
                agent, method = _resolve_sub_agent(owner)
                fn = getattr(agent, method)
                # Sub-agents accept (product=...) for listing/marketing, etc.
                # We do best-effort keyword dispatch.
                if isinstance(agent, ListingOptimizer):
                    sku = _first_sku(state["user_request"]) or "BB-EARBUD-001"
                    product = _find_product(sku) or {}
                    inv = get_inventory(sku)
                    r = fn(product={**product, "inventory": inv}, marketplace="amazon_us", language="en")
                elif isinstance(agent, MarketingCopilot):
                    sku = _first_sku(state["user_request"]) or "BB-EARBUD-001"
                    product = _find_product(sku) or {}
                    r = fn(product=product, channel="instagram", audience="commuters 25-35")
                elif isinstance(agent, SupportAgent):
                    r = fn(customer_message=state["user_request"], customer_id="C1024")
                elif isinstance(agent, IntelScout):
                    from atlas_mercator.tools.competitor_tool import fetch_competitor_page

                    page = fetch_competitor_page(url="amazon_bestseller_earbuds")
                    r = fn(competitor_data=page)
                else:
                    r = None
                span.set("latency_ms", getattr(r, "latency_ms", 0))
                span.set("model", getattr(r, "model", ""))
                results.append(
                    {
                        "step": step.step,
                        "owner": owner,
                        "action": action,
                        "parsed": getattr(r, "parsed", None),
                        "raw": getattr(r, "content", ""),
                        "latency_ms": getattr(r, "latency_ms", 0),
                    }
                )
            except Exception as exc:  # pragma: no cover - logged via span
                span.log(f"dispatch failed: {exc}")
                results.append({"step": step.step, "owner": owner, "error": str(exc)})
    return {**state, "step_results": results, "tracer": tracer}


def _node_synthesize(state: OrchestratorState) -> OrchestratorState:
    """Write a final answer that cites the producing agent for each part."""
    plan: OrchestratorPlan = state.get("plan")  # type: ignore[assignment]
    results = state.get("step_results", [])
    if not results:
        return {**state, "final_answer": "_no steps executed_", "citations": []}

    bullets: list[str] = []
    citations: list[dict[str, str]] = []
    for r in results:
        if "error" in r:
            bullets.append(f"- step {r['step']} ({r['owner']}) failed: {r['error']}")
            continue
        owner = r["owner"]
        parsed = r.get("parsed") or {}
        if isinstance(parsed, dict) and parsed.get("title"):
            bullets.append(f"- **{owner}** → `{parsed.get('title')[:80]}`")
        elif isinstance(parsed, dict) and parsed.get("answer"):
            bullets.append(f"- **{owner}** → {parsed.get('answer')[:140]}")
            for c in parsed.get("citations", []):
                citations.append(c)
        elif isinstance(parsed, dict) and parsed.get("variants"):
            n = len(parsed.get("variants", []))
            bullets.append(f"- **{owner}** → {n} marketing variants drafted")
        elif isinstance(parsed, dict) and parsed.get("competitor_summary"):
            cs = parsed["competitor_summary"]
            bullets.append(f"- **{owner}** → competitor: {cs.get('title', '?')} @ {cs.get('price', '?')}")
        else:
            bullets.append(f"- **{owner}** → produced output")

    final = (
        f"**Plan**: {plan.thought if plan else ''}\n\n"
        + "**Results**\n"
        + "\n".join(bullets)
    )
    return {**state, "final_answer": final, "citations": citations}


# -- Helpers -------------------------------------------------------------
def _find_product(sku: str) -> dict[str, Any] | None:
    for p in search_products(query="", limit=20):
        if p["sku"] == sku:
            return p
    return None


def _first_sku(text: str) -> str | None:
    import re

    m = re.search(r"\b([A-Z]{2,4}-[A-Z0-9]+-\d{3})\b", text)
    return m.group(1) if m else None


# -- Graph assembly ------------------------------------------------------
def build_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("router", _node_router)
    g.add_node("dispatch", _node_dispatch)
    g.add_node("synthesize", _node_synthesize)
    g.add_edge(START, "router")
    g.add_edge("router", "dispatch")
    g.add_edge("dispatch", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()


def run(user_request: str, *, tracer: Tracer | None = None) -> dict[str, Any]:
    """Top-level convenience: build the graph, run it, return the final state."""
    graph = build_graph()
    state: OrchestratorState = {
        "user_request": user_request,
        "tracer": tracer or Tracer(),
    }
    out = graph.invoke(state)
    return out
