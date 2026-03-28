#!/usr/bin/env python3
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

from backend.faker_seed import generate_fake_marketplace_data

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "cloudduka")


def main():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()

    # clear relevant collections
    for collection in ["products", "vendors", "categories", "suppliers", "users", "shops"]:
        db[collection].delete_many({})

    shop_id = "seed-shop-1"
    owner_id = "seed-owner-1"

    db.users.insert_one(
        {
            "id": owner_id,
            "phone": "0700000000",
            "name": "Seed Owner",
            "email": "owner.seed@example.com",
            "address": "Seed Address, Nairobi",
            "role": "owner",
            "pin_hash": "$2b$12$Qf6e2AkaV2H6Y5vBHE24a.7GOZQb8NOxDAiQfQxr42sO3N99mM9w.",
            "password_hash": "seed-owner-password-hash",
            "shop_id": shop_id,
            "default_shop_id": shop_id,
            "shop_ids": [shop_id],
            "created_at": now,
        }
    )

    db.shops.insert_one(
        {
            "id": shop_id,
            "name": "CloudDuka Demo Shop",
            "owner_id": owner_id,
            "is_active": True,
            "subscription": {"plan": "online", "status": "active", "expires_at": None},
            "created_at": now,
        }
    )

    payload = generate_fake_marketplace_data(
        category_count=7,
        vendor_count=8,
        user_count=16,
        product_count=100,
        shop_id=shop_id,
    )

    db.categories.insert_many(payload["categories"])
    db.vendors.insert_many(payload["vendors"])
    db.users.insert_many(payload["users"])
    db.suppliers.insert_many(payload["suppliers"])
    db.products.insert_many(payload["products"])

    print("Faker seed completed successfully")
    print(
        {
            "categories": len(payload["categories"]),
            "vendors": len(payload["vendors"]),
            "users": len(payload["users"]),
            "products": len(payload["products"]),
            "suppliers": len(payload["suppliers"]),
        }
    )


if __name__ == "__main__":
    main()
