# DESIGN.md — MiningProcessor Visual Design System

## Color Strategy: Restrained

Single accent (blue-gray #475569) for interactive states only. No decorative color.

### Palette (Tailwind v4 @theme)

| Token | Value | Usage |
|---|---|---|
| --color-bg | #F9FAFB | Page background |
| --color-surface | #FFFFFF | Cards, panels |
| --color-surface-raised | #F3F4F6 | Sidebar, toolbar, secondary panels |
| --color-border | #E5E7EB | Default borders |
| --color-border-strong | #D1D5DB | Emphasized borders |
| --color-text | #111827 | Primary text (contrast 15:1 on white) |
| --color-text-secondary | #4B5563 | Secondary text (contrast 7:1 on white) |
| --color-text-muted | #9CA3AF | Placeholder, hints (contrast 3.5:1) |
| --color-accent | #2563EB | Primary action, selection, focus ring |
| --color-accent-hover | #1D4ED8 | Hover state |
| --color-accent-subtle | #EFF6FF | Selection background |
| --color-success | #059669 | Success state |
| --color-error | #DC2626 | Error state |
| --color-warning | #D97706 | Warning state |

## Typography

- **Family:** MiSans VF (custom), system sans fallback
- **Scale:** Fixed rem, 1.15 ratio
  - xs: 0.75rem (12px) — captions, badges
  - sm: 0.8125rem (13px) — labels, table cells, secondary
  - base: 0.875rem (14px) — body text (product density)
  - lg: 1rem (16px) — section headings
  - xl: 1.125rem (18px) — page titles
- **Weights:** 400 (body), 500 (labels, buttons), 600 (headings)
- **Line height:** 1.5 for body, 1.25 for headings

## Component Tokens

### Buttons
- Primary: bg-slate-900 text-white rounded-md px-3.5 py-1.5 text-sm font-medium
- Secondary: bg-white border border-slate-300 text-slate-700 rounded-md px-3.5 py-1.5 text-sm
- Danger: bg-red-50 text-red-700 border border-red-200 rounded-md px-3.5 py-1.5 text-sm
- All: hover darkens bg, focus ring 2px blue-500/20, disabled opacity-50

### Inputs
- border border-slate-300 rounded-md px-3 py-1.5 text-sm
- Focus: ring-2 ring-blue-500/20 border-blue-500
- Error: border-red-300 ring-red-500/20

### Tables
- Header: bg-slate-50 text-xs font-medium text-slate-500 uppercase tracking-wider
- Row: h-9 (36px), border-b border-slate-100, hover:bg-slate-50
- Cell: px-3 py-2 text-sm text-slate-700

### Cards
- bg-white rounded-lg border border-slate-200 p-4
- No shadows on cards (elevation via border only)

### Sidebar
- bg-slate-50 border-r border-slate-200
- Active: bg-blue-50 text-blue-700, left 2px bar
- Hover: bg-slate-100

## Spacing Scale (4px base)

- 1: 4px (tight inner padding)
- 2: 8px (compact gap)
- 3: 12px (standard gap)
- 4: 16px (card padding)
- 5: 20px (section gap)
- 6: 24px (page padding)
- 8: 32px (major section break)

## Motion

- Duration: 150ms (micro), 200ms (standard), 300ms (complex)
- Easing: ease-out for enter, ease-in for exit
- No layout-property animation (height, width, padding)
- prefers-reduced-motion: disable all transitions
