# KESCO Integration — Complete Documentation

## Overview

KESCO (Kosovo Electric Company) integration fetches utility bills from the KESCO portal API and stores them as `MeterLedger` records in the building management system. This allows tracking of electricity expenses per meter for tenant reimbursement.

---

## KESCO API

### Login (requires captcha)

```
POST https://fatura.kesco-energy.com/api/TokenAuth/login
Content-Type: application/json

{
  "Username": "1001324418",
  "Password": "a8TXMD7aAQkxg@T",
  "RememberMe": true,
  "CaptchaResponse": "..."
}
```

Response:
```json
{
  "State": 1,
  "Data": {
    "requertAt": "2026-04-25T19:07:08.290688+02:00",
    "expiresIn": 604800.0,
    "tokeyType": "Bearer",
    "accessToken": "eyJhbGci...",
    "refreshToken": "CIBqoZne..."
  }
}
```

**Token expires in 604800 seconds (7 days).**

### Fetch Debitor Accounts

```
GET https://fatura.kesco-energy.com/api/Account/user-debitors
Authorization: Bearer eyJhbGci...
```

Response:
```json
{
  "State": 1,
  "Data": {
    "debitors": [{
      "UserId": "cf99fe01-b332-48cd-a73a-54be398826c5",
      "AgencyId": "DFE",
      "ElDebitorId": 160,
      "FullName": "Avni Hetem Ademi",
      "DebitorAddress": "Rizah Matoshi 1. Ferizaj - FERIZAJI",
      "TariffGroup": "4/02",
      "IsAMR": false,
      "LastDueDate": "2026-04-12T00:00:00",
      "TotalDebt": 111.75
    }]
  }
}
```

### Token Handling

- Captured via user login (captcha solved manually)
- Pasted into Django credential form with username + token + user_id
- Stored in `KescoCredential` model with 7-day expiry tracking
- Sync command loads tokens from DB, attempts auto-refresh on expiry

---

## Database Models

### `KescoCredential` (locations/models.py)

| Field | Type | Description |
|-------|------|-------------|
| `username` | CharField(255) | KESCO account ID (e.g. `1001324418`) |
| `password` | CharField(500) | KESCO password (used for auto-refresh attempts) |
| `user_id` | CharField(255) | JWT user ID (e.g. `cf99fe01-b332-...`) |
| `bearer_token` | TextField | Current valid access token |
| `token_obtained_at` | DateTimeField | When token was captured |
| `token_expires_at` | DateTimeField | Token expiry (7 days from obtain) |
| `last_sync_at` | DateTimeField | Last successful sync timestamp |
| `last_sync_status` | CharField(50) | Status message (e.g. "Success", "Token expired...") |
| `is_active` | BooleanField | Enable/disable credential |

### `Meter` — KESCO Fields (locations/models.py)

| Field | Type | Description |
|-------|------|-------------|
| `kesco_debitor_id` | CharField(100) | Links meter to KESCO `ElDebitorId` (e.g. `160`) |
| `kesco_agency_id` | CharField(50) | KESCO `AgencyId` (e.g. `DFE`) |
| `kesco_full_name` | CharField(255) | KESCO `FullName` |
| `kesco_address` | CharField(500) | KESCO `DebitorAddress` |
| `kesco_tariff_group` | CharField(100) | KESCO `TariffGroup` (e.g. `4/02`) |
| `kesco_last_due_date` | DateField | KESCO `LastDueDate` |

**Meter name convention:** `AgencyId` + `ElDebitorId` → `DFE160`

### `MeterLedger` — KESCO Updates

| Field | Source |
|-------|--------|
| `meter` | Matched via `kesco_debitor_id` on Meter |
| `month` / `year` | Extracted from KESCO `LastDueDate` |
| `billed_amount` | KESCO `TotalDebt` |
| `settled_at` | Set when `TotalDebt` = 0 |

---

## Sync Command

**File:** `locations/management/commands/sync_kesco_meters.py`

```bash
# Run once
python manage.py sync_kesco_meters --once

# Run continuously (every 3 days by default)
python manage.py sync_kesco_meters --loop
```

### Behavior

1. Loads credentials from DB (`KescoCredential`), falls back to env vars
2. For each credential:
   - Checks token validity → auto-refreshes via API login if expired
   - If captcha required → skips with warning
   - **Sleeps 3–10 seconds (random)**
   - Fetches `/api/Account/user-debitors`
   - For each debitor:
     - **Sleeps 3–10 seconds (random)**
     - Looks up meter by `kesco_debitor_id`
     - Falls back to orphan match (`serial_number="KESCO-{id}"`)
     - Creates new meter under Location 0 if not found
     - Merges orphan ledgers into linked meter if both exist
     - Updates KESCO fields on meter (name, address, tariff, etc.)
     - Upserts `MeterLedger` on `(meter, month, year)`
   - Updates `last_sync_at` and `last_sync_status`

### Meter Matching Priority

1. **Explicit link:** `Meter.kesco_debitor_id == ElDebitorId`
2. **Orphan fallback:** `Meter.serial_number == "KESCO-{ElDebitorId}"`
3. **Create new:** Under "Location 0 - Unassigned KESCO Meters"

### Rate Limiting

- Random sleep 3–10 seconds before each API request
- Random sleep 3–10 seconds between each debitor processing
- Random sleep 3–10 seconds between each account in multi-credential setup

---

## Web UI

### KESCO Dashboard (`/locations/kesco/`)

- Stats: KESCO meters count, total meters, active credentials
- Credential list with token validity, last sync status
- "Sync Now" per credential, "Sync All" button
- Recent meter ledgers table

### Credential Form (`/locations/kesco/credentials/create/`)

Fields:
- **Username / Account ID** (required)
- **Password** (optional — for future auto-refresh)
- **Bearer Token** (textarea — paste full token from KESCO login response)
- **User ID** (optional — from JWT `nameid` or login response)

### Credential Detail

- Shows token validity, expiry date, status, last sync time
- "Sync Now" button if token valid
- "Edit" link to update fields

### Sidebar Link

"KESCO Integration" → "KESCO Dashboard" under Location Management group.

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/locations/kesco/` | KESCO dashboard |
| GET | `/locations/kesco/credentials/` | Credential list |
| POST | `/locations/kesco/credentials/create/` | Create credential |
| GET | `/locations/kesco/credentials/<uuid>/edit/` | Edit form |
| POST | `/locations/kesco/credentials/<uuid>/delete/` | Delete credential |
| GET | `/locations/kesco/credentials/<uuid>/` | Credential detail |
| POST | `/locations/kesco/credentials/<uuid>/trigger-sync/` | Sync one credential |
| POST | `/locations/kesco/trigger-sync-all/` | Sync all credentials |
| POST | `/locations/kesco/api/capture-token/` | CSRF-exempt token submission |

### Capture Token API

```bash
curl -X POST http://localhost:8800/locations/kesco/api/capture-token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"1001324418","token":"eyJhbGci...","user_id":"cf99fe01-..."}'
```

Response:
```json
{"message": "Token saved for 1001324418", "expires_at": "2026-05-02T20:35:56+00:00"}
```

---

## Docker Services

### `kesco-sync` (background worker)

Runs under `integrations` profile. Starts automatically with:

```bash
docker compose --profile integrations up -d kesco-sync
```

**Environment:**
- `KESCO_SYNC_INTERVAL_SECONDS=259200` (default: 3 days)

**Stop:**
```bash
docker compose --profile integrations stop kesco-sync
```

---

## Files Changed

| File | Change |
|------|--------|
| `locations/models.py` | Added `KescoCredential`, `Meter` KESCO fields |
| `locations/kesco_views.py` | KESCO CRUD views, token capture API |
| `locations/management/commands/sync_kesco_meters.py` | DB credential loading, debitor matching, rate limiting |
| `locations/management/commands/cleanup_kesco_orphans.py` | Orphan meter cleanup utility |
| `locations/forms.py` | `MeterForm` with KESCO fields |
| `locations/urls.py` | KESCO routes |
| `locations/templates/locations/kesco/` | Dashboard, credential form/list/detail templates |
| `locations/migrations/0010_kescocredential.py` | KESCO credential model |
| `locations/migrations/0011_meter_kesco_debitor_id.py` | Debitor ID field |
| `locations/migrations/0012_meter_kesco_address_*.py` | KESCO detail fields |
| `templates/base.html` | KESCO sidebar menu |
| `config/settings/base.py` | `X_FRAME_OPTIONS = 'SAMEORIGIN'` |
| `docker-compose.yml` | `kesco-sync` service, 3-day interval |
| `locale/sq/LC_MESSAGES/django.po` | "Covered" → "E mbuluar" translation |

---

## Next Task: RBAC Hardening + WAF

Pending: Role-based access control hardening and Web Application Firewall configuration.
