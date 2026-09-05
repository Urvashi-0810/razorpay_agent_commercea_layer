# Razorpay ACL — Step 1: Feed Generator

Turns a merchant's product catalog (SQLite-backed here) into two agent-consumable feed formats:

- `GET /feed.json` — native JSON, meant to be called directly by the MCP tool server we build in step 2
- `GET /feed.csv` — ACP-spec CSV, upload-ready for any ACP-compatible catalog import API

## Run it

```bash
cd acl-feed
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then visit:
- http://127.0.0.1:8000/docs — interactive Swagger UI
- http://127.0.0.1:8000/feed.json — the agent feed
- http://127.0.0.1:8000/feed.csv — the ACP-spec CSV
- http://127.0.0.1:8000/products — your raw catalog (admin view)

The DB (`catalog.db`) is auto-created and seeded from `app/seed_data.py` on first run.

## What's actually being modeled

- `app/models.py` — canonical `Product` schema. Nothing platform-specific lives here.
- `app/db.py` — SQLite storage (stand-in for a real Shopify/WooCommerce/custom DB).
- `app/adapters/acp_feed.py` — canonical Product → agent-native JSON (nested types).
- `app/adapters/acp_csv_feed.py` — canonical Product → the ACP CSV column spec
  (colon-delimited `related_products`, `"price": "3499.00 INR"`, etc.)

Adding a second output format (say, a Google Merchant Center feed) later means writing
one new file in `adapters/` — nothing else changes.

## Example: one product through both adapters

Source (`seed_data.py`):
```python
Product(
    id="SKU-SNK-001",
    title="Loopin Trail Runner Sneakers",
    price_inr=Decimal("3499.00"),
    availability=Availability.IN_STOCK,
    related_products=[RelatedProduct(relation_type=RelationType.UPSELL, target_id="SKU-SNK-002")],
    ...
)
```

`feed.json` output:
```json
{
  "id": "SKU-SNK-001",
  "title": "Loopin Trail Runner Sneakers",
  "price": {"amount": 3499.0, "currency": "INR"},
  "related_products": [{"relation": "upsell", "target_id": "SKU-SNK-002"}]
}
```

`feed.csv` row:
```
SKU-SNK-001,Loopin Trail Runner Sneakers,...,3499.00 INR,,,false,4.4,212,4.3,upsell:SKU-SNK-002
```

## Try upserting a product

```bash
curl -X POST http://127.0.0.1:8000/products \
  -H "Content-Type: application/json" \
  -d '{
    "id": "SKU-TSHIRT-100",
    "title": "Loopin Essential Tee",
    "description": "100% cotton crew neck tee.",
    "link": "https://loopinthreads.example.com/products/essential-tee",
    "brand": "Loopin Threads",
    "product_category": "Apparel & Accessories > Clothing > T-Shirts",
    "availability": "in_stock",
    "inventory_quantity": 100,
    "price_inr": "699.00"
  }'
```

---

# Step 2: MCP Tool Server

Exposes the catalog to any MCP-compatible agent (Claude Desktop, Claude Code, etc.)
as five tools, sitting on top of step 1's `/feed.json` and `/products/{id}` over HTTP
-- it's a separate process, talking to the feed generator like any other client would.

| Tool | What it does |
|---|---|
| `search_products` | keyword / category / max-price filter, ranked by popularity |
| `get_product` | full detail, with `related_products` resolved into real titles + prices |
| `add_to_cart` | validates stock, re-prices fresh, auto-attaches up to 3 upsell/cross-sell suggestions |
| `view_cart` | current cart, re-priced |
| `checkout` | finalizes the order total; stops right before payment -- step 3 plugs in here |

## Run it

Terminal 1 (the feed generator must be running first):
```bash
cd acl-feed
source .venv/bin/activate
uvicorn app.main:app --reload
```

Terminal 2:
```bash
cd acl-feed
pip install -r mcp_server/requirements.txt
python -m mcp_server.server
```

It'll sit there waiting on stdio -- that's normal, it's meant to be launched *by* an
MCP client, not run interactively. To actually use it, point Claude Desktop at it.

## Connect it to Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "razorpay-acl": {
      "command": "/absolute/path/to/acl-feed/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/acl-feed",
      "env": { "FEED_API_BASE": "http://127.0.0.1:8000" }
    }
  }
}
```

Restart Claude Desktop, keep the feed generator running in the background, and you
should be able to ask things like *"search Loopin's catalog for sneakers under ₹4000"*
or *"add the trail runner sneakers to my cart"* and watch it call the tools live.

## What the growth hook looks like in practice

Ask the agent to add `SKU-SNK-001` (Trail Runner Sneakers) to a cart. The response
includes `suggested_addons` pulled from that product's `related_products` graph --
the ankle socks (accessory) and the Pro sneakers (upsell) -- with real prices, not
just IDs. That's the merchant-revenue lever: the agent has enough to say *"want to
add the cushion socks for ₹499?"* without you writing any prompt-engineered upsell
logic -- it's structural, coming straight off the catalog graph from step 1.
