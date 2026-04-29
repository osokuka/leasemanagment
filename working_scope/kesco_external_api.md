# External API Usage

## Purpose

Use these APIs from external tools to:

- Insert or update KESCO meters and their monthly ledger standings.
- Read lease debt status and search leases.
- Generate or email an on-demand report for one lease.
- Settle lease payments and electric meter debts for a specific period.

The APIs are intentionally least-privilege. Use a separate scoped key for each integration need.

## API Key Management

Open the user edit page in the web app:

```text
Users -> Edit User -> KESCO API Keys
```

From there you can:

- Generate a new key for the selected user.
- Choose the narrowest scope needed by the tool.
- Copy the raw key from the success message. It is shown only once.
- Revoke old keys so they can no longer authenticate.

The database stores only a hash of the key.

Available scopes:

| Scope | Purpose |
|---|---|
| `kesco_meter_write` | Insert/update KESCO meters and meter ledgers |
| `lease_report_read` | Read lease debt status and send lease reports |
| `settlement_write` | Settle lease payments and electric meter debts |

## Authentication

All API endpoints accept either header:

```http
X-API-Key: bmgm_your_key_here
```

or:

```http
Authorization: Bearer bmgm_your_key_here
```

## KESCO Meter Upsert API

Required scope:

```text
kesco_meter_write
```

Endpoint:

```http
POST /locations/api/kesco/meters/upsert/
Content-Type: application/json
X-API-Key: bmgm_your_key_here
```

### Raw KESCO Payload

The endpoint accepts the KESCO `user-debitors` response shape directly:

```json
{
  "Data": {
    "debitors": [
      {
        "AgencyId": "DFE",
        "ElDebitorId": 160,
        "FullName": "Consumer Name",
        "DebitorAddress": "Consumer Address",
        "TariffGroup": "4/02",
        "LastDueDate": "2026-04-12T00:00:00",
        "TotalDebt": 111.75,
        "MeterReading": "1234.50"
      }
    ]
  }
}
```

It also accepts:

```json
{"debitors": [...]}
```

```json
{"meters": [...]}
```

```json
[{...}, {...}]
```

or a single meter object.

### Write Behavior

For each debitor/meter item:

1. Match an existing meter by `ElDebitorId` -> `Meter.kesco_debitor_id`.
2. If no match exists, create a new electric meter in:

```text
Location 0 - Unassigned KESCO Meters
  -> Unassigned KESCO Meters
```

3. Update meter metadata:

- `name`: `AgencyId + ElDebitorId`, for example `DFE160`
- `kesco_debitor_id`
- `kesco_agency_id`
- `kesco_full_name`
- `kesco_address`
- `kesco_tariff_group`
- `kesco_last_due_date`

4. Upsert a `MeterLedger` by `(meter, month, year)`.

Ledger mapping:

| API field | App field |
|---|---|
| `LastDueDate` | ledger `month` / `year` |
| `TotalDebt` | `billed_amount` |
| `MeterReading`, `Reading`, `reading`, `meter_reading`, `ActiveEnergy` | `reading` |

If `TotalDebt` is `0`, the ledger is marked settled with today as `settled_at`.

### Example Curl

```bash
curl -X POST "https://bm.prosolutions-ks.com/locations/api/kesco/meters/upsert/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: bmgm_your_key_here" \
  -d '{
    "Data": {
      "debitors": [
        {
          "AgencyId": "DFE",
          "ElDebitorId": 160,
          "FullName": "Consumer Name",
          "DebitorAddress": "Consumer Address",
          "TariffGroup": "4/02",
          "LastDueDate": "2026-04-12T00:00:00",
          "TotalDebt": 111.75,
          "MeterReading": "1234.50"
        }
      ]
    }
  }'
```

### Response

Successful response:

```json
{
  "owner": "username",
  "scope": "kesco_meter_write",
  "results": [
    {
      "uuid": "meter-uuid",
      "created": true,
      "name": "DFE160",
      "kesco_debitor_id": "160",
      "ledger": {
        "uuid": "ledger-uuid",
        "created": true,
        "month": 4,
        "year": 2026,
        "billed_amount": "111.75"
      }
    }
  ],
  "errors": []
}
```

If some rows fail and some succeed, the API returns HTTP `207` with both `results` and `errors`.

If all rows fail, the API returns HTTP `400`.

## Lease Debt Status API

Required scope:

```text
lease_report_read
```

Endpoint:

```http
GET /locations/api/leases/status/
X-API-Key: bmgm_your_key_here
```

Query parameters:

| Parameter | Default | Description |
|---|---:|---|
| `search` | empty | Search by lease ID, tenant name, contact, phone, or email |
| `debt_only` | `1` | Use `1` for leases with debt only, `0` for all matching leases |
| `limit` | `100` | Max rows returned, capped at `500` |
| `as_of` | today | Optional date in `YYYY-MM-DD` format |

Example:

```bash
curl "https://bm.prosolutions-ks.com/locations/api/leases/status/?search=LS-WDUFE&debt_only=1" \
  -H "X-API-Key: bmgm_your_key_here"
```

Response:

```json
{
  "owner": "username",
  "scope": "lease_report_read",
  "as_of": "2026-04-27",
  "search": "LS-WDUFE",
  "debt_only": true,
  "summary": {
    "leases_returned": 1,
    "leases_with_debt": 1,
    "total_debt": "300.00"
  },
  "results": [
    {
      "uuid": "internal-uuid",
      "display_id": "LS-WDUFE",
      "name": "Tenant Name",
      "contact": "Contact Person",
      "phone": "123456",
      "email": "tenant@example.com",
      "is_active": true,
      "start_date": "2026-04-01",
      "end_date": null,
      "monthly_payment": "500.00",
      "total_due": "500.00",
      "total_paid": "200.00",
      "balance": "300.00",
      "has_debt": true
    }
  ]
}
```

## Lease Report API

Required scope:

```text
lease_report_read
```

Use the public lease ID, not the internal UUID:

```http
GET /locations/api/leases/LS-WDUFE/report/
X-API-Key: bmgm_your_key_here
```

UUIDs still work as a fallback, but external tools should use `display_id`, for example `LS-WDUFE`.

Optional query parameter:

| Parameter | Default | Description |
|---|---:|---|
| `as_of` | today | Optional date in `YYYY-MM-DD` format |

Example:

```bash
curl "https://bm.prosolutions-ks.com/locations/api/leases/LS-WDUFE/report/" \
  -H "X-API-Key: bmgm_your_key_here"
```

Response includes:

- lease identity and contact details
- totals: due, paid, balance
- ledger rows
- latest meter standings for units assigned to the lease

Example response shape:

```json
{
  "owner": "username",
  "scope": "lease_report_read",
  "as_of": "2026-04-27",
  "sent_to": null,
  "report": {
    "uuid": "internal-uuid",
    "display_id": "LS-WDUFE",
    "name": "Tenant Name",
    "total_due": "500.00",
    "total_paid": "200.00",
    "balance": "300.00",
    "has_debt": true,
    "ledgers": [
      {
        "month": 4,
        "year": 2026,
        "amount_due": "500.00",
        "amount_paid": "200.00",
        "running_balance": "300.00",
        "status": "partial"
      }
    ],
    "meters": [
      {
        "unit_name": "Unit A",
        "meter_name": "DFE160",
        "period": {"month": 4, "year": 2026},
        "reading": "1234.50",
        "outstanding_amount": "111.75",
        "status": "open"
      }
    ],
    "meter_outstanding_total": "111.75"
  }
}
```

### Send Report By Email

```http
POST /locations/api/leases/LS-WDUFE/report/
Content-Type: application/json
X-API-Key: bmgm_your_key_here
```

Payload:

```json
{
  "email_to": "person@example.com"
}
```

If `email_to` is omitted, the API uses the lease email. If the lease has no email, `email_to` is required.

Example:

```bash
curl -X POST "https://bm.prosolutions-ks.com/locations/api/leases/LS-WDUFE/report/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: bmgm_your_key_here" \
  -d '{"email_to":"person@example.com"}'
```

Email sending depends on Django email settings being configured in production.

## Settlement APIs

Required scope:

```text
settlement_write
```

Settlement APIs always require a specific period. You may send either:

```json
{"period": "2026-04"}
```

or:

```json
{"month": 4, "year": 2026}
```

### Settle Lease Payment

Use the public lease ID:

```http
POST /locations/api/leases/LS-WDUFE/settle-payment/
Content-Type: application/json
X-API-Key: bmgm_your_key_here
```

Payload:

```json
{
  "period": "2026-04",
  "payment_date": "2026-04-27",
  "amount_paid": "500.00",
  "notes": "Paid via bank transfer"
}
```

`amount_paid` is optional. If omitted, the API settles the period by setting `amount_paid` equal to `amount_due`.

`payment_date` is optional. If omitted, today is used.

If the lease ledger period does not exist, it is created with `amount_due` from the lease monthly payment.

Example:

```bash
curl -X POST "https://bm.prosolutions-ks.com/locations/api/leases/LS-WDUFE/settle-payment/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: bmgm_your_key_here" \
  -d '{"period":"2026-04","payment_date":"2026-04-27"}'
```

Response:

```json
{
  "owner": "username",
  "scope": "settlement_write",
  "lease": {
    "display_id": "LS-WDUFE",
    "balance": "0.00",
    "has_debt": false
  },
  "ledger": {
    "month": 4,
    "year": 2026,
    "amount_due": "500.00",
    "amount_paid": "500.00",
    "status": "paid",
    "payment_date": "2026-04-27"
  }
}
```

### Settle Electric Debt

Endpoint:

```http
POST /locations/api/electric-debts/settle/
Content-Type: application/json
X-API-Key: bmgm_your_key_here
```

Settle all electric meter ledgers for a lease and period:

```json
{
  "lease_id": "LS-WDUFE",
  "period": "2026-04",
  "settled_at": "2026-04-27"
}
```

Or settle one electric meter by KESCO debitor ID:

```json
{
  "kesco_debitor_id": "160",
  "period": "2026-04"
}
```

Accepted meter identifiers:

- `kesco_debitor_id`
- `meter_uuid`
- `serial_number`
- `meter_name`

For each matching electric meter ledger, the API sets:

- `billed_amount = 0`
- `settled_at = settled_at` or today

If a matching meter has no ledger for that period, the response marks that row as `missing_ledger`; it does not create a zero ledger.

Example:

```bash
curl -X POST "https://bm.prosolutions-ks.com/locations/api/electric-debts/settle/" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: bmgm_your_key_here" \
  -d '{"lease_id":"LS-WDUFE","period":"2026-04"}'
```

Response:

```json
{
  "owner": "username",
  "scope": "settlement_write",
  "results": [
    {
      "meter_name": "DFE160",
      "status": "settled",
      "month": 4,
      "year": 2026,
      "previous_billed_amount": "111.75",
      "billed_amount": "0.00",
      "settled_at": "2026-04-27"
    }
  ]
}
```

## Common Errors

Missing key:

```json
{"error": "Missing API key."}
```

Invalid or revoked key:

```json
{"error": "Invalid API key."}
```

Invalid JSON:

```json
{"error": "Invalid JSON payload."}
```

Missing meter identity:

```json
{
  "results": [],
  "errors": [
    {
      "index": 0,
      "error": "One of kesco_debitor_id, uuid, or serial_number is required."
    }
  ]
}
```
