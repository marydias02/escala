# Workflows

Step-by-step execution guides. Each workflow is self-contained and grounded in current repository patterns. Follow them in order — every step matters.

---

## 1. Project Bootstrapping

### Target Folder Layout

```
your-project/
└── plotly_webapp/
    └── frontend/    ← clone this repo here
```

### Steps

1. Clone this repository into `plotly_webapp/frontend/`:
   ```bash
   git clone <repo-url> plotly_webapp/frontend
   ```
2. Open the folder in your editor
3. Install dependencies:
   ```bash
   uv sync
   ```
4. Start the development server:
   ```bash
   uv run app.py
   ```
5. Open `http://localhost:8050` in your browser

### Validation

- App loads without import errors in the terminal
- Sidebar and header are visible
- Home page route (`/`) renders content
- No red error messages in the browser console (open with F12 → Console)

---

## 2. Adding A New Page

### Pattern Source

`pages/index.py`, `pages/components.py`, `pages/grid.py`

### Step 1 — Create the page file

```python
# pages/analytics.py
import dash
from dash import html

from components.page_header.page_header import PageHeader
from utils.base.grid_system.grid import Container, Row, Col

# Register the route with Dash
dash.register_page(__name__, path="/analytics", title="Analytics")

# Define the page layout
layout = html.Div(
    className="analytics-page",
    children=[
        PageHeader(
            icon="lucide:bar-chart",
            title="Analytics",
            subtitle="Overview of key performance metrics",
        ),
        Container([
            Row([
                Col([html.P("Content goes here", className="body-sm")], xs=12, lg=8),
            ])
        ]),
    ],
)
```

### Step 2 — Add a sidebar link (if the page should appear in navigation)

Open `app.py`. Find the `sidebar__menu` div and add a `Menu` entry:

```python
# Inside the sidebar__menu div in app.py
Menu(title="Analytics", href="/analytics"),
# Or with an icon:
Menu(title="Analytics", href="/analytics", icon="lucide:bar-chart"),
```

Note: `dash.register_page()` makes the URL work automatically. The sidebar link must be added manually — it is not automatic.

### Step 3 — Create the page CSS file

If your page introduces page-specific layout classes, create a CSS file in `assets/css/pages/`. Legacy/demo pages may rely only on shared DS/base classes and not need a dedicated page CSS file.

Create `assets/css/pages/analytics.css`:

```css
/* analytics page layout */

.analytics-page {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-40);
  margin-bottom: var(--spacing-40);
}

.analytics-page__header {
  width: 100%;
}

.analytics-page__content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-16);
}
```

Mirror these class names in your page Python file:

```python
layout = html.Div(
    className="analytics-page",
    children=[
        html.Section(className="analytics-page__header", children=[...]),
        html.Section(className="analytics-page__content", children=[...]),
    ],
)
```

Follow the BEM naming pattern: `<page-name>__<section>`. Keep all page-level layout composition here and all responsive overrides in a `@media` block at the bottom of the same file.

### Important Rules

- `dash.register_page(__name__, path="...", title="...")` must be at module level, not inside a function
- `layout` must be a variable or no-argument function at module level
- The `path` is the URL: `path="/reports/monthly"` maps to `http://localhost:8050/reports/monthly`
- Keep heavy logic in `callbacks/` — page files are for layout composition only
- `__name__` is a Python built-in that gives the current module's name — always use it as-is

### Validation

- The URL `http://localhost:8050/analytics` loads your page
- Page layout CSS file exists in `assets/css/pages/`
- `className` values in the Python file match class names in the CSS file
- The sidebar link appears and navigates correctly
- No import errors in the terminal
- Breadcrumb shows the correct path
- Page renders inside the shell (sidebar and header still visible)

---

## 3. Adding A New Component

### Pattern Source

`components/button/button.py`, `components/section/section.py`

### Step 1 — Check if it already exists

```bash
ls components/
ls assets/css/components/
```

Read the README of any candidate before deciding to build new. Many components have variants via props (`variant="outline"`, `size="xs"`, etc.) that might already cover your need.

### Step 2 — Create the component folder and file

Follow this exact structure and conventions:

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

Conventions to follow:
- Function-based (not a class)
- Typed props with Python type hints
- `Literal` for constrained string choices
- `id` accepts both `str` and `dict` for pattern-matching support
- Optional `className` that appends to base classes
- Return type is a single `html.*` element

### Step 3 — Add the component's CSS in `assets/css/custom/`

```css
/* assets/css/custom/status-chip.css */
.status-chip {
  display: inline-flex;
  align-items: center;
  padding: var(--spacing-2) var(--spacing-8);
  border-radius: var(--border-radius-round);
}

.status-chip--positive {
  background: var(--positive-background);
  color: var(--positive-primary);
  border: var(--border-normal) solid var(--positive-border);
}

.status-chip--warning {
  background: var(--warning-background);
  color: var(--warning-primary);
  border: var(--border-normal) solid var(--warning-border);
}

.status-chip--negative {
  background: var(--negative-background);
  color: var(--negative-primary);
  border: var(--border-normal) solid var(--negative-border);
}

.status-chip--neutral {
  background: var(--surface-medium);
  color: var(--text-icon-secondary);
  border: var(--border-normal) solid var(--border-medium);
}
```

CSS goes in `assets/css/custom/` — **not** in `assets/css/components/` (that folder is frozen DS-owned).

### Step 4 — Write the README

```markdown
# StatusChip

Compact inline status indicator for displaying categorical states.

## Props

| Prop | Type | Default | Description |
|---|---|---|---|
| label | str | required | Display text |
| variant | "positive" / "warning" / "negative" / "neutral" | "neutral" | Visual style |
| id | str or dict | "status-chip" | Component ID — use dict for pattern-matching |
| className | str or None | None | Additional CSS classes appended to base classes |

## Usage

from components.status_chip.status_chip import StatusChip

StatusChip("Active", variant="positive")
StatusChip("Delayed", variant="warning", id="order-status")
StatusChip("Failed", variant="negative")

## Constraints

- Intended for compact inline display — uses body-xs sizing
- Maximum of one line of text
```

### Step 5 — Import and use the component

```python
from components.status_chip.status_chip import StatusChip

StatusChip("Active", variant="positive", id="row-status")
```

### Validation

- Component renders in at least one page without errors
- CSS classes resolve correctly (browser dev tools → inspect element → check applied styles)
- No inline styles in the component file
- README is present and accurate

---

## 4. Changing The Theme Color

This is the **only** permitted change in the frozen base layer.

### Steps

1. Open `assets/css/base/colors.css`
2. Find this line at the top of the `:root {}` block:
   ```css
   :root {
     --custom-theme: 233;
   }
   ```
3. Replace `233` with the hue integer provided by the design team
4. Save the file — the browser hot-reloads immediately in debug mode

### Hue Reference

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

### What Updates Automatically

Changing `--custom-theme` updates: sidebar background color (`--accent-sidebar`), primary button color (`--accent-primary`), all 16 `--primary-color-*` tints and shades.

### What Does NOT Change

Neutral colors (black, white, surface, border, text, status colors) are independent of `--custom-theme` and stay the same regardless of hue.

### Validation

- Sidebar background updates to the new hue
- Primary action buttons update
- `--accent-primary` and `--accent-sidebar` reflect the new hue
- No other files in `assets/css/base/` were modified

---

## 5. Adding Project Styles

### Steps

1. Create a focused CSS file in `assets/css/custom/` with a descriptive name:
   ```
   assets/css/custom/export-panel.css
   ```

2. Write CSS using only token variables:
   ```css
   .export-panel {
     background: var(--surface-medium);
     border: var(--border-normal) solid var(--border-light);
     border-radius: var(--border-radius-md);
     padding: var(--spacing-16);
     box-shadow: var(--shadow-sm);
   }

   .export-panel__title {
     color: var(--text-icon-primary);
     margin-bottom: var(--spacing-8);
   }

   .export-panel__actions {
     display: flex;
     gap: var(--spacing-8);
     margin-top: var(--spacing-12);
   }
   ```

3. Apply the class in your component or page:
   ```python
   from components.button.button import Button
   from dash import html

   html.Div(
       className="export-panel",
       children=[
           html.H3("Export", className="export-panel__title heading-3"),
           html.Div(
               className="export-panel__actions",
               children=[
                   Button("Download CSV", icon="lucide:download", variant="primary", id="download-btn"),
               ]
           ),
       ]
   )
   ```

### Rules

- Never hardcode pixel values or color codes — use `var(--token)`
- One concern per file — do not pile unrelated rules into one CSS file
- File names must describe the concern, not the page: `tooltip.css` not `index-extras.css`

---

## 6. Adding A Sidebar Link

### Steps

1. Open `app.py`
2. Find the `sidebar__menu` div
3. Add a `Menu` entry inside it:

   ```python
   # Basic link
   Menu(title="Reports", href="/reports"),

   # Link with a Lucide icon
   Menu(title="Reports", href="/reports", icon="lucide:file-text"),

   # Collapsible group with sub-links
   Menu(
       title="Reports",
       children=[
           dcc.Link("Monthly", href="/reports/monthly"),
           dcc.Link("Yearly", href="/reports/yearly"),
       ],
   ),
   ```

4. Make sure the `href` exactly matches the `path` in `dash.register_page()`

### Note

Sidebar links and page routes are independent. A page route works without a sidebar link (accessible via direct URL). A sidebar link without a matching `dash.register_page()` will navigate to a 404.

---

## 7. Using Icons

Icons come from **DashIconify** using the **Lucide** icon set.

### Steps

1. Find your icon name at: `https://lucide.dev/icons/`  
   Icon names use `kebab-case`: `arrow-down-up`, `triangle-alert`, `file-text`

2. Use in Python with the `lucide:` prefix:
   ```python
   from dash_iconify import DashIconify

   DashIconify(icon="lucide:star")
   DashIconify(icon="lucide:download", width=20)
   DashIconify(icon="lucide:triangle-alert", className="my-icon")
   ```

3. Most DS components have an `icon` prop that accepts the same string directly:
   ```python
   Button("Save", icon="lucide:save", variant="primary", id="save-btn")
   Menu(title="Home", href="/", icon="lucide:home")
   PageHeader(title="Reports", icon="lucide:file-text", ...)
   ```

4. Icons used as tab indicators use a CSS class pattern instead (from `typography.css`):
   ```python
   Tab(label="Overview", value="overview", className="lucide--layout-dashboard")
   ```
   Note the `--` separator and no `lucide:` prefix when used as a CSS class.

### Rules

- Use Lucide icons only
- Never add other icon fonts or icon sets without approval
- For custom icon mask or color overrides, add rules in `assets/css/custom/icons.css`

---

## 8. Using Charts

Dash uses Plotly for charts. No third-party charting libraries (Chart.js, D3, etc.).

### Steps

```python
import plotly.express as px
from dash import dcc

# Create a Plotly figure
fig = px.bar(df, x="Category", y="Value", title="Sales by Category")

# Embed in the layout
dcc.Graph(id="sales-chart", figure=fig)
```

### Styling Charts

- Use `fig.update_layout()` for chart appearance (background color, font, margins)
- Use `fig.update_traces()` for series colors — reference DS palette colors as hex if needed, but prefer the design team's provided chart palette
- Keep chart containers inside `Section` or `Container/Row/Col` wrappers for consistent spacing
- Do not set a fixed `height` on `dcc.Graph` unless explicitly needed — let the grid control layout

---

## 9. Using The Grid System

The grid provides `Container`, `Row`, and `Col` from `utils/base/grid_system/grid.py`.

### Steps

```python
from utils.base.grid_system.grid import Container, Row, Col
from dash import html

Container([
    Row([
        # Full width on mobile, half width above md breakpoint
        Col([html.Div("Left", className="body-sm")], xs=12, md=6),
        Col([html.Div("Right", className="body-sm")], xs=12, md=6),
    ]),
    Row([
        # One third / two thirds above lg breakpoint
        Col([html.Div("Sidebar")], xs=12, lg=4),
        Col([html.Div("Main content")], xs=12, lg=8),
    ]),
])
```

### Breakpoints

| Prop | Min-width | Meaning |
|---|---|---|
| `xs` | 0px | All screen sizes (mobile-first default) |
| `sm` | 640px | Small tablets and up |
| `md` | 768px | Tablets and up |
| `lg` | 1024px | Laptops and up |
| `xl` | 1280px | Large displays |

Column values are 1–12, where 12 = full width. Unset breakpoints inherit from the smaller breakpoint.

### Common Patterns

```python
# 3-column card grid (stacks to 1 column on mobile)
Col([...], xs=12, md=6, lg=4)

# 2-column split (stacks on mobile)
Col([...], xs=12, md=6)

# Full width always
Col([...], xs=12)
```

### `fluid=True`

Use on `Container` when the layout must stretch edge-to-edge:

```python
Container([Row([...])], fluid=True)
```

### `no_gutter`

Removes the 7.5px horizontal padding on columns. Use only when the layout explicitly requires zero gap:

```python
Row([Col([...], no_gutter=True)], no_gutter=True)
```

---

## 10. Adding A TableV1

### Pattern Source

`pages/index.py`, `components/table/V1/table.py`, `callbacks/table/V1/`

### Step 1 — Load data and define columns

```python
import pandas as pd
from utils.table.data_loader import get_brand_and_year_columns
from components.table.shared.col_def_config import create_simple_table_column_defs

df = pd.read_csv("path/to/data.csv")
brand_cols, year_cols = get_brand_and_year_columns(list(df.columns))
col_defs = create_simple_table_column_defs(brand_cols, year_cols)
```

### Step 2 — Import callback factories

```python
from functools import partial
from callbacks.table.V1.primary_action_callback import create_export_csv_callback_v1
from callbacks.table.V1.secondary_actions_callback import (
    create_quickfilter_secondary,
    create_sort_secondary,
    create_reset_secondary,
)
```

### Step 3 — Instantiate the table

```python
from components.table.V1.table import Table as TableV1

TableV1(
    data_frames=[{"df": df, "col_def": col_defs}],
    grid_id="orders-table",             # must be unique on this page
    title="Orders",
    primary_action=("Export CSV", create_export_csv_callback_v1),
    secondary_actions=[
        ("Filter High",  "lucide:filter",       partial(create_quickfilter_secondary, value="High")),
        ("Sort Asc",     "lucide:arrow-down-up", partial(create_sort_secondary, col_id="Status", direction="asc")),
        ("Reset",        "lucide:brush-cleaning", create_reset_secondary),
    ],
    enable_reset=True,
)
```

### Multi-Tab Table

To show different datasets in tabs on the same table:

```python
from components.tabs.tabs import Tabs
from dash.dcc import Tab

TableV1(
    data_frames=[
        {"df": monthly_df, "col_def": monthly_cols, "tab": "monthly"},
        {"df": yearly_df,  "col_def": yearly_cols,  "tab": "yearly"},
    ],
    grid_id="tabbed-table",
    tabs=Tabs(
        value="monthly",
        children=[
            Tab(label="Monthly", value="monthly", className="lucide--table-2"),
            Tab(label="Yearly",  value="yearly",  className="lucide--table-2"),
        ],
    ),
    title="Sales Data",
    primary_action=("Export CSV", create_export_csv_callback_v1),
    enable_reset=True,
)
```

### Rules

- `grid_id` must be unique — two tables on the same page must not share an ID
- Use callback factories — do not write manual `@callback` functions for table behavior
- Keep column definitions in shared helpers (`components/table/shared/`) when they are reused

### Validation

- Table renders with correct columns and rows
- Filter, sort, and reset actions respond to clicks
- Tab switching shows the correct dataset
- No `grid_id` collision errors in the terminal

---

## 11. Adding A Feature Callback

### Steps

**Step 1 — Create the callback module**

```python
# callbacks/export/export.py
from dash import callback, Input, Output, State

@callback(
    Output("download-component", "data"),
    Input("export-btn", "n_clicks"),
    State("table-data-store", "data"),
    prevent_initial_call=True,
)
def trigger_export(n_clicks, stored_data):
    # process stored_data and return a download payload
    ...
```

**Step 2 — Import the module so the decorator registers**

```python
# In the page file that uses this callback:
import callbacks.export.export   # registers the @callback decorator

layout = html.Div([
    Button("Export", id="export-btn", icon="lucide:download"),
    dcc.Download(id="download-component"),
])
```

Or in `app.py` if the callback should be active on all pages.

### Rules

- Callback IDs (`Input("...", ...)`, `Output("...", ...)`) must match the component `id` values exactly
- A callback module that is never imported will never register — always verify the import chain
- Keep callback logic pure where possible — no layout construction inside callback functions

### Validation

- Callback fires on the expected user interaction
- No `Duplicate callback outputs` error in the terminal
- `prevent_initial_call=True` is set on interaction-triggered callbacks

---

## 12. Consulting The Figma

```
https://www.figma.com/design/7Ymb1vvX8ljNfh1d0zUwx0/LTP–Design-System-by-Significa
```

### Steps

1. Open the Figma file
2. Navigate to the **Detail Page** template — this is the target layout for new pages
3. Use the Figma as the visual authority:
   - Check spacing and padding between elements
   - Verify which component variants are called for (primary vs outline button, which card type, etc.)
   - Confirm component placement and visual hierarchy
4. Translate the design through existing DS components first
5. If a Figma element has no Python equivalent, check `components_extra_design_system/` before building from scratch

---

## FAQ

### Do pages auto-register in the sidebar?

No. The URL route auto-registers via `dash.register_page()`. The sidebar link must be added manually in the `sidebar__menu` div in `app.py`.

### Can I have two tables on the same page?

Yes. Give each a different `grid_id`. The callback factories scope all behavior to the specific table.

### Why does my callback fire immediately with `None` values?

Dash fires every callback once on startup. Add `prevent_initial_call=True` to suppress this for interaction callbacks.

### Where do component styles go vs page styles?

Component CSS (rules that describe the component's own appearance) goes in `assets/css/custom/<component>.css`. Page-specific layout adjustments (how the component is positioned within a particular page) go in `assets/css/pages/<page>.css`.

### Can a page `layout` be a function?

Yes. Define it as a no-argument function: `def layout(): return html.Div([...])`. Dash calls it on every visit. Useful when content should reload fresh data on each page load.

### What is `partial()` and why is it used with table callbacks?

`partial()` from Python's `functools` module pre-fills arguments into a function, creating a new callable with those arguments locked in. Table callback factories accept a `grid_id` at registration time — `partial(create_quickfilter_secondary, value="High")` locks in `value="High"` so the factory receives it correctly when the table calls it.
