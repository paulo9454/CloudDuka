#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-staging"
SCREENSHOT_DIR="${ROOT_DIR}/screenshots"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_PORT="3000"
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
DB_NAME="${DB_NAME:-cloudduka_staging}"
DROP_STAGING_DB="${DROP_STAGING_DB:-1}"

log() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

cleanup() {
  set +e
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$ROOT_DIR"
mkdir -p "$SCREENSHOT_DIR"

log "Creating Python virtual environment at ${VENV_DIR}"
python -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

log "Upgrading pip and installing backend requirements"
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

export MONGO_URL DB_NAME
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"

if [[ "$DROP_STAGING_DB" == "1" ]]; then
  log "Seeding staging database with a clean reset"
  python backend/seed_staging.py --drop-existing
else
  log "Seeding staging database without dropping existing data"
  python backend/seed_staging.py
fi

log "Running backend pytest suite"
pytest -q backend/tests

log "Installing frontend dependencies"
pushd frontend >/dev/null
npm install

log "Building React frontend"
npm run build
log "Ensuring Playwright Chromium is available"
npx playwright install chromium
popd >/dev/null

log "Starting FastAPI backend on http://${BACKEND_HOST}:${BACKEND_PORT}"
uvicorn backend.server:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" > /tmp/cloudduka-backend.log 2>&1 &
BACKEND_PID=$!

log "Starting static frontend on http://${BACKEND_HOST}:${FRONTEND_PORT}"
pushd frontend >/dev/null
npx serve -s build -l "$FRONTEND_PORT" > /tmp/cloudduka-frontend.log 2>&1 &
FRONTEND_PID=$!
popd >/dev/null

log "Waiting for backend and frontend to become ready"
until curl -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" >/dev/null; do sleep 1; done
until curl -fsS "http://${BACKEND_HOST}:${FRONTEND_PORT}" >/dev/null; do sleep 1; done

log "Requesting owner token for screenshot automation"
AUTH_JSON="$(curl -fsS -X POST "http://${BACKEND_HOST}:${BACKEND_PORT}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"phone":"0712345678","pin":"1234"}')"
export AUTH_JSON
export FRONTEND_URL="http://${BACKEND_HOST}:${FRONTEND_PORT}"
export SCREENSHOT_DIR

log "Capturing Playwright screenshots"
node <<'EOF_NODE'
const fs = require('fs');
const path = require('path');
const { chromium } = require('./frontend/node_modules/playwright');

(async () => {
  const auth = JSON.parse(process.env.AUTH_JSON);
  const screenshotDir = process.env.SCREENSHOT_DIR;
  const frontendUrl = process.env.FRONTEND_URL;
  const persistedAuth = {
    state: {
      token: auth.token,
      user: auth.user,
      isAuthenticated: true,
      isLoading: false,
      error: null,
    },
    version: 0,
  };

  const pages = [
    { route: '/dashboard', file: 'owner-dashboard.png' },
    { route: '/vendor-dashboard', file: 'vendor-dashboard.png' },
    { route: '/admin-dashboard', file: 'admin-dashboard.png' },
    { route: '/purchases', file: 'marketplace-orders.png' },
  ];

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  await context.addInitScript((payload) => {
    window.localStorage.setItem('cloudduka-auth', JSON.stringify(payload));
  }, persistedAuth);

  for (const entry of pages) {
    const page = await context.newPage();
    console.log(`[screenshots] Opening ${entry.route}`);
    await page.goto(`${frontendUrl}${entry.route}`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: path.join(screenshotDir, entry.file), fullPage: true });
    await page.close();
  }

  await browser.close();
})();
EOF_NODE

log "Screenshots saved to ${SCREENSHOT_DIR}"
log "Staging automation complete"
