# Segmented Control

The SegmentedControl component provides a tab-like interface with a compact design. It accepts an array of Tab components as children, similar to dcc.Tabs.

## Basic Usage

```python
from components.segmented_control.segmented_control import SegmentedControl
from dash.dcc import Tab

SegmentedControl(
    children=[
        Tab(
            label="Dashboard",
            value="dashboard",
            className="lucide--layout-dashboard",
            children=html.Div("Dashboard content")
        ),
        Tab(
            label="Analytics", 
            value="analytics",
            className="lucide--chart-line",
            children=html.Div("Analytics content")
        )
    ],
    value="dashboard",
    size="medium"
)
```

## Properties

- **children**: List of Tab components (required)
- **id**: Optional string or dict. If not provided, a random id will be generated
- **value**: Currently selected tab value 
- **size**: "small" or "medium" (default: "medium")

## Size Options

- **small**: Compact size for sidebar navigation or limited space
- **medium**: Standard size for main content areas

## Adding/Modifying Icons

To add or modify the icons in the tabs, you need to do the following steps:

1. Locate your desired icon on the [Dash Iconify / Lucide page](https://icon-sets.iconify.design/lucide/).

2. Get the css code for the icon on the bottom of the page. For instance, for the House icon, we have:

```css
.lucide--house {
    display: inline-block;
    width: 24px;
    height: 24px;
    --svg: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cg fill='none' stroke='%23000' stroke-linecap='round' stroke-linejoin='round' stroke-width='2'%3E%3Cpath d='M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8'/%3E%3Cpath d='M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'/%3E%3C/g%3E%3C/svg%3E");
    background-color: currentColor;
    -webkit-mask-image: var(--svg);
    mask-image: var(--svg);
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
    -webkit-mask-size: 100% 100%;
    mask-size: 100% 100%;
    }
```

3. Paste the code on assets/custom/icons.css, and keep ONLY the **--svg** property. Like this:

```css
.lucide--house {
  --svg: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cg fill='none' stroke='%23000' stroke-linecap='round' stroke-linejoin='round' stroke-width='2'%3E%3Cpath d='M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8'/%3E%3Cpath d='M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'/%3E%3C/g%3E%3C/svg%3E");
}
```

4. Finally, when defining your tabs, be sure to add the classname of the icon to the **className** property:

```python
   Tab(
        label="Overview",
        value="overview",
        className="lucide--house",
        # ... Other attributes
   )
```
