import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_cloudduka_social')

from backend import server
from backend.tests.test_cloudduka_features import FakeDB

TEST_PHONE = '0711002200'
TEST_PIN = '1234'
TEST_SHOP_ID = 'shop-social-1'
TEST_USER_ID = 'owner-social-1'


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
        shops=[{
            'id': TEST_SHOP_ID,
            'name': 'Social Demo Shop',
            'owner_id': TEST_USER_ID,
            'description': 'Social-first catalog',
            'logo_url': 'https://cdn.example.com/logo.png',
            'subscription': {'plan': 'online', 'status': 'active', 'expires_at': None},
            'is_active': True,
            'created_at': now,
        }],
        shop_users=[{'id': 'membership-social-1', 'user_id': TEST_USER_ID, 'shop_id': TEST_SHOP_ID, 'role': 'owner', 'created_at': now}],
        subscriptions=[{'id': 'sub-social-1', 'shop_id': TEST_SHOP_ID, 'owner_id': TEST_USER_ID, 'status': 'active', 'expires_at': '2999-01-01T00:00:00+00:00'}],
        products=[
            {
                'id': 'prod-social-1',
                'shop_id': TEST_SHOP_ID,
                'name': 'Tomatoes 1kg',
                'description': 'Fresh farm tomatoes',
                'unit_price': 120.0,
                'stock_quantity': 15,
                'category': 'Groceries',
                'brand': 'FarmCo',
                'image_url': 'https://cdn.example.com/tomatoes.jpg',
                'created_at': now,
            },
            {
                'id': 'prod-social-2',
                'shop_id': TEST_SHOP_ID,
                'name': 'Rice 2kg',
                'description': 'Premium rice',
                'unit_price': 250.0,
                'stock_quantity': 8,
                'category': 'Food',
                'brand': 'GrainCo',
                'image_url': 'https://cdn.example.com/rice.jpg',
                'created_at': now,
            },
        ],
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


def test_social_product_feed_contains_required_fields(client, auth_headers):
    response = client.get('/api/social/product-feed', headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['count'] == 2
    first = payload['items'][0]
    required = {
        'product_id', 'title', 'description', 'price', 'availability',
        'image_url', 'product_url', 'category', 'brand'
    }
    assert required.issubset(first.keys())


def test_whatsapp_ingestion_creates_order_and_deducts_inventory(client, auth_headers):
    response = client.post(
        '/api/integrations/whatsapp/order',
        json={
            'phone_number': '+254700000001',
            'product_ids': [
                {'product_id': 'prod-social-1', 'quantity': 2},
                {'product_id': 'prod-social-2', 'quantity': 1},
                {'product_id': 'missing-prod', 'quantity': 1},
            ],
            'metadata': {'payment_method': 'cash', 'customer_name': 'Amina'}
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['status'] == 'completed'
    assert payload['payment_method'] == 'cash'
    assert payload['unknown_items'] and payload['unknown_items'][0]['product_id'] == 'missing-prod'

    prod_1 = next(item for item in server.db.products.documents if item['id'] == 'prod-social-1')
    prod_2 = next(item for item in server.db.products.documents if item['id'] == 'prod-social-2')
    assert prod_1['stock_quantity'] == 13
    assert prod_2['stock_quantity'] == 7


def test_social_webhook_requires_signature_when_configured(client, monkeypatch):
    monkeypatch.setenv('SOCIAL_WEBHOOK_SECRET', 'secret-123')
    bad = client.post(
        '/api/webhooks/social/whatsapp',
        json={
            'shop_id': TEST_SHOP_ID,
            'phone_number': '+254700000009',
            'items': [{'product_id': 'prod-social-1', 'quantity': 1}],
            'metadata': {'payment_method': 'cash'},
        },
        headers={'X-Social-Secret': 'wrong-secret'},
    )
    assert bad.status_code == 401
