# Best Practices

The complete rulebook for extending this design system safely and consistently. Every rule has a rationale. Treat this document as the source of truth when making any implementation decision.

---

## The Five Core Constraints

These five rules are always in effect. Every other rule in this document elaborates on one of them.

1. **No inline styles.** All styling goes in `.css` files.
2. **Never edit frozen DS layers** (`assets/css/base/` or `assets/css/components/`).
3. **Reuse before creating.** Always check existing components first.
4. **Components must be reusable.** No one-off components scoped to a single page.
5. **Use CSS variables.** Never hardcode colors, sizes, or spacing.

---

## Styling Rules

### No Inline Styles In Production Code

```python
# WRONG — inline style bypasses the design system
html.Div("Card", style={"background": "#f0f0f0", "padding": "16px", "borderRadius": "8px"})

# RIGHT — all styling in a CSS file
html.Div("Card", className="my-card")
```

```css
/* assets/css/custom/my-card.css */
.my-card {
  background: var(--surface-medium);
  padding: var(--spacing-16);
  border-radius: var(--border-radius-md);
}
```

**Why:** inline styles cannot respond to theme changes, cannot be shared across components, cannot be audited in one place, and circumvent the token system entirely.

**Tolerated exception:** `utils/base/grid_system/grid.py` uses inline styles internally for flex layout math (column widths, gutter margins). This is a contained utility with no CSS variable equivalent. Do not extend this pattern.

### Use Typography Classes, Not Font Style Dicts

Never set font size, weight, or line height via `style={}`. Use the pre-built classes from `assets/css/base/typography.css`:

```python
# WRONG
html.H2("Title", style={"fontSize": "15px", "fontWeight": 550})

# RIGHT
html.H2("Title", className="heading-2")
```

Full typography class set:

| Class | Semantic use | Size | Weight |
|---|---|---|---|
| `.heading-1` | Page-level title | 20px | Heavy |
| `.heading-2` | Section title | 15px | Heavy |
| `.heading-3` | Subsection title | 13px | Heavy |
| `.body-xl` | Featured or highlighted text | 20px | Heavy |
| `.body-md` | Large description text | 15px | Normal |
| `.body-sm` | Default body text | 13px | Normal |
| `.body-xs` | Labels, captions | 11px | Heavy |

### Frozen CSS Boundaries

These two directories must never be edited for project work:

```
assets/css/base/       ← FROZEN — design tokens
assets/css/components/ ← FROZEN — DS component styles
```

**Why:** they are the shared source of truth for the entire system. A local edit creates silent regressions in every component that uses the same tokens.

The only exception: `--custom-theme` in the `:root {}` block of `assets/css/base/colors.css`.

Project styles go in:

```
assets/css/custom/     ← all new project-specific reusable styles
assets/css/pages/      ← page-level layout and composition overrides
```

### Token-First CSS

Every new CSS rule must reference design tokens via `var(--...)`:

```css
/* WRONG */
.status-chip {
  padding: 4px 10px;
  background: #f0f0f0;
  border-radius: 99px;
  color: #333;
  border: 1px solid #e0e0e0;
}

/* RIGHT */
.status-chip {
  padding: var(--spacing-4) var(--spacing-10);
  background: var(--surface-medium);
  border-radius: var(--border-radius-round);
  color: var(--text-icon-primary);
  border: var(--border-normal) solid var(--border-medium);
}
```

**Available token categories:**

**Spacing:** `--spacing-1`, `--spacing-2`, `--spacing-4`, `--spacing-6`, `--spacing-8`, `--spacing-10`, `--spacing-12`, `--spacing-14`, `--spacing-16`, `--spacing-20`, `--spacing-24`, `--spacing-32`, `--spacing-40`, `--spacing-60`, `--spacing-80`

**Border radius:** `--border-radius-xs` (4px) · `--border-radius-sm` (6px) · `--border-radius-md` (8px) · `--border-radius-lg` (10px) · `--border-radius-xl` (16px) · `--border-radius-round` (100%)

**Text colors:** `--text-icon-primary` · `--text-icon-secondary` · `--text-icon-tertiary` · `--text-icon-disabled` · `--text-icon-high-contrast`

**Surface (backgrounds):** `--surface-lightest` · `--surface-light` · `--surface-medium` · `--surface-heavy` · `--surface-heaviest` · `--surface-page-background` · `--surface-modal`

**Borders:** `--border-lightest` · `--border-light` · `--border-medium` · `--border-heavy`

**Status colors:** `--positive-primary/highlight/background/border` · `--warning-primary/highlight/background/border` · `--negative-primary/highlight/background/border`

**Theme palette:** `--primary-color-1` through `--primary-color-16` · `--accent-primary` · `--accent-sidebar`

**Shadows:** `--shadow-sm` · `--shadow-md`

**Borders (widths):** `--border-normal` (1px) · `--border-focus` (4px)

### Small Files, One Concern

Create one CSS file per concern in `assets/css/custom/`. Use descriptive names:

```
custom/
  tooltip.css           ← tooltip component styles
  status-chip.css       ← custom status indicator
  export-panel.css      ← export/download panel layout
```

Not:

```
custom/
  styles.css            ← everything piled in one file
  misc.css
```

---

## Component Rules

### Import Pattern

Every component is imported from its own module:

```python
from components.<folder>.<filename> import <FunctionName>

# Common imports:
from components.button.button import Button
from components.section.section import Section
from components.banner.banner import Banner
from components.page_header.page_header import PageHeader
from components.tabs.tabs import Tabs
from components.select.select import Select
from components.menu.menu import Menu
from components.progress.progress import Progress
from components.badge.badge import Badge
from components.table.V1.table import Table as TableV1
from components.cards.indicator_card.indicator_card import IndicatorCard
```

### Reuse-First Workflow

Before building anything new:

1. `ls components/` — does a component already exist?
2. Check `components/<name>/README.md` — does it have the variant or prop you need?
3. `ls assets/css/components/` — is there a CSS modifier you can apply?
4. Only if nothing fits: create a new component

### Component API Conventions

Follow these patterns when writing new components:

```python
# components/status_chip/status_chip.py
from typing import Any, Dict, Literal, Optional, Union
from dash import html

Variant = Literal["positive", "warning", "negative", "neutral"]

def StatusChip(
    label: str,
    variant: Variant = "neutral",
    id: Union[str, Dict[str, Any]] = "status-chip",
    className: Optional[str] = None,
) -> html.Span:
    classes = [f"status-chip status-chip--{variant}", "body-xs"]
    if className:
        classes.append(className)
    return html.Span(label, className=" ".join(classes), id=id)
```

**Rules:**
- **Function-based** — components are plain Python functions, not classes
- **Typed props** — use Python type hints; use `Literal` for constrained string choices
- **`id` accepts both string and dict** — `Union[str, Dict[str, Any]]` supports pattern-matching
- **`className` is optional** — lets the caller append extra classes without replacing the base ones
- **Returns a single Dash HTML element** — the return type is always a `html.*` element
- **No logic in CSS files** — visual variants are expressed via modifier class names, not computed in Python

### BEM Class Naming

This repo uses BEM (Block–Element–Modifier) naming for CSS classes. Follow it for all new components:

```
block              → button
block--modifier    → button--primary  button--destructive  button--loading
block__element     → section__header  section__content  banner__footer
block__element--modifier → section__header--open
```

Real examples from the codebase:

```
button
button--primary / button--ghost / button--outline / button--ghost.secondary
button--destructive
button--loading
section__header
section__content
section__extra-elements
banner__content
banner--warning / banner--positive / banner--negative
banner--dismissed
```

### New Component Folder Structure

```
components/
  my_component/
    my_component.py     ← component function (snake_case filename)
    README.md           ← required
```

CSS for the new component goes in `assets/css/custom/my-component.css`. **Never** in `assets/css/components/`.

### Component README Requirements

Every new component must have a `README.md` containing:

1. **Purpose** — what this component is for, when to use it
2. **Props table** — each prop: name, type, default value, description
3. **Usage example** — a working Python snippet that can be copy-pasted
4. **Constraints** — limitations, gotchas, maximum values, dependencies on other components

### The `id` Prop: String vs Dict

Use a plain string when there will only be one instance of this component on a page:

```python
Button("Save", id="save-button")
Section(title="Overview", id="overview-section")
```

Use a dict when the component may appear multiple times and needs per-instance callbacks:

```python
# The Banner component auto-generates a dict id:
Banner(header="Warning", id="low-stock-banner")
# → internally becomes: id={"type": "banner", "index": "low-stock-banner"}

# The MATCH callback handles all instances without enumerating them:
Output({"type": "banner", "index": MATCH}, "className")
```

When building new components that can appear multiple times on a page and need individual callbacks (dismissable notifications, per-row actions, collapsible list items), follow this pattern.

### Component Source Priority

When no DS component exists for a needed UI element:

| Priority | Source | Notes |
|---|---|---|
| 1st | Dash Core Components | `dcc.Dropdown`, `dcc.Graph`, `dcc.Checklist`, `dcc.Slider`, etc. |
| 2nd | Dash Mantine Components | More complete component set, heavier dependency |
| 3rd | Custom component in `components/` | Must be reusable, must have README, styled in `custom/` |

See `docs/resources.md` for links.

---

## Theming Rules

### Only One Change Allowed In The Frozen Layer

`--custom-theme` in the `:root {}` block of `assets/css/base/colors.css`:

```css
:root {
  --custom-theme: 233;   /* only this integer may be changed */
}
```

### The Value Is Provided By The Design Team

Do not invent or guess hue values. The design team provides the exact integer. Typical values: blue-indigo = 233, blue = 208, green = 135, purple = 293.

### Do Not Touch Derived Palette Variables

`--primary-color-1` through `--primary-color-16`, `--accent-primary`, and `--accent-sidebar` are all auto-derived from `--custom-theme` via the `.app[data-theme='custom-theme']` block. Do not override them manually. Change only the hue and let the cascade produce the palette.

### Typography Changes Require Justification

Overriding typography tokens outside of `assets/css/base/typography.css` is a deviation. If a page or component requires a different font size, document the reason and scope the override tightly in `assets/css/custom/` or `assets/css/pages/`.

---

## Callback Rules

### Keep Interaction Logic In `callbacks/`

Page files are for composition. Callbacks are for behavior.

```python
# WRONG — callback defined inside a page file
@callback(Output("result", "children"), Input("btn", "n_clicks"))
def handle_click(n):
    return "Clicked"

# RIGHT — callback in callbacks/feature/feature.py, imported by the page
```

```python
# pages/my_page.py
import callbacks.my_feature.my_feature   # registers the decorator

layout = html.Div([
    Button("Go", id="btn"),
    html.P(id="result"),
])
```

### Import Callbacks So Decorators Register

A `@callback` decorator only runs when Python imports the file. If a callback is not firing, confirm the module is in the import chain.

```python
# App-wide callbacks: import in app.py
from callbacks.layout import update_sidebar_logic
import callbacks.banner.banner    # registers banner dismiss for all pages

# Page-specific callbacks: import at top of the page
import callbacks.export.export    # registers export callback
```

### Use `prevent_initial_call=True` For Interaction Callbacks

Dash fires all callbacks once at startup. For any callback triggered by clicks or user actions, this will receive `None` inputs and usually error. Always add `prevent_initial_call=True`:

```python
@callback(
    Output("result", "children"),
    Input("action-btn", "n_clicks"),
    prevent_initial_call=True,   # do not fire on page load
)
def on_click(n_clicks):
    return "Action triggered"
```

### Use Pattern-Matching For Repeated Component Instances

For components that appear multiple times (dismissable banners, per-row action buttons, collapsible items), use dict IDs and `MATCH` — not enumerated IDs like `"banner-1"`, `"banner-2"`:

```python
# Enumerate IDs — WRONG for dynamic lists
Banner(header="A", id="banner-1")
Banner(header="B", id="banner-2")

# Pattern-matching — RIGHT
Banner(header="A", id="alert-a")   # Banner assigns {"type": "banner", "index": "alert-a"} internally
Banner(header="B", id="alert-b")   # one MATCH callback handles both
```

---

## Table Rules

1. Every `TableV1` instance must have a **unique** `grid_id` — two tables on the same page must not share one
2. Use callback factories for table behavior — do not write ad hoc `@callback` definitions for table interactions
3. Table callback code belongs in `callbacks/table/V1/`
4. Keep column definition logic in `components/table/shared/` helpers when it is reused across pages
5. Use `partial()` from `functools` to pre-fill factory arguments:
   ```python
   from functools import partial
   partial(create_quickfilter_secondary, value="High")
   ```

---

## Grid System Rules

1. Use `Container`, `Row`, `Col` from `utils/base/grid_system/grid.py` for all responsive layout composition
2. Use breakpoint props (`xs`, `sm`, `md`, `lg`, `xl`) instead of hardcoded widths or inline flex hacks
3. Use `no_gutter` only when the layout explicitly requires zero gap between columns
4. Keep grid logic in page composition — not inside reusable component internals

---

## Structural Rules

### Project Placement

When starting a new project from this template, place the repo at:

```
your-project/
└── plotly_webapp/
    └── frontend/    ← this repo
```

### Separation of Concerns

| Layer | Responsibility | What does NOT go here |
|---|---|---|
| `pages/` | Layout composition | Business logic, callbacks |
| `callbacks/` | Interaction and event logic | Layout, styling |
| `components/` | Reusable UI building blocks | Page-specific one-offs |
| `utils/` | Shared non-UI helpers | UI components, callbacks |
| `assets/css/custom/` | Project-specific styles | Frozen layer edits |

---

## Deviation Policy

A deviation from any rule in this document is acceptable only when all of the following are true:

1. There is a documented business or client reason
2. The scope is minimal and contained
3. The change lives in `custom/` or `pages/` — never in frozen layers
4. The rationale is captured in a code comment or PR description

---

## Review Checklist

Before merging any change, verify:

- [ ] No edits to `assets/css/base/` or `assets/css/components/`
- [ ] New styles are in `assets/css/custom/` or `assets/css/pages/`
- [ ] CSS uses `var(--token)` — no hardcoded colors, sizes, or spacing
- [ ] No inline `style={}` in production code
- [ ] Existing components were checked before building new ones
- [ ] New component: function-based, typed props, `id` accepts string and dict
- [ ] New component: CSS in `assets/css/custom/`, not `assets/css/components/`
- [ ] New component: `README.md` is present, accurate, and includes a usage example
- [ ] Typography uses `className` (`.heading-*`, `.body-*`), not inline font styles
- [ ] Callback logic is in `callbacks/`, not in page composition files
- [ ] Callback module is imported somewhere in the startup path
- [ ] `prevent_initial_call=True` is set on interaction callbacks
- [ ] `TableV1` instances have unique `grid_id` values
- [ ] New page has a corresponding CSS file in `assets/css/pages/`
- [ ] `className` values in the page Python file match class names in that CSS file
- [ ] Sidebar links for new pages are added to `app.py`

---

## FAQ

### Why do some existing files use `style={}`?

Legacy code and demo pages in the DS template predate strict enforcement. Treat them as historical context, not as the current standard. All new code must follow the CSS file + className pattern.

### Can I override a frozen component's style for a specific use case?

Yes — add override rules in `assets/css/custom/` or `assets/css/pages/`, targeting the component's existing class names with higher specificity. Do not edit the component's file in `assets/css/components/`.

```css
/* assets/css/pages/my-page.css — override only in this page context */
.my-page .button--primary {
  background: var(--primary-color-12);  /* darker variant for this page */
}
```

### What if I need a color that does not exist in the token palette?

Check whether a combination of existing tokens achieves the same result. If not, ask the design team — do not add ad hoc color constants. Never hardcode a hex value in production CSS.

### Can I define new CSS variables in `custom/`?

Yes. Variables defined in `assets/css/custom/` are valid. Use the `--` prefix and define them in `:root {}` or scoped to a class block.

### What if a component has no README?

It needs one before being merged. Inspect the component source, understand its API, and write it.

### Why do I need a unique `grid_id` per table?

TableV1 uses callback factories that register callbacks scoped to `grid_id`. Two tables sharing a `grid_id` would cause both to respond to the same callback outputs, producing conflicts and Dash errors.

### Do I need to update the sidebar after adding a page?

Yes, manually. Dash registers the page route automatically, but sidebar links are hard-coded in the `sidebar__menu` div in `app.py` and must be added by hand.
