# Atlas Mercator — Roadmap

## v0.1.0 (current)

- 1 Orchestrator scaffold + 4 sub-agents
- 9 Pydantic-typed tools (mock ERP/CRM + real LLM content tools)
- TF-IDF + Chroma RAG over 20 FAQ + 3 policy docs
- Gradio 6-tab demo
- 43 unit tests, 65% coverage
- Conventional-Commits-ready Git history

## v0.2 — Observability & Reliability

- LangSmith integration for full request tracing
- Token usage dashboard in the Gradio sidebar
- Per-tool retry with exponential backoff
- Schema-sanitizer auto-retry (one re-prompt on parse failure)

## v0.3 — Real Connectors

- Shopify Admin API (replace `get_inventory`, `search_products`)
- Zendesk / HubSpot (replace `create_ticket`, `get_order`)
- Bing Shopping + eBay Browse (replace `fetch_competitor_page`)
- All swaps live behind the same Pydantic tool contract.

## v0.4 — MCP Server

- Expose the orchestrator as an MCP server so other agents (Claude Desktop,
  custom IDE plugins, internal dashboards) can call `atlas_orchestrate`
  directly.

## v0.5 — Hugging Face Spaces Deployment

- Containerize the Gradio app
- Add a `spaces/Dockerfile` and `spaces/README.md`
- CI: build + push on tag

## Backlog (no version yet)

- Multi-tenant user accounts (Langfuse + Supabase)
- Persistent chat history
- Real-time token streaming in the Orchestrator tab
- A/B test result ingestion (Variant → outcome → model retrain)
- i18n for the Gradio UI itself (English / Chinese / Spanish)
