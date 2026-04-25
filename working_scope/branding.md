# Project Branding & Style Guide

## Overview
- **Type:** Web application (mobile-first, responsive)
- **Languages:** English (primary), Albanian (secondary)
- **Themes:** Dark mode and light mode support

## Design Philosophy
- **Inspiration:** LinkedIn — clean, professional, minimal
- **No gradients** — use solid, flat colors only
- **Subtle border radius** — avoid heavy/large rounded corners; keep elements clean and sharp (2px–4px range for most elements)

## Color Palette

### Light Theme
| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#FFFFFF` | Main background |
| `--bg-secondary` | `#F3F2EF` | Cards, sidebars, secondary surfaces |
| `--bg-tertiary` | `#E8E5DF` | Hover states, subtle highlights |
| `--text-primary` | `#000000` | Primary text |
| `--text-secondary` | `#666666` | Secondary text, captions |
| `--border-color` | `#E0DEDA` | Dividers, card borders |
| `--accent-primary` | `#0A66C2` | Primary actions, links, buttons |
| `--accent-hover` | `#004182` | Hover state for accent |
| `--success` | `#057642` | Success states |
| `--warning` | `#B78103` | Warning states only |
| `--error` | `#CC1022` | Error / critical states only |
| `--info` | `#0A66C2` | Informational states |

### Dark Theme
| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `#1A1A1A` | Main background |
| `--bg-secondary` | `#242424` | Cards, sidebars, secondary surfaces |
| `--bg-tertiary` | `#2D2D2D` | Hover states, subtle highlights |
| `--text-primary` | `#FFFFFF` | Primary text |
| `--text-secondary` | `#A0A0A0` | Secondary text, captions |
| `--border-color` | `#3D3D3D` | Dividers, card borders |
| `--accent-primary` | `#0A66C2` | Primary actions, links, buttons |
| `--accent-hover` | `#3B8DD6` | Hover state for accent |
| `--success` | `#0B8A54` | Success states |
| `--warning` | `#D49B1A` | Warning states only |
| `--error` | `#E62E3F` | Error / critical states only |
| `--info` | `#3B8DD6` | Informational states |

## Color Usage Rules
- **Red (`--error`)** — reserved exclusively for error messages, destructive actions, and critical alerts. Never used for badges, tags, or decorative elements.
- **Yellow/Amber (`--warning`)** — reserved exclusively for warning states. Never used for role badges, status tags, or decorative elements.
- **All other elements** — use `--accent-primary` (blue), `--success` (green), `--info` (blue), neutral grays, or solid muted tones inspired by LinkedIn's palette.

## Typography
- **Font family:** System font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif`)
- **Base font size:** `16px`
- **Headings:**
  - H1: `24px`, weight `600`
  - H2: `20px`, weight `600`
  - H3: `18px`, weight `600`
  - H4: `16px`, weight `600`
- **Body:** `14px`, weight `400`
- **Small/Caption:** `12px`, weight `400`
- **Line height:** `1.5` for body, `1.3` for headings

## Spacing
- **Base unit:** `8px`
- Scale: `4px`, `8px`, `12px`, `16px`, `24px`, `32px`, `48px`, `64px`

## Border Radius
- **Default:** `4px` (buttons, inputs, cards)
- **Small:** `2px` (tags, badges, chips)
- **Large:** `8px` (modals, dropdowns — max)
- **Avoid:** Anything above `8px`

## Layout
- **Mobile-first:** Design for `375px` minimum, scale up
- **Max content width:** `1280px` for desktop
- **Sidebar width:** `240px` (desktop, collapsible to `56px` icon-only), hamburger slide-in on mobile
- **Card padding:** `16px`
- **Section gaps:** `24px`

## Components
### Buttons
- Solid fill, no gradients
- Primary: `accent-primary` background, white text
- Secondary: transparent with `border-color` border, `text-primary` text
- Height: `40px` (desktop), `36px` (mobile)
- Radius: `4px`

### Inputs
- Border: `1px solid --border-color`
- Focus: `2px solid --accent-primary` ring
- Radius: `4px`
- Height: `40px`

### Cards
- Background: `--bg-secondary`
- Border: `1px solid --border-color`
- Radius: `4px`
- Padding: `16px`

### Navigation
- Sticky top bar, height `56px`
- **Desktop sidebar:** 240px wide, collapsible to 56px icon-only with chevron button
- **Mobile sidebar:** hamburger slide-in with dark overlay, tap overlay to close
- **Sidebar structure:** Parent items with chevron toggle, indented child submenus (accordion-style)
- Language toggle: EN / SQ switch

### Tables
- **Desktop:** Standard table with header row and bordered rows
- **Mobile (≤768px):** Tables convert to a vertical card grid — each row becomes a card, cells display `data-label` as a caption label on the left, actions aligned right
- **Clickable rows:** Every row in a list table must be clickable to navigate to its detail page. The first cell (or primary identifier) is a link, and the entire row has a hover highlight and `cursor: pointer`. On mobile card view, tapping anywhere on the card navigates to the detail page.

## Data Modeling
- **UUID primary keys:** Every model must include a `uuid` field (UUID4) that serves as the public identifier
- UUIDs are used as foreign key references across related tables instead of auto-increment IDs
- Internal Django `id` field remains for ORM performance but is never exposed externally

## Internationalization (i18n)
- **Languages:** English (`en`), Albanian (`sq`)
- All user-facing strings must be externalized (no hardcoded text)
- Language preference persisted in localStorage
- Default language: English
- RTL not required (both EN and SQ are LTR)

## Accessibility
- Minimum contrast ratio: `4.5:1` (WCAG AA)
- Focus indicators always visible
- Tap targets minimum `44x44px` on mobile
- Semantic HTML throughout
