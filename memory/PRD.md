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

## Pricing Model (Updated Jan 2025)
- Monthly: KES 300
- Annual: KES 3,000 (17% savings)
- Free Trial: 14 Days

---

## What's Been Implemented

### Core Features
- [x] JWT Authentication with Phone + PIN
- [x] Two user roles: Owner and Shopkeeper
- [x] Product/Stock Management (CRUD)
- [x] POS System with Cart
- [x] Three Payment Methods: Cash, M-Pesa (Mock), Credit
- [x] Credit Customer Management (Persistent, System-wide)
- [x] Damaged/Spoiled Stock Tracking
- [x] Sales Reports with Date Range
- [x] PDF Export (Sales, Credit, Damaged reports)
- [x] User Management (Owner only)
- [x] Shop Settings
- [x] Basic Offline Support (localStorage caching)
- [x] Mobile-first responsive design

### Product Entry Features (Jan 2025)
- [x] Unit types: Single, Packet, Dozen
- [x] Auto-calculation of total stock units for Packet/Dozen purchases
- [x] Auto-calculation of cost per unit
- [x] Stock field locked when buying in bulk (Packet/Dozen)
- [x] Optional free-text category with autocomplete

### Credit Customer Features (Jan 2025)
- [x] Persistent credit customers stored in MongoDB
- [x] System-wide availability (Credit Page, POS dropdown)
- [x] Balance tracking with automatic updates
- [x] Transaction history (sales + payments)
- [x] Credit limit management
- [x] Payment recording with notes

### Dashboard Features (Jan 2025)
- [x] 4 main action buttons (New Sale, Credit Sale, Today's Sales, Stock)
- [x] Today's Summary with Cash/M-Pesa/Credit breakdown
- [x] Low Stock Alert section
- [x] Total Sales Today
- [x] Credit Outstanding display

### Technical Stack
- **Backend:** FastAPI with MongoDB
- **Frontend:** React with Tailwind CSS, shadcn/ui
- **Auth:** JWT tokens
- **State:** Zustand
- **Charts:** Recharts
- **PDF:** fpdf (backend), jspdf (frontend)

### API Endpoints
- `/api/auth/*` - Register, Login, Profile
- `/api/products/*` - CRUD operations
- `/api/products/categories/list` - Simple category list
- `/api/sales/*` - Create and list sales
- `/api/credit-customers/*` - Customer management + history + payments
- `/api/damaged-stock/*` - Track stock losses
- `/api/reports/*` - Dashboard, sales, credit, damaged reports
- `/api/mpesa/*` - Mock STK Push (simulation mode)
- `/api/users/*` - User management (owner only)
- `/api/shop` - Shop settings

---

## Prioritized Backlog

### P0 - Critical (Next Sprint)
- [ ] **Bundle Pricing** - Add optional bundle pricing (e.g., 3 units for 50 KES) with bundle-only toggle
- [ ] **DB-backed Categories** - Replace free-text with dropdown from database CRUD
- [ ] Real M-Pesa Daraja API integration

### P1 - High Priority
- [ ] Multi-shop support (owner can manage multiple shops)
- [ ] Add CloudDuka logo to dashboard header
- [ ] Full offline mode with IndexedDB + background sync
- [ ] Receipt printing support
- [ ] Barcode scanning for products
- [ ] Excel/CSV export alongside PDF

### P2 - Medium Priority
- [ ] SMS notifications for credit customers
- [ ] Inventory low stock auto-reorder alerts
- [ ] Customer loyalty points

### P3 - Nice to Have
- [ ] WhatsApp integration for receipts
- [ ] Supplier management
- [ ] Profit margin reports
- [ ] Mobile app (React Native)

---

## Mocked Integrations
- **M-Pesa Daraja API**: Currently simulated with mock endpoints
  - `/api/mpesa/stk-push` - Simulates STK Push request
  - `/api/mpesa/confirm/{checkout_request_id}` - Simulates payment confirmation

---

## Test Credentials
- **Phone:** 0712345678
- **PIN:** 1234

---

## Last Updated: January 30, 2025
