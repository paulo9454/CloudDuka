"""
CloudDuka POS - Feature Testing
Tests for: Login, Credit Customers, Stock Auto-Calculation, Credit Sales, Dashboard
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_PHONE = "0712345678"
TEST_PIN = "1234"

class TestAuthLogin:
    """Test login with phone number and PIN"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "phone": TEST_PHONE,
            "pin": TEST_PIN
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token not in response"
        assert "user" in data, "User not in response"
        assert data["user"]["phone"] == TEST_PHONE
        print(f"✓ Login successful for {TEST_PHONE}")
        return data["token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "phone": "0000000000",
            "pin": "9999"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")
    
    def test_login_missing_fields(self):
        """Test login with missing fields"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "phone": TEST_PHONE
        })
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Missing fields correctly rejected")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "phone": TEST_PHONE,
        "pin": TEST_PIN
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    return response.json()["token"]


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestCreditCustomers:
    """Test Credit Customer CRUD operations"""
    
    def test_create_credit_customer(self, auth_headers):
        """Create a new credit customer"""
        unique_id = str(uuid.uuid4())[:8]
        customer_data = {
            "name": f"TEST_Customer_{unique_id}",
            "phone": f"07{unique_id[:8]}",
            "email": f"test_{unique_id}@example.com",
            "credit_limit": 15000.0
        }
        response = requests.post(
            f"{BASE_URL}/api/credit-customers",
            json=customer_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        assert data["name"] == customer_data["name"]
        assert data["phone"] == customer_data["phone"]
        assert data["credit_limit"] == customer_data["credit_limit"]
        assert data["current_balance"] == 0.0
        assert "id" in data
        print(f"✓ Created credit customer: {data['name']} (ID: {data['id'][:8]}...)")
        return data
    
    def test_list_credit_customers(self, auth_headers):
        """List all credit customers"""
        response = requests.get(
            f"{BASE_URL}/api/credit-customers",
            headers=auth_headers
        )
        assert response.status_code == 200, f"List failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} credit customers")
        return data
    
    def test_get_credit_customer_by_id(self, auth_headers):
        """Get a specific credit customer"""
        # First create a customer
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(
            f"{BASE_URL}/api/credit-customers",
            json={
                "name": f"TEST_GetById_{unique_id}",
                "phone": f"08{unique_id[:8]}",
                "credit_limit": 5000.0
            },
            headers=auth_headers
        )
        assert create_response.status_code == 200
        customer_id = create_response.json()["id"]
        
        # Get by ID
        response = requests.get(
            f"{BASE_URL}/api/credit-customers/{customer_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get failed: {response.text}"
        data = response.json()
        assert data["id"] == customer_id
        print(f"✓ Retrieved customer by ID: {customer_id[:8]}...")
    
    def test_update_credit_customer(self, auth_headers):
        """Update a credit customer"""
        # First create a customer
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(
            f"{BASE_URL}/api/credit-customers",
            json={
                "name": f"TEST_Update_{unique_id}",
                "phone": f"09{unique_id[:8]}",
                "credit_limit": 5000.0
            },
            headers=auth_headers
        )
        assert create_response.status_code == 200
        customer_id = create_response.json()["id"]
        
        # Update
        response = requests.put(
            f"{BASE_URL}/api/credit-customers/{customer_id}",
            json={"credit_limit": 20000.0},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["credit_limit"] == 20000.0
        print(f"✓ Updated customer credit limit to 20000")


class TestProducts:
    """Test Product CRUD and stock management"""
    
    def test_create_product(self, auth_headers):
        """Create a new product"""
        unique_id = str(uuid.uuid4())[:8]
        product_data = {
            "name": f"TEST_Product_{unique_id}",
            "unit_price": 150.0,
            "cost_price": 100.0,
            "stock_quantity": 50,
            "min_stock_level": 10,
            "unit": "piece",
            "category": "Test Category"
        }
        response = requests.post(
            f"{BASE_URL}/api/products",
            json=product_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        assert data["name"] == product_data["name"]
        assert data["unit_price"] == product_data["unit_price"]
        assert data["stock_quantity"] == product_data["stock_quantity"]
        assert "id" in data
        print(f"✓ Created product: {data['name']} (Stock: {data['stock_quantity']})")
        return data
    
    def test_list_products(self, auth_headers):
        """List all products"""
        response = requests.get(
            f"{BASE_URL}/api/products",
            headers=auth_headers
        )
        assert response.status_code == 200, f"List failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} products")
        return data
    
    def test_update_product_stock(self, auth_headers):
        """Update product stock quantity"""
        # First create a product
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(
            f"{BASE_URL}/api/products",
            json={
                "name": f"TEST_StockUpdate_{unique_id}",
                "unit_price": 100.0,
                "stock_quantity": 20
            },
            headers=auth_headers
        )
        assert create_response.status_code == 200
        product_id = create_response.json()["id"]
        
        # Update stock
        response = requests.put(
            f"{BASE_URL}/api/products/{product_id}",
            json={"stock_quantity": 100},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["stock_quantity"] == 100
        print(f"✓ Updated product stock to 100 units")


class TestCreditSaleFlow:
    """Test complete credit sale flow"""
    
    def test_credit_sale_updates_customer_balance(self, auth_headers):
        """Test that credit sale updates customer balance"""
        unique_id = str(uuid.uuid4())[:8]
        
        # 1. Create a credit customer
        customer_response = requests.post(
            f"{BASE_URL}/api/credit-customers",
            json={
                "name": f"TEST_CreditSale_{unique_id}",
                "phone": f"07{unique_id[:8]}",
                "credit_limit": 50000.0
            },
            headers=auth_headers
        )
        assert customer_response.status_code == 200
        customer = customer_response.json()
        customer_id = customer["id"]
        initial_balance = customer["current_balance"]
        print(f"✓ Created customer with initial balance: {initial_balance}")
        
        # 2. Create a product
        product_response = requests.post(
            f"{BASE_URL}/api/products",
            json={
                "name": f"TEST_CreditProduct_{unique_id}",
                "unit_price": 500.0,
                "stock_quantity": 100
            },
            headers=auth_headers
        )
        assert product_response.status_code == 200
        product = product_response.json()
        product_id = product["id"]
        print(f"✓ Created product: {product['name']} @ {product['unit_price']} KES")
        
        # 3. Create a credit sale
        sale_amount = 1500.0  # 3 units @ 500 each
        sale_response = requests.post(
            f"{BASE_URL}/api/sales",
            json={
                "items": [{
                    "product_id": product_id,
                    "product_name": product["name"],
                    "quantity": 3,
                    "unit_price": 500.0,
                    "total": 1500.0
                }],
                "payment_method": "credit",
                "total_amount": sale_amount,
                "customer_id": customer_id
            },
            headers=auth_headers
        )
        assert sale_response.status_code == 200, f"Sale failed: {sale_response.text}"
        sale = sale_response.json()
        assert sale["payment_method"] == "credit"
        assert sale["customer_id"] == customer_id
        print(f"✓ Created credit sale: {sale['receipt_number']}")
        
        # 4. Verify customer balance updated
        customer_check = requests.get(
            f"{BASE_URL}/api/credit-customers/{customer_id}",
            headers=auth_headers
        )
        assert customer_check.status_code == 200
        updated_customer = customer_check.json()
        expected_balance = initial_balance + sale_amount
        assert updated_customer["current_balance"] == expected_balance, \
            f"Expected balance {expected_balance}, got {updated_customer['current_balance']}"
        print(f"✓ Customer balance updated: {initial_balance} → {updated_customer['current_balance']}")
        
        # 5. Verify product stock reduced
        product_check = requests.get(
            f"{BASE_URL}/api/products/{product_id}",
            headers=auth_headers
        )
        assert product_check.status_code == 200
        updated_product = product_check.json()
        assert updated_product["stock_quantity"] == 97, \
            f"Expected stock 97, got {updated_product['stock_quantity']}"
        print(f"✓ Product stock reduced: 100 → {updated_product['stock_quantity']}")
        
        return sale


class TestDashboard:
    """Test dashboard statistics"""
    
    def test_dashboard_stats(self, auth_headers):
        """Test dashboard returns correct statistics"""
        response = requests.get(
            f"{BASE_URL}/api/reports/dashboard",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "today" in data
        assert "total" in data["today"]
        assert "count" in data["today"]
        assert "cash" in data["today"]
        assert "mpesa" in data["today"]
        assert "credit" in data["today"]
        assert "low_stock_count" in data
        assert "total_credit_outstanding" in data
        assert "weekly_sales" in data
        
        print(f"✓ Dashboard stats retrieved:")
        print(f"  - Today's total: {data['today']['total']} KES")
        print(f"  - Today's transactions: {data['today']['count']}")
        print(f"  - Cash sales: {data['today']['cash']} KES")
        print(f"  - M-Pesa sales: {data['today']['mpesa']} KES")
        print(f"  - Credit sales: {data['today']['credit']} KES")
        print(f"  - Low stock items: {data['low_stock_count']}")
        print(f"  - Total credit outstanding: {data['total_credit_outstanding']} KES")
        
        return data


class TestCreditPayment:
    """Test credit payment recording"""
    
    def test_record_credit_payment(self, auth_headers):
        """Test recording a payment from credit customer"""
        unique_id = str(uuid.uuid4())[:8]
        
        # 1. Create customer with balance
        customer_response = requests.post(
            f"{BASE_URL}/api/credit-customers",
            json={
                "name": f"TEST_Payment_{unique_id}",
                "phone": f"07{unique_id[:8]}",
                "credit_limit": 10000.0
            },
            headers=auth_headers
        )
        assert customer_response.status_code == 200
        customer = customer_response.json()
        customer_id = customer["id"]
        
        # 2. Create a product and make a credit sale to add balance
        product_response = requests.post(
            f"{BASE_URL}/api/products",
            json={
                "name": f"TEST_PaymentProduct_{unique_id}",
                "unit_price": 200.0,
                "stock_quantity": 50
            },
            headers=auth_headers
        )
        assert product_response.status_code == 200
        product = product_response.json()
        
        # Make credit sale
        sale_response = requests.post(
            f"{BASE_URL}/api/sales",
            json={
                "items": [{
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "quantity": 5,
                    "unit_price": 200.0,
                    "total": 1000.0
                }],
                "payment_method": "credit",
                "total_amount": 1000.0,
                "customer_id": customer_id
            },
            headers=auth_headers
        )
        assert sale_response.status_code == 200
        print(f"✓ Created credit sale of 1000 KES")
        
        # 3. Record payment
        payment_response = requests.post(
            f"{BASE_URL}/api/credit-customers/payment",
            json={
                "customer_id": customer_id,
                "amount": 500.0,
                "payment_method": "cash",
                "notes": "Partial payment"
            },
            headers=auth_headers
        )
        assert payment_response.status_code == 200, f"Payment failed: {payment_response.text}"
        payment_result = payment_response.json()
        assert payment_result["new_balance"] == 500.0
        print(f"✓ Recorded payment of 500 KES, new balance: {payment_result['new_balance']}")
        
        # 4. Verify balance
        customer_check = requests.get(
            f"{BASE_URL}/api/credit-customers/{customer_id}",
            headers=auth_headers
        )
        assert customer_check.status_code == 200
        assert customer_check.json()["current_balance"] == 500.0
        print(f"✓ Customer balance verified: 500 KES")


class TestCreditHistory:
    """Test credit customer transaction history"""
    
    def test_get_credit_history(self, auth_headers):
        """Test getting credit customer transaction history"""
        # Get list of customers
        customers_response = requests.get(
            f"{BASE_URL}/api/credit-customers",
            headers=auth_headers
        )
        assert customers_response.status_code == 200
        customers = customers_response.json()
        
        if len(customers) == 0:
            pytest.skip("No credit customers to test history")
        
        customer_id = customers[0]["id"]
        
        # Get history
        response = requests.get(
            f"{BASE_URL}/api/credit-customers/{customer_id}/history",
            headers=auth_headers
        )
        assert response.status_code == 200, f"History failed: {response.text}"
        data = response.json()
        assert "sales" in data
        assert "payments" in data
        print(f"✓ Retrieved history for customer {customer_id[:8]}...")
        print(f"  - Sales: {len(data['sales'])}")
        print(f"  - Payments: {len(data['payments'])}")


class TestSalesListing:
    """Test sales listing and filtering"""
    
    def test_list_sales(self, auth_headers):
        """Test listing sales"""
        response = requests.get(
            f"{BASE_URL}/api/sales",
            headers=auth_headers
        )
        assert response.status_code == 200, f"List failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} sales")
        
        # Check for credit sales
        credit_sales = [s for s in data if s["payment_method"] == "credit"]
        print(f"  - Credit sales: {len(credit_sales)}")
        
        return data


class TestCreditReport:
    """Test credit report endpoint"""
    
    def test_credit_report(self, auth_headers):
        """Test credit report generation"""
        response = requests.get(
            f"{BASE_URL}/api/reports/credit",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Report failed: {response.text}"
        data = response.json()
        
        assert "customers" in data
        assert "summary" in data
        assert "total_customers" in data["summary"]
        assert "customers_with_balance" in data["summary"]
        assert "total_outstanding" in data["summary"]
        
        print(f"✓ Credit report generated:")
        print(f"  - Total customers: {data['summary']['total_customers']}")
        print(f"  - With balance: {data['summary']['customers_with_balance']}")
        print(f"  - Total outstanding: {data['summary']['total_outstanding']} KES")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
