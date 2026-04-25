# Feature: Location Management

## Scope
Create full CRUD for managing building locations within the Bldg Mgm system.
Locations represent physical places (rooms, floors, offices, warehouses, etc.) that
can be referenced by other modules (assets, bookings, maintenance tickets, etc.).

## Requirements

### Model: `Location`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uuid` | UUID4 | Yes | Public identifier (foreign key reference) |
| `name` | CharField(255) | Yes | Human-readable location name |
| `address` | TextField | Yes | Full physical address |
| `google_pin` | URLField | No | Google Maps pin/share link |
| `focal_point` | CharField(255) | No | Short descriptor for the main area/entrance |
| `created_at` | DateTime | Auto | Record creation timestamp |
| `updated_at` | DateTime | Auto | Record last-modified timestamp |

### Views
- **List** (`GET /locations/`) — paginated, 15 per page, sorted by name
- **Create** (`GET/POST /locations/create/`) — admin+ only
- **Update** (`GET/PUT /locations/<uuid>/edit/`) — admin+ only
- **Delete** (`POST /locations/<uuid>/delete/`) — super_user only

### Access Control
- **Super User:** full CRUD + delete
- **Admin:** CRUD (no delete)
- **Data Entry Clerk:** list only (read-only)

### UI
- Desktop: standard table with pagination footer
- Mobile: card grid layout (per branding spec)
- Forms styled per branding (4px radius, solid colors, no gradients)
- Sidebar: Setup → Location Management → Locations (already scaffolded)

### Location Detail Page
- Shows location info card (name, address, google pin link, focal point, created/updated)
- Lists all units assigned to the location in a table
- "Add Unit" button on the detail page (admin+ only)
- Unit rows have Edit/Delete actions (Delete = super_user only)
- Mobile: units table converts to card grid (per branding)

### Model: `Unit`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uuid` | UUID4 | Yes | Public identifier (foreign key reference) |
| `location` | FK → Location | Yes | Parent location |
| `name` | CharField(255) | Yes | Unit name/number |
| `sqm` | DecimalField | Yes | Area in square meters |
| `unit_type` | CharField | Yes | One of: Apartment, House, Villa, Office, Cafe&Restaurant, Space, Undefined |
| `created_at` | DateTime | Auto | Record creation timestamp |
| `updated_at` | DateTime | Auto | Record last-modified timestamp |

### Unit Type Badges (branding-compliant)
- **Apartment** — blue (`--accent-primary`)
- **House** — green (`--success`)
- **Villa** — purple (muted, `#7C3AED`)
- **Office** — gray (`--text-secondary` with border)
- **Cafe&Restaurant** — brown (`#92400E`)
- **Space** — neutral (`--bg-tertiary`)
- **Undefined** — outlined, muted text

### Unit CRUD Views
- **List** — shown on Location detail page, paginated 15/page
- **Create** (`POST` from location detail page)
- **Update** (`GET/POST /locations/<uuid>/units/<unit-uuid>/edit/`)
- **Delete** (`POST /locations/<uuid>/units/<unit-uuid>/delete/`) — super_user only

### Access Control
- **Super User:** full CRUD + delete
- **Admin:** CRUD (no delete)
- **Data Entry Clerk:** list only (read-only on location detail)
