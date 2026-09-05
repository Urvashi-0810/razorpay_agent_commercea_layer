"""
Canonical product schema.

This is deliberately NOT any single platform's feed format. It's our own
internal "system of record" shape. Platform-specific feed adapters (see
adapters/) translate FROM this model TO whatever an agent surface (an
ACP-compatible checkout provider, a raw MCP tool call, etc.) expects. That
separation means adding a second output format later (e.g. a WooCommerce-
flavored feed) never touches this file.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Availability(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    PREORDER = "preorder"
    BACKORDER = "backorder"


class Condition(str, Enum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED = "used"


class RelationType(str, Enum):
    UPSELL = "upsell"
    CROSS_SELL = "cross_sell"
    SUBSTITUTE = "substitute"
    ACCESSORY = "accessory"


class RelatedProduct(BaseModel):
    """One edge in the product graph, e.g. 'this belt is an accessory for these jeans'."""
    relation_type: RelationType
    target_id: str


class SalePrice(BaseModel):
    amount_inr: Decimal
    starts_on: date
    ends_on: date


class Product(BaseModel):
    # --- basic identity ---
    id: str = Field(..., max_length=100, description="Merchant SKU, unique.")
    title: str = Field(..., max_length=150)
    description: str = Field(..., max_length=5000)
    link: str = Field(..., description="Canonical product page URL on the merchant's own site.")
    brand: str = Field(..., max_length=70)
    product_category: str = Field(..., description="e.g. 'Apparel > Footwear > Sneakers'")
    condition: Condition = Condition.NEW

    # --- availability ---
    availability: Availability
    inventory_quantity: int = Field(..., ge=0)

    # --- price (INR only for this build; Razorpay-first) ---
    price_inr: Decimal = Field(..., gt=0)
    sale_price: Optional[SalePrice] = None

    # --- checkout eligibility ---
    disable_checkout: bool = Field(
        default=False,
        description="If true, product is discoverable by agents but purchase redirects to `link` instead of in-agent checkout.",
    )

    # --- signals that help an agent rank/recommend ---
    popularity_score: Optional[float] = Field(default=None, ge=0, le=5)
    review_count: Optional[int] = Field(default=None, ge=0)
    review_rating: Optional[float] = Field(default=None, ge=1, le=5)

    # --- the growth hook: explicit upsell/cross-sell graph ---
    related_products: list[RelatedProduct] = Field(default_factory=list)

    @field_validator("review_rating")
    @classmethod
    def rating_requires_count(cls, v, info):
        count = info.data.get("review_count")
        if v is not None and (count is None or count == 0):
            raise ValueError("review_rating requires review_count > 0")
        return v


class ProductUpsert(Product):
    """Same shape as Product; kept as a distinct name so the API layer can
    later diverge (e.g. allow partial updates) without touching the storage model."""
    pass
