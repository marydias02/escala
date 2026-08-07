import dash
from dash import html
from dash_iconify import DashIconify
from dash.dcc import Tab
from dash import dcc
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

from assets.api_calls.extraction_api import get_big_numbers, get_priority_documents, get_all_documents, get_pending_documents


dash.register_page(
    __name__,
    path="/",
    title="Extracao",
)

def trend(delta):
    if delta > 0:
        return "increase"
    if delta < 0:
        return "decrease"
    return "neutral"

def fmt_pct(value):
    return f"{value:g}%"

def fmt_delta(value):
    return f"{abs(value):g}%"


# df = load_group_table_data()
# brand_cols, year_cols = get_brand_and_year_columns(list(df.columns))
# simple_table_column_defs = create_simple_table_column_defs(brand_cols, year_cols)


documents_col_def = [
    {
        "field": "document_number",
        "headerName": "Documento",
        "width": 160,
    },
    {
        "field": "bu_name",
        "headerName": "Unidade de Negócio",
        "minWidth": 220,
    },
    {
        "field": "supplier_name",
        "headerName": "Fornecedor",
        "minWidth": 220,
    },
    {
        "field": "total_amount",
        "headerName": "Valor",
        "width": 120,
    },
    {
        "field": "issue_date",
        "headerName": "Data de Emissão",
        "width": 150,
    },
    {
        "field": "created_at",
        "headerName": "Data de Processamento",
        "width": 200,
    },
    {
        "field": "action",
        "headerName": "Ação",
        "width": 180,
        "cellRenderer": "Action",
    },
    {
        "field": "status",
        "headerName": "Estado",
        "width": 120,
        "cellRenderer": "Status",
    },
]

short_documents_col_def = [
    {
        "field": "created_at",
        "headerName": "Data de Processamento",
        "width": 260,
    },
    {
        "field": "action",
        "headerName": "Ação",
        "width": 335,
        "cellRenderer": "Action",
    },
    {
        "field": "status",
        "headerName": "Estado",
        "width": 220,
        "cellRenderer": "Status",
    },
]


def make_medium_tabs(priority_documents, all_documents, pending_documents):
    return Tabs(
        value="all",
        size="medium",
        children=[
            Tab(
                label="Processamento de Faturas",
                value="all",
                className="lucide--focus",
                children=[
                    Section(
                        title="Processos Prioritários",
                        content=[
                            dcc.Loading(
                                id="priority-processes-loading",
                                type="default",
                                color="var(--primary-color-13)",
                                children=TableV1(
                                    data_frames=[
                                        {
                                            "df": priority_documents,
                                            "col_def": documents_col_def,
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
                                            "flex": 0,
                                        },
                                    },
                                    height={"mode": "px", "value": 250},
                                ),
                            ),
                        ],
                        open=True,
                    ),
                    Section(
                        title="Todos os Processos",
                        content=[
                            dcc.Loading(
                                id="all-processes-loading",
                                type="default",
                                color="var(--primary-color-13)",
                                children=TableV1(
                                    data_frames=[
                                        {
                                            "df": all_documents,
                                            "col_def": documents_col_def,
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
                                            "flex": 0,
                                        },
                                    },
                                    height={"mode": "px", "value": 330},
                                ),
                            ),
                        ],
                        open=True,
                    ),
                ],
            ),
            Tab(
                label="Processos sem Seguimento",
                value="pending",
                className="lucide--file-clock",
                children=[
                    Section(
                        title="Processos Pendentes",
                        content=[
                            dcc.Loading(
                                id="pending-processes-loading",
                                type="default",
                                color="var(--primary-color-13)",
                                children=TableV1(
                                    data_frames=[
                                        {
                                            "df": pending_documents,
                                            "col_def": short_documents_col_def,
                                        }
                                    ],
                                    grid_id="pending-processes-table",
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
                                            "flex": 0,
                                        },
                                    },
                                    height={"mode": "px", "value": 350},
                                ),
                            ),
                        ],
                        open=True,
                    ),
                ],
            ),
        ],
    )


def layout():
    # Render a lightweight page immediately and load heavy data via a background callback.
    return html.Div(
    [  
        html.Div( 
            className="homepage__container",
            children=[
                html.Section(
                    className="homepage__top_section",
                    children=[
                        PageHeader(
                            icon = "lucide:scan-text",
                            title = "Extração",  
                        ),
                        html.P("Atualizado há 5 segundos", className="body-xs homepage__updated_section")
                    ],                  
                ),

                html.Section(
                    className="homepage__content_section",
                    children=[
                        # Content will be populated asynchronously; show a loading spinner meanwhile.
                        dcc.Loading(
                            id="extraction-loading",
                            type="default",
                            color="var(--primary-color-13)",
                            children=html.Div(id="extraction-content"),
                        )
                    ]
                )
            ]           
        )
    ]
)



@callback(
    Output("extraction-content", "children"),
    Input("url", "pathname"),
    prevent_initial_call=False,
)
def load_extraction_content(_pathname):
    # Fetch data when the page is rendered (runs asynchronously relative to initial layout)
    kpis = get_big_numbers()
    priority_documents = get_priority_documents()
    all_documents = get_all_documents()
    pending_documents = get_pending_documents()

    content_children = [
        Section(
            title="Indicadores",
            content=[
                html.Div(
                    className="homepage__indicator_section-wrapper",
                    children=[
                        IndicatorCard(
                            label_text="Faturas para Validação",
                            label_tooltip="faturas pendentes de validação",
                            rows=[(kpis["pending_manual_validation"],"última semana", "50%", "decrease")]
                        ),
                        IndicatorCard(
                            label_text="Faturas Ingeridas Automaticamente",
                            label_tooltip="extra info",
                            rows=[(fmt_pct(kpis["auto_ingested"]["pct"]),
                                "última semana",
                                fmt_delta(kpis["auto_ingested"]["delta_pp"]),
                                trend(kpis["auto_ingested"]["delta_pp"]))]
                        ),
                        IndicatorCard(
                            label_text="Faturas Devolvidas ao Fornecedor",
                            label_tooltip="extra info",
                            rows=[(fmt_pct(kpis["returned_to_supplier"]["pct"]),
                                "última semana",
                                fmt_delta(kpis["returned_to_supplier"]["delta_pp"]),
                                trend(kpis["returned_to_supplier"]["delta_pp"]))]
                        ),
                    ]
                ),
            ],
            open=True,
        ),
        make_medium_tabs(priority_documents, all_documents, pending_documents),
    ]

    return content_children


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

    ref_number = rows[0]["document_id"]
    return f"/detalhe/{ref_number}"