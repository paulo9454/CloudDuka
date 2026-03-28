"""Orders router facade (backward-compatible)."""

from backend.server import (  # noqa: F401
    checkout_order,
    list_orders,
    get_order,
    patch_order_status,
    patch_order_lifecycle_status,
    cancel_order,
    customer_checkout,
    customer_list_orders,
    customer_get_order,
)
