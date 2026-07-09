# Section

The **Section** component provides a collapsible content container with a header, optional description, and optional right-aligned actions or additional elements.

## Basic Usage

```python
from components.section.section import Section

Section(
    title="General Information",
    content=html.P("Section content goes here"),
)
```

## Properties

- **title**: Section title (required)
- **description**: Optional text displayed below the title in the header
- **extra_element**: One or more elements rendered on the right side of the section header
- **content**: The main content of the section, rendered inside the collapsible area
- **open**: Defines the initial open or closed state of the section (default: "False"/Closed)
- **id**: The section ID. Can be a string or a pattern-matching dictionary (default: "section-id")

### Extra Element

In the right corner of the Section header you can optionally include additional components.
Common use cases are buttons, tags or badges

```python
from components.section.section import Section
from components.button.button import Button
from components.tag.tag import Tag

Section(
    title="Section with extra elements",
    extra_element=[
      Button("Create Run", id="section-create-btn", icon="lucide:play"),
      Tag("Complete", size="xs", variant="positive")
    ],
    content=html.P("Section content goes here"),
)
```

### Content

The main content of the section can be composed of just one element as the example above or can include multiple complex elements encapsulated in a list or a Div for example

```python
from components.section.section import Section
from components.button.button import Button
from components.tag.tag import Tag
from components.table.V1.table import Table

Section(
    title="Section with extra elements",
    extra_element=[
      Button("Create Run", id="section-create-btn", icon="lucide:play"),
      Tag("Complete", size="xs", variant="positive")
    ],
    content=[
      html.H1("Overview Table"),
      Table(
          data_frames=[...],
      ),
    ],
    open=True
)
```
