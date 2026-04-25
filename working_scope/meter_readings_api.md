# Meter API Integration & Automatic Updates

## Purpose

Provide an internal integration tool for third-party meter systems to insert or update meter readings and external expense standings in the building management system.

This integration is needed because meter expenses such as electricity, water, or gas are often billed by external providers to the property owner, while the tenant is responsible for keeping those expenses paid.

## Architecture

The KESCO integration runs as a separate internal-only worker container. It has no ingress from outside and exposes no ports. It only needs outbound HTTPS access to KESCO and internal database access through the Docker network.

Run target:

```bash
docker compose --profile integrations up -d kesco-sync
```

The worker executes:

```bash
python manage.py sync_kesco_meters --loop
```

## Credentials

The worker enumerates accounts from a mounted JSON credentials file or equivalent secret-backed environment value. Real credentials must not be committed.

Recommended environment:

```env
KESCO_ACCOUNTS_FILE=/run/secrets/kesco_accounts.json
KESCO_LOGIN_URL=https://fatura.kesco-energy.com/api/Account/login
KESCO_LOGIN_USERNAME_FIELD=email
KESCO_LOGIN_PASSWORD_FIELD=password
KESCO_SYNC_INTERVAL_SECONDS=3600
```

Credential file shape:

```json
{
  "accounts": [
    {
      "username": "user@example.com",
      "password": "replace-with-secret-password",
      "user_id": "optional-kesco-user-id-if-not-present-in-token"
    }
  ]
}
```

The worker logs in for each account, obtains a bearer token, derives the KESCO `user_id` from the credential file or JWT payload, then calls the user-data endpoint.

## KESCO Payload Example

KESCO currently returns data from:

`GET https://fatura.kesco-energy.com/api/Account/user-data?userId=<external-user-id>`

Example response shape:

```json
{
  "State": 1,
  "Msg": null,
  "Data": {
    "balance": {
      "AgencyId": "DFE",
      "DebitorId": 160,
      "ConsumerName": "Avni Hetem Ademi",
      "BillingAddress": "Rizah Matoshi 1. Ferizaj",
      "AMeterId": "62267012",
      "AMeterConstant": 1.0,
      "TariffGroup": "4/02",
      "LastBillAmount": 111.92,
      "A1Price": 6.75,
      "A2Price": 2.89,
      "KescoBalance": 111.75,
      "KekBalance": 0.0,
      "CurrentBalance": 111.75
    },
    "lastUpdate": "2026-04-25T19:07:08.4559551+02:00"
  }
}
```

Recommended mapping:

- `balance.AgencyId + balance.DebitorId` forms the provider account key, for example `DFE160`.
- `balance.AMeterId` maps to `Meter.serial_number`.
- `balance.ConsumerName` and `balance.BillingAddress` are reference metadata for validation.
- `balance.CurrentBalance` maps to `MeterLedger.billed_amount` as the current outstanding tenant expense.
- `balance.LastBillAmount` can be stored as reference metadata if invoice history is added later.
- `Data.lastUpdate` should be stored as the source timestamp/audit value.
- `MeterLedger.reading` may remain blank if KESCO does not provide an actual meter reading in this response.

Imported or updated meter names should use:

```text
<AgencyId><DebitorId> - <AMeterId> - <ConsumerName>
```

Example:

```text
DFE160 - 62267012 - Avni Hetem Ademi
```

## Automatic Updates

The sync command upserts records by meter serial number and billing period:

- Existing `Meter` records are matched by `Meter.serial_number`.
- Unknown meters are created automatically.
- `MeterLedger` entries are updated or created for the `lastUpdate` month/year.
- `CurrentBalance` becomes the current outstanding meter expense.
- If `CurrentBalance` is `0`, the period is considered settled and `settled_at` is set.
- Meter expenses remain separate from lease rent balances.

## Location 0 Holding Area

Unknown KESCO meters are registered under the fictive holding location:

```text
Location 0 - Unassigned KESCO Meters
```

Because every meter must belong to a unit, the sync creates or reuses this holding unit:

```text
Unassigned KESCO Meters
```

Staff can later open the app, edit imported meters, and assign them to the correct real unit.

## Development Fallback

For development only, the command can still accept:

```env
KESCO_BEARER_TOKEN=...
KESCO_USER_IDS=cf99fe01-b332-48cd-a73a-54be398826c5
```

Production should use the credential file or secret-mounted equivalent instead of copied browser tokens.

## Security & Validation

Do not store real KESCO usernames, passwords, bearer tokens, or cookies in code, migrations, logs, or documentation. The real `kesco_accounts.json` file must be mounted from a controlled environment and ignored by Git.

Recommended safeguards:

- Keep the `kesco-sync` service without `ports`.
- Mount credentials as Docker secrets or protected files.
- Rotate credentials when staff access changes.
- Validate non-negative balances.
- Match existing meters by `AMeterId` / `serial_number`.
- Preserve separation between lease ledgers and meter expense standings.
