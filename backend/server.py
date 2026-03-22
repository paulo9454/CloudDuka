from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Response, Header, UploadFile, File, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import asyncio
import smtplib
import ssl
from io import BytesIO
from email.message import EmailMessage
from fpdf import FPDF
import base64
import os
from uuid import uuid4

from backend.config import settings

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
client = AsyncIOMotorClient(settings.mongo_url)
db = client[settings.db_name]

# JWT Configuration
JWT_SECRET = settings.jwt_secret
JWT_ALGORITHM = settings.jwt_algorithm
JWT_EXPIRATION_HOURS = settings.jwt_expiration_hours
REFRESH_TOKEN_EXPIRATION_DAYS = settings.refresh_token_expiration_days
EMAIL_VERIFICATION_EXPIRATION_HOURS = settings.email_verification_expiration_hours
MEDIA_PATH = settings.media_path
MEDIA_PATH.mkdir(parents=True, exist_ok=True)

# Create the main app
app = FastAPI(title=settings.app_name)
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
    email: Optional[EmailStr] = None
    role: str = "shopkeeper"  # owner or shopkeeper
    shop_name: Optional[str] = None

class UserLogin(BaseModel):
    phone: str
    pin: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class EmailVerificationRequest(BaseModel):
    token: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_pin: str = Field(min_length=4, max_length=10)

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    phone: str
    name: str
    role: str
    shop_id: str
    email: Optional[EmailStr] = None
    email_verified: bool = False
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
    image_url: Optional[str] = None

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
    image_url: Optional[str] = None
    shop_id: str
    created_at: str
    updated_at: str

class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)

class CartItemResponse(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total: float
    image_url: Optional[str] = None

class CartResponse(BaseModel):
    id: str
    shop_id: str
    user_id: str
    items: List[CartItemResponse]
    total_items: int
    total_amount: float
    updated_at: str

class CheckoutRequest(BaseModel):
    payment_method: Literal["cash", "mpesa", "card"]
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    shipping_address: Optional[str] = None
    notes: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: Literal["pending", "paid", "processing", "shipped", "completed", "cancelled"]

class OrderItemResponse(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total: float
    image_url: Optional[str] = None

class OrderResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    order_number: str
    shop_id: str
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    shipping_address: Optional[str] = None
    notes: Optional[str] = None
    items: List[OrderItemResponse]
    total_amount: float
    payment_method: str
    payment_status: str
    status: str
    mpesa_checkout_request_id: Optional[str] = None
    mpesa_receipt: Optional[str] = None
    created_by: str
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

class ShopCreate(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

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

class MarketplaceOrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int = Field(gt=0)
    unit_cost: float = Field(gt=0)

class MarketplaceOrderCreate(BaseModel):
    vendor_id: str
    items: List[MarketplaceOrderItem]
    payment_method: Literal["mpesa", "paystack", "bank_transfer", "cash"] = "mpesa"
    notes: Optional[str] = None

class MarketplaceDeliveryUpdate(BaseModel):
    status: Literal["delivered", "cancelled"]
    notes: Optional[str] = None

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

def create_refresh_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRATION_DAYS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_email_verification_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "type": "email_verification",
        "exp": datetime.now(timezone.utc) + timedelta(hours=EMAIL_VERIFICATION_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_password_reset_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "type": "password_reset",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def build_media_url(filename: str) -> str:
    if settings.media_base_url:
        return f"{settings.media_base_url}/{filename}"
    if settings.public_base_url:
        return f"{settings.public_base_url}/api/uploads/{filename}"
    return f"/api/uploads/{filename}"

def generate_order_number():
    return f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

async def create_notification(
    *,
    user_id: str,
    shop_id: str,
    title: str,
    message: str,
    channel: str = "email",
    metadata: Optional[dict] = None
):
    notification = {
        "id": str(uuid4()),
        "user_id": user_id,
        "shop_id": shop_id,
        "title": title,
        "message": message,
        "channel": channel,
        "metadata": metadata or {},
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "logged" if settings.smtp_enabled else "queued"
    }
    await db.notifications.insert_one(notification)
    return notification

def build_restock_suggestions(products: List[dict]) -> List[dict]:
    """
    Convert raw inventory rows into actionable restock suggestions.
    The score intentionally weighs shortage depth and stock-cover ratio so the
    dashboards can sort the most urgent items first without extra client logic.
    """
    suggestions = []
    for product in products:
        min_level = max(product.get("min_stock_level", 0), 0)
        stock = max(product.get("stock_quantity", 0), 0)
        if stock > min_level:
            continue

        shortage = max(min_level - stock, 0)
        recommended_restock = max(shortage, min_level or 1)
        coverage_ratio = 1 if min_level == 0 else round(stock / min_level, 2)
        urgency_score = (shortage * 2) + (0 if coverage_ratio >= 1 else round((1 - coverage_ratio) * 10, 2))
        suggestions.append({
            "product_id": product["id"],
            "product_name": product["name"],
            "sku": product.get("sku"),
            "category": product.get("category"),
            "stock_quantity": stock,
            "min_stock_level": min_level,
            "recommended_restock": recommended_restock,
            "estimated_restock_cost": round((product.get("cost_price") or 0) * recommended_restock, 2),
            "coverage_ratio": coverage_ratio,
            "urgency_score": urgency_score,
        })

    return sorted(suggestions, key=lambda item: (-item["urgency_score"], item["product_name"]))

async def get_shop_low_stock_products(shop_id: str) -> List[dict]:
    products = await db.products.find({"shop_id": shop_id}, {"_id": 0}).to_list(1000)
    return build_restock_suggestions(products)

def summarize_payment_mix(payments: List[dict]) -> dict:
    summary = {
        "total_collected": 0.0,
        "pending_amount": 0.0,
        "successful_count": 0,
        "pending_count": 0,
        "failed_count": 0,
        "by_method": {},
    }
    for payment in payments:
        method = payment.get("method") or payment.get("provider") or "unknown"
        bucket = summary["by_method"].setdefault(method, {"amount": 0.0, "count": 0})
        bucket["amount"] += payment.get("amount", 0.0)
        bucket["count"] += 1
        status_value = payment.get("status")
        if status_value in {"successful", "paid"}:
            summary["total_collected"] += payment.get("amount", 0.0)
            summary["successful_count"] += 1
        elif status_value == "pending":
            summary["pending_amount"] += payment.get("amount", 0.0)
            summary["pending_count"] += 1
        elif status_value:
            summary["failed_count"] += 1
    return summary

async def send_email_message(*, to_email: str, subject: str, body: str):
    if not settings.smtp_enabled:
        logger.info("SMTP disabled; email queued for %s with subject %s", to_email, subject)
        return {"status": "queued", "provider": "smtp-disabled"}

    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        raise HTTPException(status_code=500, detail="SMTP is enabled but credentials are incomplete")

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    def _send():
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ssl.create_default_context()) as server:
                server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)
            return

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls(context=ssl.create_default_context())
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)

    await asyncio.to_thread(_send)
    return {"status": "sent", "provider": "smtp"}

async def send_transactional_email(
    *,
    user_id: str,
    shop_id: str,
    to_email: str,
    subject: str,
    body: str,
    notification_title: str,
    metadata: Optional[dict] = None
):
    send_result = await send_email_message(to_email=to_email, subject=subject, body=body)
    notification = await create_notification(
        user_id=user_id,
        shop_id=shop_id,
        title=notification_title,
        message=body,
        metadata={**(metadata or {}), **send_result}
    )
    await db.notifications.update_one(
        {"id": notification["id"]},
        {"$set": {"status": send_result["status"], "provider": send_result["provider"]}}
    )
    return send_result

async def build_cart_response(user: dict) -> CartResponse:
    cart = await db.cart.find_one({"user_id": user["id"], "shop_id": user["shop_id"]}, {"_id": 0})
    items = cart.get("items", []) if cart else []
    response_items: List[CartItemResponse] = []
    total_amount = 0.0
    total_items = 0

    for item in items:
        product = await db.products.find_one({"id": item["product_id"], "shop_id": user["shop_id"]}, {"_id": 0})
        if not product:
            continue

        total = product["unit_price"] * item["quantity"]
        total_amount += total
        total_items += item["quantity"]
        response_items.append(
            CartItemResponse(
                product_id=product["id"],
                product_name=product["name"],
                quantity=item["quantity"],
                unit_price=product["unit_price"],
                total=total,
                image_url=product.get("image_url")
            )
        )

    return CartResponse(
        id=cart["id"] if cart else str(uuid4()),
        shop_id=user["shop_id"],
        user_id=user["id"],
        items=response_items,
        total_items=total_items,
        total_amount=total_amount,
        updated_at=cart["updated_at"] if cart else datetime.now(timezone.utc).isoformat()
    )

async def get_default_membership(user_id: str):
    membership = await db.shop_users.find_one({"user_id": user_id}, {"_id": 0})
    if membership:
        return membership
    return None

async def resolve_shop_membership(user_id: str, requested_shop_id: Optional[str] = None) -> dict:
    membership = None
    if requested_shop_id:
        membership = await db.shop_users.find_one({"user_id": user_id, "shop_id": requested_shop_id}, {"_id": 0})
    else:
        membership = await get_default_membership(user_id)

    if not membership:
        raise HTTPException(status_code=403, detail="You do not have access to this shop")

    return membership

async def get_active_subscription(shop_id: str):
    return await db.subscriptions.find_one({"shop_id": shop_id}, {"_id": 0}, sort=[("expires_at", -1)])

async def ensure_shop_subscription_active(shop_id: str):
    subscription = await get_active_subscription(shop_id)
    if not subscription:
        raise HTTPException(status_code=403, detail="Shop subscription is inactive")

    expires_at = datetime.fromisoformat(subscription["expires_at"])
    if subscription.get("status") != "active" or expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Shop subscription is inactive")
    return subscription

async def run_transaction(operation):
    try:
        async with await client.start_session() as session:
            async with session.start_transaction():
                return await operation(session)
    except Exception:
        return await operation(None)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_shop_id: Optional[str] = Header(default=None, alias="X-Shop-Id")
):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        membership = await resolve_shop_membership(user["id"], x_shop_id or payload.get("shop_id") or user.get("default_shop_id"))
        exempt_paths = {
            "/api/health",
            "/api/auth/me",
            "/api/subscriptions/current",
            "/api/subscriptions/pay",
        }
        if request.url.path not in exempt_paths and not request.url.path.startswith("/api/mpesa/webhook"):
            await ensure_shop_subscription_active(membership["shop_id"])

        return {
            **user,
            "user_id": user["id"],
            "id": user["id"],
            "role": membership["role"],
            "shop_id": membership["shop_id"],
            "shop_user_id": membership["id"],
            "primary_shop_id": user.get("default_shop_id") or membership["shop_id"]
        }
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

def generate_purchase_number():
    return f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

# =============================================================================
# AUTH ROUTES
# =============================================================================

@api_router.post("/auth/register", response_model=dict)
async def register(data: UserCreate):
    if data.role != "owner":
        raise HTTPException(status_code=400, detail="Only owner registration is allowed on this endpoint")

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
        "email": data.email,
        "email_verified": False,
        "default_shop_id": shop_id,
        "trial_ends_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Update shop owner_id
    if data.role == "owner":
        await db.shops.update_one({"id": shop_id}, {"$set": {"owner_id": user_id}})
    
    await db.users.insert_one(user)
    await db.shop_users.insert_one({
        "id": str(uuid4()),
        "user_id": user_id,
        "shop_id": shop_id,
        "role": "owner",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    await db.subscriptions.insert_one({
        "id": str(uuid4()),
        "shop_id": shop_id,
        "owner_id": user_id,
        "amount": 300,
        "status": "active",
        "paid_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "mpesa_receipt": "TRIAL"
    })

    token = create_token(user_id, shop_id, "owner")
    refresh_token = create_refresh_token(user_id)
    email_verification_token = create_email_verification_token(user_id) if data.email else None

    if data.email:
        await send_transactional_email(
            user_id=user_id,
            shop_id=shop_id,
            to_email=data.email,
            subject="Verify your CloudDuka account",
            body=(
                f"Hello {data.name},\n\n"
                f"Use this verification token to verify your CloudDuka account:\n\n{email_verification_token}\n\n"
                "If you did not create this account, please ignore this email."
            ),
            notification_title="Verify your email",
            metadata={"verification_token": email_verification_token}
        )
    
    return {
        "token": token,
        "refresh_token": refresh_token,
        "email_verification_token": email_verification_token,
        "user": {
            "id": user_id,
            "phone": data.phone,
            "name": data.name,
            "email": data.email,
            "email_verified": False,
            "role": "owner",
            "shop_id": shop_id,
            "trial_ends_at": user["trial_ends_at"],
            "subscription_status": "active",
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
    
    membership = await get_default_membership(user["id"])
    if not membership:
        raise HTTPException(status_code=403, detail="User is not linked to any shop")

    subscription = await get_active_subscription(membership["shop_id"])
    token = create_token(user["id"], membership["shop_id"], membership["role"])
    refresh_token = create_refresh_token(user["id"])
    
    return {
        "token": token,
        "refresh_token": refresh_token,
        "user": {
            "id": user["id"],
            "phone": user["phone"],
            "name": user["name"],
            "email": user.get("email"),
            "email_verified": user.get("email_verified", False),
            "role": membership["role"],
            "shop_id": membership["shop_id"],
            "trial_ends_at": user.get("trial_ends_at"),
            "subscription_status": subscription.get("status", "expired") if subscription else "expired",
            "created_at": user["created_at"]
        }
    }

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        phone=user["phone"],
        name=user["name"],
        email=user.get("email"),
        email_verified=user.get("email_verified", False),
        role=user["role"],
        shop_id=user["shop_id"],
        trial_ends_at=user.get("trial_ends_at"),
        subscription_status=user.get("subscription_status", "trial"),
        created_at=user["created_at"]
    )

@api_router.post("/auth/refresh", response_model=dict)
async def refresh_access_token(data: RefreshTokenRequest):
    try:
        payload = jwt.decode(data.refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    membership = await get_default_membership(user["id"])
    if not membership:
        raise HTTPException(status_code=403, detail="User is not linked to any shop")
    subscription = await get_active_subscription(membership["shop_id"])

    return {
        "token": create_token(user["id"], membership["shop_id"], membership["role"]),
        "refresh_token": create_refresh_token(user["id"]),
        "user": {
            "id": user["id"],
            "phone": user["phone"],
            "name": user["name"],
            "email": user.get("email"),
            "email_verified": user.get("email_verified", False),
            "role": membership["role"],
            "shop_id": membership["shop_id"],
            "trial_ends_at": user.get("trial_ends_at"),
            "subscription_status": subscription.get("status", "expired") if subscription else "expired",
            "created_at": user["created_at"]
        }
    }

@api_router.post("/auth/verify-email", response_model=dict)
async def verify_email(data: EmailVerificationRequest):
    try:
        payload = jwt.decode(data.token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "email_verification":
            raise HTTPException(status_code=400, detail="Invalid verification token")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    result = await db.users.update_one(
        {"id": payload["user_id"]},
        {"$set": {"email_verified": True, "email_verified_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Email verified successfully"}

@api_router.post("/auth/request-password-reset", response_model=dict)
async def request_password_reset(data: PasswordResetRequest):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user:
        return {"message": "If the email exists, a reset email has been sent"}

    reset_token = create_password_reset_token(user["id"])
    await send_transactional_email(
        user_id=user["id"],
        shop_id=user["shop_id"],
        to_email=data.email,
        subject="Reset your CloudDuka PIN",
        body=(
            f"Hello {user['name']},\n\n"
            f"Use this password reset token to set a new PIN:\n\n{reset_token}\n\n"
            "This token expires in 1 hour."
        ),
        notification_title="Password reset requested",
        metadata={"password_reset_token": reset_token}
    )
    return {"message": "If the email exists, a reset email has been sent"}

@api_router.post("/auth/reset-password", response_model=dict)
async def reset_password(data: PasswordResetConfirm):
    try:
        payload = jwt.decode(data.token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "password_reset":
            raise HTTPException(status_code=400, detail="Invalid reset token")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    result = await db.users.update_one(
        {"id": payload["user_id"]},
        {"$set": {"pin_hash": hash_pin(data.new_pin), "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "PIN reset successfully"}

# =============================================================================
# PRODUCT ROUTES
# =============================================================================

@api_router.post("/products", response_model=ProductResponse)
async def create_product(data: ProductCreate, user: dict = Depends(require_owner)):
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
        "image_url": None,
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
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None,
    sort_by: Optional[str] = Query(default="updated_at"),
    sort_order: Optional[str] = Query(default="desc"),
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

    price_filter = {}
    if min_price is not None:
        price_filter["$gte"] = min_price
    if max_price is not None:
        price_filter["$lte"] = max_price
    if price_filter:
        query["unit_price"] = price_filter
    
    products = await db.products.find(query, {"_id": 0}).to_list(1000)
    
    if low_stock:
        products = [p for p in products if p["stock_quantity"] <= p["min_stock_level"]]
    if in_stock:
        products = [p for p in products if p["stock_quantity"] > 0]

    reverse = sort_order != "asc"
    allowed_sort_fields = {"updated_at", "created_at", "unit_price", "name", "stock_quantity"}
    sort_key = sort_by if sort_by in allowed_sort_fields else "updated_at"
    products = sorted(products, key=lambda item: item.get(sort_key) or "", reverse=reverse)
    
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
async def update_product(product_id: str, data: ProductUpdate, user: dict = Depends(require_owner)):
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

@api_router.post("/products/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: str,
    image: UploadFile = File(...),
    user: dict = Depends(require_owner)
):
    product = await db.products.find_one({"id": product_id, "shop_id": user["shop_id"]}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    extension = Path(image.filename or "").suffix.lower() or ".jpg"
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    filename = f"{product_id}-{uuid4().hex}{extension}"
    destination = MEDIA_PATH / filename
    destination.write_bytes(await image.read())
    image_url = build_media_url(filename)

    await db.products.update_one(
        {"id": product_id, "shop_id": user["shop_id"]},
        {"$set": {"image_url": image_url, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await db.products.find_one({"id": product_id, "shop_id": user["shop_id"]}, {"_id": 0})
    return ProductResponse(**updated)

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

@api_router.post("/mpesa/webhook", response_model=dict)
async def mpesa_webhook(payload: dict, x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret")):
    if x_webhook_secret != settings.mpesa_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    checkout_request_id = payload.get("checkout_request_id")
    if not checkout_request_id:
        raise HTTPException(status_code=400, detail="checkout_request_id is required")

    transaction = await db.mpesa_transactions.find_one({"checkout_request_id": checkout_request_id}, {"_id": 0})
    payment = await db.payments.find_one({"checkout_request_id": checkout_request_id}, {"_id": 0})
    if not transaction and not payment:
        raise HTTPException(status_code=404, detail="Transaction not found")

    mpesa_receipt = payload.get("mpesa_receipt") or f"MPESA-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    async def operation(session):
        if transaction:
            await db.mpesa_transactions.update_one(
                {"checkout_request_id": checkout_request_id},
                {"$set": {"status": "completed", "mpesa_receipt": mpesa_receipt, "webhook_payload": payload}},
                session=session
            )
            await db.orders.update_one(
                {"mpesa_checkout_request_id": checkout_request_id},
                {"$set": {"payment_status": "paid", "status": "paid", "mpesa_receipt": mpesa_receipt, "updated_at": datetime.now(timezone.utc).isoformat()}},
                session=session
            )
        if payment and payment.get("type") == "subscription":
            expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            await db.payments.update_one(
                {"checkout_request_id": checkout_request_id},
                {"$set": {"status": "successful", "mpesa_receipt": mpesa_receipt, "paid_at": datetime.now(timezone.utc).isoformat()}},
                session=session
            )
            await db.subscriptions.insert_one({
                "id": str(uuid4()),
                "shop_id": payment["shop_id"],
                "owner_id": payment["owner_id"],
                "amount": 300,
                "status": "active",
                "paid_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at,
                "mpesa_receipt": mpesa_receipt
            }, session=session)

    await run_transaction(operation)
    return {"message": "Webhook processed", "mpesa_receipt": mpesa_receipt}

# =============================================================================
# CART & ORDER ROUTES
# =============================================================================

@api_router.get("/cart", response_model=CartResponse)
async def get_cart(user: dict = Depends(get_current_user)):
    return await build_cart_response(user)

@api_router.put("/cart", response_model=CartResponse)
async def replace_cart(items: List[CartItem], user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    await db.cart.update_one(
        {"user_id": user["id"], "shop_id": user["shop_id"]},
        {
            "$set": {
                "items": [item.model_dump() for item in items],
                "updated_at": now
            },
            "$setOnInsert": {"id": str(uuid4())}
        },
        upsert=True
    )
    return await build_cart_response(user)

@api_router.post("/cart/items", response_model=CartResponse)
async def add_cart_item(item: CartItem, user: dict = Depends(get_current_user)):
    cart = await db.cart.find_one({"user_id": user["id"], "shop_id": user["shop_id"]}, {"_id": 0}) or {
        "id": str(uuid4()),
        "user_id": user["id"],
        "shop_id": user["shop_id"],
        "items": []
    }
    items = cart["items"]
    for existing in items:
        if existing["product_id"] == item.product_id:
            existing["quantity"] = item.quantity
            break
    else:
        items.append(item.model_dump())

    await db.cart.update_one(
        {"user_id": user["id"], "shop_id": user["shop_id"]},
        {"$set": {"id": cart["id"], "items": items, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return await build_cart_response(user)

@api_router.delete("/cart/items/{product_id}", response_model=CartResponse)
async def remove_cart_item(product_id: str, user: dict = Depends(get_current_user)):
    cart = await db.cart.find_one({"user_id": user["id"], "shop_id": user["shop_id"]}, {"_id": 0})
    if cart:
        items = [item for item in cart.get("items", []) if item["product_id"] != product_id]
        await db.cart.update_one(
            {"user_id": user["id"], "shop_id": user["shop_id"]},
            {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    return await build_cart_response(user)

@api_router.post("/orders/checkout", response_model=OrderResponse)
async def checkout_cart(data: CheckoutRequest, user: dict = Depends(get_current_user)):
    cart = await build_cart_response(user)
    if not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    for item in cart.items:
        product = await db.products.find_one({"id": item.product_id, "shop_id": user["shop_id"]}, {"_id": 0})
        if not product or product["stock_quantity"] < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {item.product_name}")

    now = datetime.now(timezone.utc).isoformat()
    order_id = str(uuid4())
    checkout_request_id = None
    payment_status = "pending" if data.payment_method == "mpesa" else "paid"
    order_status = "pending" if data.payment_method == "mpesa" else "paid"

    payment_id = str(uuid4())
    if data.payment_method == "mpesa":
        checkout_request_id = f"ws_CO_{uuid4().hex[:12]}"

    order = {
        "id": order_id,
        "order_number": generate_order_number(),
        "shop_id": user["shop_id"],
        "customer_name": data.customer_name,
        "customer_email": data.customer_email or user.get("email"),
        "customer_phone": data.customer_phone,
        "shipping_address": data.shipping_address,
        "notes": data.notes,
        "items": [item.model_dump() for item in cart.items],
        "total_amount": cart.total_amount,
        "payment_method": data.payment_method,
        "payment_status": payment_status,
        "status": order_status,
        "mpesa_checkout_request_id": checkout_request_id,
        "mpesa_receipt": None,
        "created_by": user["id"],
        "created_at": now,
        "updated_at": now
    }
    async def operation(session):
        if data.payment_method == "mpesa":
            await db.mpesa_transactions.insert_one({
                "id": str(uuid4()),
                "checkout_request_id": checkout_request_id,
                "merchant_request_id": str(uuid4()),
                "phone": data.customer_phone,
                "amount": cart.total_amount,
                "reference": order_id,
                "shop_id": user["shop_id"],
                "status": "pending",
                "callback_url": settings.mpesa_callback_url or None,
                "created_at": now
            }, session=session)

        for item in cart.items:
            await db.products.update_one(
                {"id": item.product_id, "shop_id": user["shop_id"]},
                {"$inc": {"stock_quantity": -item.quantity}},
                session=session
            )
            await db.order_items.insert_one({
                "id": str(uuid4()),
                "order_id": order_id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "price": item.unit_price
            }, session=session)

        await db.orders.insert_one(order, session=session)
        await db.payments.insert_one({
            "id": payment_id,
            "shop_id": user["shop_id"],
            "order_id": order_id,
            "amount": cart.total_amount,
            "status": "pending" if data.payment_method == "mpesa" else "successful",
            "method": data.payment_method,
            "checkout_request_id": checkout_request_id,
            "created_at": now,
            "user_id": user["user_id"]
        }, session=session)
        await db.cart.update_one(
            {"user_id": user["id"], "shop_id": user["shop_id"]},
            {"$set": {"items": [], "updated_at": now}},
            upsert=True,
            session=session
        )

    await run_transaction(operation)
    await create_notification(
        user_id=user["id"],
        shop_id=user["shop_id"],
        title="Order created",
        message=f"Order {order['order_number']} was created with status {order['status']}",
        metadata={"order_id": order_id}
    )

    confirmation_email = order.get("customer_email") or user.get("email")
    if confirmation_email:
        await send_transactional_email(
            user_id=user["id"],
            shop_id=user["shop_id"],
            to_email=confirmation_email,
            subject=f"Order confirmation: {order['order_number']}",
            body=(
                f"Hello {order.get('customer_name') or user['name']},\n\n"
                f"Your order {order['order_number']} has been created.\n"
                f"Payment method: {order['payment_method']}\n"
                f"Order total: KES {order['total_amount']:.2f}\n"
                f"Current status: {order['status']}\n\n"
                "Thank you for shopping with CloudDuka."
            ),
            notification_title="Order confirmation email sent",
            metadata={"order_id": order_id, "order_number": order["order_number"]}
        )
    return OrderResponse(**order)

@api_router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    query = {"shop_id": user["shop_id"]}
    if status:
        query["status"] = status
    if payment_status:
        query["payment_status"] = payment_status
    orders = await db.orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [OrderResponse(**order) for order in orders]

@api_router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, user: dict = Depends(get_current_user)):
    order = await db.orders.find_one({"id": order_id, "shop_id": user["shop_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse(**order)

@api_router.put("/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(order_id: str, data: OrderStatusUpdate, owner: dict = Depends(require_owner)):
    await db.orders.update_one(
        {"id": order_id, "shop_id": owner["shop_id"]},
        {"$set": {"status": data.status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    order = await db.orders.find_one({"id": order_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse(**order)

@api_router.get("/orders/history/me", response_model=List[OrderResponse])
async def my_order_history(user: dict = Depends(get_current_user)):
    orders = await db.orders.find({"created_by": user["id"], "shop_id": user["shop_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [OrderResponse(**order) for order in orders]

# =============================================================================
# USER MANAGEMENT ROUTES (Owner only)
# =============================================================================

@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, owner: dict = Depends(require_owner)):
    """Create a shopkeeper (owner only)"""
    existing = await db.users.find_one({"phone": data.phone})
    user_record = existing
    if existing:
        user_id = existing["id"]
    else:
        user_id = str(uuid.uuid4())
        user_record = {
            "id": user_id,
            "phone": data.phone,
            "pin_hash": hash_pin(data.pin),
            "name": data.name,
            "email": data.email,
            "email_verified": False,
            "default_shop_id": owner["shop_id"],
            "trial_ends_at": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(user_record)

    existing_membership = await db.shop_users.find_one({"user_id": user_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    if existing_membership:
        raise HTTPException(status_code=400, detail="User already linked to this shop")

    await db.shop_users.insert_one({
        "id": str(uuid4()),
        "user_id": user_id,
        "shop_id": owner["shop_id"],
        "role": "shopkeeper",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    return UserResponse(
        id=user_id,
        phone=data.phone,
        name=data.name,
        email=data.email,
        email_verified=False,
        role="shopkeeper",
        shop_id=owner["shop_id"],
        subscription_status="active",
        created_at=user_record["created_at"]
    )

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(owner: dict = Depends(require_owner)):
    """List all users in the shop"""
    memberships = await db.shop_users.find({"shop_id": owner["shop_id"]}, {"_id": 0}).to_list(100)
    users = []
    for membership in memberships:
        user = await db.users.find_one({"id": membership["user_id"]}, {"_id": 0, "pin_hash": 0})
        if user:
            users.append(UserResponse(
                id=user["id"],
                phone=user["phone"],
                name=user["name"],
                email=user.get("email"),
                email_verified=user.get("email_verified", False),
                role=membership["role"],
                shop_id=membership["shop_id"],
                subscription_status="active",
                created_at=user["created_at"]
            ))
    return users

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, owner: dict = Depends(require_owner)):
    """Delete a shopkeeper (owner only)"""
    membership = await db.shop_users.find_one({"user_id": user_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    if not membership:
        raise HTTPException(status_code=404, detail="User not found")
    if membership["role"] == "owner":
        raise HTTPException(status_code=400, detail="Cannot delete owner")
    
    await db.shop_users.delete_one({"id": membership["id"]})
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
    
    # Restock suggestions are calculated server-side so every dashboard uses the
    # same urgency scoring and recommended reorder quantity.
    low_stock = await get_shop_low_stock_products(shop_id)
    
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
        "restock_suggestions": low_stock[:10],
        "total_credit_outstanding": total_credit,
        "recent_sales": recent_sales,
        "weekly_sales": weekly_data
    }

@api_router.get("/reports/restock-suggestions")
async def get_restock_suggestions(limit: int = 20, user: dict = Depends(get_current_user)):
    suggestions = await get_shop_low_stock_products(user["shop_id"])
    return {
        "shop_id": user["shop_id"],
        "count": len(suggestions),
        "items": suggestions[: max(limit, 1)]
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
        "created_at": now
    }
    
    await db.suppliers.insert_one(supplier)
    return SupplierResponse(**supplier)

@api_router.get("/suppliers", response_model=List[SupplierResponse])
async def list_suppliers(
    search: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    query = {"shop_id": user["shop_id"]}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
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
    supplier_id: str, 
    data: SupplierUpdate, 
    user: dict = Depends(require_owner)
):
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    result = await db.suppliers.update_one(
        {"id": supplier_id, "shop_id": user["shop_id"]},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    supplier = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    return SupplierResponse(**supplier)

@api_router.delete("/suppliers/{supplier_id}")
async def delete_supplier(supplier_id: str, user: dict = Depends(require_owner)):
    result = await db.suppliers.delete_one({"id": supplier_id, "shop_id": user["shop_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return {"message": "Supplier deleted"}

# =============================================================================
# MARKETPLACE ORDERING ROUTES
# =============================================================================

@api_router.get("/marketplace/vendors", response_model=List[SupplierResponse])
async def list_marketplace_vendors(user: dict = Depends(get_current_user)):
    return await list_suppliers(user=user)

@api_router.post("/marketplace/orders", response_model=dict)
async def create_marketplace_order(data: MarketplaceOrderCreate, owner: dict = Depends(require_owner)):
    vendor = await db.suppliers.find_one({"id": data.vendor_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    now = datetime.now(timezone.utc).isoformat()
    order_id = str(uuid4())
    payment_id = str(uuid4())
    total_amount = round(sum(item.quantity * item.unit_cost for item in data.items), 2)
    order = {
        "id": order_id,
        "order_number": generate_purchase_number(),
        "shop_id": owner["shop_id"],
        "order_type": "marketplace",
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "customer_name": vendor["name"],
        "customer_email": None,
        "customer_phone": vendor["phone"],
        "shipping_address": None,
        "notes": data.notes,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": item.unit_cost,
                "total": round(item.quantity * item.unit_cost, 2)
            }
            for item in data.items
        ],
        "total_amount": total_amount,
        "payment_method": data.payment_method,
        "payment_status": "pending",
        "status": "ordered",
        "mpesa_checkout_request_id": None,
        "mpesa_receipt": None,
        "created_by": owner["user_id"],
        "created_at": now,
        "updated_at": now
    }

    async def operation(session):
        for item in data.items:
            await db.order_items.insert_one({
                "id": str(uuid4()),
                "order_id": order_id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "price": item.unit_cost,
                "item_type": "marketplace",
            }, session=session)

        await db.orders.insert_one(order, session=session)
        await db.payments.insert_one({
            "id": payment_id,
            "shop_id": owner["shop_id"],
            "order_id": order_id,
            "amount": total_amount,
            "status": "pending",
            "method": data.payment_method,
            "provider": data.payment_method,
            "type": "marketplace_order",
            "user_id": owner["user_id"],
            "created_at": now,
        }, session=session)

    await run_transaction(operation)
    return order

@api_router.get("/marketplace/orders", response_model=List[dict])
async def list_marketplace_orders(user: dict = Depends(get_current_user)):
    orders = await db.orders.find(
        {"shop_id": user["shop_id"], "order_type": "marketplace"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return orders

@api_router.post("/marketplace/orders/{order_id}/receive", response_model=dict)
async def receive_marketplace_order(order_id: str, data: MarketplaceDeliveryUpdate, owner: dict = Depends(require_owner)):
    order = await db.orders.find_one(
        {"id": order_id, "shop_id": owner["shop_id"], "order_type": "marketplace"},
        {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Marketplace order not found")

    now = datetime.now(timezone.utc).isoformat()

    async def operation(session):
        if data.status == "delivered":
            for item in order.get("items", []):
                # Delivery updates stock only once, guarded by the status check above.
                await db.products.update_one(
                    {"id": item["product_id"], "shop_id": owner["shop_id"]},
                    {"$inc": {"stock_quantity": item["quantity"]}, "$set": {"updated_at": now}},
                    session=session
                )
            await db.payments.update_one(
                {"order_id": order_id, "shop_id": owner["shop_id"]},
                {"$set": {"status": "successful", "updated_at": now}},
                session=session
            )
        elif data.status == "cancelled":
            await db.payments.update_one(
                {"order_id": order_id, "shop_id": owner["shop_id"]},
                {"$set": {"status": "cancelled", "updated_at": now}},
                session=session
            )

        await db.orders.update_one(
            {"id": order_id, "shop_id": owner["shop_id"]},
            {"$set": {"status": data.status, "payment_status": "paid" if data.status == "delivered" else "cancelled", "notes": data.notes or order.get("notes"), "updated_at": now}},
            session=session
        )

    if order.get("status") == "delivered":
        raise HTTPException(status_code=400, detail="Marketplace order already delivered")

    await run_transaction(operation)
    updated = await db.orders.find_one({"id": order_id, "shop_id": owner["shop_id"]}, {"_id": 0})
    return updated

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
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        
        # Calculate total units to add based on unit type
        total_units = item.quantity * item.units_per_package
        
        # Update product stock and cost price
        cost_per_unit = item.cost / total_units if total_units > 0 else 0
        await db.products.update_one(
            {"id": item.product_id},
            {
                "$inc": {"stock_quantity": total_units},
                "$set": {"cost_price": cost_per_unit, "updated_at": now}
            }
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
        "created_at": now
    }
    
    await db.purchases.insert_one(purchase)
    return PurchaseResponse(**purchase)

@api_router.get("/purchases", response_model=List[PurchaseResponse])
async def list_purchases(
    supplier_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user)
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
    
    purchases = await db.purchases.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
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
    return {"message": "Purchase record deleted"}

@api_router.get("/purchases/stats/summary")
async def get_purchases_summary(user: dict = Depends(get_current_user)):
    """Get purchase statistics"""
    shop_id = user["shop_id"]
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Today's purchases
    today_purchases = await db.purchases.find(
        {"shop_id": shop_id, "created_at": {"$gte": today.isoformat()}},
        {"_id": 0}
    ).to_list(1000)
    
    today_total = sum(p["total_cost"] for p in today_purchases)
    
    # Total suppliers
    supplier_count = await db.suppliers.count_documents({"shop_id": shop_id})
    
    # This month's purchases
    month_start = today.replace(day=1)
    month_purchases = await db.purchases.find(
        {"shop_id": shop_id, "created_at": {"$gte": month_start.isoformat()}},
        {"_id": 0}
    ).to_list(10000)
    
    month_total = sum(p["total_cost"] for p in month_purchases)
    
    return {
        "today_purchases": len(today_purchases),
        "today_total": today_total,
        "month_total": month_total,
        "supplier_count": supplier_count
    }

# =============================================================================
# DASHBOARD EXTENSIONS
# =============================================================================

@api_router.get("/dashboard/vendor")
async def get_vendor_dashboard(user: dict = Depends(require_owner)):
    products_count = await db.products.count_documents({"shop_id": user["shop_id"]})
    orders = await db.orders.find({"shop_id": user["shop_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    payments = await db.payments.find({"shop_id": user["shop_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    marketplace_orders = [order for order in orders if order.get("order_type") == "marketplace"]
    total_earnings = sum(order["total_amount"] for order in orders if order.get("payment_status") == "paid")
    pending_orders = sum(1 for order in orders if order.get("status") not in {"completed", "cancelled"})
    restock_suggestions = await get_shop_low_stock_products(user["shop_id"])
    top_products = sorted(
        (
            {
                "product_name": item["product_name"],
                "quantity": item["quantity"],
                "total": item["total"]
            }
            for order in orders
            for item in order.get("items", [])
        ),
        key=lambda item: item["quantity"],
        reverse=True
    )[:5]
    return {
        "shop_id": user["shop_id"],
        "products_count": products_count,
        "total_earnings": total_earnings,
        "pending_orders": pending_orders,
        "restock_suggestions": restock_suggestions[:5],
        "payments_summary": summarize_payment_mix(payments),
        "marketplace_orders": marketplace_orders[:10],
        "recent_orders": orders[:10],
        "top_products": top_products
    }

@api_router.get("/dashboard/admin")
async def get_admin_dashboard(owner: dict = Depends(require_owner)):
    owned_shops = await db.shops.find({"owner_id": owner["id"]}, {"_id": 0}).to_list(100)
    shop_ids = [shop["id"] for shop in owned_shops]
    memberships = await db.shop_users.find({"shop_id": {"$in": shop_ids}}, {"_id": 0}).to_list(1000)
    users_count = len({membership["user_id"] for membership in memberships})
    orders = await db.orders.find({"shop_id": {"$in": shop_ids}}, {"_id": 0}).sort("created_at", -1).to_list(500)
    payments = await db.payments.find({"shop_id": {"$in": shop_ids}}, {"_id": 0}).sort("created_at", -1).to_list(500)
    total_revenue = sum(order["total_amount"] for order in orders if order.get("payment_status") == "paid")
    restock_suggestions = []
    for shop in owned_shops:
        for suggestion in await get_shop_low_stock_products(shop["id"]):
            restock_suggestions.append({**suggestion, "shop_id": shop["id"], "shop_name": shop["name"]})
    restock_suggestions = sorted(restock_suggestions, key=lambda item: (-item["urgency_score"], item["shop_name"]))[:10]
    return {
        "shops_count": len(owned_shops),
        "users_count": users_count,
        "orders_count": len(orders),
        "total_revenue": total_revenue,
        "payments_summary": summarize_payment_mix(payments),
        "restock_suggestions": restock_suggestions,
        "marketplace_orders": [order for order in orders if order.get("order_type") == "marketplace"][:10],
        "recent_orders": orders[:10]
    }

@api_router.get("/payments/summary")
async def get_payments_summary(user: dict = Depends(get_current_user)):
    payments = await db.payments.find({"shop_id": user["shop_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    subscriptions = await db.subscriptions.find({"shop_id": user["shop_id"]}, {"_id": 0}).sort("expires_at", -1).to_list(20)
    return {
        "shop_id": user["shop_id"],
        "summary": summarize_payment_mix(payments),
        "recent_payments": payments[:10],
        "subscriptions": subscriptions[:5]
    }

@api_router.get("/payments/providers/compare")
async def compare_payment_providers(user: dict = Depends(require_owner)):
    return {
        "recommended_provider": "paystack",
        "recommended_for": "multi-country card and wallet growth",
        "comparison": [
            {
                "provider": "mpesa",
                "best_for": "Kenyan mobile money collections and subscription renewals",
                "strengths": ["Deep local trust", "Low customer friction for Kenya", "Strong cash-to-wallet conversion"],
                "tradeoffs": ["Primarily regional", "Less flexible for cards and cross-border scale"],
            },
            {
                "provider": "paystack",
                "best_for": "Regional scaling across cards, bank transfers, and multiple digital payment rails",
                "strengths": ["Broader payment method coverage", "Better fit for marketplace expansion", "Stronger developer ecosystem for retries/webhooks"],
                "tradeoffs": ["M-Pesa still feels more native for many Kenyan-only merchants"],
            },
        ],
        "guidance": "Keep M-Pesa for local checkout and subscription collections in Kenya, but add Paystack as the scalable default for marketplace and card-heavy growth. Subscriptions remain isolated per shop because each payment record and subscription row is stored with its own shop_id.",
    }

@api_router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    notifications = await db.notifications.find(
        {"user_id": user["id"], "shop_id": user["shop_id"]},
        {"_id": 0}
    ).sort("sent_at", -1).to_list(100)
    return notifications

@api_router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    file_path = MEDIA_PATH / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return {"url": build_media_url(filename), "filename": filename}

@api_router.post("/shops", response_model=dict)
async def create_shop(data: ShopCreate, owner: dict = Depends(require_owner)):
    shop_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    shop = {
        "id": shop_id,
        "name": data.name,
        "address": data.address,
        "phone": data.phone,
        "email": data.email,
        "owner_id": owner["user_id"],
        "created_at": now
    }
    await db.shops.insert_one(shop)
    await db.shop_users.insert_one({
        "id": str(uuid4()),
        "user_id": owner["user_id"],
        "shop_id": shop_id,
        "role": "owner",
        "created_at": now
    })
    await db.subscriptions.insert_one({
        "id": str(uuid4()),
        "shop_id": shop_id,
        "owner_id": owner["user_id"],
        "amount": 300,
        "status": "active",
        "paid_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "mpesa_receipt": "TRIAL"
    })
    return shop

@api_router.get("/shops", response_model=List[dict])
async def list_shops(user: dict = Depends(get_current_user)):
    memberships = await db.shop_users.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    shops = []
    for membership in memberships:
        shop = await db.shops.find_one({"id": membership["shop_id"]}, {"_id": 0})
        if shop:
            shops.append({**shop, "role": membership["role"]})
    return shops

@api_router.get("/subscriptions/current", response_model=dict)
async def get_current_subscription(user: dict = Depends(get_current_user)):
    subscription = await get_active_subscription(user["shop_id"])
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@api_router.post("/subscriptions/pay", response_model=dict)
async def initiate_subscription_payment(owner: dict = Depends(require_owner)):
    now = datetime.now(timezone.utc).isoformat()
    payment_id = str(uuid4())
    checkout_request_id = f"sub_{uuid4().hex[:12]}"
    payment = {
        "id": payment_id,
        "shop_id": owner["shop_id"],
        "owner_id": owner["user_id"],
        "type": "subscription",
        "amount": 300,
        "status": "pending",
        "checkout_request_id": checkout_request_id,
        "created_at": now
    }
    await db.payments.insert_one(payment)
    return payment

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
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.app_env
    }

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def ensure_indexes():
    await db.users.create_index("phone", unique=True)
    await db.users.create_index("id", unique=True)
    await db.products.create_index("shop_id")
    await db.products.create_index("id", unique=True)
    await db.orders.create_index("shop_id")
    await db.orders.create_index("id", unique=True)
    await db.orders.create_index("created_by")
    await db.shop_users.create_index([("user_id", 1), ("shop_id", 1)], unique=True)
    await db.cart.create_index([("shop_id", 1), ("user_id", 1)], unique=True)
    await db.order_items.create_index("order_id")
    await db.order_items.create_index("product_id")
    await db.payments.create_index("shop_id")
    await db.payments.create_index("user_id")
    await db.payments.create_index("order_id")
    await db.subscriptions.create_index("shop_id")
    await db.notifications.create_index([("user_id", 1), ("sent_at", -1)])

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
