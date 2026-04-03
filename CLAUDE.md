# QuickBooks Project — Claude Context

**Company:** Curtis Painting and Remodeling (Nik Curtis)
**Goal:** QuickBooks Online integration — create invoices and estimates from plain-text job notes

---

## Current Status (2026-03-23)

### ✅ Phase 1 Complete — Auth & Sandbox Connected
- Developer app created: **Curtis Painting Integration** (AppID: `7d846630-3fd6-4629-a56c-da367278cbb9`)
- Sandbox realm ID: `9341456664410884`
- OAuth 2.0 flow working — tokens saved to `tokens/qbo_token.json`
- `test_connection.py` passed all checks — company info and customers retrieved from sandbox
- Redirect URI `http://localhost:8080/callback` added to app settings

### 🔲 Phase 2 — Next Up: Invoice Creation
Build `create_invoice.py`:
- Look up or create a customer by name in QBO
- Map line items to QBO invoice format
- POST to QBO API → return invoice ID + link
- Test against sandbox first

### 🔲 Phase 3 — Text Parsing
Build `parse_estimate.py`:
- Takes raw job note text as input
- Calls Claude API to extract structured JSON (customer, line items, total, deposit)
- Returns validated JSON for use in `create_invoice.py`

### 🔲 Phase 4 — Wire Together
- `main.py` or Discord `quickbooks` channel handles the full flow
- Accept job description → parse → confirm → create invoice

---

## Project Structure

```
QuickBooks Project/
├── CLAUDE.md               ← this file
├── .env                    ← API credentials (sandbox)
├── .env.example            ← template (no secrets)
├── requirements.txt        ← requests, python-dotenv
├── auth_qbo.py             ← OAuth 2.0 flow + token save/load/refresh
├── test_connection.py      ← sandbox connectivity test (PASSING ✅)
├── tokens/
│   └── qbo_token.json      ← saved OAuth tokens (do not commit)
```

**Coming:**
```
├── create_invoice.py       ← QBO API: JSON → invoice
├── parse_estimate.py       ← Claude API: text → structured JSON
└── main.py                 ← entry point / orchestrator
```

---

## Key Technical Notes

### Libraries
- `requests` — all HTTP (QBO API + OAuth token exchange)
- `python-dotenv` — credential management
- **Note:** `intuitlib` and `python-quickbooks` are NOT used — both removed from PyPI

### Auth Flow (auth_qbo.py)
- `get_tokens()` — returns valid token dict, handles refresh automatically
- `api_get(path, tokens)` — helper for QBO REST API GET calls
- Token exchange endpoint: `https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer`
- Auth URL: `https://appcenter.intuit.com/connect/oauth2`

### QBO API (Sandbox)
- Base URL: `https://sandbox-quickbooks.api.intuit.com/v3/company/{realmId}/`
- Auth: `Bearer {access_token}` header
- Format: JSON (`Accept: application/json`)
- Query endpoint: `GET /query?query=SELECT * FROM {Entity}`
- Create endpoint: `POST /{entity}` with JSON body

### Credentials (.env)
```
QBO_CLIENT_ID=ABjdgbYBZSMKFWSf1lB84jxBOGpMPeuPOOc9jDBP5tVu6TWrxy
QBO_CLIENT_SECRET=oQEbFC7pqBPLQWiSk9PQr4U4f9zfmlOnVLJhk4Cd
QBO_REDIRECT_URI=http://localhost:8080/callback
QBO_ENVIRONMENT=sandbox
QBO_REALM_ID=9341456664410884
```
Switch `QBO_ENVIRONMENT=production` and add production keys when ready to go live.

### Running Scripts
Initial auth requires a browser — run on **laptop** (N:\Claude\QuickBooks Project):
```
C:\Users\nikcu\venvs\qb-venv\Scripts\Activate.ps1
python test_connection.py
```
Token refresh is headless — can run on NUC after initial auth.

### venv Location
- **Laptop:** `C:\Users\nikcu\venvs\qb-venv\` (local, not on NAS)
- NAS path: `N:\Claude\QuickBooks Project\`

---

## Invoice Data Model (target)
```json
{
  "customer": {
    "name": "Sarah Miller",
    "address": "456 Elm St"
  },
  "line_items": [
    { "description": "Interior painting - living room", "amount": 1800.00 },
    { "description": "Materials & supplies", "amount": 400.00 }
  ],
  "total": 2200.00,
  "deposit": {
    "required": true,
    "amount": 1100.00,
    "due": "on start"
  },
  "notes": "Job approved 2026-03-23, starts Monday"
}
```

---

## Discord Channel
- Channel: `#quickbooks` (ID: `1485627685496684676`)
- Memory: `/mnt/nas/discord/channels/quickbooks/memory.md`
- Tools available: read_file, write_file, run_shell, get_system_stats, list_services, read_nas_file, update_memory_section, append_error_log
