"""Self-contained feature tests for CloudDuka core flows."""
import os
import sys
import uuid
import hmac
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_cloudduka')

from backend import server


class FakeInsertResult:
    def __init__(self, inserted_id=None):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, matched_count=0):
        self.matched_count = matched_count


class FakeDeleteResult:
    def __init__(self, deleted_count=0):
        self.deleted_count = deleted_count


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents
        self._offset = 0
        self._limit = None

    def sort(self, key, direction):
        self.documents = sorted(
            self.documents,
            key=lambda document: document.get(key, ''),
            reverse=direction == -1,
        )
        return self

    def skip(self, offset):
        self._offset = max(0, offset or 0)
        return self

    def limit(self, limit):
        self._limit = limit if limit is not None else self._limit
        return self

    async def to_list(self, limit):
        effective_limit = self._limit if self._limit is not None else limit
        sliced = self.documents[self._offset:]
        if effective_limit is None:
            return [deepcopy(document) for document in sliced]
        return [deepcopy(document) for document in sliced[:effective_limit]]


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = [deepcopy(document) for document in (documents or [])]
        self.indexes = []

    def _matches(self, document, query):
        for key, value in query.items():
            if key == '$or':
                if not any(self._matches(document, item) for item in value):
                    return False
                continue
            if key == '$expr':
                if '$lte' in value:
                    left, right = value['$lte']
                    left_value = document.get(left.lstrip('$'), 0)
                    right_value = document.get(right.lstrip('$'), 0)
                    if left_value > right_value:
                        return False
                continue

            actual = document.get(key)
            if isinstance(value, dict):
                if '$in' in value and actual not in value['$in']:
                    return False
                if '$gte' in value and actual < value['$gte']:
                    return False
                if '$lte' in value and actual > value['$lte']:
                    return False
                if '$lt' in value and actual >= value['$lt']:
                    return False
                if '$regex' in value:
                    needle = value['$regex'].lower()
                    haystack = str(actual or '').lower()
                    if needle not in haystack:
                        return False
                continue

            if actual != value:
                return False
        return True

    def _project(self, document, projection):
        cleaned = {key: value for key, value in document.items() if key != '_id'}
        if projection:
            excluded = {key for key, value in projection.items() if value == 0}
            for key in excluded:
                cleaned.pop(key, None)
        return deepcopy(cleaned)

    async def find_one(self, query, projection=None, sort=None):
        matches = [document for document in self.documents if self._matches(document, query)]
        if sort and matches:
            key, direction = sort[0]
            matches = sorted(matches, key=lambda document: document.get(key, ''), reverse=direction == -1)
        if not matches:
            return None
        return self._project(matches[0], projection)

    def find(self, query, projection=None):
        matches = [self._project(document, projection) for document in self.documents if self._matches(document, query)]
        return FakeCursor(matches)

    async def insert_one(self, document, session=None):
        self.documents.append(deepcopy(document))
        return FakeInsertResult(document.get('id'))

    async def update_one(self, query, update, upsert=False, session=None):
        for document in self.documents:
            if self._matches(document, query):
                if '$set' in update:
                    document.update(deepcopy(update['$set']))
                if '$inc' in update:
                    for key, value in update['$inc'].items():
                        document[key] = document.get(key, 0) + value
                if '$push' in update:
                    for key, value in update['$push'].items():
                        existing = document.get(key, [])
                        if not isinstance(existing, list):
                            existing = [existing]
                        existing.append(deepcopy(value))
                        document[key] = existing
                if '$setOnInsert' in update:
                    for key, value in update['$setOnInsert'].items():
                        document.setdefault(key, deepcopy(value))
                return FakeUpdateResult(matched_count=1)

        if upsert:
            new_doc = deepcopy(query)
            if '$set' in update:
                new_doc.update(deepcopy(update['$set']))
            if '$setOnInsert' in update:
                for key, value in update['$setOnInsert'].items():
                    new_doc.setdefault(key, deepcopy(value))
            self.documents.append(new_doc)
            return FakeUpdateResult(matched_count=1)
        return FakeUpdateResult(matched_count=0)

    async def delete_one(self, query):
        before = len(self.documents)
        self.documents = [document for document in self.documents if not self._matches(document, query)]
        return FakeDeleteResult(deleted_count=before - len(self.documents))

    async def delete_many(self, query):
        before = len(self.documents)
        self.documents = [document for document in self.documents if not self._matches(document, query)]
        return FakeDeleteResult(deleted_count=before - len(self.documents))

    async def count_documents(self, query):
        return len([document for document in self.documents if self._matches(document, query)])

    async def distinct(self, field, query):
        return sorted({document.get(field) for document in self.documents if self._matches(document, query) and document.get(field) is not None})

    async def create_index(self, *args, **kwargs):
        self.indexes.append({"args": args, "kwargs": kwargs})
        return None


class FakeDB:
    def __init__(self, **collections):
        defaults = {
            'users': [],
            'shops': [],
            'shop_users': [],
            'subscriptions': [],
            'products': [],
            'sales': [],
            'credit_customers': [],
            'credit_payments': [],
            'suppliers': [],
            'cart': [],
            'orders': [],
            'order_items': [],
            'payments': [],
            'notifications': [],
            'mpesa_transactions': [],
            'damaged_stock': [],
            'purchases': [],
            'customer_cart': [],
            'checkout_requests': [],
        }
        defaults.update(collections)
        for name, documents in defaults.items():
            setattr(self, name, FakeCollection(documents))


TEST_PHONE = '0712345678'
TEST_PIN = '1234'
TEST_SHOP_ID = 'shop-1'
TEST_USER_ID = 'owner-1'


@pytest.fixture()
def fake_db():
    now = '2026-03-22T00:00:00+00:00'
    pin_hash = server.hash_pin(TEST_PIN)
    return FakeDB(
        users=[{
            'id': TEST_USER_ID,
            'phone': TEST_PHONE,
            'pin_hash': pin_hash,
            'name': 'Owner',
            'email': 'owner@example.com',
            'email_verified': True,
            'default_shop_id': TEST_SHOP_ID,
            'trial_ends_at': '2999-01-01T00:00:00+00:00',
            'created_at': now,
        }],
        shops=[{'id': TEST_SHOP_ID, 'name': 'CloudDuka Demo', 'owner_id': TEST_USER_ID, 'created_at': now}],
        shop_users=[{'id': 'membership-1', 'user_id': TEST_USER_ID, 'shop_id': TEST_SHOP_ID, 'role': 'owner', 'created_at': now}],
        subscriptions=[{'id': 'sub-1', 'shop_id': TEST_SHOP_ID, 'owner_id': TEST_USER_ID, 'status': 'active', 'expires_at': '2999-01-01T00:00:00+00:00'}],
    )


@pytest.fixture()
def client(monkeypatch, fake_db):
    monkeypatch.setattr(server, 'db', fake_db)
    monkeypatch.setattr(server, 'client', SimpleNamespace(close=lambda: None))
    with TestClient(server.app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client):
    response = client.post('/api/auth/login', json={'phone': TEST_PHONE, 'pin': TEST_PIN})
    assert response.status_code == 200, response.text
    token = response.json()['token']
    return {'Authorization': f'Bearer {token}'}


class TestAuthLogin:
    def test_login_success(self, client):
        response = client.post('/api/auth/login', json={'phone': TEST_PHONE, 'pin': TEST_PIN})
        assert response.status_code == 200, response.text
        data = response.json()
        assert 'token' in data
        assert data['user']['phone'] == TEST_PHONE
        assert 'pin_hash' not in data['user']

    def test_login_invalid_credentials(self, client):
        response = client.post('/api/auth/login', json={'phone': '0000000000', 'pin': '9999'})
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        response = client.post('/api/auth/login', json={'phone': TEST_PHONE})
        assert response.status_code == 422


class TestCustomerAuth:
    def test_customer_registration_defaults_to_customer_role(self, client):
        response = client.post('/api/auth/register', json={
            'phone': '0799990000',
            'pin': '1234',
            'name': 'Customer One',
        })
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload['user']['role'] == 'customer'
        assert payload['user'].get('shop_id') is None

    def test_customer_login_and_sanitized_user(self, client):
        register = client.post('/api/auth/register', json={
            'phone': '0799990001',
            'pin': '1234',
            'name': 'Customer Two',
            'role': 'customer',
        })
        assert register.status_code == 200, register.text

        login = client.post('/api/auth/login', json={'phone': '0799990001', 'pin': '1234'})
        assert login.status_code == 200, login.text
        user = login.json()['user']
        assert user['role'] == 'customer'
        assert 'pin_hash' not in user

    def test_customer_cannot_access_owner_shop_routes(self, client):
        register = client.post('/api/auth/register', json={
            'phone': '0799990002',
            'pin': '1234',
            'name': 'Customer Three',
        })
        token = register.json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        blocked = client.get('/api/products', headers=headers)
        assert blocked.status_code == 403


class TestCustomerCart:
    def _customer_headers(self, client, phone='0788880000'):
        register = client.post('/api/auth/register', json={
            'phone': phone,
            'pin': '1234',
            'name': f'Customer {phone[-2:]}',
        })
        assert register.status_code == 200, register.text
        token = register.json()['token']
        return {'Authorization': f'Bearer {token}'}

    def test_customer_add_to_cart_valid_product(self, client, auth_headers):
        product = client.post('/api/products', json={
            'name': 'Catalog Product',
            'unit_price': 150.0,
            'stock_quantity': 20,
            'is_active': True,
        }, headers=auth_headers).json()
        customer_headers = self._customer_headers(client, phone='0788880001')

        response = client.post('/api/customer/cart', json={
            'product_id': product['id'],
            'shop_id': TEST_SHOP_ID,
            'quantity': 2,
        }, headers=customer_headers)
        assert response.status_code == 200, response.text
        item = response.json()
        assert item['product_id'] == product['id']
        assert item['name'] == 'Catalog Product'
        assert item['price'] == 150.0
        assert item['quantity'] == 2

    def test_customer_cart_rejects_inactive_product(self, client, auth_headers):
        product = client.post('/api/products', json={
            'name': 'Inactive Catalog Product',
            'unit_price': 99.0,
            'stock_quantity': 5,
            'is_active': False,
        }, headers=auth_headers).json()
        customer_headers = self._customer_headers(client, phone='0788880002')

        response = client.post('/api/customer/cart', json={
            'product_id': product['id'],
            'shop_id': TEST_SHOP_ID,
            'quantity': 1,
        }, headers=customer_headers)
        assert response.status_code == 400

    def test_customer_cart_rejects_invalid_quantity(self, client, auth_headers):
        product = client.post('/api/products', json={
            'name': 'Qty Validation Product',
            'unit_price': 75.0,
            'stock_quantity': 10,
            'is_active': True,
        }, headers=auth_headers).json()
        customer_headers = self._customer_headers(client, phone='0788880003')

        response = client.post('/api/customer/cart', json={
            'product_id': product['id'],
            'shop_id': TEST_SHOP_ID,
            'quantity': 0,
        }, headers=customer_headers)
        assert response.status_code == 422

    def test_customer_cart_customer_only_access(self, client, auth_headers):
        product = client.post('/api/products', json={
            'name': 'Customer Only Product',
            'unit_price': 120.0,
            'stock_quantity': 10,
            'is_active': True,
        }, headers=auth_headers).json()

        response = client.post('/api/customer/cart', json={
            'product_id': product['id'],
            'shop_id': TEST_SHOP_ID,
            'quantity': 1,
        }, headers=auth_headers)
        assert response.status_code == 403

    def test_customer_cart_retrieval_and_update(self, client, auth_headers):
        product = client.post('/api/products', json={
            'name': 'Retrieval Product',
            'unit_price': 200.0,
            'stock_quantity': 30,
            'is_active': True,
        }, headers=auth_headers).json()
        customer_headers = self._customer_headers(client, phone='0788880004')

        added = client.post('/api/customer/cart', json={
            'product_id': product['id'],
            'shop_id': TEST_SHOP_ID,
            'quantity': 1,
        }, headers=customer_headers)
        assert added.status_code == 200
        item_id = added.json()['id']

        cart = client.get('/api/customer/cart', headers=customer_headers)
        assert cart.status_code == 200
        assert len(cart.json()) == 1
        assert cart.json()[0]['quantity'] == 1

        updated = client.put(f'/api/customer/cart/{item_id}', json={'quantity': 4}, headers=customer_headers)
        assert updated.status_code == 200
        assert updated.json()['quantity'] == 4

        deleted = client.delete(f'/api/customer/cart/{item_id}', headers=customer_headers)
        assert deleted.status_code == 200

        empty = client.get('/api/customer/cart', headers=customer_headers)
        assert empty.status_code == 200
        assert empty.json() == []


class TestCustomerCheckoutBridge:
    def _customer_headers(self, client, phone='0777770000'):
        register = client.post('/api/auth/register', json={
            'phone': phone,
            'pin': '1234',
            'name': f'Checkout Customer {phone[-2:]}',
        })
        assert register.status_code == 200, register.text
        return {'Authorization': f"Bearer {register.json()['token']}"}

    def test_customer_checkout_success_and_cart_cleared(self, client, auth_headers):
        product = client.post('/api/products', json={
            'name': 'Checkout Product',
            'unit_price': 100.0,
            'stock_quantity': 5,
            'is_active': True,
        }, headers=auth_headers).json()
        customer_headers = self._customer_headers(client, phone='0777770001')

        add = client.post('/api/customer/cart', json={
            'product_id': product['id'],
            'shop_id': TEST_SHOP_ID,
            'quantity': 2,
        }, headers=customer_headers)
        assert add.status_code == 200, add.text

        checkout = client.post('/api/customer/checkout', json={'payment_method': 'cash'}, headers=customer_headers)
        assert checkout.status_code == 200, checkout.text
        payload = checkout.json()
        assert payload['order']['total_amount'] == 200.0

        assert server.db.customer_cart.documents == []
        created_order = next(order for order in server.db.orders.documents if order['id'] == payload['order']['id'])
        assert created_order.get('source') == 'customer_app'

    def test_customer_checkout_rejects_empty_cart(self, client):
        customer_headers = self._customer_headers(client, phone='0777770002')
        response = client.post('/api/customer/checkout', json={'payment_method': 'cash'}, headers=customer_headers)
        assert response.status_code == 400

    def test_customer_checkout_rejects_multi_shop_cart(self, client):
        customer_headers = self._customer_headers(client, phone='0777770003')
        customer = next(user for user in server.db.users.documents if user['phone'] == '0777770003')
        server.db.shops.documents.append({'id': 'shop-2', 'name': 'Second Shop', 'owner_id': TEST_USER_ID, 'created_at': 'now'})
        server.db.customer_cart.documents.extend([
            {'id': 'c1', 'user_id': customer['id'], 'product_id': 'p1', 'shop_id': TEST_SHOP_ID, 'quantity': 1, 'created_at': 'now'},
            {'id': 'c2', 'user_id': customer['id'], 'product_id': 'p2', 'shop_id': 'shop-2', 'quantity': 1, 'created_at': 'now'},
        ])
        response = client.post('/api/customer/checkout', json={'payment_method': 'cash'}, headers=customer_headers)
        assert response.status_code == 400

    def test_customer_checkout_rejects_insufficient_stock(self, client, auth_headers):
        product = client.post('/api/products', json={
            'name': 'Low Stock Checkout Product',
            'unit_price': 100.0,
            'stock_quantity': 1,
            'is_active': True,
        }, headers=auth_headers).json()
        customer_headers = self._customer_headers(client, phone='0777770004')

        add = client.post('/api/customer/cart', json={
            'product_id': product['id'],
            'shop_id': TEST_SHOP_ID,
            'quantity': 2,
        }, headers=customer_headers)
        # Add succeeds because customer cart does not reserve stock; failure is enforced at checkout
        assert add.status_code == 200, add.text

        checkout = client.post('/api/customer/checkout', json={'payment_method': 'cash'}, headers=customer_headers)
        assert checkout.status_code == 400


class TestCustomerOrdersDashboard:
    def _customer_headers(self, client, phone='0766660000'):
        register = client.post('/api/auth/register', json={
            'phone': phone,
            'pin': '1234',
            'name': f'Orders Customer {phone[-2:]}',
        })
        assert register.status_code == 200, register.text
        return {'Authorization': f"Bearer {register.json()['token']}"}

    def _create_customer_order(self, client, customer_headers, auth_headers, *, product_name='Order Product', amount=100.0):
        product = client.post('/api/products', json={
            'name': product_name,
            'unit_price': amount,
            'stock_quantity': 20,
            'is_active': True,
        }, headers=auth_headers).json()
        add = client.post('/api/customer/cart', json={
            'product_id': product['id'],
            'shop_id': TEST_SHOP_ID,
            'quantity': 1,
        }, headers=customer_headers)
        assert add.status_code == 200, add.text
        checkout = client.post('/api/customer/checkout', json={'payment_method': 'cash'}, headers=customer_headers)
        assert checkout.status_code == 200, checkout.text
        order_id = checkout.json()['order']['id']
        return order_id, product

    def test_list_customer_orders_sorted_desc(self, client, auth_headers):
        customer_headers = self._customer_headers(client, phone='0766660001')
        first_order_id, _ = self._create_customer_order(client, customer_headers, auth_headers, product_name='First')
        second_order_id, _ = self._create_customer_order(client, customer_headers, auth_headers, product_name='Second')

        # Ensure ordering is deterministic for the fake DB sort
        for order in server.db.orders.documents:
            if order['id'] == first_order_id:
                order['created_at'] = '2026-03-20T10:00:00+00:00'
            if order['id'] == second_order_id:
                order['created_at'] = '2026-03-21T10:00:00+00:00'

        response = client.get('/api/customer/orders', headers=customer_headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert len(payload) == 2
        assert payload[0]['order_id'] == second_order_id
        assert payload[1]['order_id'] == first_order_id

    def test_retrieve_single_customer_order(self, client, auth_headers):
        customer_headers = self._customer_headers(client, phone='0766660002')
        order_id, _ = self._create_customer_order(client, customer_headers, auth_headers, product_name='Single Order')

        response = client.get(f'/api/customer/orders/{order_id}', headers=customer_headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload['order_id'] == order_id
        assert payload['order_number'] == order_id
        assert isinstance(payload['items'], list)
        assert payload['payment']['status'] in {'successful', 'pending', 'on_credit'}

    def test_customer_cannot_access_another_users_order(self, client, auth_headers):
        customer_a_headers = self._customer_headers(client, phone='0766660003')
        customer_b_headers = self._customer_headers(client, phone='0766660004')
        order_id, _ = self._create_customer_order(client, customer_a_headers, auth_headers, product_name='Private Order')

        response = client.get(f'/api/customer/orders/{order_id}', headers=customer_b_headers)
        assert response.status_code == 404

    def test_order_structure_includes_items_and_unknown_payment_fallback(self, client):
        register = client.post('/api/auth/register', json={
            'phone': '0766660005',
            'pin': '1234',
            'name': 'Manual Order Customer',
        })
        assert register.status_code == 200, register.text
        token = register.json()['token']
        customer_headers = {'Authorization': f'Bearer {token}'}
        customer_user = next(user for user in server.db.users.documents if user['phone'] == '0766660005')

        order_id = 'manual-order-1'
        server.db.orders.documents.append({
            'id': order_id,
            'user_id': customer_user['id'],
            'shop_id': TEST_SHOP_ID,
            'total_amount': 450.0,
            'status': 'completed',
            'created_at': '2026-03-22T10:00:00+00:00',
        })
        server.db.order_items.documents.append({
            'id': 'manual-item-1',
            'order_id': order_id,
            'shop_id': TEST_SHOP_ID,
            'product_id': 'prod-xyz',
            'product_name': 'Manual Item',
            'quantity': 3,
            'unit_price': 150.0,
            'total': 450.0,
            'created_at': '2026-03-22T10:00:00+00:00',
        })

        response = client.get(f'/api/customer/orders/{order_id}', headers=customer_headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload['order_id'] == order_id
        assert payload['payment']['status'] == 'unknown'
        assert payload['payment']['method'] == 'unknown'
        assert len(payload['items']) == 1
        assert payload['items'][0] == {
            'product_id': 'prod-xyz',
            'name': 'Manual Item',
            'quantity': 3,
            'price': 150.0,
        }

    def test_customer_orders_pagination(self, client, auth_headers):
        customer_headers = self._customer_headers(client, phone='0766660006')
        self._create_customer_order(client, customer_headers, auth_headers, product_name='P1')
        self._create_customer_order(client, customer_headers, auth_headers, product_name='P2')

        first_page = client.get('/api/customer/orders?limit=1&offset=0', headers=customer_headers)
        second_page = client.get('/api/customer/orders?limit=1&offset=1', headers=customer_headers)
        assert first_page.status_code == 200
        assert second_page.status_code == 200
        assert len(first_page.json()) == 1
        assert len(second_page.json()) == 1


class TestPaymentFlows:
    def _create_checkout_payment(self, client, auth_headers, payment_method='mpesa'):
        product = client.post('/api/products', json={
            'name': f'{payment_method} Payment Product',
            'unit_price': 100.0,
            'stock_quantity': 10,
            'is_active': True,
        }, headers=auth_headers).json()
        client.post('/api/cart', json={'product_id': product['id'], 'quantity': 1}, headers=auth_headers)
        checkout = client.post('/api/orders/checkout', json={'payment_method': payment_method}, headers=auth_headers)
        assert checkout.status_code == 200, checkout.text
        order_id = checkout.json()['order']['id']
        payment = next(p for p in server.db.payments.documents if p['order_id'] == order_id)
        return order_id, payment

    def test_mpesa_pending_to_successful_flow(self, client, auth_headers):
        order_id, payment = self._create_checkout_payment(client, auth_headers, payment_method='mpesa')
        initiated = client.post('/api/payments/mpesa/initiate', json={
            'order_id': order_id,
            'payment_id': payment['id'],
            'phone': '254700000001',
        }, headers=auth_headers)
        assert initiated.status_code == 200, initiated.text
        assert initiated.json()['status'] == 'pending'

        confirm = client.post('/api/payments/mpesa/confirm', json={
            'payment_id': payment['id'],
            'status': 'successful',
            'checkout_request_id': initiated.json()['checkout_request_id'],
            'mpesa_receipt': 'MPESA123',
        }, headers=auth_headers)
        assert confirm.status_code == 200, confirm.text
        assert confirm.json()['status'] == 'successful'

        status = client.get(f"/api/payments/{payment['id']}/status", headers=auth_headers)
        assert status.status_code == 200
        assert status.json()['status'] == 'successful'
        assert status.json()['order_id'] == order_id

    def test_mpesa_failure_flow(self, client, auth_headers):
        order_id, payment = self._create_checkout_payment(client, auth_headers, payment_method='mpesa')
        initiated = client.post('/api/payments/mpesa/initiate', json={
            'order_id': order_id,
            'payment_id': payment['id'],
            'phone': '254700000002',
        }, headers=auth_headers)
        assert initiated.status_code == 200

        failed = client.post('/api/payments/mpesa/confirm', json={
            'payment_id': payment['id'],
            'status': 'failed',
            'checkout_request_id': initiated.json()['checkout_request_id'],
        }, headers=auth_headers)
        assert failed.status_code == 200
        assert failed.json()['status'] == 'failed'

    def test_paystack_webhook_updates_payment_status(self, client):
        os.environ['PAYSTACK_WEBHOOK_SECRET'] = 'test-secret'
        server.db.payments.documents.append({
            'id': 'pay-1',
            'shop_id': TEST_SHOP_ID,
            'order_id': 'order-1',
            'amount': 100,
            'method': 'paystack',
            'status': 'pending',
            'paystack_reference': 'ref-123',
            'created_at': 'now',
        })
        payload = {
            'event': 'charge.success',
            'data': {'reference': 'ref-123'},
        }
        raw_body = json.dumps(payload).encode()
        signature = hmac.new(
            os.environ['PAYSTACK_WEBHOOK_SECRET'].encode(),
            raw_body,
            hashlib.sha512,
        ).hexdigest()
        response = client.post(
            '/api/payments/paystack/webhook',
            content=raw_body,
            headers={'x-paystack-signature': signature, 'Content-Type': 'application/json'},
        )
        assert response.status_code == 200, response.text
        payment = next(p for p in server.db.payments.documents if p['id'] == 'pay-1')
        assert payment['status'] == 'successful'

    def test_paystack_webhook_rejects_missing_signature(self, client):
        os.environ['PAYSTACK_WEBHOOK_SECRET'] = 'test-secret'
        response = client.post('/api/payments/paystack/webhook', json={
            'event': 'charge.success',
            'data': {'reference': 'ref-123'},
        })
        assert response.status_code == 400

    def test_paystack_webhook_rejects_invalid_signature(self, client):
        os.environ['PAYSTACK_WEBHOOK_SECRET'] = 'test-secret'
        response = client.post(
            '/api/payments/paystack/webhook',
            json={'event': 'charge.success', 'data': {'reference': 'ref-123'}},
            headers={'x-paystack-signature': 'invalid'},
        )
        assert response.status_code == 400

    def test_legacy_paystack_webhook_rejects_missing_signature(self, client):
        os.environ['PAYSTACK_WEBHOOK_SECRET'] = 'test-secret'
        response = client.post('/api/paystack/webhook', json={
            'event': 'charge.success',
            'data': {'reference': 'ref-123'},
        })
        assert response.status_code == 400

    def test_duplicate_update_prevention(self, client, auth_headers):
        order_id, payment = self._create_checkout_payment(client, auth_headers, payment_method='mpesa')
        initiated = client.post('/api/payments/mpesa/initiate', json={
            'order_id': order_id,
            'payment_id': payment['id'],
            'phone': '254700000003',
        }, headers=auth_headers)
        assert initiated.status_code == 200

        first = client.post('/api/payments/mpesa/confirm', json={
            'payment_id': payment['id'],
            'status': 'successful',
            'checkout_request_id': initiated.json()['checkout_request_id'],
        }, headers=auth_headers)
        assert first.status_code == 200
        assert first.json()['updated'] is True

        second = client.post('/api/payments/mpesa/confirm', json={
            'payment_id': payment['id'],
            'status': 'failed',
            'checkout_request_id': initiated.json()['checkout_request_id'],
        }, headers=auth_headers)
        assert second.status_code == 200
        assert second.json()['updated'] is False
        assert second.json()['status'] == 'successful'


class TestCreditCustomers:
    def test_create_credit_customer(self, client, auth_headers):
        unique_id = str(uuid.uuid4())[:8]
        response = client.post('/api/credit-customers', json={
            'name': f'TEST_Customer_{unique_id}',
            'phone': f'07{unique_id[:8]}',
            'email': f'test_{unique_id}@example.com',
            'credit_limit': 15000.0,
        }, headers=auth_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['current_balance'] == 0.0
        assert data['credit_limit'] == 15000.0

    def test_list_credit_customers(self, client, auth_headers):
        client.post('/api/credit-customers', json={'name': 'Customer A', 'phone': '0700000001', 'credit_limit': 1000.0}, headers=auth_headers)
        response = client.get('/api/credit-customers', headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    def test_get_credit_customer_by_id(self, client, auth_headers):
        created = client.post('/api/credit-customers', json={'name': 'Customer B', 'phone': '0700000002', 'credit_limit': 5000.0}, headers=auth_headers)
        customer_id = created.json()['id']
        response = client.get(f'/api/credit-customers/{customer_id}', headers=auth_headers)
        assert response.status_code == 200
        assert response.json()['id'] == customer_id

    def test_update_credit_customer(self, client, auth_headers):
        created = client.post('/api/credit-customers', json={'name': 'Customer C', 'phone': '0700000003', 'credit_limit': 5000.0}, headers=auth_headers)
        customer_id = created.json()['id']
        response = client.put(f'/api/credit-customers/{customer_id}', json={'credit_limit': 20000.0}, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()['credit_limit'] == 20000.0


class TestProducts:
    def test_create_product(self, client, auth_headers):
        response = client.post('/api/products', json={
            'name': 'Demo Product',
            'unit_price': 150.0,
            'cost_price': 100.0,
            'stock_quantity': 50,
            'min_stock_level': 10,
            'unit': 'piece',
            'category': 'Test Category',
        }, headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()['stock_quantity'] == 50

    def test_list_products(self, client, auth_headers):
        client.post('/api/products', json={'name': 'List Product', 'unit_price': 100.0, 'stock_quantity': 20}, headers=auth_headers)
        response = client.get('/api/products', headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_update_product_stock(self, client, auth_headers):
        created = client.post('/api/products', json={'name': 'Stock Update Product', 'unit_price': 100.0, 'stock_quantity': 20}, headers=auth_headers)
        product_id = created.json()['id']
        response = client.put(f'/api/products/{product_id}', json={'stock_quantity': 100}, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()['stock_quantity'] == 100


class TestCreditSaleFlow:
    def test_credit_sale_updates_customer_balance(self, client, auth_headers):
        customer = client.post('/api/credit-customers', json={'name': 'Credit Buyer', 'phone': '0711111111', 'credit_limit': 50000.0}, headers=auth_headers).json()
        product = client.post('/api/products', json={'name': 'Credit Product', 'unit_price': 500.0, 'stock_quantity': 100}, headers=auth_headers).json()

        sale_response = client.post('/api/sales', json={
            'items': [{
                'product_id': product['id'],
                'product_name': product['name'],
                'quantity': 3,
                'unit_price': 500.0,
                'total': 1500.0,
            }],
            'payment_method': 'credit',
            'total_amount': 1500.0,
            'customer_id': customer['id'],
        }, headers=auth_headers)
        assert sale_response.status_code == 200, sale_response.text

        updated_customer = client.get(f"/api/credit-customers/{customer['id']}", headers=auth_headers).json()
        updated_product = client.get(f"/api/products/{product['id']}", headers=auth_headers).json()
        assert updated_customer['current_balance'] == 1500.0
        assert updated_product['stock_quantity'] == 97


class TestDashboard:
    def test_dashboard_stats(self, client, auth_headers):
        client.post('/api/products', json={'name': 'Low Stock Item', 'unit_price': 90.0, 'stock_quantity': 2, 'min_stock_level': 5}, headers=auth_headers)
        response = client.get('/api/reports/dashboard', headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'today' in data
        assert 'restock_suggestions' in data
        assert 'weekly_sales' in data


class TestCreditPayment:
    def test_record_credit_payment(self, client, auth_headers):
        customer = client.post('/api/credit-customers', json={'name': 'Payment Customer', 'phone': '0722222222', 'credit_limit': 10000.0}, headers=auth_headers).json()
        product = client.post('/api/products', json={'name': 'Payment Product', 'unit_price': 200.0, 'stock_quantity': 50}, headers=auth_headers).json()
        sale_response = client.post('/api/sales', json={
            'items': [{
                'product_id': product['id'],
                'product_name': product['name'],
                'quantity': 5,
                'unit_price': 200.0,
                'total': 1000.0,
            }],
            'payment_method': 'credit',
            'total_amount': 1000.0,
            'customer_id': customer['id'],
        }, headers=auth_headers)
        assert sale_response.status_code == 200

        payment_response = client.post('/api/credit-customers/payment', json={
            'customer_id': customer['id'],
            'amount': 500.0,
            'payment_method': 'cash',
            'notes': 'Partial payment',
        }, headers=auth_headers)
        assert payment_response.status_code == 200
        assert payment_response.json()['new_balance'] == 500.0


class TestCreditHistory:
    def test_get_credit_history(self, client, auth_headers):
        customer = client.post('/api/credit-customers', json={'name': 'History Customer', 'phone': '0733333333', 'credit_limit': 10000.0}, headers=auth_headers).json()
        product = client.post('/api/products', json={'name': 'History Product', 'unit_price': 100.0, 'stock_quantity': 20}, headers=auth_headers).json()
        client.post('/api/sales', json={
            'items': [{
                'product_id': product['id'],
                'product_name': product['name'],
                'quantity': 2,
                'unit_price': 100.0,
                'total': 200.0,
            }],
            'payment_method': 'credit',
            'total_amount': 200.0,
            'customer_id': customer['id'],
        }, headers=auth_headers)
        client.post('/api/credit-customers/payment', json={'customer_id': customer['id'], 'amount': 50.0, 'payment_method': 'cash'}, headers=auth_headers)

        response = client.get(f"/api/credit-customers/{customer['id']}/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data['sales']) == 1
        assert len(data['payments']) == 1


class TestSalesListing:
    def test_list_sales(self, client, auth_headers):
        product = client.post('/api/products', json={'name': 'Sales List Product', 'unit_price': 50.0, 'stock_quantity': 20}, headers=auth_headers).json()
        client.post('/api/sales', json={
            'items': [{
                'product_id': product['id'],
                'product_name': product['name'],
                'quantity': 1,
                'unit_price': 50.0,
                'total': 50.0,
            }],
            'payment_method': 'cash',
            'total_amount': 50.0,
        }, headers=auth_headers)
        response = client.get('/api/sales', headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) >= 1


class TestCreditReport:
    def test_credit_report(self, client, auth_headers):
        client.post('/api/credit-customers', json={'name': 'Report Customer', 'phone': '0744444444', 'credit_limit': 1000.0}, headers=auth_headers)
        response = client.get('/api/reports/credit', headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert 'summary' in data
        assert 'total_customers' in data['summary']


class TestCartAndOrders:
    def test_cart_crud_and_checkout(self, client, auth_headers):
        product = client.post('/api/products', json={'name': 'Cart Product', 'unit_price': 120.0, 'stock_quantity': 10}, headers=auth_headers).json()

        add_response = client.post('/api/cart', json={'product_id': product['id'], 'quantity': 2}, headers=auth_headers)
        assert add_response.status_code == 200, add_response.text

        cart_response = client.get('/api/cart', headers=auth_headers)
        assert cart_response.status_code == 200
        cart_payload = cart_response.json()
        assert len(cart_payload['items']) == 1
        item_id = cart_payload['items'][0]['id']

        update_response = client.put(f'/api/cart/{item_id}', json={'quantity': 3}, headers=auth_headers)
        assert update_response.status_code == 200

        checkout = client.post('/api/orders/checkout', json={'payment_method': 'cash'}, headers=auth_headers)
        assert checkout.status_code == 200, checkout.text
        assert checkout.json()['order']['total_amount'] == 360.0
        assert checkout.json()['order']['payment_status'] == 'successful'

    def test_cart_invalid_object_id_and_insufficient_stock(self, client, auth_headers):
        invalid_response = client.post('/api/cart', json={'product_id': 'bad-id', 'quantity': 1}, headers=auth_headers)
        assert invalid_response.status_code == 400

        product = client.post('/api/products', json={'name': 'Limited Product', 'unit_price': 50.0, 'stock_quantity': 1}, headers=auth_headers).json()
        stock_response = client.post('/api/cart', json={'product_id': product['id'], 'quantity': 2}, headers=auth_headers)
        assert stock_response.status_code == 400

    def test_orders_listing_and_detail_pagination(self, client, auth_headers):
        product = client.post('/api/products', json={'name': 'Paged Product', 'unit_price': 100.0, 'stock_quantity': 20}, headers=auth_headers).json()
        client.post('/api/cart', json={'product_id': product['id'], 'quantity': 1}, headers=auth_headers)
        checkout = client.post('/api/orders/checkout', json={'payment_method': 'cash'}, headers=auth_headers).json()
        order_id = checkout['order']['id']

        listing = client.get('/api/orders?limit=1&offset=0', headers=auth_headers)
        assert listing.status_code == 200
        assert listing.json()['pagination']['limit'] == 1
        assert listing.json()['pagination']['total'] >= 1

        detail = client.get(f'/api/orders/{order_id}', headers=auth_headers)
        assert detail.status_code == 200
        assert detail.json()['order']['id'] == order_id

        invalid_detail = client.get('/api/orders/not-an-id', headers=auth_headers)
        assert invalid_detail.status_code == 400

    def test_orders_owner_patch_and_cancel_rules(self, client, auth_headers):
        product = client.post('/api/products', json={'name': 'Patch Product', 'unit_price': 80.0, 'stock_quantity': 10}, headers=auth_headers).json()
        client.post('/api/cart', json={'product_id': product['id'], 'quantity': 1}, headers=auth_headers)
        checkout = client.post('/api/orders/checkout', json={'payment_method': 'cash'}, headers=auth_headers).json()
        order_id = checkout['order']['id']

        patch_response = client.patch(f'/api/orders/{order_id}', json={'status': 'completed'}, headers=auth_headers)
        assert patch_response.status_code == 200

        cancel_response = client.delete(f'/api/orders/{order_id}', headers=auth_headers)
        assert cancel_response.status_code == 400

    def test_checkout_idempotency_same_key_returns_same_order(self, client, auth_headers):
        product = client.post('/api/products', json={'name': 'Idempotent Product', 'unit_price': 60.0, 'stock_quantity': 10}, headers=auth_headers).json()
        client.post('/api/cart', json={'product_id': product['id'], 'quantity': 1}, headers=auth_headers)
        headers = {**auth_headers, 'Idempotency-Key': 'idem-1'}

        first = client.post('/api/orders/checkout', json={'payment_method': 'cash'}, headers=headers)
        second = client.post('/api/orders/checkout', json={'payment_method': 'cash'}, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()['order']['id'] == second.json()['order']['id']

    def test_checkout_idempotency_different_key_creates_new_order(self, client, auth_headers):
        product = client.post('/api/products', json={'name': 'Idempotent Product 2', 'unit_price': 70.0, 'stock_quantity': 10}, headers=auth_headers).json()
        client.post('/api/cart', json={'product_id': product['id'], 'quantity': 1}, headers=auth_headers)

        first = client.post('/api/orders/checkout', json={'payment_method': 'cash'}, headers={**auth_headers, 'Idempotency-Key': 'idem-a'})
        # Add to cart again for second checkout
        client.post('/api/cart', json={'product_id': product['id'], 'quantity': 1}, headers=auth_headers)
        second = client.post('/api/orders/checkout', json={'payment_method': 'cash'}, headers={**auth_headers, 'Idempotency-Key': 'idem-b'})
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()['order']['id'] != second.json()['order']['id']

    def test_orders_requires_auth(self, client):
        response = client.get('/api/orders')
        assert response.status_code in (401, 403)


class TestOrderLifecycle:
    def _create_checkout_order(self, client, auth_headers):
        product = client.post('/api/products', json={'name': 'Lifecycle Product', 'unit_price': 100.0, 'stock_quantity': 20}, headers=auth_headers).json()
        client.post('/api/cart', json={'product_id': product['id'], 'quantity': 1}, headers=auth_headers)
        checkout = client.post('/api/orders/checkout', json={'payment_method': 'mpesa'}, headers=auth_headers)
        assert checkout.status_code == 200, checkout.text
        return checkout.json()['order']['id']

    def _shopkeeper_headers(self, client, auth_headers, phone='0791110000'):
        created = client.post('/api/users', json={
            'phone': phone,
            'pin': '1234',
            'name': 'Lifecycle Keeper',
            'role': 'shopkeeper',
        }, headers=auth_headers)
        assert created.status_code == 200, created.text
        login = client.post('/api/auth/login', json={'phone': phone, 'pin': '1234'})
        assert login.status_code == 200, login.text
        return {'Authorization': f"Bearer {login.json()['token']}"}

    def test_payment_success_sets_order_paid(self, client, auth_headers):
        order_id = self._create_checkout_order(client, auth_headers)
        payment = next(p for p in server.db.payments.documents if p['order_id'] == order_id)
        initiated = client.post('/api/payments/mpesa/initiate', json={
            'order_id': order_id,
            'payment_id': payment['id'],
            'phone': '254711111111',
        }, headers=auth_headers)
        assert initiated.status_code == 200, initiated.text

        confirmed = client.post('/api/payments/mpesa/confirm', json={
            'payment_id': payment['id'],
            'status': 'successful',
            'checkout_request_id': initiated.json()['checkout_request_id'],
        }, headers=auth_headers)
        assert confirmed.status_code == 200

        order = next(o for o in server.db.orders.documents if o['id'] == order_id)
        assert order.get('lifecycle_status') == 'paid'

    def test_valid_transition_succeeds_and_history_records(self, client, auth_headers):
        order_id = self._create_checkout_order(client, auth_headers)
        payment = next(p for p in server.db.payments.documents if p['order_id'] == order_id)
        initiated = client.post('/api/payments/mpesa/initiate', json={'order_id': order_id, 'payment_id': payment['id'], 'phone': '254722222222'}, headers=auth_headers)
        client.post('/api/payments/mpesa/confirm', json={'payment_id': payment['id'], 'status': 'successful', 'checkout_request_id': initiated.json()['checkout_request_id']}, headers=auth_headers)

        to_processing = client.patch(f'/api/orders/{order_id}/status', json={'status': 'processing'}, headers=auth_headers)
        assert to_processing.status_code == 200, to_processing.text
        assert to_processing.json()['status'] == 'processing'
        assert len(to_processing.json()['status_history']) >= 3

    def test_invalid_transition_fails(self, client, auth_headers):
        order_id = self._create_checkout_order(client, auth_headers)
        invalid = client.patch(f'/api/orders/{order_id}/status', json={'status': 'ready'}, headers=auth_headers)
        assert invalid.status_code == 400

    def test_customer_cannot_update_order_status(self, client, auth_headers):
        order_id = self._create_checkout_order(client, auth_headers)
        customer_register = client.post('/api/auth/register', json={'phone': '0791110001', 'pin': '1234', 'name': 'Status Customer'})
        customer_headers = {'Authorization': f"Bearer {customer_register.json()['token']}"}
        response = client.patch(f'/api/orders/{order_id}/status', json={'status': 'processing'}, headers=customer_headers)
        assert response.status_code == 403

    def test_owner_and_shopkeeper_can_update_order_status(self, client, auth_headers):
        order_id = self._create_checkout_order(client, auth_headers)
        payment = next(p for p in server.db.payments.documents if p['order_id'] == order_id)
        initiated = client.post('/api/payments/mpesa/initiate', json={'order_id': order_id, 'payment_id': payment['id'], 'phone': '254733333333'}, headers=auth_headers)
        client.post('/api/payments/mpesa/confirm', json={'payment_id': payment['id'], 'status': 'successful', 'checkout_request_id': initiated.json()['checkout_request_id']}, headers=auth_headers)

        owner_update = client.patch(f'/api/orders/{order_id}/status', json={'status': 'processing'}, headers=auth_headers)
        assert owner_update.status_code == 200

        shopkeeper_headers = self._shopkeeper_headers(client, auth_headers, phone='0791110002')
        keeper_update = client.patch(f'/api/orders/{order_id}/status', json={'status': 'ready'}, headers=shopkeeper_headers)
        assert keeper_update.status_code == 200
        assert keeper_update.json()['status'] == 'ready'

    def test_delivered_order_cannot_be_changed(self, client, auth_headers):
        order_id = self._create_checkout_order(client, auth_headers)
        payment = next(p for p in server.db.payments.documents if p['order_id'] == order_id)
        initiated = client.post('/api/payments/mpesa/initiate', json={'order_id': order_id, 'payment_id': payment['id'], 'phone': '254744444444'}, headers=auth_headers)
        client.post('/api/payments/mpesa/confirm', json={'payment_id': payment['id'], 'status': 'successful', 'checkout_request_id': initiated.json()['checkout_request_id']}, headers=auth_headers)
        client.patch(f'/api/orders/{order_id}/status', json={'status': 'processing'}, headers=auth_headers)
        client.patch(f'/api/orders/{order_id}/status', json={'status': 'ready'}, headers=auth_headers)
        delivered = client.patch(f'/api/orders/{order_id}/status', json={'status': 'delivered'}, headers=auth_headers)
        assert delivered.status_code == 200

        blocked = client.patch(f'/api/orders/{order_id}/status', json={'status': 'cancelled'}, headers=auth_headers)
        assert blocked.status_code == 400

    def test_order_without_lifecycle_status_returns_pending(self, client, auth_headers):
        order_id = str(uuid.uuid4())
        server.db.orders.documents.append({
            'id': order_id,
            'shop_id': TEST_SHOP_ID,
            'user_id': TEST_USER_ID,
            'total_amount': 99.0,
            'created_at': '2026-03-22T00:00:00+00:00',
        })
        response = client.get(f'/api/orders/{order_id}', headers=auth_headers)
        assert response.status_code == 200
        assert response.json()['order']['status'] == 'pending'

    def test_order_without_status_history_returns_fallback_history(self, client, auth_headers):
        order_id = str(uuid.uuid4())
        server.db.orders.documents.append({
            'id': order_id,
            'shop_id': TEST_SHOP_ID,
            'user_id': TEST_USER_ID,
            'status': 'pending',
            'created_at': '2026-03-22T10:00:00+00:00',
        })
        response = client.get(f'/api/orders/{order_id}', headers=auth_headers)
        assert response.status_code == 200
        history = response.json()['order']['status_history']
        assert len(history) >= 1
        assert history[0]['status'] == 'pending'
        assert history[0]['timestamp'] == '2026-03-22T10:00:00+00:00'

    def test_status_and_lifecycle_match_after_update(self, client, auth_headers):
        order_id = self._create_checkout_order(client, auth_headers)
        payment = next(p for p in server.db.payments.documents if p['order_id'] == order_id)
        initiated = client.post('/api/payments/mpesa/initiate', json={'order_id': order_id, 'payment_id': payment['id'], 'phone': '254755555555'}, headers=auth_headers)
        client.post('/api/payments/mpesa/confirm', json={'payment_id': payment['id'], 'status': 'successful', 'checkout_request_id': initiated.json()['checkout_request_id']}, headers=auth_headers)
        client.patch(f'/api/orders/{order_id}/status', json={'status': 'processing'}, headers=auth_headers)
        order = next(o for o in server.db.orders.documents if o['id'] == order_id)
        assert order.get('status') == order.get('lifecycle_status') == 'processing'

    @pytest.mark.asyncio
    async def test_ensure_order_lifecycle_initialized_helper(self, client, auth_headers):
        order = {
            'id': str(uuid.uuid4()),
            'shop_id': TEST_SHOP_ID,
            'user_id': TEST_USER_ID,
            'created_at': '2026-03-22T00:00:00+00:00',
        }
        server.db.orders.documents.append(order)
        await server.ensure_order_lifecycle_initialized(order)
        updated = next(o for o in server.db.orders.documents if o['id'] == order['id'])
        assert updated['lifecycle_status'] == 'pending'
        assert updated['status'] == 'pending'
        assert len(updated.get('status_history', [])) >= 1

    def test_lifecycle_index_exists(self, client):
        lifecycle_indexes = [
            idx for idx in server.db.orders.indexes
            if idx['args'] and idx['args'][0] == [('lifecycle_status', 1), ('shop_id', 1)]
        ]
        assert lifecycle_indexes


class TestPublicCatalog:
    def test_public_stores_list(self, client):
        response = client.get('/api/public/stores')
        assert response.status_code == 200, response.text
        payload = response.json()
        assert isinstance(payload, list)
        assert any(store['id'] == TEST_SHOP_ID for store in payload)
        assert all(set(store.keys()) <= {'id', 'name', 'category'} for store in payload)

    def test_public_stores_pagination(self, client):
        server.db.shops.documents.extend([
            {'id': 'shop-2', 'name': 'Shop 2', 'owner_id': TEST_USER_ID, 'created_at': 'now', 'is_active': True},
            {'id': 'shop-3', 'name': 'Shop 3', 'owner_id': TEST_USER_ID, 'created_at': 'now', 'is_active': True},
        ])
        response = client.get('/api/public/stores?limit=1&offset=1')
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_public_store_products_filters_inactive_and_hides_internal_fields(self, client, auth_headers):
        active_product = client.post('/api/products', json={
            'name': 'Public Active',
            'unit_price': 120.0,
            'cost_price': 80.0,
            'stock_quantity': 3,
            'is_active': True,
            'image_url': 'https://example.com/a.jpg',
            'description': 'Visible product',
        }, headers=auth_headers).json()
        client.post('/api/products', json={
            'name': 'Public Inactive',
            'unit_price': 120.0,
            'cost_price': 80.0,
            'stock_quantity': 0,
            'is_active': False,
            'description': 'Hidden product',
        }, headers=auth_headers).json()

        response = client.get(f'/api/public/stores/{TEST_SHOP_ID}/products')
        assert response.status_code == 200, response.text
        products = response.json()

        assert any(product['id'] == active_product['id'] for product in products)
        assert all(product['name'] != 'Public Inactive' for product in products)
        assert all('cost_price' not in product for product in products)
        assert all(
            set(product.keys()) == {'id', 'name', 'price', 'image_url', 'description', 'availability'}
            for product in products
        )

    def test_public_single_product_view(self, client, auth_headers):
        in_stock = client.post('/api/products', json={
            'name': 'Single Product',
            'unit_price': 99.0,
            'stock_quantity': 1,
            'is_active': True,
        }, headers=auth_headers).json()
        out_of_stock = client.post('/api/products', json={
            'name': 'Out of Stock Product',
            'unit_price': 49.0,
            'stock_quantity': 0,
            'is_active': True,
        }, headers=auth_headers).json()
        inactive = client.post('/api/products', json={
            'name': 'Inactive Product',
            'unit_price': 49.0,
            'stock_quantity': 5,
            'is_active': False,
        }, headers=auth_headers).json()

        in_stock_response = client.get(f"/api/public/products/{in_stock['id']}")
        assert in_stock_response.status_code == 200
        assert in_stock_response.json()['availability'] == 'in_stock'

        out_stock_response = client.get(f"/api/public/products/{out_of_stock['id']}")
        assert out_stock_response.status_code == 200
        assert out_stock_response.json()['availability'] == 'out_of_stock'

        inactive_response = client.get(f"/api/public/products/{inactive['id']}")
        assert inactive_response.status_code == 404

    def test_public_products_list_pagination(self, client, auth_headers):
        client.post('/api/products', json={'name': 'Public List A', 'unit_price': 20.0, 'stock_quantity': 5, 'is_active': True}, headers=auth_headers)
        client.post('/api/products', json={'name': 'Public List B', 'unit_price': 25.0, 'stock_quantity': 5, 'is_active': True}, headers=auth_headers)
        response = client.get('/api/public/products?limit=1&offset=0')
        assert response.status_code == 200
        assert len(response.json()) == 1
