"""Order and Ticket schemas — the OMS/CRM-side contract."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    RETURNED = "returned"
    REFUNDED = "refunded"


class Order(BaseModel):
    """An order record from the OMS mock."""

    order_id: str
    customer_id: str
    sku: str
    qty: int = Field(..., ge=1)
    total_usd: float = Field(..., ge=0)
    status: OrderStatus
    placed_at: datetime
    delivered_at: datetime | None = None
    destination_country: str = Field(..., min_length=2, max_length=2)


class Ticket(BaseModel):
    """A support ticket created in the CRM mock."""

    ticket_id: str
    customer_id: str
    issue: str
    created_at: datetime
    resolution: str | None = None
    closed: bool = False
