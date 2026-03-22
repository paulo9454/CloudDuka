#!/usr/bin/env python3
"""Seed a staging MongoDB database with CloudDuka demo data."""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
from pymongo import MongoClient


def iso_now(offset_days: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).isoformat()


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def build_seed_documents() -> dict:
    owner_id = "owner-demo"
    shopkeeper_id = "shopkeeper-demo"
    main_shop_id = "shop-main"
    annex_shop_id = "shop-annex"
    supplier_id = "supplier-acme"

    products = [
        {
            "id": "prod-milk",
            "name": "Milk",
            "sku": "SKU-MILK-001",
            "category": "Dairy",
            "unit_price": 80.0,
            "cost_price": 55.0,
            "stock_quantity": 4,
            "min_stock_level": 10,
            "unit": "piece",
            "image_url": None,
            "shop_id": main_shop_id,
            "created_at": iso_now(-10),
            "updated_at": iso_now(-1),
        },
        {
            "id": "prod-bread",
            "name": "Bread",
            "sku": "SKU-BREAD-001",
            "category": "Bakery",
            "unit_price": 65.0,
            "cost_price": 40.0,
            "stock_quantity": 12,
            "min_stock_level": 8,
            "unit": "piece",
            "image_url": None,
            "shop_id": main_shop_id,
            "created_at": iso_now(-9),
            "updated_at": iso_now(-1),
        },
        {
            "id": "prod-rice",
            "name": "Rice 2kg",
            "sku": "SKU-RICE-002",
            "category": "Groceries",
            "unit_price": 260.0,
            "cost_price": 210.0,
            "stock_quantity": 2,
            "min_stock_level": 6,
            "unit": "bag",
            "image_url": None,
            "shop_id": annex_shop_id,
            "created_at": iso_now(-8),
            "updated_at": iso_now(-2),
        },
    ]

    sales = [
        {
            "id": "sale-1",
            "receipt_number": "RCP-202603220001-ABCD",
            "items": [{"product_id": "prod-bread", "product_name": "Bread", "quantity": 3, "unit_price": 65.0, "total": 195.0}],
            "payment_method": "cash",
            "total_amount": 195.0,
            "amount_paid": 200.0,
            "change_amount": 5.0,
            "customer_id": None,
            "mpesa_transaction_id": None,
            "status": "completed",
            "shop_id": main_shop_id,
            "created_by": owner_id,
            "created_at": iso_now(),
        },
        {
            "id": "sale-2",
            "receipt_number": "RCP-202603220002-EFGH",
            "items": [{"product_id": "prod-milk", "product_name": "Milk", "quantity": 2, "unit_price": 80.0, "total": 160.0}],
            "payment_method": "mpesa",
            "total_amount": 160.0,
            "amount_paid": None,
            "change_amount": None,
            "customer_id": None,
            "mpesa_transaction_id": "MPESA123456",
            "status": "completed",
            "shop_id": main_shop_id,
            "created_by": shopkeeper_id,
            "created_at": iso_now(),
        },
    ]

    marketplace_order_id = "market-order-1"
    checkout_order_id = "checkout-order-1"

    return {
        "users": [
            {
                "id": owner_id,
                "phone": "0712345678",
                "pin_hash": hash_pin("1234"),
                "name": "Demo Owner",
                "email": "owner@cloudduka.test",
                "email_verified": True,
                "default_shop_id": main_shop_id,
                "trial_ends_at": iso_now(14),
                "created_at": iso_now(-14),
            },
            {
                "id": shopkeeper_id,
                "phone": "0799999999",
                "pin_hash": hash_pin("1234"),
                "name": "Demo Shopkeeper",
                "email": "shopkeeper@cloudduka.test",
                "email_verified": True,
                "default_shop_id": main_shop_id,
                "trial_ends_at": None,
                "created_at": iso_now(-7),
            },
        ],
        "shops": [
            {"id": main_shop_id, "name": "CloudDuka Main Branch", "owner_id": owner_id, "address": "Nairobi CBD", "phone": "0700000001", "email": "main@cloudduka.test", "created_at": iso_now(-30)},
            {"id": annex_shop_id, "name": "CloudDuka Annex", "owner_id": owner_id, "address": "Westlands", "phone": "0700000002", "email": "annex@cloudduka.test", "created_at": iso_now(-20)},
        ],
        "shop_users": [
            {"id": "su-1", "user_id": owner_id, "shop_id": main_shop_id, "role": "owner", "created_at": iso_now(-30)},
            {"id": "su-2", "user_id": owner_id, "shop_id": annex_shop_id, "role": "owner", "created_at": iso_now(-20)},
            {"id": "su-3", "user_id": shopkeeper_id, "shop_id": main_shop_id, "role": "shopkeeper", "created_at": iso_now(-7)},
        ],
        "subscriptions": [
            {"id": "sub-main", "shop_id": main_shop_id, "owner_id": owner_id, "amount": 300, "status": "active", "paid_at": iso_now(-2), "expires_at": iso_now(28), "mpesa_receipt": "TRIAL-MAIN"},
            {"id": "sub-annex", "shop_id": annex_shop_id, "owner_id": owner_id, "amount": 300, "status": "active", "paid_at": iso_now(-1), "expires_at": iso_now(29), "mpesa_receipt": "TRIAL-ANNEX"},
        ],
        "products": products,
        "suppliers": [
            {"id": supplier_id, "name": "Acme Supplies", "phone": "0722000000", "notes": "Preferred marketplace vendor", "shop_id": main_shop_id, "created_at": iso_now(-15)},
        ],
        "orders": [
            {
                "id": checkout_order_id,
                "order_number": "ORD-202603220001-ABCD",
                "shop_id": main_shop_id,
                "customer_name": "Jane Customer",
                "customer_email": "jane@example.com",
                "customer_phone": "0711111111",
                "shipping_address": "Nairobi",
                "notes": "Same day delivery",
                "items": [{"product_id": "prod-bread", "product_name": "Bread", "quantity": 2, "unit_price": 65.0, "total": 130.0}],
                "total_amount": 130.0,
                "payment_method": "cash",
                "payment_status": "paid",
                "status": "paid",
                "mpesa_checkout_request_id": None,
                "mpesa_receipt": None,
                "created_by": owner_id,
                "created_at": iso_now(-1),
                "updated_at": iso_now(-1),
            },
            {
                "id": marketplace_order_id,
                "order_number": "PO-202603220001-XYZ1",
                "shop_id": main_shop_id,
                "order_type": "marketplace",
                "vendor_id": supplier_id,
                "vendor_name": "Acme Supplies",
                "customer_name": "Acme Supplies",
                "customer_email": None,
                "customer_phone": "0722000000",
                "shipping_address": None,
                "notes": "Restock low inventory",
                "items": [{"product_id": "prod-milk", "product_name": "Milk", "quantity": 12, "unit_price": 55.0, "total": 660.0}],
                "total_amount": 660.0,
                "payment_method": "mpesa",
                "payment_status": "pending",
                "status": "ordered",
                "mpesa_checkout_request_id": None,
                "mpesa_receipt": None,
                "created_by": owner_id,
                "created_at": iso_now(-1),
                "updated_at": iso_now(-1),
            },
        ],
        "order_items": [
            {"id": "oi-1", "order_id": checkout_order_id, "product_id": "prod-bread", "product_name": "Bread", "quantity": 2, "price": 65.0},
            {"id": "oi-2", "order_id": marketplace_order_id, "product_id": "prod-milk", "product_name": "Milk", "quantity": 12, "price": 55.0, "item_type": "marketplace"},
        ],
        "payments": [
            {"id": "payment-1", "shop_id": main_shop_id, "order_id": checkout_order_id, "amount": 130.0, "status": "successful", "method": "cash", "created_at": iso_now(-1), "user_id": owner_id},
            {"id": "payment-2", "shop_id": main_shop_id, "order_id": marketplace_order_id, "amount": 660.0, "status": "pending", "method": "mpesa", "provider": "mpesa", "type": "marketplace_order", "created_at": iso_now(-1), "user_id": owner_id},
        ],
        "sales": sales,
        "credit_customers": [
            {"id": "credit-1", "name": "Corner Hotel", "phone": "0701231234", "email": "hotel@example.com", "address": "Ngara", "credit_limit": 10000.0, "current_balance": 2400.0, "shop_id": main_shop_id, "created_at": iso_now(-5)},
        ],
        "credit_payments": [
            {"id": "credit-payment-1", "customer_id": "credit-1", "amount": 600.0, "payment_method": "cash", "notes": "Partial settlement", "shop_id": main_shop_id, "created_by": owner_id, "created_at": iso_now(-1)},
        ],
        "cart": [
            {"id": "cart-1", "shop_id": main_shop_id, "user_id": owner_id, "items": [{"product_id": "prod-bread", "quantity": 1}], "updated_at": iso_now(-1)},
        ],
        "notifications": [
            {"id": "notification-1", "user_id": owner_id, "shop_id": main_shop_id, "title": "Marketplace order pending", "message": "Acme Supplies order is awaiting delivery.", "channel": "email", "metadata": {"order_id": marketplace_order_id}, "sent_at": iso_now(-1), "status": "logged"},
        ],
    }


def seed_database(drop_existing: bool) -> None:
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'cloudduka_staging')

    print(f"[seed] Connecting to MongoDB at {mongo_url} (db={db_name})")
    client = MongoClient(mongo_url)
    db = client[db_name]
    documents = build_seed_documents()

    if drop_existing:
        print('[seed] Dropping existing staging collections')
        for collection_name in documents:
            db[collection_name].drop()

    for collection_name, rows in documents.items():
        if not rows:
            continue
        db[collection_name].insert_many(rows)
        print(f"[seed] Inserted {len(rows):>2} documents into {collection_name}")

    client.close()
    print('[seed] Staging seed complete')
    print('[seed] Demo owner login: 0712345678 / 1234')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed CloudDuka staging data')
    parser.add_argument('--drop-existing', action='store_true', help='Drop and recreate seeded collections before inserting data')
    args = parser.parse_args()
    seed_database(drop_existing=args.drop_existing)
