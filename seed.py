#!/usr/bin/env python3
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "cloudduka")


def main():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()

    # Clear existing demo-facing data
    db.products.delete_many({})
    db.vendors.delete_many({})
    db.suppliers.delete_many({"id": {"$regex": "^seed-supplier-"}})
    db.shops.delete_many({"id": "seed-shop-1"})
    db.users.delete_many({"id": "seed-owner-1"})

    db.users.insert_one(
        {
            "id": "seed-owner-1",
            "phone": "0700000000",
            "name": "Seed Owner",
            "role": "owner",
            "shop_id": "seed-shop-1",
            "default_shop_id": "seed-shop-1",
            "shop_ids": ["seed-shop-1"],
            "pin_hash": "$2b$12$Qf6e2AkaV2H6Y5vBHE24a.7GOZQb8NOxDAiQfQxr42sO3N99mM9w.",
            "created_at": now,
        }
    )

    db.shops.insert_one(
        {
            "id": "seed-shop-1",
            "name": "CloudDuka Demo Shop",
            "owner_id": "seed-owner-1",
            "is_active": True,
            "subscription": {"plan": "online", "status": "active", "expires_at": None},
            "created_at": now,
        }
    )

    vendors = [
        {"id": "seed-vendor-1", "name": "Fresh Farm Supplies", "created_at": now},
        {"id": "seed-vendor-2", "name": "Urban Wholesale Hub", "created_at": now},
    ]
    db.vendors.insert_many(vendors)

    suppliers = [
        {
            "id": "seed-supplier-1",
            "name": "Fresh Farm Supplies",
            "phone": "0711000001",
            "notes": "Manual seed supplier",
            "shop_id": "seed-shop-1",
            "created_at": now,
        },
        {
            "id": "seed-supplier-2",
            "name": "Urban Wholesale Hub",
            "phone": "0711000002",
            "notes": "Manual seed supplier",
            "shop_id": "seed-shop-1",
            "created_at": now,
        },
    ]
    db.suppliers.insert_many(suppliers)

    products = [
        {
            "id": "seed-product-1",
            "name": "Bananas (1kg)",
            "description": "Fresh ripe bananas",
            "price": 120.0,
            "unit_price": 120.0,
            "stock": 80,
            "stock_quantity": 80,
            "vendor_id": "seed-vendor-1",
            "image": None,
            "image_url": None,
            "shop_id": "seed-shop-1",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "seed-product-2",
            "name": "Tomatoes (1kg)",
            "description": "Premium red tomatoes",
            "price": 150.0,
            "unit_price": 150.0,
            "stock": 60,
            "stock_quantity": 60,
            "vendor_id": "seed-vendor-1",
            "image": None,
            "image_url": None,
            "shop_id": "seed-shop-1",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "seed-product-3",
            "name": "Cooking Oil (1L)",
            "description": "Refined sunflower oil",
            "price": 320.0,
            "unit_price": 320.0,
            "stock": 45,
            "stock_quantity": 45,
            "vendor_id": "seed-vendor-2",
            "image": None,
            "image_url": None,
            "shop_id": "seed-shop-1",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "seed-product-4",
            "name": "Rice (2kg)",
            "description": "Long grain rice",
            "price": 410.0,
            "unit_price": 410.0,
            "stock": 35,
            "stock_quantity": 35,
            "vendor_id": "seed-vendor-2",
            "image": None,
            "image_url": None,
            "shop_id": "seed-shop-1",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "seed-product-5",
            "name": "Milk (500ml)",
            "description": "Pasteurized fresh milk",
            "price": 75.0,
            "unit_price": 75.0,
            "stock": 120,
            "stock_quantity": 120,
            "vendor_id": "seed-vendor-1",
            "image": None,
            "image_url": None,
            "shop_id": "seed-shop-1",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    ]
    db.products.insert_many(products)

    print("Database reset and seeded successfully.")


if __name__ == "__main__":
    main()
