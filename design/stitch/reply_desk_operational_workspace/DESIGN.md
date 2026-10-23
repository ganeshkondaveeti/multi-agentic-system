---
name: Reply Desk Operational Workspace
colors:
  surface: '#071421'
  surface-dim: '#071421'
  surface-bright: '#2e3a49'
  surface-container-lowest: '#030f1c'
  surface-container-low: '#101d2a'
  surface-container: '#14212e'
  surface-container-high: '#1e2b39'
  surface-container-highest: '#293644'
  on-surface: '#d6e4f6'
  on-surface-variant: '#bacac5'
  inverse-surface: '#d6e4f6'
  inverse-on-surface: '#25313f'
  outline: '#859490'
  outline-variant: '#3c4a46'
  surface-tint: '#3cddc7'
  primary: '#57f1db'
  on-primary: '#003731'
  primary-container: '#2dd4bf'
  on-primary-container: '#00574d'
  inverse-primary: '#006b5f'
  secondary: '#a2c9ff'
  on-secondary: '#00315c'
  secondary-container: '#0071c7'
  on-secondary-container: '#f0f4ff'
  tertiary: '#e5d2ff'
  on-tertiary: '#41008b'
  tertiary-container: '#ceb0ff'
  on-tertiary-container: '#612ab1'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#62fae3'
  primary-fixed-dim: '#3cddc7'
  on-primary-fixed: '#00201c'
  on-primary-fixed-variant: '#005047'
  secondary-fixed: '#d3e4ff'
  secondary-fixed-dim: '#a2c9ff'
  on-secondary-fixed: '#001c38'
  on-secondary-fixed-variant: '#004882'
  tertiary-fixed: '#ecdcff'
  tertiary-fixed-dim: '#d5bbff'
  on-tertiary-fixed: '#270058'
  on-tertiary-fixed-variant: '#5a21ab'
  background: '#071421'
  on-background: '#d6e4f6'
  surface-variant: '#293644'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-xs:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  trace-mono:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
  code-inline:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 0.75rem
  gutter-dense: 0.5rem
  margin: 1rem
  margin-panel: 0.75rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system serves high-velocity fintech support operations handling complex mutual fund inquiries, escalations, and regulatory compliance. Built for specialized operators, compliance analysts, and dispute managers, the interface prioritizes spatial density, high visual trust, and rapid keyboard-first navigation over ornamental visuals.

The visual style merges tactical developer minimalism with enterprise-grade observability:
- **Zero Distraction Canvas:** Flat, matte dark surfaces avoid glowing drop shadows, ambient blur, or decorative gradients. Visual weight belongs exclusively to ticket state, SLA decay timers, and LLM inference markers.
- **Architectural Discipline:** Structured 1px dividers demarcate operational views, allowing continuous scanning across high-density triage queues and side-by-side agent diff views.
- **Agent Transparency:** Specialized autonomous agents (Facts, Pattern, Compliance) hold distinct semantic hues to provide immediate traceability of machine-generated claims vs verified transactional data.

## Colors

The palette is engineered strictly for dark operational environments. Surfaces maintain distinct luminescent stepping to reflect structural hierarchy without relying on drop shadows:

- **Canvas & Surface Architecture:**
  - Base Background: `#0B0F14` (root workspace level).
  - Base Surface: `#121821` (panels, sidebars, ticket feeds).
  - Raised Surface: `#18202B` (active cards, flyouts, contextual modals).
  - Subtle Border: `#243042` (strict structural dividers and panel borders).
- **Text & Hierarchy:**
  - Primary Content: `#E6EDF3` (crisp legibility across all data points).
  - Muted/Metadata: `#8B98A9` (timestamps, secondary labels, unselected values).
- **Primary Operational Accent:**
  - Action Teal: `#2DD4BF` (reserved exclusively for primary resolution actions, submission, and confirmation).
- **Agent Identification System:**
  - **Facts Agent:** `#58A6FF` (blue – extracts audited fund records, transaction logs, NAV prices).
  - **Pattern Agent:** `#A371F7` (violet – surfaces complaint trends, customer churn signals, precedent resolutions).
  - **Compliance Agent:** `#D29922` (amber – flags SEC/FINRA regulatory guardrails, liability risks, and disclosure requirements).
- **Operational Status:**
  - Success: `#3FB950`
  - Warning / Impending SLA: `#D29922`
  - Critical / Breach / Danger: `#F85149`
  - Info / Trace: `#58A6FF`

## Typography

Typography balances clean natural-language ticket readability with rigorous monospaced data alignment:

- **Inter** handles all human-readable interactions: ticket narratives, internal agent dialogues, form labels, and section headings. Base reading size is set to `14px` with a dense `20px` line height for maximum throughput without eye fatigue.
- **JetBrains Mono** governs machine outputs, verification logs, latency statistics, monetary figures, timestamps, portfolio account identifiers, and masked PII (e.g., `SSN-***-**-8421`, `ACC-0912-US`).
- All numeric tables and agent trace execution feeds must set tabular figures (`font-variant-numeric: tabular-nums`) to preserve strict column alignment across real-time streaming updates.

## Layout & Spacing

The layout is built around an uncompromising 8px baseline grid with 4px sub-grid allowances for compact operational controls:

- **Screen Distribution:**
  - Fixed-ratio three-column operational workbench:
    - Left Column (Queue & Filters): 280px to 320px fixed width.
    - Center Column (Active Case & Customer Thread): Fluid min-width (min 500px).
    - Right Column (Multi-Agent Inference & Verification Matrix): 380px to 460px fixed width.
- **Spacing Density:**
  - Cell padding within data grids and lists is strictly fixed at 8px vertical and 12px horizontal.
  - Form field spacing conforms to an 8px vertical cadence (`space-sm`).
  - Section dividers leverage absolute 1px lines without surrounding padding, reserving space entirely for actionable content.
- **Viewport Constraints:**
  - Primarily optimized for full-screen desktop operation (1440px and wider). When viewport width drops under 1280px, the multi-agent analysis panel collapses into an overlay drawer accessible via keyboard shortcut (`Cmd/Ctrl + K`).

## Elevation & Depth

Depth is established strictly through tonal layering and structural outlines. Floating shadows are prohibited to maintain precise, low-latency UI performance.

- **Level 0 (Workspace Canvas):** `#0B0F14` flat background.
- **Level 1 (Panels & Sidebar Containers):** `#121821` with a persistent `1px solid #243042` border.
- **Level 2 (Active Cards, Hover States, Table Rows):** `#18202B` background with `1px solid #243042`.
- **Level 3 (Dropdowns, Command Palette, Tooltips):** `#18202B` with a highlighted border (`#2DD4BF` at 30% opacity or `#8B98A9` at 20% opacity) and a direct flat edge offset: `0 4px 12px rgba(0, 0, 0, 0.45)`.
- **Focus Rings:** Non-offset, high-contrast outline (`2px solid #2DD4BF`) applied on interactive operational targets during keyboard focus.

## Shapes

The interface balances sharp industrial precision with ergonomic usability:
- Standard container and card radius is set uniformly to `10px` (`rounded-lg` level).
- Nested internal controls (inputs, sub-tabs, filter chips, monospace trace tags) inherit a tighter `6px` radius to prevent nested curvature clipping.
- System metrics badges, status indicators, and SLA timers use subtle `4px` or full pill shapes depending on their state as non-interactive status pills.

## Components

### Buttons
- **Primary Action (Resolution/Approve):** Solid `#2DD4BF`, text `#0B0F14`, font-weight `600`, 32px height, 12px horizontal padding. Hover brings lightness shift (`#5EEAD4`).
- **Secondary (Triage Actions):** Transparent background, `1px solid #243042`, text `#E6EDF3`. Hover state shifts surface to `#18202B` with border `#8B98A9`.
- **Danger (Reject/Flag Regulatory Violation):** Ghost state with `#F85149` text; on hover, fills with `rgba(248, 81, 73, 0.12)` with `1px solid #F85149`.

### Agent Badges & Identity Chips
- Height: 22px. Padding: 0 8px. Font: `JetBrains Mono` 11px.
- **Facts Agent:** Text `#58A6FF`, background `rgba(88, 166, 255, 0.10)`, border `1px solid rgba(88, 166, 255, 0.25)`.
- **Pattern Agent:** Text `#A371F7`, background `rgba(163, 113, 247, 0.10)`, border `1px solid rgba(163, 113, 247, 0.25)`.
- **Compliance Agent:** Text `#D29922`, background `rgba(210, 153, 34, 0.10)`, border `1px solid rgba(210, 153, 34, 0.25)`.

### Input Fields & Search Bars
- Background `#0B0F14`, border `1px solid #243042`, border-radius `6px`, text `#E6EDF3`, height `32px`.
- Monospace mode used automatically for account lookups, fund ticker symbols (e.g., `VTSAX`), and monetary amounts.
- Focus border turns `#2DD4BF` with no glow blur.

### Lists & Queue Tables
- Alternating or unified flat surface `#121821` with `1px solid #243042` row dividers.
- Selected state: Background `#18202B` with a vertical 2px left border strip matching the active agent or priority tier.
- Row heights clamped at 40px for dense scanning.

### Agent Trace & Verification Cards
- Self-contained container in `#18202B` with 10px radius and `1px solid #243042`.
- Header bar features agent tag, latency metric in JetBrains Mono (`142ms`), and confidence percentage tag (`99.4%`).
- Monospace collapsible diff blocks compare customer claims directly against custodial system logs.