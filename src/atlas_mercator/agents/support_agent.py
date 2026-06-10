"""SupportAgent — RAG-driven customer support for cross-border e-commerce."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from atlas_mercator.agents.base import AgentRunResult, BaseAgent
from atlas_mercator.observability.tracer import Tracer
from atlas_mercator.prompts.support_agent import SUPPORT_AGENT_SYSTEM_PROMPT
from atlas_mercator.tools.kb_tool import search_kb
from atlas_mercator.tools.support_tools import create_ticket, get_order


class SupportOutput(BaseModel):
    thought: str = ""
    intent: str = "other"
    answer: str = ""
    citations: list[dict[str, str]] = Field(default_factory=list)
    action_taken: str = "none"
    ticket_id: str | None = None


class SupportAgent(BaseAgent):
    """RAG-grounded support agent.  Uses ``search_kb`` for evidence."""

    name = "SupportAgent"
    system_prompt = SUPPORT_AGENT_SYSTEM_PROMPT

    def __init__(
        self,
        *,
        tracer: Tracer | None = None,
        top_k: int = 3,
        llm=None,
    ) -> None:
        super().__init__(tracer=tracer, llm=llm)
        self.top_k = top_k

    def handle(
        self,
        customer_message: str,
        *,
        order_id: str = "",
        customer_id: str = "",
    ) -> AgentRunResult:
        """Process a customer message end-to-end.

        Steps:
        1. Retrieve ``top_k`` KB chunks relevant to the message.
        2. Optionally pull order context.
        3. Ask Claude to produce a structured response.
        4. If the response says "created_ticket", open one in the CRM mock.
        """
        retrieved = search_kb(query=customer_message, top_k=self.top_k)
        orders = get_order(order_id=order_id, customer_id=customer_id)
        ctx: dict[str, Any] = {
            "retrieved_kb": [
                {"source": r["source"], "text": r["text"], "score": r.get("score")}
                for r in retrieved
            ],
            "order_summary": orders,
        }
        result = self.run(
            user_input=customer_message,
            extra_context=ctx,
            response_schema=SupportOutput,
        )
        # Side-effect: create the ticket if the agent decided to escalate.
        if result.parsed and result.parsed.get("action_taken") == "created_ticket":
            ticket = create_ticket(
                issue=customer_message,
                customer_id=customer_id or "anonymous",
                priority="normal",
            )
            result.parsed["ticket_id"] = ticket["ticket_id"]
        return result


__all__ = ["SupportAgent", "SupportOutput"]
