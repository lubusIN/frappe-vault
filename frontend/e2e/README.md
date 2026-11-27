# Frappe Vault Frontend & E2E Tests

## Test Layers

1. **Unit & Component Tests (Vitest + Vue Test Utils)**
   - Location: `frontend/src/__tests__/`
   - Runs fast in `jsdom` with mocked `frappe-ui` (no live bench required).
   ```bash
   cd frontend
   yarn test
   # Watch mode
   yarn test:watch
   ```

2. **End-to-End Browser Tests (Playwright)**
   - Location: `frontend/e2e/`
   - Runs against any live Frappe bench or site URL via `BASE_URL`.
   - Test suites:
     - `auth.setup.js` — Authenticates via `/api/method/login` and saves session state (`e2e/.auth/admin.json`).
     - `01-navigation.spec.js` — Sidebar routes & mobile viewport layout.
     - `02-secrets-totp.spec.js` — Secret lifecycle, password reveal, and TOTP 6-digit code generation.
     - `03-security-boundaries.spec.js` — Guest & `Vault User` security checks (TOTP masking, REST privilege escalation blocks).
     - `04-folders.spec.js` — Root & nested folder creation, secret placement, and reparenting.
     - `05-sharing-permissions.spec.js` — Admin → User A → User B sharing matrix (`View Only`, `Edit` preserving TOTP, `Full Control`, and `Revoke`).
     - `06-admin-settings.spec.js` — Vault Admin vs standard `Vault User` route isolation.

## Running Playwright E2E

First-time browser setup:
```bash
cd frontend
npx playwright install chromium
```

Run against any running Frappe site by passing `BASE_URL` (and credentials if different from `Administrator` / `admin`):
```bash
# Headless run (Desktop + Mobile Chrome)
BASE_URL=http://localhost:8000 ADMIN_USER=Administrator ADMIN_PASS=admin yarn test:e2e

# Watch in a visible Chrome window (Desktop Chrome)
BASE_URL=http://localhost:8000 ADMIN_USER=Administrator ADMIN_PASS=admin yarn test:e2e:headed --project=setup --project=chromium

# Slow-motion Chrome (700ms pause between actions)
BASE_URL=http://localhost:8000 SLOW_MO=700 yarn test:e2e:headed --project=setup --project=chromium

# Interactive Playwright UI (step-by-step timeline & DOM inspector)
BASE_URL=http://localhost:8000 yarn test:e2e:ui

# View last HTML report
yarn test:e2e:report
```
