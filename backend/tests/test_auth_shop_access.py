import os
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_cloudduka')

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend import server


class FakeUpdateResult:
    def __init__(self, matched_count=0):
        self.matched_count = matched_count


class FakeInsertResult:
    def __init__(self, inserted_id=None):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = documents or []

    def _matches(self, document, query):
        for key, value in query.items():
            if isinstance(value, dict) and '$in' in value:
                if document.get(key) not in value['$in']:
                    return False
            else:
                if document.get(key) != value:
                    return False
        return True

    async def find_one(self, query, projection=None, sort=None):
        docs = [doc for doc in self.documents if self._matches(doc, query)]
        if sort and docs:
            key, direction = sort[0]
            docs = sorted(docs, key=lambda doc: doc.get(key, ''), reverse=direction == -1)
        if not docs:
            return None
        return {k: v for k, v in docs[0].items() if k != '_id'}

    async def insert_one(self, document, session=None):
        self.documents.append(dict(document))
        return FakeInsertResult(document.get('id'))

    async def update_one(self, query, update, upsert=False, session=None):
        for document in self.documents:
            if self._matches(document, query):
                if '$set' in update:
                    document.update(update['$set'])
                if '$inc' in update:
                    for key, value in update['$inc'].items():
                        document[key] = document.get(key, 0) + value
                if '$setOnInsert' in update:
                    for key, value in update['$setOnInsert'].items():
                        document.setdefault(key, value)
                return FakeUpdateResult(matched_count=1)
        if upsert:
            new_doc = dict(query)
            if '$set' in update:
                new_doc.update(update['$set'])
            if '$setOnInsert' in update:
                for key, value in update['$setOnInsert'].items():
                    new_doc.setdefault(key, value)
            self.documents.append(new_doc)
            return FakeUpdateResult(matched_count=1)
        return FakeUpdateResult(matched_count=0)

    async def delete_one(self, query):
        before = len(self.documents)
        self.documents = [doc for doc in self.documents if not self._matches(doc, query)]
        return SimpleNamespace(deleted_count=before - len(self.documents))


class FakeDB:
    def __init__(self, **collections):
        defaults = {
            'users': [],
            'shops': [],
            'shop_users': [],
            'subscriptions': [],
            'products': [],
            'suppliers': [],
            'cart': [],
            'orders': [],
            'order_items': [],
            'payments': [],
            'notifications': [],
            'mpesa_transactions': [],
        }
        defaults.update(collections)
        for name, documents in defaults.items():
            setattr(self, name, FakeCollection(documents))


@pytest.mark.asyncio
async def test_owner_can_switch_to_owned_shop(monkeypatch):
    monkeypatch.setattr(
        server,
        'db',
        FakeDB(
            users=[{'id': 'owner-1', 'phone': '0700', 'name': 'Owner', 'default_shop_id': 'shop-1', 'created_at': 'now'}],
            shop_users=[
                {'id': 'link-1', 'user_id': 'owner-1', 'shop_id': 'shop-1', 'role': 'owner', 'created_at': 'now'},
                {'id': 'link-2', 'user_id': 'owner-1', 'shop_id': 'shop-2', 'role': 'owner', 'created_at': 'now'},
            ],
            subscriptions=[{'id': 'sub-1', 'shop_id': 'shop-2', 'status': 'active', 'expires_at': '2999-01-01T00:00:00+00:00'}],
        ),
    )

    token = server.create_token('owner-1', 'shop-1', 'owner')
    user = await server.get_current_user(
        request=SimpleNamespace(url=SimpleNamespace(path='/api/products')),
        credentials=HTTPAuthorizationCredentials(scheme='Bearer', credentials=token),
        x_shop_id='shop-2',
    )

    assert user['shop_id'] == 'shop-2'
    assert user['role'] == 'owner'


@pytest.mark.asyncio
async def test_shopkeeper_cannot_switch_shops(monkeypatch):
    monkeypatch.setattr(
        server,
        'db',
        FakeDB(
            users=[{'id': 'user-1', 'phone': '0700', 'name': 'Keeper', 'default_shop_id': 'shop-1', 'created_at': 'now'}],
            shop_users=[{'id': 'link-1', 'user_id': 'user-1', 'shop_id': 'shop-1', 'role': 'shopkeeper', 'created_at': 'now'}],
            subscriptions=[{'id': 'sub-1', 'shop_id': 'shop-1', 'status': 'active', 'expires_at': '2999-01-01T00:00:00+00:00'}],
        ),
    )

    token = server.create_token('user-1', 'shop-1', 'shopkeeper')
    with pytest.raises(HTTPException) as exc:
        await server.get_current_user(
            request=SimpleNamespace(url=SimpleNamespace(path='/api/products')),
            credentials=HTTPAuthorizationCredentials(scheme='Bearer', credentials=token),
            x_shop_id='shop-2',
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_subscription_enforcement_blocks_access(monkeypatch):
    monkeypatch.setattr(
        server,
        'db',
        FakeDB(
            users=[{'id': 'owner-1', 'phone': '0700', 'name': 'Owner', 'default_shop_id': 'shop-1', 'created_at': 'now'}],
            shop_users=[{'id': 'link-1', 'user_id': 'owner-1', 'shop_id': 'shop-1', 'role': 'owner', 'created_at': 'now'}],
            subscriptions=[{'id': 'sub-1', 'shop_id': 'shop-1', 'status': 'expired', 'expires_at': '2000-01-01T00:00:00+00:00'}],
        ),
    )

    token = server.create_token('owner-1', 'shop-1', 'owner')
    with pytest.raises(HTTPException) as exc:
        await server.get_current_user(
            request=SimpleNamespace(url=SimpleNamespace(path='/api/products')),
            credentials=HTTPAuthorizationCredentials(scheme='Bearer', credentials=token),
            x_shop_id='shop-1',
        )

    assert exc.value.status_code == 403
    assert 'subscription' in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_checkout_creates_order_items_and_updates_stock(monkeypatch):
    fake_db = FakeDB(
        products=[{'id': 'prod-1', 'shop_id': 'shop-1', 'name': 'Product', 'unit_price': 100.0, 'stock_quantity': 5}],
        cart=[{'id': 'cart-1', 'user_id': 'owner-1', 'shop_id': 'shop-1', 'items': [{'product_id': 'prod-1', 'quantity': 2}], 'updated_at': 'now'}],
        subscriptions=[{'id': 'sub-1', 'shop_id': 'shop-1', 'status': 'active', 'expires_at': '2999-01-01T00:00:00+00:00'}],
    )
    monkeypatch.setattr(server, 'db', fake_db)
    monkeypatch.setattr(server, 'client', SimpleNamespace())

    user = {'id': 'owner-1', 'user_id': 'owner-1', 'name': 'Owner', 'email': 'owner@example.com', 'shop_id': 'shop-1', 'role': 'owner'}
    order = await server.checkout_cart(
        server.CheckoutRequest(payment_method='cash', customer_name='Buyer', customer_email='buyer@example.com'),
        user=user,
    )

    assert order.total_amount == 200.0
    assert fake_db.products.documents[0]['stock_quantity'] == 3
    assert len(fake_db.order_items.documents) == 1
    assert fake_db.payments.documents[0]['status'] == 'successful'


def test_build_restock_suggestions_prioritises_items():
    suggestions = server.build_restock_suggestions([
        {'id': 'prod-1', 'name': 'Milk', 'stock_quantity': 1, 'min_stock_level': 5, 'cost_price': 20},
        {'id': 'prod-2', 'name': 'Bread', 'stock_quantity': 5, 'min_stock_level': 5, 'cost_price': 10},
        {'id': 'prod-3', 'name': 'Rice', 'stock_quantity': 8, 'min_stock_level': 3, 'cost_price': 50},
    ])

    assert [item['product_name'] for item in suggestions] == ['Milk', 'Bread']
    assert suggestions[0]['recommended_restock'] == 5
    assert suggestions[0]['estimated_restock_cost'] == 100


@pytest.mark.asyncio
async def test_marketplace_delivery_updates_stock_and_payment(monkeypatch):
    fake_db = FakeDB(
        suppliers=[{'id': 'supplier-1', 'name': 'Acme Vendor', 'phone': '0700', 'shop_id': 'shop-1', 'created_at': 'now'}],
        products=[{'id': 'prod-1', 'name': 'Milk', 'shop_id': 'shop-1', 'stock_quantity': 2, 'updated_at': 'now'}],
    )
    monkeypatch.setattr(server, 'db', fake_db)
    monkeypatch.setattr(server, 'client', SimpleNamespace())

    owner = {'id': 'owner-1', 'user_id': 'owner-1', 'shop_id': 'shop-1', 'role': 'owner'}
    created = await server.create_marketplace_order(
        server.MarketplaceOrderCreate(
            vendor_id='supplier-1',
            payment_method='mpesa',
            items=[server.MarketplaceOrderItem(product_id='prod-1', product_name='Milk', quantity=4, unit_cost=25)],
        ),
        owner=owner,
    )

    delivered = await server.receive_marketplace_order(
        created['id'],
        server.MarketplaceDeliveryUpdate(status='delivered', notes='Arrived'),
        owner=owner,
    )

    assert delivered['status'] == 'delivered'
    assert fake_db.products.documents[0]['stock_quantity'] == 6
    assert fake_db.payments.documents[0]['status'] == 'successful'


@pytest.mark.asyncio
async def test_payment_provider_comparison_recommends_paystack():
    owner = {'id': 'owner-1', 'user_id': 'owner-1', 'shop_id': 'shop-1', 'role': 'owner'}
    comparison = await server.compare_payment_providers(user=owner)

    assert comparison['recommended_provider'] == 'paystack'
    assert 'shop_id' in comparison['guidance']
