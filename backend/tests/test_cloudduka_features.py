"""Self-contained feature tests for CloudDuka core flows."""
import os
import sys
import uuid
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

    def sort(self, key, direction):
        self.documents = sorted(
            self.documents,
            key=lambda document: document.get(key, ''),
            reverse=direction == -1,
        )
        return self

    async def to_list(self, limit):
        if limit is None:
            return [deepcopy(document) for document in self.documents]
        return [deepcopy(document) for document in self.documents[:limit]]


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = [deepcopy(document) for document in (documents or [])]

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

    def test_orders_requires_auth(self, client):
        response = client.get('/api/orders')
        assert response.status_code in (401, 403)


class TestPublicCatalog:
    def test_public_stores_list(self, client):
        response = client.get('/api/public/stores')
        assert response.status_code == 200, response.text
        payload = response.json()
        assert isinstance(payload, list)
        assert any(store['id'] == TEST_SHOP_ID for store in payload)
        assert all(set(store.keys()) <= {'id', 'name', 'category'} for store in payload)

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
