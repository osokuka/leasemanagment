# Feature: Meters, Monthly Ledger & Parking

## Scope
Extend the unit detail page to show utility meters, monthly billing ledgers, and
parking assignments. Clicking a unit in the location detail page opens a **Unit Detail**
page (not the edit form), which shows all relevant unit information.

---

## Model: `Meter`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uuid` | UUID4 | Yes | Public identifier |
| `unit` | FK → Unit | Yes | Parent unit |
| `name` | CharField(255) | Yes | Human-readable name (e.g. "Main Electric", "Kitchen Gas") |
| `meter_type` | CharField | Yes | One of: `electric`, `water`, `gas` |
| `reading_metric` | CharField | Yes | Unit of measurement: `kWh`, `m³`, `m³_gas` |
| `serial_number` | CharField(100) | No | Meter hardware serial |
| `created_at` | DateTime | Auto | |
| `updated_at` | DateTime | Auto | |

### Meter Types
- **Electric** — reading in `kWh`
- **Water** — reading in `m³`
- **Gas** — reading in `m³_gas`

---

## Model: `MeterLedger`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uuid` | UUID4 | Yes | Public identifier |
| `meter` | FK → Meter | Yes | Associated meter |
| `month` | IntegerField | Yes | 1–12 |
| `year` | IntegerField | Yes | e.g. 2026 |
| `reading` | DecimalField | No | Meter reading for the period (optional) |
| `billed_amount` | DecimalField | No | Amount billed by external services (EUR) |
| `created_at` | DateTime | Auto | |
| `updated_at` | DateTime | Auto | |

- One record per meter per month/year
- Reading is optional (may not have been collected yet)
- Billed amount is filled by external billing integration

---

## Model: `ParkingPlace`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uuid` | UUID4 | Yes | Public identifier |
| `location` | FK → Location | Yes | Parent location |
| `label` | CharField(100) | Yes | Identifier (e.g. "P-01", "Basement A-3") |
| `unit` | FK → Unit | No | Currently assigned unit (nullable) |
| `covered` | BooleanField | No | Whether the spot is covered/indoor |
| `created_at` | DateTime | Auto | |
| `updated_at` | DateTime | Auto | |

---

## Unit Detail Page
Clicking a unit navigates to `/locations/<location-uuid>/units/<unit-uuid>/` which shows:

### Info Card
- Unit name, type badge, status badge
- Area (sqm)
- Parking places count (linked to this unit)
- List of assigned parking place labels

### Meters Section
- Table of all meters for this unit (name, type, reading metric, serial)
- Each meter row links to its monthly ledger page
- "+ Add Meter" button (admin+)

### Ledger Section (per meter)
- When clicking a meter, shows monthly ledger table
- Columns: Month/Year, Reading, Billed Amount
- Pagination at 12 items/month
- Edit/Add ledger entries (admin+)

### Access Control
- **Super User / Admin:** full CRUD on meters and ledgers
- **Data Entry Clerk:** read-only on unit detail, meters, and ledgers

---

## UX Changes
- **Unit list row click** → navigates to **Unit Detail** page (not edit)
- **Unit Detail** page has separate "Edit" button for edit mode
- Meters table: clickable rows → navigate to meter ledger detail
- All tables follow clickable row branding rule
- Mobile: card grid pattern (per branding)
