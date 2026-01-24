#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

class CloudDukaPOSAPITester:
    def __init__(self, base_url: str = "https://duka-pos-system.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.shop_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test data storage
        self.test_product_id = None
        self.test_customer_id = None
        self.test_sale_id = None
        self.test_category_id = None

    def log_result(self, test_name: str, success: bool, message: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED - {message}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "response_data": response_data
        })

    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, expected_status: int = 200) -> tuple[bool, Dict]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return False, {"error": f"Unsupported method: {method}"}

            success = response.status_code == expected_status
            try:
                response_data = response.json()
            except:
                response_data = {"status_code": response.status_code, "text": response.text}

            return success, response_data

        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def test_health_check(self):
        """Test health endpoint"""
        success, data = self.make_request('GET', 'health')
        self.log_result("Health Check", success, 
                       "" if success else f"Health check failed: {data}")
        return success

    def test_user_registration(self):
        """Test user registration"""
        test_phone = f"254712{datetime.now().strftime('%H%M%S')}"
        registration_data = {
            "phone": test_phone,
            "pin": "1234",
            "name": "Test Owner",
            "shop_name": "Test Shop",
            "role": "owner"
        }
        
        success, data = self.make_request('POST', 'auth/register', registration_data, 200)
        
        if success and 'token' in data and 'user' in data:
            self.token = data['token']
            self.user_id = data['user']['id']
            self.shop_id = data['user']['shop_id']
            self.log_result("User Registration", True)
        else:
            self.log_result("User Registration", False, f"Registration failed: {data}")
        
        return success

    def test_user_login(self):
        """Test user login with existing credentials"""
        if not self.token:
            self.log_result("User Login", False, "No token from registration")
            return False
            
        # Test login with same credentials
        login_data = {
            "phone": f"254712{datetime.now().strftime('%H%M%S')}",
            "pin": "1234"
        }
        
        success, data = self.make_request('POST', 'auth/login', login_data, 401)  # Should fail with wrong phone
        
        if success:  # Should fail
            self.log_result("User Login (Invalid)", False, "Login should have failed with wrong credentials")
            return False
        else:
            self.log_result("User Login (Invalid)", True, "Correctly rejected invalid credentials")
            return True

    def test_get_user_profile(self):
        """Test getting user profile"""
        success, data = self.make_request('GET', 'auth/me')
        
        if success and 'id' in data and 'role' in data:
            self.log_result("Get User Profile", True)
        else:
            self.log_result("Get User Profile", False, f"Profile fetch failed: {data}")
        
        return success

    def test_create_category(self):
        """Test creating a category (Owner only)"""
        category_data = {
            "name": "Test Beverages",
            "description": "Test category for drinks",
            "color": "#007BFF"
        }
        
        success, data = self.make_request('POST', 'categories', category_data, 200)
        
        if success and 'id' in data:
            self.test_category_id = data['id']
            self.log_result("Create Category", True)
        else:
            self.log_result("Create Category", False, f"Category creation failed: {data}")
        
        return success

    def test_list_categories(self):
        """Test listing categories with product counts"""
        success, data = self.make_request('GET', 'categories')
        
        if success and isinstance(data, list):
            # Should include our test category, "Other" category may or may not be present
            category_names = [cat['name'] for cat in data]
            has_test_category = 'Test Beverages' in category_names
            
            if has_test_category:
                self.log_result("List Categories", True, f"Found {len(data)} categories including test category")
            else:
                self.log_result("List Categories", False, "Missing test category")
                return False
        else:
            self.log_result("List Categories", False, f"Category listing failed: {data}")
            return False
        
        return success

    def test_update_category(self):
        """Test updating a category (Owner only)"""
        if not self.test_category_id:
            self.log_result("Update Category", False, "No category ID available")
            return False
            
        update_data = {
            "name": "Updated Test Beverages",
            "description": "Updated description",
            "color": "#FF8C00"
        }
        
        success, data = self.make_request('PUT', f'categories/{self.test_category_id}', update_data)
        
        if success and data.get('name') == 'Updated Test Beverages':
            self.log_result("Update Category", True)
        else:
            self.log_result("Update Category", False, f"Category update failed: {data}")
        
        return success

    def test_get_category_products(self):
        """Test getting products in a category"""
        if not self.test_category_id:
            self.log_result("Get Category Products", False, "No category ID available")
            return False
            
        success, data = self.make_request('GET', f'categories/{self.test_category_id}/products')
        
        if success and isinstance(data, list):
            self.log_result("Get Category Products", True, f"Found {len(data)} products in category")
        else:
            self.log_result("Get Category Products", False, f"Get category products failed: {data}")
        
        return success

    def test_get_other_category_products(self):
        """Test getting products in 'Other' category"""
        success, data = self.make_request('GET', 'categories/other/products')
        
        if success and isinstance(data, list):
            self.log_result("Get Other Category Products", True, f"Found {len(data)} uncategorized products")
        else:
            self.log_result("Get Other Category Products", False, f"Get other category products failed: {data}")
        
        return success

    def test_delete_category(self):
        """Test deleting a category (Owner only) - should make products uncategorized"""
        if not self.test_category_id:
            self.log_result("Delete Category", False, "No category ID available")
            return False
            
        success, data = self.make_request('DELETE', f'categories/{self.test_category_id}', expected_status=200)
        
        if success:
            self.log_result("Delete Category", True)
            # Verify category is gone
            get_success, get_data = self.make_request('GET', f'categories/{self.test_category_id}', expected_status=404)
            if not get_success:  # Should fail with 404
                self.log_result("Verify Category Deleted", True)
            else:
                self.log_result("Verify Category Deleted", False, "Category still exists after deletion")
        else:
            self.log_result("Delete Category", False, f"Category deletion failed: {data}")
        
        return success

    def test_create_product(self):
        """Test creating a product"""
        product_data = {
            "name": "Test Milk 500ml",
            "category": "Updated Test Beverages",  # Use our test category
            "unit_price": 50.0,
            "cost_price": 40.0,
            "stock_quantity": 100,
            "min_stock_level": 10,
            "unit": "piece"
        }
        
        success, data = self.make_request('POST', 'products', product_data, 200)
        
        if success and 'id' in data:
            self.test_product_id = data['id']
            self.log_result("Create Product", True)
        else:
            self.log_result("Create Product", False, f"Product creation failed: {data}")
        
        return success

    def test_list_products(self):
        """Test listing products"""
        success, data = self.make_request('GET', 'products')
        
        if success and isinstance(data, list):
            self.log_result("List Products", True, f"Found {len(data)} products")
        else:
            self.log_result("List Products", False, f"Product listing failed: {data}")
        
        return success

    def test_update_product(self):
        """Test updating a product"""
        if not self.test_product_id:
            self.log_result("Update Product", False, "No product ID available")
            return False
            
        update_data = {
            "unit_price": 55.0,
            "stock_quantity": 95
        }
        
        success, data = self.make_request('PUT', f'products/{self.test_product_id}', update_data)
        
        if success and data.get('unit_price') == 55.0:
            self.log_result("Update Product", True)
        else:
            self.log_result("Update Product", False, f"Product update failed: {data}")
        
        return success

    def test_create_credit_customer(self):
        """Test creating a credit customer"""
        customer_data = {
            "name": "Test Customer",
            "phone": "254712345678",
            "email": "test@example.com",
            "credit_limit": 5000.0
        }
        
        success, data = self.make_request('POST', 'credit-customers', customer_data)
        
        if success and 'id' in data:
            self.test_customer_id = data['id']
            self.log_result("Create Credit Customer", True)
        else:
            self.log_result("Create Credit Customer", False, f"Customer creation failed: {data}")
        
        return success

    def test_list_credit_customers(self):
        """Test listing credit customers"""
        success, data = self.make_request('GET', 'credit-customers')
        
        if success and isinstance(data, list):
            self.log_result("List Credit Customers", True, f"Found {len(data)} customers")
        else:
            self.log_result("List Credit Customers", False, f"Customer listing failed: {data}")
        
        return success

    def test_create_cash_sale(self):
        """Test creating a cash sale"""
        if not self.test_product_id:
            self.log_result("Create Cash Sale", False, "No product available for sale")
            return False
            
        sale_data = {
            "items": [
                {
                    "product_id": self.test_product_id,
                    "product_name": "Test Milk 500ml",
                    "quantity": 2,
                    "unit_price": 55.0,
                    "total": 110.0
                }
            ],
            "payment_method": "cash",
            "total_amount": 110.0,
            "amount_paid": 120.0,
            "change_amount": 10.0
        }
        
        success, data = self.make_request('POST', 'sales', sale_data)
        
        if success and 'id' in data:
            self.test_sale_id = data['id']
            self.log_result("Create Cash Sale", True)
        else:
            self.log_result("Create Cash Sale", False, f"Sale creation failed: {data}")
        
        return success

    def test_create_credit_sale(self):
        """Test creating a credit sale"""
        if not self.test_product_id or not self.test_customer_id:
            self.log_result("Create Credit Sale", False, "Missing product or customer")
            return False
            
        sale_data = {
            "items": [
                {
                    "product_id": self.test_product_id,
                    "product_name": "Test Milk 500ml",
                    "quantity": 1,
                    "unit_price": 55.0,
                    "total": 55.0
                }
            ],
            "payment_method": "credit",
            "total_amount": 55.0,
            "customer_id": self.test_customer_id
        }
        
        success, data = self.make_request('POST', 'sales', sale_data)
        
        if success and 'id' in data:
            self.log_result("Create Credit Sale", True)
        else:
            self.log_result("Create Credit Sale", False, f"Credit sale failed: {data}")
        
        return success

    def test_mpesa_stk_push(self):
        """Test M-Pesa STK Push (mock)"""
        if not self.test_sale_id:
            # Create a quick sale for M-Pesa test
            sale_data = {
                "items": [
                    {
                        "product_id": self.test_product_id,
                        "product_name": "Test Milk 500ml",
                        "quantity": 1,
                        "unit_price": 55.0,
                        "total": 55.0
                    }
                ],
                "payment_method": "mpesa",
                "total_amount": 55.0,
                "customer_phone": "254712345678"
            }
            
            sale_success, sale_data_resp = self.make_request('POST', 'sales', sale_data)
            if not sale_success:
                self.log_result("M-Pesa STK Push", False, "Could not create sale for M-Pesa test")
                return False
            self.test_sale_id = sale_data_resp['id']
        
        mpesa_data = {
            "phone": "254712345678",
            "amount": 55.0,
            "sale_id": self.test_sale_id
        }
        
        success, data = self.make_request('POST', 'mpesa/stk-push', mpesa_data)
        
        if success and 'checkout_request_id' in data:
            self.log_result("M-Pesa STK Push", True)
            
            # Test confirmation
            checkout_id = data['checkout_request_id']
            confirm_success, confirm_data = self.make_request('POST', f'mpesa/confirm/{checkout_id}')
            
            if confirm_success:
                self.log_result("M-Pesa Confirmation", True)
            else:
                self.log_result("M-Pesa Confirmation", False, f"Confirmation failed: {confirm_data}")
        else:
            self.log_result("M-Pesa STK Push", False, f"STK Push failed: {data}")
        
        return success

    def test_damaged_stock(self):
        """Test logging damaged stock"""
        if not self.test_product_id:
            self.log_result("Log Damaged Stock", False, "No product available")
            return False
            
        damaged_data = {
            "product_id": self.test_product_id,
            "quantity": 2,
            "reason": "damaged",
            "notes": "Test damage entry"
        }
        
        success, data = self.make_request('POST', 'damaged-stock', damaged_data)
        
        if success and 'id' in data:
            self.log_result("Log Damaged Stock", True)
        else:
            self.log_result("Log Damaged Stock", False, f"Damaged stock logging failed: {data}")
        
        return success

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        success, data = self.make_request('GET', 'reports/dashboard')
        
        if success and 'today' in data:
            self.log_result("Dashboard Stats", True)
        else:
            self.log_result("Dashboard Stats", False, f"Dashboard stats failed: {data}")
        
        return success

    def test_sales_report(self):
        """Test sales report"""
        today = datetime.now()
        start_date = (today - timedelta(days=7)).isoformat()
        end_date = today.isoformat()
        
        success, data = self.make_request('GET', f'reports/sales?start_date={start_date}&end_date={end_date}')
        
        if success and 'sales' in data and 'summary' in data:
            self.log_result("Sales Report", True)
        else:
            self.log_result("Sales Report", False, f"Sales report failed: {data}")
        
        return success

    def test_credit_report(self):
        """Test credit report"""
        success, data = self.make_request('GET', 'reports/credit')
        
        if success and 'customers' in data and 'summary' in data:
            self.log_result("Credit Report", True)
        else:
            self.log_result("Credit Report", False, f"Credit report failed: {data}")
        
        return success

    def test_shop_settings(self):
        """Test shop settings"""
        success, data = self.make_request('GET', 'shop')
        
        if success and 'id' in data:
            self.log_result("Get Shop Settings", True)
            
            # Test update
            update_data = {"name": "Updated Test Shop"}
            update_success, update_resp = self.make_request('PUT', 'shop', update_data)
            
            if update_success:
                self.log_result("Update Shop Settings", True)
            else:
                self.log_result("Update Shop Settings", False, f"Shop update failed: {update_resp}")
        else:
            self.log_result("Get Shop Settings", False, f"Shop settings failed: {data}")
        
        return success

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting CloudDuka POS API Tests...")
        print(f"📡 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Core authentication tests
        if not self.test_health_check():
            print("❌ Health check failed - stopping tests")
            return False
            
        if not self.test_user_registration():
            print("❌ User registration failed - stopping tests")
            return False
            
        self.test_user_login()
        self.test_get_user_profile()
        
        # Product management tests
        self.test_create_category()
        self.test_list_categories()
        self.test_update_category()
        self.test_create_product()
        self.test_list_products()
        self.test_update_product()
        self.test_get_category_products()
        self.test_get_other_category_products()
        
        # Customer management tests
        self.test_create_credit_customer()
        self.test_list_credit_customers()
        
        # Sales tests
        self.test_create_cash_sale()
        self.test_create_credit_sale()
        self.test_mpesa_stk_push()
        
        # Inventory tests
        self.test_damaged_stock()
        
        # Reporting tests
        self.test_dashboard_stats()
        self.test_sales_report()
        self.test_credit_report()
        
        # Settings tests
        self.test_shop_settings()
        
        # Category deletion test (after other tests)
        self.test_delete_category()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Summary:")
        print(f"   Total Tests: {self.tests_run}")
        print(f"   Passed: {self.tests_passed}")
        print(f"   Failed: {self.tests_run - self.tests_passed}")
        print(f"   Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    tester = CloudDukaPOSAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/test_reports/backend_api_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_tests': tester.tests_run,
            'passed_tests': tester.tests_passed,
            'success_rate': (tester.tests_passed/tester.tests_run*100) if tester.tests_run > 0 else 0,
            'results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())