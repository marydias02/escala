import dash
from dash import html, dcc

from components.select.select import Select

from utils.base.grid_system.grid import Col, Container, Row

from components.cards.indicator_card.indicator_card import IndicatorCard


from components.button.button import Button
from utils.base.grid_system.grid import Container, Row, Col
from components.page_header.page_header import PageHeader
from components.section.section import Section
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
    path="/components/select",
    title="Select",
)


TOC_LINKS = [
    ("Default Select", "default_select"),
    ("Captions", "captions"),
    ("Disabled", "disabled"),
    ("Multi Select", "multi_select"),
    ("Error", "error"),
    ("Color Mode", "color_mode"),
    ("Properties", "properties"),
]



PROPERTIES = [
    {"name": "select_options", "type": "(dict | list[str] | list[dict] ; required)",
     "description": "Options displayed in the dropdown. Accepts a {label: value} dict, a list of strings "
                    "(labels=values), or a list of dicts like {'label': '', 'value': '', 'disabled': False} "
                    "with the disabled flag defaulting to False."},

    {"name": "value", "type": "(str | dict | list ; optional)",
     "description": "Optional default selection. Supports a single string or dict (with label/value) and a "
                    "list when multi=True."},

    {"name": "placeholder", "type": "(str ; optional)",
     "description": "Placeholder text shown when no value is selected."},

    {"name": "multi", "type": "(boolean ; default False)",
     "description": "Enable multi-select mode so multiple values can be chosen."},

    {"name": "clearable", "type": "(boolean ; default True)",
     "description": "Shows a clear icon that removes the current selection."},

    {"name": "closeOnSelect", "type": "(boolean ; default True)",
     "description": "Closes the dropdown menu immediately after an option is picked."},

    {"name": "disabled", "type": "(boolean ; default False)",
     "description": "Disable the select control so it cannot be interacted with."},

    {"name": "searchable", "type": "(boolean ; default True)",
     "description": "Enable the search input inside the dropdown to filter options."},

    {"name": "id_select", "type": "(str ; optional)",
     "description": "ID passed to the underlying Dash dropdown, useful for wiring labels or messages."},

    {"name": "wrapper_className", "type": "(str ; optional)",
     "description": "Additional CSS class applied to the wrapper div around the select."},
    
    {"name": "select_color_mode", "type": "('default' | 'custom_light' ; default 'default')",
     "description": "Controls the color styling of the wrapper via helper classes; use 'custom_light' "
                    "when placing the select on dark backgrounds."},

    {"name": "select_background_color", "type": "(str ; optional)",
     "description": "CSS color value (typically a variable) that matches the dark background when using "
                    "select_color_mode='custom_light' so the component blends into its surface."},

    {"name": "label", "type": "(str ; optional)",
     "description": "Optional label text rendered above the select."},

    {"name": "additional_message", "type": "(str ; optional)",
     "description": "Optional helper text rendered below the select."},

    {"name": "has_error", "type": "(boolean ; default False)",
     "description": "Apply error styling when set to True."},

    {"name": "error_message", "type": "(str ; optional)",
     "description": "Text displayed below the select when has_error=True."},

    {"name": "**kwargs", "type": "(any ; optional)",
     "description": "Additional HTML button attributes forwarded to the underlying element (e.g., disabled)."},
]



layout = DocumentationPage(
    title="Select",
    toc_links=TOC_LINKS,
    content_sections=[
        PageHeader(title="Select", icon="lucide:group", subtitle="Displays a select dropdown component"),

        # Default Select
        SectionHeader("Default Select", id="default_select", subtitle="Select Options can be defined having the labels equal to the values or having them be different"),
        Tabs(
            children=[
                Tab(
                    label="Label and Value",
                    value="Label and Value",
                    children=ExampleSection(
                        preview=[
                            Select(
                                select_options={'New York City':'ny', 'Montreal':"mt", 'San Francisco':'sf'}
                            )
                        ],
                        code="""
from components.select.select import Select

Select(
    select_options={'New York City':'ny', 'Montreal':"mt", 'San Francisco':'sf'}
)
""",
                        code_id="code_label_value",
                    ),
                ),
                Tab(
                    label="Value",
                    value="Value",
                    children=ExampleSection(
                        preview=[
                            Select(
                                select_options=['New York City', 'Montreal', 'San Francisco']
                            )
                        ],
                        code="""
from components.select.select import Select

Select(
    select_options=['New York City', 'Montreal', 'San Francisco']
)
""",
                        code_id="code_value",
                    ),
                ),
            ],
            value="Label and Value",
            size="small",
        ),

        # Captions
        SectionHeader("Captions", id="captions"),
        Tabs(
            children=[
                Tab(
                    label="Label",
                    value="Label",
                    children=ExampleSection(
                        preview=[
                            Select(
                                select_options={'New York City':'ny', 'Montreal':"mt", 'San Francisco':'sf'},
                                label="Label"
                            )
                        ],
                        code="""
from components.select.select import Select

Select(
    select_options={'New York City':'ny', 'Montreal':"mt", 'San Francisco':'sf'},
    label="Label"
)
""",
                        code_id="code_label",
                    ),
                ),
                Tab(
                    label="Placeholder",
                    value="Placeholder",
                    children=ExampleSection(
                        preview=[
                            Select(
                                select_options={'New York City':'ny', 'Montreal':"mt", 'San Francisco':'sf'},
                                label="Label",
                                placeholder="Select placeholder"
                            )
                        ],
                        code="""
from components.select.select import Select

Select(
    select_options={'New York City':'ny', 'Montreal':"mt", 'San Francisco':'sf'},
    label="Label",
    placeholder="Select placeholder"
)
""",
                        code_id="code_placeholder",
                    ),
                ),
                Tab(
                    label="Additional Message",
                    value="Additional Message",
                    children=ExampleSection(
                        preview=[
                            Select(
                                select_options=['New York City', 'Montreal', 'San Francisco'],
                                label="Label",
                                placeholder="Select placeholder",
                                additional_message="Extra message with info"
                            )
                        ],
                        code="""
from components.select.select import Select

Select(
    select_options=['New York City', 'Montreal', 'San Francisco'],
    label="Label",
    placeholder="Select placeholder",
    additional_message="Extra message with info"
)
""",
                        code_id="code_additional_message",
                    ),
                ),
            ],
            value="Label",
            size="small",
        ),

        # Disabled
        SectionHeader("Disabled", id="disabled", subtitle="The select can be disabled in full or it can have one of the options disabled"),
        Tabs(
            children=[
                Tab(
                    label="Full Disable",
                    value="Full Disable",
                    children=ExampleSection(
                        preview=[
                            Select(
                                select_options=['New York City', 'Montreal', 'San Francisco'],
                                label="Label",
                                disabled=True,
                            )
                        ],
                        code="""
from components.select.select import Select

Select(
    select_options=['New York City', 'Montreal', 'San Francisco'],
    label="Label",
    disabled=True,
)
""",
                        code_id="code_full_disable",
                    ),
                ),
                Tab(
                    label="Option Disable",
                    value="Option Disable",
                    children=ExampleSection(
                        preview=[
                            Select(
                                select_options=[
                                    {'label': 'New York City', 'value': 'New York City', 'disabled':False},
                                    {'label': 'Montreal', 'value': 'Montreal', 'disabled':True},
                                    {'label': 'San Francisco', 'value': 'San Francisco', 'disabled':False},
                                ],
                                label="Label"
                            ),
                        ],
                        code="""
from components.select.select import Select

Select(
    select_options=[
        {'label': 'New York City', 'value': 'New York City', 'disabled':False},
        {'label': 'Montreal', 'value': 'Montreal', 'disabled':True},
        {'label': 'San Francisco', 'value': 'San Francisco', 'disabled':False},
    ],
    label="Label"
),
""",
                        code_id="code_option_disable",
                    ),
                ),
            ],
            value="Full Disable",
            size="small",
        ),

        # Multi Select
        SectionHeader("Multi Select", id="multi_select"),
        ExampleSection(
            preview=[
              Select(
                    select_options=['New York City', 'Montreal', 'San Francisco'],
                    label="Label",
                    multi=True,
                )
            ],
            code="""
from components.select.select import Select

Select(
    select_options=['New York City', 'Montreal', 'San Francisco'],
    label="Label",
    multi=True,
)
""",
            section_id="multi_select",
        ),

        # Error
        SectionHeader("Error", id="error", ),
        ExampleSection(
            preview=[
              Select(
                    select_options=['New York City', 'Montreal', 'San Francisco'],
                    label="Label",
                    has_error=True,
                    error_message="Error message"
                )
            ],
            code="""
from components.select.select import Select

Select(
    select_options=['New York City', 'Montreal', 'San Francisco'],
    label="Label",
    has_error=True,
    error_message="Error message"
)
""",
            section_id="error",
        ),

        # Color Mode
        SectionHeader("Color Mode", id="color_mode"),
        ExampleSection(
            preview=[
              html.Div(
                className="select_color_mode_wrapper",
                children=[
                    Select(
                        select_options=['New York City', 'Montreal', 'San Francisco'],
                        label="Label",
                        placeholder="Select placeholder",
                        additional_message="Extra message with info",
                        select_color_mode="custom_light",
                        select_background_color="var(--accent-sidebar)"
                    )
                ])
            ],
            code="""
from components.select.select import Select

Select(
    select_options=['New York City', 'Montreal', 'San Francisco'],
    label="Label",
    placeholder="Select placeholder",
    additional_message="Extra message with info",
    select_color_mode="custom_light",
    select_background_color="var(--accent-sidebar)"
)
""",
            section_id="color_mode",
        ),

        # Properties
        SectionHeader("Select Properties", id="properties"),
        PropertiesSection(PROPERTIES),
    ],
)








