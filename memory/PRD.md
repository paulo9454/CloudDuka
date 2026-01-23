# CloudDuka Retail POS - Product Requirements Document

## Overview
CloudDuka is a cloud-based, mobile-first POS system designed for retail shops in Kenya/East Africa. It supports retail unit sales, M-Pesa payments, credit customers, stock management, and damaged/spoiled product tracking.

## Brand Identity
- **Name:** CloudDuka
- **Tagline:** Your Retail POS in the Cloud
- **Brand Colors:** Blue #007BFF, Orange #FF8C00
- **Author:** Mosetech Solution

## User Personas
1. **Shop Owner** - Full system access including stock, users, reports, and settings
2. **Shopkeeper** - Sales, M-Pesa payments, and credit sales only

## Pricing Model
- Monthly: KES 499
- Annual: KES 5,000 (17% savings)
- Free Trial: 14 Days

---

## What's Been Implemented (January 2024)

### Core Features
- [x] JWT Authentication with Phone + PIN
- [x] Two user roles: Owner and Shopkeeper
- [x] Product/Stock Management (CRUD)
- [x] POS System with Cart
- [x] Three Payment Methods: Cash, M-Pesa (Mock), Credit
- [x] Credit Customer Management
- [x] Damaged/Spoiled Stock Tracking
- [x] Sales Reports with Date Range
- [x] PDF Export (Sales, Credit, Damaged reports)
- [x] User Management (Owner only)
- [x] Shop Settings
- [x] Basic Offline Support (localStorage caching)
- [x] Mobile-first responsive design

### Technical Stack
- **Backend:** FastAPI with MongoDB
- **Frontend:** React with Tailwind CSS, shadcn/ui
- **Auth:** JWT tokens
- **State:** Zustand
- **Charts:** Recharts
- **PDF:** jspdf + jspdf-autotable

### API Endpoints
- `/api/auth/*` - Register, Login, Profile
- `/api/products/*` - CRUD operations
- `/api/sales/*` - Create and list sales
- `/api/credit-customers/*` - Customer management
- `/api/damaged-stock/*` - Track stock losses
- `/api/reports/*` - Dashboard, sales, credit, damaged reports
- `/api/mpesa/*` - Mock STK Push (simulation mode)
- `/api/users/*` - User management (owner only)
- `/api/shop` - Shop settings

---

## Prioritized Backlog

### P0 - Critical (Next Sprint)
- [ ] Real M-Pesa Daraja API integration
- [ ] Subscription/Payment processing for KES 499/5000

### P1 - High Priority
- [ ] Full offline mode with IndexedDB + background sync
- [ ] Receipt printing support
- [ ] Barcode scanning for products
- [ ] Excel/CSV export alongside PDF

### P2 - Medium Priority
- [ ] SMS notifications for credit customers
- [ ] Inventory low stock auto-reorder alerts
- [ ] Multi-shop support
- [ ] Customer loyalty points

### P3 - Nice to Have
- [ ] WhatsApp integration for receipts
- [ ] Supplier management
- [ ] Profit margin reports
- [ ] Mobile app (React Native)

---

## Next Action Items
1. Obtain M-Pesa Daraja API credentials for real integration
2. Implement Stripe/PayPal for subscription payments
3. Add IndexedDB for robust offline support
4. Implement receipt thermal printer support
