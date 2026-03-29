from __future__ import annotations

import random
import uuid
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional
from math import radians, sin, cos, sqrt, atan2

try:
    from faker import Faker  # type: ignore
except Exception:  # pragma: no cover
    Faker = None


PAYMENT_METHODS = ["cash", "mpesa", "credit", "paystack"]
LOW_STOCK_THRESHOLD = 10
MODULE_LOGGER = logging.getLogger(__name__)
REQUIRED_COLLECTIONS = [
    "users",
    "shops",
    "products",
    "orders",
    "subscriptions",
    "riders",
    "shop_users",
    "categories",
    "vendors",
    "suppliers",
    "sales",
    "order_items",
    "payments",
    "deliveries",
    "damaged_stock",
    "shop_recommendations",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_blueprint() -> Dict[str, List[dict]]:
    now = _now_iso()
    owners_and_partner = [
        {
            "id": "owner-nairobi-1",
            "name": "Peter Kamau",
            "phone": "0700100001",
            "email": "peter.kamau@cloudduka.demo",
            "role": "owner",
            "shop_id": "shop-nairobi-central",
            "default_shop_id": "shop-nairobi-central",
            "shop_ids": ["shop-nairobi-central"],
            "created_at": now,
        },
        {
            "id": "owner-kisumu-1",
            "name": "Agnes Achieng",
            "phone": "0700100002",
            "email": "agnes.achieng@cloudduka.demo",
            "role": "owner",
            "shop_id": "shop-kisumu-lakeside",
            "default_shop_id": "shop-kisumu-lakeside",
            "shop_ids": ["shop-kisumu-lakeside", "shop-kisumu-online"],
            "created_at": now,
        },
        {
            "id": "partner-mombasa-1",
            "name": "Salim Mwinyi",
            "phone": "0700100003",
            "email": "salim.mwinyi@cloudduka.demo",
            "role": "partner",
            "shop_id": "shop-mombasa-online",
            "default_shop_id": "shop-mombasa-online",
            "shop_ids": ["shop-mombasa-online"],
            "created_at": now,
        },
    ]

    shops = [
        {
            "id": "shop-nairobi-central",
            "name": "Nairobi Central Mart",
            "owner_id": "owner-nairobi-1",
            "package": "pos",
            "subscription": {"plan": "pos", "status": "active", "expires_at": None},
            "is_active": True,
            "location": {"lat": -1.286389, "lng": 36.817223, "label": "Nairobi CBD"},
            "geo_location": {"type": "Point", "coordinates": [36.817223, -1.286389]},
            "created_at": now,
        },
        {
            "id": "shop-kisumu-lakeside",
            "name": "Lakeside Fresh Store",
            "owner_id": "owner-kisumu-1",
            "package": "online",
            "subscription": {"plan": "online", "status": "active", "expires_at": None},
            "is_active": True,
            "location": {"lat": -0.1022, "lng": 34.7617, "label": "Kisumu CBD"},
            "geo_location": {"type": "Point", "coordinates": [34.7617, -0.1022]},
            "created_at": now,
        },
        {
            "id": "shop-kisumu-online",
            "name": "Lakeside Plus Hub",
            "owner_id": "owner-kisumu-1",
            "package": "plus",
            "subscription": {"plan": "online", "status": "active", "expires_at": None},
            "is_active": True,
            "location": {"lat": -0.099, "lng": 34.755, "label": "Milimani, Kisumu"},
            "geo_location": {"type": "Point", "coordinates": [34.755, -0.099]},
            "created_at": now,
        },
        {
            "id": "shop-mombasa-online",
            "name": "Coastline Online Market",
            "owner_id": "partner-mombasa-1",
            "package": "online",
            "subscription": {"plan": "online", "status": "active", "expires_at": None},
            "is_active": True,
            "location": {"lat": -4.0435, "lng": 39.6682, "label": "Mombasa Island"},
            "geo_location": {"type": "Point", "coordinates": [39.6682, -4.0435]},
            "created_at": now,
        },
    ]

    shopkeepers = [
        {
            "id": "keeper-nairobi-1",
            "name": "Mercy Wanjiru",
            "phone": "0711100001",
            "email": "mercy.wanjiru@cloudduka.demo",
            "role": "shopkeeper",
            "shop_id": "shop-nairobi-central",
            "default_shop_id": "shop-nairobi-central",
            "shop_ids": ["shop-nairobi-central"],
            "created_at": now,
        },
        {
            "id": "keeper-kisumu-1",
            "name": "Kevin Odhiambo",
            "phone": "0711100002",
            "email": "kevin.odhiambo@cloudduka.demo",
            "role": "shopkeeper",
            "shop_id": "shop-kisumu-lakeside",
            "default_shop_id": "shop-kisumu-lakeside",
            "shop_ids": ["shop-kisumu-lakeside"],
            "created_at": now,
        },
    ]

    riders = [
        {
            "id": "rider-1",
            "name": "Joseph Kibet",
            "phone": "0744000001",
            "role": "rider",
            "is_available": True,
            "current_location": {"lat": -0.102, "lng": 34.762},
            "created_at": now,
        },
        {
            "id": "rider-2",
            "name": "Hassan Ali",
            "phone": "0744000002",
            "role": "rider",
            "is_available": True,
            "current_location": {"lat": -4.046, "lng": 39.669},
            "created_at": now,
        },
    ]

    vendors = [
        {"id": "vendor-fresh-fields", "name": "Fresh Fields Suppliers", "description": "Farm produce and greens", "created_at": now},
        {"id": "vendor-urban-goods", "name": "Urban Goods Wholesale", "description": "Packaged household goods", "created_at": now},
        {"id": "vendor-blue-harvest", "name": "Blue Harvest Distributors", "description": "Beverages and staples", "created_at": now},
    ]

    categories = [
        {"id": "cat-groceries", "name": "Groceries", "description": "Daily grocery essentials", "created_at": now},
        {"id": "cat-household", "name": "Household", "description": "Home and cleaning", "created_at": now},
        {"id": "cat-beverages", "name": "Beverages", "description": "Drinks and refreshments", "created_at": now},
        {"id": "cat-personal-care", "name": "Personal Care", "description": "Hygiene and wellness", "created_at": now},
        {"id": "cat-snacks", "name": "Snacks", "description": "Quick bites", "created_at": now},
    ]

    suppliers = [
        {"id": "supplier-fresh-fields", "name": "Fresh Fields Suppliers", "phone": "0722001001", "notes": "Primary produce vendor", "shop_id": "shop-nairobi-central", "vendor_id": "vendor-fresh-fields", "created_at": now},
        {"id": "supplier-urban-goods", "name": "Urban Goods Wholesale", "phone": "0722001002", "notes": "Household and packed goods", "shop_id": "shop-kisumu-lakeside", "vendor_id": "vendor-urban-goods", "created_at": now},
        {"id": "supplier-blue-harvest", "name": "Blue Harvest Distributors", "phone": "0722001003", "notes": "Beverages and staples", "shop_id": "shop-kisumu-online", "vendor_id": "vendor-blue-harvest", "created_at": now},
    ]

    products = [
        {"id": "prod-ugali-flour-2kg", "name": "Ugali Flour 2kg", "category": "Groceries", "category_id": "cat-groceries", "vendor_id": "vendor-blue-harvest", "vendor": "Blue Harvest Distributors", "unit_price": 180.0, "price": 180.0, "stock_quantity": 120, "stock": 120, "shop_id": "shop-nairobi-central", "description": "Stone-milled maize flour", "image_url": "https://picsum.photos/seed/ugali/600/400", "is_active": True, "created_at": now, "updated_at": now},
        {"id": "prod-sugar-2kg", "name": "Sugar 2kg", "category": "Groceries", "category_id": "cat-groceries", "vendor_id": "vendor-blue-harvest", "vendor": "Blue Harvest Distributors", "unit_price": 310.0, "price": 310.0, "stock_quantity": 80, "stock": 80, "shop_id": "shop-nairobi-central", "description": "Refined white sugar", "image_url": "https://picsum.photos/seed/sugar/600/400", "is_active": True, "created_at": now, "updated_at": now},
        {"id": "prod-rice-2kg", "name": "Rice 2kg", "category": "Groceries", "category_id": "cat-groceries", "vendor_id": "vendor-blue-harvest", "vendor": "Blue Harvest Distributors", "unit_price": 420.0, "price": 420.0, "stock_quantity": 70, "stock": 70, "shop_id": "shop-kisumu-lakeside", "description": "Long grain rice", "image_url": "https://picsum.photos/seed/rice/600/400", "is_active": True, "created_at": now, "updated_at": now},
        {"id": "prod-cooking-oil-1l", "name": "Cooking Oil 1L", "category": "Groceries", "category_id": "cat-groceries", "vendor_id": "vendor-urban-goods", "vendor": "Urban Goods Wholesale", "unit_price": 330.0, "price": 330.0, "stock_quantity": 95, "stock": 95, "shop_id": "shop-kisumu-online", "description": "Refined sunflower oil", "image_url": "https://picsum.photos/seed/oil/600/400", "is_active": True, "created_at": now, "updated_at": now},
        {"id": "prod-soap-bar", "name": "Laundry Soap Bar", "category": "Household", "category_id": "cat-household", "vendor_id": "vendor-urban-goods", "vendor": "Urban Goods Wholesale", "unit_price": 85.0, "price": 85.0, "stock_quantity": 150, "stock": 150, "shop_id": "shop-kisumu-lakeside", "description": "Multi-purpose cleaning soap", "image_url": "https://picsum.photos/seed/soap/600/400", "is_active": True, "created_at": now, "updated_at": now},
        {"id": "prod-bath-tissue-4pk", "name": "Bath Tissue 4 Pack", "category": "Household", "category_id": "cat-household", "vendor_id": "vendor-urban-goods", "vendor": "Urban Goods Wholesale", "unit_price": 220.0, "price": 220.0, "stock_quantity": 65, "stock": 65, "shop_id": "shop-kisumu-online", "description": "Soft 2-ply tissue", "image_url": "https://picsum.photos/seed/tissue/600/400", "is_active": True, "created_at": now, "updated_at": now},
        {"id": "prod-orange-juice-1l", "name": "Orange Juice 1L", "category": "Beverages", "category_id": "cat-beverages", "vendor_id": "vendor-blue-harvest", "vendor": "Blue Harvest Distributors", "unit_price": 260.0, "price": 260.0, "stock_quantity": 55, "stock": 55, "shop_id": "shop-kisumu-online", "description": "100% fruit juice", "image_url": "https://picsum.photos/seed/juice/600/400", "is_active": True, "created_at": now, "updated_at": now},
        {"id": "prod-mineral-water-1l", "name": "Mineral Water 1L", "category": "Beverages", "category_id": "cat-beverages", "vendor_id": "vendor-blue-harvest", "vendor": "Blue Harvest Distributors", "unit_price": 70.0, "price": 70.0, "stock_quantity": 200, "stock": 200, "shop_id": "shop-nairobi-central", "description": "Purified bottled water", "image_url": "https://picsum.photos/seed/water/600/400", "is_active": True, "created_at": now, "updated_at": now},
    ]

    customers = [
        {"id": "customer-demo-1", "name": "Faith Nyambura", "phone": "0733000001", "email": "faith.nyambura@example.com", "address": "Kilimani, Nairobi", "role": "customer", "current_location": {"lat": -1.2921, "lng": 36.8219}, "created_at": now},
        {"id": "customer-demo-2", "name": "James Ouma", "phone": "0733000002", "email": "james.ouma@example.com", "address": "Milimani, Kisumu", "role": "customer", "current_location": {"lat": -0.0917, "lng": 34.7680}, "created_at": now},
        {"id": "customer-demo-3", "name": "Ruth Chepkemoi", "phone": "0733000003", "email": "ruth.chepkemoi@example.com", "address": "Nyali, Mombasa", "role": "customer", "current_location": {"lat": -4.0336, "lng": 39.6892}, "created_at": now},
    ]

    return {
        "owners_and_partner": owners_and_partner,
        "shops": shops,
        "shopkeepers": shopkeepers,
        "riders": riders,
        "vendors": vendors,
        "categories": categories,
        "suppliers": suppliers,
        "products": products,
        "customers": customers,
    }


def _calculate_total(items: List[dict]) -> float:
    return float(sum(float(item["unit_price"]) * int(item["quantity"]) for item in items))


async def _validate_stock(db, items: List[dict]) -> bool:
    for item in items:
        product = await db.products.find_one({"id": item["product_id"]}, {"_id": 0})
        if not product or product.get("stock_quantity", 0) < item["quantity"]:
            return False
    return True


async def _deduct_stock(db, items: List[dict]):
    adjustments = 0
    low_stock_alerts = 0
    for item in items:
        await db.products.update_one(
            {"id": item["product_id"]},
            {"$inc": {"stock_quantity": -int(item["quantity"]), "stock": -int(item["quantity"])}, "$set": {"updated_at": _now_iso()}},
        )
        adjustments += int(item["quantity"])
        product = await db.products.find_one({"id": item["product_id"]}, {"_id": 0})
        if product and int(product.get("stock_quantity", 0)) <= LOW_STOCK_THRESHOLD:
            alert_id = f"low-stock-{item['product_id']}"
            if not await db.stock_alerts.find_one({"id": alert_id}, {"_id": 0}):
                await db.stock_alerts.insert_one(
                    {
                        "id": alert_id,
                        "product_id": item["product_id"],
                        "shop_id": product.get("shop_id"),
                        "stock_quantity": int(product.get("stock_quantity", 0)),
                        "threshold": LOW_STOCK_THRESHOLD,
                        "created_at": _now_iso(),
                    }
                )
                low_stock_alerts += 1
    return {"adjustments": adjustments, "low_stock_alerts": low_stock_alerts}


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    earth_radius_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius_km * c


async def _ensure_geo_indexes(db):
    async def _get_indexes(collection):
        if not hasattr(collection, "list_indexes"):
            return []
        indexes = collection.list_indexes()
        if hasattr(indexes, "to_list"):
            return await indexes.to_list(None)
        if hasattr(indexes, "__aiter__"):
            return [doc async for doc in indexes]
        return []

    shop_indexes = await _get_indexes(db.shops)
    has_shop_geo = any(idx.get("key", {}).get("geo_location") == "2dsphere" for idx in shop_indexes)
    if not has_shop_geo:
        await db.shops.create_index([("geo_location", "2dsphere")])

    user_indexes = await _get_indexes(db.users)
    has_user_geo = any(idx.get("key", {}).get("current_location") == "2dsphere" for idx in user_indexes)
    if not has_user_geo:
        await db.users.create_index([("current_location", "2dsphere")], sparse=True)


async def _ensure_geo_fields(db):
    shops = await db.shops.find({}, {"_id": 0}).to_list(5000)
    shop_backfills = 0
    for shop in shops:
        if shop.get("geo_location"):
            continue
        loc = shop.get("location") or {}
        if "lat" in loc and "lng" in loc:
            await db.shops.update_one(
                {"id": shop["id"]},
                {"$set": {"geo_location": {"type": "Point", "coordinates": [loc["lng"], loc["lat"]]}}},
            )
            shop_backfills += 1

    customers = await db.users.find({"role": "customer"}, {"_id": 0}).to_list(5000)
    customer_backfills = 0
    for customer in customers:
        if customer.get("current_location"):
            continue
        recommended_shop = await db.shops.find_one({"is_active": True}, {"_id": 0})
        if not recommended_shop:
            continue
        loc = recommended_shop.get("location") or {}
        lat = float(loc.get("lat", -1.286389))
        lng = float(loc.get("lng", 36.817223))
        await db.users.update_one(
            {"id": customer["id"]},
            {"$set": {"current_location": {"lat": lat, "lng": lng}}},
        )
        customer_backfills += 1

    if shop_backfills:
        MODULE_LOGGER.warning("Backfilled geo_location for %s shops", shop_backfills)
    if customer_backfills:
        MODULE_LOGGER.warning("Backfilled current_location for %s customers", customer_backfills)


def _verify_seed_dependencies(db):
    # Defensive backfill for environments that model riders inside `users`.
    if not hasattr(db, "riders") and hasattr(db, "users"):
        setattr(db, "riders", db.users)
        MODULE_LOGGER.warning("Using riders collection fallback mapped to users")

    missing_collections = [name for name in REQUIRED_COLLECTIONS if not hasattr(db, name)]
    if missing_collections:
        raise RuntimeError(f"Missing required collections: {', '.join(sorted(missing_collections))}")

    for fn in (_validate_stock, _deduct_stock, _calculate_total):
        if not callable(fn):
            raise RuntimeError(f"Seed dependency is not callable: {fn}")

    try:
        from backend import server as backend_server
    except Exception:
        return
    auth_dependency = getattr(backend_server, "get_current_user", None)
    if auth_dependency is None or not callable(auth_dependency):
        # Seeder does not invoke auth directly, so keep this safe and non-fatal.
        MODULE_LOGGER.warning("Missing auth middleware/dependency: get_current_user")


async def _user_exists(db, user: dict) -> bool:
    if await db.users.find_one({"phone": user.get("phone")}, {"_id": 0}):
        return True
    email = user.get("email")
    if email and await db.users.find_one({"email": email}, {"_id": 0}):
        return True
    return False


async def _shop_exists(db, shop: dict) -> bool:
    if await db.shops.find_one({"id": shop.get("id")}, {"_id": 0}):
        return True
    code = shop.get("code")
    if code and await db.shops.find_one({"code": code}, {"_id": 0}):
        return True
    return False


async def _collect_observability(db) -> dict:
    payments = await db.payments.find({}, {"_id": 0}).to_list(10000)
    deliveries = await db.deliveries.find({}, {"_id": 0}).to_list(10000)
    orders_by_payment_method = {method: 0 for method in PAYMENT_METHODS}
    for payment in payments:
        method = str(payment.get("method", "")).lower()
        if method in orders_by_payment_method:
            orders_by_payment_method[method] += 1

    rider_delivery_counts = {}
    for delivery in deliveries:
        rider_id = delivery.get("rider_id")
        if not rider_id:
            continue
        rider_delivery_counts[rider_id] = rider_delivery_counts.get(rider_id, 0) + 1
    return {
        "orders_by_payment_method": orders_by_payment_method,
        "rider_delivery_counts": rider_delivery_counts,
    }


async def _upsert_customer_recommendations(db):
    customers = await db.users.find({"role": "customer"}, {"_id": 0}).to_list(1000)
    shops = await db.shops.find({"is_active": True}, {"_id": 0}).to_list(1000)
    for customer in customers:
        loc = customer.get("current_location") or {}
        if "lat" not in loc or "lng" not in loc:
            continue
        ranked = []
        for shop in shops:
            s_loc = shop.get("location") or {}
            if "lat" not in s_loc or "lng" not in s_loc:
                continue
            distance_km = _distance_km(loc["lat"], loc["lng"], s_loc["lat"], s_loc["lng"])
            ranked.append((distance_km, shop["id"]))
        ranked.sort(key=lambda x: x[0])
        nearby_ids = [shop_id for _, shop_id in ranked[:3]]
        await db.shop_recommendations.update_one(
            {"for_customer_id": customer["id"]},
            {"$set": {"id": f"seed-reco-{customer['id']}", "nearby_shop_ids": nearby_ids, "generated_at": _now_iso()}},
            upsert=True,
        )


async def _faker_expand_async(db, hash_pin: Callable[[str], str], summary: dict, size: int = 20):
    fake = Faker() if Faker else None
    now = _now_iso()
    vendors = await db.vendors.find({}, {"_id": 0}).to_list(1000)
    categories = await db.categories.find({}, {"_id": 0}).to_list(1000)
    shops = await db.shops.find({"is_active": True}, {"_id": 0}).to_list(1000)
    if not vendors or not categories or not shops:
        return

    for i in range(size):
        user_id = f"faker-customer-{i+1}"
        phone = f"0799{i:06d}"
        if await db.users.find_one({"phone": phone}, {"_id": 0}):
            continue
        name = fake.name() if fake else f"Faker Customer {i+1}"
        email = fake.email() if fake else f"faker.customer{i+1}@example.com"
        address = fake.address() if fake else f"Block {i+1}, Demo Estate"
        await db.users.insert_one(
            {
                "id": user_id,
                "name": name,
                "phone": phone,
                "email": email,
                "address": address,
                "role": "customer",
                "current_location": {
                    "lat": round(random.uniform(-4.1, -0.05), 6),
                    "lng": round(random.uniform(34.7, 39.7), 6),
                },
                "pin_hash": hash_pin("1234"),
                "created_at": now,
            }
        )
        summary["faker_generated"]["customers"] += 1

        # Optional online order simulation for faker customers
        if i % 3 == 0:
            candidate_product = await db.products.find_one({"is_active": True, "stock_quantity": {"$gte": 1}}, {"_id": 0})
            if candidate_product:
                order_id = f"faker-order-{i+1}"
                if not await db.orders.find_one({"id": order_id}, {"_id": 0}):
                    await _deduct_stock(db, [{"product_id": candidate_product["id"], "quantity": 1, "unit_price": candidate_product["unit_price"]}])
                    total = float(candidate_product["unit_price"])
                    now_order = _now_iso()
                    await db.orders.insert_one(
                        {
                            "id": order_id,
                            "order_number": order_id,
                            "user_id": user_id,
                            "shop_id": candidate_product["shop_id"],
                            "status": "completed",
                            "lifecycle_status": "delivered",
                            "source": "customer_app",
                            "is_online_order": True,
                            "total_amount": total,
                            "created_at": now_order,
                        }
                    )
                    await db.order_items.insert_one(
                        {
                            "id": f"faker-order-item-{i+1}",
                            "order_id": order_id,
                            "shop_id": candidate_product["shop_id"],
                            "product_id": candidate_product["id"],
                            "product_name": candidate_product["name"],
                            "quantity": 1,
                            "unit_price": candidate_product["unit_price"],
                            "total": total,
                            "created_at": now_order,
                        }
                    )
                    await db.payments.insert_one(
                        {
                            "id": f"faker-payment-{i+1}",
                            "shop_id": candidate_product["shop_id"],
                            "order_id": order_id,
                            "amount": total,
                            "method": random.choice(PAYMENT_METHODS),
                            "status": "successful",
                            "reference": f"faker-payment-ref-{i+1}",
                            "created_at": now_order,
                        }
                    )
                    summary["faker_generated"]["orders"] += 1

    for i in range(size):
        vendor_name = fake.company() if fake else f"Faker Vendor {i+1}"
        if await db.vendors.find_one({"name": vendor_name}, {"_id": 0}):
            continue
        vendor_id = f"faker-vendor-{uuid.uuid4().hex[:8]}"
        await db.vendors.insert_one({"id": vendor_id, "name": vendor_name, "description": "Faker expansion vendor", "created_at": now})
        summary["faker_generated"]["vendors"] += 1

        for p in range(3):
            category = random.choice(categories)
            shop = random.choice(shops)
            product_name = f"{(fake.word().title() if fake else 'Item')} {(fake.color_name() if fake else 'Color')}"
            if await db.products.find_one({"name": product_name, "shop_id": shop["id"]}, {"_id": 0}):
                continue
            price = round(random.uniform(80, 4500), 2)
            qty = random.randint(8, 180)
            await db.products.insert_one(
                {
                    "id": f"faker-product-{uuid.uuid4().hex[:10]}",
                    "name": product_name,
                    "category": category["name"],
                    "category_id": category["id"],
                    "vendor_id": vendor_id,
                    "vendor": vendor_name,
                    "unit_price": price,
                    "price": price,
                    "stock_quantity": qty,
                    "stock": qty,
                    "shop_id": shop["id"],
                    "description": fake.text(max_nb_chars=160) if fake else "Faker generated product",
                    "image_url": fake.image_url() if fake else "https://picsum.photos/600/400",
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            summary["faker_generated"]["products"] += 1


async def seed_realistic_async(db, hash_pin: Callable[[str], str], logger, faker_expand: bool = False) -> dict:
    _verify_seed_dependencies(db)
    data = _seed_blueprint()
    summary = {
        "owners_shops": 0,
        "shopkeepers": 0,
        "vendors_products": 0,
        "customers": 0,
        "riders": 0,
        "sample_pos_orders": 0,
        "sample_online_orders": 0,
        "sales_total": 0.0,
        "stock_adjustments": 0,
        "low_stock_alerts": 0,
        "faker_generated": {"customers": 0, "vendors": 0, "products": 0, "orders": 0},
    }

    await _ensure_geo_indexes(db)

    for account in data["owners_and_partner"]:
        if not await _user_exists(db, account):
            await db.users.insert_one({**account, "pin_hash": hash_pin("1234")})
            summary["owners_shops"] += 1

    for shop in data["shops"]:
        if not await _shop_exists(db, shop):
            await db.shops.insert_one(shop)
            summary["owners_shops"] += 1
        if not await db.subscriptions.find_one({"shop_id": shop["id"]}, {"_id": 0}):
            await db.subscriptions.insert_one(
                {
                    "id": f"sub-{shop['id']}",
                    "shop_id": shop["id"],
                    "owner_id": shop["owner_id"],
                    "package": shop.get("package", "pos"),
                    "status": "active",
                    "created_at": _now_iso(),
                }
            )

    for keeper in data["shopkeepers"]:
        if not await _user_exists(db, keeper):
            await db.users.insert_one({**keeper, "pin_hash": hash_pin("1234")})
            summary["shopkeepers"] += 1
        if not await db.shop_users.find_one({"user_id": keeper["id"], "shop_id": keeper["shop_id"], "role": "shopkeeper"}, {"_id": 0}):
            await db.shop_users.insert_one(
                {
                    "id": f"membership-{keeper['id']}-{keeper['shop_id']}",
                    "user_id": keeper["id"],
                    "shop_id": keeper["shop_id"],
                    "role": "shopkeeper",
                    "created_at": _now_iso(),
                }
            )
            summary["shopkeepers"] += 1

    for rider in data["riders"]:
        if not await _user_exists(db, rider):
            await db.users.insert_one({**rider, "pin_hash": hash_pin("1234")})
            summary["riders"] += 1

    for category in data["categories"]:
        if not await db.categories.find_one({"name": category["name"]}, {"_id": 0}):
            await db.categories.insert_one(category)

    for vendor in data["vendors"]:
        if not await db.vendors.find_one({"name": vendor["name"]}, {"_id": 0}):
            await db.vendors.insert_one(vendor)
            summary["vendors_products"] += 1

    for supplier in data["suppliers"]:
        if not await db.suppliers.find_one({"name": supplier["name"], "shop_id": supplier["shop_id"]}, {"_id": 0}):
            await db.suppliers.insert_one(supplier)

    for product in data["products"]:
        if not await db.products.find_one({"name": product["name"], "shop_id": product["shop_id"]}, {"_id": 0}):
            await db.products.insert_one(product)
            summary["vendors_products"] += 1

    for customer in data["customers"]:
        if not await _user_exists(db, customer):
            await db.users.insert_one({**customer, "pin_hash": hash_pin("1234")})
            summary["customers"] += 1

    # Damaged stock log with automatic deduction (once)
    if not await db.damaged_stock.find_one({"id": "seed-damaged-1"}, {"_id": 0}):
        product = await db.products.find_one({"id": "prod-soap-bar"}, {"_id": 0})
        if product and product.get("stock_quantity", 0) >= 2:
            deduction = await _deduct_stock(
                db, [{"product_id": product["id"], "quantity": 2, "unit_price": float(product.get("unit_price", 0.0))}]
            )
            summary["stock_adjustments"] += deduction["adjustments"]
            summary["low_stock_alerts"] += deduction["low_stock_alerts"]
            await db.damaged_stock.insert_one(
                {
                    "id": "seed-damaged-1",
                    "shop_id": product["shop_id"],
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "quantity": 2,
                    "reason": "expired",
                    "notes": "Deterministic damaged stock seed",
                    "created_at": _now_iso(),
                }
            )

    # sample POS order
    if not await db.sales.find_one({"id": "seed-sale-pos-1"}, {"_id": 0}):
        pos_items = [{"product_id": "prod-sugar-2kg", "quantity": 1, "unit_price": 310.0}]
        if await _validate_stock(db, pos_items):
            deduction = await _deduct_stock(db, pos_items)
            summary["stock_adjustments"] += deduction["adjustments"]
            summary["low_stock_alerts"] += deduction["low_stock_alerts"]
            total = _calculate_total(pos_items)
            await db.sales.insert_one(
                {
                    "id": "seed-sale-pos-1",
                    "receipt_number": "RCP-SEED-001",
                    "shop_id": "shop-nairobi-central",
                    "user_id": "keeper-nairobi-1",
                    "items": pos_items,
                    "total_amount": total,
                    "payment_method": "cash",
                    "status": "completed",
                    "created_at": _now_iso(),
                }
            )
            summary["sample_pos_orders"] += 1
            summary["sales_total"] += total

    # sample online order + payment + delivery assignment
    if not await db.orders.find_one({"id": "seed-order-online-1"}, {"_id": 0}):
        online_items = [
            {"product_id": "prod-ugali-flour-2kg", "quantity": 2, "unit_price": 180.0},
            {"product_id": "prod-mineral-water-1l", "quantity": 3, "unit_price": 70.0},
        ]
        if await _validate_stock(db, online_items):
            deduction = await _deduct_stock(db, online_items)
            summary["stock_adjustments"] += deduction["adjustments"]
            summary["low_stock_alerts"] += deduction["low_stock_alerts"]
            total = _calculate_total(online_items)
            now = _now_iso()
            await db.orders.insert_one(
                {
                    "id": "seed-order-online-1",
                    "order_number": "seed-order-online-1",
                    "user_id": "customer-demo-1",
                    "shop_id": "shop-nairobi-central",
                    "status": "completed",
                    "lifecycle_status": "delivered",
                    "source": "customer_app",
                    "is_online_order": True,
                    "delivery_tracking": True,
                    "total_amount": total,
                    "created_at": now,
                }
            )
            await db.order_items.insert_many(
                [
                    {
                        "id": "seed-order-item-1",
                        "order_id": "seed-order-online-1",
                        "shop_id": "shop-nairobi-central",
                        "product_id": "prod-ugali-flour-2kg",
                        "product_name": "Ugali Flour 2kg",
                        "quantity": 2,
                        "unit_price": 180.0,
                        "total": 360.0,
                        "created_at": now,
                    },
                    {
                        "id": "seed-order-item-2",
                        "order_id": "seed-order-online-1",
                        "shop_id": "shop-nairobi-central",
                        "product_id": "prod-mineral-water-1l",
                        "product_name": "Mineral Water 1L",
                        "quantity": 3,
                        "unit_price": 70.0,
                        "total": 210.0,
                        "created_at": now,
                    },
                ]
            )
            await db.payments.insert_one(
                {
                    "id": "seed-payment-paystack-1",
                    "shop_id": "shop-nairobi-central",
                    "order_id": "seed-order-online-1",
                    "amount": total,
                    "method": "paystack",
                    "status": "successful",
                    "reference": "seed-paystack-ref-1",
                    "created_at": now,
                }
            )
            await db.deliveries.insert_one(
                {
                    "id": "seed-delivery-1",
                    "order_id": "seed-order-online-1",
                    "rider_id": "rider-1",
                    "status": "delivered",
                    "pickup_location": {"lat": -1.286389, "lng": 36.817223},
                    "dropoff_location": {"lat": -1.292066, "lng": 36.821946},
                    "rider_location": {"lat": -1.289, "lng": 36.82},
                    "created_at": now,
                }
            )
            await db.users.update_one({"id": "rider-1"}, {"$set": {"is_available": False, "status": "on_delivery"}})
            await db.users.update_one({"id": "rider-1"}, {"$set": {"is_available": True, "status": "available"}})
            summary["sample_online_orders"] += 1
            summary["sales_total"] += total

    # additional payment diversity samples (amount always equals order total)
    method_samples = {
        "cash": {"order_id": "seed-order-cash", "product_id": "prod-rice-2kg", "quantity": 1},
        "mpesa": {"order_id": "seed-order-mpesa", "product_id": "prod-cooking-oil-1l", "quantity": 1},
        "credit": {"order_id": "seed-order-credit", "product_id": "prod-bath-tissue-4pk", "quantity": 1},
        "paystack": {"order_id": "seed-order-paystack", "product_id": "prod-orange-juice-1l", "quantity": 1},
    }
    for method, sample in method_samples.items():
        order_id = sample["order_id"]
        payment_id = f"seed-payment-{method}"
        if await db.orders.find_one({"id": order_id}, {"_id": 0}):
            continue
        product = await db.products.find_one({"id": sample["product_id"]}, {"_id": 0})
        if not product:
            continue
        order_items = [
            {
                "product_id": product["id"],
                "quantity": int(sample["quantity"]),
                "unit_price": float(product["unit_price"]),
            }
        ]
        if not await _validate_stock(db, order_items):
            continue
        deduction = await _deduct_stock(db, order_items)
        summary["stock_adjustments"] += deduction["adjustments"]
        summary["low_stock_alerts"] += deduction["low_stock_alerts"]
        total = _calculate_total(order_items)
        now = _now_iso()
        await db.orders.insert_one(
            {
                "id": order_id,
                "order_number": order_id,
                "user_id": "customer-demo-2",
                "shop_id": product["shop_id"],
                "status": "completed",
                "lifecycle_status": "delivered",
                "source": "customer_app",
                "is_online_order": True,
                "total_amount": total,
                "created_at": now,
            }
        )
        await db.order_items.insert_one(
            {
                "id": f"{order_id}-item-1",
                "order_id": order_id,
                "shop_id": product["shop_id"],
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": int(sample["quantity"]),
                "unit_price": float(product["unit_price"]),
                "total": total,
                "created_at": now,
            }
        )
        if not await db.payments.find_one({"id": payment_id}, {"_id": 0}):
            await db.payments.insert_one(
                {
                    "id": payment_id,
                    "shop_id": product["shop_id"],
                    "order_id": order_id,
                    "amount": total,
                    "method": method,
                    "status": "successful",
                    "reference": f"seed-{method}-ref",
                    "created_at": now,
                }
            )

    await _ensure_geo_fields(db)
    await _upsert_customer_recommendations(db)

    if faker_expand:
        await _faker_expand_async(db, hash_pin, summary)

    summary["low_stock_alerts"] += await db.products.count_documents({"stock_quantity": {"$lte": LOW_STOCK_THRESHOLD}})
    summary.update(await _collect_observability(db))

    logger.info(
        "Realistic seed summary: owners+shops=%s, shopkeepers=%s, vendors+products=%s, customers=%s, riders=%s, pos_orders=%s, online_orders=%s, stock_adjustments=%s, low_stock_alerts=%s, sales_total=%.2f, faker=%s",
        summary["owners_shops"],
        summary["shopkeepers"],
        summary["vendors_products"],
        summary["customers"],
        summary["riders"],
        summary["sample_pos_orders"],
        summary["sample_online_orders"],
        summary["stock_adjustments"],
        summary["low_stock_alerts"],
        summary["sales_total"],
        summary["faker_generated"],
    )
    return summary
