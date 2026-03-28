"""Products router facade (backward-compatible)."""

from backend.server import (  # noqa: F401
    create_product,
    list_products,
    get_product,
    update_product,
    delete_product,
    list_categories_simple,
)
