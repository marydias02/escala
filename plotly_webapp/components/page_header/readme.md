# Page Header

The Page Header component provides a standard header block for pages, with a required title and optional subtitle, icon, and extra elements. It adapts its layout based on which optional fields you include.

## Basic Usage

```python
from components.page_header.page_header import PageHeader

PageHeader(
    title="Dashboard"
)
```

## Properties

- **title**: Header title text (required)
- **icon**: Optional icon name for DashIconify (e.g. "lucide:chart-line")
- **subtitle**: Optional subtitle text
- **title_id**: Optional string or dict id for the title element
- **subtitle_id**: Optional string or dict id for the subtitle element
- **kwargs**: Any additional props supported by `dash.html.Header` (e.g. className)

## Page Header with Subtitle and Icon

```python
from components.page_header.page_header import PageHeader

PageHeader(
    title="Sales Overview",
    subtitle="Last 30 days",
    icon="lucide:chart-line"
)
```

## Page Heather with Extra Elements

```python
from dash import html
from components.page_header.page_header import PageHeader
from components.button.button import Button

PageHeader(
    title="Users",
    subtitle="Active this week",
)
```
