import dash
from dash import html
from dash_iconify import DashIconify
from dash.dcc import Tab
from dash import dcc
from dash import callback, Input, Output, State, callback_context, no_update
from dash.exceptions import PreventUpdate

from components.page_header.page_header import PageHeader
from components.tabs.tabs import Tabs
from components.button.button import Button
from components.section.section import Section
from components.cards.indicator_card.indicator_card import IndicatorCard
from components.right_drawer.right_drawer import RightDrawer
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

from assets.api_calls.extraction_api import get_extraction_dashboard


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
    },
    {
        "field": "status",
        "headerName": "Estado",
        "width": 130,
        "cellRenderer": "Status",
    },
]

short_documents_col_def = [
    {
        "field": "reception_date",
        "headerName": "Data da Última Comunicação",
        "width": 240,
    },
    {
        "field": "sender_email",
        "headerName": "Email do Remetente",
        "minWidth": 220,
    },
    {
        "field": "email_subject",
        "headerName": "Assunto do Email",
        "minWidth": 240,
    },
    {
        "field": "email_status",
        "headerName": "Estado",
        "width": 160,
        "cellRenderer": "EmailStatus",
    },
    {
        "field": "first_email_date",
        "headerName": "Data da Primeira Comunicação",
        "width": 250,
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
    # The page shell renders first; the API client loads these independent resources concurrently.
    dashboard = get_extraction_dashboard()
    kpis = dashboard["kpis"]
    priority_documents = dashboard["priority_documents"]
    all_documents = dashboard["all_documents"]
    pending_documents = dashboard["pending_documents"]

    content_children = [
        Section(
            title="Indicadores",
            content=[
                html.Div(
                    className="homepage__indicator_section-wrapper",
                    children=[
                        IndicatorCard(
                            label_text="Faturas para Validação",
                            label_tooltip="Faturas pendentes de validação manual; variação percentual face à semana anterior no número de documentos que necessitaram de validação manual",
                            rows=[(kpis["pending_manual_validation"]["value"],
                                   "última semana",
                                   abs(kpis["pending_manual_validation"]["delta_pp"]),
                                   trend(kpis["pending_manual_validation"]["delta_pp"])
                                )
                            ],
                            badge_unit="%",
                        ),
                        IndicatorCard(
                            label_text="Faturas Ingeridas Automaticamente",
                            label_tooltip="Percentagem de documentos que não necessitaram de validação manual e foram ingeridas em SAP; diferença em pontos percentuais face à semana anterior",
                            rows=[(fmt_pct(kpis["auto_ingested"]["pct"]),
                                "última semana",
                                abs(kpis["auto_ingested"]["delta_pp"]),
                                trend(kpis["auto_ingested"]["delta_pp"]))],
                            badge_unit="pp",
                        ),
                        IndicatorCard(
                            label_text="Faturas Devolvidas ao Fornecedor",
                            label_tooltip="Percentagem de documentos que devolvidas ao fornecedor; diferença em pontos percentuais face à semana anterior",
                            rows=[(fmt_pct(kpis["returned_to_supplier"]["pct"]),
                                "última semana",
                                abs(kpis["returned_to_supplier"]["delta_pp"]),
                                trend(kpis["returned_to_supplier"]["delta_pp"]))],
                            badge_unit="pp",
        ),
    ]
                ),
            ],
            open=True,
        ),
        make_medium_tabs(priority_documents, all_documents, pending_documents),
        RightDrawer(
            drawer_id="extraction-email-drawer",
            title="Detalhes do Email",
            children=[
                Section(
                    title="Conteúdo do Email",
                    content=html.Div(id="extraction-email-drawer-content"),
                    open=True,
                ),
            ],
        ),
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


def _build_pending_email_drawer_content(row):
    sender = row.get("sender_email") or "N/D"
    if "@" in sender:
        name, domain = sender.split("@", 1)
        sender_display = html.Span(
            [f"{name}@", html.Br(), domain],
            className="right-sidebar__meta-value",
        )
    else:
        sender_display = html.Span(sender, className="right-sidebar__meta-value")

    return html.Div(
        className="right-sidebar__content",
        children=[
            html.Div(
                className="right-sidebar__meta-box",
                children=[
                    html.Div(
                        className="right-sidebar__meta-item",
                        children=[
                            html.Span("Remetente", className="right-sidebar__meta-label"),
                            sender_display,
                        ],
                    ),
                    html.Div(className="right-sidebar__meta-divider"),
                    html.Div(
                        className="right-sidebar__meta-item",
                        children=[
                            html.Span("Data de Receção", className="right-sidebar__meta-label"),
                            html.Span(str(row.get("reception_date") or "N/D"), className="right-sidebar__meta-value"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="right-sidebar__email-box",
                children=[
                    html.Div(row.get("email_subject") or "N/D", className="right-sidebar__email-subject"),
                    html.Div(
                        html.Div(
                            row.get("email_content") or "N/D",
                            className="right-sidebar__email-body",
                        ),
                        className="right-sidebar__email-body-box",
                    ),
                ],
            ),
        ],
    )


@callback(
    Output("extraction-email-drawer", "className"),
    Output("extraction-email-drawer-content", "children"),
    Input("pending-processes-table", "selectedRows"),
    Input("extraction-email-drawer-close", "n_clicks"),
    State("extraction-email-drawer", "className"),
    prevent_initial_call=True,
)
def toggle_extraction_email_drawer(selected_rows, close_clicks, current_class_name):
    triggered = callback_context.triggered
    if not triggered:
        raise PreventUpdate

    trigger_id = triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "extraction-email-drawer-close":
        return "right-sidebar sidebar--collapsed", no_update

    if not selected_rows:
        raise PreventUpdate

    row = selected_rows[0]
    content = _build_pending_email_drawer_content(row)
    return "right-sidebar", content
