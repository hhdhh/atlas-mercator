"""Support-side tools — mock the WMS (orders) and CRM (tickets) layers."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from atlas_mercator.tools.base import tool

_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "orders.json"

# In-memory ticket store.  A real implementation would write to a CRM
# like Salesforce / HubSpot / Zendesk; here we just keep it in process.
_ticket_lock = threading.Lock()
_tickets: list[dict[str, Any]] = []


@lru_cache(maxsize=1)
def _load_orders() -> list[dict[str, Any]]:
    if not _DATA_PATH.exists():
        return []
    with _DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@tool(
    name="get_order",
    description="Look up an order by order_id or customer_id. Returns order + shipping status.",
    tags=["oms", "read"],
)
def get_order(order_id: str = "", customer_id: str = "") -> list[dict[str, Any]]:
    """Return orders matching either ``order_id`` or ``customer_id``."""
    orders = _load_orders()
    out: list[dict[str, Any]] = []
    for o in orders:
        if order_id and o["order_id"].lower() == order_id.lower():
            out.append(o)
        elif customer_id and o["customer_id"].lower() == customer_id.lower():
            out.append(o)
    return out


@tool(
    name="create_ticket",
    description="Open a support ticket in the CRM. Returns the new ticket_id.",
    tags=["crm", "write"],
)
def create_ticket(issue: str, customer_id: str, priority: str = "normal") -> dict[str, Any]:
    """Create a ticket. ``priority`` is one of: low, normal, high, urgent."""
    ticket_id = f"T-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
    record = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "issue": issue,
        "priority": priority,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "closed": False,
    }
    with _ticket_lock:
        _tickets.append(record)
    return record


@tool(
    name="list_tickets",
    description="List tickets (most recent first). Optional customer_id filter.",
    tags=["crm", "read"],
)
def list_tickets(customer_id: str = "", limit: int = 10) -> list[dict[str, Any]]:
    """Return up to ``limit`` most-recent tickets, newest first."""
    rows = list(_tickets)
    if customer_id:
        rows = [t for t in rows if t["customer_id"] == customer_id]
    rows.reverse()
    return rows[: max(1, min(limit, 50))]
