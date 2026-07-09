import dash
from dash import html

from components.button.button import Button
from components.tag.tag import Tag
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
    path="/components/section",
    title="Section",
)


TOC_LINKS = [
    ("Default Section", "default_section"),
    ("Description", "description"),
    ("Extra Header Element", "extra_header_element"),
    ("Properties", "properties"),
]


PROPERTIES = [
    {"name": "title", "type": "(str ; required)",
     "description": "Section title displayed in the header."},

    {"name": "description", "type": "(str ; optional)",
     "description": "Text shown below the title inside the header."},

    {"name": "extra_element", "type": "(Any | Sequence[Any] ; optional)",
     "description": "One or more elements rendered on the right side of the header (buttons, tags, etc.)."},

    {"name": "content", "type": "(Any ; optional)",
     "description": "Main content displayed inside the collapsible area."},

    {"name": "open", "type": "(bool ; default False)",
     "description": "Initial open/closed state of the sectio. The default initial state is closed."},

    {"name": "id", "type": "(str | Dict[str, Any] ; default: 'section-id')",
     "description": "Section identifier or pattern-matching dict."},
]


layout = DocumentationPage(
    title="Section",
    toc_links=TOC_LINKS,
    content_sections=[
        PageHeader(title="Section", icon="lucide:group", subtitle="Displays a collapsible content container"),

        # Default Section
        SectionHeader("Default Section", id="default_section"),
        ExampleSection(
            preview=[
                Section(
                    title="Section Header",
                    content=html.P("Simple section content", className="body-sm")
                ),
            ],
            code="""
from components.section.section import Section

Section(
    title="Section Header",
    content=html.P("Simple section content", className="body-sm")
)
""",
            section_id="default_section",
        ),

        # Description
        SectionHeader("Description", id="description"),
        ExampleSection(
            preview=[
                Section(
                    title="Section Header",
                    description="Section additional description",
                    content=html.P("Simple section content", className="body-sm"),
                    id="section-description",
                ),
            ],
            code="""
from components.section.section import Section

Section(
    title="Section Header",
    description="Section additional description",
    content=html.P("Simple section content", className="body-sm"),
    id="section-description",
)
""",
            section_id="description",
        ),

        # Extra Header Element
        SectionHeader("Extra Header Element", id="extra_header_element", subtitle="The header can include one or more additional actions or elements"),
        Tabs(
            children=[
                Tab(
                    label="Single",
                    value="Single",
                    children=ExampleSection(
                        preview=[
                            Section(
                                title="Section Header",
                                description="Section additional description",
                                extra_element=Button("Main Action", size="xs", icon="lucide:square-asterisk"),
                                content=html.P("Simple section content", className="body-sm")
                            ),
                        ],
                        code="""
from components.section.section import Section
from components.button.button import Button

Section(
    title="Section Header",
    description="Section additional description",
    extra_element=Button("Main Action", size="xs", icon="lucide:square-asterisk"),
    content=html.P("Simple section content", className="body-sm"),
)
""",
                        code_id="code_single",
                    ),
                ),
                Tab(
                    label="Multiple",
                    value="Multiple",
                    children=ExampleSection(
                        preview=[
                            Section(
                                title="Section Header",
                                description="Section additional description",
                                extra_element=[
                                    Button("Secondary Action", size="xs", variant="outline", icon="lucide:square-asterisk"),
                                    Tag("example", size="xs", variant="positive")
                                ],
                                content=html.Div(
                                    className="example-section-content-wrapper",
                                    children=[
                                        html.H2("Content Title", className="heading-2"),
                                        html.P("Complex content text", className="body-sm")
                                    ]
                                )
                            ),
                        ],
                        code="""
from components.section.section import Section
from components.button.button import Button
from components.tag.tag import Tag

Section(
    title="Section Header",
    description="Section additional description",
    extra_element=[
        Button("Secondary Action", size="xs", variant="outline", icon="lucide:square-asterisk"),
        Tag("example", size="xs", variant="positive")
    ],
    content=html.Div(
        className="example-section-content-wrapper",
        children=[
            html.H3("Content Title", className="heading-3"),
            html.P("Complex content text", className="body-sm")
        ]
    )
)
""",
                        code_id="code_multiple",
                    ),
                ),
            ],
            value="Single",
            size="small",
        ),

        # Properties
        SectionHeader("Properties", id="properties"),
        PropertiesSection(PROPERTIES),
    ],
)


