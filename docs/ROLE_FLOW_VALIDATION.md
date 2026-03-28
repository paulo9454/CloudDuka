# Role Flow Validation Report

This report maps requested business flows to existing automated coverage and current platform behavior.

## 1) Authentication, registration, and login JSON responses

### Owner login
- Covered by auth/login tests for valid + invalid credentials.
- Result: JSON responses and auth token/user payload are returned as expected for valid login and validation errors for invalid login.

### Customer registration + login
- Covered by tests asserting customer role defaults, sanitized payloads, and restricted access to owner-only routes.
- Result: Customer registration/login flows are healthy; customer role isolation is enforced.

## 2) Shop creation, ownership, and shopkeeper allocation

### Owner creates/manages shop context
- Covered in shop and membership-related tests and order/status authorization tests.
- Result: Owner has shop-scoped control over catalog/orders and subscription updates.

### Shopkeeper allocation
- Covered by shopkeeper helper/login + order status update authorization tests.
- Result: Shopkeepers can perform allowed operational actions while respecting scope.

## 3) Sales, stock, and inventory

### Product + stock operations
- Covered by product create/list/update-stock tests and insufficient-stock checkout/cart validations.
- Result: Inventory quantities update correctly and stock limits are enforced at checkout/cart boundaries.

### Sales and payment processing
- Covered by checkout, payment status transitions, credit sale and credit payment history tests.
- Result: Sales records, payment states, and balances update with expected JSON responses.

## 4) Customer shopping journey

### Marketplace to cart to checkout
- Covered by customer cart add/get/update/remove tests and customer checkout tests (success, empty cart, stock failure, mixed shop failure).
- Result: End-to-end customer shopping journey is validated server-side, including order creation and cart cleanup.

### Customer order history
- Covered by customer orders listing/detail/pagination/access-control tests.
- Result: Customers can only access their own orders; pagination and ordering behaviors are validated.

## 5) Subscription behavior (POS vs online store)

### POS-only vs online gating
- Covered by subscription feature gating tests for public stores and customer checkout behavior.
- Result:
  - Online plan enables storefront/public surface area.
  - POS-only plan blocks online-only checkout paths where expected.
  - Legacy shop compatibility logic prevents false blocking for shops missing embedded subscription payloads.

## 6) Vendor/admin/shop model and actor fit

### Intended actor model
- **Owner/Admin/Partner**: creates and manages shops, products, subscriptions, staff.
- **Shopkeeper**: operational role delegated within owner-controlled scope.
- **Customer**: shops via public storefront and customer cart/checkout.

This aligns with the requested model: merchants create shops and customers shop from those stores.

## 7) Facebook login/share and Glovo-like social/aggregator integrations

- Current repository test and backend route coverage do **not** include native Facebook OAuth login, Facebook share posting, or Glovo partner marketplace integration endpoints.
- Status: **not currently implemented/covered** in this codebase.
- Recommendation: treat these as separate feature epics (OAuth provider integration + social share endpoint + external marketplace adapter) with dedicated API contracts and tests.
