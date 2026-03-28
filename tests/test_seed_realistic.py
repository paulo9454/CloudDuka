import logging
from copy import deepcopy

import pytest

from backend.seed_realistic import seed_realistic_async


class FakeInsertResult:
    def __init__(self, inserted_id=None):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, matched_count=0):
        self.matched_count = matched_count


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, limit):
        if limit is None:
            return deepcopy(self.documents)
        return deepcopy(self.documents[:limit])


class FakeCollection:
    def __init__(self):
        self.documents = []
        self.indexes = []

    def _matches(self, doc, query):
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$gte" in expected and not (actual >= expected["$gte"]):
                    return False
                if "$lte" in expected and not (actual <= expected["$lte"]):
                    return False
                continue
            if actual != expected:
                return False
        return True

    def _project(self, doc, projection):
        out = deepcopy(doc)
        out.pop("_id", None)
        if projection:
            for key, value in projection.items():
                if value == 0:
                    out.pop(key, None)
        return out

    async def find_one(self, query, projection=None):
        for doc in self.documents:
            if self._matches(doc, query):
                return self._project(doc, projection)
        return None

    def find(self, query, projection=None):
        matches = [self._project(d, projection) for d in self.documents if self._matches(d, query)]
        return FakeCursor(matches)

    async def insert_one(self, doc):
        self.documents.append(deepcopy(doc))
        return FakeInsertResult(doc.get("id"))

    async def insert_many(self, docs):
        for doc in docs:
            self.documents.append(deepcopy(doc))
        return FakeInsertResult()

    async def update_one(self, query, update, upsert=False):
        for doc in self.documents:
            if self._matches(doc, query):
                for k, v in update.get("$set", {}).items():
                    doc[k] = deepcopy(v)
                for k, v in update.get("$inc", {}).items():
                    doc[k] = doc.get(k, 0) + v
                return FakeUpdateResult(1)
        if upsert:
            new_doc = deepcopy(query)
            for k, v in update.get("$set", {}).items():
                new_doc[k] = deepcopy(v)
            self.documents.append(new_doc)
            return FakeUpdateResult(1)
        return FakeUpdateResult(0)

    async def count_documents(self, query):
        return sum(1 for d in self.documents if self._matches(d, query))

    async def create_index(self, spec, **kwargs):
        self.indexes.append({"spec": spec, "kwargs": kwargs})


class FakeDB:
    def __init__(self):
        self.users = FakeCollection()
        self.shops = FakeCollection()
        self.subscriptions = FakeCollection()
        self.shop_users = FakeCollection()
        self.categories = FakeCollection()
        self.vendors = FakeCollection()
        self.suppliers = FakeCollection()
        self.products = FakeCollection()
        self.sales = FakeCollection()
        self.orders = FakeCollection()
        self.order_items = FakeCollection()
        self.payments = FakeCollection()
        self.deliveries = FakeCollection()
        self.damaged_stock = FakeCollection()
        self.shop_recommendations = FakeCollection()
        self.stock_alerts = FakeCollection()


@pytest.mark.asyncio
async def test_seed_realistic_geospatial_and_recommendations_idempotent():
    db = FakeDB()
    logger = logging.getLogger("test-seed")

    summary1 = await seed_realistic_async(db, lambda pin: f"hash-{pin}", logger, faker_expand=False)
    summary2 = await seed_realistic_async(db, lambda pin: f"hash-{pin}", logger, faker_expand=False)

    assert summary1["owners_shops"] > 0
    assert summary2["owners_shops"] == 0

    assert any(idx["spec"] == [("geo_location", "2dsphere")] for idx in db.shops.indexes)
    assert any(idx["spec"] == [("current_location", "2dsphere")] for idx in db.users.indexes)

    shops = await db.shops.find({}, {"_id": 0}).to_list(100)
    assert all(shop.get("geo_location") for shop in shops)

    customers = await db.users.find({"role": "customer"}, {"_id": 0}).to_list(100)
    assert customers
    assert all(customer.get("current_location") for customer in customers)

    recommendations = await db.shop_recommendations.find({}, {"_id": 0}).to_list(500)
    assert len(recommendations) == len(customers)
    assert len({r["for_customer_id"] for r in recommendations}) == len(recommendations)
    assert all(r.get("nearby_shop_ids") for r in recommendations)
    # Recommendation upsert remains idempotent across re-runs.
    summary3 = await seed_realistic_async(db, lambda pin: f"hash-{pin}", logger, faker_expand=False)
    recommendations_again = await db.shop_recommendations.find({}, {"_id": 0}).to_list(500)
    assert len(recommendations_again) == len(recommendations)
    assert summary3["orders_by_payment_method"]["cash"] >= 1


@pytest.mark.asyncio
async def test_seed_realistic_stock_payments_and_delivery_flows():
    db = FakeDB()
    logger = logging.getLogger("test-seed")

    await seed_realistic_async(db, lambda pin: f"hash-{pin}", logger, faker_expand=False)

    sugar = await db.products.find_one({"id": "prod-sugar-2kg"}, {"_id": 0})
    assert sugar["stock_quantity"] == 79

    ugali = await db.products.find_one({"id": "prod-ugali-flour-2kg"}, {"_id": 0})
    water = await db.products.find_one({"id": "prod-mineral-water-1l"}, {"_id": 0})
    assert ugali["stock_quantity"] == 118
    assert water["stock_quantity"] == 197

    soap = await db.products.find_one({"id": "prod-soap-bar"}, {"_id": 0})
    assert soap["stock_quantity"] == 148
    damaged = await db.damaged_stock.find_one({"id": "seed-damaged-1"}, {"_id": 0})
    assert damaged and damaged["quantity"] == 2

    online_order = await db.orders.find_one({"id": "seed-order-online-1"}, {"_id": 0})
    paystack = await db.payments.find_one({"id": "seed-payment-paystack-1"}, {"_id": 0})
    assert online_order["total_amount"] == 570.0
    assert paystack["amount"] == online_order["total_amount"]

    for method in ("cash", "mpesa", "credit", "paystack"):
        payment = await db.payments.find_one({"id": f"seed-payment-{method}"}, {"_id": 0})
        order = await db.orders.find_one({"id": f"seed-order-{method}"}, {"_id": 0})
        assert payment is not None
        assert order is not None
        assert payment["amount"] == order["total_amount"]

    delivery = await db.deliveries.find_one({"id": "seed-delivery-1"}, {"_id": 0})
    assert delivery["rider_id"] == "rider-1"
    assert delivery["status"] == "delivered"

    rider = await db.users.find_one({"id": "rider-1"}, {"_id": 0})
    assert rider["is_available"] is True
    assert rider["status"] == "available"

    # Low-stock alerts are deduplicated by product id.
    alert_ids = [a["id"] for a in (await db.stock_alerts.find({}, {"_id": 0}).to_list(1000))]
    assert len(alert_ids) == len(set(alert_ids))


@pytest.mark.asyncio
async def test_seed_realistic_faker_expansion_is_additive_only():
    db = FakeDB()
    logger = logging.getLogger("test-seed")

    await seed_realistic_async(db, lambda pin: f"hash-{pin}", logger, faker_expand=False)
    deterministic_customer = await db.users.find_one({"id": "customer-demo-1"}, {"_id": 0})
    customers_before = await db.users.count_documents({"role": "customer"})

    summary = await seed_realistic_async(db, lambda pin: f"hash-{pin}", logger, faker_expand=True)
    deterministic_customer_after = await db.users.find_one({"id": "customer-demo-1"}, {"_id": 0})
    customers_after = await db.users.count_documents({"role": "customer"})

    assert deterministic_customer_after["phone"] == deterministic_customer["phone"]
    assert deterministic_customer_after["name"] == deterministic_customer["name"]
    assert customers_after >= customers_before
    assert summary["faker_generated"]["customers"] >= 0
    assert summary["faker_generated"]["vendors"] >= 0
    assert summary["faker_generated"]["products"] >= 0
    assert "orders_by_payment_method" in summary
    assert "rider_delivery_counts" in summary
