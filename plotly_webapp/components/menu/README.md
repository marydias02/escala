# Menu

The Menu component renders a sidebar navigation item. It supports simple links and expandable items with subpages.

The sidebar layout is typically defined in `app.py`, where the base page structure is created.

## Basic Usage

### Simple sidebar (page links only)

```python
from dash import dcc
from dash import html
from components.menu.menu import Menu

html.Aside(
    className="app__sidebar",
    children=[
        html.Div(
            className="sidebar__menu",
            children=[
                Menu(title="Homepage", href="/", icon="lucide:home"),
                Menu(title="Grid", href="/grid"),
                Menu(title="Tabs", href="/components/tabs"),
            ],
        ),
    ],
)
```

### Sidebar with an expandable submenu

```python
from dash import dcc
from dash import html
from components.menu.menu import Menu

html.Aside(
    className="app__sidebar",
    children=[
        html.Div(
            className="sidebar__menu",
            children=[
                Menu(title="Homepage", href="/", icon="lucide:home"),
                Menu(title="Grid", href="/grid"),
                Menu(
                    title="Components",
                    children=[
                        dcc.Link("Buttons", href="/components/button"),
                        dcc.Link("Tabs", href="/components/tabs"),
                    ],
                ),
                Menu(title="Settings", href="/settings"),
            ],
        ),
    ],
)
```

## Properties

- **title**: Menu label (required)
- **href**: Link path for simple items (default: auto-generated from title)
- **icon**: Optional icon string (Dash Iconify / Lucide)
- **children**: Optional list of `dcc.Link` items to create a dropdown
- **open**: Initial open state for dropdown menus (default: `False`)

## Behavior

- If **children** is provided, the Menu renders a collapsible dropdown using `<details>`/`<summary>`.
- If **children** is omitted, the Menu renders a single clickable link row.
- For simple items, the entire row is clickable (not just the text).
