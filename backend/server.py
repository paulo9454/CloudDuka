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
from io import StringIO
from fpdf import FPDF
import base64
import requests
import time
import hmac
import hashlib
import json
import csv
import re
from math import radians, sin, cos, sqrt, atan2
from bson import ObjectId
from backend.seed_realistic import seed_realistic_async

load_dotenv()

# MongoDB connection
mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
db_name = os.environ.get("DB_NAME", "cloudduka")
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

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
    shop_ids: Optional[List[str]] = None


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
    shop_ids: Optional[List[str]] = None
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
    reliability_score: Optional[float] = None
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
    supplier_id: Optional[str] = None
    items: List[PurchaseItem] = Field(default_factory=list)
    total_cost: float = 0.0
    product_ids: List[str] = Field(default_factory=list)
    use_auto_suggestions: bool = False
    notes: Optional[str] = None


class PurchaseResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    purchase_number: str
    supplier_id: str
    supplier_name: str
    items: List[PurchaseItem]
    total_cost: float
    estimated_arrival_days: Optional[int] = None
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
    shop_id: Optional[str] = None
    name: str
    price: float
    image_url: Optional[str] = None
    description: Optional[str] = None
    availability: str


class SocialOrderLineItem(BaseModel):
    product_id: Optional[str] = None
    quantity: int = Field(default=1, gt=0)


class WhatsAppOrderIngestionRequest(BaseModel):
    phone_number: str
    product_ids: List[SocialOrderLineItem] = Field(default_factory=list)
    metadata: Optional[dict] = None


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


class RiderOrderStatusPatch(BaseModel):
    status: Literal["on_delivery", "completed"]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())


def create_token(user_id: str, shop_id: Optional[str], role: str) -> str:
    payload = {
        "user_id": user_id,
        "shop_id": shop_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def check_subscription(shop_or_id):
    shop_id = shop_or_id["id"] if isinstance(shop_or_id, dict) else shop_or_id
    if not shop_id:
        return True

    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        if hasattr(db, "subscriptions"):
            legacy_subscription = await db.subscriptions.find_one(
                {"shop_id": shop_id}, {"_id": 0}
            )
            if legacy_subscription and (
                legacy_subscription.get("status") or ""
            ).lower() == "expired":
                raise HTTPException(status_code=403, detail="Subscription expired")
        return True
    return check_shop_subscription(shop)


def normalize_shop_subscription(shop: dict) -> dict:
    subscription = shop.get("subscription") or {}

    plan = (subscription.get("plan") or "pos").lower()
    if plan not in {"pos", "online"}:
        plan = "pos"

    status = (subscription.get("status") or "active").lower()
    if status not in {"active", "expired"}:
        status = "active"

    expires_at = subscription.get("expires_at")
    return {"plan": plan, "status": status, "expires_at": expires_at}


def check_shop_subscription(shop: dict, required_feature: Optional[str] = None):
    subscription = normalize_shop_subscription(shop)
    status = subscription["status"]
    expires_at = subscription.get("expires_at")
    if expires_at:
        try:
            expires_at_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires_at_dt < datetime.now(timezone.utc):
                status = "expired"
        except ValueError:
            logger.warning("Invalid subscription expires_at for shop %s", shop.get("id"))

    if status != "active":
        raise HTTPException(status_code=403, detail="Subscription expired")

    # Backward compatibility: legacy shops may not yet have an embedded
    # `subscription` payload. Do not hard-block those records for online checks.
    has_embedded_subscription = bool(shop.get("subscription"))
    if (
        required_feature == "online"
        and subscription["plan"] != "online"
        and has_embedded_subscription
    ):
        raise HTTPException(status_code=403, detail="Online store not enabled")

    return True


async def validate_shop_access(user: dict, shop_id: Optional[str] = None):
    target_shop_id = shop_id or get_active_shop_id(user)
    if not target_shop_id:
        raise HTTPException(status_code=400, detail="shop_id is required")

    shop_ids = [sid for sid in user.get("shop_ids", []) if sid]
    if shop_ids and target_shop_id not in shop_ids:
        raise HTTPException(status_code=403, detail="You do not have access to this shop")

    if (
        user.get("role") == "shopkeeper"
        and user.get("shop_id") != target_shop_id
        and not shop_ids
    ):
        raise HTTPException(status_code=403, detail="Shopkeepers cannot switch shops")

    return {"id": target_shop_id}


def get_active_shop_id(
    user: dict, request: Optional[Request] = None, x_shop_id: Optional[str] = None
) -> Optional[str]:
    if user.get("role") == "customer":
        return None

    header_shop_id = None
    if request and getattr(request, "headers", None):
        header_shop_id = request.headers.get("X-Shop-Id")

    requested_shop_id = x_shop_id or header_shop_id
    shop_ids = [sid for sid in (user.get("shop_ids") or []) if sid]

    if requested_shop_id:
        if shop_ids and requested_shop_id not in shop_ids:
            raise HTTPException(status_code=403, detail="You do not have access to this shop")
        return requested_shop_id

    fallback_shop_id = user.get("shop_id") or user.get("default_shop_id")
    if fallback_shop_id:
        if shop_ids and fallback_shop_id not in shop_ids:
            return shop_ids[0]
        return fallback_shop_id

    if shop_ids:
        return shop_ids[0]

    return None


async def get_current_user(
    request: Request = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_shop_id: Optional[str] = Header(default=None, alias="X-Shop-Id"),
):
    try:
        resolved_x_shop_id = x_shop_id if isinstance(x_shop_id, str) else None
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        role = user.get("role") or payload.get("role", "owner")
        default_shop_id = (
            user.get("shop_id") or user.get("default_shop_id") or payload.get("shop_id")
        )
        shop_ids = [sid for sid in (user.get("shop_ids") or []) if sid]
        if not shop_ids and default_shop_id:
            shop_ids = [default_shop_id]

        if role == "customer":
            hydrated_user = {
                **user,
                "role": "customer",
                "shop_id": None,
                "shop_ids": [],
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

        active_shop_id = (
            resolved_x_shop_id
            or payload.get("shop_id")
            or default_shop_id
            or (shop_ids[0] if shop_ids else None)
        )

        if hasattr(db, "shop_users") and active_shop_id:
            membership = await db.shop_users.find_one(
                {"user_id": user["id"], "shop_id": active_shop_id}, {"_id": 0}
            )
            if membership:
                role = membership.get("role", role)
                if active_shop_id not in shop_ids:
                    shop_ids.append(active_shop_id)
            elif role == "shopkeeper" and default_shop_id != active_shop_id:
                raise HTTPException(status_code=403, detail="Shopkeepers cannot switch shops")

        if (
            role == "shopkeeper"
            and resolved_x_shop_id
            and default_shop_id
            and resolved_x_shop_id != default_shop_id
            and resolved_x_shop_id not in shop_ids
        ):
            raise HTTPException(status_code=403, detail="Shopkeepers cannot switch shops")

        if default_shop_id and default_shop_id not in shop_ids:
            shop_ids.append(default_shop_id)
        if active_shop_id and shop_ids and active_shop_id not in shop_ids:
            raise HTTPException(status_code=403, detail="You do not have access to this shop")

        hydrated_user = {
            **user,
            "role": role,
            "shop_id": active_shop_id or default_shop_id or (shop_ids[0] if shop_ids else None),
            "shop_ids": shop_ids,
            "default_shop_id": user.get("default_shop_id", default_shop_id),
        }
        hydrated_user["shop_id"] = get_active_shop_id(
            hydrated_user, request=request, x_shop_id=resolved_x_shop_id
        )

        if (
            role in {"owner", "shopkeeper"}
            and request
            and request.url.path.startswith("/api/")
            and not request.url.path.startswith("/api/auth/")
            and not request.url.path.startswith("/api/public/")
            and not request.url.path.startswith("/api/customer/")
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


def require_rider(user: dict = Depends(get_current_user)):
    if user.get("role") != "rider":
        raise HTTPException(status_code=403, detail="Rider access required")
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


def resolve_period_range(period: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    normalized = (period or "today").strip().lower()
    if normalized == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif normalized == "week":
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif normalized == "month":
        start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        raise HTTPException(status_code=400, detail="Invalid period. Use today, week, or month")
    return start.isoformat(), now.isoformat()


FORECAST_OBSERVABILITY = {
    "forecast_requests": 0,
    "stockout_predictions": 0,
    "restock_accuracy": None,  # reserved for future calibration pipeline
}
AUTO_PURCHASE_OBSERVABILITY = {
    "auto_purchase_requests": 0,
    "recommended_purchase_accuracy": None,  # reserved for future calibration pipeline
    "supplier_rank_usage": 0,
}
SOCIAL_COMMERCE_OBSERVABILITY = {
    "social_product_feed_requests": 0,
    "social_order_ingestions": 0,
    "webhook_event_errors": 0,
    "external_checkout_redirects": 0,
}
_DAILY_SALES_CACHE: Dict[str, dict] = {}


async def get_product_daily_sales(shop_id: str, product_id: str, lookback_days: int = 14) -> List[float]:
    days = max(lookback_days, 1)
    cache_key = f"{shop_id}:{product_id}:{days}"
    now = datetime.now(timezone.utc)
    cached = _DAILY_SALES_CACHE.get(cache_key)
    if cached and (now - cached["computed_at"]).total_seconds() < 300:
        return list(cached["series"])

    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    pipeline = [
        {"$match": {"shop_id": shop_id, "product_id": product_id, "created_at": {"$gte": start}}},
        {"$project": {"day": {"$substr": ["$created_at", 0, 10]}, "quantity": 1}},
        {"$group": {"_id": "$day", "units": {"$sum": "$quantity"}}},
        {"$sort": {"_id": 1}},
    ]
    rows = await db.order_items.aggregate(pipeline).to_list(days + 5)
    by_day = {row.get("_id"): float(row.get("units", 0) or 0) for row in rows}

    series: List[float] = []
    for i in range(days):
        day = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        series.append(float(by_day.get(day, 0.0)))

    _DAILY_SALES_CACHE[cache_key] = {"computed_at": now, "series": series}
    return series


async def forecast_demand(product_id: str, shop_id: str, days: int = 7) -> dict:
    FORECAST_OBSERVABILITY["forecast_requests"] += 1
    forecast_days = max(days, 1)
    series = await get_product_daily_sales(shop_id, product_id, lookback_days=14)
    if not series:
        series = [0.0]
    avg_daily_sales = float(sum(series) / len(series)) if series else 0.0
    last_3_avg = float(sum(series[-3:]) / max(len(series[-3:]), 1)) if series else 0.0

    if avg_daily_sales == 0:
        trend_factor = 1.0
    elif last_3_avg > avg_daily_sales * 1.05:
        trend_factor = 1.2
    elif last_3_avg < avg_daily_sales * 0.95:
        trend_factor = 0.8
    else:
        trend_factor = 1.0

    forecast_value = avg_daily_sales * forecast_days * trend_factor
    product = await db.products.find_one({"id": product_id, "shop_id": shop_id}, {"_id": 0}) or {}
    if avg_daily_sales <= 0:
        # New/unsold products fallback to velocity signal.
        fallback_velocity = float(product.get("sales_velocity", 0.0) or 0.0)
        if fallback_velocity > 0:
            avg_daily_sales = fallback_velocity
            forecast_value = avg_daily_sales * forecast_days

    current_stock = float(product.get("stock_quantity", 0) or 0)
    days_until_stockout = None if avg_daily_sales <= 0 else round(current_stock / avg_daily_sales, 2)
    if days_until_stockout is not None:
        FORECAST_OBSERVABILITY["stockout_predictions"] += 1

    predicted_demand_7d = round(float(forecast_value), 2)
    await db.products.update_one(
        {"id": product_id, "shop_id": shop_id},
        {
            "$set": {
                "predicted_demand_7d": predicted_demand_7d,
                "predicted_stockout_days": days_until_stockout,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    return {
        "product_id": product_id,
        "last_7_days_sales": series[-7:],
        "avg_daily_sales": round(avg_daily_sales, 4),
        "trend_factor": trend_factor,
        "forecast_7d": predicted_demand_7d,
        "days_until_stockout": days_until_stockout,
    }


async def compute_inventory_health(shop_id: str) -> dict:
    products = await db.products.find({"shop_id": shop_id}, {"_id": 0}).to_list(5000)
    total = max(len(products), 1)
    low_stock = 0
    out_of_stock = 0
    forecast_risk = 0
    for product in products:
        stock = float(product.get("stock_quantity", 0) or 0)
        min_stock = float(product.get("min_stock_level", 0) or 0)
        if stock <= min_stock:
            low_stock += 1
        if stock <= 0:
            out_of_stock += 1
        days_until_stockout = product.get("predicted_stockout_days")
        if isinstance(days_until_stockout, (int, float)) and days_until_stockout < 5:
            forecast_risk += 1

    low_ratio = low_stock / total
    out_ratio = out_of_stock / total
    risk_ratio = forecast_risk / total
    raw_score = 100 - int((low_ratio * 35 + out_ratio * 45 + risk_ratio * 20) * 100)
    score = max(0, min(100, raw_score))
    status = "good" if score >= 75 else ("warning" if score >= 45 else "critical")
    return {"health_score": score, "status": status}


async def compute_sales_velocity(shop_id: str, days: int = 30) -> dict:
    start = (datetime.now(timezone.utc) - timedelta(days=max(days, 1))).isoformat()
    pipeline = [
        {"$match": {"shop_id": shop_id, "created_at": {"$gte": start}}},
        {
            "$group": {
                "_id": "$product_id",
                "units_sold": {"$sum": "$quantity"},
            }
        },
    ]
    order_item_stats = await db.order_items.aggregate(pipeline).to_list(5000)
    velocity_by_product = {}
    for row in order_item_stats:
        product_id = row.get("_id")
        units = float(row.get("units_sold", 0) or 0)
        velocity = round(units / max(days, 1), 4)
        velocity_by_product[product_id] = velocity
        await db.products.update_one(
            {"id": product_id, "shop_id": shop_id},
            {"$set": {"sales_velocity": velocity, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    return velocity_by_product


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_po_reference(shop_id: str, supplier_id: str, product_ids: List[str], now: datetime) -> str:
    key = f"{shop_id}:{supplier_id}:{','.join(sorted(product_ids))}:{now.strftime('%Y%m%d')}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8].upper()
    return f"PO-AUTO-{now.strftime('%Y%m%d')}-{digest}"


def _calc_supplier_reliability(stats: dict) -> float:
    avg_arrival = _safe_float(stats.get("avg_arrival_days"), 7.0)
    avg_fulfillment = _safe_float(stats.get("avg_fulfillment_rate"), 1.0)
    if avg_arrival <= 2:
        speed_score = 1.0
    elif avg_arrival <= 5:
        speed_score = 0.8
    elif avg_arrival <= 8:
        speed_score = 0.6
    else:
        speed_score = 0.4
    reliability = (avg_fulfillment * 0.7) + (speed_score * 0.3)
    return round(max(0.0, min(1.0, reliability)), 4)


async def _supplier_rankings(shop_id: str) -> List[dict]:
    suppliers = await db.suppliers.find({"shop_id": shop_id}, {"_id": 0}).to_list(2000)
    purchases = await db.purchases.find({"shop_id": shop_id}, {"_id": 0}).to_list(10000)

    perf: Dict[str, dict] = {}
    for supplier in suppliers:
        perf[supplier["id"]] = {
            "supplier_id": supplier["id"],
            "name": supplier.get("name"),
            "lead_time_days": max(1, _safe_int(supplier.get("lead_time_days"), 3)),
            "purchase_count": 0,
            "total_spend": 0.0,
            "total_units_ordered": 0,
            "total_units_received": 0,
            "total_arrival_days": 0.0,
            "arrival_samples": 0,
            "reliability_score": _safe_float(supplier.get("reliability_score"), 0.0),
            "cost_efficiency": 0.0,
            "average_fulfillment_rate": 1.0,
        }

    for purchase in purchases:
        sid = purchase.get("supplier_id")
        if sid not in perf:
            continue
        row = perf[sid]
        row["purchase_count"] += 1
        row["total_spend"] += _safe_float(purchase.get("total_cost"), 0.0)

        ordered_units = 0
        received_units = 0
        for item in purchase.get("items", []):
            qty = max(0, _safe_int(item.get("quantity"), 0))
            upp = max(1, _safe_int(item.get("units_per_package"), 1))
            ordered_units += qty * upp
            received_units += max(0, _safe_int(item.get("received_quantity"), qty)) * upp
        row["total_units_ordered"] += ordered_units
        row["total_units_received"] += min(received_units, ordered_units) if ordered_units > 0 else 0
        arrival_days = _safe_float(
            purchase.get("estimated_arrival_days", purchase.get("actual_arrival_days", row["lead_time_days"])),
            row["lead_time_days"],
        )
        row["total_arrival_days"] += max(1.0, arrival_days)
        row["arrival_samples"] += 1

    ranked = []
    for row in perf.values():
        ordered = max(row["total_units_ordered"], 1)
        arrival_samples = max(row["arrival_samples"], 1)
        avg_arrival = row["total_arrival_days"] / arrival_samples
        avg_fulfillment = row["total_units_received"] / ordered
        avg_cost_per_unit = row["total_spend"] / ordered if ordered > 0 else 0.0
        row["average_fulfillment_rate"] = round(avg_fulfillment, 4)
        row["avg_arrival_days"] = round(avg_arrival, 2)
        row["avg_cost_per_unit"] = round(avg_cost_per_unit, 4)
        row["cost_efficiency"] = round(1 / max(avg_cost_per_unit, 0.01), 4)
        computed_reliability = _calc_supplier_reliability(row)
        row["reliability_score"] = computed_reliability
        await db.suppliers.update_one(
            {"id": row["supplier_id"], "shop_id": shop_id},
            {"$set": {"reliability_score": computed_reliability, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        ranked.append(row)

    ranked.sort(
        key=lambda s: (
            -_safe_float(s.get("reliability_score"), 0.0),
            -_safe_float(s.get("average_fulfillment_rate"), 0.0),
            -_safe_float(s.get("cost_efficiency"), 0.0),
            _safe_int(s.get("lead_time_days"), 99),
            -_safe_int(s.get("purchase_count"), 0),
        )
    )
    return ranked


async def _compute_auto_purchase_suggestions(shop_id: str, days: int = 7) -> List[dict]:
    AUTO_PURCHASE_OBSERVABILITY["auto_purchase_requests"] += 1
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0}) or {}
    subscription = normalize_shop_subscription(shop)
    demand_multiplier = 1.15 if subscription.get("plan") == "online" else 1.0
    products = await db.products.find({"shop_id": shop_id}, {"_id": 0}).to_list(5000)
    rankings = await _supplier_rankings(shop_id)
    velocity_by_product = await compute_sales_velocity(shop_id, days=max(days, 1))
    suggestions: List[dict] = []
    for product in products:
        product_id = product.get("id")
        stock = max(0, _safe_int(product.get("stock_quantity"), 0))
        trend = await forecast_demand(product_id=product_id, shop_id=shop_id, days=max(days, 1))
        predicted_demand = _safe_float(trend.get("forecast_7d"), 0.0)
        if predicted_demand <= 0:
            fallback_velocity = _safe_float(
                velocity_by_product.get(product_id, product.get("sales_velocity", 0.0)),
                0.0,
            )
            predicted_demand = max(0.0, round(fallback_velocity * max(days, 1), 2))
        predicted_demand = round(predicted_demand * demand_multiplier, 2)

        candidate_suppliers = [s for s in rankings if s.get("purchase_count", 0) > 0]
        if not candidate_suppliers:
            candidate_suppliers = rankings
        if not candidate_suppliers:
            continue
        preferred = candidate_suppliers[0]
        AUTO_PURCHASE_OBSERVABILITY["supplier_rank_usage"] += 1
        lead_time = max(1, _safe_int(preferred.get("lead_time_days"), 3))
        reliability = max(0.1, _safe_float(preferred.get("reliability_score"), 0.7))
        moq = max(1, _safe_int(product.get("moq"), 1))
        lead_time_buffer = predicted_demand * (lead_time / 7)
        reliability_buffer = predicted_demand * (1 - min(reliability, 1.0)) * 0.5
        target_qty = int(round(predicted_demand + lead_time_buffer + reliability_buffer))
        shortage = max(0, target_qty - stock)
        if shortage <= 0:
            continue
        recommended_qty = int(((max(shortage, moq) + moq - 1) // moq) * moq)
        est_unit_cost = _safe_float(product.get("cost_price"), 0.0)
        estimated_cost = round(est_unit_cost * recommended_qty, 2)
        await db.products.update_one(
            {"id": product_id, "shop_id": shop_id},
            {
                "$set": {
                    "recommended_purchase_qty": recommended_qty,
                    "preferred_supplier_id": preferred["supplier_id"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        suggestions.append(
            {
                "product_id": product_id,
                "name": product.get("name"),
                "current_stock": stock,
                "predicted_demand_7d": round(predicted_demand, 2),
                "recommended_quantity": recommended_qty,
                "preferred_supplier_id": preferred["supplier_id"],
                "estimated_arrival_days": lead_time,
                "estimated_cost": estimated_cost,
                "lead_time_days": lead_time,
                "supplier_reliability_score": reliability,
            }
        )
    return suggestions


def _shop_slug(shop: dict) -> str:
    source = (shop or {}).get("slug") or (shop or {}).get("name") or (shop or {}).get("id") or "shop"
    slug = re.sub(r"[^a-z0-9]+", "-", str(source).strip().lower()).strip("-")
    return slug or "shop"


def _build_social_product_feed_item(product: dict, shop_slug: str) -> dict:
    stock = _safe_int(product.get("stock_quantity"), 0)
    return {
        "product_id": product.get("id"),
        "title": product.get("name"),
        "description": product.get("description") or "",
        "price": _safe_float(product.get("unit_price"), 0.0),
        "availability": "in_stock" if stock > 0 else "out_of_stock",
        "image_url": product.get("image_url") or "",
        "product_url": f"/public/storefront/{shop_slug}/product/{product.get('id')}",
        "category": product.get("category") or "General",
        "brand": product.get("brand") or (product.get("shop_name") or "CloudDuka"),
        # Optional platform fields (left additive for future connectors)
        "gtin": product.get("gtin"),
        "ean": product.get("ean"),
        "upc": product.get("upc"),
        "sale_price": product.get("sale_price"),
        "additional_images": product.get("additional_images") or [],
    }


async def _ingest_social_order(
    *,
    shop_id: str,
    channel: str,
    phone_number: str,
    line_items: List[dict],
    metadata: Optional[dict] = None,
) -> dict:
    SOCIAL_COMMERCE_OBSERVABILITY["social_order_ingestions"] += 1
    clean_items = []
    unknown_items = []
    for row in line_items or []:
        product_id = str(row.get("product_id") or "").strip()
        quantity = max(1, _safe_int(row.get("quantity"), 1))
        if not product_id:
            unknown_items.append(row)
            continue
        product = await db.products.find_one({"id": product_id, "shop_id": shop_id}, {"_id": 0})
        if not product:
            unknown_items.append(row)
            continue
        clean_items.append({"product_id": product_id, "quantity": quantity})

    if not clean_items:
        SOCIAL_COMMERCE_OBSERVABILITY["webhook_event_errors"] += 1
        raise HTTPException(status_code=400, detail="No valid products found in social order payload")

    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0}) or {}
    check_shop_subscription(shop)
    actor_user_id = shop.get("owner_id")
    if not actor_user_id:
        SOCIAL_COMMERCE_OBSERVABILITY["webhook_event_errors"] += 1
        raise HTTPException(status_code=400, detail="Shop owner not configured")

    cart = await db.cart.find_one({"user_id": actor_user_id, "shop_id": shop_id}, {"_id": 0})
    cart_id = cart.get("id") if cart else str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    cart_items = [
        {
            "id": str(uuid.uuid4()),
            "product_id": item["product_id"],
            "quantity": item["quantity"],
            "created_at": now,
        }
        for item in clean_items
    ]
    await db.cart.update_one(
        {"id": cart_id},
        {
            "$set": {
                "id": cart_id,
                "user_id": actor_user_id,
                "shop_id": shop_id,
                "items": cart_items,
                "updated_at": now,
            }
        },
        upsert=True,
    )

    requested_method = validate_checkout_payment_method((metadata or {}).get("payment_method"))
    checkout = await checkout_cart(
        CheckoutRequest(
            payment_method=requested_method,
            customer_name=(metadata or {}).get("customer_name"),
            customer_id=(metadata or {}).get("customer_id"),
        ),
        {"id": actor_user_id, "shop_id": shop_id},
    )
    await db.orders.update_one(
        {"id": checkout.id, "shop_id": shop_id},
        {
            "$set": {
                "source": f"social_{channel}",
                "social_channel": channel,
                "social_phone_number": phone_number,
                "social_metadata": metadata or {},
            }
        },
    )

    payment_link = None
    if requested_method in {"paystack", "mpesa"}:
        SOCIAL_COMMERCE_OBSERVABILITY["external_checkout_redirects"] += 1
        payment_link = f"/api/orders/{checkout.id}/pay"

    return {
        "order_id": checkout.id,
        "status": checkout.status,
        "payment_method": checkout.payment_method,
        "payment_status": checkout.payment_status,
        "payment_link": payment_link,
        "unknown_items": unknown_items,
    }


def safe_regex(value: str, *, max_len: int = 80) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) > max_len:
        text = text[:max_len]
    return re.escape(text)


def tokenize_search_terms(query_text: str) -> List[str]:
    cleaned = (query_text or "").strip().lower()
    if not cleaned:
        return []
    parts = [part for part in re.split(r"\s+", cleaned) if part]
    return parts[:8]


def compute_fallback_search_score(product: dict, query_text: str, terms: List[str]) -> float:
    name = str(product.get("name") or "").lower()
    description = str(product.get("description") or "").lower()
    exact_query = query_text.strip().lower()
    score = 0.0
    if exact_query and name == exact_query:
        score += 100.0
    elif exact_query and exact_query in name:
        score += 60.0
    elif exact_query and exact_query in description:
        score += 30.0

    for term in terms:
        if term == name:
            score += 20.0
        elif term in name:
            score += 10.0
        elif term in description:
            score += 4.0
    return score


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


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    earth_radius_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius_km * c


VALID_CHECKOUT_PAYMENT_METHODS = {"cash", "mpesa", "credit", "paystack"}


def validate_checkout_payment_method(payment_method: Optional[str]) -> str:
    normalized = (payment_method or "").strip().lower()
    if normalized not in VALID_CHECKOUT_PAYMENT_METHODS:
        raise HTTPException(
            status_code=422,
            detail="payment_method is required and must be one of: cash, mpesa, credit, paystack",
        )
    return normalized


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
    if stored and stored.get("status") == "completed" and stored.get("response"):
        return stored["response"]
    return None


async def begin_checkout_idempotency(user_id: str, key: Optional[str]) -> dict:
    if not key or not hasattr(db, "checkout_requests"):
        return {"state": "disabled"}

    existing = await db.checkout_requests.find_one({"key": key, "user_id": user_id}, {"_id": 0})
    if existing:
        if existing.get("status") == "completed" and existing.get("response"):
            return {"state": "completed", "response": existing["response"]}
        return {"state": "processing"}

    now = datetime.now(timezone.utc).isoformat()
    await db.checkout_requests.update_one(
        {"key": key, "user_id": user_id},
        {
            "$set": {"status": "processing", "updated_at": now},
            "$setOnInsert": {"key": key, "user_id": user_id, "created_at": now},
        },
        upsert=True,
    )
    return {"state": "acquired"}


async def store_checkout_response(user_id: str, key: Optional[str], response_payload: dict):
    if not key or not hasattr(db, "checkout_requests"):
        return
    await db.checkout_requests.update_one(
        {"key": key, "user_id": user_id},
        {
            "$set": {
                "status": "completed",
                "response": response_payload,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$setOnInsert": {"key": key, "user_id": user_id, "created_at": datetime.now(timezone.utc).isoformat()},
        },
        upsert=True,
    )


async def mark_checkout_idempotency_failed(user_id: str, key: Optional[str]):
    if not key or not hasattr(db, "checkout_requests"):
        return
    await db.checkout_requests.update_one(
        {"key": key, "user_id": user_id},
        {"$set": {"status": "failed", "updated_at": datetime.now(timezone.utc).isoformat()}},
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
            "shop_ids": [data.shop_id],
            "default_shop_id": data.shop_id,
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
            "shop_ids": user.get("shop_ids", [user.get("shop_id")] if user.get("shop_id") else []),
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
        "subscription": {"plan": "pos", "status": "active", "expires_at": None},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.shops.insert_one(shop)

    owner_record = await db.users.find_one({"id": user["id"]}, {"_id": 0}) or user
    owner_shop_ids = [
        sid
        for sid in (
            owner_record.get("shop_ids")
            or [owner_record.get("shop_id")]
            or [owner_record.get("default_shop_id")]
        )
        if sid
    ]
    if shop_id not in owner_shop_ids:
        owner_shop_ids.append(shop_id)
    default_shop_id = owner_record.get("default_shop_id") or owner_record.get("shop_id") or shop_id
    update_doc = {"shop_ids": owner_shop_ids, "default_shop_id": default_shop_id}
    if not owner_record.get("shop_id"):
        update_doc["shop_id"] = default_shop_id
    await db.users.update_one({"id": user["id"]}, {"$set": update_doc})

    if hasattr(db, "shop_users"):
        existing_membership = await db.shop_users.find_one(
            {"user_id": user["id"], "shop_id": shop_id}, {"_id": 0}
        )
        if not existing_membership:
            await db.shop_users.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user["id"],
                    "shop_id": shop_id,
                    "role": "owner",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    return shop


@api_router.get("/shops/my")
async def list_my_shops(user: dict = Depends(get_current_user)):
    if user.get("role") == "customer":
        raise HTTPException(status_code=403, detail="Customer access is limited to public/customer endpoints")

    shop_ids = [sid for sid in (user.get("shop_ids") or []) if sid]
    if not shop_ids and user.get("shop_id"):
        shop_ids = [user["shop_id"]]
    if not shop_ids:
        return []

    shops = await db.shops.find({"id": {"$in": shop_ids}}, {"_id": 0}).to_list(1000)
    return [
        {
            "id": shop["id"],
            "name": shop.get("name", ""),
            "category": shop.get("category"),
        }
        for shop in shops
    ]
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
    shop_ids = [sid for sid in (user.get("shop_ids") or []) if sid]
    if not shop_ids and default_shop_id:
        shop_ids = [default_shop_id]
    membership = None
    if hasattr(db, "shop_users"):
        membership = await db.shop_users.find_one(
            {"user_id": user["id"], "shop_id": default_shop_id}, {"_id": 0}
        )
    if membership and default_shop_id and default_shop_id not in shop_ids:
        shop_ids.append(default_shop_id)
    role = user.get("role") or (membership.get("role") if membership else "owner")
    active_shop_id = shop_ids[0] if shop_ids else default_shop_id
    token = create_token(user["id"], active_shop_id, role)

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "phone": user["phone"],
            "name": user["name"],
            "role": role,
            "shop_id": active_shop_id,
            "shop_ids": shop_ids,
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
        shop_ids=user.get("shop_ids"),
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


@api_router.get("/products/{product_id}/demand-trend")
async def get_product_demand_trend(
    product_id: str,
    days: int = 7,
    user: dict = Depends(get_current_user),
):
    await validate_shop_access(user, user.get("shop_id"))
    product = await db.products.find_one({"id": product_id, "shop_id": user["shop_id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    trend = await forecast_demand(product_id=product_id, shop_id=user["shop_id"], days=max(days, 1))
    return {
        "product_id": product_id,
        "name": product.get("name"),
        "last_7_days_sales": trend["last_7_days_sales"],
        "avg_daily_sales": trend["avg_daily_sales"],
        "trend_factor": trend["trend_factor"],
        "forecast_7d": trend["forecast_7d"],
        "days_until_stockout": trend["days_until_stockout"],
    }


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


@api_router.get("/products/low-stock")
async def list_low_stock_products(
    period_days: int = 30,
    user: dict = Depends(get_current_user),
):
    await validate_shop_access(user, user.get("shop_id"))
    velocity_by_product = await compute_sales_velocity(user["shop_id"], days=max(period_days, 1))
    products = await db.products.find(
        {
            "shop_id": user["shop_id"],
            "$expr": {"$lte": ["$stock_quantity", "$min_stock_level"]},
        },
        {"_id": 0},
    ).to_list(5000)
    fast_threshold = 1.0
    slow_threshold = 0.1
    for product in products:
        velocity = float(velocity_by_product.get(product.get("id"), product.get("sales_velocity", 0.0)) or 0.0)
        product["sales_velocity"] = velocity
        product["movement"] = "fast_moving" if velocity >= fast_threshold else ("slow_moving" if velocity <= slow_threshold else "steady")
    return {"count": len(products), "products": products}


@api_router.get("/products/out-of-stock")
async def list_out_of_stock_products(
    period_days: int = 30,
    user: dict = Depends(get_current_user),
):
    await validate_shop_access(user, user.get("shop_id"))
    velocity_by_product = await compute_sales_velocity(user["shop_id"], days=max(period_days, 1))
    products = await db.products.find(
        {"shop_id": user["shop_id"], "stock_quantity": {"$lte": 0}},
        {"_id": 0},
    ).to_list(5000)
    for product in products:
        product["sales_velocity"] = float(velocity_by_product.get(product.get("id"), product.get("sales_velocity", 0.0)) or 0.0)
    return {"count": len(products), "products": products}


@api_router.get("/inventory/restock-suggestions")
async def restock_suggestions(
    period_days: int = 30,
    user: dict = Depends(get_current_user),
):
    await validate_shop_access(user, user.get("shop_id"))
    velocity_by_product = await compute_sales_velocity(user["shop_id"], days=max(period_days, 1))
    products = await db.products.find({"shop_id": user["shop_id"]}, {"_id": 0}).to_list(5000)
    suggestions = []
    for product in products:
        min_stock = int(product.get("min_stock_level", 0) or 0)
        stock = int(product.get("stock_quantity", 0) or 0)
        velocity = float(velocity_by_product.get(product.get("id"), product.get("sales_velocity", 0.0)) or 0.0)
        low_stock_needed = stock <= min_stock
        high_demand = velocity >= 1.0
        if not low_stock_needed and not high_demand:
            continue
        recommended_quantity = max(min_stock - stock, int(round(velocity * 14)))
        if recommended_quantity <= 0:
            continue
        reason = "high_demand" if high_demand and not low_stock_needed else ("low_stock" if low_stock_needed and not high_demand else "low_stock,high_demand")
        suggestions.append(
            {
                "product_id": product.get("id"),
                "recommended_quantity": max(int(round(velocity * 7)) - stock, 0),
                "reason": reason,
                "sales_velocity": velocity,
                "predicted_demand_7d": round(float(velocity * 7), 2),
                "current_stock": stock,
            }
        )
    return {"count": len(suggestions), "suggestions": suggestions}


@api_router.get("/inventory/forecast")
async def inventory_forecast(
    days: int = 7,
    user: dict = Depends(get_current_user),
):
    await validate_shop_access(user, user.get("shop_id"))
    products = await db.products.find({"shop_id": user["shop_id"]}, {"_id": 0}).to_list(5000)
    forecasts = []
    for product in products:
        trend = await forecast_demand(product_id=product["id"], shop_id=user["shop_id"], days=max(days, 1))
        days_until_stockout = trend.get("days_until_stockout")
        if days_until_stockout is None:
            status = "safe"
        elif days_until_stockout < 2:
            status = "critical"
        elif days_until_stockout < 5:
            status = "warning"
        else:
            status = "safe"
        forecasts.append(
            {
                "product_id": product.get("id"),
                "name": product.get("name"),
                "current_stock": int(product.get("stock_quantity", 0) or 0),
                "predicted_demand_7d": trend.get("forecast_7d", 0.0),
                "days_until_stockout": days_until_stockout,
                "status": status,
            }
        )
    return forecasts


@api_router.get("/inventory/forecast/alerts")
async def inventory_forecast_alerts(
    days: int = 7,
    user: dict = Depends(get_current_user),
):
    forecasts = await inventory_forecast(days=days, user=user)
    alerts = [row for row in forecasts if row.get("status") in {"critical", "warning"}]
    return {"count": len(alerts), "alerts": alerts}
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

    active_shop_id = get_active_shop_id(owner)
    if not active_shop_id:
        raise HTTPException(status_code=400, detail="shop_id is required")

    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "phone": data.phone,
        "pin_hash": hash_pin(data.pin),
        "name": data.name,
        "role": "shopkeeper",  # Always shopkeeper when created by owner
        "shop_id": active_shop_id,
        "shop_ids": [active_shop_id],
        "default_shop_id": active_shop_id,
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
        shop_id=active_shop_id,
        shop_ids=[active_shop_id],
        subscription_status="active",
        created_at=user["created_at"],
    )


@api_router.get("/users", response_model=List[UserResponse])
async def list_users(owner: dict = Depends(require_owner)):
    """List all users in the shop"""
    active_shop_id = get_active_shop_id(owner)
    users = await db.users.find(
        {"shop_id": active_shop_id}, {"_id": 0, "pin_hash": 0}
    ).to_list(100)
    all_users = await db.users.find({}, {"_id": 0, "pin_hash": 0}).to_list(1000)
    seen_ids = {u.get("id") for u in users}
    for candidate in all_users:
        candidate_shop_ids = [sid for sid in (candidate.get("shop_ids") or []) if sid]
        if active_shop_id in candidate_shop_ids and candidate.get("id") not in seen_ids:
            users.append(candidate)
            seen_ids.add(candidate.get("id"))
    return [UserResponse(**u) for u in users]


@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, owner: dict = Depends(require_owner)):
    """Delete a shopkeeper (owner only)"""
    active_shop_id = get_active_shop_id(owner)
    user = await db.users.find_one(
        {"id": user_id, "shop_id": active_shop_id}, {"_id": 0}
    )
    if not user:
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if user:
            candidate_shop_ids = [sid for sid in (user.get("shop_ids") or []) if sid]
            if active_shop_id not in candidate_shop_ids:
                user = None
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user["role"] == "owner":
        raise HTTPException(status_code=400, detail="Cannot delete owner")

    await db.users.delete_one({"id": user_id})
    await write_audit_log(active_shop_id, owner["id"], "delete", "user", user_id)
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


@api_router.get("/reports/top-products")
async def get_top_products_insight(
    period: str = "today",
    limit: int = 10,
    user: dict = Depends(get_current_user),
):
    start_iso, end_iso = resolve_period_range(period)
    safe_limit = max(1, min(limit, 50))
    pipeline = [
        {
            "$match": {
                "shop_id": user["shop_id"],
                "created_at": {"$gte": start_iso, "$lte": end_iso},
            }
        },
        {
            "$group": {
                "_id": "$product_id",
                "product_name": {"$first": "$product_name"},
                "units_sold": {"$sum": "$quantity"},
                "revenue": {"$sum": "$total"},
            }
        },
        {"$sort": {"units_sold": -1, "revenue": -1}},
        {"$limit": safe_limit},
    ]
    items = await db.order_items.aggregate(pipeline).to_list(safe_limit)
    return {"period": period, "top_products": items}


@api_router.get("/reports/sales-trends")
async def get_sales_trends(
    period: str = "week",
    user: dict = Depends(get_current_user),
):
    start_iso, end_iso = resolve_period_range(period)
    sales_match = {
        "shop_id": user["shop_id"],
        "created_at": {"$gte": start_iso, "$lte": end_iso},
    }
    by_hour_pipeline = [
        {"$match": sales_match},
        {"$project": {"hour": {"$substr": ["$created_at", 11, 2]}, "total_amount": 1}},
        {"$group": {"_id": "$hour", "total_sales": {"$sum": "$total_amount"}, "total_orders": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    by_day_pipeline = [
        {"$match": sales_match},
        {"$project": {"day": {"$substr": ["$created_at", 0, 10]}, "total_amount": 1}},
        {"$group": {"_id": "$day", "total_sales": {"$sum": "$total_amount"}, "total_orders": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    sales_by_hour = await db.sales.aggregate(by_hour_pipeline).to_list(48)
    sales_by_day = await db.sales.aggregate(by_day_pipeline).to_list(90)
    return {"period": period, "sales_by_hour": sales_by_hour, "sales_by_day": sales_by_day}


@api_router.get("/reports/insights")
async def get_report_insights(
    period: str = "today",
    user: dict = Depends(get_current_user),
):
    start_iso, end_iso = resolve_period_range(period)
    sales_pipeline = [
        {
            "$match": {
                "shop_id": user["shop_id"],
                "created_at": {"$gte": start_iso, "$lte": end_iso},
            }
        },
        {"$group": {"_id": None, "total_sales": {"$sum": "$total_amount"}, "total_orders": {"$sum": 1}}},
    ]
    totals = await db.sales.aggregate(sales_pipeline).to_list(1)
    sales_totals = totals[0] if totals else {"total_sales": 0.0, "total_orders": 0}
    top_products = await get_top_products_insight(period=period, limit=5, user=user)
    trends = await get_sales_trends(period=period, user=user)
    total_sales = float(sales_totals.get("total_sales", 0.0) or 0.0)
    total_orders = int(sales_totals.get("total_orders", 0) or 0)
    return {
        "period": period,
        "total_sales": total_sales,
        "total_orders": total_orders,
        "average_order_value": (total_sales / total_orders) if total_orders else 0.0,
        "top_products": top_products.get("top_products", []),
        "sales_by_hour": trends.get("sales_by_hour", []),
        "sales_by_day": trends.get("sales_by_day", []),
    }


@api_router.get("/dashboard/vendor")
async def get_vendor_dashboard_compat(user: dict = Depends(get_current_user)):
    """Backward-compatible alias used by legacy frontend dashboards."""
    return await get_dashboard_stats(user)


@api_router.get("/dashboard/admin")
async def get_admin_dashboard_compat(user: dict = Depends(get_current_user)):
    """Backward-compatible alias used by legacy frontend dashboards."""
    return await get_dashboard_stats(user)


@api_router.get("/payments/providers/compare")
async def get_payment_providers_compare(user: dict = Depends(get_current_user)):
    """Return simple provider totals for dashboards expecting compare data."""
    payments = await db.payments.find({"shop_id": user["shop_id"]}, {"_id": 0}).to_list(5000)
    by_method: dict[str, float] = {}
    by_status: dict[str, int] = {}
    for payment in payments:
        method = str(payment.get("method") or "unknown").lower()
        status = str(payment.get("status") or "unknown").lower()
        amount = float(payment.get("amount") or 0)
        by_method[method] = by_method.get(method, 0.0) + amount
        by_status[status] = by_status.get(status, 0) + 1
    return {"by_method": by_method, "by_status": by_status, "count": len(payments)}


@api_router.get("/dashboard/summary")
async def get_dashboard_summary(user: dict = Depends(get_current_user)):
    start_iso, end_iso = resolve_period_range("today")
    sales = await db.sales.find(
        {"shop_id": user["shop_id"], "created_at": {"$gte": start_iso, "$lte": end_iso}},
        {"_id": 0},
    ).to_list(5000)
    orders_today = await db.orders.count_documents({"shop_id": user["shop_id"], "created_at": {"$gte": start_iso, "$lte": end_iso}})
    low_stock_count = await db.products.count_documents(
        {"shop_id": user["shop_id"], "$expr": {"$lte": ["$stock_quantity", "$min_stock_level"]}}
    )
    forecast_rows = await inventory_forecast(days=7, user=user)
    predicted_stockouts = [row for row in forecast_rows if row.get("days_until_stockout") is not None and row.get("days_until_stockout") < 5]
    critical_stock_count = len([row for row in forecast_rows if row.get("status") == "critical"])
    purchase_need_rows = await _compute_auto_purchase_suggestions(user["shop_id"], days=7)
    estimated_spend = round(sum(_safe_float(row.get("estimated_cost"), 0.0) for row in purchase_need_rows), 2)
    inventory_health = await compute_inventory_health(user["shop_id"])
    top_product_data = await get_top_products_insight(period="today", limit=1, user=user)
    top_product = (top_product_data.get("top_products") or [{}])[0]
    return {
        "sales_today": float(sum(float(s.get("total_amount", 0.0) or 0.0) for s in sales)),
        "orders_today": int(orders_today),
        "low_stock_count": int(low_stock_count),
        "top_product": top_product,
        "inventory_health_score": inventory_health.get("health_score", 0),
        "inventory_health_status": inventory_health.get("status", "warning"),
        "critical_stock_count": critical_stock_count,
        "predicted_stockouts": predicted_stockouts,
        "predicted_purchase_needs": purchase_need_rows,
        "estimated_restock_spend": estimated_spend,
        "forecast_observability": FORECAST_OBSERVABILITY,
        "auto_purchase_observability": AUTO_PURCHASE_OBSERVABILITY,
        "social_commerce_observability": SOCIAL_COMMERCE_OBSERVABILITY,
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


@api_router.get("/suppliers/recommended")
async def recommended_suppliers(
    limit: int = 5,
    user: dict = Depends(get_current_user),
):
    safe_limit = max(1, min(limit, 20))
    ranked = await _supplier_rankings(user["shop_id"])
    recommended = [
        {
            "supplier_id": row.get("supplier_id"),
            "name": row.get("name"),
            "purchase_count": int(row.get("purchase_count", 0) or 0),
            "average_fulfillment_rate": float(row.get("average_fulfillment_rate", 1.0) or 1.0),
            "reliability_score": float(row.get("reliability_score", 0.0) or 0.0),
            "cost_efficiency": float(row.get("cost_efficiency", 0.0) or 0.0),
            "avg_arrival_days": float(row.get("avg_arrival_days", row.get("lead_time_days", 3)) or 3.0),
            "lead_time_days": int(row.get("lead_time_days", 3) or 3),
            "total_spend": round(float(row.get("total_spend", 0.0) or 0.0), 2),
        }
        for row in ranked[:safe_limit]
    ]
    return {"recommended": recommended}


# =============================================================================
# PURCHASE ROUTES
# =============================================================================


@api_router.post("/purchases", response_model=PurchaseResponse)
async def create_purchase(data: PurchaseCreate, user: dict = Depends(get_current_user)):
    """Create a purchase order and update stock quantities"""
    now = datetime.now(timezone.utc).isoformat()
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0}) or {}
    check_shop_subscription(shop)

    payload_items: List[PurchaseItem] = list(data.items or [])
    supplier_id = data.supplier_id
    if data.use_auto_suggestions:
        suggestions = await _compute_auto_purchase_suggestions(user["shop_id"], days=7)
        if data.product_ids:
            wanted_ids = set(data.product_ids)
            suggestions = [row for row in suggestions if row.get("product_id") in wanted_ids]
        if not suggestions:
            raise HTTPException(status_code=400, detail="No auto purchase suggestions available")
        if not supplier_id:
            supplier_id = suggestions[0].get("preferred_supplier_id")
        payload_items = []
        for row in suggestions:
            product = await db.products.find_one(
                {"id": row["product_id"], "shop_id": user["shop_id"]},
                {"_id": 0},
            )
            if not product:
                continue
            quantity = max(1, _safe_int(row.get("recommended_quantity"), 1))
            unit_cost = _safe_float(product.get("cost_price"), 0.0)
            payload_items.append(
                PurchaseItem(
                    product_id=row["product_id"],
                    product_name=product.get("name", "Unknown Product"),
                    quantity=quantity,
                    unit_type="units",
                    units_per_package=1,
                    cost=round(quantity * unit_cost, 2),
                )
            )

    if not supplier_id:
        raise HTTPException(status_code=400, detail="supplier_id is required")
    if not payload_items:
        raise HTTPException(status_code=400, detail="items are required")
    # Get supplier info
    supplier = await db.suppliers.find_one(
        {"id": supplier_id, "shop_id": user["shop_id"]}, {"_id": 0}
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    lead_time_days = max(1, _safe_int(supplier.get("lead_time_days"), 3))
    deterministic_ref = _build_po_reference(
        user["shop_id"], supplier_id, [item.product_id for item in payload_items], datetime.now(timezone.utc)
    )
    existing_auto_po = await db.purchases.find_one(
        {"shop_id": user["shop_id"], "purchase_number": deterministic_ref, "is_auto_generated": True},
        {"_id": 0},
    )
    if existing_auto_po:
        return PurchaseResponse(**existing_auto_po)

    split_purchase_records: List[dict] = []
    if data.use_auto_suggestions:
        ranked_suppliers = await _supplier_rankings(user["shop_id"])
        supplier_by_id = {
            row["supplier_id"]: await db.suppliers.find_one({"id": row["supplier_id"], "shop_id": user["shop_id"]}, {"_id": 0})
            for row in ranked_suppliers
        }
        remaining_by_product = {item.product_id: item.quantity for item in payload_items}
        split_allocations: Dict[str, List[PurchaseItem]] = {}
        for row in ranked_suppliers:
            sid = row["supplier_id"]
            supplier_doc = supplier_by_id.get(sid) or {}
            product_stock = supplier_doc.get("product_stock") or {}
            allocation: List[PurchaseItem] = []
            for item in payload_items:
                remaining_qty = max(0, _safe_int(remaining_by_product.get(item.product_id), 0))
                if remaining_qty <= 0:
                    continue
                available_qty = max(0, _safe_int(product_stock.get(item.product_id), remaining_qty if sid == supplier_id else 0))
                take_qty = min(remaining_qty, available_qty) if available_qty > 0 else (remaining_qty if sid == supplier_id else 0)
                if take_qty <= 0:
                    continue
                remaining_by_product[item.product_id] = remaining_qty - take_qty
                unit_cost = _safe_float(item.cost, 0.0) / max(1, item.quantity)
                allocation.append(
                    PurchaseItem(
                        product_id=item.product_id,
                        product_name=item.product_name,
                        quantity=take_qty,
                        unit_type=item.unit_type,
                        units_per_package=item.units_per_package,
                        cost=round(unit_cost * take_qty, 2),
                    )
                )
            if allocation:
                split_allocations[sid] = allocation
        if split_allocations:
            payload_items = split_allocations.get(supplier_id, payload_items)
            for sid, split_items in split_allocations.items():
                if sid == supplier_id:
                    continue
                split_supplier = supplier_by_id.get(sid) or {}
                split_number = _build_po_reference(
                    user["shop_id"], sid, [it.product_id for it in split_items], datetime.now(timezone.utc)
                )
                exists = await db.purchases.find_one(
                    {"shop_id": user["shop_id"], "purchase_number": split_number, "is_auto_generated": True},
                    {"_id": 0},
                )
                if exists:
                    continue
                split_purchase_records.append(
                    {
                        "id": str(uuid.uuid4()),
                        "purchase_number": split_number,
                        "supplier_id": sid,
                        "supplier_name": split_supplier.get("name", sid),
                        "items": [it.model_dump() for it in split_items],
                        "total_cost": round(sum(_safe_float(it.cost, 0.0) for it in split_items), 2),
                        "estimated_arrival_days": max(1, _safe_int(split_supplier.get("lead_time_days"), 3)),
                        "is_auto_generated": True,
                        "notes": "Auto-generated split PO for partial supplier stock coverage",
                        "shop_id": user["shop_id"],
                        "created_by": user["id"],
                        "created_at": now,
                    }
                )

    # Update stock for each item
    computed_total_cost = 0.0
    for item in payload_items:
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
        computed_total_cost += _safe_float(item.cost, 0.0)
        await db.products.update_one(
            {"id": item.product_id, "shop_id": user["shop_id"]},
            {
                "$inc": {"stock_quantity": total_units},
                "$set": {"cost_price": cost_per_unit, "updated_at": now},
            },
        )

    purchase = {
        "id": str(uuid.uuid4()),
        "purchase_number": deterministic_ref if data.use_auto_suggestions else generate_purchase_number(),
        "supplier_id": supplier_id,
        "supplier_name": supplier["name"],
        "items": [item.model_dump() for item in payload_items],
        "total_cost": round(_safe_float(data.total_cost, 0.0) or computed_total_cost, 2),
        "estimated_arrival_days": lead_time_days,
        "is_auto_generated": bool(data.use_auto_suggestions),
        "notes": data.notes,
        "shop_id": user["shop_id"],
        "created_by": user["id"],
        "created_at": now,
    }

    await db.purchases.insert_one(purchase)
    if split_purchase_records:
        await db.purchases.insert_many(split_purchase_records)
    return PurchaseResponse(**purchase)


@api_router.get("/purchases/auto-suggestions")
async def auto_purchase_suggestions(
    days: int = 7,
    user: dict = Depends(get_current_user),
):
    await validate_shop_access(user, user.get("shop_id"))
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0}) or {}
    check_shop_subscription(shop)
    suggestions = await _compute_auto_purchase_suggestions(user["shop_id"], days=max(days, 1))
    return suggestions


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


@api_router.get("/purchases/stats/summary")
async def get_purchases_summary(user: dict = Depends(get_current_user)):
    """Get purchase statistics"""
    shop_id = user["shop_id"]
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    today_purchases = await db.purchases.find(
        {"shop_id": shop_id, "created_at": {"$gte": today.isoformat()}}, {"_id": 0}
    ).to_list(1000)
    today_total = sum(float(p.get("total_cost", 0.0) or 0.0) for p in today_purchases)
    supplier_count = await db.suppliers.count_documents({"shop_id": shop_id})
    month_start = today.replace(day=1)
    month_purchases = await db.purchases.find(
        {"shop_id": shop_id, "created_at": {"$gte": month_start.isoformat()}},
        {"_id": 0},
    ).to_list(10000)
    month_total = sum(float(p.get("total_cost", 0.0) or 0.0) for p in month_purchases)
    supplier_summary = {}
    for row in month_purchases:
        sid = row.get("supplier_id")
        if not sid:
            continue
        supplier_summary[sid] = supplier_summary.get(sid, 0.0) + float(row.get("total_cost", 0.0) or 0.0)
    return {
        "today_purchases": len(today_purchases),
        "today_total": round(today_total, 2),
        "month_total": round(month_total, 2),
        "supplier_count": supplier_count,
        "supplier_spend": supplier_summary,
    }


@api_router.get("/purchases/{purchase_id}", response_model=PurchaseResponse)
@api_router.get("/purchases/id/{purchase_id}", response_model=PurchaseResponse)
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


@api_router.get("/purchases/suggestions")
async def purchase_suggestions(
    period_days: int = 30,
    user: dict = Depends(get_current_user),
):
    velocity = await compute_sales_velocity(user["shop_id"], days=max(period_days, 1))
    products = await db.products.find({"shop_id": user["shop_id"]}, {"_id": 0}).to_list(5000)
    purchase_history = await db.purchases.find({"shop_id": user["shop_id"]}, {"_id": 0}).sort("created_at", -1).to_list(5000)

    product_last_cost = {}
    product_supplier = {}
    for purchase in purchase_history:
        supplier_id = purchase.get("supplier_id")
        supplier = await db.suppliers.find_one({"id": supplier_id, "shop_id": user["shop_id"]}, {"_id": 0})
        for item in purchase.get("items", []):
            product_id = item.get("product_id")
            if product_id and product_id not in product_last_cost:
                product_last_cost[product_id] = float(item.get("cost", 0.0) or 0.0)
                product_supplier[product_id] = supplier.get("name") if supplier else supplier_id

    suggestions = []
    for product in products:
        velocity_value = float(velocity.get(product.get("id"), product.get("sales_velocity", 0.0)) or 0.0)
        min_stock = int(product.get("min_stock_level", 0) or 0)
        stock = int(product.get("stock_quantity", 0) or 0)
        if stock > min_stock and velocity_value < 1.0:
            continue
        reorder_qty = max(min_stock - stock, int(round(velocity_value * 14)))
        if reorder_qty <= 0:
            continue
        unit_cost = float(product_last_cost.get(product.get("id"), product.get("cost_price", 0.0)) or 0.0)
        suggestions.append(
            {
                "supplier": product_supplier.get(product.get("id"), "Unassigned Supplier"),
                "product_id": product.get("id"),
                "product_name": product.get("name"),
                "recommended_quantity": reorder_qty,
                "estimated_cost": round(reorder_qty * unit_cost, 2),
            }
        )

    return {"suggestions": suggestions}


@api_router.get("/marketplace/vendors")
async def list_marketplace_vendors_compat(user: dict = Depends(get_current_user)):
    """Compatibility alias for supplier list used by older marketplace pages."""
    return await list_suppliers(user=user)


@api_router.get("/marketplace/orders")
async def list_marketplace_orders_compat(user: dict = Depends(get_current_user)):
    """Compatibility alias for purchase list used by older marketplace pages."""
    return await list_purchases(user=user)


@api_router.post("/marketplace/orders")
async def create_marketplace_order_compat(data: dict, user: dict = Depends(get_current_user)):
    """Compatibility wrapper that maps marketplace purchase payloads to purchases API."""
    supplier_id = data.get("supplier_id")
    items = data.get("items") or []
    if not supplier_id or not isinstance(items, list) or len(items) == 0:
        raise HTTPException(status_code=400, detail="supplier_id and items are required")

    normalized_items = []
    total_cost = 0.0
    for raw in items:
        quantity = int(raw.get("quantity", 0) or 0)
        units_per_package = int(raw.get("units_per_package", 1) or 1)
        cost = float(raw.get("cost", 0) or 0)
        normalized = PurchaseItem(
            product_id=str(raw.get("product_id") or ""),
            product_name=str(raw.get("product_name") or "Unknown Product"),
            quantity=max(quantity, 1),
            unit_type=str(raw.get("unit_type") or "units"),
            units_per_package=max(units_per_package, 1),
            cost=max(cost, 0.0),
        )
        normalized_items.append(normalized)
        total_cost += normalized.cost

    purchase = PurchaseCreate(
        supplier_id=str(supplier_id),
        items=normalized_items,
        total_cost=float(data.get("total_cost") or total_cost),
        notes=data.get("notes"),
    )
    return await create_purchase(purchase, user)


@api_router.post("/marketplace/orders/{order_id}/receive")
async def receive_marketplace_order_compat(
    order_id: str,
    payload: dict,
    user: dict = Depends(get_current_user),
):
    """Compatibility endpoint to mark a purchase/marketplace order as received."""
    purchase = await db.purchases.find_one(
        {"id": order_id, "shop_id": user["shop_id"]},
        {"_id": 0},
    )
    if not purchase:
        raise HTTPException(status_code=404, detail="Marketplace order not found")

    status = str(payload.get("status") or "received")
    now = datetime.now(timezone.utc).isoformat()
    await db.purchases.update_one(
        {"id": order_id, "shop_id": user["shop_id"]},
        {"$set": {"status": status, "received_at": now}},
    )
    return {"id": order_id, "status": status, "received_at": now}


# =============================================================================
# SHOP SETTINGS
# =============================================================================


@api_router.get("/shop")
async def get_shop(user: dict = Depends(get_current_user)):
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    shop["subscription"] = normalize_shop_subscription(shop)
    return shop


@api_router.put("/shop")
async def update_shop(data: dict, owner: dict = Depends(require_owner)):
    allowed_fields = ["name", "address", "phone", "email"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    subscription_payload = data.get("subscription") if isinstance(data.get("subscription"), dict) else None
    if subscription_payload:
        shop = await db.shops.find_one({"id": owner["shop_id"]}, {"_id": 0}) or {}
        current_subscription = normalize_shop_subscription(shop)
        plan = subscription_payload.get("plan", current_subscription["plan"])
        status = subscription_payload.get("status", current_subscription["status"])
        expires_at = subscription_payload.get("expires_at", current_subscription["expires_at"])

        if plan not in {"pos", "online"}:
            raise HTTPException(status_code=400, detail="Invalid subscription plan")
        if status not in {"active", "expired"}:
            raise HTTPException(status_code=400, detail="Invalid subscription status")
        if plan == "online" and status == "expired":
            raise HTTPException(
                status_code=400,
                detail="Invalid subscription combination: online plan cannot be expired",
            )
        update_data["subscription"] = {
            "plan": plan,
            "status": status,
            "expires_at": expires_at,
        }

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
    if shop:
        shop["subscription"] = normalize_shop_subscription(shop)
    return shop


@api_router.get("/shops/{shop_id}/product-feed")
async def shop_product_feed(shop_id: str):
    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    products = await db.products.find(
        {"shop_id": shop_id, "is_active": True},
        {"_id": 0},
    ).to_list(10000)
    return {
        "shop_id": shop_id,
        "shop_name": shop.get("name"),
        "products": [
            {
                "id": product.get("id"),
                "name": product.get("name"),
                "price": float(product.get("unit_price", 0)),
                "availability": "in stock" if int(product.get("stock_quantity", 0)) > 0 else "out of stock",
                "category": product.get("category"),
                "image_url": product.get("image_url"),
            }
            for product in products
        ],
    }


@api_router.get("/rider/me")
async def rider_me(rider: dict = Depends(require_rider)):
    return {
        "id": rider.get("id"),
        "name": rider.get("name"),
        "phone": rider.get("phone"),
        "status": rider.get("status", "available"),
        "is_available": rider.get("is_available", True),
        "current_location": rider.get("current_location"),
    }


@api_router.get("/rider/orders")
async def rider_orders(
    limit: Optional[int] = None,
    offset: int = 0,
    rider: dict = Depends(require_rider),
):
    safe_limit, safe_offset = normalize_limit_offset(limit, offset, default_limit=50, max_limit=200)
    deliveries = await db.deliveries.find({"rider_id": rider["id"]}, {"_id": 0}).sort("created_at", -1).skip(safe_offset).limit(safe_limit).to_list(safe_limit)
    return {"data": deliveries, "pagination": {"limit": safe_limit, "offset": safe_offset, "total": len(deliveries)}}


@api_router.patch("/rider/orders/{delivery_id}/status")
async def rider_update_order_status(
    delivery_id: str,
    data: RiderOrderStatusPatch,
    rider: dict = Depends(require_rider),
):
    delivery = await db.deliveries.find_one({"id": delivery_id, "rider_id": rider["id"]}, {"_id": 0})
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    status_map = {
        "on_delivery": {"delivery_status": "on_delivery", "rider_status": "on_delivery", "is_available": False},
        "completed": {"delivery_status": "delivered", "rider_status": "available", "is_available": True},
    }
    mapped = status_map[data.status]
    await db.deliveries.update_one(
        {"id": delivery_id, "rider_id": rider["id"]},
        {"$set": {"status": mapped["delivery_status"], "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.users.update_one(
        {"id": rider["id"]},
        {"$set": {"status": mapped["rider_status"], "is_available": mapped["is_available"]}},
    )
    updated = await db.deliveries.find_one({"id": delivery_id, "rider_id": rider["id"]}, {"_id": 0})
    return {"delivery": updated, "rider_status": mapped["rider_status"]}


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
    invalid_item_ids: List[str] = []
    for item in items:
        shop = await db.shops.find_one({"id": item["shop_id"]}, {"_id": 0})
        if not shop:
            invalid_item_ids.append(item["id"])
            continue
        product = await db.products.find_one(
            {"id": item["product_id"], "shop_id": item["shop_id"]},
            {"_id": 0},
        )
        if not product or not product.get("is_active", True):
            invalid_item_ids.append(item["id"])
            continue
        response_items.append(build_customer_cart_item_response(item, product))
    if invalid_item_ids:
        await db.customer_cart.delete_many(
            {"user_id": customer["id"], "id": {"$in": invalid_item_ids}}
        )
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
    shop = await db.shops.find_one({"id": item["shop_id"]}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

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
    data.payment_method = validate_checkout_payment_method(data.payment_method)
    idem_key = request.headers.get("Idempotency-Key")
    idem_state = await begin_checkout_idempotency(customer["id"], idem_key)
    if idem_state.get("state") == "completed":
        return idem_state["response"]
    if idem_state.get("state") == "processing":
        raise HTTPException(status_code=409, detail="Checkout already in progress")

    logger.info("Checkout start flow=customer user_id=%s", customer["id"])

    customer_items = await db.customer_cart.find({"user_id": customer["id"]}, {"_id": 0}).to_list(1000)
    if not customer_items:
        raise HTTPException(status_code=400, detail="Customer cart is empty")

    shop_ids = {item["shop_id"] for item in customer_items}
    if len(shop_ids) != 1:
        raise HTTPException(status_code=400, detail="Customer cart must contain items from one shop")
    checkout_shop_id = next(iter(shop_ids))
    checkout_shop = await db.shops.find_one({"id": checkout_shop_id}, {"_id": 0})
    if not checkout_shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    check_shop_subscription(checkout_shop, required_feature="online")

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
        {"id": cart_id, "user_id": customer["id"], "shop_id": checkout_shop_id},
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
        await mark_checkout_idempotency_failed(customer["id"], idem_key)
        logger.exception("Checkout failure flow=customer user_id=%s", customer["id"])
        raise

    await db.orders.update_one(
        {"id": checkout_result.id, "shop_id": checkout_shop_id},
        {"$set": {"source": "customer_app"}},
    )

    await initialize_order_lifecycle(checkout_result.id, checkout_shop_id)
    await db.customer_cart.delete_many(
        {"user_id": customer["id"], "shop_id": checkout_shop_id}
    )
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
    order_shop_ids = [order.get("shop_id") for order in orders if order.get("shop_id")]

    order_items_query = {"order_id": {"$in": order_ids}}
    payments_query = {"order_id": {"$in": order_ids}}
    if order_shop_ids:
        order_items_query["shop_id"] = {"$in": order_shop_ids}
        payments_query["shop_id"] = {"$in": order_shop_ids}

    order_items_list = await db.order_items.find(order_items_query, {"_id": 0}).to_list(5000)
    payments_list = await db.payments.find(payments_query, {"_id": 0}).to_list(5000)

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

    order_items = await db.order_items.find(
        {"order_id": order["id"], "shop_id": order.get("shop_id")},
        {"_id": 0},
    ).to_list(1000)
    payment = await db.payments.find_one(
        {"order_id": order["id"], "shop_id": order.get("shop_id")},
        {"_id": 0},
    )
    return build_customer_order_response(order, order_items, payment)


@api_router.get("/customer/recommendations")
async def customer_recommendations(customer: dict = Depends(require_customer)):
    location = customer.get("current_location") or {}
    if "lat" not in location or "lng" not in location:
        raise HTTPException(status_code=400, detail="Customer location is required for recommendations")

    recommendation_doc = await db.shop_recommendations.find_one(
        {"for_customer_id": customer["id"]},
        {"_id": 0},
    )
    ranked = []
    if recommendation_doc and recommendation_doc.get("nearby_shop_ids"):
        shops = await db.shops.find(
            {"id": {"$in": recommendation_doc["nearby_shop_ids"]}, "is_active": True},
            {"_id": 0},
        ).to_list(200)
        index_map = {shop_id: idx for idx, shop_id in enumerate(recommendation_doc["nearby_shop_ids"])}
        ranked = sorted(shops, key=lambda shop: index_map.get(shop.get("id"), 9999))
    else:
        shops = await db.shops.find({"is_active": True}, {"_id": 0}).to_list(500)
        for shop in shops:
            shop_loc = shop.get("location") or {}
            if "lat" not in shop_loc or "lng" not in shop_loc:
                continue
            ranked.append(
                {
                    **shop,
                    "_distance_km": distance_km(
                        float(location["lat"]),
                        float(location["lng"]),
                        float(shop_loc["lat"]),
                        float(shop_loc["lng"]),
                    ),
                }
            )
        ranked = sorted(ranked, key=lambda item: item.get("_distance_km", 10**6))

    response = []
    for shop in ranked[:10]:
        shop_loc = shop.get("location") or {}
        dist = shop.get("_distance_km")
        if dist is None and "lat" in shop_loc and "lng" in shop_loc:
            dist = distance_km(
                float(location["lat"]),
                float(location["lng"]),
                float(shop_loc["lat"]),
                float(shop_loc["lng"]),
            )
        response.append(
            {
                "shop_id": shop.get("id"),
                "shop_name": shop.get("name"),
                "distance_km": round(float(dist), 3) if dist is not None else None,
                "location": shop.get("location"),
            }
        )

    logger.info("recommendation_served customer_id=%s count=%s", customer["id"], len(response))
    return {"customer_id": customer["id"], "recommendations": response}




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
        {"id": cart["id"], "user_id": user["id"], "shop_id": user["shop_id"]},
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
        {"id": cart["id"], "user_id": user["id"], "shop_id": user["shop_id"]},
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
        {"id": cart["id"], "user_id": user["id"], "shop_id": user["shop_id"]},
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
    data.payment_method = validate_checkout_payment_method(data.payment_method)
    idem_key = request.headers.get("Idempotency-Key")
    idem_state = await begin_checkout_idempotency(user["id"], idem_key)
    if idem_state.get("state") == "completed":
        return idem_state["response"]
    if idem_state.get("state") == "processing":
        raise HTTPException(status_code=409, detail="Checkout already in progress")

    logger.info("Checkout start flow=pos user_id=%s shop_id=%s", user["id"], user.get("shop_id"))
    try:
        result = await checkout_cart(data, user)
    except Exception:
        await mark_checkout_idempotency_failed(user["id"], idem_key)
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
    # SINGLE SOURCE OF TRUTH:
    # Orders and payments are created ONLY in checkout_cart.
    payment_method = validate_checkout_payment_method(data.payment_method)
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
            "payment_method": payment_method,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.orders.insert_one(order, session=session)

        if payment_method == "credit":
            if not data.customer_id:
                raise HTTPException(status_code=400, detail="customer_id is required for credit checkout")
            await db.credit_customers.update_one(
                {"id": data.customer_id, "shop_id": user["shop_id"]},
                {"$inc": {"current_balance": total_amount}},
                session=session,
            )

        if payment_method == "credit":
            payment_status = "on_credit"
        elif payment_method == "mpesa":
            payment_status = "pending"
        else:
            payment_status = "successful"

        payment_doc = {
            "id": str(uuid.uuid4()),
            "order_id": order_id,
            "shop_id": user["shop_id"],
            "amount": total_amount,
            "method": payment_method,
            "status": payment_status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if abs(float(payment_doc["amount"]) - float(order["total_amount"])) > 1e-9:
            logger.error(
                "payment_amount_mismatch order_id=%s payment=%s order=%s",
                order_id,
                payment_doc["amount"],
                order["total_amount"],
            )
            raise HTTPException(status_code=500, detail="Payment amount mismatch")

        await db.payments.insert_one(
            {
                **payment_doc,
            },
            session=session,
        )

        # Clear POS cart only after successful order + payment creation
        await db.cart.update_one(
            {"id": cart["id"], "user_id": user["id"], "shop_id": user["shop_id"]},
            {"$set": {"items": [], "updated_at": datetime.now(timezone.utc).isoformat()}},
            session=session,
        )
        return CheckoutResponse(
            id=order["id"],
            total_amount=order["total_amount"],
            shop_id=order["shop_id"],
            status=order["status"],
            payment_status=payment_status,
            payment_method=payment_method,
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
        {"id": cart_id, "user_id": owner["id"], "shop_id": owner["shop_id"]},
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
            {"id": existing_cart["id"], "user_id": owner["id"], "shop_id": owner["shop_id"]},
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
            logger.error(
                "Missing payment for order_id during marketplace delivery order_id=%s shop_id=%s",
                order_id,
                owner["shop_id"],
            )
            raise HTTPException(
                status_code=409,
                detail="Missing payment for order during marketplace delivery",
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
        shop_id=product.get("shop_id"),
        name=product.get("name", ""),
        price=product.get("unit_price", 0),
        image_url=product.get("image_url"),
        description=product.get("description") or "",
        availability="in_stock" if product.get("stock_quantity", 0) > 0 else "out_of_stock",
    )


PUBLIC_MARKETPLACE_CATEGORIES = [
    {"id": "food", "name": "Food"},
    {"id": "groceries", "name": "Groceries"},
    {"id": "pharmacy", "name": "Pharmacy"},
    {"id": "electronics", "name": "Electronics"},
    {"id": "fashion", "name": "Fashion"},
    {"id": "other", "name": "Other"},
    {"id": "shops", "name": "Shops"},
]

VALID_CATEGORIES = [
    "food",
    "groceries",
    "pharmacy",
    "electronics",
    "fashion",
    "other",
]


def normalize_category(value: Optional[str]) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned in {"shop", "shops"}:
        return "other"
    if cleaned in VALID_CATEGORIES:
        return cleaned
    return "other"


async def track_marketplace_view(event_type: str, entity_id: Optional[str]):
    if not entity_id:
        return
    if not hasattr(db, "marketplace_metrics"):
        return
    try:
        await db.marketplace_metrics.update_one(
            {"event_type": event_type, "entity_id": entity_id},
            {
                "$inc": {"count": 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
                "$setOnInsert": {
                    "event_type": event_type,
                    "entity_id": entity_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            },
            upsert=True,
        )
    except Exception:
        logger.debug("marketplace view tracking unavailable for %s:%s", event_type, entity_id)


def to_public_store_view(shop: dict) -> PublicStoreResponse:
    return PublicStoreResponse(
        id=shop["id"],
        name=shop.get("name", ""),
        category=normalize_category(shop.get("category")),
    )


async def list_online_public_shops(
    limit: Optional[int] = None,
    offset: int = 0,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> List[dict]:
    safe_limit, safe_offset = normalize_limit_offset(
        limit, offset, default_limit=50, max_limit=100
    )
    candidate_limit = min(max(safe_offset + safe_limit, 200), 2000)
    shops = await db.shops.find({}, {"_id": 0}).limit(candidate_limit).to_list(candidate_limit)
    safe_category = safe_regex(category or "")
    safe_search = safe_regex(search or "")
    category_pattern = re.compile(safe_category, re.IGNORECASE) if safe_category else None
    name_pattern = re.compile(safe_search, re.IGNORECASE) if safe_search else None
    filtered = []
    for shop in shops:
        if not shop.get("is_active", True):
            continue
        try:
            check_shop_subscription(shop, required_feature="online")
        except HTTPException:
            continue
        if category_pattern and not category_pattern.search(str(shop.get("category") or "")):
            continue
        if name_pattern and not name_pattern.search(str(shop.get("name") or "")):
            continue
        filtered.append(shop)
    return filtered[safe_offset : safe_offset + safe_limit]


async def get_online_public_shop_map(
    *,
    category: Optional[str] = None,
) -> Dict[str, dict]:
    query: Dict[str, object] = {}
    safe_category = safe_regex(category or "")
    if safe_category:
        query["category"] = {"$regex": safe_category, "$options": "i"}
    shops = await db.shops.find(query, {"_id": 0}).to_list(5000)
    shop_map: Dict[str, dict] = {}
    for shop in shops:
        if not shop.get("is_active", True):
            continue
        try:
            check_shop_subscription(shop, required_feature="online")
        except HTTPException:
            continue
        sid = shop.get("id")
        if sid:
            shop_map[sid] = shop
    return shop_map


def dedupe_store_views(
    shops: List[dict],
    seen: Optional[set] = None,
    *,
    limit: int = 10,
) -> List[dict]:
    used = seen if seen is not None else set()
    views: List[dict] = []
    for shop in shops:
        sid = shop.get("id")
        if not sid or sid in used:
            continue
        views.append(to_public_store_view(shop).model_dump())
        used.add(sid)
        if len(views) >= limit:
            break
    return views


@api_router.get("/social/product-feed")
async def social_product_feed(
    format: str = "json",
    user: dict = Depends(get_current_user),
):
    """
    Build an export-friendly social catalog feed.
    Field mapping is intentionally explicit so platform-specific connectors
    (Meta/Facebook/Instagram/WhatsApp catalogs) can transform safely.
    """
    SOCIAL_COMMERCE_OBSERVABILITY["social_product_feed_requests"] += 1
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0}) or {}
    shop_slug = _shop_slug(shop)
    products = await db.products.find({"shop_id": user["shop_id"]}, {"_id": 0}).to_list(10000)
    feed = [_build_social_product_feed_item(product, shop_slug) for product in products]
    if (format or "json").lower() != "csv":
        return {
            "shop_id": user["shop_id"],
            "shop_slug": shop_slug,
            "count": len(feed),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": feed,
        }

    out = StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=[
            "product_id",
            "title",
            "description",
            "price",
            "availability",
            "image_url",
            "product_url",
            "category",
            "brand",
        ],
    )
    writer.writeheader()
    for item in feed:
        writer.writerow({k: item.get(k) for k in writer.fieldnames})
    return Response(content=out.getvalue(), media_type="text/csv")


@api_router.post("/integrations/whatsapp/order")
async def whatsapp_order_ingestion(
    payload: WhatsAppOrderIngestionRequest,
    user: dict = Depends(get_current_user),
):
    result = await _ingest_social_order(
        shop_id=user["shop_id"],
        channel="whatsapp",
        phone_number=payload.phone_number,
        line_items=[row.model_dump() for row in payload.product_ids],
        metadata=payload.metadata or {},
    )
    return result


async def _social_webhook_handler(channel: str, payload: dict, x_social_secret: Optional[str]) -> dict:
    configured_secret = os.environ.get("SOCIAL_WEBHOOK_SECRET")
    if configured_secret and x_social_secret != configured_secret:
        SOCIAL_COMMERCE_OBSERVABILITY["webhook_event_errors"] += 1
        raise HTTPException(status_code=401, detail="Invalid social webhook signature")

    shop_id = str(payload.get("shop_id") or "").strip()
    phone = str(payload.get("phone_number") or payload.get("customer_phone") or "unknown")
    line_items = payload.get("items") or payload.get("product_ids") or []
    metadata = payload.get("metadata") or {}
    if not shop_id:
        SOCIAL_COMMERCE_OBSERVABILITY["webhook_event_errors"] += 1
        raise HTTPException(status_code=400, detail="shop_id is required")
    try:
        return await _ingest_social_order(
            shop_id=shop_id,
            channel=channel,
            phone_number=phone,
            line_items=line_items,
            metadata=metadata,
        )
    except HTTPException:
        raise
    except Exception:
        SOCIAL_COMMERCE_OBSERVABILITY["webhook_event_errors"] += 1
        logger.exception("social_webhook_processing_failed channel=%s", channel)
        raise HTTPException(status_code=500, detail="Failed to process social webhook")


@api_router.post("/webhooks/social/facebook")
async def webhook_social_facebook(
    payload: dict = Body(default={}),
    x_social_secret: Optional[str] = Header(default=None),
):
    return await _social_webhook_handler("facebook", payload, x_social_secret)


@api_router.post("/webhooks/social/instagram")
async def webhook_social_instagram(
    payload: dict = Body(default={}),
    x_social_secret: Optional[str] = Header(default=None),
):
    return await _social_webhook_handler("instagram", payload, x_social_secret)


@api_router.post("/webhooks/social/whatsapp")
async def webhook_social_whatsapp(
    payload: dict = Body(default={}),
    x_social_secret: Optional[str] = Header(default=None),
):
    return await _social_webhook_handler("whatsapp", payload, x_social_secret)


@api_router.get("/public/storefront/{shop_slug}")
async def public_storefront(shop_slug: str):
    shops = await db.shops.find({}, {"_id": 0}).to_list(5000)
    shop = next((row for row in shops if _shop_slug(row) == shop_slug), None)
    if not shop or not shop.get("is_active", True):
        raise HTTPException(status_code=404, detail="Storefront not found")
    products = await db.products.find({"shop_id": shop["id"]}, {"_id": 0}).to_list(10000)
    return {
        "shop": {
            "id": shop.get("id"),
            "slug": shop_slug,
            "name": shop.get("name"),
            "description": shop.get("description") or "",
            "logo_url": shop.get("logo_url"),
        },
        "shareable_link": f"/public/storefront/{shop_slug}",
        "products": [to_public_product_view(product).model_dump() for product in products],
    }


@api_router.get("/public/storefront/{shop_slug}/product/{product_id}")
async def public_storefront_product(shop_slug: str, product_id: str):
    shops = await db.shops.find({}, {"_id": 0}).to_list(5000)
    shop = next((row for row in shops if _shop_slug(row) == shop_slug), None)
    if not shop or not shop.get("is_active", True):
        raise HTTPException(status_code=404, detail="Storefront not found")
    product = await db.products.find_one({"id": product_id, "shop_id": shop["id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "shop": {"id": shop.get("id"), "slug": shop_slug, "name": shop.get("name")},
        "product": to_public_product_view(product).model_dump(),
        "shareable_link": f"/public/storefront/{shop_slug}/product/{product_id}",
    }


@api_router.get("/public/categories")
async def public_list_categories():
    return PUBLIC_MARKETPLACE_CATEGORIES


@api_router.get("/public/home")
async def public_home():
    categories = PUBLIC_MARKETPLACE_CATEGORIES
    shops = await list_online_public_shops(limit=200, offset=0)
    shop_map = {shop["id"]: shop for shop in shops if shop.get("id")}
    shop_ids = list(shop_map.keys())

    order_stats: Dict[str, Dict[str, float]] = {
        sid: {"total_orders": 0, "total_revenue": 0.0, "popularity_score": 0.0}
        for sid in shop_ids
    }
    if shop_ids:
        pipeline = [
            {"$match": {"shop_id": {"$in": shop_ids}}},
            {
                "$group": {
                    "_id": "$shop_id",
                    "total_orders": {"$sum": 1},
                    "total_revenue": {"$sum": {"$ifNull": ["$total_amount", 0]}},
                }
            },
            {"$sort": {"total_orders": -1}},
            {"$limit": 1000},
        ]
        aggregate_cursor = db.orders.aggregate(pipeline)
        grouped = await aggregate_cursor.to_list(1000)
        for row in grouped:
            sid = row.get("_id")
            if sid in order_stats:
                total_orders = int(row.get("total_orders", 0) or 0)
                total_revenue = float(row.get("total_revenue", 0) or 0)
                order_stats[sid] = {
                    "total_orders": total_orders,
                    "total_revenue": total_revenue,
                    "popularity_score": float(total_orders),
                }

    featured_candidates = [shop for shop in shops if shop.get("is_featured", False)]
    if not featured_candidates:
        featured_candidates = sorted(
            shops,
            key=lambda shop: order_stats.get(shop["id"], {}).get("popularity_score", 0),
            reverse=True,
        )
    ranked_shop_ids = sorted(
        shop_ids,
        key=lambda sid: order_stats.get(sid, {}).get("popularity_score", 0),
        reverse=True,
    )
    popular_shops = [shop_map[sid] for sid in ranked_shop_ids if sid in shop_map]
    new_shops = sorted(shops, key=lambda shop: shop.get("created_at", ""), reverse=True)
    seen_ids: set = set()
    featured_views = dedupe_store_views(featured_candidates, seen_ids, limit=10)
    popular_views = dedupe_store_views(popular_shops, seen_ids, limit=10)
    new_views = dedupe_store_views(new_shops, seen_ids, limit=10)

    return {
        "categories": categories,
        "featured_stores": featured_views,
        "popular_stores": popular_views,
        "new_stores": new_views,
    }


@api_router.get("/public/stores", response_model=List[PublicStoreResponse])
async def public_list_stores(
    limit: Optional[int] = None,
    offset: int = 0,
    category: Optional[str] = None,
    search: Optional[str] = None,
):
    shops = await list_online_public_shops(
        limit=limit, offset=offset, category=category, search=search
    )
    return [to_public_store_view(shop) for shop in shops]


@api_router.get(
    "/public/stores/{shop_id}/products",
    response_model=List[PublicProductResponse],
)
async def public_list_store_products(shop_id: str, limit: Optional[int] = None, offset: int = 0):
    safe_limit, safe_offset = normalize_limit_offset(
        limit, offset, default_limit=50, max_limit=100
    )

    shop = await db.shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop or not shop.get("is_active", True):
        raise HTTPException(status_code=404, detail="Store not found")
    check_shop_subscription(shop, required_feature="online")

    products = (
        await db.products.find({"shop_id": shop_id}, {"_id": 0})
        .skip(safe_offset)
        .limit(safe_limit)
        .to_list(safe_limit)
    )

    active_products = [product for product in products if product.get("is_active", True)]
    await track_marketplace_view("store_view", shop_id)
    return [to_public_product_view(product) for product in active_products]



@api_router.get("/public/products", response_model=List[PublicProductResponse])
async def public_list_products(
    limit: Optional[int] = None,
    offset: int = 0,
    category: Optional[str] = None,
):
    safe_limit, safe_offset = normalize_limit_offset(
        limit, offset, default_limit=50, max_limit=100
    )
    shop_map = await get_online_public_shop_map(category=category)
    eligible_shop_ids = list(shop_map.keys())
    if not eligible_shop_ids:
        return []
    products = (
        await db.products.find(
            {"is_active": True, "shop_id": {"$in": eligible_shop_ids}},
            {"_id": 0},
        )
        .skip(safe_offset)
        .limit(safe_limit)
        .to_list(safe_limit)
    )
    return [to_public_product_view(product) for product in products]



@api_router.get("/public/products/search", response_model=List[PublicProductResponse])
async def public_search_products(
    q: str,
    limit: Optional[int] = None,
    offset: int = 0,
    category: Optional[str] = None,
):
    query_text = (q or "").strip()
    if not query_text:
        return []
    safe_limit, safe_offset = normalize_limit_offset(
        limit, offset, default_limit=50, max_limit=100
    )
    safe_query_text = safe_regex(query_text)
    if not safe_query_text:
        return []
    shop_map = await get_online_public_shop_map(category=category)
    eligible_shop_ids = list(shop_map.keys())
    if not eligible_shop_ids:
        return []
    terms = tokenize_search_terms(query_text)

    text_query = {
        "is_active": True,
        "shop_id": {"$in": eligible_shop_ids},
        "$text": {"$search": query_text},
    }
    text_projection = {"_id": 0, "score": {"$meta": "textScore"}}
    text_results = []
    try:
        text_results = (
            await db.products.find(text_query, text_projection)
            .sort("score", {"$meta": "textScore"})
            .skip(safe_offset)
            .limit(safe_limit)
            .to_list(safe_limit)
        )
    except Exception:
        text_results = []

    if text_results:
        return [to_public_product_view(product) for product in text_results]

    regex_query = {
        "is_active": True,
        "shop_id": {"$in": eligible_shop_ids},
        "$or": [
            {"name": {"$regex": safe_query_text, "$options": "i"}},
            {"description": {"$regex": safe_query_text, "$options": "i"}},
        ],
    }
    candidates = await db.products.find(regex_query, {"_id": 0}).to_list(1000)
    ranked_candidates = sorted(
        candidates,
        key=lambda product: compute_fallback_search_score(product, query_text, terms),
        reverse=True,
    )
    paged = ranked_candidates[safe_offset : safe_offset + safe_limit]
    return [to_public_product_view(product) for product in paged]


@api_router.get("/public/products/{product_id}", response_model=PublicProductResponse)
async def public_get_product(product_id: str):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product or not product.get("is_active", True):
        raise HTTPException(status_code=404, detail="Product not found")
    shop = await db.shops.find_one({"id": product.get("shop_id")}, {"_id": 0})
    if not shop or not shop.get("is_active", True):
        raise HTTPException(status_code=404, detail="Product not found")
    check_shop_subscription(shop, required_feature="online")
    await track_marketplace_view("product_view", product_id)
    return to_public_product_view(product)


# =============================================================================
# HEALTH CHECK
# =============================================================================


@api_router.get("/health")
async def health_check():
    return {"status": "ok"}


async def seed_data():
    """
    Seed baseline demo data if the database is empty.
    This function is idempotent and only seeds on first run.
    """
    logger.info("Seeding database...")
    await seed_realistic_async(db, hash_pin, logger)
    logger.info("Database seeded")


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
        if hasattr(client, "admin") and hasattr(client.admin, "command"):
            await client.admin.command("ping")
        await db.orders.create_index([("user_id", 1), ("created_at", -1)])
        await db.orders.create_index([("shop_id", 1), ("created_at", -1)])
        await db.orders.create_index([("lifecycle_status", 1), ("shop_id", 1)])
        await db.shops.create_index([("subscription.plan", 1), ("subscription.status", 1)])
        await db.shops.create_index([("is_active", 1), ("subscription.plan", 1), ("subscription.status", 1)])
        await db.products.create_index([("shop_id", 1), ("updated_at", -1)])
        await db.products.create_index([("shop_id", 1), ("is_active", 1)])
        await db.products.create_index([("name", "text"), ("description", "text")])
        await db.cart.create_index([("shop_id", 1), ("user_id", 1)])
        await db.payments.create_index([("shop_id", 1), ("created_at", -1)])
        await db.payments.create_index("reference", unique=True, sparse=True)
        await db.order_items.create_index("order_id")
        await db.customer_cart.create_index([("user_id", 1), ("shop_id", 1)])
        await seed_data()
    except Exception:
        logger.exception("Failed to ensure indexes")
        logger.error("MongoDB is not running. Please start MongoDB on localhost:27017")


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
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    check_shop_subscription(shop, required_feature="online")

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
    shop = await db.shops.find_one({"id": user["shop_id"]}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    check_shop_subscription(shop, required_feature="online")

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
