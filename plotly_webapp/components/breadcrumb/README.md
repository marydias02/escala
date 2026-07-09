# Breadcrumb

The **Breadcrumb** component provides contextual navigation based on the current URL.  
It automatically reflects the page hierarchy and updates on route changes.

The component is **URL-driven**, meaning breadcrumb items are derived from the pathname and **do not** need to be manually defined.

All configuration is optional and handled internally.

## Usage

The `Breadcrumb()` component is currently defined in the main application layout (`app.py`).  
Because of this, it is automatically rendered in the header of **every page** in the app.

No additional setup is required when creating new pages.

## Responsiveness

On smaller screens, if the breadcrumb contains **three or more elements**, the intermediate items are replaced with an ellipsis (`...`).

> _Example:_ Home > ... > Current Page

The screen-width breakpoint that controls this behavior is currently defined in the `breadcrumb.py` file and is set to 790px.
