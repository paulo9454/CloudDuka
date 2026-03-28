#!/usr/bin/env python3
import asyncio
import argparse
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from backend.server import hash_pin
from backend.seed_realistic import seed_realistic_async

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "cloudduka")


async def main(faker_expand: bool):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    summary = await seed_realistic_async(
        db,
        hash_pin,
        logger=type("Logger", (), {"info": print})(),
        faker_expand=faker_expand,
    )

    print("\nSeed realistic summary")
    print(f"Owners + shops: {summary['owners_shops']}")
    print(f"Shopkeepers: {summary['shopkeepers']}")
    print(f"Vendors + products: {summary['vendors_products']}")
    print(f"Customers: {summary['customers']}")
    print(f"Riders: {summary['riders']}")
    print(f"Sample POS orders: {summary['sample_pos_orders']}")
    print(f"Sample online orders: {summary['sample_online_orders']}")
    print(f"Stock adjustments: {summary['stock_adjustments']}")
    print(f"Low-stock alerts: {summary['low_stock_alerts']}")
    print(f"Sales total: {summary['sales_total']:.2f}")
    print(f"Faker generated: {summary['faker_generated']}")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed CloudDuka realistic marketplace data")
    parser.add_argument(
        "--faker-expand",
        action="store_true",
        help="Append additional faker-generated customers/vendors/products",
    )
    args = parser.parse_args()
    asyncio.run(main(faker_expand=args.faker_expand))
