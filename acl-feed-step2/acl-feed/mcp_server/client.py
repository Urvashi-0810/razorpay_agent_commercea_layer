"""
Talks to the feed generator (step 1) over plain HTTP. Deliberately not
importing app.db directly -- in a real deployment the feed generator and the
MCP tool server are two separate services (possibly owned by different teams,
possibly the feed generator being a live merchant API we don't control), so
this client is the only thing that would need to change if that backend
were swapped out.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx

FEED_API_BASE = os.environ.get("FEED_API_BASE", "http://127.0.0.1:8000")


async def get_full_catalog(only_in_stock: bool = True) -> dict:
    async with httpx.AsyncClient(base_url=FEED_API_BASE, timeout=10.0) as client:
        resp = await client.get("/feed.json", params={"only_in_stock": only_in_stock})
        resp.raise_for_status()
        return resp.json()


async def get_product_detail(product_id: str) -> Optional[dict]:
    async with httpx.AsyncClient(base_url=FEED_API_BASE, timeout=10.0) as client:
        resp = await client.get(f"/products/{product_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
