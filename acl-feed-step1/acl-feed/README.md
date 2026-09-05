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
