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

    def test_login_invalid_credentials(self, client):
        response = client.post('/api/auth/login', json={'phone': '0000000000', 'pin': '9999'})
        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        response = client.post('/api/auth/login', json={'phone': TEST_PHONE})
        assert response.status_code == 422


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

