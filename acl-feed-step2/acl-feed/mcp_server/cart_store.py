"""
In-memory cart storage, scoped to the MCP server process's lifetime.

Fine for a demo / single agent session. If carts need to survive a server
restart or be shared across processes, swap this module for a SQLite-backed
one -- the function signatures below are the contract the rest of the server
depends on, so that swap wouldn't touch server.py.
"""

from __future__ import annotations

import uuid
from typing import Optional

# cart_id -> {product_id: quantity}
_CARTS: dict[str, dict[str, int]] = {}


def new_cart() -> str:
    cart_id = uuid.uuid4().hex[:8]
    _CARTS[cart_id] = {}
    return cart_id


def cart_exists(cart_id: str) -> bool:
    return cart_id in _CARTS


def get_items(cart_id: str) -> Optional[dict[str, int]]:
    return _CARTS.get(cart_id)


def set_quantity(cart_id: str, product_id: str, quantity: int) -> None:
    if quantity <= 0:
        _CARTS[cart_id].pop(product_id, None)
    else:
        _CARTS[cart_id][product_id] = quantity


def add_quantity(cart_id: str, product_id: str, delta: int) -> int:
    current = _CARTS[cart_id].get(product_id, 0)
    new_qty = max(0, current + delta)
    set_quantity(cart_id, product_id, new_qty)
    return new_qty
