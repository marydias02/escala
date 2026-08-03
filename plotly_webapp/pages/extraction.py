import dash
from dash import html
from dash_iconify import DashIconify
from dash.dcc import Tab
from dash import callback, Input, Output
from dash.exceptions import PreventUpdate

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

import pandas as pd
from functools import partial


dash.register_page(
    __name__,
    path="/",
    title="Extraction",
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
priority_df = pd.read_csv("assets/data/dummy_priority_processes.csv")

# yearly_df, yearly_col_defs, monthly_df, monthly_col_defs = create_demo_tab_table()


######  TABLE 2  ######
all_processes_df = pd.read_csv("assets/data/dummy_all_processes.csv")

# df = load_group_table_data()
# brand_cols, year_cols = get_brand_and_year_columns(list(df.columns))
# simple_table_column_defs = create_simple_table_column_defs(brand_cols, year_cols)




layout = html.Div(
    [  
        html.Div( 
            className="homepage__container",
            children=[
                html.Section(
                    className="homepage__top_section",
                    children=[
                        PageHeader(
                            icon = "lucide:scan-text",
                            title = "Extraction",  
                        ),
                        html.P("Atualizado há 5 segundos", className="body-xs homepage__updated_section")
                    ],                  
                ),
                
                html.Section(
                    className="homepage__content_section",
                    children=[
                        Section(
                            title="Indicadores",
                            # description="This is a section that contains indicator cards.",
                            content=[
                                html.Div(
                                    className="homepage__indicator_section-wrapper",
                                    children=[
                                        IndicatorCard(
                                            label_text="Faturas para Validação",
                                            label_tooltip="faturas pendentes de validação",
                                            rows=[("150", "última semana", "12%", "decrease")]
                                        ),
                                        IndicatorCard(
                                            label_text="Faturas Ingeridas Automaticamente",
                                            label_tooltip="extra info",
                                            rows=[("93%", "última semana", "2%", "increase")]
                                        ),
                                        IndicatorCard(
                                            label_text="Faturas Devolvidas ao Fornecedor",
                                            label_tooltip="extra info",
                                            rows=[("3%", "última semana", "10%", "increase")]
                                        ),
                                        IndicatorCard(
                                            label_text="Emails por Processar",
                                            label_tooltip="extra info",
                                            rows=[("5", "última semana", "15%", "decrease")]
                                        )
                                    ]
                                ),
                            ],
                            open=True
                        ),
                        Section(
                            title="Processos Prioritários",
                            content=[
                                TableV1(
                                    data_frames=[
                                        {
                                            "df": priority_df,
                                        }
                                    ],
                                    grid_id="priority-processes-table",
                                    dashGridOptions={
                                        "rowSelection": {
                                            "mode": "singleRow",
                                            "headerCheckbox": False,
                                            "checkboxes": False,
                                            "enableClickSelection": True,
                                        },
                                        "defaultColDef": {
                                            "filter": True, 
                                            "sortable": True, 
                                            "resizable": True,
                                            "flex":0,
                                        },
                                    },
                                    height={"mode": "px", "value": 250},
                                ),
                            ],
                            open=True
                        ),
                        Section(
                            title="Todos os Processos",
                            content=[
                                TableV1(
                                    data_frames=[
                                        {
                                            "df": all_processes_df,
                                        }
                                    ],
                                    grid_id="all-processes-table",
                                    dashGridOptions={
                                        "rowSelection": {
                                            "mode": "singleRow",
                                            "headerCheckbox": False,
                                            "checkboxes": False,
                                            "enableClickSelection": True,
                                        },
                                        "defaultColDef": {
                                            "filter": True, 
                                            "sortable": True, 
                                            "resizable": True,
                                            "flex":0,
                                        },
                                    },
                                    height={"mode": "px", "value": 330},
                                ),
                            ],
                            open=True
                        )
                    ]
                )
            ]           
        )
    ]
)


@callback(
    Output("url", "pathname"),
    Input("priority-processes-table", "selectedRows"),
    Input("all-processes-table", "selectedRows"),
    prevent_initial_call=True,
)
def go_to_detail(priority_rows, all_rows):
    rows = priority_rows or all_rows

    if not rows:
        raise PreventUpdate

    ref_number = rows[0]["Número de Referência"]
    return f"/detail/{ref_number}"