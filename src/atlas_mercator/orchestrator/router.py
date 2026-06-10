"""Intent router — turns a free-form user request into a structured plan.

The router is a thin LLM call: it parses the user input into the
``OrchestratorPlan`` schema.  Heavy lifting (sub-agent invocation,
tool calls, citation) lives in :mod:`atlas_mercator.orchestrator.graph`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from atlas_mercator.config import get_settings
from atlas_mercator.llm import get_default_llm
from atlas_mercator.observability.tracer import Tracer
from atlas_mercator.prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT
from atlas_mercator.schemas.intent import OrchestratorPlan


_HEURISTIC_HINTS: list[tuple[str, str, list[str]]] = [
    ("listing", "上架", ["listing", "上架", "amazon", "ebay", "shopee", "tiktok"]),
    ("support", "客服", ["客服", "退货", "保修", "运费", "怎么", "不能", "坏", "投诉", "support"]),
    ("marketing", "营销", ["营销", "instagram", "tiktok", "facebook", "文案", "广告", "email"]),
    ("intel", "竞品", ["竞品", "对比", "分析", "竞争对手", "intel", "competitor", "scout"]),
]


def _heuristic_intent(text: str) -> str | None:
    """Return a best-guess intent from a few simple keyword buckets.

    This is a fast path used when the LLM call is unavailable or as a
    sanity check on the LLM's output.
    """
    lowered = text.lower()
    scores: dict[str, int] = {}
    for intent, _label, words in _HEURISTIC_HINTS:
        scores[intent] = sum(1 for w in words if w in lowered)
    best = max(scores.values())
    if best == 0:
        return None
    for intent, score in scores.items():
        if score == best:
            return intent
    return None


def route(
    user_request: str, *, tracer: Tracer | None = None
) -> OrchestratorPlan:
    """Parse ``user_request`` into a structured plan.

    Falls back to a heuristic intent if the LLM output is unparseable.
    """
    settings = get_settings()
    llm = get_default_llm()
    tracer = tracer or Tracer()
    fallback_intent = _heuristic_intent(user_request) or "mixed"

    with tracer.span("router", user_request) as span:
        try:
            resp = llm.invoke(
                [
                    SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
                    HumanMessage(content=user_request),
                ]
            )
            text = str(resp.content)
            parsed = _parse_plan(text)
            if parsed is None:
                raise ValueError("could not parse plan JSON")
        except Exception as exc:
            span.log(f"router LLM failed ({exc}); using heuristic {fallback_intent}")
            parsed = OrchestratorPlan(
                thought=f"Heuristic dispatch: {fallback_intent}",
                plan=[],
            )
        # If the LLM didn't return any plan steps, seed one with the fallback intent.
        if not parsed.plan and parsed.clarifying_question is None:
            from atlas_mercator.schemas.intent import AgentStep

            parsed.plan = [
                AgentStep(
                    step=1,
                    owner=f"{fallback_intent}_agent:handle",
                    action=f"Process request: {user_request[:140]}",
                    expected_output=f"{fallback_intent} result",
                )
            ]
        span.set("intent", fallback_intent)
        span.set("plan_steps", len(parsed.plan))
        return parsed


def _parse_plan(text: str) -> OrchestratorPlan | None:
    """Best-effort parse of the orchestrator JSON output."""
    candidates: list[str] = [text]
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        candidates.insert(0, m.group(1))
    s = text.find("{")
    e = text.rfind("}")
    if 0 <= s < e:
        candidates.append(text[s : e + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            if not isinstance(obj, dict):
                continue
            return OrchestratorPlan.model_validate(obj)
        except Exception:
            continue
    return None
