# Feature: Lease Management

## Scope
A Lease represents a rental agreement between a responsible party and the building
management. A lease can cover **multiple units** simultaneously. A unit's status
(Vacant/Leased) is **derived** from whether it has an active lease — it is no longer
a manually-set field.

---

## Model: `Lease`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uuid` | UUID4 | Yes | Public identifier |
| `name` | CharField(255) | Yes | Responsible party / tenant name |
| `contact` | CharField(255) | No | Alternate contact person |
| `phone` | CharField(50) | No | Phone number |
| `email` | EmailField | No | Email address |
| `contract` | FileField | No | Lease contract PDF upload |
| `start_date` | DateField | Yes | Lease start date |
| `end_date` | DateField | No | Lease end date (nullable for open-ended) |
| `is_active` | BooleanField | Yes | Default True, soft-deactivate when expired |
| `notes` | TextField | No | Additional notes |
| `units` | M2M → Unit | Yes | Units covered by this lease |
| `created_at` | DateTime | Auto | |
| `updated_at` | DateTime | Auto | |

---

## Unit Status (Computed)
- **Vacant** — unit has NO active lease (`unit.lease_set.filter(is_active=True).exists()` == False)
- **Leased** — unit has at least one active lease
- The `status` field on Unit becomes a **property**, not a stored field

---

## Lease CRUD
- **List** (`/leases/`) — paginated table, 15/page, sorted by name
  - Columns: Name, Phone, Email, Units count, Active, Start/End dates
  - Clickable rows → lease detail page
- **Detail** (`/leases/<uuid>/`) — shows lease info + list of assigned units
- **Create** (`/leases/create/`) — admin+ only, includes unit multi-select
- **Update** (`/leases/<uuid>/edit/`) — admin+ only
- **Delete** (`POST /leases/<uuid>/delete/`) — super_user only

---

## Sidebar
New category under **Setup**:
- ⚙️ **Setup**
  - User Management
  - Location Management
- 📋 **Leases**
  - Lease Management → `/leases/`

---

## Access Control
- **Super User:** full CRUD + delete
- **Admin:** CRUD (no delete)
- **Data Entry Clerk:** list + detail only (read-only)

---

## Contract Upload
- FileField stored at `media/contracts/`
- Accepts PDF only
- Shows download link on lease detail page
- On mobile: download button instead of link
