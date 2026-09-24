import json
from pathlib import Path

import dash
from dash import dcc, html

from components.button.button import Button
from components.cards.indicator_card.indicator_card import IndicatorCard
from components.page_header.page_header import PageHeader
from components.section.section import Section
from components.table.V1.table import Table as TableV1

dash.register_page(__name__, path="/reconciliation", title="Reconciliação de Pagamentos")

DATA_PATH = Path(__file__).parents[1] / "data" / "reconciliation_allocations.json"

ALLOCATION_COLUMNS = [
    {"field": "document_number", "headerName": "Nr. Doc.", "width": 140, "minWidth": 90},
    {"field": "posting_date", "headerName": "Dt. Lançamento", "width": 160, "minWidth": 110},
    {"field": "document", "headerName": "Documento", "width": 135, "minWidth": 90},
    {"field": "net_amount", "headerName": "Mont. líquido", "width": 140, "minWidth": 100},
    {"field": "paid_amount", "headerName": "Mont. pgto.", "width": 135, "minWidth": 105},
]


def load_allocations():
    with DATA_PATH.open(encoding="utf-8") as data_file:
        return json.load(data_file)


def build_layout():
    allocations = load_allocations()

    return html.Div(
        className="reconciliation__container",
        children=[
            html.Section(
                className="reconciliation__top_section",
                children=[PageHeader(icon="lucide:hand-coins", title="Reconciliação de Pagamentos")],
            ),
            html.Div(
                id="reconciliation-indicators-section",
                children=html.Div(
                    className="reconciliation__indicator-wrapper",
                    children=[
                        IndicatorCard(label_text="ID da Transação", rows=[("4", None, None, None)]),
                        IndicatorCard(
                            label_text="Descritivo da Transação", rows=[("SEPA AT26262 - LOGISLINK", None, None, None)]
                        ),
                        IndicatorCard(label_text="Data da Transação", rows=[("24/09/2026", None, None, None)]),
                        IndicatorCard(label_text="Crédito/Débito", rows=[("1100 EUR", None, None, None)]),
                    ],
                ),
            ),
            Section(
                title="Dados gerais de pagamento",
                open=True,
                id="reconciliation-payment-section",
                content=html.Div(
                    className="reconciliation__client-row",
                    children=[
                        html.Span("Cliente:"),
                        html.Div("01920020299 | SONAE SR", className="reconciliation__value-box"),
                    ],
                ),
            ),
            Section(
                title="Evidências de associação a faturas",
                open=True,
                id="reconciliation-evidence-section",
                content=html.Div(
                    "Informação inferida com base em processos abertos em SAP",
                    className="reconciliation__evidence-box",
                ),
            ),
            html.Div(
                className="reconciliation__allocation-area",
                children=[
                    html.Div(
                        className="reconciliation__allocation-table",
                        children=[
                            html.H2("Alocação de montante a faturas", className="heading-2"),
                            TableV1(
                                data_frames=[{"df": allocations, "col_def": ALLOCATION_COLUMNS}],
                                grid_id="reconciliation-allocation-table",
                                dashGridOptions={
                                    "defaultColDef": {
                                        "filter": True,
                                        "sortable": True,
                                        "resizable": True,
                                        "flex": 0,
                                    }
                                },
                                height={"mode": "px", "value": 360},
                            ),
                        ],
                    ),
                    html.Div(
                        className="reconciliation__decision-column",
                        children=[
                            html.H2("Decisão", className="heading-2"),
                            html.Div("Pedir nota de pagamento", className="reconciliation__decision-box"),
                            html.H2("Racional da Decisão", className="heading-2"),
                            dcc.Markdown(
                                """**Evidências**

Por ausência de faturas no extrato e pela não prestação de nota de pagamento, pesquisei as faturas em aberto em SAP para este cliente.

**Decisão**

Uma vez que o montante transferido não abate as faturas em aberto por ordem de antiguidade, recomenda-se pedir *nota de pagamento* para validar que despesas o cliente pretendia saldar.""",
                                className="reconciliation__rationale-box",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="reconciliation__actions",
                children=[
                    Button(
                        "Requisitar NP",
                        icon="lucide:file-pen",
                        id="reconciliation-request-np-button",
                    ),
                    Button(
                        "Emitir recibo",
                        icon="lucide:receipt",
                        id="reconciliation-issue-receipt-button",
                    ),
                ],
            ),
        ],
    )


layout = build_layout()
