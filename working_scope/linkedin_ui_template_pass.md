# LinkedIn UI Template Pass

Date: 2026-04-27

## Scope

Applied the LinkedIn-style template cleanup across `templates/`, `accounts/templates/`, and `locations/templates/`.

## Rules Applied

- Feature templates should not use `style=""` attributes.
- Page elements should use shared classes from `static/css/main.css`.
- Colors should come from theme tokens or print-local tokens.
- Detail fields should use `summary-grid`, `summary-label`, and `summary-value`.
- Table wrappers should use `card card--flush`.
- Empty states should use `empty-state` or `table-empty`.
- Forms should use shared card width helpers such as `card--narrow` and `card--wide`.
- Button groups and row actions should use `flex`, `gap-*`, `flex-wrap`, and `d-inline`.

## New Shared Classes

- `summary-grid--wide`
- `section-heading`
- `page-header__eyebrow`
- `detail-divider`
- `form-help`
- `card--narrow`
- `card--wide`
- `empty-state--compact`
- `empty-state--table`
- `table-empty`
- `code-block`
- `kpi-card--disabled`
- `kpi-card__label--offset`
- `text-body`
- `text-strong`
- `text-neutral`

## Notes

The printable lease ledger remains standalone for print/PDF output, but its colors are now routed through print-local CSS variables instead of direct component color declarations.
