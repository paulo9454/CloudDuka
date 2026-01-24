# CloudDuka Retail POS - FINAL MASTER SPECIFICATION

## Project Overview
**Name:** CloudDuka Retail POS  
**Tagline:** Your Retail POS in the Cloud  
**Author:** Mosetech Solution  
**Brand Colors:** Blue #007BFF, Orange #FF8C00  
**Logo:** https://customer-assets.emergentagent.com/job_983fa6fb-7b7a-442c-bfdf-c5926d9538b8/artifacts/uzuoo21v_CloudDuka%20Logo.jpeg

CloudDuka is a cloud-based, mobile-first POS system designed for retail shops in Kenya/East Africa. It supports retail unit sales, M-Pesa payments, credit customers, stock management, and damaged/spoiled product tracking.

---

## Tech Stack
- **Backend:** FastAPI + MongoDB
- **Frontend:** React + Tailwind CSS + shadcn/ui
- **State Management:** Zustand
- **Charts:** Recharts
- **PDF Generation:** jspdf + jspdf-autotable
- **Authentication:** JWT (phone + PIN)

---

## User Roles & Pricing

### Roles
| Role | Access |
|------|--------|
| Owner | Full system access: stock, users, reports, settings, delete products |
| Shopkeeper | Sales, M-Pesa payments, credit sales, view products (no delete) |

### Pricing
- **Monthly:** KES 499
- **Annual:** KES 5,000 (save 17%)
- **Free Trial:** 14 days

---

## Core Features

### 1. Authentication
- Phone number + PIN login (JWT-based)
- Owner registration creates shop automatically
- Shopkeepers added by Owner
- 14-day trial for new owners

### 2. Product Management
**Entry Fields:**
- Product Name * (required)
- Selling Price (per unit) * (required)
- Buying Unit Type: Single / Packet / Dozen
- Units per Packet (when Packet selected)
- Number of Packets/Dozens buying
- Total Buying Cost
- **Auto-calculated:** Cost per unit, Total stock units
- Stock Quantity (locked when Packet/Dozen - auto-calculated)
- Min Stock Level (for low stock alerts)
- Category (optional free-text with suggestions)
- SKU (optional, auto-generated if empty)

**Auto-Division Logic:**
- Dozen: `buying_cost ÷ 12 = cost_per_unit`
- Packet: `buying_cost ÷ items_per_packet = cost_per_unit`
- Stock: `buying_quantity × units_per_buy = total_units` (locked field)

**Category Handling:**
- Optional free-text input
- Suggestions from existing categories
- Used for filtering only - no validation/blocking
- Simple filter chips in Products and POS pages

### 3. POS (Point of Sale)
- Product search by name/SKU
- Optional category filter chips
- Add to cart with quantity controls
- Stock validation (can't exceed available)
- Three payment methods:
  - **Cash:** Enter amount received, show change
  - **M-Pesa:** Enter phone, send STK Push (mock mode)
  - **Credit:** Select existing credit customer (required)
- Receipt number generation
- Stock auto-deduction on sale

### 4. Credit Customers (PERSISTENT)
**Customer Fields:**
- Name * (required)
- Phone * (required)
- Email (optional)
- Address (optional)
- Credit Limit (default: KES 10,000)

**Tracking:**
- Current Balance (outstanding amount)
- Credit Limit
- Available Credit (limit - balance)
- Transaction History (sales + payments)

**Credit Sales:**
- MUST select existing credit customer
- Stores: customer_id, sale amount, date, items
- Auto-deducts stock like normal sale
- Updates customer balance

**Payment Recording:**
- Record payments against customer
- Updates balance immediately
- Payment history with notes

**CRITICAL:** Credit customers are stored in MongoDB, NOT local storage. They persist across sessions and are available system-wide.

### 5. Damaged/Spoiled Stock
- Log damaged items with reason
- Reasons: Damaged, Expired, Spoiled, Other
- Auto-deducts from stock
- Optional notes
- Monthly reports

### 6. Reports & PDF Export
**Dashboard Stats:**
- Today's sales (total, count, by payment method)
- Low stock count
- Total credit outstanding
- Weekly sales chart
- Recent transactions

**Report Types:**
- Sales Report (date range)
- Credit Report (all customers)
- Damaged Stock Report (date range)

**PDF Export:**
- Sales report with transactions table
- Credit report with customer balances
- Damaged stock report with items

### 7. User Management (Owner Only)
- Add shopkeepers (phone + PIN)
- View all users
- Delete shopkeepers
- Cannot delete owner

### 8. Settings
- View profile
- Edit shop details (name, phone, address)
- Subscription status
- Logout

### 9. Offline Support
- Basic localStorage caching
- Pending sales queue
- Auto-sync when online
- Offline indicator banner

---

## API Endpoints

### Auth
```
POST /api/auth/register - Create owner account
POST /api/auth/login - Login with phone + PIN
GET  /api/auth/me - Get current user
```

### Products
```
POST /api/products - Create product
GET  /api/products - List products (search, category, low_stock filters)
GET  /api/products/{id} - Get single product
PUT  /api/products/{id} - Update product
DELETE /api/products/{id} - Delete product (owner only)
GET  /api/products/categories/list - Get category names
```

### Sales
```
POST /api/sales - Create sale
GET  /api/sales - List sales (date range, payment method filters)
GET  /api/sales/{id} - Get single sale
```

### Credit Customers
```
POST /api/credit-customers - Create customer
GET  /api/credit-customers - List customers (search, has_balance filters)
GET  /api/credit-customers/{id} - Get customer
PUT  /api/credit-customers/{id} - Update customer
POST /api/credit-customers/payment - Record payment
GET  /api/credit-customers/{id}/history - Get transaction history
```

### Damaged Stock
```
POST /api/damaged-stock - Log damaged item
GET  /api/damaged-stock - List damaged items (date range, reason filters)
```

### M-Pesa (Mock)
```
POST /api/mpesa/stk-push - Initiate STK Push
POST /api/mpesa/confirm/{checkout_id} - Confirm payment
GET  /api/mpesa/status/{checkout_id} - Check status
```

### Reports
```
GET /api/reports/dashboard - Dashboard stats
GET /api/reports/sales - Sales report
GET /api/reports/credit - Credit report
GET /api/reports/damaged - Damaged stock report
GET /api/reports/pdf/sales - Generate sales PDF
GET /api/reports/pdf/credit - Generate credit PDF
GET /api/reports/pdf/damaged - Generate damaged PDF
```

### Users (Owner Only)
```
POST /api/users - Create shopkeeper
GET  /api/users - List users
DELETE /api/users/{id} - Delete shopkeeper
```

### Shop
```
GET /api/shop - Get shop details
PUT /api/shop - Update shop details (owner only)
```

---

## Database Collections (MongoDB)

### users
```json
{
  "id": "uuid",
  "phone": "0712345678",
  "pin_hash": "bcrypt_hash",
  "name": "John Doe",
  "role": "owner|shopkeeper",
  "shop_id": "uuid",
  "trial_ends_at": "ISO_date",
  "subscription_status": "trial|active|expired",
  "created_at": "ISO_date"
}
```

### shops
```json
{
  "id": "uuid",
  "name": "Shop Name",
  "owner_id": "uuid",
  "phone": "optional",
  "address": "optional",
  "created_at": "ISO_date"
}
```

### products
```json
{
  "id": "uuid",
  "name": "Product Name",
  "sku": "SKU-XXXXXXXX",
  "category": "optional",
  "unit_price": 100.0,
  "cost_price": 80.0,
  "stock_quantity": 50,
  "min_stock_level": 5,
  "unit": "piece",
  "shop_id": "uuid",
  "created_at": "ISO_date",
  "updated_at": "ISO_date"
}
```

### sales
```json
{
  "id": "uuid",
  "receipt_number": "RCP-YYYYMMDDHHMMSS-XXXX",
  "items": [
    {
      "product_id": "uuid",
      "product_name": "Name",
      "quantity": 2,
      "unit_price": 100.0,
      "total": 200.0
    }
  ],
  "payment_method": "cash|mpesa|credit",
  "total_amount": 200.0,
  "amount_paid": 200.0,
  "change_amount": 0.0,
  "customer_id": "uuid (for credit)",
  "mpesa_transaction_id": "optional",
  "status": "completed|pending",
  "shop_id": "uuid",
  "created_by": "uuid",
  "created_at": "ISO_date"
}
```

### credit_customers
```json
{
  "id": "uuid",
  "name": "Customer Name",
  "phone": "0712345678",
  "email": "optional",
  "address": "optional",
  "credit_limit": 10000.0,
  "current_balance": 500.0,
  "shop_id": "uuid",
  "created_at": "ISO_date"
}
```

### credit_payments
```json
{
  "id": "uuid",
  "customer_id": "uuid",
  "amount": 500.0,
  "payment_method": "cash",
  "notes": "optional",
  "shop_id": "uuid",
  "created_by": "uuid",
  "created_at": "ISO_date"
}
```

### damaged_stock
```json
{
  "id": "uuid",
  "product_id": "uuid",
  "product_name": "Name",
  "quantity": 5,
  "reason": "damaged|expired|spoiled|other",
  "notes": "optional",
  "shop_id": "uuid",
  "created_by": "uuid",
  "created_at": "ISO_date"
}
```

### mpesa_transactions
```json
{
  "id": "uuid",
  "checkout_request_id": "ws_CO_...",
  "merchant_request_id": "MR_...",
  "sale_id": "uuid",
  "phone": "254...",
  "amount": 100.0,
  "status": "pending|completed",
  "mpesa_receipt": "optional",
  "shop_id": "uuid",
  "created_at": "ISO_date"
}
```

---

## Frontend Pages

1. **LoginPage** - Phone + PIN auth, registration
2. **DashboardPage** - Stats, charts, recent sales, low stock alerts
3. **POSPage** - Product grid, cart, payment modal
4. **ProductsPage** - Product CRUD, stock management
5. **CreditPage** - Customer list, add customer, record payments, view history
6. **DamagedPage** - Log damaged stock, view history
7. **ReportsPage** - Sales/Credit/Damaged reports with PDF export
8. **UsersPage** - User management (owner only)
9. **SettingsPage** - Profile, shop settings, logout

---

## UI/UX Guidelines

- **Mobile-first** design (max-width: 420px primary)
- **Bottom navigation** with: Home, POS, Products, More (menu)
- **Brand colors:** Blue #007BFF (primary), Orange #FF8C00 (secondary)
- **Font:** Outfit (headings), Public Sans (body)
- **Cards** with subtle shadows, rounded corners
- **Toast notifications** for feedback
- **Loading skeletons** for async data
- **Touch-friendly** buttons (min 44px)

---

## Business Rules

1. **Stock Management:**
   - Stock deducted on completed sale
   - Stock deducted on damaged stock logging
   - Low stock alert when quantity ≤ min_stock_level

2. **Credit Sales:**
   - Must select existing credit customer
   - Customer balance increases by sale amount
   - Stock deducted immediately

3. **M-Pesa (Mock):**
   - STK Push initiated, sale status = pending
   - On confirmation, sale status = completed
   - Real integration requires Daraja API credentials

4. **Role Permissions:**
   - Owner: Full access
   - Shopkeeper: No delete products, no user management, no shop settings

---

## Future Enhancements (Backlog)

### P0 - Critical
- Real M-Pesa Daraja API integration
- Subscription payment processing

### P1 - High Priority
- Full offline mode with IndexedDB
- Receipt printing support
- Barcode scanning
- Excel/CSV export

### P2 - Medium Priority
- SMS notifications for credit customers
- Inventory auto-reorder alerts
- Multi-shop support

### P3 - Nice to Have
- WhatsApp integration
- Supplier management
- Profit margin reports
- Mobile app (React Native)

---

## Test Credentials
- **Phone:** 0799123456
- **PIN:** 1234
- **Role:** Owner

---

## Deployment Notes
- Backend runs on port 8001 (internal)
- Frontend runs on port 3000
- All API routes prefixed with `/api`
- Environment variables in `.env` files
- MongoDB connection via MONGO_URL
- JWT secret in backend .env

---

*Generated: January 2024*
*Version: 1.0.0*
