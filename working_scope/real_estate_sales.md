# Real Estate Sales Feature Scope

## Purpose

The company also sells apartments and other real estate property. The system needs a sales module separate from leases so management can track:

- Unsold property inventory
- Sold property
- Sold property that is partially paid
- Buyer information
- Sale contracts and agreed sale price
- Payment arrangements and installments
- Due dates, overdue installments, and remaining balances
- Full payment history per sold property

This feature should live alongside the current `locations` and `leases` workflows, but it should not reuse lease ledgers because sales are ownership transactions, not recurring rental contracts.

## Core Concepts

### Saleable Property

A saleable property represents a real estate asset the company can sell.

It can be linked to an existing `Unit` when the asset already exists in the building inventory, but it should also support standalone real estate property if the company sells something that is not managed as a rental unit.

Suggested fields:

- Property ID, for example `RE-A8K3D`
- Linked unit, optional
- Location, optional if linked unit already provides location
- Property name
- Property type: apartment, house, villa, office, land, parking, commercial, other
- Area in sqm
- Floor, optional
- Address or description
- Asking price
- Final sale price
- Status: unsold, reserved, sold_partial, sold_paid, cancelled
- Notes
- Created and updated timestamps

### Buyer

A buyer is the responsible party for a sale.

Suggested fields:

- Full name or company name
- Contact person
- Phone
- Email
- Personal/business ID number, optional
- Address
- Notes

### Sale Agreement

A sale agreement connects a buyer to a property and defines the commercial terms.

Suggested fields:

- Sale ID, for example `SA-X9K2P`
- Property
- Buyer
- Contract file
- Agreement date
- Sale price
- Down payment amount
- Payment arrangement type
- Expected closing date
- Status: active, completed, cancelled, defaulted
- Notes

Payment arrangement types:

- Full payment
- Down payment plus installments
- Custom installment plan
- Bank financing
- Deferred payment
- Other

### Payment Schedule

Each sale agreement can have one or more scheduled payment obligations.

Suggested fields:

- Sale agreement
- Installment number
- Due date
- Amount due
- Amount paid
- Payment date
- Status: unpaid, partial, paid, overdue
- Notes
- Payment slip, optional

Rules:

- If `amount_paid` is 0 and due date is past, status becomes overdue.
- If `amount_paid` is less than `amount_due`, status is partial.
- If `amount_paid` is greater than or equal to `amount_due`, status is paid.
- Remaining sale balance is total scheduled due minus total paid.
- A sale becomes `sold_paid` only when the agreement is completed and balance is zero.
- A sale becomes `sold_partial` when the buyer has paid something but still has remaining balance.

## Required Screens

### Real Estate Dashboard

Shows summary cards:

- Total properties
- Unsold properties
- Reserved properties
- Sold and fully paid properties
- Sold with remaining balance
- Total outstanding receivables
- Overdue installments

Also show quick tables:

- Properties with overdue payments
- Recently sold properties
- Unsold inventory

### Property Inventory List

Filters:

- Status
- Location
- Property type
- Search by property ID, unit name, buyer name, or address

Columns:

- Property ID
- Property name
- Location
- Type
- Area
- Asking price
- Sale price
- Status
- Buyer, if sold/reserved
- Balance
- Actions

### Property Detail

Shows:

- Property details
- Linked unit details, if applicable
- Current sale status
- Buyer and sale agreement, if sold/reserved
- Payment summary
- Payment schedule table
- Payment history

Actions:

- Edit property
- Mark reserved
- Create sale agreement
- Upload contract
- Add scheduled payment
- Record payment
- Cancel sale agreement

### Sale Agreement Form

Used when a property is reserved or sold.

Fields:

- Buyer
- Sale price
- Agreement date
- Contract upload
- Arrangement type
- Down payment
- Expected closing date
- Notes

After save, the system should allow either:

- Auto-generate installment schedule
- Manually create custom installments

### Payment Schedule Form

Fields:

- Due date
- Amount due
- Amount paid
- Payment date
- Payment slip
- Notes

This should support editing payment rows later if an arrangement changes.

## Suggested URL Structure

```text
/real-estate/
/real-estate/properties/
/real-estate/properties/create/
/real-estate/properties/<uuid>/
/real-estate/properties/<uuid>/edit/
/real-estate/properties/<uuid>/sale/create/
/real-estate/sales/<uuid>/
/real-estate/sales/<uuid>/edit/
/real-estate/sales/<uuid>/schedule/create/
/real-estate/sales/<uuid>/schedule/<uuid>/edit/
/real-estate/sales/<uuid>/schedule/<uuid>/delete/
```

## Permissions

View access:

- Authenticated users can view property inventory and sale status.

Create/edit access:

- Admin users can create and edit properties, buyers, sale agreements, and payments.

Delete/cancel access:

- Super users should be required for deleting records or cancelling sale agreements.

## Reporting Needs

Required reports:

- Unsold property inventory
- Sold property with remaining balance
- Overdue payment schedule
- Buyer statement per sale
- Monthly expected receivables
- Monthly collected payments

Export formats:

- Print/PDF buyer statement
- CSV export for outstanding receivables

## Implementation Phases

### Phase 1: Data Model

Create models:

- `RealEstateProperty`
- `PropertyBuyer`
- `PropertySale`
- `PropertySalePayment`

Add migrations and admin registration.

### Phase 2: Basic CRUD

Create:

- Property list/detail/form
- Buyer form
- Sale agreement form
- Payment schedule form

Add navigation entry in sidebar.

### Phase 3: Payment Logic

Implement:

- Sale balance calculation
- Payment status calculation
- Overdue detection
- Auto update property sale status
- Optional installment schedule generator

### Phase 4: Reporting

Implement:

- Real estate dashboard
- Outstanding balances report
- Overdue payments report
- Buyer statement print view

### Phase 5: Polish

Apply existing LinkedIn-style UI primitives:

- `card`
- `card--flush`
- `badge`
- `summary-grid`
- `summary-label`
- `summary-value`
- `table-empty`
- `empty-state`

## Open Decisions

- Should a sold property always be linked to a `Unit`, or should standalone properties be common?
- Should buyers be reusable across multiple sales?
- Should parking places be saleable independently?
- Should sales support multiple buyers per property?
- Should the system support currency other than EUR?
- Should payment schedules support interest, penalties, or late fees?
- Should payment changes be auditable with immutable history?

## Recommended First Build

Start with the simplest complete workflow:

1. Create saleable property.
2. Mark it as unsold.
3. Create buyer.
4. Create sale agreement.
5. Add payment schedule rows.
6. Record payments against schedule rows.
7. Show status as unsold, sold partial, or sold paid.
8. Report overdue and remaining balances.

This gives the company immediate visibility into inventory, partial payments, due dates, and expected receivables without overcomplicating the first version.
