import dash
from dash import html
from dash_iconify import DashIconify
from dash.dcc import Tab

from components.page_header.page_header import PageHeader
from components.tabs.tabs import Tabs
from components.button.button import Button
from components.section.section import Section
from components.cards.indicator_card.indicator_card import IndicatorCard
from utils.base.grid_system.grid import Col, Container, Row

from components.table.V1.table import Table as TableV1
from callbacks.table.V1.secondary_actions_callback import (
    create_quickfilter_secondary, create_sort_secondary, create_reset_secondary )
from callbacks.table.V1.primary_action_callback import (
    create_export_csv_callback_v1 )
from utils.table.data_loader import get_brand_and_year_columns, load_group_table_data
from components.table.shared.col_def_config import (
    create_simple_table_column_defs , create_demo_tab_table )
from components.table.shared.action_bar import action_bar


from functools import partial


dash.register_page(
    __name__,
    path="/",
    title="Home",
)


MediumTabs = Tabs(
    value="overview",
    size="medium",
    children=[
        Tab(
            label="Overview",
            value="overview",
            className="lucide--layout-dashboard",
        ),
        Tab(
            label="Statistics",
            value="statistics",
            className="lucide--chart-no-axes-combined",
        ),
        Tab(
            label="Insights",
            value="insights",
            className="lucide--lightbulb",
        ),
        Tab(
            label="Reports",
            value="reports",
            className="lucide--file-text",
        ),
    ],
)


######  TABLE 1  ######
yearly_df, yearly_col_defs, monthly_df, monthly_col_defs = create_demo_tab_table()


######  TABLE 2  ######
df = load_group_table_data()
brand_cols, year_cols = get_brand_and_year_columns(list(df.columns))
simple_table_column_defs = create_simple_table_column_defs(brand_cols, year_cols)




layout = html.Div(
    [  
        html.Div( 
            className="homepage__container",
            children=[
                html.Section(
                    className="homepage__top_section",
                    children=[
                        PageHeader(
                            icon = "lucide:file-text",
                            title = "Template Page", 
                            subtitle = "This is a small page description, which may exist or not exist. Lorem ipsum sit dolor amet",   
                        ),
                        html.Div(
                            className="actions-wrapper",
                            children=[
                                html.Div(
                                    className="tabs-wrapper",
                                    children=[
                                        MediumTabs
                                    ]
                                ),
                                html.Div(
                                    className="button-wrapper",
                                    children=[
                                        Button("Action", variant="outline", icon="lucide:asterisk", id="action-button"),
                                        Button("Action", variant="outline", icon="lucide:asterisk", id="action-button"),
                                        Button("Action", variant="outline", icon="lucide:asterisk", id="action-button"),
                                        Button("Filters", variant="outline", icon="lucide:funnel", id="filter-button"),
                                        Button("Create Run", icon="lucide:play", variant="primary", id="create-run-button"),
                                    ]
                                )
                            ]
                        ),
                    ],                  
                ),

                html.Section(
                    className="homepage__content_section",
                    children=[
                        Section(
                            title="Indicators",
                            description="This is a section that containes indicator cards.",
                            content=[
                                html.Div(
                                    className="homepage__indicator_section-wrapper",
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
                        ),
                        Section(
                            title="Table Section",
                            description="This is a section that containes data that can be filtered.",
                            content=[
                                TableV1(
                                    data_frames=[
                                        {"df": monthly_df, "col_def": monthly_col_defs, "tab": "monthly"},
                                        {"df": yearly_df,  "col_def": yearly_col_defs,  "tab": "yearly"},
                                    ],
                                    grid_id="example-table",
                                    title="Table Title",
                                    dashGridOptions={
                                        "rowSelection": {
                                            "mode": "singleRow",
                                            "headerCheckbox": False,
                                            "checkboxes": False,
                                            "enableClickSelection": False,
                                        },
                                        "defaultColDef": {
                                            "filter": True, 
                                            "sortable": True, 
                                            "resizable": True,
                                            "flex":1,
                                        },
                                        "dataTypeDefinitions": {
                                            "number": {
                                                "baseDataType": "number",
                                                "extendsDataType": "number",
                                                "columnTypes": "leftAligned",
                                            }
                                        },
                                    },
                                    height={"mode": "auto"},
                                    tabs=Tabs(
                                        value="monthly",
                                        children=[
                                            Tab(
                                                label="Yearly",
                                                value="yearly",
                                                className="lucide--table-2",
                                            ),
                                            Tab(
                                                label="Monthly",
                                                value="monthly",
                                                className="lucide--table-2",
                                            ),
                                        ],
                                    ),
                                    banner={"text": "Some Message", "variant": "warning", "icon": "lucide:triangle-alert"},
                                    primary_action=("Export CSV", create_export_csv_callback_v1),
                                    note="Updated 5 days ago",
                                    secondary_actions=[("Filter 2024", "lucide:filter", partial(create_quickfilter_secondary, value="High")),
                                                       ("Priority Asc", "lucide:arrow-down-up", partial(create_sort_secondary, col_id="Priority", direction="asc")),
                                                       ("Reset", "lucide:brush-cleaning", create_reset_secondary),
                                                       ("Analyze",     "lucide:grid-2x2", None),     # dummy
                                                       ("Share",       "lucide:eye",    None),     # dummy
                                                       ],
                                    enable_reset=True,
                                ),
                                html.Div(
                                    className="table-section__graphic-wrapper",
                                    children=[
                                        Container([
                                            Row([
                                                Col([
                                                    html.Div(
                                                        className="table-section__graphic", ### CHECK CLASS IN CSS FILE - index.css
                                                        children=[
                                                            html.P("Graphic here", className="body-sm")
                                                    ])
                                                ], xs=12,lg=6),

                                                Col([
                                                    html.Div(
                                                        className="table-section__graphic", ### CHECK CLASS IN CSS FILE - index.css
                                                        children=[
                                                            html.P("Graphic here", className="body-sm")
                                                    ])
                                                ], xs=12,lg=6),
                                            ]),
                                        ], fluid=True)
                                    ], 
                                )
                            ],
                        ),
                        Section(
                            title="Colapsed Section",
                            description="This is a colapsed placeholder section.",
                            content=[]
                        ),
                        Section(
                            title="Validation Section",
                            description="This is a section description.",
                            extra_element=[
                                Button("Action", variant="outline", icon="lucide:asterisk", id="action-a-button"),
                                Button("Action", variant="outline", icon="lucide:asterisk", id="action-b-button"),
                                Button("Action", variant="outline", icon="lucide:asterisk", id="action-c-button"),
                                Button("Create Run", icon="lucide:play", variant="primary", id="create-run-button"),],
                            content=[
                                TableV1(
                                    data_frames=[
                                        {"df": df, "col_def": simple_table_column_defs},
                                    ],
                                    grid_id="table-section-main-mp",
                                    action_bar=action_bar,
                                    dashGridOptions={
                                        "rowSelection": {
                                            "mode": "singleRow",
                                            "headerCheckbox": False,
                                            "checkboxes": True,
                                            "enableClickSelection": True,
                                        },
                                        "selectionColumnDef": {
                                            "pinned": "left",
                                            "resizable": False,
                                            "lockPosition": True,
                                            "lockPinned": True,
                                        },
                                    },
                                ),
                            ],
                            id="default-section",
                        ),
                    ]
                )
            ],            
        ),
    ]
)


