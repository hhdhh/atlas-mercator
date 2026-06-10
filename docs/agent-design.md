# Atlas Mercator — Agent Design Notes

## Prompt Pattern

Every sub-agent prompt follows the same five-section template:

1. **Role** — who the agent is, in 1-2 sentences.
2. **Reasoning scaffold** — explicit THOUGHT → ACT → OBSERVE steps.
3. **Input contract** — JSON shape of what the agent receives.
4. **Output schema** — JSON the agent MUST return, with field-level constraints.
5. **Hard rules** — what the agent MUST NOT do (fabricate, hallucinate, etc).

This is the same pattern that Anthropic's own agent cookbook uses
(``claude-cookbooks/patterns/agents``) and it composes well: a tool error
becomes a single line in OBSERVE, and a malformed JSON becomes a one-line
retry in the agent runtime.

## ReAct vs Function-Calling

We use **ReAct-style explicit reasoning** for the orchestrator and
**structured function-calling** for the sub-agents. The split is intentional:

* The orchestrator is *open-ended* — it has to decide which sub-agent to
  call. We want the model to articulate its decision (THOUGHT) so the
  trace is auditable.
* The sub-agents are *closed-form* — they have a fixed input → fixed
  output schema. Forcing them to also produce a thought is useful for
  debugging, but the output is validated as structured JSON.

## Why Not Pure Tool-Use?

Tool-use (a.k.a. function-calling) is excellent for *single-step* lookups.
It is awkward for *multi-step* reasoning because the model has no
incentive to articulate *why* it picked tool A over tool B — that
information is lost in the next turn. ReAct keeps the reasoning in the
state stream, which is what we want for an auditable, resumable workflow.

## Schema Sanitization

The biggest failure mode of ReAct agents is malformed JSON. We guard
against it in three places:

1. **System prompt** — every prompt tells the model the exact output
   schema and says "return ONLY this JSON".
2. **Parser** — `BaseAgent._parse_json` does a best-effort extraction
   (fenced code block, then first {...} span).
3. **Validator** — the parsed dict is fed through the agent's Pydantic
   output model; mismatches are logged but do not crash the agent.

This is the "schema sanitizer" pattern from the user's existing
``.openclaw`` Agent infrastructure.

## When to Extend

| If you need… | Add… |
|---|---|
| A new tool | `@tool(name=..., description=...)` in `src/atlas_mercator/tools/`. |
| A new sub-agent | `agents/<name>.py` + `prompts/<name>.py` + a Gradio tab in `web/gradio_app.py`. |
| A new end-to-end workflow | `orchestrator/workflows.py` (Phase C). |
| A new KB source | drop the file in `data/` + extend `rag/indexer.py:_load_*`. |

All extensions follow the same five-section prompt template and the same
Pydantic-typed tool contract.
