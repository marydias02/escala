import dash

from components.button.button import Button
from components.page_header.page_header import PageHeader
from components.tabs.tabs import Tabs
from dash.dcc import Tab

from assets.scripts.documentation.general_documentation_page import (
  DocumentationPage,
  ExampleSection,
  PropertiesSection,
  SectionHeader
)

dash.register_page(
    __name__,
    path="/components/button",
    title="Button",
)

TOC_LINKS = [
    ("Default Button", "default-button"),
    ("Size", "size"),
    ("Variant", "variant"),
    ("Disabled", "disabled"),
    ("Destructive", "destructive"),
    ("Loading", "loading"),
    ("Properties", "properties"),
]

PROPERTIES = [
    {"name": "children", "type": "(list | str | int | component ; optional)",
     "description": "The visible content of the button (text or nested components). "
                    "When loading=True, children are visually hidden but remain accessible."},

    {"name": "icon", "type": "(str ; optional)",
     "description": "Icon identifier passed to DashIconify (e.g. 'lucide:trash'). "
                    "The icon is rendered before the children and hidden when loading=True."},

    {"name": "variant", "type": "('primary' | 'ghost' | 'outline' | 'ghost secondary' ; default 'primary')",
     "description": "Defines the visual style of the button."},

    {"name": "size", "type": "('2xs' | 'xs' | 's' | 'm' ; default 'm')",
     "description": "Controls the size of the button."},

    {"name": "id", "type": "(str | dict ; default 'button')",
     "description": "The component identifier. Supports both string and pattern-matching dict IDs."},

    {"name": "loading", "type": "(boolean ; default False)",
     "description": "When true, hides the button content and icon and displays a loading spinner."},

    {"name": "destructive", "type": "(boolean ; default False)",
     "description": "Marks the button as a destructive action. Changes the button style to red."},

    {"name": "className", "type": "(str ; optional)",
     "description": "Additional CSS class names appended to the root button element."},

    {"name": "**kwargs", "type": "(any ; optional)",
     "description": "Additional HTML button attributes forwarded to the underlying element (e.g., disabled)."},
]


layout = DocumentationPage(
    title="Button",
    toc_links=TOC_LINKS,
    content_sections=[
        PageHeader(title="Button", icon="lucide:group", subtitle="Displays a clickable button component"),

        # Default Button
        SectionHeader("Default Button", id="default-button"),
        ExampleSection(
            preview=[
                Button("Default"),
                Button(icon="lucide:square-asterisk"),
                Button("Default", icon="lucide:square-asterisk"),
            ],
            code="""
from components.button.button import Button

Button("Default"),
Button(icon="lucide:square-asterisk"),
Button("Default", icon="lucide:square-asterisk")
""",
            section_id="default-button",
        ),

        # Size
        SectionHeader("Size", id="size", subtitle="Use the size attribute to change the component from 2xs to m"),
        Tabs(
            children=[
                Tab(
                    label="Default",
                    value="Default",
                    children=ExampleSection(
                        preview=[
                            Button("Size M", size="m"),
                            Button(icon="lucide:square-asterisk", size="m"),
                            Button("Size M", icon="lucide:square-asterisk", size="m"),
                        ],
                        code="""
from components.button.button import Button

Button("Size M", size="m"),
Button(icon="lucide:square-asterisk", size="m"),
Button("Size M", icon="lucide:square-asterisk", size="m")
""",
                        code_id="code-size_m",
                    ),
                ),
                Tab(
                    label="2XS",
                    value="2XS",
                    children=ExampleSection(
                        preview=[
                            Button("Size 2XS", size="2xs"),
                            Button(icon="lucide:square-asterisk", size="2xs"),
                            Button("Size 2XS", icon="lucide:square-asterisk", size="2xs"),
                        ],
                        code="""
from components.button.button import Button

Button("Size 2XS", size="2xs"),
Button(icon="lucide:square-asterisk", size="2xs"),
Button("Size 2XS", icon="lucide:square-asterisk", size="2xs")
""",
                        code_id="code-size_2xs",
                    ),
                ),
                Tab(
                    label="XS",
                    value="XS",
                    children=ExampleSection(
                        preview=[
                            Button("Size XS", size="xs"),
                            Button(icon="lucide:square-asterisk", size="xs"),
                            Button("Size XS", icon="lucide:square-asterisk", size="xs"),
                        ],
                        code="""
from components.button.button import Button

Button("Size XS", size="xs"),
Button(icon="lucide:square-asterisk", size="xs"),
Button("Size XS", icon="lucide:square-asterisk", size="xs")
""",
                        code_id="code-size_xs",
                    ),
                ),
                Tab(
                    label="S",
                    value="S",
                    children=ExampleSection(
                        preview=[
                            Button("Size S", size="s"),
                            Button(icon="lucide:square-asterisk", size="s"),
                            Button("Size S", icon="lucide:square-asterisk", size="s"),
                        ],
                        code="""
from components.button.button import Button

Button("Size S", size="s"),
Button(icon="lucide:square-asterisk", size="s"),
Button("Size S", icon="lucide:square-asterisk", size="s")
""",
                        code_id="code-size_s",
                    ),
                ),
            ],
            value="Default",
            size="small",
        ),

        # Variant
        SectionHeader("Variant", id="variant", subtitle="Use the variant attribute to change the component styling"),
        Tabs(
            children=[
                Tab(
                    label="Default",
                    value="Default",
                    children=ExampleSection(
                        preview=[
                            Button("Primary", variant="primary"),
                            Button(icon="lucide:square-asterisk", variant="primary"),
                            Button("Primary", icon="lucide:square-asterisk", variant="primary"),
                        ],
                        code="""
from components.button.button import Button

Button("Primary", variant="primary"),
Button(icon="lucide:square-asterisk", variant="primary"),
Button("Primary", icon="lucide:square-asterisk", variant="primary")
""",
                        code_id="code-var_p",
                    ),
                ),
                Tab(
                    label="Outline",
                    value="Outline",
                    children=ExampleSection(
                        preview=[
                            Button("Outline", variant="outline"),
                            Button(icon="lucide:square-asterisk", variant="outline"),
                            Button("Outline", icon="lucide:square-asterisk", variant="outline"),
                        ],
                        code="""
from components.button.button import Button

Button("Outline", variant="outline"),
Button(icon="lucide:square-asterisk", variant="outline"),
Button("Outline", icon="lucide:square-asterisk", variant="outline")
""",
                        code_id="code-var_o",
                    ),
                ),
                Tab(
                    label="Ghost",
                    value="Ghost",
                    children=ExampleSection(
                        preview=[
                            Button("Ghost", variant="ghost"),
                            Button(icon="lucide:square-asterisk", variant="ghost"),
                            Button("Ghost", icon="lucide:square-asterisk", variant="ghost"),
                        ],
                        code="""
from components.button.button import Button

Button("Ghost", variant="ghost"),
Button(icon="lucide:square-asterisk", variant="ghost"),
Button("Ghost", icon="lucide:square-asterisk", variant="ghost")
""",
                        code_id="code-var_g",
                    ),
                ),
                Tab(
                    label="Ghost Secondary",
                    value="Ghost Secondary",
                    children=ExampleSection(
                        preview=[
                            Button("Ghost Secondary", variant="ghost secondary"),
                            Button(icon="lucide:square-asterisk", variant="ghost secondary"),
                            Button("Ghost Secondary", icon="lucide:square-asterisk", variant="ghost secondary"),
                        ],
                        code="""
from components.button.button import Button

Button("Ghost Secondary", variant="ghost secondary"),
Button(icon="lucide:square-asterisk", variant="ghost secondary"),
Button("Ghost Secondary", icon="lucide:square-asterisk", variant="ghost secondary")
""",
                        code_id="code-var_gs",
                    ),
                ),
            ],
            value="Default",
            size="small",
        ),

        # Disabled
        SectionHeader("Disabled", id="disabled", subtitle="Use the disabled attribute to change the component state"),
        ExampleSection(
            preview=[
                Button("Primary", icon="lucide:square-asterisk", variant="primary", disabled=True),
                Button("Outline", icon="lucide:square-asterisk", variant="outline", disabled=True),
                Button("Ghost", icon="lucide:square-asterisk", variant="ghost", disabled=True),
                Button("Ghost Secondary", icon="lucide:square-asterisk", variant="ghost secondary", disabled=True),
            ],
            code="""
from components.button.button import Button

Button("Primary", icon="lucide:square-asterisk", variant="primary", disabled=True),
Button("Outline", icon="lucide:square-asterisk", variant="outline", disabled=True),
Button("Ghost", icon="lucide:square-asterisk", variant="ghost", disabled=True),
Button("Ghost Secondary", icon="lucide:square-asterisk", variant="ghost secondary", disabled=True),
""",
            section_id="disabled",
        ),

        # Destructive
        SectionHeader("Destructive", id="destructive", subtitle="Use the destructive attribute to change the component state"),
        ExampleSection(
            preview=[
                Button("Delete", icon="lucide:trash", variant="primary", destructive=True),
                Button(icon="lucide:trash", variant="primary", destructive=True),
                Button("Cancel", icon="lucide:trash", variant="outline", destructive=True),
                Button(icon="lucide:trash", variant="outline", destructive=True),
                Button("Eliminate", icon="lucide:trash", variant="ghost", destructive=True),
                Button(icon="lucide:trash", variant="ghost secondary", destructive=True),
            ],
            code="""
from components.button.button import Button

Button("Delete", icon="lucide:trash", variant="primary", destructive=True),
Button(icon="lucide:trash", variant="primary", destructive=True),

Button("Cancel", icon="lucide:trash", variant="outline", destructive=True),
Button(icon="lucide:trash", variant="outline", destructive=True),

Button("Eliminate", icon="lucide:trash", variant="ghost", destructive=True),
Button(icon="lucide:trash", variant="ghost secondary", destructive=True),
""",
            section_id="destructive",
        ),

        # Loading
        SectionHeader("Loading", id="loading", subtitle="Use the loading attribute to change the component state"),
        ExampleSection(
            preview=[
                Button("Loading", icon="lucide:square-asterisk", variant="primary", loading=True),
                Button(icon="lucide:square-asterisk", variant="primary", loading=True),
                Button("Loading", icon="lucide:square-asterisk", variant="outline", loading=True),
                Button(icon="lucide:square-asterisk", variant="outline", loading=True),
                Button("Loading", icon="lucide:square-asterisk", variant="ghost", loading=True),
                Button(icon="lucide:square-asterisk", variant="ghost", loading=True),
                Button("Loading", icon="lucide:square-asterisk", variant="ghost secondary", loading=True),
                Button(icon="lucide:square-asterisk", variant="ghost secondary", loading=True),
            ],
            code="""
from components.button.button import Button

Button("Loading", icon="lucide:square-asterisk", variant="primary", loading=True),
Button(icon="lucide:square-asterisk", variant="primary", loading=True),

Button("Loading", icon="lucide:square-asterisk", variant="outline", loading=True),
Button(icon="lucide:square-asterisk", variant="outline", loading=True),

Button("Loading", icon="lucide:square-asterisk", variant="ghost", loading=True),
Button(icon="lucide:square-asterisk", variant="ghost", loading=True),

Button("Loading", icon="lucide:square-asterisk", variant="ghost secondary", loading=True),
Button(icon="lucide:square-asterisk", variant="ghost secondary", loading=True),
""",
            section_id="loading",
        ),

        # Properties
        SectionHeader("Button Properties", id="properties"),
        PropertiesSection(PROPERTIES),
    ],
)
