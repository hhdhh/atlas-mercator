"""Product and Listing schemas — the PIM-side contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Product(BaseModel):
    """A product master record, roughly equivalent to a PIM entity."""

    sku: str = Field(..., description="Unique stock-keeping unit, e.g. 'BB-EARBUD-001'.")
    title_zh: str = Field(..., description="Original Chinese title.")
    category: str = Field(..., description="Marketplace category path.")
    price_usd: float = Field(..., ge=0)
    cost_usd: float = Field(..., ge=0)
    weight_g: int = Field(..., ge=0)
    origin: str = Field(..., description="City of origin in China, e.g. 'Shenzhen'.")
    stock: int = Field(..., ge=0)
    rating: float = Field(..., ge=0.0, le=5.0)
    image_prompt: str = Field("", description="Prompt for an image-generation tool.")

    @field_validator("sku")
    @classmethod
    def _sku_uppercase(cls, v: str) -> str:
        return v.strip().upper()


Marketplace = Literal[
    "amazon_us",
    "amazon_de",
    "amazon_jp",
    "ebay_de",
    "shopee_sg",
    "tiktok_us",
]


class Listing(BaseModel):
    """A localized, marketplace-ready listing."""

    sku: str
    marketplace: Marketplace
    language: str = Field(..., description="ISO 639-1, e.g. 'en', 'de', 'ja'.")
    title: str = Field(..., max_length=200)
    bullets: list[str] = Field(default_factory=list, max_length=5)
    description: str = Field("")
    keywords: list[str] = Field(default_factory=list)
    compliance_notes: list[str] = Field(default_factory=list)
