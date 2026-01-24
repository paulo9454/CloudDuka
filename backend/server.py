from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from io import BytesIO
from fpdf import FPDF
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'cloudduka-secret-key-2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Create the main app
app = FastAPI(title="CloudDuka POS API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class UserCreate(BaseModel):
    phone: str
    pin: str
    name: str
    role: str = "shopkeeper"  # owner or shopkeeper
    shop_name: Optional[str] = None

class UserLogin(BaseModel):
    phone: str
    pin: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    phone: str
    name: str
    role: str
    shop_id: str
    trial_ends_at: Optional[str] = None
    subscription_status: str = "trial"
    created_at: str

class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    unit_price: float
    cost_price: Optional[float] = None
    stock_quantity: int = 0
    min_stock_level: int = 5
    unit: str = "piece"
    # Bundle pricing fields
    sell_by: str = "unit"  # "unit" or "bundle"
    bundle_units: Optional[int] = None  # e.g., 3 units per bundle
    bundle_price: Optional[float] = None  # e.g., 10 KES for bundle
    bundle_only: bool = False  # If true, only sell in full bundles

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[float] = None
    cost_price: Optional[float] = None
    stock_quantity: Optional[int] = None
    min_stock_level: Optional[int] = None
    unit: Optional[str] = None
    sell_by: Optional[str] = None
    bundle_units: Optional[int] = None
    bundle_price: Optional[float] = None
    bundle_only: Optional[bool] = None

class ProductResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    unit_price: float
    cost_price: Optional[float] = None
    stock_quantity: int
    min_stock_level: int
    unit: str
    sell_by: str = "unit"
    bundle_units: Optional[int] = None
    bundle_price: Optional[float] = None
    bundle_only: bool = False
    shop_id: str
    created_at: str
    updated_at: str

class SaleItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total: float

class SaleCreate(BaseModel):
    items: List[SaleItem]
    payment_method: str  # cash, mpesa, credit
    total_amount: float
    customer_id: Optional[str] = None  # Required for credit sales
    customer_phone: Optional[str] = None  # For M-Pesa
    amount_paid: Optional[float] = None
    change_amount: Optional[float] = None

class SaleResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    receipt_number: str
    items: List[SaleItem]
    payment_method: str
    total_amount: float
    amount_paid: Optional[float] = None
    change_amount: Optional[float] = None
    customer_id: Optional[str] = None
    mpesa_transaction_id: Optional[str] = None
    status: str
    shop_id: str
    created_by: str
    created_at: str

class CreditCustomerCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    credit_limit: float = 10000.0

class CreditCustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    credit_limit: Optional[float] = None

class CreditCustomerResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    credit_limit: float
    current_balance: float
    shop_id: str
    created_at: str

class CreditPayment(BaseModel):
    customer_id: str
    amount: float
    payment_method: str = "cash"
    notes: Optional[str] = None

class DamagedStockCreate(BaseModel):
    product_id: str
    quantity: int
    reason: str  # damaged, expired, spoiled, other
    notes: Optional[str] = None

class DamagedStockResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    product_id: str
    product_name: str
    quantity: int
    reason: str
    notes: Optional[str] = None
    shop_id: str
    created_by: str
    created_at: str

class MpesaSTKRequest(BaseModel):
    phone: str
    amount: float
    sale_id: str

class MpesaSTKResponse(BaseModel):
    checkout_request_id: str
    merchant_request_id: str
    response_code: str
    response_description: str
    customer_message: str

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

def verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())

def create_token(user_id: str, shop_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "shop_id": shop_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_owner(user: dict = Depends(get_current_user)):
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return user

def generate_receipt_number():
    return f"RCP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

def generate_sku():
    return f"SKU-{str(uuid.uuid4())[:8].upper()}"

# =============================================================================
# AUTH ROUTES
# =============================================================================

@api_router.post("/auth/register", response_model=dict)
async def register(data: UserCreate):
    # Check if phone already exists
    existing = await db.users.find_one({"phone": data.phone})
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    # Create shop for owner
    shop_id = str(uuid.uuid4())
    if data.role == "owner":
        shop = {
            "id": shop_id,
            "name": data.shop_name or f"{data.name}'s Shop",
            "owner_id": "",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.shops.insert_one(shop)
    
    # Create user
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "phone": data.phone,
        "pin_hash": hash_pin(data.pin),
        "name": data.name,
        "role": data.role,
        "shop_id": shop_id,
        "trial_ends_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "subscription_status": "trial",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Update shop owner_id
    if data.role == "owner":
        await db.shops.update_one({"id": shop_id}, {"$set": {"owner_id": user_id}})
    
    await db.users.insert_one(user)
    token = create_token(user_id, shop_id, data.role)
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "phone": data.phone,
            "name": data.name,
            "role": data.role,
            "shop_id": shop_id,
            "trial_ends_at": user["trial_ends_at"],
            "subscription_status": user["subscription_status"],
            "created_at": user["created_at"]
        }
    }

@api_router.post("/auth/login", response_model=dict)
async def login(data: UserLogin):
    user = await db.users.find_one({"phone": data.phone}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid phone or PIN")
    
    if not verify_pin(data.pin, user["pin_hash"]):
        raise HTTPException(status_code=401, detail="Invalid phone or PIN")
    
    token = create_token(user["id"], user["shop_id"], user["role"])
    
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "phone": user["phone"],
            "name": user["name"],
            "role": user["role"],
            "shop_id": user["shop_id"],
            "trial_ends_at": user.get("trial_ends_at"),
            "subscription_status": user.get("subscription_status", "trial"),
            "created_at": user["created_at"]
        }
    }

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        phone=user["phone"],
        name=user["name"],
        role=user["role"],
        shop_id=user["shop_id"],
        trial_ends_at=user.get("trial_ends_at"),
        subscription_status=user.get("subscription_status", "trial"),
        created_at=user["created_at"]
    )

# =============================================================================
# PRODUCT ROUTES
# =============================================================================

@api_router.post("/products", response_model=ProductResponse)
async def create_product(data: ProductCreate, user: dict = Depends(get_current_user)):
    product_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    product = {
        "id": product_id,
        "name": data.name,
        "sku": data.sku or generate_sku(),
        "category": data.category,
        "unit_price": data.unit_price,
        "cost_price": data.cost_price,
        "stock_quantity": data.stock_quantity,
        "min_stock_level": data.min_stock_level,
        "unit": data.unit,
        "shop_id": user["shop_id"],
        "created_at": now,
        "updated_at": now
    }
    
    await db.products.insert_one(product)
    return ProductResponse(**product)

@api_router.get("/products", response_model=List[ProductResponse])
async def list_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    low_stock: Optional[bool] = None,
    user: dict = Depends(get_current_user)
):
    query = {"shop_id": user["shop_id"]}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}}
        ]
    
    if category:
        query["category"] = category
    
    products = await db.products.find(query, {"_id": 0}).to_list(1000)
    
    if low_stock:
        products = [p for p in products if p["stock_quantity"] <= p["min_stock_level"]]
    
    return [ProductResponse(**p) for p in products]

@api_router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, user: dict = Depends(get_current_user)):
    product = await db.products.find_one(
        {"id": product_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(**product)

@api_router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, data: ProductUpdate, user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.products.update_one(
        {"id": product_id, "shop_id": user["shop_id"]},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    return ProductResponse(**product)

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str, user: dict = Depends(require_owner)):
    result = await db.products.delete_one({"id": product_id, "shop_id": user["shop_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted"}

@api_router.get("/products/categories/list")
async def list_categories_simple(user: dict = Depends(get_current_user)):
    """Simple list of category names - just for filtering"""
    categories = await db.products.distinct("category", {"shop_id": user["shop_id"]})
    return [c for c in categories if c]

# =============================================================================
# SALES ROUTES
# =============================================================================

@api_router.post("/sales", response_model=SaleResponse)
async def create_sale(data: SaleCreate, user: dict = Depends(get_current_user)):
    sale_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Validate credit sale has customer
    if data.payment_method == "credit" and not data.customer_id:
        raise HTTPException(status_code=400, detail="Customer required for credit sales")
    
    # Check stock and update quantities
    for item in data.items:
        product = await db.products.find_one(
            {"id": item.product_id, "shop_id": user["shop_id"]}, {"_id": 0}
        )
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product["stock_quantity"] < item.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient stock for {product['name']}. Available: {product['stock_quantity']}"
            )
    
    # Update stock quantities
    for item in data.items:
        await db.products.update_one(
            {"id": item.product_id},
            {"$inc": {"stock_quantity": -item.quantity}}
        )
    
    # Update credit customer balance if credit sale
    if data.payment_method == "credit" and data.customer_id:
        await db.credit_customers.update_one(
            {"id": data.customer_id},
            {"$inc": {"current_balance": data.total_amount}}
        )
    
    sale = {
        "id": sale_id,
        "receipt_number": generate_receipt_number(),
        "items": [item.model_dump() for item in data.items],
        "payment_method": data.payment_method,
        "total_amount": data.total_amount,
        "amount_paid": data.amount_paid,
        "change_amount": data.change_amount,
        "customer_id": data.customer_id,
        "mpesa_transaction_id": None,
        "status": "completed" if data.payment_method != "mpesa" else "pending",
        "shop_id": user["shop_id"],
        "created_by": user["id"],
        "created_at": now
    }
    
    await db.sales.insert_one(sale)
    return SaleResponse(**sale)

@api_router.get("/sales", response_model=List[SaleResponse])
async def list_sales(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    payment_method: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user)
):
    query = {"shop_id": user["shop_id"]}
    
    if start_date:
        query["created_at"] = {"$gte": start_date}
    if end_date:
        if "created_at" in query:
            query["created_at"]["$lte"] = end_date
        else:
            query["created_at"] = {"$lte": end_date}
    if payment_method:
        query["payment_method"] = payment_method
    
    sales = await db.sales.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [SaleResponse(**s) for s in sales]

@api_router.get("/sales/{sale_id}", response_model=SaleResponse)
async def get_sale(sale_id: str, user: dict = Depends(get_current_user)):
    sale = await db.sales.find_one({"id": sale_id, "shop_id": user["shop_id"]}, {"_id": 0})
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return SaleResponse(**sale)

# =============================================================================
# CREDIT CUSTOMER ROUTES
# =============================================================================

@api_router.post("/credit-customers", response_model=CreditCustomerResponse)
async def create_credit_customer(data: CreditCustomerCreate, user: dict = Depends(get_current_user)):
    customer_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    customer = {
        "id": customer_id,
        "name": data.name,
        "phone": data.phone,
        "email": data.email,
        "address": data.address,
        "credit_limit": data.credit_limit,
        "current_balance": 0.0,
        "shop_id": user["shop_id"],
        "created_at": now
    }
    
    await db.credit_customers.insert_one(customer)
    return CreditCustomerResponse(**customer)

@api_router.get("/credit-customers", response_model=List[CreditCustomerResponse])
async def list_credit_customers(
    search: Optional[str] = None,
    has_balance: Optional[bool] = None,
    user: dict = Depends(get_current_user)
):
    query = {"shop_id": user["shop_id"]}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
        ]
    
    customers = await db.credit_customers.find(query, {"_id": 0}).to_list(1000)
    
    if has_balance:
        customers = [c for c in customers if c["current_balance"] > 0]
    
    return [CreditCustomerResponse(**c) for c in customers]

@api_router.get("/credit-customers/{customer_id}", response_model=CreditCustomerResponse)
async def get_credit_customer(customer_id: str, user: dict = Depends(get_current_user)):
    customer = await db.credit_customers.find_one(
        {"id": customer_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CreditCustomerResponse(**customer)

@api_router.put("/credit-customers/{customer_id}", response_model=CreditCustomerResponse)
async def update_credit_customer(
    customer_id: str, 
    data: CreditCustomerUpdate, 
    user: dict = Depends(get_current_user)
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    result = await db.credit_customers.update_one(
        {"id": customer_id, "shop_id": user["shop_id"]},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer = await db.credit_customers.find_one({"id": customer_id}, {"_id": 0})
    return CreditCustomerResponse(**customer)

@api_router.post("/credit-customers/payment")
async def record_credit_payment(data: CreditPayment, user: dict = Depends(get_current_user)):
    customer = await db.credit_customers.find_one(
        {"id": data.customer_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Record payment
    payment = {
        "id": str(uuid.uuid4()),
        "customer_id": data.customer_id,
        "amount": data.amount,
        "payment_method": data.payment_method,
        "notes": data.notes,
        "shop_id": user["shop_id"],
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.credit_payments.insert_one(payment)
    
    # Update customer balance
    new_balance = max(0, customer["current_balance"] - data.amount)
    await db.credit_customers.update_one(
        {"id": data.customer_id},
        {"$set": {"current_balance": new_balance}}
    )
    
    return {"message": "Payment recorded", "new_balance": new_balance}

@api_router.get("/credit-customers/{customer_id}/history")
async def get_credit_history(customer_id: str, user: dict = Depends(get_current_user)):
    # Get credit sales
    sales = await db.sales.find(
        {"customer_id": customer_id, "shop_id": user["shop_id"], "payment_method": "credit"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Get payments
    payments = await db.credit_payments.find(
        {"customer_id": customer_id, "shop_id": user["shop_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return {"sales": sales, "payments": payments}

# =============================================================================
# DAMAGED STOCK ROUTES
# =============================================================================

@api_router.post("/damaged-stock", response_model=DamagedStockResponse)
async def create_damaged_stock(data: DamagedStockCreate, user: dict = Depends(get_current_user)):
    # Get product info
    product = await db.products.find_one(
        {"id": data.product_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if product["stock_quantity"] < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    
    # Reduce stock
    await db.products.update_one(
        {"id": data.product_id},
        {"$inc": {"stock_quantity": -data.quantity}}
    )
    
    # Record damaged stock
    damaged_id = str(uuid.uuid4())
    damaged = {
        "id": damaged_id,
        "product_id": data.product_id,
        "product_name": product["name"],
        "quantity": data.quantity,
        "reason": data.reason,
        "notes": data.notes,
        "shop_id": user["shop_id"],
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.damaged_stock.insert_one(damaged)
    return DamagedStockResponse(**damaged)

@api_router.get("/damaged-stock", response_model=List[DamagedStockResponse])
async def list_damaged_stock(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    reason: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    query = {"shop_id": user["shop_id"]}
    
    if start_date:
        query["created_at"] = {"$gte": start_date}
    if end_date:
        if "created_at" in query:
            query["created_at"]["$lte"] = end_date
        else:
            query["created_at"] = {"$lte": end_date}
    if reason:
        query["reason"] = reason
    
    items = await db.damaged_stock.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [DamagedStockResponse(**i) for i in items]

# =============================================================================
# M-PESA MOCK ROUTES
# =============================================================================

@api_router.post("/mpesa/stk-push", response_model=MpesaSTKResponse)
async def mpesa_stk_push(data: MpesaSTKRequest, user: dict = Depends(get_current_user)):
    """Mock M-Pesa STK Push - simulates sending payment request to customer's phone"""
    checkout_request_id = f"ws_CO_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"
    merchant_request_id = f"MR_{str(uuid.uuid4())[:12]}"
    
    # Store pending transaction
    transaction = {
        "id": str(uuid.uuid4()),
        "checkout_request_id": checkout_request_id,
        "merchant_request_id": merchant_request_id,
        "sale_id": data.sale_id,
        "phone": data.phone,
        "amount": data.amount,
        "status": "pending",
        "shop_id": user["shop_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.mpesa_transactions.insert_one(transaction)
    
    return MpesaSTKResponse(
        checkout_request_id=checkout_request_id,
        merchant_request_id=merchant_request_id,
        response_code="0",
        response_description="Success. Request accepted for processing",
        customer_message="Success. Request accepted for processing"
    )

@api_router.post("/mpesa/confirm/{checkout_request_id}")
async def mpesa_confirm_payment(checkout_request_id: str, user: dict = Depends(get_current_user)):
    """Mock endpoint to simulate M-Pesa payment confirmation"""
    transaction = await db.mpesa_transactions.find_one(
        {"checkout_request_id": checkout_request_id, "shop_id": user["shop_id"]},
        {"_id": 0}
    )
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Update transaction status
    mpesa_receipt = f"SIM{datetime.now().strftime('%Y%m%d%H%M%S')}"
    await db.mpesa_transactions.update_one(
        {"checkout_request_id": checkout_request_id},
        {"$set": {"status": "completed", "mpesa_receipt": mpesa_receipt}}
    )
    
    # Update sale status
    await db.sales.update_one(
        {"id": transaction["sale_id"]},
        {"$set": {"status": "completed", "mpesa_transaction_id": mpesa_receipt}}
    )
    
    return {
        "result_code": "0",
        "result_desc": "The service request is processed successfully.",
        "mpesa_receipt": mpesa_receipt
    }

@api_router.get("/mpesa/status/{checkout_request_id}")
async def mpesa_check_status(checkout_request_id: str, user: dict = Depends(get_current_user)):
    """Check M-Pesa transaction status"""
    transaction = await db.mpesa_transactions.find_one(
        {"checkout_request_id": checkout_request_id, "shop_id": user["shop_id"]},
        {"_id": 0}
    )
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return {
        "status": transaction["status"],
        "mpesa_receipt": transaction.get("mpesa_receipt")
    }

# =============================================================================
# USER MANAGEMENT ROUTES (Owner only)
# =============================================================================

@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, owner: dict = Depends(require_owner)):
    """Create a shopkeeper (owner only)"""
    existing = await db.users.find_one({"phone": data.phone})
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")
    
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "phone": data.phone,
        "pin_hash": hash_pin(data.pin),
        "name": data.name,
        "role": "shopkeeper",  # Always shopkeeper when created by owner
        "shop_id": owner["shop_id"],
        "trial_ends_at": None,
        "subscription_status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user)
    return UserResponse(
        id=user_id,
        phone=data.phone,
        name=data.name,
        role="shopkeeper",
        shop_id=owner["shop_id"],
        subscription_status="active",
        created_at=user["created_at"]
    )

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(owner: dict = Depends(require_owner)):
    """List all users in the shop"""
    users = await db.users.find({"shop_id": owner["shop_id"]}, {"_id": 0, "pin_hash": 0}).to_list(100)
    return [UserResponse(**u) for u in users]

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, owner: dict = Depends(require_owner)):
    """Delete a shopkeeper (owner only)"""
    user = await db.users.find_one({"id": user_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user["role"] == "owner":
        raise HTTPException(status_code=400, detail="Cannot delete owner")
    
    await db.users.delete_one({"id": user_id})
    return {"message": "User deleted"}

# =============================================================================
# REPORTS ROUTES
# =============================================================================

@api_router.get("/reports/dashboard")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    """Get dashboard statistics"""
    shop_id = user["shop_id"]
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Today's sales
    today_sales = await db.sales.find(
        {"shop_id": shop_id, "created_at": {"$gte": today.isoformat()}, "status": "completed"},
        {"_id": 0}
    ).to_list(1000)
    
    today_total = sum(s["total_amount"] for s in today_sales)
    today_count = len(today_sales)
    
    # Sales by payment method today
    cash_sales = sum(s["total_amount"] for s in today_sales if s["payment_method"] == "cash")
    mpesa_sales = sum(s["total_amount"] for s in today_sales if s["payment_method"] == "mpesa")
    credit_sales = sum(s["total_amount"] for s in today_sales if s["payment_method"] == "credit")
    
    # Low stock products
    low_stock = await db.products.find(
        {"shop_id": shop_id, "$expr": {"$lte": ["$stock_quantity", "$min_stock_level"]}},
        {"_id": 0}
    ).to_list(100)
    
    # Total credit outstanding
    credit_customers = await db.credit_customers.find({"shop_id": shop_id}, {"_id": 0}).to_list(1000)
    total_credit = sum(c["current_balance"] for c in credit_customers)
    
    # Recent sales
    recent_sales = await db.sales.find(
        {"shop_id": shop_id, "status": "completed"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(10)
    
    # Weekly sales data for chart
    weekly_data = []
    for i in range(7):
        day = today - timedelta(days=6-i)
        day_end = day + timedelta(days=1)
        day_sales = await db.sales.find(
            {
                "shop_id": shop_id,
                "created_at": {"$gte": day.isoformat(), "$lt": day_end.isoformat()},
                "status": "completed"
            },
            {"_id": 0}
        ).to_list(1000)
        weekly_data.append({
            "date": day.strftime("%a"),
            "sales": sum(s["total_amount"] for s in day_sales)
        })
    
    return {
        "today": {
            "total": today_total,
            "count": today_count,
            "cash": cash_sales,
            "mpesa": mpesa_sales,
            "credit": credit_sales
        },
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock[:5],
        "total_credit_outstanding": total_credit,
        "recent_sales": recent_sales,
        "weekly_sales": weekly_data
    }

@api_router.get("/reports/sales")
async def get_sales_report(
    start_date: str,
    end_date: str,
    user: dict = Depends(get_current_user)
):
    """Get detailed sales report"""
    sales = await db.sales.find(
        {
            "shop_id": user["shop_id"],
            "created_at": {"$gte": start_date, "$lte": end_date},
            "status": "completed"
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(10000)
    
    total = sum(s["total_amount"] for s in sales)
    by_method = {}
    for s in sales:
        method = s["payment_method"]
        by_method[method] = by_method.get(method, 0) + s["total_amount"]
    
    return {
        "sales": sales,
        "summary": {
            "total": total,
            "count": len(sales),
            "by_payment_method": by_method
        }
    }

@api_router.get("/reports/credit")
async def get_credit_report(user: dict = Depends(get_current_user)):
    """Get credit customers report"""
    customers = await db.credit_customers.find(
        {"shop_id": user["shop_id"]},
        {"_id": 0}
    ).to_list(1000)
    
    total_outstanding = sum(c["current_balance"] for c in customers)
    customers_with_balance = [c for c in customers if c["current_balance"] > 0]
    
    return {
        "customers": customers,
        "summary": {
            "total_customers": len(customers),
            "customers_with_balance": len(customers_with_balance),
            "total_outstanding": total_outstanding
        }
    }

@api_router.get("/reports/damaged")
async def get_damaged_report(
    start_date: str,
    end_date: str,
    user: dict = Depends(get_current_user)
):
    """Get damaged stock report"""
    items = await db.damaged_stock.find(
        {
            "shop_id": user["shop_id"],
            "created_at": {"$gte": start_date, "$lte": end_date}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(10000)
    
    by_reason = {}
    for item in items:
        reason = item["reason"]
        by_reason[reason] = by_reason.get(reason, 0) + item["quantity"]
    
    return {
        "items": items,
        "summary": {
            "total_items": len(items),
            "total_quantity": sum(i["quantity"] for i in items),
            "by_reason": by_reason
        }
    }

@api_router.get("/reports/pdf/sales")
async def generate_sales_pdf(
    start_date: str,
    end_date: str,
    user: dict = Depends(get_current_user)
):
    """Generate PDF sales report"""
    sales = await db.sales.find(
        {
            "shop_id": user["shop_id"],
            "created_at": {"$gte": start_date, "$lte": end_date},
            "status": "completed"
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(10000)
    
    # Get shop info
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0})
    shop_name = shop["name"] if shop else "CloudDuka Shop"
    
    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"{shop_name} - Sales Report", 0, 1, "C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, f"Period: {start_date[:10]} to {end_date[:10]}", 0, 1, "C")
    pdf.ln(10)
    
    # Summary
    total = sum(s["total_amount"] for s in sales)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"Total Sales: KES {total:,.2f}", 0, 1)
    pdf.cell(0, 8, f"Number of Transactions: {len(sales)}", 0, 1)
    pdf.ln(5)
    
    # Table header
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 8, "Receipt #", 1)
    pdf.cell(35, 8, "Date", 1)
    pdf.cell(30, 8, "Method", 1)
    pdf.cell(35, 8, "Amount", 1)
    pdf.cell(40, 8, "Status", 1)
    pdf.ln()
    
    # Table data
    pdf.set_font("Arial", "", 9)
    for sale in sales[:100]:  # Limit to 100 rows
        pdf.cell(40, 7, sale["receipt_number"][:15], 1)
        pdf.cell(35, 7, sale["created_at"][:10], 1)
        pdf.cell(30, 7, sale["payment_method"].upper(), 1)
        pdf.cell(35, 7, f"KES {sale['total_amount']:,.2f}", 1)
        pdf.cell(40, 7, sale["status"], 1)
        pdf.ln()
    
    # Output PDF
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    pdf_base64 = base64.b64encode(pdf_bytes).decode()
    
    return {"pdf": pdf_base64, "filename": f"sales_report_{start_date[:10]}_{end_date[:10]}.pdf"}

@api_router.get("/reports/pdf/credit")
async def generate_credit_pdf(user: dict = Depends(get_current_user)):
    """Generate PDF credit report"""
    customers = await db.credit_customers.find(
        {"shop_id": user["shop_id"]},
        {"_id": 0}
    ).to_list(1000)
    
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0})
    shop_name = shop["name"] if shop else "CloudDuka Shop"
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"{shop_name} - Credit Report", 0, 1, "C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1, "C")
    pdf.ln(10)
    
    total_outstanding = sum(c["current_balance"] for c in customers)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"Total Outstanding: KES {total_outstanding:,.2f}", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(50, 8, "Customer", 1)
    pdf.cell(40, 8, "Phone", 1)
    pdf.cell(40, 8, "Balance", 1)
    pdf.cell(40, 8, "Limit", 1)
    pdf.ln()
    
    pdf.set_font("Arial", "", 9)
    for c in customers:
        pdf.cell(50, 7, c["name"][:20], 1)
        pdf.cell(40, 7, c["phone"], 1)
        pdf.cell(40, 7, f"KES {c['current_balance']:,.2f}", 1)
        pdf.cell(40, 7, f"KES {c['credit_limit']:,.2f}", 1)
        pdf.ln()
    
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    pdf_base64 = base64.b64encode(pdf_bytes).decode()
    
    return {"pdf": pdf_base64, "filename": f"credit_report_{datetime.now().strftime('%Y%m%d')}.pdf"}

@api_router.get("/reports/pdf/damaged")
async def generate_damaged_pdf(
    start_date: str,
    end_date: str,
    user: dict = Depends(get_current_user)
):
    """Generate PDF damaged stock report"""
    items = await db.damaged_stock.find(
        {
            "shop_id": user["shop_id"],
            "created_at": {"$gte": start_date, "$lte": end_date}
        },
        {"_id": 0}
    ).to_list(10000)
    
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0})
    shop_name = shop["name"] if shop else "CloudDuka Shop"
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"{shop_name} - Damaged/Spoiled Stock Report", 0, 1, "C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, f"Period: {start_date[:10]} to {end_date[:10]}", 0, 1, "C")
    pdf.ln(10)
    
    total_qty = sum(i["quantity"] for i in items)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"Total Items Affected: {total_qty}", 0, 1)
    pdf.ln(5)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(50, 8, "Product", 1)
    pdf.cell(25, 8, "Qty", 1)
    pdf.cell(35, 8, "Reason", 1)
    pdf.cell(35, 8, "Date", 1)
    pdf.cell(45, 8, "Notes", 1)
    pdf.ln()
    
    pdf.set_font("Arial", "", 9)
    for item in items:
        pdf.cell(50, 7, item["product_name"][:20], 1)
        pdf.cell(25, 7, str(item["quantity"]), 1)
        pdf.cell(35, 7, item["reason"], 1)
        pdf.cell(35, 7, item["created_at"][:10], 1)
        pdf.cell(45, 7, (item.get("notes") or "")[:20], 1)
        pdf.ln()
    
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    pdf_base64 = base64.b64encode(pdf_bytes).decode()
    
    return {"pdf": pdf_base64, "filename": f"damaged_report_{start_date[:10]}_{end_date[:10]}.pdf"}

# =============================================================================
# SHOP SETTINGS
# =============================================================================

@api_router.get("/shop")
async def get_shop(user: dict = Depends(get_current_user)):
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop

@api_router.put("/shop")
async def update_shop(data: dict, owner: dict = Depends(require_owner)):
    allowed_fields = ["name", "address", "phone", "email"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    await db.shops.update_one({"id": owner["shop_id"]}, {"$set": update_data})
    shop = await db.shops.find_one({"id": owner["shop_id"]}, {"_id": 0})
    return shop

# =============================================================================
# HEALTH CHECK
# =============================================================================

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
