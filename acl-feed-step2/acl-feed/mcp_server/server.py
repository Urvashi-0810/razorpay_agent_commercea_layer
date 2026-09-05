"""
Razorpay ACL — Step 2: MCP tool server.

Exposes the merchant catalog (step 1's feed generator) to any MCP-compatible
agent as five tools: search_products, get_product, add_to_cart, view_cart,
checkout. Run from the acl-feed/ directory with:
    python -m mcp_server.server
(stdio transport) and point Claude Desktop / Claude Code at it.

checkout() intentionally stops at "order finalized, ready for payment" --
step 3 wires in Razorpay Order + Payment Link creation at that exact seam.
"""

from __future__ import annotations

# from mcp.server.fastmcp import FastMCP
from mcp.server.mcpserver import MCPServer

from . import cart_store, client

mcp = MCPServer("razorpay-acl")

MAX_SEARCH_RESULTS = 10
MAX_SUGGESTIONS = 3


def _price_summary(product: dict) -> dict:
    return {"amount_inr": float(product["price_inr"]), "currency": "INR"}


@mcp.tool()
async def search_products(
    query: str = "",
    category: str | None = None,
    max_price_inr: float | None = None,
) -> list[dict]:
    """
    Search the merchant's product catalog.

    Args:
        query: Free-text match against product title, description, and category.
        category: Optional exact/substring filter on product category
            (e.g. "Footwear", "Outerwear").
        max_price_inr: Optional upper price bound in INR.

    Returns up to 10 matching products ranked by popularity, each with id,
    title, price, availability, and rating -- enough to decide what to look
    at next with get_product.
    """
    catalog = await client.get_full_catalog(only_in_stock=True)
    results = []
    q = query.lower().strip()

    for p in catalog["products"]:
        haystack = f"{p['title']} {p['description']} {p['category']}".lower()
        if q and q not in haystack:
            continue
        if category and category.lower() not in p["category"].lower():
            continue
        if max_price_inr is not None and p["price"]["amount"] > max_price_inr:
            continue
        results.append(p)

    results.sort(key=lambda p: p["signals"]["popularity_score"] or 0, reverse=True)
    results = results[:MAX_SEARCH_RESULTS]

    return [
        {
            "id": p["id"],
            "title": p["title"],
            "price": p["price"],
            "availability": p["availability"],
            "review_rating": p["signals"]["review_rating"],
        }
        for p in results
    ]


@mcp.tool()
async def get_product(product_id: str) -> dict:
    """
    Get full detail on a single product, including resolved recommendations
    (upsell / cross-sell / accessory items) with their own titles and prices
    -- not just raw IDs -- so you can mention them naturally in conversation.
    """
    product = await client.get_product_detail(product_id)
    if product is None:
        return {"error": f"No product with id '{product_id}'."}

    resolved_related = []
    for rel in product.get("related_products", []):
        target = await client.get_product_detail(rel["target_id"])
        if target:
            resolved_related.append(
                {
                    "relation": rel["relation_type"],
                    "id": target["id"],
                    "title": target["title"],
                    "price": _price_summary(target),
                    "availability": target["availability"],
                }
            )

    return {
        "id": product["id"],
        "title": product["title"],
        "description": product["description"],
        "brand": product["brand"],
        "category": product["product_category"],
        "price": _price_summary(product),
        "availability": product["availability"],
        "inventory_quantity": product["inventory_quantity"],
        "review_rating": product.get("review_rating"),
        "review_count": product.get("review_count"),
        "you_might_also_want": resolved_related,
    }


async def _price_cart(cart_id: str) -> dict:
    """Re-fetches current prices/stock for every line item -- never trust a cached price."""
    items = cart_store.get_items(cart_id) or {}
    line_items = []
    subtotal = 0.0
    suggested_ids_seen = set(items.keys())
    suggestions = []

    for product_id, quantity in items.items():
        product = await client.get_product_detail(product_id)
        if product is None:
            continue
        line_total = float(product["price_inr"]) * quantity
        subtotal += line_total
        line_items.append(
            {
                "product_id": product_id,
                "title": product["title"],
                "quantity": quantity,
                "unit_price_inr": float(product["price_inr"]),
                "line_total_inr": line_total,
                "in_stock": product["availability"] == "in_stock"
                and product["inventory_quantity"] >= quantity,
            }
        )

        for rel in product.get("related_products", []):
            if rel["target_id"] in suggested_ids_seen or len(suggestions) >= MAX_SUGGESTIONS:
                continue
            target = await client.get_product_detail(rel["target_id"])
            if target and target["availability"] == "in_stock":
                suggestions.append(
                    {
                        "relation": rel["relation_type"],
                        "id": target["id"],
                        "title": target["title"],
                        "price": _price_summary(target),
                    }
                )
                suggested_ids_seen.add(rel["target_id"])

    return {
        "cart_id": cart_id,
        "items": line_items,
        "subtotal_inr": round(subtotal, 2),
        "currency": "INR",
        "suggested_addons": suggestions,
    }


@mcp.tool()
async def add_to_cart(product_id: str, quantity: int = 1, cart_id: str | None = None) -> dict:
    """
    Add a product to a cart, creating a new cart if cart_id is omitted or unknown.

    Validates current stock before adding. Returns the updated cart, including
    freshly-priced line items and up to 3 suggested add-ons based on what's
    already in the cart -- surface these to the shopper before checkout.
    """
    if not cart_id or not cart_store.cart_exists(cart_id):
        cart_id = cart_store.new_cart()

    product = await client.get_product_detail(product_id)
    if product is None:
        return {"error": f"No product with id '{product_id}'."}
    if product["availability"] != "in_stock":
        return {"error": f"'{product['title']}' is currently {product['availability']}."}
    if quantity > product["inventory_quantity"]:
        return {
            "error": (
                f"Only {product['inventory_quantity']} of '{product['title']}' "
                f"in stock; requested {quantity}."
            )
        }

    cart_store.add_quantity(cart_id, product_id, quantity)
    return await _price_cart(cart_id)


@mcp.tool()
async def view_cart(cart_id: str) -> dict:
    """View the current contents of a cart, freshly re-priced."""
    if not cart_store.cart_exists(cart_id):
        return {"error": f"No cart with id '{cart_id}'."}
    return await _price_cart(cart_id)


@mcp.tool()
async def checkout(cart_id: str, customer_name: str, customer_phone: str) -> dict:
    """
    Finalize a cart into an order summary, ready for payment.

    This does NOT move money -- it validates the cart one last time and
    returns a finalized total. Payment execution (Razorpay Order + Payment
    Link, human taps to pay) is wired in at step 3.
    """
    if not cart_store.cart_exists(cart_id):
        return {"error": f"No cart with id '{cart_id}'."}

    priced = await _price_cart(cart_id)
    if not priced["items"]:
        return {"error": "Cart is empty."}

    out_of_stock = [i for i in priced["items"] if not i["in_stock"]]
    if out_of_stock:
        return {
            "error": "Some items are no longer available at the requested quantity.",
            "affected_items": out_of_stock,
        }

    return {
        "status": "AWAITING_PAYMENT_INTEGRATION",
        "cart_id": cart_id,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "order_total_inr": priced["subtotal_inr"],
        "currency": "INR",
        "line_items": priced["items"],
        "message": (
            "Order finalized. Payment execution not yet wired up -- "
            "step 3 will create a Razorpay Order + Payment Link here."
        ),
    }


if __name__ == "__main__":
    mcp.run()
