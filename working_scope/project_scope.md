# Project Scope & Feature Summary

> Last updated: 2026-04-25

## Project Overview
- **Type:** Web application (mobile-first, responsive)
- **Languages:** English (primary), Albanian (secondary)
- **Themes:** Dark mode and light mode support
- **Stack:** Django 5.1 + PostgreSQL 16, Docker-first
- **Design:** LinkedIn-inspired — clean, professional, minimal

---

## Models

### User (accounts)
| Field | Description |
|-------|-------------|
| `uuid` | Public identifier |
| `username` | Login username |
| `role` | Super User, Admin, Data Entry Clerk |
| `is_active` | Account active flag |

### Location (locations)
| Field | Description |
|-------|-------------|
| `uuid` | Public identifier |
| `name` | Location name |
| `address` | Full address |
| `google_pin` | Google Maps link (optional) |
| `focal_point` | Descriptor (e.g. "Floor 3") |

### Unit (locations)
| Field | Description |
|-------|-------------|
| `uuid` | Public identifier |
| `location` | FK → Location |
| `lease` | FK → Lease (nullable) — determines leased/vacant status |
| `name` | Unit name/number |
| `sqm` | Area in square meters |
| `unit_type` | Apartment, House, Villa, Office, Cafe & Restaurant, Space, Undefined |
| `is_leased` | Computed property (has active lease?) |

### Lease (locations)
| Field | Description |
|-------|-------------|
| `uuid` | Public identifier |
| `display_id` | Memorable 8-char ID (e.g. `LS-SWBH6`) |
| `name` | Responsible party / tenant name |
| `contact` | Alternate contact person |
| `phone` | Phone number |
| `email` | Email address |
| `contract` | PDF upload |
| `start_date` / `end_date` | Lease period |
| `is_active` | Active toggle |
| `monthly_payment` | € amount per month |
| `advance_months` | Months tenant pays in advance |
| `deposit` | Security deposit (optional) |
| `notes` | Additional notes |

### Meter (locations)
| Field | Description |
|-------|-------------|
| `uuid` | Public identifier |
| `unit` | FK → Unit |
| `name` | Meter name |
| `meter_type` | Electric, Water, Gas |
| `reading_metric` | kWh, m³, m³_gas |
| `serial_number` | Hardware serial (optional) |

### MeterLedger (locations)
| Field | Description |
|-------|-------------|
| `uuid` | Public identifier |
| `meter` | FK → Meter |
| `month` / `year` | Billing period |
| `reading` | Optional meter reading |
| `billed_amount` | € billed by external services |

### LeaseLedger (locations)
| Field | Description |
|-------|-------------|
| `uuid` | Public identifier |
| `lease` | FK → Lease |
| `month` / `year` | Billing period |
| `amount_due` | Auto-filled from lease monthly_payment |
| `amount_paid` | Recorded payment |
| `status` | Auto: Paid / Partial / Unpaid / Overdue |
| `payment_date` | When payment received |
| `notes` | Optional |

### ParkingPlace (locations)
| Field | Description |
|-------|-------------|
| `uuid` | Public identifier |
| `location` | FK → Location |
| `label` | Identifier (e.g. "P-01") |
| `unit` | FK → Unit (nullable) |
| `covered` | Indoor/outdoor |

---

## URL Routes

| Route | Description |
|-------|-------------|
| `/login/` | Login page |
| `/logout/` | Logout |
| `/users/` | User list |
| `/users/create/` | Create user |
| `/users/<pk>/edit/` | Edit user |
| `/locations/` | Location list |
| `/locations/<uuid>/` | Location detail (info + units) |
| `/locations/<uuid>/unit/create/` | Create unit |
| `/locations/<uuid>/unit/<uuid>/edit/` | Edit unit |
| `/locations/<uuid>/units/<uuid>/` | Unit detail (info + meters + parking) |
| `/locations/<uuid>/units/<uuid>/meters/<uuid>/ledger/` | Meter ledger |
| `/leases/` | Lease list |
| `/leases/<uuid>/` | Lease detail (info + assigned units) |
| `/leases/<uuid>/ledger/` | Lease payment ledger |
| `/leases/<uuid>/ledger/create/` | Add ledger entry |

---

## Navigation Structure
- ⚙️ **Setup** (accordion)
  - User Management
  - Location Management
- 📍 **Location Management** (accordion)
  - Locations
- 📋 **Lease Management** (accordion)
  - Leases

---

## Access Control
| Role | Capabilities |
|------|-------------|
| Super User | Full CRUD + delete on everything |
| Admin | CRUD (no delete) |
| Data Entry Clerk | Read-only (list + detail) |

---

## Branding Rules
- **No gradients** — solid, flat colors only
- **Minimal border radius** — 2px–4px (max 8px)
- **Red** reserved for errors/critical only
- **Yellow/Amber** reserved for warnings only
- **Clickable rows** on all list tables (click → detail page)
- **Mobile tables** → card grid with data-label captions

---

## Status Logic
- **Unit status** = computed from `is_leased` (has active lease FK?)
- **Lease ledger status** = auto-computed from amount_paid vs amount_due
