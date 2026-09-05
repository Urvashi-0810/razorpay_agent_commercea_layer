from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

from . import db
from .adapters.acp_feed import to_feed
from .adapters.acp_csv_feed import to_csv_feed
from .models import Product, ProductUpsert
from .seed_data import CATALOG

app = FastAPI(
    title="Razorpay ACL — Feed Generator",
    description="Turns a merchant catalog into agent-browsable feeds (JSON + ACP-spec CSV).",
    version="0.1.0",
)


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    if not db.list_products():
        db.seed(CATALOG)


@app.get("/health")
def health():
    return {"status": "ok", "product_count": len(db.list_products())}


# ---------------------------------------------------------------------------
# Admin CRUD — this is the merchant's own view of their catalog
# ---------------------------------------------------------------------------

@app.get("/products", response_model=list[Product])
def list_products(only_in_stock: bool = Query(default=False)):
    return db.list_products(only_in_stock=only_in_stock)


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: str):
    product = db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"No product with id '{product_id}'")
    return product


@app.post("/products", response_model=Product, status_code=201)
def upsert_product(product: ProductUpsert):
    db.upsert_product(product)
    return product


@app.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: str):
    if not db.delete_product(product_id):
        raise HTTPException(status_code=404, detail=f"No product with id '{product_id}'")


# ---------------------------------------------------------------------------
# Feeds — what an agent / MCP tool actually consumes
# ---------------------------------------------------------------------------

@app.get("/feed.json")
def feed_json(only_in_stock: bool = Query(default=True)):
    """Agent-native JSON feed. This is what step 2 (the MCP tool server) will call."""
    products = db.list_products(only_in_stock=only_in_stock)
    return to_feed(products)


@app.get("/feed.csv", response_class=PlainTextResponse)
def feed_csv(only_in_stock: bool = Query(default=False)):
    """ACP-spec CSV -- upload-ready for any ACP-compatible catalog import API."""
    products = db.list_products(only_in_stock=only_in_stock)
    return to_csv_feed(products)
