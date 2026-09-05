"""
Translates our canonical Product into the open Agentic Commerce Protocol
(ACP) product feed CSV format -- the same column-based catalog shape used
across agentic checkout surfaces (ChatGPT commerce, agent-facing checkout
providers, etc).

Only the MVP subset of the ~40-column full spec is emitted, matching what
our canonical model actually captures. Columns the full spec would otherwise
require (gtin/mpn, images, shipping, tax codes) are intentionally left out
for this build and can be added here later without touching models.py.
"""

from __future__ import annotations

import csv
import io

from ..models import Product

# Column order matters for a clean CSV; keep it stable.
ACP_CSV_COLUMNS = [
    "id",
    "title",
    "description",
    "link",
    "brand",
    "product_category",
    "condition",
    "availability",
    "inventory_quantity",
    "price",
    "sale_price",
    "sale_price_effective_date",
    "disable_checkout",
    "popularity_score",
    "product_review_count",
    "product_review_rating",
    "related_products",
]


def _money(amount) -> str:
    return f"{amount:.2f} INR"


def _related_products(product: Product) -> str:
    if not product.related_products:
        return ""
    return ",".join(f"{r.relation_type.value}:{r.target_id}" for r in product.related_products)


def to_csv_row(product: Product) -> dict:
    row = {
        "id": product.id,
        "title": product.title,
        "description": product.description,
        "link": product.link,
        "brand": product.brand,
        "product_category": product.product_category,
        "condition": product.condition.value,
        "availability": product.availability.value,
        "inventory_quantity": product.inventory_quantity,
        "price": _money(product.price_inr),
        "sale_price": "",
        "sale_price_effective_date": "",
        "disable_checkout": str(product.disable_checkout).lower(),
        "popularity_score": product.popularity_score if product.popularity_score is not None else "",
        "product_review_count": product.review_count if product.review_count is not None else "",
        "product_review_rating": product.review_rating if product.review_rating is not None else "",
        "related_products": _related_products(product),
    }
    if product.sale_price:
        row["sale_price"] = _money(product.sale_price.amount_inr)
        row["sale_price_effective_date"] = (
            f"{product.sale_price.starts_on.isoformat()}/{product.sale_price.ends_on.isoformat()}"
        )
    return row


def to_csv_feed(products: list[Product]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ACP_CSV_COLUMNS)
    writer.writeheader()
    for p in products:
        writer.writerow(to_csv_row(p))
    return buf.getvalue()
