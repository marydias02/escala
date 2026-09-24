import json
from pathlib import Path

import dash
from dash import Input, Output, callback, dcc, html

from components.button.button import Button
from components.cards.indicator_card.indicator_card import IndicatorCard
from components.page_header.page_header import PageHeader
from components.section.section import Section
from components.table.V1.table import Table as TableV1

DATA_PATH = Path(__file__).parents[1] / "data" / "harbor_transactions.json"

dash.register_page(__name__, path="/", title="Dashboard")


def load_transactions():
    with DATA_PATH.open(encoding="utf-8") as data_file:
        return json.load(data_file)


TRANSACTION_COLUMNS = [
    {"field": "trans_id", "headerName": "ID Trans.", "width": 110},
    {"field": "trans_date", "headerName": "Data Trans.", "width": 140},
    {"field": "description", "headerName": "Descritivo da Transação", "width": 240},
    {"field": "credit_debit", "headerName": "Crédito / Débito", "width": 155},
    {"field": "proc_date", "headerName": "Data Proc.", "width": 130},
    {"field": "val_date", "headerName": "Data Val.", "width": 120},
    {"field": "scope", "headerName": "Âmbito", "width": 150, "editable": True, "cellEditor": "agSelectCellEditor", "cellEditorParams": {"values": ["Tesouraria", "Contas a Receber"]}},
    {"field": "decision", "headerName": "Decisão", "width": 150},
    {"field": "status", "headerName": "Estado", "width": 150},
]


def build_layout():
    transactions = load_transactions()
    return html.Div(
        className="dashboard__container",
        children=[
            html.Section(
                className="dashboard__top_section",
                children=[PageHeader(icon="lucide:layout-dashboard", title="Dashboard")],
            ),
            html.Div(
                className="dashboard__filters",
                children=[
                    html.Div(
                        className="dashboard__account-filter",
                        children=[
                            html.Label("ID da Conta", htmlFor="harbor-account-id"),
                            dcc.Dropdown(
                                id="harbor-account-id",
                                options=[
                                    {"label": "ACC-1001", "value": "ACC-1001"},
                                    {"label": "ACC-2002", "value": "ACC-2002"},
                                ],
                                value="ACC-1001",
                                clearable=False,
                            ),
                        ],
                    ),
                    html.P("Última ingestão: 23/09/2026", className="body-xs dashboard__updated_section"),
                ],
            ),
            html.Section(
                className="dashboard__content_section",
                children=[
                    Section(
                        title="Indicadores",
                        open=True,
                        id="harbor-indicators-section",
                        content=html.Div(
                            className="dashboard__indicator_section-wrapper",
                            children=[
                                IndicatorCard(
                                    label_text="Montante por Validar",
                                    rows=[("23.938,76€", "última semana", 12, "decrease")],
                                    badge_unit="%",
                                ),
                                IndicatorCard(
                                    label_text="Número de Movimentos Por Fechar",
                                    rows=[
                                        (
                                            42,
                                            "última semana",
                                            36,
                                            "increase",
                                        )
                                    ],
                                ),
                                IndicatorCard(
                                    label_text="Número de Processos a aguardar NP",
                                    rows=[
                                        (
                                            3,
                                            "última semana",
                                            50,
                                            "decrease",
                                        )
                                    ],
                                ),
                            ],
                        ),
                    ),
                    html.Details(
                        [
                            html.Summary(
                                [
                                    Button(
                                        icon="f7:arrowtriangle-down-fill",
                                        variant="ghost secondary",
                                        className="section__arrow",
                                        id="harbor-transactions-toggle",
                                    ),
                                    html.Header(
                                        html.H2("Transações", className="heading-2"),
                                        className="section__title",
                                    ),
                                    html.Aside(className="section__extra-elements"),
                                ],
                                className="section__header",
                            ),
                            html.Div(
                                TableV1(
                                    data_frames=[{"df": transactions, "col_def": TRANSACTION_COLUMNS}],
                                    grid_id="harbor-transactions-table",
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
                                        "singleClickEdit": True,
                                    },
                                    height={"mode": "px", "value": 360},
                                ),
                                className="section__content",
                            ),
                        ],
                        open=True,
                        id="harbor-transactions-section",
                        className="section",
                    ),
                ],
            ),
        ],
    )


@callback(
    Output("harbor-transactions-table", "rowData"),
    Input("harbor-account-id", "value"),
)
def filter_transactions(account_id):
    return [row for row in load_transactions() if row["account_id"] == account_id]


layout = build_layout()
