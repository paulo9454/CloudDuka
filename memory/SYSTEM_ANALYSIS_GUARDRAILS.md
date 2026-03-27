# CloudDuka System Analysis & Safe-Advancement Guardrails

## 1) Purpose of the System
CloudDuka is a **cloud-based, mobile-first retail POS platform** targeting small-to-medium shops (especially Kenya/East Africa), with support for:
- Daily POS sales (cash, M-Pesa, credit)
- Inventory/product lifecycle
- Credit customer balances and repayments
- Damaged stock logging
- Shop/user management with role-based controls
- Reporting + PDF export
- Emerging marketplace/order/cart capabilities

The project is effectively two products in one codebase:
1. **Core POS for shops**
2. **Marketplace/customer ordering flows** (cart/order/public store endpoints)

---

## 2) Current Technical Architecture

### Frontend
- React SPA with route-based pages and guarded routes.  
- Zustand stores for auth, cart, and offline sync queue.  
- Mobile-first navigation with owner-only sections.

### Backend
- FastAPI monolith (`backend/server.py`) containing:
  - Data models
  - Auth/authorization helpers
  - All API endpoints
  - Payment integration hooks (mock M-Pesa + Paystack flows)
  - Reports + PDF generation
- MongoDB as primary datastore via Motor async client.

### Data/Domain model (high level)
Core collections implied by APIs/specs:
- users, shops, products, sales
- credit customers + credit transactions
- damaged stock
- suppliers + purchases
- carts + orders + order items + payments

---

## 3) Functional Capability Map (What it does today)

### A. Identity & Access
- Phone + PIN auth with JWT token issuance.
- Role checks for owner/customer/shopkeeper.
- Shop-bound access controls and subscription/trial checks.
- Login rate limiting middleware.

### B. POS Operations
- Product CRUD and category listing.
- Sales recording with stock deduction.
- Payment method handling (cash, credit, M-Pesa paths).
- Receipt-number generation.

### C. Credit Management
- Credit customer CRUD.
- Credit payment recording.
- History and balances.

### D. Inventory Loss Tracking
- Damaged stock entry + retrieval with date/reason filtering.

### E. Business Reporting
- Dashboard statistics
- Sales/Credit/Damaged reports
- PDF report generation endpoints

### F. Extended Commerce/Marketplace
- Supplier and purchase flows
- Internal cart and checkout/order lifecycle
- Customer cart + customer checkout + customer order APIs
- Public product/store listing APIs

### G. Frontend Navigation Coverage
- Protected routes: dashboard, POS, products, credit, orders, damaged, reports, settings.
- Owner routes: users, suppliers, purchases, vendor dashboard, admin dashboard.
- Offline mode indicator and pending-sale auto-sync.

---

## 4) Critical Risks That Can Cause Breakage or Duplication

1. **Monolith concentration risk**  
   `backend/server.py` contains nearly all backend logic. Any cross-cutting change can unintentionally affect multiple domains (POS, payments, reports, orders).

2. **Observed duplicate/overlapping definitions in backend**  
   There are repeated sections (e.g., duplicated `RateLimitMiddleware` declarations and overlapping public endpoint function definitions). This increases risk of shadowing/override bugs and confusion over which implementation is active.

3. **Spec drift risk**  
   PRD/master spec and implementation have diverged in places (e.g., broader marketplace/payment features now present). New work should treat runtime API behavior as source-of-truth and update specs in lockstep.

4. **Role + shop scoping sensitivity**  
   Access logic is central for multi-user safety. Regressions here can expose shop data across tenants.

5. **Offline + sync semantics**  
   Frontend queues pending sales and syncs on reconnect; backend endpoint contract changes can silently break sync.

---

## 5) “Do Not Break / Do Not Duplicate” Advancement Rules

### Rule 1: One endpoint, one owner
Before adding an endpoint:
- Search for existing route path and function intent first.
- Extend existing handler where feasible, rather than adding parallel variants.

### Rule 2: Domain-first placement
When adding backend features:
- Keep related logic grouped by domain section (auth, products, sales, orders, etc.).
- Avoid copy-pasting utility functions across sections; reuse shared helpers.

### Rule 3: Preserve contracts
Treat these as contract-sensitive and update frontend/tests together:
- Auth payload (`token`, `user`, role/shop fields)
- Product and sale schemas
- Credit customer balance fields
- Order/cart status fields

### Rule 4: Enforce role/shop boundaries in every new query
- Always scope tenant data by `shop_id` where applicable.
- Reuse existing authorization dependencies (`require_owner`, `get_current_user`, etc.).

### Rule 5: Keep docs and runtime aligned
Every substantial feature change should include:
- endpoint update
- tests update
- spec/memory docs update
This prevents duplicate “re-implementations” caused by stale docs.

### Rule 6: Prefer additive migrations over replacements
For high-traffic flows (POS/sales/reporting), prefer backward-compatible field additions and deprecations rather than immediate field removal/rename.

---

## 6) Recommended Next Refactor to Reduce Future Duplication

1. Split `backend/server.py` into modules:
   - `api/auth.py`, `api/products.py`, `api/sales.py`, `api/orders.py`, `api/payments.py`, etc.
2. Centralize shared dependencies:
   - auth dependency, tenant scoping, pagination helpers, object-id normalization.
3. Introduce service layer per domain:
   - product service, order service, payment service.
4. Introduce route uniqueness checks in CI:
   - automated assertion for duplicate route paths/function names.
5. Keep a single source API contract (OpenAPI snapshot) and validate frontend assumptions in CI.

---

## 7) Practical Change Checklist (Use before any new feature)
- [ ] I searched for an existing endpoint/handler before adding a new one.
- [ ] I verified role/shop authorization impact.
- [ ] I verified frontend store/API helper compatibility.
- [ ] I added/updated tests for the changed flow.
- [ ] I updated docs/spec notes to avoid future duplicate work.
- [ ] I checked for similarly named or duplicate functions after edits.

---

## 8) Bottom Line
CloudDuka’s purpose is to be a complete retail operating system (sales + stock + credit + reporting + payments), now expanding toward marketplace ordering. The biggest stability risk is not missing features—it is **duplicative and overlapping implementation in a single large backend file**. Safe advancement means: extend existing flows, keep contracts stable, enforce tenant/role boundaries, and update tests/docs together.
