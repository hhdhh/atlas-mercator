"""Gradio web demo for Atlas Mercator.

Six tabs, each one a sub-agent exposed as an interactive form:

1. **Atlas Orchestrator** — main stage; pick a preset workflow or type
   a free-form request, see token stream + tool-call trace.
2. **Listing Optimizer** — SKU + marketplace → 5-segment listing.
3. **Customer Support (RAG)** — customer message → RAG-grounded reply
   with citations and optional ticket creation.
4. **Marketing Copilot** — product + channel + audience → 3 A/B variants.
5. **Intel Scout** — competitor URL or preset → threat digest.
6. **Knowledge Base** — index stats and free-form semantic search.
"""

from __future__ import annotations

import json
import time
from typing import Any

import gradio as gr

from atlas_mercator.agents.intel_scout import IntelScout
from atlas_mercator.agents.listing_optimizer import ListingOptimizer as _ListingOptimizer
from atlas_mercator.agents.marketing_copilot import MarketingCopilot
from atlas_mercator.agents.support_agent import SupportAgent
from atlas_mercator.config import get_settings
from atlas_mercator.observability.tracer import Tracer
from atlas_mercator.rag.retriever import KBRetriever
from atlas_mercator.tools.competitor_tool import fetch_competitor_page
from atlas_mercator.tools.product_tools import get_inventory, search_products


# -- Helpers ---------------------------------------------------------------
def _product_choices() -> list[tuple[str, str]]:
    items = search_products(query="", limit=20)
    return [(f"{p['sku']} — {p['title_zh']}", p["sku"]) for p in items]


def _find_product(sku: str) -> dict[str, Any] | None:
    for p in search_products(query="", limit=20):
        if p["sku"] == sku:
            return p
    return None


# -- Tab 2: Listing Optimizer ---------------------------------------------
def run_listing_optimizer(sku: str, marketplace: str, language: str) -> tuple[str, str, str]:
    product = _find_product(sku)
    if product is None:
        return "❌ SKU not found", "", ""

    inv = get_inventory(sku)
    product_with_inv = {**product, "inventory": inv}

    agent = _ListingOptimizer()
    result = agent.optimize(
        product=product_with_inv, marketplace=marketplace, language=language
    )

    raw_md = f"**Model**: `{result.model or 'unknown'}` · **Latency**: {result.latency_ms} ms"
    if result.parsed is None:
        return raw_md + "\n\n⚠️ Could not parse JSON output. See raw reply below.", "", result.content

    listing = result.parsed
    bullets_md = "\n".join(f"- {b}" for b in listing.get("bullets", []))
    keywords_md = ", ".join(listing.get("keywords", []))
    compliance_md = "\n".join(f"- {n}" for n in listing.get("compliance_notes", [])) or "—"

    pretty = (
        f"### {listing.get('title', '')}\n\n"
        f"**Bullets**\n{bullets_md}\n\n"
        f"**Description**\n{listing.get('description', '')}\n\n"
        f"**Backend keywords**\n{keywords_md}\n\n"
        f"**Compliance**\n{compliance_md}\n\n"
        f"---\n*{listing.get('thought', '')}*"
    )
    return raw_md, pretty, json.dumps(listing, ensure_ascii=False, indent=2)


# -- Tab 3: Customer Support (RAG) ----------------------------------------
def run_support_agent(
    message: str, customer_id: str, order_id: str, open_ticket: bool
) -> tuple[str, str, str, str]:
    tracer = Tracer()
    agent = SupportAgent(tracer=tracer)
    result = agent.handle(
        customer_message=message,
        customer_id=customer_id or "",
        order_id=order_id or "",
    )
    parsed = result.parsed or {}
    citations_md = "\n".join(
        f"- `{c.get('source', '?')}` — {c.get('quote', '')[:140]}" for c in parsed.get("citations", [])
    ) or "_(no citations)_"
    retrieved = tracer.spans[-1].attributes.get("retrieved", []) if tracer.spans else []
    kb_md = "\n".join(
        f"- **{r['source']}** (score={r.get('score', 0):.2f}) — {r['text'][:120]}"
        for r in retrieved
    ) or "_(no KB chunks retrieved)_"

    meta = (
        f"**Model**: `{result.model}` · **Latency**: {result.latency_ms} ms · "
        f"**Intent**: `{parsed.get('intent', '?')}` · "
        f"**Action**: `{parsed.get('action_taken', '?')}`"
        + (f" · **Ticket**: `{parsed.get('ticket_id', '?')}`" if parsed.get("ticket_id") else "")
    )
    pretty = (
        f"### Reply\n{parsed.get('answer', result.content)}\n\n"
        f"### Citations\n{citations_md}\n\n"
        f"### RAG evidence\n{kb_md}"
    )
    return meta, pretty, json.dumps(parsed, ensure_ascii=False, indent=2), ""


# -- Tab 4: Marketing Copilot --------------------------------------------
def run_marketing_copilot(
    sku: str, channel: str, audience: str
) -> tuple[str, str, str]:
    product = _find_product(sku)
    if product is None:
        return "❌ SKU not found", "", ""
    agent = MarketingCopilot()
    result = agent.draft(product=product, channel=channel, audience=audience)
    parsed = result.parsed or {}
    variants = parsed.get("variants", [])
    pretty = "\n\n---\n\n".join(
        f"### Variant {v.get('label', '?')} ({v.get('angle', '?')})\n"
        f"{v.get('body', '')}\n\n"
        f"_Rationale_: {v.get('rationale', '')}\n\n"
        f"_Image prompt_: `{v.get('image_prompt', '')}`"
        for v in variants
    ) or "_(no variants)_"
    hashtags = " ".join("#" + h for h in parsed.get("hashtags", []))
    return (
        f"**Latency**: {result.latency_ms} ms · **Model**: `{result.model}`",
        pretty,
        hashtags,
    )


# -- Tab 5: Intel Scout --------------------------------------------------
_PRESET_COMPETITORS = [
    ("Amazon Best Seller — Earbuds", "amazon_bestseller_earbuds"),
    ("eBay DE — Smart Watch Deals", "ebay_deal_watch"),
    ("Shopify Niche — Yoga Mat", "shopify_niche_brand"),
]


def run_intel_scout(
    url: str, our_sku: str
) -> tuple[str, str, str]:
    raw = fetch_competitor_page(url=url)
    if "error" in raw:
        return f"❌ {raw['error']}", "", ""
    our_product = _find_product(our_sku) or {}
    agent = IntelScout()
    result = agent.scout(competitor_data=raw, our_product=our_product)
    parsed = result.parsed or {}
    diffs = "\n".join(
        f"- **Us**: {d.get('us', '')}  \n  **Them**: {d.get('them', '')}  \n  **Angle**: {d.get('angle', '')}"
        for d in parsed.get("differentiators", [])
    ) or "_(no differentiators)_"
    actions = "\n".join(f"- {a}" for a in parsed.get("recommended_actions", [])) or "_(none)_"
    threat = parsed.get("threat_score", {})
    pretty = (
        f"### Competitor\n"
        f"**{parsed.get('competitor_summary', {}).get('title', '')}** "
        f"— {parsed.get('competitor_summary', {}).get('price', '?')}\n\n"
        f"**Threat score** — price: {threat.get('price', '?')}/5, "
        f"quality: {threat.get('quality', '?')}/5, brand: {threat.get('brand', '?')}/5\n\n"
        f"### Differentiators\n{diffs}\n\n"
        f"### Recommended actions\n{actions}\n\n"
        f"---\n*{parsed.get('thought', '')}*"
    )
    return (
        f"**Latency**: {result.latency_ms} ms · **Model**: `{result.model}`",
        pretty,
        json.dumps(parsed, ensure_ascii=False, indent=2),
    )


# -- Tab 6: Knowledge Base ------------------------------------------------
def search_kb(query: str, top_k: int) -> str:
    r = KBRetriever()
    rows = r.query(query, top_k=top_k)
    return "\n\n---\n\n".join(
        f"### {row['source']} (score {row.get('score', 0):.3f})\n{row['text']}" for row in rows
    ) or "_(no results)_"


def kb_stats() -> str:
    r = KBRetriever()
    r._ensure_tfidf() if hasattr(r, "_ensure_tfidf") else None
    corpus = getattr(r, "_corpus", None)
    if corpus is None:
        return "_Retriever not yet initialised — run a query first._"
    sources: dict[str, int] = {}
    for s in corpus.sources:
        sources[s] = sources.get(s, 0) + 1
    rows = "\n".join(f"- `{k}`: {v} chunks" for k, v in sorted(sources.items()))
    return f"**Total chunks**: {len(corpus.texts)}\n\n**By source**:\n{rows}"


# -- Tab 1: Orchestrator (Phase C) ---------------------------------------
PRESET_REQUESTS = [
    ("🆕 New Market Launch — Earbuds US", "为 BB-EARBUD-001 做 Amazon US 上架文案，目标受众是 25-35 通勤族"),
    ("🆘 Customer Escalation — defective earbud", "客户 C1024 反馈蓝牙耳机左声道没声音，订单 ORD-20260417-001"),
    ("📣 Marketing A/B — Instagram", "为 BB-EARBUD-001 写 3 个 Instagram 文案，目标人群：25-35 通勤族"),
    ("🕵️ Intel — Amazon Best Seller", "分析 amazon_bestseller_earbuds 的竞品卖点"),
]


def run_orchestrator(request: str) -> tuple[str, list, list, str]:
    """Dispatch the request through the LangGraph orchestrator."""
    from atlas_mercator.orchestrator.workflows import (
        customer_escalation,
        intel_scan,
        marketing_ab_test,
        new_market_launch,
    )

    # Heuristic preset routing — saves one router LLM call.
    tracer = Tracer()
    if any(k in request for k in ["上架", "amazon_us", "Amazon US"]):
        state = new_market_launch(tracer=tracer)
    elif any(k in request for k in ["客诉", "C1024", "没声音", "退款"]):
        state = customer_escalation(message=request, tracer=tracer)
    elif any(k in request for k in ["Instagram", "instagram", "TikTok", "tiktok", "广告"]):
        state = marketing_ab_test(tracer=tracer)
    elif any(k in request for k in ["amazon_bestseller", "ebay_deal", "shopify", "竞品"]):
        state = intel_scan(tracer=tracer)
    else:
        # Fall back to the generic router
        from atlas_mercator.orchestrator.graph import run as run_graph

        state = run_graph(request, tracer=tracer)

    # Compose outputs for the Gradio widgets.
    plan = state.get("plan")
    final = state.get("final_answer", "")
    citations = state.get("citations", [])

    meta = (
        f"**Plan**: {plan.thought if plan else ''}\n\n"
        f"**Steps**: {len(state.get('step_results', []))}  ·  "
        f"**Citations**: {len(citations)}"
    )

    chat: list[tuple[str, str]] = [("user", request), ("assistant", final)]
    trace_rows = tracer.as_dataframe_rows()
    plan_dict = plan.model_dump() if plan else {}
    return meta, chat, trace_rows, plan_dict


# -- UI assembly ----------------------------------------------------------
def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Atlas Mercator") as demo:
        gr.Markdown(
            """
            # 🌍 Atlas Mercator
            **Multi-Agent Control Plane for Cross-Border E-Commerce** — production-style
            multi-agent system over LangChain + Claude + RAG + ERP/CRM-style tools.

            Use any tab to exercise one sub-agent. The **Orchestrator** tab ties them
            together with explicit ReAct reasoning (Phase C).
            """
        )

        # Tab 1: Orchestrator (Phase C wired)
        with gr.Tab("🧭 Atlas Orchestrator"):
            gr.Markdown(
                "**Plan → Dispatch → Synthesize** through the LangGraph supervisor. "
                "Click a preset or type any cross-cutting request; the orchestrator "
                "routes to the right sub-agents and renders a live tool-call trace."
            )
            with gr.Row():
                req = gr.Textbox(label="Your request", value=PRESET_REQUESTS[0][1], lines=3)
            preset_btns = [gr.Button(label, variant="secondary") for label, _ in PRESET_REQUESTS]
            for btn, (label, prompt) in zip(preset_btns, PRESET_REQUESTS):
                btn.click(fn=lambda p=prompt: p, outputs=req)
            with gr.Row():
                run = gr.Button("▶ Run Workflow", variant="primary")
            meta = gr.Markdown()
            with gr.Row():
                chat = gr.Chatbot(label="Conversation", height=300)
                trace = gr.Dataframe(
                    label="Tool-call trace",
                    headers=["step", "agent", "thought", "tool", "latency_ms", "model"],
                    datatype=["number", "str", "str", "str", "number", "str"],
                )
            final = gr.JSON(label="Final plan")
            run.click(fn=run_orchestrator, inputs=req, outputs=[meta, chat, trace, final])

        # Tab 2: Listing Optimizer
        with gr.Tab("🛒 Listing Optimizer"):
            with gr.Row():
                sku = gr.Dropdown(
                    label="Product SKU",
                    choices=_product_choices(),
                    value="BB-EARBUD-001" if _product_choices() else None,
                )
                marketplace = gr.Dropdown(
                    label="Target marketplace",
                    choices=[
                        ("Amazon US", "amazon_us"),
                        ("Amazon DE", "amazon_de"),
                        ("Amazon JP", "amazon_jp"),
                        ("eBay DE", "ebay_de"),
                        ("Shopee SG", "shopee_sg"),
                        ("TikTok US", "tiktok_us"),
                    ],
                    value="amazon_us",
                )
                language = gr.Dropdown(
                    label="Output language",
                    choices=[("English", "en"), ("German", "de"), ("Japanese", "ja"), ("Spanish", "es")],
                    value="en",
                )
            run_btn = gr.Button("✨ Generate Listing", variant="primary")
            meta = gr.Markdown()
            with gr.Row():
                pretty = gr.Markdown()
                raw = gr.Code(language="json", label="Raw JSON output")
            run_btn.click(
                fn=run_listing_optimizer,
                inputs=[sku, marketplace, language],
                outputs=[meta, pretty, raw],
            )

        # Tab 3: Customer Support (RAG)
        with gr.Tab("💬 Customer Support (RAG)"):
            with gr.Row():
                customer_id = gr.Textbox(label="Customer ID", value="C1024")
                order_id = gr.Textbox(label="Order ID (optional)", value="ORD-20260417-001")
            message = gr.Textbox(
                label="Customer message",
                lines=3,
                value="我的耳机左声道没声音了，怎么办？",
            )
            open_ticket = gr.Checkbox(label="Allow ticket creation if agent escalates", value=True)
            run_btn = gr.Button("🤝 Resolve", variant="primary")
            meta = gr.Markdown()
            with gr.Row():
                pretty = gr.Markdown()
                raw = gr.Code(language="json", label="Structured output")
            run_btn.click(
                fn=run_support_agent,
                inputs=[message, customer_id, order_id, open_ticket],
                outputs=[meta, pretty, raw, gr.State()],
            )

        # Tab 4: Marketing Copilot
        with gr.Tab("📣 Marketing Copilot"):
            with gr.Row():
                sku = gr.Dropdown(
                    label="Product SKU",
                    choices=_product_choices(),
                    value="BB-EARBUD-001" if _product_choices() else None,
                )
                channel = gr.Dropdown(
                    label="Channel",
                    choices=["instagram", "email_subject", "tiktok_hook", "facebook_ad"],
                    value="instagram",
                )
                audience = gr.Textbox(label="Target audience", value="commuters 25-35")
            run_btn = gr.Button("✨ Draft 3 variants", variant="primary")
            meta = gr.Markdown()
            with gr.Row():
                pretty = gr.Markdown()
                hashtags = gr.Textbox(label="Hashtags", interactive=False)
            run_btn.click(
                fn=run_marketing_copilot,
                inputs=[sku, channel, audience],
                outputs=[meta, pretty, hashtags],
            )

        # Tab 5: Intel Scout
        with gr.Tab("🕵️ Intel Scout"):
            with gr.Row():
                url = gr.Dropdown(
                    label="Competitor URL (preset or any string containing the key)",
                    choices=[(label, key) for label, key in _PRESET_COMPETITORS],
                    value="amazon_bestseller_earbuds",
                )
                our_sku = gr.Dropdown(
                    label="Our SKU (for differentiation)",
                    choices=_product_choices(),
                    value="BB-EARBUD-001" if _product_choices() else None,
                )
            run_btn = gr.Button("🔍 Scout", variant="primary")
            meta = gr.Markdown()
            with gr.Row():
                pretty = gr.Markdown()
                raw = gr.Code(language="json", label="Structured output")
            run_btn.click(
                fn=run_intel_scout,
                inputs=[url, our_sku],
                outputs=[meta, pretty, raw],
            )

        # Tab 6: Knowledge Base
        with gr.Tab("📚 Knowledge Base"):
            stats = gr.Markdown(value=kb_stats)
            with gr.Row():
                q = gr.Textbox(label="Query", value="蓝牙耳机无法配对")
                k = gr.Slider(label="top_k", minimum=1, maximum=10, value=3, step=1)
            run_btn = gr.Button("🔎 Search", variant="primary")
            result = gr.Markdown()
            run_btn.click(fn=search_kb, inputs=[q, k], outputs=result)
            gr.Button("Refresh stats").click(fn=kb_stats, outputs=stats)

    return demo


def main() -> None:
    demo = build_demo()
    demo.launch(server_name="127.0.0.1", server_port=7860, theme=gr.themes.Soft())


if __name__ == "__main__":  # pragma: no cover
    main()
