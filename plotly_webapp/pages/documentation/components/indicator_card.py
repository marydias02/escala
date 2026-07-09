

import dash
from dash import html

# from components.cards.indicator_card.indicator_card import IndicatorCard
from components.cards.indicator_card.indicator_card import IndicatorCard
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
    path="/components/indicator-card",
    title="Indicator Card",
)

TOC_LINKS = [
    ("Default Card", "default_card"),
    ("Caption", "caption"),
    ("Label", "label"),
    ("Delta Badge", "delta_badge"),
    ("Multiple Rows", "multiple_rows"),
    ("Example Card Banner", "example_card_banner"),
    ("Properties", "properties"),
]


PROPERTIES = [
    {"name": "label_text", "type": "(str ; optional)",
     "description": "Optional label shown at the top of the card."},

    {"name": "label_tooltip", "type": "(str ; optional)",
     "description": "Optional tooltip text. "
                    "This is shown on hover on an info icon next to the label"},

    {"name": "rows", "type": "(List of tuples[str | float, str | none, str | none, 'increase' | 'decrease' | none] ; required)",
     "description": "List to define the card rows. Each one includes a value with an optional caption and delta badge"
                      " - The fisrt element (str | float) represents the main value;"
                      " - The second element (str ; optional) represents the description text;"
                      " - The third element (str ; optional) represents the delta badge text;"
                      " - The forth element ('increase' | 'decrease' ; optional) represents the the delta badge delta direction;"},
]


layout = DocumentationPage(
    title="Indicator Card",
    toc_links=TOC_LINKS,
    content_sections=[
        PageHeader(title="Indicator Card", icon="lucide:group", subtitle="Displays a dynamic kpi card component"),

        # Default Card
        SectionHeader("Default Card", id="default_card"),
        ExampleSection(
            preview=[
              html.Div(
                className="indicator_card_wrapper",
                children = [
                    IndicatorCard(
                        rows=[("13%", None, None, None)]
                    )
                ]
              )
            ],
            code="""
from components.cards.indicator_card.indicator_card import IndicatorCard

IndicatorCard(
    rows=[("13%", None, None, None)]
)
""",
            section_id="default_card",
        ),

        # Caption
        SectionHeader("Caption", id="caption"),
        ExampleSection(
            preview=[
              html.Div(
                className="indicator_card_wrapper",
                children = [
                    IndicatorCard(
                        rows=[("13%", "Message with kpi description", None, None)]
                    )
                ]
              )
            ],
            code="""
from components.cards.indicator_card.indicator_card import IndicatorCard

IndicatorCard(
    rows=[("13%", "Message with kpi description", None, None)]
)
""",
            section_id="caption",
        ),

        # Label
        SectionHeader("Label", id="label", subtitle="When assigning a label it can include an additional tooltip"),
        Tabs(
            children=[
                Tab(
                    label="Label",
                    value="Label",
                    children=ExampleSection(
                        preview=[
                            html.Div(
                                className="indicator_card_wrapper",
                                children = [
                                    IndicatorCard(
                                        rows=[("13%", "Message with kpi description", None, None)],
                                        label_text="Label"
                                    )
                                ]
                            )
                        ],
                        code="""
from components.cards.indicator_card.indicator_card import IndicatorCard

IndicatorCard(
    rows=[("13%", "Message with kpi description", None, None)],
    label_text="Label"
)
""",
                        code_id="code_label",
                    ),
                ),
                Tab(
                    label="With Tooltip",
                    value="With Tooltip",
                    children=ExampleSection(
                        preview=[
                            html.Div(
                                className="indicator_card_wrapper",
                                children = [
                                    IndicatorCard(
                                        rows=[("13%", "Message with kpi description", None, None)],
                                        label_text="Label",
                                        label_tooltip="Additional info"
                                    )
                                ]
                            )
                        ],
                        code="""
from components.cards.indicator_card.indicator_card import IndicatorCard

IndicatorCard(
    rows=[("13%", "Message with kpi description", None, None)],
    label_text="Label",
    label_tooltip="Additional info"
)
""",
                        code_id="code_label_tt",
                    ),
                ),
            ],
            value="Label",
            size="small",
        ),

        # Delta Badge
        SectionHeader("Delta Badge", id="delta_badge"),
        ExampleSection(
            preview=[
              html.Div(
                className="indicator_card_wrapper",
                children = [
                    IndicatorCard(
                        rows=[("13%", "Message with kpi description", "50%", "increase")],
                        label_text="Label",
                        label_tooltip="Additional info"
                    )
                ]
              )
            ],
            code="""
from components.cards.indicator_card.indicator_card import IndicatorCard

IndicatorCard(
    rows=[("13%", "Message with kpi description", "50%", "increase")],
    label_text="Label",
    label_tooltip="Additional info"
)
""",
            section_id="delta_badge",
        ),

        # Multiple Rows
        SectionHeader("Multiple Rows", id="multiple_rows", ),
        ExampleSection(
            preview=[
              html.Div(
                className="indicator_card_wrapper",
                children = [
                    IndicatorCard(
                            rows=[
                                ("13%", "Message with kpi description", "50%", "increase"),
                                ("30%", "Message with kpi description", "20%", "decrease")],
                            label_text="Label",
                            label_tooltip="Additional info"
                    )
                ]
              )
            ],
            code="""
from components.cards.indicator_card.indicator_card import IndicatorCard

IndicatorCard(
    rows=[
        ("13%", "Message with kpi description", "50%", "increase"),
        ("30%", "Message with kpi description", "20%", "decrease")],
    label_text="Label",
    label_tooltip="Additional info"
)
""",
            section_id="multiple_rows",
        ),

        # Example Card Banner
        SectionHeader("Example Card Banner", id="example_card_banner", subtitle="Example of a banner with multiple cards including css code"),
        Tabs(
            children=[
                Tab(
                    label="Python Code",
                    value="Python Code",
                    children=ExampleSection(
                        preview=[
                            html.Div(
                                className="indicator_card_banner_wrapper",
                                children=[
                                    IndicatorCard(
                                        label_text="Item Label",
                                        label_tooltip="extra info",
                                        rows=[("36%", "Expected SLA", "12%", "decrease")]
                                    ),
                                    IndicatorCard(
                                        label_text="Item Label",
                                        label_tooltip="extra info",
                                        rows=[("13%", "Expected Setup/Production Ratio", "2%", "increase")]
                                    ),
                                    IndicatorCard(
                                        label_text="Item Label",
                                        label_tooltip="extra info",
                                        rows=[("22%", "Expected PM Utilization", "20%", "decrease")]
                                    ),
                                    IndicatorCard(
                                        label_text="Item Label",
                                        label_tooltip="extra info",
                                        rows=[("52%", "Expected SLA Accomplishment", "20%", "increase")]
                                    ),
                                ]
                            ),
                        ],
                        code="""
from components.cards.indicator_card.indicator_card import IndicatorCard

html.Div(
    className="indicator_card_banner_wrapper",
    children=[
        IndicatorCard(
            label_text="Item Label",
            label_tooltip="extra info",
            rows=[("36%", "Expected SLA", "12%", "decrease")]
        ),
        IndicatorCard(
            label_text="Item Label",
            label_tooltip="extra info",
            rows=[("13%", "Expected Setup/Production Ratio", "2%", "increase")]
        ),
        IndicatorCard(
            label_text="Item Label",
            label_tooltip="extra info",
            rows=[("22%", "Expected PM Utilization", "20%", "decrease")]
        ),
        IndicatorCard(
            label_text="Item Label",
            label_tooltip="extra info",
            rows=[("52%", "Expected SLA Accomplishment", "20%", "increase")]
        ),
    ]
),
""",
                        code_id="code_card_banner_python",
                    ),
                ),
                Tab(
                    label="CSS Code",
                    value="CSS Code",
                    children=ExampleSection(
                        preview=[
                            html.Div(
                                className="indicator_card_banner_wrapper",
                                children=[
                                    IndicatorCard(
                                        label_text="Item Label",
                                        label_tooltip="extra info",
                                        rows=[("36%", "Expected SLA", "12%", "decrease")]
                                    ),
                                    IndicatorCard(
                                        label_text="Item Label",
                                        label_tooltip="extra info",
                                        rows=[("13%", "Expected Setup/Production Ratio", "2%", "increase")]
                                    ),
                                    IndicatorCard(
                                        label_text="Item Label",
                                        label_tooltip="extra info",
                                        rows=[("22%", "Expected PM Utilization", "20%", "decrease")]
                                    ),
                                    IndicatorCard(
                                        label_text="Item Label",
                                        label_tooltip="extra info",
                                        rows=[("52%", "Expected SLA Accomplishment", "20%", "increase")]
                                    ),
                                ]
                            ),
                        ],
                        code="""
.indicator_card_banner_wrapper {
  width: 100%;
  display: flex;
  gap: var(--spacing-16);
  padding: var(--spacing-12);
  border-radius: var(--border-radius-md);
  border: var(--border-normal) solid var(--border-lightest);
  background-color: var(--surface-lightest);
}

.indicator_card_banner_wrapper .indicator-card {
  width: 25%;
  padding-left: var(--spacing-16);
  border-left: var(--border-normal) solid var(--border-light);
}

.indicator_card_banner_wrapper .indicator-card:first-child {
  width: 25%;
  padding-left: var(--spacing-none);
  border-left: none;
}
""",
                        code_id="code_card_banner_css",
                    ),
                ),
            ],
            value="Python Code",
            size="small",
        ),

        # Properties
        SectionHeader("Properties", id="properties"),
        PropertiesSection(PROPERTIES),
    ],
)

