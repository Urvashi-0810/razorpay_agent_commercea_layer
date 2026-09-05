"""
Storage layer.

Products are stored as one row per SKU: a few indexed columns (id, availability)
for cheap filtering, plus the full canonical Product serialized as JSON in
`payload`. This keeps the schema stable while `models.Product` evolves --
we're not fighting a rigid SQL schema every time we add a field.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .models import Product

DB_PATH = Path(__file__).parent.parent / "catalog.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                availability TEXT NOT NULL,
                disable_checkout INTEGER NOT NULL DEFAULT 0,
                payload TEXT NOT NULL
            )
            """
        )


def upsert_product(product: Product) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO products (id, availability, disable_checkout, payload)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                availability = excluded.availability,
                disable_checkout = excluded.disable_checkout,
                payload = excluded.payload
            """,
            (
                product.id,
                product.availability.value,
                int(product.disable_checkout),
                product.model_dump_json(),
            ),
        )


def delete_product(product_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        return cur.rowcount > 0


def get_product(product_id: str) -> Optional[Product]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT payload FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        return Product.model_validate_json(row["payload"]) if row else None


def list_products(only_in_stock: bool = False) -> list[Product]:
    query = "SELECT payload FROM products"
    if only_in_stock:
        query += " WHERE availability = 'in_stock'"
    with get_conn() as conn:
        rows = conn.execute(query).fetchall()
        return [Product.model_validate_json(r["payload"]) for r in rows]


def seed(products: Iterable[Product], reset: bool = False) -> None:
    if reset:
        with get_conn() as conn:
            conn.execute("DELETE FROM products")
    for p in products:
        upsert_product(p)
