# PRODUCT.md — MiningProcessor

## Register

Product. Mining operations Excel report processing tool with desktop GUI (Tauri + React). Design serves the product — efficiency, clarity, and reliability are the priority.

## Users & Purpose

**Who:** Mining site data administrators and operations managers (Chinese-speaking, Mongolia operations context).

**Context:** Daily batch processing of Excel reports from equipment fuel consumption, electrical usage, production output, and worktime tracking. Users process dozens of files per session, often under time pressure for reporting deadlines.

**Primary job:** Transform raw Excel data into standardized, ledger-matched output files for operational reporting and MineBase sync.

**Workflow:** Select files/folder → configure parameters → process → review output → sync to MineBase.

## Brand & Personality

**3 words:** Industrial, Precise, Reliable

**Tone:** Professional, functional, no-nonsense. Chinese/Mongolian bilingual context.

**Visual cues:** Data-dense dashboard aesthetic. Navy/blue professional palette. Clear hierarchy between navigation, controls, and data display.

**Anti-references:** Consumer apps, playful UIs, marketing landing pages. Avoid gamification or excessive decoration.

## Strategic Design Principles

1. **Data over decoration** — Every pixel should help users process data faster
2. **Progressive disclosure** — Show essential controls first, advanced options on demand
3. **Error prevention** — Validate before processing, confirm before destructive actions
4. **Multilingual ready** — Chinese UI with support for Mongolian/Cyrillic data fields
5. **Offline-first** — All processing happens locally, no cloud dependency

## Accessibility Needs

- WCAG AA compliance minimum
- Keyboard navigation for all interactive elements
- Clear focus states
- Sufficient contrast for data-heavy interfaces
- Reduced motion support

## Tech Stack

- **Frontend:** React + TypeScript + Tailwind CSS v4 (Tauri v2 shell)
- **Backend:** Python 3.14 (pandas, openpyxl, rapidfuzz, psycopg2)
- **Bridge:** JSON-RPC over stdin/stdout (Python subprocess)
- **Font:** MiSans VF (custom Chinese font)
- **Icons:** Inline SVG (Lucide-style, no emojis)
