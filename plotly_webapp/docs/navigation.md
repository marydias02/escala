# Navigation

This document explains exactly how the repository is organized, how each piece is wired at runtime, and where to start for every common task. Written for someone who has never worked in Dash or frontend.

---

## How The App Boots

The entry point is `app.py`. Here is what happens in order when you run `uv run app.py`:

1. Python imports `app.py`
2. `Dash(__name__, use_pages=True, external_stylesheets=[...])` creates the app instance and tells Dash to discover page modules automatically
3. `external_stylesheets` loads the AG Grid CSS theme and Font Awesome from CDN — these arrive before `assets/` files
4. `app.layout` is evaluated: it defines the full shell — sidebar (`html.Aside`), header (`html.Header`), main content area, and footer
5. `page_container` (imported from `dash`) sits inside the main area. Dash renders the current route's layout inside it — this is the "page slot"
6. `dcc.Store` elements are placed in the layout as invisible in-memory state holders (viewport width, sidebar open/closed state)
7. Callback modules imported at the bottom of `app.py` register their `@callback` decorators at import time
8. `app.run(debug=True)` starts the development server on `http://localhost:8050`

Key imports in `app.py`:

```python
from dash import Dash, dcc, html, page_container
from callbacks.layout import update_sidebar_logic
from components.breadcrumb.breadcrumb import Breadcrumb
from components.button.button import Button
from components.menu.menu import Menu
from components.sidebar_footer.sidebar_footer import SidebarFooter
from components.footer.footer import Footer
from components.select.select import Select
```

---

## Top-Level Structure

| Path | Role | When to edit |
|---|---|---|
| `app.py` | App entrypoint, shell layout, app-level stores | Shell changes, new sidebar links, app-wide callback imports |
| `assets/` | CSS, scripts, images, icons, sample data | Styling, JS helpers, static resources |
| `callbacks/` | Feature behavior and callback registration | All interaction and event logic |
| `components/` | Reusable Python UI component functions | New reusable UI building blocks |
| `pages/` | Route-level page composition | New pages, page layout changes |
| `utils/` | Shared non-UI helper logic | Grid wrappers, data loading helpers |
| `docs/` | DS guide knowledge base and skills | Guide maintenance and skill updates |
| `INDEX.md` | Agent-facing repo navigation map | After structural changes |
| `README.md` | First-contact setup and guide entrypoints | Setup or onboarding changes |
| `pyproject.toml` | Dependencies and tool configuration | Adding/removing packages |

---

## How Pages Work

Dash has a built-in multi-page system. When `use_pages=True` is set in the `Dash()` constructor, it scans the `pages/` folder for any `.py` file that calls `dash.register_page()` and automatically registers it as a route. No configuration file, no app.py imports needed for the page itself.

### The Page Pattern

Every page file follows this structure:

```python
# pages/analytics.py
import dash
from dash import html
from components.page_header.page_header import PageHeader
from utils.base.grid_system.grid import Container, Row, Col

# Step 1: register the route
dash.register_page(__name__, path="/analytics", title="Analytics")

# Step 2: define the layout
layout = html.Div(
    className="analytics-page",
    children=[
        PageHeader(
            icon="lucide:bar-chart",
            title="Analytics",
            subtitle="Key performance metrics",
        ),
        Container([
            Row([
                Col([html.P("Content goes here", className="body-sm")], xs=12, lg=8),
            ])
        ]),
    ],
)
```

**Rules:**
- `dash.register_page(__name__, path="...", title="...")` must be called at module level (not inside a function)
- `layout` must be a variable (or a no-argument function) defined at module level
- `path` is the URL route: `path="/analytics"` maps to `http://localhost:8050/analytics`
- `__name__` gives Dash the module name so it can identify this file — always use it as-is
- New pages that introduce page-specific `className` values should include a corresponding CSS file in `assets/css/pages/`; legacy demo pages may rely on shared DS/base classes only

### `layout` As A Variable vs A Function

```python
# Static: evaluated once at startup, reused on every visit
layout = html.Div([...])

# Dynamic: called fresh on every page visit — use this for live data
def layout():
    df = load_fresh_data()
    return html.Div([...])
```

Use a function when the page needs fresh data on each load (e.g., a table that reads from a database). Use a plain variable when the layout is static or data is loaded via callbacks.

### Adding A Page To The Sidebar

Route discovery is automatic. **Sidebar links are not.** The sidebar is hard-coded in `app.py`. To make a page accessible from the sidebar, open `app.py`, find the `sidebar__menu` div, and add a `Menu` entry:

```python
# In app.py — inside the sidebar__menu div
Menu(title="Analytics", href="/analytics"),
Menu(title="Analytics With Icon", href="/analytics", icon="lucide:bar-chart"),
```

`Menu` with `children` creates a collapsible group with sub-links:

```python
Menu(
    title="Reports",
    children=[
        dcc.Link("Monthly", href="/reports/monthly"),
        dcc.Link("Yearly", href="/reports/yearly"),
    ],
),
```

---

## How Callbacks Work

A callback is a Python function that Dash calls automatically when a component's property changes — a button click, a text input change, a dropdown selection.

### Basic Anatomy

```python
from dash import callback, Input, Output, State

@callback(
    Output("output-id", "children"),       # what property to update, on which component
    Input("button-id", "n_clicks"),        # what triggers the callback
    State("input-id", "value"),            # a value to read without triggering
    prevent_initial_call=True,             # don't fire once on page load
)
def my_callback(n_clicks, current_value):
    return f"Button clicked. Current value: {current_value}"
```

- `Output(component_id, property)` — the component property that gets updated when the callback runs
- `Input(component_id, property)` — the component property that triggers the callback when it changes
- `State(component_id, property)` — a value read at call time but does not trigger when it changes
- `prevent_initial_call=True` — suppresses the automatic first fire on page load

### Where Callbacks Live

All callbacks go in `callbacks/`, organized by feature area. The directory structure mirrors the feature, not the page:

```
callbacks/
  layout.py                 ← sidebar toggle logic
  banner/
    banner.py               ← dismiss callback for all Banner instances
  table/
    V1/
      primary_action_callback.py
      secondary_actions_callback.py
  tutorial_card/
    tutorial_card.py
```

A `@callback` decorator only registers when Python **imports the module**. If a callback is not firing, the module was never imported.

```python
# In app.py (for app-wide callbacks):
from callbacks.layout import update_sidebar_logic   # sidebar toggle
import callbacks.documentation.documentation        # documentation callbacks

# In a page file (for page-scoped callbacks):
import callbacks.my_feature.my_feature             # registers the decorator
```

### `prevent_initial_call=True`

Dash fires every callback once on page load with `None` as all Input values (unless the inputs have initial values). This usually causes errors or unintended behavior for interaction callbacks. **Always add `prevent_initial_call=True` to callbacks triggered by buttons, clicks, or user actions.**

### Pattern-Matching Callbacks (MATCH)

When multiple instances of the same component type appear on a page (multiple dismissible banners, multiple collapsible rows), use pattern-matching IDs so one callback handles all of them:

```python
# Component uses a dict ID:
id={"type": "banner", "index": "order-warning"}

# Callback uses MATCH — fires once per matching instance
from dash import MATCH, callback, Input, Output, State

@callback(
    Output({"type": "banner", "index": MATCH}, "className"),
    Input({"type": "banner", "index": MATCH, "subtype": "close"}, "n_clicks"),
    State({"type": "banner", "index": MATCH}, "className"),
    prevent_initial_call=True,
)
def dismiss_banner(n_clicks, current_class):
    if n_clicks:
        return current_class + " banner--dismissed"
    return current_class
```

The `Banner` component handles this automatically. When you use `Banner(header="...", id="my-banner")`, it assigns a dict ID internally and `callbacks/banner/banner.py` handles dismissal for every banner on the page via MATCH.

### Callback Factories (TableV1)

TableV1 uses callback factories — Python functions that create and register callbacks scoped to a specific `grid_id`. This allows multiple independent tables on the same page without ID conflicts.

```python
from functools import partial
from callbacks.table.V1.primary_action_callback import create_export_csv_callback_v1
from callbacks.table.V1.secondary_actions_callback import (
    create_quickfilter_secondary,
    create_sort_secondary,
    create_reset_secondary,
)

TableV1(
    data_frames=[{"df": df, "col_def": col_defs}],
    grid_id="orders-table",                          # must be unique on this page
    primary_action=("Export CSV", create_export_csv_callback_v1),
    secondary_actions=[
        ("Filter High", "lucide:filter", partial(create_quickfilter_secondary, value="High")),
        ("Sort Asc", "lucide:arrow-down-up", partial(create_sort_secondary, col_id="Status", direction="asc")),
        ("Reset", "lucide:brush-cleaning", create_reset_secondary),
    ],
    enable_reset=True,
)
```

The factory receives `grid_id` and registers callbacks namespaced to that specific table. Two tables on the same page need two different `grid_id` values.

---

## How Components Are Structured

Every component lives in `components/<name>/`. The folder contains at minimum the component Python file. New or updated components should include a `README.md` (legacy folders may still be missing docs).

```
components/
  button/
    button.py          ← Button() function
    README.md
  section/
    section.py
    README.md
  banner/
    banner.py          ← defines both Banner() and TableBanner()
  page_header/
    page_header.py
  cards/
    indicator_card/
      indicator_card.py
    page_card/
      page_card.py
    tutorial_card/
      tutorial_card.py
    workflow_card/
      workflow_card.py
  table/
    V1/
      table.py
      shared/
        col_def_config.py
        action_bar.py
  components_extra_design_system/
    (supplementary DS components — see below)
```

### Import Pattern

```python
from components.<folder>.<filename> import <FunctionName>
```

Real examples from the codebase:

```python
from components.button.button import Button
from components.section.section import Section
from components.banner.banner import Banner
from components.page_header.page_header import PageHeader
from components.tabs.tabs import Tabs
from components.select.select import Select
from components.menu.menu import Menu
from components.table.V1.table import Table as TableV1
from components.cards.indicator_card.indicator_card import IndicatorCard
from components.standard_card.standard_card import StandardCard
from components.sidebar_footer.sidebar_footer import SidebarFooter
from components.footer.footer import Footer
```

For nested paths (like cards):

```python
from components.cards.indicator_card.indicator_card import IndicatorCard
#    ^folder        ^subfolder       ^filename           ^function
```

---

## `components_extra_design_system`

This folder exists intentionally. It contains supplementary DS components that do not fit cleanly into a single canonical component family — multi-purpose or composite elements that the design system provides but that are not standalone concepts.

Its name does not follow the standard `components/<single-name>` convention — this is deliberate. Do not treat it as an error or an anomaly.

---

## The CSS Architecture

```
assets/css/
  base/           ← FROZEN — design tokens (colors, spacing, typography, layout, grid, reset)
  components/     ← FROZEN — one CSS file per DS component
  custom/         ← YOUR ZONE — all new project-specific styles go here
  pages/          ← YOUR ZONE — page-level layout overrides go here
```

CSS files in `assets/` are loaded automatically by Dash in folder/alphabetical order. No manual imports needed.

**Frozen means: do not edit.** `base/` and `components/` are the design system's shared source of truth. Editing them affects every component globally and can introduce silent regressions.

The only permitted change in the frozen layer is `--custom-theme` in the `:root {}` block of `assets/css/base/colors.css`.

**Component inventory cross-check:**

`ls components/` lists Python component folders. `ls assets/css/components/` lists component CSS files. These correspond one-to-one, with these known exceptions:

- `components_extra_design_system/` maps to `assets/css/components/components_extra_ds.css`
- `assets/css/components/datepicker.css`, `dropdown.css`, `table_actionbar.css`, `table_flyout.css` have no standalone Python component folder — they are used by composite components

---

## The Grid System

Layout uses `Container`, `Row`, `Col` from `utils/base/grid_system/grid.py`:

```python
from utils.base.grid_system.grid import Container, Row, Col
from dash import html

Container([
    Row([
        Col([html.Div("Left half")], xs=12, md=6),
        Col([html.Div("Right half")], xs=12, md=6),
    ]),
    Row([
        Col([html.Div("One third")], xs=12, lg=4),
        Col([html.Div("Two thirds")], xs=12, lg=8),
    ]),
])
```

Breakpoints: `xs`=0px · `sm`=640px · `md`=768px · `lg`=1024px · `xl`=1280px

Column values are 1–12, where 12 = full width. `xs=12, lg=6` means full-width on mobile, half-width on large screens.

`Container(children, fluid=True)` removes the max-width constraint for edge-to-edge layouts.

---

## The `utils/` Folder

| Path | Provides |
|---|---|
| `utils/base/grid_system/grid.py` | `Container`, `Row`, `Col` layout wrappers |
| `utils/table/data_loader.py` | Data loading helpers, column group splitters for TableV1 |

---

## `app.py` Responsibilities

Edit `app.py` only for:

- **Shell-level changes:** sidebar content, header action buttons, footer text
- **Sidebar links:** adding `Menu(title="...", href="...")` entries for new pages
- **External stylesheets:** adding CDN CSS links (e.g., new icon font, AG Grid theme)
- **Global stores:** `dcc.Store` elements for app-wide state
- **App-wide callback imports:** importing callback modules that must be active regardless of the current page

Do not put feature logic, page layouts, or business logic in `app.py`.

---

## Where To Start For Common Tasks

| If you want to... | Start at... |
|---|---|
| Understand DS concepts | `docs/overview.md` |
| Know the rules | `docs/best_practices.md` |
| Add a new page | `docs/workflows.md` → Workflow 2 |
| Add a sidebar link for a new page | Edit `sidebar__menu` div in `app.py` |
| Add a new component | `docs/workflows.md` → Workflow 3 |
| Find existing components | `ls components/` then read `components/<name>/README.md` |
| Add project-specific styles | `assets/css/custom/` |
| Add page-specific styles | `assets/css/pages/` |
| Understand a CSS token | `assets/css/base/INDEX.md` then the specific file |
| Change the brand color | `docs/workflows.md` → Workflow 4 |
| Add table behavior | `docs/workflows.md` → Workflow 9 |
| Add a feature callback | `docs/workflows.md` → Workflow 10 |

---

## FAQ

### Why doesn't my new page appear in the sidebar?

Route discovery is automatic — the URL works — but sidebar links are not. Open `app.py`, find the `sidebar__menu` div, and add `Menu(title="...", href="...")`.

### Why isn't my callback firing?

Two most common causes:
1. The callback module was never imported. The `@callback` decorator only registers when Python imports the file. Import it in `app.py` or at the top of the page that uses it.
2. The `id` on your component does not match the `id` string in your `Input` or `Output`.

### What is `page_container`?

`page_container` is a Dash-provided element that acts as a slot where the current page's layout renders. It is placed once in `app.py`. When the URL changes, Dash swaps the content inside `page_container` to the matching page's layout.

### Do I need to restart the server after adding a new page file?

Yes, for a brand new file — Dash discovers pages at startup. For edits to an existing page file, Dash hot-reloads in debug mode without a restart.

### Can `layout` in a page be a function?

Yes. If `layout` is a no-argument function, Dash calls it on each page visit. Use this when you need fresh data on every load. Plain variable layouts are static across visits.

### Can two pages define callbacks with the same output ID?

Not safely, unless the pages are never rendered at the same time (which is true for Dash pages routing — only one page is active at a time). But if the same callback ID could fire from two different page loads, prefer pattern-matching IDs to scope them.

### What is `dcc.Location`?

`dcc.Location` tracks the browser's current URL as a component property. In `app.py` it enables the breadcrumb callback to read the current path. You do not interact with it directly when adding new pages.

### What is `prevent_initial_call=True` and when do I need it?

By default, Dash fires every callback once on page load with `None` as all Input values. For button-click callbacks, this usually causes `None` errors. Add `prevent_initial_call=True` to any callback triggered by user interaction (clicks, dismissals, form submissions) to suppress the startup fire.

### How does the sidebar collapse work?

Two stores and a callback in `app.py` manage it. `dcc.Store(id="sidebar--state")` holds `{"open": True/False}`. A callback in `callbacks/layout.py` reads the state and returns updated `className` values for the sidebar and the hamburger button, toggling the `sidebar--collapsed` modifier class.
