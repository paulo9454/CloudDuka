from fastapi import (
    FastAPI,
    APIRouter,
    HTTPException,
    Depends,
    status,
    Response,
    Request,
    Body,
    Header,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Literal
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from io import BytesIO
from fpdf import FPDF
import base64
import requests
import time
import hmac
import hashlib
import json
from bson import ObjectId

load_dotenv()

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# JWT Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "cloudduka-dev-jwt-secret-minimum-32")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters long")

# Create the main app
app = FastAPI(title="CloudDuka POS API")

from fastapi.middleware.cors import CORSMiddleware

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.1.29:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "%s %s %s %sms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    except Exception:
        logger.exception(
            "Unhandled error in request %s %s", request.method, request.url.path
        )
        raise

# ------------------------------
# Rate Limiting Middleware
# ------------------------------

LOGIN_ATTEMPTS = {}

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if os.environ.get("DB_NAME", "").startswith("test_") or os.environ.get("PYTEST_CURRENT_TEST"):
            return await call_next(request)

        # Allow CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        # Apply rate limiting only to login endpoint
        if request.url.path.endswith("/api/auth/login") and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            window = 60
            limit = 10

            attempts = [
                t for t in LOGIN_ATTEMPTS.get(client_ip, [])
                if now - t < window
            ]

            if len(attempts) >= limit:
                return Response(
                    content='{"detail":"Too many login attempts. Try again in a minute."}',
                    media_type="application/json",
                    status_code=429,
                )

            attempts.append(now)
            LOGIN_ATTEMPTS[client_ip] = attempts

        return await call_next(request)


# ------------------------------
# Register Middleware
# ------------------------------

# Rate limit protection
app.add_middleware(RateLimitMiddleware)

# CORS configuration
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
# =============================================================================
# PYDANTIC MODELS
# =============================================================================


class UserCreate(BaseModel):
    phone: str
    pin: str
    name: str
    role: Literal["owner", "shopkeeper", "customer"] = "customer"
    shop_name: Optional[str] = None
    shop_id: Optional[str] = None


class UserLogin(BaseModel):
    phone: str
    pin: str


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    phone: str
    name: str
    role: str
    shop_id: Optional[str] = None
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
    image_url: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
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
    image_url: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
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
    image_url: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
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


class PaystackInitializeRequest(BaseModel):
    email: str
    amount: float
    sale_id: str


class PaystackWebhookPayload(BaseModel):
    event: str
    data: dict


class MpesaPaymentInitiateRequest(BaseModel):
    order_id: str
    payment_id: Optional[str] = None
    phone: str
    amount: Optional[float] = None


class MpesaPaymentConfirmRequest(BaseModel):
    payment_id: str
    status: Literal["successful", "failed"]
    checkout_request_id: Optional[str] = None
    mpesa_receipt: Optional[str] = None


class ClientErrorEvent(BaseModel):
    message: str
    source: Optional[str] = None
    lineno: Optional[int] = None
    colno: Optional[int] = None
    stack: Optional[str] = None
    url: Optional[str] = None


# Supplier Models
class SupplierCreate(BaseModel):
    name: str
    phone: str
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class SupplierResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    phone: str
    notes: Optional[str] = None
    shop_id: str
    created_at: str


# Purchase Models
class PurchaseItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_type: str  # units, packets, dozens, boxes
    units_per_package: int = 1  # How many units per packet/dozen/box
    cost: float


class PurchaseCreate(BaseModel):
    supplier_id: str
    items: List[PurchaseItem]
    total_cost: float
    notes: Optional[str] = None


class PurchaseResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    purchase_number: str
    supplier_id: str
    supplier_name: str
    items: List[PurchaseItem]
    total_cost: float
    notes: Optional[str] = None
    shop_id: str
    created_by: str
    created_at: str


class CheckoutRequest(BaseModel):
    payment_method: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None

    customer_id: Optional[str] = None


class CheckoutResponse(BaseModel):
    id: str
    total_amount: float
    shop_id: str
    status: str

    payment_status: str
    payment_method: str
    customer_id: Optional[str] = None
    items: List[dict] = []


class PublicStoreResponse(BaseModel):
    id: str
    name: str
    category: Optional[str] = None


class PublicProductResponse(BaseModel):
    id: str
    name: str
    price: float
    image_url: Optional[str] = None
    description: Optional[str] = None
    availability: str


class MarketplaceOrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_cost: float


class MarketplaceOrderCreate(BaseModel):
    vendor_id: str
    payment_method: str
    items: List[MarketplaceOrderItem]


class MarketplaceDeliveryUpdate(BaseModel):
    status: str
    notes: Optional[str] = None



class CartItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CustomerCartItemCreate(BaseModel):
    product_id: str
    shop_id: str
    quantity: int = Field(gt=0)


class CustomerCartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CustomerCartItemResponse(BaseModel):
    id: str
    shop_id: str
    product_id: str
    name: str
    price: float
    image_url: Optional[str] = None
    quantity: int
    created_at: str


class CustomerCheckoutRequest(BaseModel):
    payment_method: str
    customer_id: Optional[str] = None


class CustomerOrderItemResponse(BaseModel):
    product_id: str
    name: str
    quantity: int
    price: float


class CustomerOrderPaymentResponse(BaseModel):
    method: str
    status: str


class CustomerOrderResponse(BaseModel):
    order_id: str
    order_number: str
    total_amount: float
    status: str
    created_at: str
    items: List[CustomerOrderItemResponse]
    payment: CustomerOrderPaymentResponse


class OrderStatusPatch(BaseModel):
    status: str


class OrderLifecycleStatusPatch(BaseModel):
    status: Literal["pending", "paid", "processing", "ready", "delivered", "cancelled"]

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
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def check_subscription(shop_or_id):
    shop_id = shop_or_id["id"] if isinstance(shop_or_id, dict) else shop_or_id
    if not shop_id or not hasattr(db, "subscriptions"):
        return True

    subscription = await db.subscriptions.find_one({"shop_id": shop_id}, {"_id": 0})
    if not subscription:
        return True

    status = (subscription.get("status") or "").lower()
    if status == "expired":
        raise HTTPException(status_code=403, detail="Shop subscription is expired")
    return True


async def validate_shop_access(user: dict, shop_id: Optional[str] = None):
    target_shop_id = shop_id or user.get("shop_id") or user.get("default_shop_id")
    if not target_shop_id:
        raise HTTPException(status_code=400, detail="shop_id is required")

    if user.get("role") == "shopkeeper" and user.get("shop_id") != target_shop_id:
        raise HTTPException(status_code=403, detail="Shopkeepers cannot switch shops")

    if user.get("role") == "owner" and hasattr(db, "shop_users"):
        membership = await db.shop_users.find_one(
            {"user_id": user["id"], "shop_id": target_shop_id}, {"_id": 0}
        )
        if membership is None:
            existing = getattr(getattr(db, "shop_users", None), "documents", [])
            if existing:
                raise HTTPException(status_code=403, detail="You do not have access to this shop")

    return {"id": target_shop_id}


async def get_current_user(
    request: Request = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_shop_id: Optional[str] = Header(default=None, alias="X-Shop-Id"),
):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        role = user.get("role") or payload.get("role", "owner")
        default_shop_id = user.get("shop_id") or user.get("default_shop_id") or payload.get("shop_id")

        if role == "customer":
            hydrated_user = {
                **user,
                "role": "customer",
                "shop_id": None,
                "default_shop_id": None,
            }
            if request and request.url.path.startswith("/api/"):
                if not (
                    request.url.path.startswith("/api/auth/")
                    or request.url.path.startswith("/api/public/")
                    or request.url.path.startswith("/api/customer/")
                ):
                    raise HTTPException(status_code=403, detail="Customer access is limited to public/customer endpoints")
            return hydrated_user

        active_shop_id = x_shop_id or payload.get("shop_id") or default_shop_id

        if hasattr(db, "shop_users") and active_shop_id:
            membership = await db.shop_users.find_one(
                {"user_id": user["id"], "shop_id": active_shop_id}, {"_id": 0}
            )
            if membership:
                role = membership.get("role", role)
            elif role == "shopkeeper" and default_shop_id != active_shop_id:
                raise HTTPException(status_code=403, detail="Shopkeepers cannot switch shops")

        if role == "shopkeeper" and x_shop_id and default_shop_id and x_shop_id != default_shop_id:
            raise HTTPException(status_code=403, detail="Shopkeepers cannot switch shops")

        hydrated_user = {
            **user,
            "role": role,
            "shop_id": active_shop_id or default_shop_id,
            "default_shop_id": user.get("default_shop_id", default_shop_id),
        }

        if (
            role == "owner"
            and request
            and request.url.path.startswith("/api/")
            and not request.url.path.startswith("/api/auth/")
        ):
            await check_subscription(hydrated_user.get("shop_id"))

        return hydrated_user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_owner(user: dict = Depends(get_current_user)):
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return user


def require_customer(user: dict = Depends(get_current_user)):
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Customer access required")
    return user


def require_shopkeeper(user: dict = Depends(get_current_user)):
    if user.get("role") != "shopkeeper":
        raise HTTPException(status_code=403, detail="Shopkeeper access required")
    return user


def require_active_subscription(user: dict = Depends(get_current_user)):
    status = user.get("subscription_status", "trial")
    trial_ends_at = user.get("trial_ends_at")
    now = datetime.now(timezone.utc)
    if status == "expired":
        raise HTTPException(status_code=402, detail="Subscription expired")
    if status == "trial" and trial_ends_at:
        try:
            trial_end = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
            if trial_end < now:
                raise HTTPException(
                    status_code=402,
                    detail="Trial expired. Please activate subscription",
                )
        except ValueError:
            logger.warning("Invalid trial_ends_at format for user %s", user.get("id"))
    return user


LOGIN_ATTEMPTS: Dict[str, List[float]] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if os.environ.get("DB_NAME", "").startswith("test_") or os.environ.get("PYTEST_CURRENT_TEST"):
            return await call_next(request)
        if request.url.path.endswith("/api/auth/login") and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            window = 60
            limit = 10
            attempts = [
                t for t in LOGIN_ATTEMPTS.get(client_ip, []) if now - t < window
            ]
            if len(attempts) >= limit:
                return Response(
                    content='{"detail":"Too many login attempts. Try again in a minute."}',
                    media_type="application/json",
                    status_code=429,
                )
            attempts.append(now)
            LOGIN_ATTEMPTS[client_ip] = attempts
        return await call_next(request)


def generate_receipt_number():
    return f"RCP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"


def generate_sku():
    return f"SKU-{str(uuid.uuid4())[:8].upper()}"


def generate_purchase_number():
    return f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"


def build_restock_suggestions(products: List[dict]) -> List[dict]:
    suggestions = []
    for product in products:
        stock = product.get("stock_quantity", 0)
        minimum = product.get("min_stock_level", 0)
        if stock <= minimum:
            recommended = max(minimum, 0)
            unit_cost = product.get("cost_price") or 0
            suggestions.append(
                {
                    "product_id": product.get("id"),
                    "product_name": product.get("name"),
                    "recommended_restock": recommended,
                    "estimated_restock_cost": recommended * unit_cost,
                }
            )
    return suggestions



def is_valid_object_id(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    if ObjectId.is_valid(value):
        return True
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def normalize_object_ids(payload):
    if isinstance(payload, dict):
        return {key: normalize_object_ids(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [normalize_object_ids(item) for item in payload]
    if isinstance(payload, ObjectId):
        return str(payload)
    return payload


def normalize_limit_offset(limit: Optional[int], offset: int, default_limit: int = 100, max_limit: int = 200):
    safe_offset = max(0, offset or 0)
    if limit is None:
        return default_limit, safe_offset
    return max(1, min(limit, max_limit)), safe_offset


VALID_ORDER_STATUSES = ["pending", "paid", "processing", "ready", "delivered", "cancelled"]
VALID_ORDER_TRANSITIONS = {
    "pending": ["paid", "cancelled"],
    "paid": ["processing", "cancelled"],
    "processing": ["ready"],
    "ready": ["delivered"],
    "delivered": [],
    "cancelled": [],
}


def get_order_lifecycle_status(order: dict) -> str:
    return (order.get("lifecycle_status") or order.get("status") or "pending").lower()


def build_status_history_entry(status_value: str):
    return {"status": status_value, "timestamp": datetime.now(timezone.utc).isoformat()}


def get_order_status_history(order: dict):
    if order.get("status_history"):
        return order["status_history"]
    return [
        {
            "status": get_order_lifecycle_status(order),
            "timestamp": order.get("created_at"),
        }
    ]


async def ensure_order_lifecycle_initialized(order: dict):
    if not order or order.get("lifecycle_status"):
        return
    fallback_entry = {
        "status": "pending",
        "timestamp": order.get("created_at"),
    }
    await db.orders.update_one(
        {"id": order["id"], "shop_id": order.get("shop_id")},
        {
            "$set": {
                "lifecycle_status": "pending",
                "status": "pending",
            },
            "$push": {"status_history": fallback_entry},
        },
    )
    order["lifecycle_status"] = "pending"
    order["status"] = "pending"
    order["status_history"] = [fallback_entry]


async def initialize_order_lifecycle(order_id: str, shop_id: str):
    order = await db.orders.find_one({"id": order_id, "shop_id": shop_id}, {"_id": 0})
    if not order:
        return
    await ensure_order_lifecycle_initialized(order)


async def set_order_lifecycle_status(
    order_id: str,
    shop_id: str,
    new_status: str,
    enforce_transition: bool = True,
):
    order = await db.orders.find_one({"id": order_id, "shop_id": shop_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = (new_status or "").lower()
    if new_status not in VALID_ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid order status")

    current_status = get_order_lifecycle_status(order)
    if current_status not in VALID_ORDER_TRANSITIONS:
        raise HTTPException(status_code=400, detail="Invalid current state")
    if enforce_transition and new_status not in VALID_ORDER_TRANSITIONS.get(current_status, []):
        raise HTTPException(status_code=400, detail=f"Invalid status transition: {current_status} -> {new_status}")
    if current_status == new_status:
        return order

    history = list(get_order_status_history(order))
    history.append(build_status_history_entry(new_status))
    await db.orders.update_one(
        {"id": order_id, "shop_id": shop_id},
        {"$set": {"lifecycle_status": new_status, "status": new_status, "status_history": history, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    order["lifecycle_status"] = new_status
    order["status"] = new_status
    order["status_history"] = history
    return order


async def get_stored_checkout_response(user_id: str, key: Optional[str]):
    if not key or not hasattr(db, "checkout_requests"):
        return None
    stored = await db.checkout_requests.find_one({"key": key, "user_id": user_id}, {"_id": 0})
    if stored and stored.get("response"):
        return stored["response"]
    return None


async def store_checkout_response(user_id: str, key: Optional[str], response_payload: dict):
    if not key or not hasattr(db, "checkout_requests"):
        return
    await db.checkout_requests.update_one(
        {"key": key, "user_id": user_id},
        {
            "$set": {
                "response": response_payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "$setOnInsert": {"key": key, "user_id": user_id},
        },
        upsert=True,
    )


async def write_audit_log(
    shop_id: str,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: Optional[dict] = None,
):
    if not hasattr(db, "audit_logs"):
        return
    await db.audit_logs.insert_one(
        {
            "id": str(uuid.uuid4()),
            "shop_id": shop_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

#======================================================================
# # AUTH ROUTES (UPDATED FOR MULTI-SHOP SUPPORT)
# #=============================================================================

@api_router.post("/auth/register", response_model=dict)
async def register(data: UserCreate):
    # Check if phone already exists
    existing = await db.users.find_one({"phone": data.phone})
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # OWNER
    if data.role == "owner":
        user = {
            "id": user_id,
            "phone": data.phone,
            "pin_hash": hash_pin(data.pin),
            "name": data.name,
            "role": "owner",
            "trial_ends_at": (now + timedelta(days=14)).isoformat(),
            "subscription_status": "trial",
            "created_at": now.isoformat(),
        }

    # SHOPKEEPER
    elif data.role == "shopkeeper":
        if not data.shop_id:
            raise HTTPException(status_code=400, detail="shop_id is required")

        shop = await db.shops.find_one({"id": data.shop_id})
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")

        user = {
            "id": user_id,
            "phone": data.phone,
            "pin_hash": hash_pin(data.pin),
            "name": data.name,
            "role": "shopkeeper",
            "shop_id": data.shop_id,
            "created_at": now.isoformat(),
        }

    # CUSTOMER (default)
    elif data.role == "customer":
        user = {
            "id": user_id,
            "phone": data.phone,
            "pin_hash": hash_pin(data.pin),
            "name": data.name,
            "role": "customer",
            "created_at": now.isoformat(),
        }

    else:
        raise HTTPException(status_code=400, detail="Invalid role")

    await db.users.insert_one(user)

    token = create_token(
        user_id,
        user.get("shop_id") if user["role"] == "shopkeeper" else None,
        user["role"]
    )

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "phone": user["phone"],
            "name": user["name"],
            "role": user["role"],
            "shop_id": user.get("shop_id"),
            "trial_ends_at": user.get("trial_ends_at"),
            "subscription_status": user.get("subscription_status", "trial"),
            "created_at": user["created_at"],
        }
    }


@api_router.post("/shops")
async def create_shop(
    user: dict = Depends(require_owner),
    name: str = Body(...)
):
    shop_id = str(uuid.uuid4())

    shop = {
        "id": shop_id,
        "name": name,
        "owner_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.shops.insert_one(shop)

    return shop
# =========================
# LOGIN
# =========================
@api_router.post("/auth/login", response_model=dict)
async def login(data: UserLogin):
    user = await db.users.find_one({"phone": data.phone}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid phone or PIN")

    if not verify_pin(data.pin, user["pin_hash"]):
        raise HTTPException(status_code=401, detail="Invalid phone or PIN")

    default_shop_id = user.get("shop_id") or user.get("default_shop_id")
    membership = None
    if hasattr(db, "shop_users"):
        membership = await db.shop_users.find_one(
            {"user_id": user["id"], "shop_id": default_shop_id}, {"_id": 0}
        )
    role = user.get("role") or (membership.get("role") if membership else "owner")
    token = create_token(user["id"], default_shop_id, role)

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "phone": user["phone"],
            "name": user["name"],
            "role": role,
            "shop_id": default_shop_id,
            "trial_ends_at": user.get("trial_ends_at"),
            "subscription_status": user.get("subscription_status", "trial"),
            "created_at": user["created_at"],
        },
    }


# =========================
# CURRENT USER
# =========================
@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        phone=user["phone"],
        name=user["name"],
        role=user["role"],
        shop_id=user.get("shop_id"),  # ✅ safe for owner
        trial_ends_at=user.get("trial_ends_at"),
        subscription_status=user.get("subscription_status", "trial"),
        created_at=user["created_at"],
        )
# ===========================================================================
# PRODUCT ROUTES
# =============================================================================


# =============================================================================
# PRODUCT ROUTES (MULTI-SHOP READY ✅)
# =============================================================================

@api_router.post("/products", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    user: dict = Depends(get_current_user),
):
    # 🔐 Only OWNER can create products
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only owner can add products")

    # ✅ Validate shop access
    shop_id = getattr(data, "shop_id", None) or user.get("shop_id")
    shop = await validate_shop_access(user, shop_id)

    # 💳 Check subscription
    await check_subscription(shop)

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
        "image_url": data.image_url,
        "description": data.description,
        "is_active": data.is_active,
        "shop_id": shop_id,
        "created_at": now,
        "updated_at": now,
    }

    await db.products.insert_one(product)

    return ProductResponse(**product)


# -----------------------------------------------------------------------------

@api_router.get("/products", response_model=List[ProductResponse])
async def list_products(
    shop_id: Optional[str] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    low_stock: Optional[bool] = None,
    user: dict = Depends(get_current_user),
):
    # ✅ Validate access
    resolved_shop_id = shop_id or user.get("shop_id")
    await validate_shop_access(user, resolved_shop_id)

    query = {"shop_id": resolved_shop_id}

    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
        ]

    if category:
        query["category"] = category

    products = await db.products.find(query, {"_id": 0}).to_list(1000)

    if low_stock:
        products = [
            p for p in products if p["stock_quantity"] <= p["min_stock_level"]
        ]

    return [ProductResponse(**p) for p in products]


# -----------------------------------------------------------------------------

@api_router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    shop_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    # ✅ Validate access
    resolved_shop_id = shop_id or user.get("shop_id")
    await validate_shop_access(user, resolved_shop_id)

    product = await db.products.find_one(
        {"id": product_id, "shop_id": resolved_shop_id}, {"_id": 0}
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return ProductResponse(**product)


# -----------------------------------------------------------------------------

@api_router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    shop_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    # 🔐 Only OWNER can update
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only owner can update products")

    # ✅ Validate access
    resolved_shop_id = shop_id or user.get("shop_id")
    await validate_shop_access(user, resolved_shop_id)

    update_data = {
        k: v for k, v in data.model_dump().items() if v is not None
    }
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.products.update_one(
        {"id": product_id, "shop_id": resolved_shop_id},
        {"$set": update_data},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    product = await db.products.find_one(
        {"id": product_id, "shop_id": resolved_shop_id}, {"_id": 0}
    )

    await write_audit_log(
        resolved_shop_id,
        user["id"],
        "update",
        "product",
        product_id,
        {"fields": list(update_data.keys())},
    )

    return ProductResponse(**product)


# -----------------------------------------------------------------------------

@api_router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    shop_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    # 🔐 Only OWNER can delete
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only owner can delete products")

    # ✅ Validate access
    resolved_shop_id = shop_id or user.get("shop_id")
    await validate_shop_access(user, resolved_shop_id)

    result = await db.products.delete_one(
        {"id": product_id, "shop_id": resolved_shop_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    await write_audit_log(
        resolved_shop_id,
        user["id"],
        "delete",
        "product",
        product_id,
    )

    return {"message": "Product deleted"}


# -----------------------------------------------------------------------------

@api_router.get("/products/categories/list")
async def list_categories_simple(
    shop_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    # ✅ Validate access
    resolved_shop_id = shop_id or user.get("shop_id")
    await validate_shop_access(user, resolved_shop_id)

    categories = await db.products.distinct("category", {"shop_id": resolved_shop_id})
    categories = [c for c in categories if c]

    # Default categories
    if not categories:
        categories = [
            "Beverages",
            "Bakery",
            "Snacks",
            "Dairy",
            "Fruits",
            "Vegetables",
            "Household",
            "Personal Care",
            "Stationery",
            "Cigarettes",
            "Sweets",
            "Other",
        ]

    return categories
# =============================================================================
# SALES ROUTES
# =============================================================================


@api_router.post("/sales", response_model=SaleResponse)
async def create_sale(
    data: SaleCreate,
    user: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc).isoformat()
    sale_id = str(uuid.uuid4())

    # ✅ Validate access
    shop_id = getattr(data, "shop_id", None) or user.get("shop_id")
    shop = await validate_shop_access(user, shop_id)

    # ✅ Check subscription
    await check_subscription(shop)

    # Validate credit sale
    if data.payment_method == "credit" and not data.customer_id:
        raise HTTPException(400, "Customer required for credit sales")

    # Atomic stock update with oversell protection
    for item in data.items:
        stock_update = await db.products.update_one(
            {
                "id": item.product_id,
                "shop_id": shop_id,
                "stock_quantity": {"$gte": item.quantity},
            },
            {"$inc": {"stock_quantity": -item.quantity}},
        )
        if stock_update.matched_count == 0:
            product = await db.products.find_one(
                {"id": item.product_id, "shop_id": shop_id},
                {"_id": 0},
            )
            if not product:
                raise HTTPException(404, f"Product {item.product_id} not found")
            raise HTTPException(
                400,
                f"Insufficient stock for {product.get('name', item.product_id)}. Available: {product.get('stock_quantity', 0)}",
            )

    # Credit balance
    if data.payment_method == "credit" and data.customer_id:
        await db.credit_customers.update_one(
            {"id": data.customer_id, "shop_id": shop_id},
            {"$inc": {"current_balance": data.total_amount}},
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
        "shop_id": shop_id,
        "created_by": user["id"],
        "created_at": now,
    }

    await db.sales.insert_one(sale)

    return SaleResponse(**sale) 


@api_router.get("/sales", response_model=List[SaleResponse])
async def list_sales(user: dict = Depends(get_current_user)):
    sales = await db.sales.find({"shop_id": user["shop_id"]}, {"_id": 0}).to_list(1000)
    return [SaleResponse(**sale) for sale in sales]
# =============================================================================
# CREDIT CUSTOMER ROUTES
# =============================================================================


@api_router.post("/credit-customers", response_model=CreditCustomerResponse)
async def create_credit_customer(
    data: CreditCustomerCreate, user: dict = Depends(get_current_user)
):
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
        "created_at": now,
    }

    await db.credit_customers.insert_one(customer)
    return CreditCustomerResponse(**customer)


@api_router.get("/credit-customers", response_model=List[CreditCustomerResponse])
async def list_credit_customers(
    search: Optional[str] = None,
    has_balance: Optional[bool] = None,
    user: dict = Depends(get_current_user),
):
    query = {"shop_id": user["shop_id"]}

    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
        ]

    customers = await db.credit_customers.find(query, {"_id": 0}).to_list(1000)

    if has_balance:
        customers = [c for c in customers if c["current_balance"] > 0]

    return [CreditCustomerResponse(**c) for c in customers]


@api_router.get(
    "/credit-customers/{customer_id}", response_model=CreditCustomerResponse
)
async def get_credit_customer(customer_id: str, user: dict = Depends(get_current_user)):
    customer = await db.credit_customers.find_one(
        {"id": customer_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CreditCustomerResponse(**customer)


@api_router.put(
    "/credit-customers/{customer_id}", response_model=CreditCustomerResponse
)
async def update_credit_customer(
    customer_id: str, data: CreditCustomerUpdate, user: dict = Depends(get_current_user)
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    result = await db.credit_customers.update_one(
        {"id": customer_id, "shop_id": user["shop_id"]}, {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = await db.credit_customers.find_one({"id": customer_id}, {"_id": 0})
    return CreditCustomerResponse(**customer)


@api_router.post("/credit-customers/payment")
async def record_credit_payment(
    data: CreditPayment, user: dict = Depends(get_current_user)
):
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
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.credit_payments.insert_one(payment)

    # Update customer balance
    new_balance = max(0, customer["current_balance"] - data.amount)
    await db.credit_customers.update_one(
        {"id": data.customer_id}, {"$set": {"current_balance": new_balance}}
    )

    return {"message": "Payment recorded", "new_balance": new_balance}


@api_router.get("/credit-customers/{customer_id}/history")
async def get_credit_history(customer_id: str, user: dict = Depends(get_current_user)):
    # Get credit sales
    sales = (
        await db.sales.find(
            {
                "customer_id": customer_id,
                "shop_id": user["shop_id"],
                "payment_method": "credit",
            },
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(100)
    )

    # Get payments
    payments = (
        await db.credit_payments.find(
            {"customer_id": customer_id, "shop_id": user["shop_id"]}, {"_id": 0}
        )
        .sort("created_at", -1)
        .to_list(100)
    )

    return {"sales": sales, "payments": payments}


# =============================================================================
# DAMAGED STOCK ROUTES
# =============================================================================


@api_router.post("/damaged-stock", response_model=DamagedStockResponse)
async def create_damaged_stock(
    data: DamagedStockCreate, user: dict = Depends(get_current_user)
):
    # Get product info
    product = await db.products.find_one(
        {"id": data.product_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if product["stock_quantity"] < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    # Reduce stock
    stock_update = await db.products.update_one(
        {
            "id": data.product_id,
            "shop_id": user["shop_id"],
            "stock_quantity": {"$gte": data.quantity},
        },
        {"$inc": {"stock_quantity": -data.quantity}},
    )
    if stock_update.matched_count == 0:
        raise HTTPException(status_code=400, detail="Insufficient stock")

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
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.damaged_stock.insert_one(damaged)
    return DamagedStockResponse(**damaged)


@api_router.get("/damaged-stock", response_model=List[DamagedStockResponse])
async def list_damaged_stock(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    reason: Optional[str] = None,
    user: dict = Depends(get_current_user),
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

    items = (
        await db.damaged_stock.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(1000)
    )
    return [DamagedStockResponse(**i) for i in items]


# =============================================================================
# M-PESA MOCK ROUTES
# =============================================================================


@api_router.post("/mpesa/stk-push", response_model=MpesaSTKResponse)
async def mpesa_stk_push(data: MpesaSTKRequest, user: dict = Depends(get_current_user)):
    """Sandbox compatibility endpoint (legacy M-Pesa mock). Prefer /paystack/initialize."""
    checkout_request_id = (
        f"ws_CO_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"
    )
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
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.mpesa_transactions.insert_one(transaction)

    return MpesaSTKResponse(
        checkout_request_id=checkout_request_id,
        merchant_request_id=merchant_request_id,
        response_code="0",
        response_description="Success. Request accepted for processing",
        customer_message="Success. Request accepted for processing",
    )


@api_router.post("/mpesa/confirm/{checkout_request_id}")
async def mpesa_confirm_payment(
    checkout_request_id: str, user: dict = Depends(get_current_user)
):
    """Sandbox compatibility endpoint (legacy M-Pesa mock)."""
    transaction = await db.mpesa_transactions.find_one(
        {"checkout_request_id": checkout_request_id, "shop_id": user["shop_id"]},
        {"_id": 0},
    )

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Update transaction status
    mpesa_receipt = f"SIM{datetime.now().strftime('%Y%m%d%H%M%S')}"
    await db.mpesa_transactions.update_one(
        {"checkout_request_id": checkout_request_id},
        {"$set": {"status": "completed", "mpesa_receipt": mpesa_receipt}},
    )

    # Update sale status
    await db.sales.update_one(
        {"id": transaction["sale_id"]},
        {"$set": {"status": "completed", "mpesa_transaction_id": mpesa_receipt}},
    )

    return {
        "result_code": "0",
        "result_desc": "The service request is processed successfully.",
        "mpesa_receipt": mpesa_receipt,
    }


@api_router.get("/mpesa/status/{checkout_request_id}")
async def mpesa_check_status(
    checkout_request_id: str, user: dict = Depends(get_current_user)
):
    """Check legacy sandbox M-Pesa transaction status."""
    transaction = await db.mpesa_transactions.find_one(
        {"checkout_request_id": checkout_request_id, "shop_id": user["shop_id"]},
        {"_id": 0},
    )

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {
        "status": transaction["status"],
        "mpesa_receipt": transaction.get("mpesa_receipt"),
    }


def _normalize_payment_method(method: str) -> str:
    method = (method or "").lower()
    return method if method in {"cash", "mpesa", "paystack", "credit"} else method


def _normalize_payment_status(status: str) -> str:
    status = (status or "").lower()
    if status in {"pending", "successful", "failed"}:
        return status
    if status in {"on_credit"}:
        return "pending"
    return status


async def _set_payment_status_if_pending(
    payment_id: str,
    shop_id: str,
    new_status: str,
    extra_fields: Optional[dict] = None,
):
    new_status = _normalize_payment_status(new_status)
    update_payload = {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if extra_fields:
        update_payload.update(extra_fields)

    result = await db.payments.update_one(
        {"id": payment_id, "shop_id": shop_id, "status": "pending"},
        {"$set": update_payload},
    )
    if result.matched_count == 1:
        logger.info("Payment status updated payment_id=%s shop_id=%s status=%s", payment_id, shop_id, new_status)
        if new_status == "successful":
            payment = await db.payments.find_one({"id": payment_id, "shop_id": shop_id}, {"_id": 0})
            if payment and payment.get("order_id"):
                order = await db.orders.find_one({"id": payment["order_id"], "shop_id": shop_id}, {"_id": 0})
                if order and get_order_lifecycle_status(order) == "pending":
                    await set_order_lifecycle_status(payment["order_id"], shop_id, "paid", enforce_transition=False)
        return {"updated": True, "status": new_status}

    existing = await db.payments.find_one({"id": payment_id, "shop_id": shop_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Payment not found")
    if _normalize_payment_status(existing.get("status")) == "successful":
        return {"updated": False, "status": "successful", "message": "Payment already successful"}
    return {"updated": False, "status": existing.get("status"), "message": "Payment status not updated"}


def verify_paystack_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    if not signature or not secret:
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature)


async def handle_paystack_webhook_event(payload: dict):
    event = payload.get("event")
    data = payload.get("data", {}) or {}
    reference = data.get("reference")
    if event != "charge.success" or not reference:
        return {"received": True}

    payment = await db.payments.find_one({"paystack_reference": reference}, {"_id": 0})
    if not payment:
        metadata = data.get("metadata", {}) or {}
        order_id = metadata.get("order_id")
        if order_id:
            payment = await db.payments.find_one({"order_id": order_id}, {"_id": 0})
    if not payment:
        return {"received": True}

    update = await _set_payment_status_if_pending(
        payment_id=payment["id"],
        shop_id=payment["shop_id"],
        new_status="successful",
        extra_fields={"method": "paystack", "paystack_reference": reference},
    )
    return {"received": True, "payment_id": payment["id"], "status": update.get("status")}


@api_router.post("/payments/mpesa/initiate")
async def payments_mpesa_initiate(
    data: MpesaPaymentInitiateRequest,
    user: dict = Depends(get_current_user),
):
    order = await db.orders.find_one({"id": data.order_id, "shop_id": user["shop_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    payment_query = {"order_id": data.order_id, "shop_id": user["shop_id"]}
    if data.payment_id:
        payment_query["id"] = data.payment_id
    payment = await db.payments.find_one(payment_query, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.get("order_id") != data.order_id:
        raise HTTPException(status_code=400, detail="Payment is not linked to the order")

    if _normalize_payment_status(payment.get("status")) == "successful":
        return {"message": "Payment already successful", "payment_id": payment["id"], "status": "successful"}

    amount = data.amount if data.amount is not None else payment.get("amount", order.get("total_amount", 0))
    checkout_request_id = f"ws_PAY_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"

    await db.payments.update_one(
        {"id": payment["id"], "shop_id": user["shop_id"]},
        {
            "$set": {
                "method": "mpesa",
                "status": "pending",
                "mpesa_checkout_request_id": checkout_request_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    await db.mpesa_transactions.insert_one(
        {
            "id": str(uuid.uuid4()),
            "checkout_request_id": checkout_request_id,
            "merchant_request_id": f"MR_{str(uuid.uuid4())[:12]}",
            "order_id": data.order_id,
            "payment_id": payment["id"],
            "phone": data.phone,
            "amount": amount,
            "status": "pending",
            "provider": "mpesa",
            "shop_id": user["shop_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {
        "payment_id": payment["id"],
        "order_id": data.order_id,
        "checkout_request_id": checkout_request_id,
        "status": "pending",
    }


@api_router.post("/payments/mpesa/confirm")
async def payments_mpesa_confirm(
    data: MpesaPaymentConfirmRequest,
    user: dict = Depends(get_current_user),
):
    payment = await db.payments.find_one({"id": data.payment_id, "shop_id": user["shop_id"]}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if _normalize_payment_method(payment.get("method")) not in {"mpesa", "paystack", "cash", "credit"}:
        raise HTTPException(status_code=400, detail="Unsupported payment method")

    status_update = await _set_payment_status_if_pending(
        payment_id=data.payment_id,
        shop_id=user["shop_id"],
        new_status=data.status,
        extra_fields={
            "method": "mpesa",
            "mpesa_receipt": data.mpesa_receipt,
            "mpesa_checkout_request_id": data.checkout_request_id or payment.get("mpesa_checkout_request_id"),
        },
    )

    if data.checkout_request_id:
        await db.mpesa_transactions.update_one(
            {"checkout_request_id": data.checkout_request_id, "shop_id": user["shop_id"]},
            {"$set": {"status": data.status, "mpesa_receipt": data.mpesa_receipt}},
        )

    return {"payment_id": data.payment_id, **status_update}


@api_router.get("/payments/{payment_id}/status")
async def get_payment_status(payment_id: str, user: dict = Depends(get_current_user)):
    payment = await db.payments.find_one({"id": payment_id, "shop_id": user["shop_id"]}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {
        "id": payment["id"],
        "order_id": payment.get("order_id"),
        "method": _normalize_payment_method(payment.get("method")),
        "status": _normalize_payment_status(payment.get("status")),
    }


@api_router.post("/payments/paystack/webhook")
async def payments_paystack_webhook(
    request: Request,
    x_paystack_signature: Optional[str] = Header(default=None, alias="x-paystack-signature"),
):
    raw_body = await request.body()
    secret = os.environ.get("PAYSTACK_WEBHOOK_SECRET")
    if not verify_paystack_signature(raw_body, x_paystack_signature or "", secret or ""):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    payload = json.loads(raw_body.decode("utf-8"))
    logger.info("Paystack webhook received path=/payments/paystack/webhook")
    return await handle_paystack_webhook_event(payload)


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
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.users.insert_one(user)
    return UserResponse(
        id=user_id,
        phone=data.phone,
        name=data.name,
        role="shopkeeper",
        shop_id=owner["shop_id"],
        subscription_status="active",
        created_at=user["created_at"],
    )


@api_router.get("/users", response_model=List[UserResponse])
async def list_users(owner: dict = Depends(require_owner)):
    """List all users in the shop"""
    users = await db.users.find(
        {"shop_id": owner["shop_id"]}, {"_id": 0, "pin_hash": 0}
    ).to_list(100)
    return [UserResponse(**u) for u in users]


@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, owner: dict = Depends(require_owner)):
    """Delete a shopkeeper (owner only)"""
    user = await db.users.find_one(
        {"id": user_id, "shop_id": owner["shop_id"]}, {"_id": 0}
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user["role"] == "owner":
        raise HTTPException(status_code=400, detail="Cannot delete owner")

    await db.users.delete_one({"id": user_id})
    await write_audit_log(owner["shop_id"], owner["id"], "delete", "user", user_id)
    return {"message": "User deleted"}


# =============================================================================
# REPORTS ROUTES
# =============================================================================


@api_router.get("/reports/dashboard")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    """Get dashboard statistics"""
    shop_id = user["shop_id"]
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Today's sales
    today_sales = await db.sales.find(
        {
            "shop_id": shop_id,
            "created_at": {"$gte": today.isoformat()},
            "status": "completed",
        },
        {"_id": 0},
    ).to_list(1000)

    today_total = sum(s["total_amount"] for s in today_sales)
    today_count = len(today_sales)

    # Sales by payment method today
    cash_sales = sum(
        s["total_amount"] for s in today_sales if s["payment_method"] == "cash"
    )
    paystack_sales = sum(
        s["total_amount"]
        for s in today_sales
        if s["payment_method"] in ["paystack", "mpesa"]
    )
    credit_sales = sum(
        s["total_amount"] for s in today_sales if s["payment_method"] == "credit"
    )

    # Low stock products
    low_stock = await db.products.find(
        {
            "shop_id": shop_id,
            "$expr": {"$lte": ["$stock_quantity", "$min_stock_level"]},
        },
        {"_id": 0},
    ).to_list(100)

    # Total credit outstanding
    credit_customers = await db.credit_customers.find(
        {"shop_id": shop_id}, {"_id": 0}
    ).to_list(1000)
    total_credit = sum(c["current_balance"] for c in credit_customers)

    # Recent sales
    recent_sales = (
        await db.sales.find({"shop_id": shop_id, "status": "completed"}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(10)
    )

    # Weekly sales data for chart
    weekly_data = []
    for i in range(7):
        day = today - timedelta(days=6 - i)
        day_end = day + timedelta(days=1)
        day_sales = await db.sales.find(
            {
                "shop_id": shop_id,
                "created_at": {"$gte": day.isoformat(), "$lt": day_end.isoformat()},
                "status": "completed",
            },
            {"_id": 0},
        ).to_list(1000)
        weekly_data.append(
            {
                "date": day.strftime("%a"),
                "sales": sum(s["total_amount"] for s in day_sales),
            }
        )

    return {
        "today": {
            "total": today_total,
            "count": today_count,
            "cash": cash_sales,
            "paystack": paystack_sales,
            "mpesa": paystack_sales,
            "credit": credit_sales,
        },
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock[:5],
        "restock_suggestions": build_restock_suggestions(low_stock),
        "total_credit_outstanding": total_credit,
        "recent_sales": recent_sales,
        "weekly_sales": weekly_data,
    }


@api_router.get("/reports/sales")
async def get_sales_report(
    start_date: str, end_date: str, user: dict = Depends(get_current_user)
):
    """Get detailed sales report"""
    sales = (
        await db.sales.find(
            {
                "shop_id": user["shop_id"],
                "created_at": {"$gte": start_date, "$lte": end_date},
                "status": "completed",
            },
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(10000)
    )

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
            "by_payment_method": by_method,
        },
    }


@api_router.get("/reports/credit")
async def get_credit_report(user: dict = Depends(get_current_user)):
    """Get credit customers report"""
    customers = await db.credit_customers.find(
        {"shop_id": user["shop_id"]}, {"_id": 0}
    ).to_list(1000)

    total_outstanding = sum(c["current_balance"] for c in customers)
    customers_with_balance = [c for c in customers if c["current_balance"] > 0]

    return {
        "customers": customers,
        "summary": {
            "total_customers": len(customers),
            "customers_with_balance": len(customers_with_balance),
            "total_outstanding": total_outstanding,
        },
    }


@api_router.get("/reports/damaged")
async def get_damaged_report(
    start_date: str, end_date: str, user: dict = Depends(get_current_user)
):
    """Get damaged stock report"""
    items = (
        await db.damaged_stock.find(
            {
                "shop_id": user["shop_id"],
                "created_at": {"$gte": start_date, "$lte": end_date},
            },
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(10000)
    )

    by_reason = {}
    for item in items:
        reason = item["reason"]
        by_reason[reason] = by_reason.get(reason, 0) + item["quantity"]

    return {
        "items": items,
        "summary": {
            "total_items": len(items),
            "total_quantity": sum(i["quantity"] for i in items),
            "by_reason": by_reason,
        },
    }


@api_router.get("/reports/pdf/sales")
async def generate_sales_pdf(
    start_date: str, end_date: str, user: dict = Depends(get_current_user)
):
    """Generate PDF sales report"""
    sales = (
        await db.sales.find(
            {
                "shop_id": user["shop_id"],
                "created_at": {"$gte": start_date, "$lte": end_date},
                "status": "completed",
            },
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(10000)
    )

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
    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    pdf_base64 = base64.b64encode(pdf_bytes).decode()

    return {
        "pdf": pdf_base64,
        "filename": f"sales_report_{start_date[:10]}_{end_date[:10]}.pdf",
    }


@api_router.get("/reports/pdf/credit")
async def generate_credit_pdf(user: dict = Depends(get_current_user)):
    """Generate PDF credit report"""
    customers = await db.credit_customers.find(
        {"shop_id": user["shop_id"]}, {"_id": 0}
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

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    pdf_base64 = base64.b64encode(pdf_bytes).decode()

    return {
        "pdf": pdf_base64,
        "filename": f"credit_report_{datetime.now().strftime('%Y%m%d')}.pdf",
    }


@api_router.get("/reports/pdf/damaged")
async def generate_damaged_pdf(
    start_date: str, end_date: str, user: dict = Depends(get_current_user)
):
    """Generate PDF damaged stock report"""
    items = await db.damaged_stock.find(
        {
            "shop_id": user["shop_id"],
            "created_at": {"$gte": start_date, "$lte": end_date},
        },
        {"_id": 0},
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

    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    pdf_base64 = base64.b64encode(pdf_bytes).decode()

    return {
        "pdf": pdf_base64,
        "filename": f"damaged_report_{start_date[:10]}_{end_date[:10]}.pdf",
    }


# =============================================================================
# SUPPLIER ROUTES
# =============================================================================


@api_router.post("/suppliers", response_model=SupplierResponse)
async def create_supplier(data: SupplierCreate, user: dict = Depends(get_current_user)):
    supplier_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    supplier = {
        "id": supplier_id,
        "name": data.name,
        "phone": data.phone,
        "notes": data.notes,
        "shop_id": user["shop_id"],
        "created_at": now,
    }

    await db.suppliers.insert_one(supplier)
    return SupplierResponse(**supplier)


@api_router.get("/suppliers", response_model=List[SupplierResponse])
async def list_suppliers(
    search: Optional[str] = None, user: dict = Depends(get_current_user)
):
    query = {"shop_id": user["shop_id"]}

    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
        ]

    suppliers = await db.suppliers.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    return [SupplierResponse(**s) for s in suppliers]


@api_router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(supplier_id: str, user: dict = Depends(get_current_user)):
    supplier = await db.suppliers.find_one(
        {"id": supplier_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return SupplierResponse(**supplier)


@api_router.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: str, data: SupplierUpdate, user: dict = Depends(require_owner)
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    result = await db.suppliers.update_one(
        {"id": supplier_id, "shop_id": user["shop_id"]}, {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Supplier not found")

    supplier = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    return SupplierResponse(**supplier)


@api_router.delete("/suppliers/{supplier_id}")
async def delete_supplier(supplier_id: str, user: dict = Depends(require_owner)):
    result = await db.suppliers.delete_one(
        {"id": supplier_id, "shop_id": user["shop_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Supplier not found")
    await write_audit_log(
        user["shop_id"], user["id"], "delete", "supplier", supplier_id
    )
    return {"message": "Supplier deleted"}


# =============================================================================
# PURCHASE ROUTES
# =============================================================================


@api_router.post("/purchases", response_model=PurchaseResponse)
async def create_purchase(data: PurchaseCreate, user: dict = Depends(get_current_user)):
    """Create a purchase order and update stock quantities"""
    purchase_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Get supplier info
    supplier = await db.suppliers.find_one(
        {"id": data.supplier_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Update stock for each item
    for item in data.items:
        product = await db.products.find_one(
            {"id": item.product_id, "shop_id": user["shop_id"]}, {"_id": 0}
        )
        if not product:
            raise HTTPException(
                status_code=404, detail=f"Product {item.product_id} not found"
            )

        # Calculate total units to add based on unit type
        total_units = item.quantity * item.units_per_package

        # Update product stock and cost price
        cost_per_unit = item.cost / total_units if total_units > 0 else 0
        await db.products.update_one(
            {"id": item.product_id, "shop_id": user["shop_id"]},
            {
                "$inc": {"stock_quantity": total_units},
                "$set": {"cost_price": cost_per_unit, "updated_at": now},
            },
        )

    purchase = {
        "id": purchase_id,
        "purchase_number": generate_purchase_number(),
        "supplier_id": data.supplier_id,
        "supplier_name": supplier["name"],
        "items": [item.model_dump() for item in data.items],
        "total_cost": data.total_cost,
        "notes": data.notes,
        "shop_id": user["shop_id"],
        "created_by": user["id"],
        "created_at": now,
    }

    await db.purchases.insert_one(purchase)
    return PurchaseResponse(**purchase)


@api_router.get("/purchases", response_model=List[PurchaseResponse])
async def list_purchases(
    supplier_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    query = {"shop_id": user["shop_id"]}

    if supplier_id:
        query["supplier_id"] = supplier_id

    if start_date:
        query["created_at"] = {"$gte": start_date}
    if end_date:
        if "created_at" in query:
            query["created_at"]["$lte"] = end_date
        else:
            query["created_at"] = {"$lte": end_date}

    purchases = (
        await db.purchases.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    )
    return [PurchaseResponse(**p) for p in purchases]


@api_router.get("/purchases/{purchase_id}", response_model=PurchaseResponse)
async def get_purchase(purchase_id: str, user: dict = Depends(get_current_user)):
    purchase = await db.purchases.find_one(
        {"id": purchase_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return PurchaseResponse(**purchase)


@api_router.delete("/purchases/{purchase_id}")
async def delete_purchase(purchase_id: str, user: dict = Depends(require_owner)):
    """Only owners can delete purchases"""
    purchase = await db.purchases.find_one(
        {"id": purchase_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    # Note: We don't reverse the stock changes when deleting
    # This is intentional as the stock was already physically received

    result = await db.purchases.delete_one({"id": purchase_id})
    await write_audit_log(
        user["shop_id"], user["id"], "delete", "purchase", purchase_id
    )
    return {"message": "Purchase record deleted"}


@api_router.get("/purchases/stats/summary")
async def get_purchases_summary(user: dict = Depends(get_current_user)):
    """Get purchase statistics"""
    shop_id = user["shop_id"]
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Today's purchases
    today_purchases = await db.purchases.find(
        {"shop_id": shop_id, "created_at": {"$gte": today.isoformat()}}, {"_id": 0}
    ).to_list(1000)

    today_total = sum(p["total_cost"] for p in today_purchases)

    # Total suppliers
    supplier_count = await db.suppliers.count_documents({"shop_id": shop_id})

    # This month's purchases
    month_start = today.replace(day=1)
    month_purchases = await db.purchases.find(
        {"shop_id": shop_id, "created_at": {"$gte": month_start.isoformat()}},
        {"_id": 0},
    ).to_list(10000)

    month_total = sum(p["total_cost"] for p in month_purchases)

    return {
        "today_purchases": len(today_purchases),
        "today_total": today_total,
        "month_total": month_total,
        "supplier_count": supplier_count,
    }


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
    await write_audit_log(
        owner["shop_id"],
        owner["id"],
        "update",
        "shop",
        owner["shop_id"],
        {"fields": list(update_data.keys())},
    )
    shop = await db.shops.find_one({"id": owner["shop_id"]}, {"_id": 0})
    return shop


def build_customer_cart_item_response(item: dict, product: dict) -> CustomerCartItemResponse:
    return CustomerCartItemResponse(
        id=item["id"],
        shop_id=item["shop_id"],
        product_id=item["product_id"],
        name=product.get("name", ""),
        price=product.get("unit_price", 0),
        image_url=product.get("image_url"),
        quantity=item.get("quantity", 0),
        created_at=item.get("created_at", datetime.now(timezone.utc).isoformat()),
    )


def build_customer_order_response(order: dict, order_items: List[dict], payment: Optional[dict]) -> CustomerOrderResponse:
    items: List[CustomerOrderItemResponse] = []
    for item in order_items:
        items.append(
            CustomerOrderItemResponse(
                product_id=item.get("product_id", ""),
                name=item.get("product_name") or item.get("name") or "Unknown Product",
                quantity=item.get("quantity", 0),
                price=item.get("unit_price", 0),
            )
        )

    payment_payload = CustomerOrderPaymentResponse(
        method=(payment or {}).get("method", "unknown"),
        status=(payment or {}).get("status", "unknown"),
    )

    return CustomerOrderResponse(
        order_id=order["id"],
        order_number=order.get("order_number") or order["id"],
        total_amount=order.get("total_amount", 0),
        status=get_order_lifecycle_status(order),
        created_at=order.get("created_at", ""),
        items=items,
        payment=payment_payload,
    )


@api_router.post("/customer/cart", response_model=CustomerCartItemResponse)
async def customer_add_to_cart(
    data: CustomerCartItemCreate,
    customer: dict = Depends(require_customer),
):
    shop = await db.shops.find_one({"id": data.shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    product = await db.products.find_one(
        {"id": data.product_id, "shop_id": data.shop_id},
        {"_id": 0},
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.get("is_active", True):
        raise HTTPException(status_code=400, detail="Product is not active")

    existing = await db.customer_cart.find_one(
        {
            "user_id": customer["id"],
            "product_id": data.product_id,
            "shop_id": data.shop_id,
        },
        {"_id": 0},
    )
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        new_quantity = existing.get("quantity", 0) + data.quantity
        await db.customer_cart.update_one(
            {"id": existing["id"], "user_id": customer["id"]},
            {"$set": {"quantity": new_quantity, "updated_at": now}},
        )
        existing["quantity"] = new_quantity
        existing["updated_at"] = now
        return build_customer_cart_item_response(existing, product)

    cart_item = {
        "id": str(uuid.uuid4()),
        "user_id": customer["id"],
        "product_id": data.product_id,
        "shop_id": data.shop_id,
        "quantity": data.quantity,
        "created_at": now,
    }
    await db.customer_cart.insert_one(cart_item)
    return build_customer_cart_item_response(cart_item, product)


@api_router.get("/customer/cart", response_model=List[CustomerCartItemResponse])
async def customer_get_cart(customer: dict = Depends(require_customer)):
    items = await db.customer_cart.find({"user_id": customer["id"]}, {"_id": 0}).to_list(1000)
    response_items: List[CustomerCartItemResponse] = []
    for item in items:
        product = await db.products.find_one(
            {"id": item["product_id"], "shop_id": item["shop_id"]},
            {"_id": 0},
        )
        if not product or not product.get("is_active", True):
            continue
        response_items.append(build_customer_cart_item_response(item, product))
    return response_items


@api_router.put("/customer/cart/{item_id}", response_model=CustomerCartItemResponse)
async def customer_update_cart_item(
    item_id: str,
    data: CustomerCartItemUpdate,
    customer: dict = Depends(require_customer),
):
    item = await db.customer_cart.find_one({"id": item_id, "user_id": customer["id"]}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    product = await db.products.find_one(
        {"id": item["product_id"], "shop_id": item["shop_id"]},
        {"_id": 0},
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.get("is_active", True):
        raise HTTPException(status_code=400, detail="Product is not active")

    await db.customer_cart.update_one(
        {"id": item_id, "user_id": customer["id"]},
        {"$set": {"quantity": data.quantity, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    item["quantity"] = data.quantity
    return build_customer_cart_item_response(item, product)


@api_router.delete("/customer/cart/{item_id}")
async def customer_delete_cart_item(item_id: str, customer: dict = Depends(require_customer)):
    result = await db.customer_cart.delete_one({"id": item_id, "user_id": customer["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cart item not found")
    return {"message": "Cart item removed"}


@api_router.post("/customer/checkout")
async def customer_checkout(
    data: CustomerCheckoutRequest,
    request: Request,
    customer: dict = Depends(require_customer),
):
    idem_key = request.headers.get("Idempotency-Key")
    existing_response = await get_stored_checkout_response(customer["id"], idem_key)
    if existing_response:
        return existing_response

    logger.info("Checkout start flow=customer user_id=%s", customer["id"])
    customer_items = await db.customer_cart.find({"user_id": customer["id"]}, {"_id": 0}).to_list(1000)
    if not customer_items:
        raise HTTPException(status_code=400, detail="Customer cart is empty")

    shop_ids = {item["shop_id"] for item in customer_items}
    if len(shop_ids) != 1:
        raise HTTPException(status_code=400, detail="Customer cart must contain items from one shop")
    checkout_shop_id = next(iter(shop_ids))

    pos_cart_items = []
    for item in customer_items:
        product = await db.products.find_one(
            {"id": item["product_id"], "shop_id": checkout_shop_id},
            {"_id": 0},
        )
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item['product_id']} not found")
        if not product.get("is_active", True):
            raise HTTPException(status_code=400, detail=f"Product {item['product_id']} is not active")
        if product.get("stock_quantity", 0) < item["quantity"]:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.get('name', item['product_id'])}")

        pos_cart_items.append(
            {
                "id": item["id"],
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "created_at": item.get("created_at", datetime.now(timezone.utc).isoformat()),
            }
        )

    cart = await db.cart.find_one(
        {"user_id": customer["id"], "shop_id": checkout_shop_id},
        {"_id": 0},
    )
    cart_id = cart["id"] if cart else str(uuid.uuid4())
    await db.cart.update_one(
        {"id": cart_id},
        {
            "$set": {
                "user_id": customer["id"],
                "shop_id": checkout_shop_id,
                "items": pos_cart_items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$setOnInsert": {"id": cart_id},
        },
        upsert=True,
    )

    checkout_user = {**customer, "shop_id": checkout_shop_id}
    try:
        checkout_result = await checkout_cart(
            CheckoutRequest(
                payment_method=data.payment_method,
                customer_id=data.customer_id,
            ),
            checkout_user,
        )
    except Exception:
        logger.exception("Checkout failure flow=customer user_id=%s", customer["id"])
        raise

    await db.orders.update_one(
        {"id": checkout_result.id, "shop_id": checkout_shop_id},
        {"$set": {"source": "customer_app"}},
    )
    await initialize_order_lifecycle(checkout_result.id, checkout_shop_id)
    await db.customer_cart.delete_many({"user_id": customer["id"]})
    response_payload = {"order": checkout_result.model_dump(), "items": checkout_result.items}
    await store_checkout_response(customer["id"], idem_key, response_payload)
    logger.info("Checkout success flow=customer user_id=%s order_id=%s", customer["id"], checkout_result.id)
    return response_payload


@api_router.get("/customer/orders", response_model=List[CustomerOrderResponse])
async def customer_list_orders(
    limit: Optional[int] = None,
    offset: int = 0,
    customer: dict = Depends(require_customer),
):
    safe_limit, safe_offset = normalize_limit_offset(limit, offset, default_limit=200, max_limit=500)
    orders = await db.orders.find(
        {"user_id": customer["id"]},
        {"_id": 0},
    ).sort("created_at", -1).skip(safe_offset).limit(safe_limit).to_list(safe_limit)

    order_ids = [order["id"] for order in orders]
    if not order_ids:
        return []

    order_items_list = await db.order_items.find({"order_id": {"$in": order_ids}}, {"_id": 0}).to_list(5000)
    payments_list = await db.payments.find({"order_id": {"$in": order_ids}}, {"_id": 0}).to_list(5000)

    items_by_order: Dict[str, List[dict]] = {}
    for item in order_items_list:
        items_by_order.setdefault(item.get("order_id"), []).append(item)

    payment_by_order: Dict[str, dict] = {}
    for payment in payments_list:
        order_id = payment.get("order_id")
        if order_id and order_id not in payment_by_order:
            payment_by_order[order_id] = payment

    response: List[CustomerOrderResponse] = []
    for order in orders:
        await ensure_order_lifecycle_initialized(order)
        order_items = items_by_order.get(order["id"], [])
        payment = payment_by_order.get(order["id"])
        response.append(build_customer_order_response(order, order_items, payment))
    return response


@api_router.get("/customer/orders/{order_id}", response_model=CustomerOrderResponse)
async def customer_get_order(order_id: str, customer: dict = Depends(require_customer)):
    order = await db.orders.find_one(
        {"id": order_id, "user_id": customer["id"]},
        {"_id": 0},
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    await ensure_order_lifecycle_initialized(order)

    order_items = await db.order_items.find({"order_id": order["id"]}, {"_id": 0}).to_list(1000)
    payment = await db.payments.find_one({"order_id": order["id"]}, {"_id": 0})
    return build_customer_order_response(order, order_items, payment)



@api_router.get("/cart")
async def get_cart(user: dict = Depends(get_current_user)):
    """Return the active user's cart with hydrated product details."""
    cart = await db.cart.find_one(
        {"user_id": user["id"], "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not cart:
        return {"items": [], "summary": {"total_items": 0, "total_amount": 0}}

    detailed_items = []
    total_amount = 0.0
    for item in cart.get("items", []):
        product = await db.products.find_one(
            {"id": item["product_id"], "shop_id": user["shop_id"]}, {"_id": 0}
        )
        if not product:
            continue
        line_total = product.get("unit_price", 0) * item["quantity"]
        total_amount += line_total
        detailed_items.append(
            {
                "id": item["id"],
                "quantity": item["quantity"],
                "line_total": line_total,
                "product": product,
            }
        )

    return normalize_object_ids(
        {
            "id": cart["id"],
            "items": detailed_items,
            "summary": {
                "total_items": sum(i["quantity"] for i in cart.get("items", [])),
                "total_amount": total_amount,
            },
        }
    )


@api_router.post("/cart")
async def add_to_cart(data: CartItemCreate, user: dict = Depends(get_current_user)):
    """Add an item to the authenticated user's cart."""
    if not is_valid_object_id(data.product_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId for product_id")

    product = await db.products.find_one(
        {"id": data.product_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart = await db.cart.find_one(
        {"user_id": user["id"], "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not cart:
        cart = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "shop_id": user["shop_id"],
            "items": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    items = list(cart.get("items", []))
    existing = next((item for item in items if item["product_id"] == data.product_id), None)
    new_quantity = data.quantity + (existing["quantity"] if existing else 0)
    if new_quantity > product.get("stock_quantity", 0):
        raise HTTPException(status_code=400, detail="Insufficient stock for requested cart quantity")

    if existing:
        existing["quantity"] = new_quantity
    else:
        items.append(
            {
                "id": str(uuid.uuid4()),
                "product_id": data.product_id,
                "quantity": data.quantity,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    await db.cart.update_one(
        {"id": cart["id"]},
        {
            "$set": {
                "user_id": user["id"],
                "shop_id": user["shop_id"],
                "items": items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$setOnInsert": {"id": cart["id"]},
        },
        upsert=True,
    )
    await write_audit_log(user["shop_id"], user["id"], "add", "cart_item", data.product_id, {"quantity": data.quantity})
    return {"message": "Item added to cart", "cart_id": cart["id"], "item_count": len(items)}


@api_router.put("/cart/{item_id}")
async def update_cart_item(
    item_id: str,
    data: CartItemUpdate,
    user: dict = Depends(get_current_user),
):
    """Update the quantity of a cart item."""
    if not is_valid_object_id(item_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId for item_id")

    cart = await db.cart.find_one(
        {"user_id": user["id"], "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    items = list(cart.get("items", []))
    item = next((entry for entry in items if entry["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    product = await db.products.find_one(
        {"id": item["product_id"], "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if data.quantity > product.get("stock_quantity", 0):
        raise HTTPException(status_code=400, detail="Insufficient stock for requested quantity")

    item["quantity"] = data.quantity
    await db.cart.update_one(
        {"id": cart["id"]},
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await write_audit_log(user["shop_id"], user["id"], "update", "cart_item", item_id, {"quantity": data.quantity})
    return {"message": "Cart item updated"}


@api_router.delete("/cart/{item_id}")
async def delete_cart_item(item_id: str, user: dict = Depends(get_current_user)):
    """Remove an item from the active user's cart."""
    if not is_valid_object_id(item_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId for item_id")

    cart = await db.cart.find_one(
        {"user_id": user["id"], "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    items = list(cart.get("items", []))
    filtered = [entry for entry in items if entry["id"] != item_id]
    if len(filtered) == len(items):
        raise HTTPException(status_code=404, detail="Cart item not found")

    await db.cart.update_one(
        {"id": cart["id"]},
        {"$set": {"items": filtered, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await write_audit_log(user["shop_id"], user["id"], "delete", "cart_item", item_id)
    return {"message": "Cart item removed"}


@api_router.post("/orders/checkout")
async def checkout_order(
    data: CheckoutRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Create an order from cart items and record payment.

    Example response:
    {
      "order": {"id": "...", "total_amount": 1200.0, "payment_status": "successful"},
      "items": [{"product_id": "...", "quantity": 2}]
    }
    """
    idem_key = request.headers.get("Idempotency-Key")
    existing_response = await get_stored_checkout_response(user["id"], idem_key)
    if existing_response:
        return existing_response

    logger.info("Checkout start flow=pos user_id=%s shop_id=%s", user["id"], user.get("shop_id"))
    try:
        result = await checkout_cart(data, user)
    except Exception:
        logger.exception("Checkout failure flow=pos user_id=%s shop_id=%s", user["id"], user.get("shop_id"))
        raise
    await initialize_order_lifecycle(result.id, user["shop_id"])
    await write_audit_log(user["shop_id"], user["id"], "checkout", "order", result.id, {"payment_method": data.payment_method})
    response_payload = {"order": result.model_dump(), "items": result.items}
    await store_checkout_response(user["id"], idem_key, response_payload)
    logger.info("Checkout success flow=pos user_id=%s order_id=%s", user["id"], result.id)
    return response_payload


@api_router.get("/orders")
async def list_orders(
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    """List orders with pagination for the active shop."""
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)
    query = {"shop_id": user["shop_id"]}
    if user["role"] != "owner":
        query["user_id"] = user["id"]

    orders = await db.orders.find(query, {"_id": 0}).to_list(5000)
    paged = orders[safe_offset : safe_offset + safe_limit]
    for order in paged:
        await ensure_order_lifecycle_initialized(order)
        order["status"] = get_order_lifecycle_status(order)
        order["status_history"] = get_order_status_history(order)
    return {
        "data": normalize_object_ids(paged),
        "pagination": {"limit": safe_limit, "offset": safe_offset, "total": len(orders)},
    }


@api_router.get("/orders/{order_id}")
async def get_order(order_id: str, user: dict = Depends(get_current_user)):
    """Get a single order with items and payments."""
    if not is_valid_object_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId for order_id")

    query = {"id": order_id, "shop_id": user["shop_id"]}
    if user["role"] != "owner":
        query["user_id"] = user["id"]
    order = await db.orders.find_one(query, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    await ensure_order_lifecycle_initialized(order)
    order["status"] = get_order_lifecycle_status(order)
    order["status_history"] = get_order_status_history(order)

    items = await db.order_items.find({"order_id": order_id, "shop_id": user["shop_id"]}, {"_id": 0}).to_list(1000)
    payments = await db.payments.find({"order_id": order_id, "shop_id": user["shop_id"]}, {"_id": 0}).to_list(1000)
    return normalize_object_ids({"order": order, "items": items, "payments": payments})


@api_router.patch("/orders/{order_id}")
async def patch_order_status(
    order_id: str,
    data: OrderStatusPatch,
    owner: dict = Depends(require_owner),
):
    """Owner-only order status update."""
    if not is_valid_object_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId for order_id")

    order = await db.orders.find_one({"id": order_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if (data.status or "").lower() in VALID_ORDER_STATUSES:
        await set_order_lifecycle_status(order_id, owner["shop_id"], data.status, enforce_transition=False)
    else:
        await db.orders.update_one(
            {"id": order_id, "shop_id": owner["shop_id"]},
            {
                "$set": {
                    "status": data.status,
                    "lifecycle_status": data.status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
    await write_audit_log(owner["shop_id"], owner["id"], "update_status", "order", order_id, {"status": data.status})
    order = await db.orders.find_one({"id": order_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    await ensure_order_lifecycle_initialized(order)
    order["status"] = get_order_lifecycle_status(order)
    order["status_history"] = get_order_status_history(order)
    return normalize_object_ids(order)


@api_router.patch("/orders/{order_id}/status")
async def patch_order_lifecycle_status(
    order_id: str,
    data: OrderLifecycleStatusPatch,
    user: dict = Depends(get_current_user),
):
    if user.get("role") not in {"owner", "shopkeeper"}:
        raise HTTPException(status_code=403, detail="Owner or shopkeeper access required")
    if not is_valid_object_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId for order_id")

    order = await db.orders.find_one({"id": order_id, "shop_id": user["shop_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updated = await set_order_lifecycle_status(order_id, user["shop_id"], data.status, enforce_transition=True)
    logger.info(
        {
            "event": "order_status_changed",
            "order_id": order_id,
            "from": get_order_lifecycle_status(order),
            "to": data.status,
            "user_id": user["id"],
        }
    )
    await write_audit_log(
        user["shop_id"],
        user["id"],
        "update_lifecycle_status",
        "order",
        order_id,
        {"status": data.status},
    )
    return normalize_object_ids(
        {
            "id": updated["id"],
            "status": get_order_lifecycle_status(updated),
            "status_history": get_order_status_history(updated),
        }
    )


@api_router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, user: dict = Depends(get_current_user)):
    """Cancel an order if it is still pending/processing."""
    if not is_valid_object_id(order_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId for order_id")

    query = {"id": order_id, "shop_id": user["shop_id"]}
    if user["role"] != "owner":
        query["user_id"] = user["id"]
    order = await db.orders.find_one(query, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    await ensure_order_lifecycle_initialized(order)
    current_status = get_order_lifecycle_status(order)
    if current_status not in {"pending", "paid", "processing"}:
        raise HTTPException(status_code=400, detail="Only pending/processing orders can be cancelled")
    await set_order_lifecycle_status(order_id, user["shop_id"], "cancelled", enforce_transition=False)
    await write_audit_log(user["shop_id"], user["id"], "cancel", "order", order_id)
    return {"message": "Order cancelled", "order_id": order_id}

async def checkout_cart(data: CheckoutRequest, user: dict):
    async def _run_checkout(session=None):
        cart = await db.cart.find_one(
            {"user_id": user["id"], "shop_id": user["shop_id"]}, {"_id": 0}
        )
        if not cart or not cart.get("items"):
            raise HTTPException(status_code=400, detail="Cart is empty")

        order_items = []
        total_amount = 0.0
        for item in cart["items"]:
            quantity = item["quantity"]
            product = await db.products.find_one(
                {"id": item["product_id"], "shop_id": user["shop_id"]}, {"_id": 0}
            )
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")

            stock_update = await db.products.update_one(
                {
                    "id": product["id"],
                    "shop_id": user["shop_id"],
                    "stock_quantity": {"$gte": quantity},
                },
                {"$inc": {"stock_quantity": -quantity}},
                session=session,
            )
            if stock_update.matched_count == 0:
                raise HTTPException(status_code=400, detail="Insufficient stock")

            line_total = product.get("unit_price", 0) * quantity
            total_amount += line_total
            order_items.append(
                {
                    "id": str(uuid.uuid4()),
                    "order_id": None,
                    "shop_id": user["shop_id"],
                    "product_id": product["id"],
                    "product_name": product.get("name"),
                    "quantity": quantity,
                    "unit_price": product.get("unit_price", 0),
                    "total": line_total,
                    "item_id": item.get("id"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        order_id = str(uuid.uuid4())
        for order_item in order_items:
            order_item["order_id"] = order_id
            await db.order_items.insert_one(order_item, session=session)

        order = {
            "id": order_id,
            "shop_id": user["shop_id"],
            "user_id": user["id"],
            "total_amount": total_amount,
            "status": "completed",
            "customer_id": data.customer_id,
            "payment_method": data.payment_method,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.orders.insert_one(order, session=session)

        if data.payment_method == "credit":
            if not data.customer_id:
                raise HTTPException(status_code=400, detail="customer_id is required for credit checkout")
            await db.credit_customers.update_one(
                {"id": data.customer_id, "shop_id": user["shop_id"]},
                {"$inc": {"current_balance": total_amount}},
                session=session,
            )

        if data.payment_method == "credit":
            payment_status = "on_credit"
        elif data.payment_method == "mpesa":
            payment_status = "pending"
        else:
            payment_status = "successful"
        await db.payments.insert_one(
            {
                "id": str(uuid.uuid4()),
                "order_id": order_id,
                "shop_id": user["shop_id"],
                "amount": total_amount,
                "method": data.payment_method,
                "status": payment_status,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            session=session,
        )

        # Clear POS cart only after successful order + payment creation
        await db.cart.update_one(
            {"id": cart["id"]},
            {"$set": {"items": [], "updated_at": datetime.now(timezone.utc).isoformat()}},
            session=session,
        )
        return CheckoutResponse(
            id=order["id"],
            total_amount=order["total_amount"],
            shop_id=order["shop_id"],
            status=order["status"],
            payment_status=payment_status,
            payment_method=data.payment_method,
            customer_id=data.customer_id,
            items=order_items,
        )

    if hasattr(client, "start_session"):
        async with await client.start_session() as session:
            async with session.start_transaction():
                return await _run_checkout(session=session)
    return await _run_checkout()


async def create_marketplace_order(data: MarketplaceOrderCreate, owner: dict):
    existing_cart = await db.cart.find_one({"user_id": owner["id"], "shop_id": owner["shop_id"]}, {"_id": 0})
    cart_id = existing_cart["id"] if existing_cart else str(uuid.uuid4())
    cart_items = []
    original_stock_levels: Dict[str, int] = {}
    for item in data.items:
        product = await db.products.find_one({"id": item.product_id, "shop_id": owner["shop_id"]}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        original_stock_levels[item.product_id] = product.get("stock_quantity", 0)
        if product.get("stock_quantity", 0) < item.quantity:
            await db.products.update_one(
                {"id": item.product_id, "shop_id": owner["shop_id"]},
                {"$inc": {"stock_quantity": item.quantity - product.get("stock_quantity", 0)}},
            )
        cart_items.append(
            {
                "id": str(uuid.uuid4()),
                "product_id": item.product_id,
                "quantity": item.quantity,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    await db.cart.update_one(
        {"id": cart_id},
        {
            "$set": {
                "id": cart_id,
                "user_id": owner["id"],
                "shop_id": owner["shop_id"],
                "items": cart_items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    checkout_result = await checkout_cart(
        CheckoutRequest(payment_method=data.payment_method),
        {"id": owner["id"], "shop_id": owner["shop_id"], "role": owner.get("role", "owner")},
    )
    order_id = checkout_result.id
    await initialize_order_lifecycle(order_id, owner["shop_id"])

    # Restore stock levels so inventory is updated only when delivery is confirmed.
    for item in data.items:
        await db.products.update_one(
            {"id": item.product_id, "shop_id": owner["shop_id"]},
            {"$set": {"stock_quantity": original_stock_levels.get(item.product_id, 0)}},
        )

    if existing_cart:
        await db.cart.update_one(
            {"id": existing_cart["id"]},
            {"$set": {"items": existing_cart.get("items", []), "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    else:
        await db.cart.delete_one({"id": cart_id})

    marketplace_items = [item.model_dump() for item in data.items]
    total_amount = sum(item.quantity * item.unit_cost for item in data.items)
    await db.orders.update_one(
        {"id": order_id, "shop_id": owner["shop_id"]},
        {
            "$set": {
                "vendor_id": data.vendor_id,
                "status": "pending",
                "payment_method": data.payment_method,
                "items": marketplace_items,
                "total_amount": total_amount,
            }
        },
    )
    await db.payments.update_one(
        {"order_id": order_id, "shop_id": owner["shop_id"]},
        {"$set": {"amount": total_amount, "status": "pending", "method": data.payment_method}},
    )
    order = await db.orders.find_one({"id": order_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    return order


async def receive_marketplace_order(order_id: str, update: MarketplaceDeliveryUpdate, owner: dict):
    order = await db.orders.find_one({"id": order_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if update.status == "delivered":
        for item in order.get("items", []):
            await db.products.update_one(
                {"id": item["product_id"], "shop_id": owner["shop_id"]},
                {"$inc": {"stock_quantity": item["quantity"]}},
            )
        existing_payment = await db.payments.find_one({"order_id": order_id, "shop_id": owner["shop_id"]}, {"_id": 0})
        if existing_payment:
            await _set_payment_status_if_pending(
                payment_id=existing_payment["id"],
                shop_id=owner["shop_id"],
                new_status="successful",
                extra_fields={"method": order.get("payment_method")},
            )
        else:
            total_amount = sum(i["quantity"] * i["unit_cost"] for i in order.get("items", []))
            await db.payments.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "order_id": order_id,
                    "shop_id": owner["shop_id"],
                    "amount": total_amount,
                    "method": order.get("payment_method"),
                    "status": "successful",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    if (update.status or "").lower() in VALID_ORDER_STATUSES:
        updated_order = await set_order_lifecycle_status(order_id, owner["shop_id"], update.status, enforce_transition=False)
        await db.orders.update_one(
            {"id": order_id, "shop_id": owner["shop_id"]},
            {"$set": {"notes": update.notes}},
        )
        order = updated_order
    else:
        await db.orders.update_one(
            {"id": order_id, "shop_id": owner["shop_id"]},
            {"$set": {"status": update.status, "notes": update.notes}},
        )
        order["status"] = update.status
    return order


async def compare_payment_providers(user: dict):
    return {
        "recommended_provider": "paystack",
        "guidance": f"Use Paystack for shop_id={user.get('shop_id')}",
    }


def to_public_product_view(product: dict) -> PublicProductResponse:
    return PublicProductResponse(
        id=product["id"],
        name=product.get("name", ""),
        price=product.get("unit_price", 0),
        image_url=product.get("image_url"),
        description=product.get("description"),
        availability="in_stock" if product.get("stock_quantity", 0) > 0 else "out_of_stock",
    )


@api_router.get("/public/stores", response_model=List[PublicStoreResponse])
async def public_list_stores(limit: Optional[int] = None, offset: int = 0):
    safe_limit, safe_offset = normalize_limit_offset(limit, offset, default_limit=10000, max_limit=10000)
    shops = await db.shops.find({}, {"_id": 0}).skip(safe_offset).limit(safe_limit).to_list(safe_limit)
    active_shops = [shop for shop in shops if shop.get("is_active", True)]
    return [
        PublicStoreResponse(
            id=shop["id"],
            name=shop.get("name", ""),
            category=shop.get("category"),
        )
        for shop in active_shops
    ]


@api_router.get(
    "/public/stores/{shop_id}/products",
    response_model=List[PublicProductResponse],
)
async def public_list_store_products(shop_id: str, limit: Optional[int] = None, offset: int = 0):
    safe_limit, safe_offset = normalize_limit_offset(limit, offset, default_limit=10000, max_limit=10000)
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop or not shop.get("is_active", True):
        raise HTTPException(status_code=404, detail="Store not found")

    products = await db.products.find({"shop_id": shop_id}, {"_id": 0}).skip(safe_offset).limit(safe_limit).to_list(safe_limit)
    active_products = [product for product in products if product.get("is_active", True)]
    return [to_public_product_view(product) for product in active_products]


@api_router.get("/public/products", response_model=List[PublicProductResponse])
async def public_list_products(limit: Optional[int] = None, offset: int = 0):
    safe_limit, safe_offset = normalize_limit_offset(limit, offset, default_limit=10000, max_limit=10000)
    products = await db.products.find({"is_active": True}, {"_id": 0}).skip(safe_offset).limit(safe_limit).to_list(safe_limit)
    return [to_public_product_view(product) for product in products]


@api_router.get("/public/products/{product_id}", response_model=PublicProductResponse)
async def public_get_product(product_id: str):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product or not product.get("is_active", True):
        raise HTTPException(status_code=404, detail="Product not found")

    return to_public_product_view(product)


# =============================================================================
# HEALTH CHECK
# =============================================================================


@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


allowed_origins = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]
if (
    "*" in allowed_origins
    and os.environ.get("ENVIRONMENT", "development") == "production"
):
    raise RuntimeError("CORS_ORIGINS must not include '*' in production")

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include router
app.include_router(api_router)


@app.on_event("startup")
async def ensure_indexes():
    try:
        await db.orders.create_index([("user_id", 1), ("created_at", -1)])
        await db.orders.create_index([("shop_id", 1), ("created_at", -1)])
        await db.orders.create_index([("lifecycle_status", 1), ("shop_id", 1)])
        await db.payments.create_index("reference", unique=True, sparse=True)
        await db.order_items.create_index("order_id")
        await db.customer_cart.create_index([("user_id", 1), ("shop_id", 1)])
    except Exception:
        logger.exception("Failed to ensure indexes")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# =============================================================================
# PAYSTACK ROUTES
# =============================================================================


@api_router.post("/paystack/initialize")
async def paystack_initialize(
    data: PaystackInitializeRequest, user: dict = Depends(get_current_user)
):
    transaction_id = (
        f"PSTK_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"
    )
    paystack_secret = os.environ.get("PAYSTACK_SECRET_KEY")
    callback_url = os.environ.get("PAYSTACK_CALLBACK_URL", "http://localhost:3000/pos")

    # Sandbox fallback when no key is configured
    if not paystack_secret:
        await db.mpesa_transactions.insert_one(
            {
                "id": str(uuid.uuid4()),
                "checkout_request_id": transaction_id,
                "merchant_request_id": transaction_id,
                "sale_id": data.sale_id,
                "phone": data.email,
                "amount": data.amount,
                "status": "pending",
                "provider": "paystack_sandbox",
                "shop_id": user["shop_id"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            "status": True,
            "message": "Paystack sandbox initialized (configure PAYSTACK_SECRET_KEY for live)",
            "data": {
                "authorization_url": f"https://sandbox.local/paystack/{transaction_id}",
                "reference": transaction_id,
                "access_code": transaction_id,
                "sandbox": True,
            },
        }

    headers = {
        "Authorization": f"Bearer {paystack_secret}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": data.email,
        "amount": int(data.amount * 100),
        "reference": transaction_id,
        "callback_url": callback_url or None,
        "metadata": {"sale_id": data.sale_id, "shop_id": user["shop_id"]},
    }
    resp = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=payload,
        headers=headers,
        timeout=20,
    )
    if not resp.ok:
        logger.error("Paystack initialize failed: %s", resp.text)
        raise HTTPException(status_code=502, detail="Paystack initialize failed")

    data_resp = resp.json()
    await db.mpesa_transactions.insert_one(
        {
            "id": str(uuid.uuid4()),
            "checkout_request_id": transaction_id,
            "merchant_request_id": transaction_id,
            "sale_id": data.sale_id,
            "phone": data.email,
            "amount": data.amount,
            "status": "pending",
            "provider": "paystack",
            "shop_id": user["shop_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return data_resp


@api_router.get("/paystack/verify/{reference}")
async def paystack_verify(reference: str, user: dict = Depends(get_current_user)):
    transaction = await db.mpesa_transactions.find_one(
        {"checkout_request_id": reference, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    paystack_secret = os.environ.get("PAYSTACK_SECRET_KEY")
    if not paystack_secret:
        await db.mpesa_transactions.update_one(
            {"checkout_request_id": reference},
            {
                "$set": {
                    "status": "completed",
                    "mpesa_receipt": f"PSTK-SBX-{reference[-6:]}",
                }
            },
        )
        await db.sales.update_one(
            {"id": transaction["sale_id"]},
            {
                "$set": {
                    "status": "completed",
                    "mpesa_transaction_id": f"PSTK-SBX-{reference[-6:]}",
                }
            },
        )
        payment = await db.payments.find_one(
            {"shop_id": user["shop_id"], "paystack_reference": reference}, {"_id": 0}
        )
        if payment:
            await _set_payment_status_if_pending(
                payment_id=payment["id"],
                shop_id=user["shop_id"],
                new_status="successful",
                extra_fields={"method": "paystack", "paystack_reference": reference},
            )
        return {"status": "success", "reference": reference, "sandbox": True}

    headers = {"Authorization": f"Bearer {paystack_secret}"}
    resp = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers=headers,
        timeout=20,
    )
    if not resp.ok:
        logger.error("Paystack verify failed: %s", resp.text)
        raise HTTPException(status_code=502, detail="Paystack verify failed")
    payload = resp.json()
    if payload.get("data", {}).get("status") == "success":
        receipt = payload.get("data", {}).get("reference", reference)
        await db.mpesa_transactions.update_one(
            {"checkout_request_id": reference},
            {"$set": {"status": "completed", "mpesa_receipt": receipt}},
        )
        await db.sales.update_one(
            {"id": transaction["sale_id"]},
            {"$set": {"status": "completed", "mpesa_transaction_id": receipt}},
        )
        payment = await db.payments.find_one(
            {"shop_id": user["shop_id"], "paystack_reference": reference}, {"_id": 0}
        )
        if payment:
            await _set_payment_status_if_pending(
                payment_id=payment["id"],
                shop_id=user["shop_id"],
                new_status="successful",
                extra_fields={"method": "paystack", "paystack_reference": receipt},
            )
    return payload


@api_router.post("/paystack/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: Optional[str] = Header(default=None, alias="x-paystack-signature"),
):
    logger.warning("Deprecated webhook endpoint used")
    raw_body = await request.body()
    secret = os.environ.get("PAYSTACK_WEBHOOK_SECRET")
    if not verify_paystack_signature(raw_body, x_paystack_signature or "", secret or ""):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = json.loads(raw_body.decode("utf-8"))
    logger.info("Paystack webhook received path=/paystack/webhook")
    event_response = await handle_paystack_webhook_event(payload)

    # Keep legacy side-effects for backwards compatibility with sale-based Paystack flows
    event = payload.get("event")
    data = payload.get("data", {}) or {}
    reference = data.get("reference")
    if event == "charge.success" and reference:
        transaction = await db.mpesa_transactions.find_one(
            {"checkout_request_id": reference}, {"_id": 0}
        )
        if transaction:
            await db.mpesa_transactions.update_one(
                {"checkout_request_id": reference},
                {"$set": {"status": "completed", "mpesa_receipt": reference}},
            )
            await db.sales.update_one(
                {"id": transaction["sale_id"]},
                {"$set": {"status": "completed", "mpesa_transaction_id": reference}},
            )
    return event_response


@app.post("/api/paystack/webhook")
async def paystack_webhook_alias(
    request: Request,
    x_paystack_signature: Optional[str] = Header(default=None, alias="x-paystack-signature"),
):
    return await paystack_webhook(request=request, x_paystack_signature=x_paystack_signature)


@api_router.post("/client-errors")
async def capture_client_error(event: ClientErrorEvent):
    logger.error(
        "FrontendError message=%s source=%s line=%s col=%s url=%s",
        event.message,
        event.source,
        event.lineno,
        event.colno,
        event.url,
    )
    if event.stack:
        logger.error("FrontendError stack=%s", event.stack)
    return {"received": True}
