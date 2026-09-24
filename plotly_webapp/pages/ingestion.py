import json
from pathlib import Path

import dash
from dash import Input, Output, callback, dcc, html

from components.button.button import Button
from components.page_header.page_header import PageHeader
from components.section.section import Section
from components.table.V1.table import Table as TableV1

DATA_PATH = Path(__file__).parents[1] / "data" / "harbor_transactions.json"

dash.register_page(__name__, path="/ingestion", title="Ingestão de Extratos")

TRANSACTION_COLUMNS = [
    {"field": "trans_date", "headerName": "Data da Transação", "minWidth": 160, "editable": True},
    {"field": "description", "headerName": "Descritivo da Transação", "minWidth": 280, "flex": 1, "editable": True},
    {"field": "credit_debit", "headerName": "Crédito/Débito", "minWidth": 170, "editable": True},
    {
        "field": "treasury",
        "headerName": "Pendente de Validação?",
        "minWidth": 220,
        "editable": True,
        "cellRenderer": "agCheckboxCellRenderer",
        "cellEditor": "agCheckboxCellEditor",
    },
]


def load_transactions():
    with DATA_PATH.open(encoding="utf-8") as data_file:
        transactions = json.load(data_file)
    for transaction in transactions:
        transaction.setdefault("treasury", False)
    return transactions


def build_layout():
    transactions = load_transactions()
    account_ids = sorted({row["account_id"] for row in transactions})

    return html.Div(
        className="ingestion__container",
        children=[
            html.Section(
                className="ingestion__top_section",
                children=[PageHeader(icon="lucide:file-up", title="Ingestão de Extratos")],
            ),
            html.Div(
                className="ingestion__filters",
                children=[
                    html.Div(
                        className="ingestion__account-filter",
                        children=[
                            html.Label("ID da Conta", htmlFor="ingestion-account-id"),
                            dcc.Dropdown(
                                id="ingestion-account-id",
                                options=[{"label": account_id, "value": account_id} for account_id in account_ids],
                                value=account_ids[0],
                                clearable=False,
                            ),
                        ],
                    ),
                    html.P("Última ingestão: 23/09/2026", className="body-xs ingestion__updated_section"),
                ],
            ),
            Section(
                title="Ingestão",
                open=True,
                id="ingestion-upload-section",
                content=dcc.Upload(
                    id="ingestion-upload",
                    children=html.Div(
                        ["Arraste o extrato bancário da conta para aqui ou ", html.A("selecione um ficheiro")]
                    ),
                    className="ingestion__upload",
                    multiple=False,
                ),
            ),
            html.Div(
                className="ingestion__table-section",
                children=Section(
                    title="Validação de dados a ingerir",
                    open=True,
                    id="ingestion-transactions-section",
                    content=html.Div(
                        [
                            TableV1(
                                data_frames=[{"df": transactions, "col_def": TRANSACTION_COLUMNS}],
                                grid_id="ingestion-transactions-table",
                                dashGridOptions={
                                    "defaultColDef": {"filter": True, "sortable": True, "resizable": True}
                                },
                                height={"mode": "px", "value": 360},
                            ),
                        ],
                    ),
                ),
            ),
            html.Div(
                Button("Submeter", variant="primary", id="ingestion-submit", icon="lucide:check"),
                className="ingestion__submit-wrapper",
            ),
        ],
    )


@callback(
    Output("ingestion-transactions-table", "rowData"),
    Input("ingestion-account-id", "value"),
)
def filter_transactions(account_id):
    return [row for row in load_transactions() if row["account_id"] == account_id]


layout = build_layout()
