# CloudDuka

## Repository structure
- `backend/` – backend application code and APIs.
- `frontend/` – frontend React application.
- `tests/` – automated integration and utility tests.
- `docs/ARCHITECTURE.md` – end-to-end architecture and flow documentation.
- `docs/ROLE_FLOW_VALIDATION.md` – role-based flow validation and coverage report.
- `run_staging.sh` – helper script for a staging workflow.

## Prerequisites
- Node.js 20 LTS (recommended) and npm 10+.
- Git.
- Optional: Python 3.10+ for backend/testing scripts.

## Quick Start
```bash
git clone <your-repo-url>
cd CloudDuka

# Backend
pip install -r backend/requirements.txt

# Frontend
cd frontend
npm install

# Start backend (auto seeds DB)
cd ..
uvicorn backend.server:app

# Start frontend
cd frontend
npm start
```

Notes:
- No manual database setup is required for demo/sample data; backend startup auto-seeds when products and vendors are empty.
- MongoDB must be running locally on `localhost:27017` (or update `MONGO_URL` in `.env`).

### Faker Marketplace Seeding
Install faker in backend environment:
```bash
pip install faker
```

Run manual realistic seeding:
```bash
python seed_faker.py
```

This inserts realistic fake categories, vendors, users, and products for marketplace testing.

### Role-based Realistic Workflow Seed
Run:
```bash
python seed_realistic.py
```

This creates a realistic workflow dataset with owners, shops/packages (POS/Online/Plus), shopkeepers, vendors/suppliers, customers, inventory, and sample POS + online orders with stock reduction.
It also seeds rider assignments, delivery tracking, location-based customer shop recommendations, subscriptions, and Paystack/Cash/Mpesa/Credit payment records.

Optional large dataset expansion:
```bash
python seed_realistic.py --faker-expand
```
This appends additional Faker-based customers/vendors/products for load and QA testing without overwriting deterministic baseline records.

## Local setup
1. Clone the repository and enter it:
   ```bash
   git clone <your-repo-url>
   cd CloudDuka
   ```
2. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   ```

## Detailed local testing guide (Windows + Ubuntu)

### Windows (PowerShell)

#### 1) Verify prerequisites
```powershell
node -v
npm -v
git --version
```
Expected:
- Node version returns v20.x (or newer supported version).
- npm version returns 10.x (or newer).

#### 2) Install dependencies
```powershell
cd frontend
npm install
```
Expected:
- No `ERR!` lines at the end.
- `added ... packages` / `up to date` summary is shown.

#### 3) Run unit tests
```powershell
npm test -- --watchAll=false --passWithNoTests
```
Expected:
- Command exits successfully.
- If there are no tests yet, Jest reports `No tests found` but does not fail.

#### 4) Build production bundle
```powershell
npm run build
```
Expected:
- Build finishes successfully.
- `frontend/build` output is generated.

#### 5) Start app locally and smoke test
```powershell
npm start
```
Open `http://localhost:3000` and validate:
1. Home/marketplace loads without crashing.
2. Product cards render even if some data fields are missing.
3. Add at least one product to cart.
4. Cart badge updates in header/bottom nav.
5. Open cart page and change item quantity.
6. Proceed to checkout page.
7. Submit checkout and confirm success page navigation.
8. Return from success page and verify cart is cleared (or reflects expected state).

---

### Ubuntu (Terminal)

#### 1) Install prerequisites
```bash
sudo apt update
sudo apt install -y curl git build-essential
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```
Verify:
```bash
node -v
npm -v
git --version
```

#### 2) Install dependencies
```bash
cd frontend
npm install
```

#### 3) Run unit tests
```bash
npm test -- --watchAll=false --passWithNoTests
```

#### 4) Run production build
```bash
npm run build
```

#### 5) Run local app
```bash
npm start
```
Open `http://localhost:3000` in browser and run the same checkout smoke test:
- Browse marketplace.
- Add item to cart.
- Validate cart badge count.
- Edit/remove cart item.
- Complete checkout.
- Confirm success page and post-checkout state.

## Troubleshooting
- If `npm install` fails with lockfile issues, remove `node_modules` and retry:
  ```bash
  rm -rf node_modules package-lock.json
  npm install
  ```
- If port 3000 is busy, run:
  ```bash
  npm start -- --port 3001
  ```
- If tests hang in CI-like environments, enforce non-watch mode:
  ```bash
  npm test -- --watchAll=false
  ```
- If `npm install` fails with `403 Forbidden` due proxy policy in locked-down environments, temporarily unset proxy variables for the install command:
  ```bash
  env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
    -u npm_config_http_proxy -u npm_config_https_proxy \
    -u YARN_HTTP_PROXY -u YARN_HTTPS_PROXY \
    npm install
  ```

## Notes for contributors
- Run tests and build before opening a pull request.
- Keep changes focused and include a concise summary in commits.
