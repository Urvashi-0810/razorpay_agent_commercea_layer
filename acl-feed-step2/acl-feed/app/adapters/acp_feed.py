"""
Translates our canonical Product into a JSON feed shape meant to be consumed
directly by an agent or MCP tool (step 2 of the build) -- so unlike the CSV
adapter, relationships and prices stay as native nested types instead of
colon-delimited strings. This is our own schema, loosely ACP-flavored.
"""

from __future__ import annotations

from ..models import Product


def to_feed_item(product: Product) -> dict:
    item = {
        "id": product.id,
        "title": product.title,
        "description": product.description,
        "link": product.link,
        "brand": product.brand,
        "category": product.product_category,
        "condition": product.condition.value,
        "availability": product.availability.value,
        "inventory_quantity": product.inventory_quantity,
        "checkout_enabled": not product.disable_checkout,
        "price": {
            "amount": float(product.price_inr),
            "currency": "INR",
        },
        "signals": {
            "popularity_score": product.popularity_score,
            "review_count": product.review_count,
            "review_rating": product.review_rating,
        },
        "related_products": [
            {"relation": r.relation_type.value, "target_id": r.target_id}
            for r in product.related_products
        ],
    }
    if product.sale_price:
        item["price"]["sale_amount"] = float(product.sale_price.amount_inr)
        item["price"]["sale_window"] = {
            "starts_on": product.sale_price.starts_on.isoformat(),
            "ends_on": product.sale_price.ends_on.isoformat(),
        }
    return item


def to_feed(products: list[Product]) -> dict:
    return {
        "feed_version": "1.0",
        "currency": "INR",
        "product_count": len(products),
        "products": [to_feed_item(p) for p in products],
    }
