# Building Management System — QWEN Context

## Project Overview

This is a **Django 5.1 building management application** for tracking leases, units, meters, utility bills, and parking spaces across multiple physical locations. The system is containerized with Docker and uses PostgreSQL 16 as its database.

### Core Domain Apps

- **`accounts/`** — Custom User model with role-based access control (Super User, Admin, Data Entry Clerk), authentication, API key management, company profiles, and language preference middleware.
- **`locations/`** — Locations, Units, Leases, Lease Ledgers (monthly payment tracking), Meters (electric/water/gas), Meter Ledgers (monthly billing records), Parking Places, and KESCO (Kosovo electric company) integration with credential management and automatic sync.

### Key Features

- **Lease Management** — CRUD for lease agreements, auto-generated ledger entries for monthly payments, advance month tracking, payment slip uploads.
- **Meter & Utility Tracking** — Meters per unit with monthly ledgers for billing. KESCO integration fetches utility bills from the Kosovo electric company API.
- **KESCO Integration** — Database-stored credentials, bearer token management with 7-day expiry, iframe captcha handling, automatic sync every 3 days via `sync_kesco_meters --loop` command, meter linking via `kesco_debitor_id`.
- **Dashboard KPIs** — Unpaid ledgers, meter debts, utility bill tracking.
- **Multi-language** — English, Albanian, German, French, Italian via Django i18n middleware (clean URLs without `/en/` or `/sq/` prefixes).
- **Role-based Access** — Super User (full access), Admin (create/edit/delete users), Data Entry Clerk (view/edit only).

## Tech Stack

- **Backend:** Django 5.1
- **Database:** PostgreSQL 16
- **Frontend:** Django templates + HTMX
- **Containerization:** Docker & Docker Compose (3 services: `web`, `db`, `kesco-sync`)
- **Static Files:** WhiteNoise
- **HTTP Client:** urllib (standard library for KESCO API)
- **Image Processing:** Pillow

## Project Structure

```
├── config/                     # Django project settings
│   ├── settings/
│   │   ├── base.py             # Shared settings
│   │   ├── local.py            # Development settings
│   │   └── production.py       # Production settings
│   ├── urls.py                 # Root URL configuration
│   └── wsgi.py
├── accounts/                   # User management app
│   ├── models.py               # Custom User, Role, ApiKey, CompanyProfile
│   ├── views.py                # CRUD views, language switcher
│   ├── forms.py                # User forms
│   ├── middleware.py            # UserLanguageMiddleware
│   └── templates/accounts/
├── locations/                  # Location/lease/meter app
│   ├── models.py               # Location, Unit, Lease, LeaseLedger, Meter, MeterLedger, KescoCredential, ParkingPlace
│   ├── views.py                # Dashboard, lease/meter CRUD
│   ├── urls.py
│   ├── management/commands/    # sync_kesco_meters, cleanup_kesco_orphans, generate_ledgers
│   └── templates/locations/
├── templates/                  # Global templates (base.html)
├── static/                     # CSS, JS assets
├── locale/                     # Translation files (en, sq, de, fr, it)
├── working_scope/              # Branding & style guidelines
├── media/                      # User uploads (contracts, payment slips)
├── docker-compose.yml
├── Dockerfile
├── seed.py                     # Initial data seeder
└── manage.py
```

## Building and Running

### Quick Start

```bash
# Start all services
docker compose up -d

# Seed default users (first time only)
docker compose exec web python seed.py

# Access the app
# http://localhost:8800/login/
```

### Default Credentials

| Role | Username | Password |
|------|----------|----------|
| Super User | admin | admin123 |
| Admin | manager | manager123 |
| Data Entry Clerk | clerk | clerk123 |

### Common Commands

```bash
# View logs
docker compose logs -f web

# Run migrations
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Compile translations
docker compose exec web python manage.py compilemessages

# Create superuser manually
docker compose exec web python manage.py createsuperuser

# Stop services
docker compose down

# Rebuild after dependency or Dockerfile changes
docker compose build && docker compose up -d

# Run KESCO sync in loop (separate service)
docker compose up -d kesco-sync
```

### Verification After Build

After `docker compose build && docker compose up -d`, **wait at least 30 seconds**, then run:

```bash
docker compose logs --tail=20
```

Verify there are no tracebacks and logs show `System check identified no issues`. A clean build exit code does not guarantee the app is running correctly.

## Testing

No test suite is currently checked in. Add tests using Django's default patterns:

```bash
docker compose exec web python manage.py test
```

For model or migration changes, also run:

```bash
docker compose exec web python manage.py makemigrations --check --dry-run
```

## Architecture Notes

### Model Design

- **All models require a `uuid` field** — used for public-facing foreign keys and URLs.
- **Utility bills are tracked per meter, not per lease** — `MeterLedger` links to `Meter`, which links to `Unit`, which may link to `Lease`. This allows accurate per-meter billing history and supports units with multiple utility types.
- **Lease auto-generates ledger entries** — When a new `Lease` is saved, `LeaseLedger` records are created for each month from `start_date` to `end_date` (or today), with advance months marked as paid.
- **KESCO Meter fields** — `Meter` model stores `kesco_debitor_id`, `kesco_agency_id`, `kesco_full_name`, `kesco_address`, `kesco_tariff_group`, `kesco_last_due_date` for API sync results.

### KESCO Integration

- **Credential management:** `/locations/kesco/` dashboard — add username, paste bearer token, optionally user_id.
- **Sync command:** `python manage.py sync_kesco_meters --loop` runs every 3 days (configurable via `KESCO_SYNC_INTERVAL_SECONDS`). Sleeps 3-10s randomly before each API call to avoid rate limiting.
- **Meter linking:** Sync matches on `kesco_debitor_id` first, then falls back to orphan detection (serial_number="KESCO-{id}"), then creates new under Location 0.
- **Token expiry:** KESCO bearer tokens expire every 7 days. System attempts auto-refresh; if captcha required, notifies user to complete iframe login.

### Language System

- Language is handled by `UserLanguageMiddleware` — no i18n URL prefixes (`/en/`, `/sq/`) in URLs.
- User's preferred language stored in `User.preferred_language` and persisted via cookie.
- Languages: English, Albanian, German, French, Italian.

## Development Conventions

- **Coding style:** 4-space indentation in Python, snake_case for functions/fields, PascalCase for classes/models.
- **Template naming:** Descriptive names such as `lease_ledger_form.html`.
- **Domain logic:** Keep within the relevant app.
- **Model naming:** Match existing business concepts: `Lease`, `Unit`, `MeterLedger`, `ParkingPlace`.
- **Templates:** Reuse `templates/base.html` for shared layout.
- **Security:** Never commit real secrets or production uploads. Local configuration from `.env` and Docker Compose defaults. Production must set `SECRET_KEY`, database credentials, `DEBUG=0`, and trusted host/origin values outside the repository.

## Pull Request Guidelines

- Use clear imperative commit subjects (e.g., `Add lease ledger payment slip upload`).
- Include testing notes, linked issue reference, and screenshots for UI changes.
- Mention migrations, seed data changes, or configuration changes explicitly.
