# Overview

This document answers foundational questions from scratch: what Dash is, what CSS is, what tokens are, what a design system is, and how this specific repository implements all of it. Assume zero prior frontend experience.

---

## What Is Dash?

Dash is a Python framework for building interactive web applications — dashboards, data tools, internal portals — without writing JavaScript, HTML, or CSS from scratch.

You write Python. Dash converts it into a working web interface that runs in a browser.

A Dash app has three layers:

1. **Layout** — what the page looks like, defined in Python using `html.*` and `dcc.*` objects
2. **Callbacks** — what happens when the user interacts (clicks, types, selects), defined as decorated Python functions
3. **CSS** — how everything is visually styled

```python
from dash import Dash, html, dcc, callback, Input, Output

app = Dash(__name__)

app.layout = html.Div([
    html.H1("Hello"),
    dcc.Input(id="name-input", type="text"),
    html.P(id="greeting-output"),
])

@callback(Output("greeting-output", "children"), Input("name-input", "value"))
def update_greeting(name):
    return f"Hello, {name}!"
```

This repository is a pre-built Dash application template. The app shell, routing, sidebar, header, and footer are already in place. You focus on adding pages, components, and feature logic.

---

## What Is CSS?

CSS (Cascading Style Sheets) controls the visual appearance of every element on a web page: colors, fonts, spacing, borders, layout, shadows.

In Dash, `html.Div("text")` creates an element with no visual styling. CSS classes apply visual rules to it:

```python
html.Div("text", className="my-card")
```

```css
/* assets/css/custom/my-card.css */
.my-card {
  background: #f0f0f0;
  padding: 16px;
  border-radius: 8px;
}
```

Dash automatically loads every `.css` file in the `assets/` folder — you do not import or link CSS files manually.

### Why Not `style={}`?

Dash allows inline style dictionaries:

```python
html.Div("text", style={"background": "#f0f0f0", "padding": "16px"})
```

**Do not use this in this repo.** Inline styles:
- Cannot respond to theme changes (a color swap would require editing dozens of files)
- Cannot be shared or reused between components
- Cannot be audited or reviewed in a single place
- Bypass the entire design system token layer

All styling in this repo belongs in `.css` files under `assets/css/`.

---

## What Are CSS Variables?

CSS variables (also called custom properties) store reusable values that any CSS rule can reference by name.

```css
/* Defined once, in assets/css/base/spacing-borders-shadows.css */
:root {
  --spacing-16: 16px;
  --border-radius-md: 8px;
  --text-icon-primary: rgb(15, 15, 15);
}

/* Used anywhere */
.my-card {
  padding: var(--spacing-16);
  border-radius: var(--border-radius-md);
  color: var(--text-icon-primary);
}
```

If the design team changes `--spacing-16` to `14px`, every element using that variable updates automatically. No searching through dozens of files.

**Rule: always use `var(--token-name)` for colors, spacing, radius, and shadows. Never hardcode values like `16px` or `#333333` in production CSS.**

---

## What Are Design Tokens?

Design tokens are named CSS variables that represent design decisions: a spacing value, a color, a shadow level. They are the "atoms" of the design system — everything else builds on top of them.

In this repo, all tokens live in `assets/css/base/` as CSS variables.

### Color Tokens

```css
/* Text and icons */
var(--text-icon-primary)     /* near-black, main text */
var(--text-icon-secondary)   /* 50% opacity, subdued */
var(--text-icon-tertiary)    /* 30% opacity, placeholder */
var(--text-icon-disabled)    /* 16% opacity, disabled state */
var(--text-icon-high-contrast) /* white, on dark backgrounds */

/* Surfaces (backgrounds) */
var(--surface-lightest)       /* barely-there tint */
var(--surface-light)          /* subtle background */
var(--surface-medium)         /* card, panel backgrounds */
var(--surface-heavy)          /* emphasized area */
var(--surface-page-background) /* page background (#fcfcfc) */

/* Borders */
var(--border-light)    /* subtle divider */
var(--border-medium)   /* standard border */
var(--border-heavy)    /* emphasized border */

/* Status colors */
var(--positive-primary)     /* dark green text */
var(--positive-background)  /* light green background */
var(--positive-border)      /* green border */
var(--warning-primary)      /* amber text */
var(--warning-background)   /* light amber background */
var(--negative-primary)     /* red text */
var(--negative-background)  /* light red background */

/* Theme palette (derived from --custom-theme) */
var(--primary-color-1)   /* lightest tint */
...
var(--primary-color-16)  /* darkest shade */
var(--accent-primary)    /* main accent color (= --primary-color-13) */
var(--accent-sidebar)    /* sidebar background (= --primary-color-14) */
```

### Spacing Tokens

```css
var(--spacing-1)    /* 1px */
var(--spacing-4)    /* 4px */
var(--spacing-8)    /* 8px */
var(--spacing-12)   /* 12px */
var(--spacing-16)   /* 16px */
var(--spacing-20)   /* 20px */
var(--spacing-24)   /* 24px */
var(--spacing-32)   /* 32px */
var(--spacing-40)   /* 40px */
var(--spacing-60)   /* 60px */
var(--spacing-80)   /* 80px */
```

### Border Radius Tokens

```css
var(--border-radius-xs)    /* 4px — tight corners */
var(--border-radius-sm)    /* 6px */
var(--border-radius-md)    /* 8px — standard card/button radius */
var(--border-radius-lg)    /* 10px */
var(--border-radius-xl)    /* 16px */
var(--border-radius-round) /* 100% — fully rounded / pill shape */
```

### Shadow Tokens

```css
var(--shadow-sm)   /* subtle: 0 0 8px rgba(black, 4%) */
var(--shadow-md)   /* card: 0 2px 12px rgba(black, 6%) */
```

---

## What Are Typography Classes?

Instead of writing `style={"fontSize": "13px", "fontWeight": 500}`, use the pre-built typography classes from `assets/css/base/typography.css` as `className` values:

| Class | Use case | Size | Weight |
|---|---|---|---|
| `.heading-1` | Page-level titles | 20px | Heavy |
| `.heading-2` | Section titles | 15px | Heavy |
| `.heading-3` | Subsection titles | 13px | Heavy |
| `.body-xl` | Featured or highlighted text | 20px | Heavy |
| `.body-md` | Large description text | 15px | Normal |
| `.body-sm` | Default body text, labels | 13px | Normal |
| `.body-xs` | Small labels, captions | 11px | Heavy |

Usage in Python:

```python
html.H1("Page Title", className="heading-1")
html.H2("Section Title", className="heading-2")
html.P("Normal body text.", className="body-sm")
html.P("Caption or label.", className="body-xs")
html.P("Large description.", className="body-md")
```

The font family (Inter) and all weights/line heights are already defined in `typography.css`. You never need to set them manually.

---

## What Is A Design System?

A design system is a coordinated set of standards, reusable components, and documented rules that keeps a product visually and behaviorally consistent across all features and contributors.

Without one, teams:
- Duplicate UI components with slight variations (three different button styles, each hand-built)
- Hardcode colors that don't match the brand
- Spend time rebuilding solved problems
- Create inconsistent, fragmented experiences for users

With one, teams:
- Pick from a known component library instead of inventing
- Know exactly where and how to apply styles
- Speak a shared visual language with designers
- Ship faster because the foundation is already built

### The Four Layers Of This Design System

```
Layer 1 — Design tokens     → assets/css/base/        colors, spacing, typography, shadows
Layer 2 — Component CSS     → assets/css/components/  visual rules per DS component
Layer 3 — Python APIs       → components/             reusable Python component functions
Layer 4 — Page composition  → pages/                  assembling components into views
```

Each layer builds on the one below. Tokens define raw values. Component CSS uses those tokens to style components. Python APIs render those components in Python code. Pages compose them into full views.

---

## How Python Components Work

In this repo, a "component" is a Python function that returns a Dash HTML element. You call it like any Python function:

```python
from components.button.button import Button
from components.section.section import Section
from components.banner.banner import Banner
from components.page_header.page_header import PageHeader
from components.cards.indicator_card.indicator_card import IndicatorCard

# A primary button with an icon
Button("Save", variant="primary", icon="lucide:save", id="save-btn")

# An outline destructive button
Button("Delete", variant="outline", destructive=True, icon="lucide:trash-2", id="delete-btn")

# A collapsible section with content
Section(
    title="Results",
    description="Filtered output based on selected criteria",
    content=[html.P("Content here")],
    open=True,
)

# A page header
PageHeader(
    icon="lucide:bar-chart",
    title="Analytics",
    subtitle="Overview of key performance metrics",
)

# A notification banner
Banner(
    header="Data load incomplete",
    description="3 rows could not be parsed.",
    variant="warning",
    icon="lucide:triangle-alert",
)
```

### Import Pattern

Every component is imported from its own module file:

```python
from components.<folder>.<filename> import <FunctionName>
```

Real examples:

```python
from components.button.button import Button
from components.section.section import Section
from components.banner.banner import Banner
from components.page_header.page_header import PageHeader
from components.tabs.tabs import Tabs
from components.table.V1.table import Table as TableV1
from components.cards.indicator_card.indicator_card import IndicatorCard
from components.cards.standard_card.standard_card import StandardCard
from components.progress.progress import Progress
from components.badge.badge import Badge
from utils.base.grid_system.grid import Container, Row, Col
```

---

## How The Theme Color Works

`--custom-theme` is a single integer from 0–360 representing a hue in the HSL color model. The design system generates a full 16-step color palette from this one number.

```css
/* In assets/css/base/colors.css — the ONLY line in the frozen base layer you may change */
:root {
  --custom-theme: 233;   /* 233 = blue-indigo */
}
```

From this single hue, the system automatically derives:
- `--primary-color-1` through `--primary-color-16` (lightest tint to darkest shade)
- `--accent-primary` (equal to `--primary-color-13` — the main accent used in buttons and links)
- `--accent-sidebar` (equal to `--primary-color-14` — the sidebar background)

**To change the brand color:** replace `233` with the integer the design team provides. HSL hue quick reference:

| Hue | Color |
|---|---|
| 0 | Red |
| 28 | Orange |
| 48 | Yellow |
| 135 | Green |
| 174 | Turquoise |
| 190 | Aqua |
| 208 | Blue |
| 233 | Blue-Indigo (default) |
| 293 | Purple |
| 320 | Pink |

This is the **only** permitted change in `assets/css/base/`. Every other token file is frozen.

---

## The Figma Reference

The design team maintains a Figma file with every component variant and the target page layout:

```
https://www.figma.com/design/7Ymb1vvX8ljNfh1d0zUwx0/LTP–Design-System-by-Significa
```

Use the **Detail Page** template inside the Figma as the baseline layout when building any new page. The Figma is the visual source of truth — when in doubt about spacing, component placement, or visual hierarchy, check there first.

---

## FAQ

### Do I need to know JavaScript to work in this repo?

No. Dash handles the browser-side rendering. You write Python. Some familiarity with CSS is needed for styling extensions, but the token system means most values are already defined — you reference them by name.

### Do I need to know HTML?

Basic familiarity helps. Dash layout objects (`html.Div`, `html.P`, `html.H1`, etc.) map directly to HTML tags. Knowing what a `<div>` or `<p>` tag does conceptually is sufficient.

### What is the difference between `html.*` and `dcc.*`?

`html.*` objects (from `dash.html`) map to plain HTML elements — `html.Div` → `<div>`, `html.P` → `<p>`, `html.H2` → `<h2>`. `dcc.*` objects (from `dash.dcc`) are Dash's higher-level interactive components: `dcc.Input`, `dcc.Dropdown`, `dcc.Graph`, `dcc.Store`, etc.

### What is `className`?

In Dash, `className` is the way you apply a CSS class to an element — it is equivalent to the HTML `class` attribute. Use it to apply CSS class names: `html.P("text", className="body-sm")`.

### Can I ever use `style={}`?

Only for temporary local experimentation during development. Never commit inline styles. Exception: `utils/base/grid_system/grid.py` uses inline styles internally for layout math (column widths, gutter margins) — this is a contained exception inside a utility with no equivalent token support.

### What is the difference between `assets/css/custom/` and `assets/css/pages/`?

`custom/` is for project-wide reusable styles — a component variant or utility class that could be used on multiple pages. `pages/` is for styles specific to one page's layout that will never be reused elsewhere.

### What is `dcc.Store`?

A `dcc.Store` is an invisible in-memory storage element. It holds data between callbacks without rendering anything visible. In `app.py`, `dcc.Store(id="sidebar--state")` tracks whether the sidebar is open so the toggle callback can read and update it.

### Why are there 16 `--primary-color-*` steps?

The palette gives fine-grained control over backgrounds, borders, hover states, and text at different lightness levels — all harmonically derived from one hue. Using tokens means the palette stays consistent when the hue changes.

### Can I create my own CSS variables?

Yes, but only in `assets/css/custom/`. Define them in `:root {}` or scoped to a class. Use the `--` prefix. Never add custom variables to `assets/css/base/`.

### What is the `data-theme` attribute on the app root?

In `app.py`, the root `html.Div` has `**{"data-theme": "custom-theme"}`. This is what activates the `.app[data-theme='custom-theme']` CSS selector in `colors.css`, which in turn activates the `--primary-color-*` palette derived from `--custom-theme`. Without this attribute, the palette would not apply.
