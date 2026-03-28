"""Marketplace router facade (backward-compatible)."""

from backend.server import (  # noqa: F401
    public_home,
    public_list_categories,
    public_list_stores,
    public_list_products,
    public_search_products,
    public_get_product,
    shop_product_feed,
    customer_recommendations,
)
