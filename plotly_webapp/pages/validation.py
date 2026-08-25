import dash
from dash import dcc, html

from assets.api_calls.validation_api import get_validation_page_data
from components.cards.indicator_card.indicator_card import IndicatorCard
from components.page_header.page_header import PageHeader
from components.section.section import Section
from components.table.V1.table import Table as TableV1


dash.register_page(__name__, path="/validation", title="Validacao")


documents_col_def = [
    {"field": "reference_no", "headerName": "No. Referencia", "width": 160},
    {"field": "bu_name", "headerName": "Unidade de Negocio", "minWidth": 220},
    {"field": "supplier_name", "headerName": "Fornecedor", "minWidth": 220},
    {"field": "total_amount", "headerName": "Valor", "width": 120},
    {"field": "document_date", "headerName": "Data do Documento", "width": 150},
    {"field": "last_interaction_datetime", "headerName": "Data de Processamento", "width": 200},
    {"field": "last_interaction", "headerName": "Ultima Interacao", "width": 180},
    {"field": "is_financial", "headerName": "Financeiro", "width": 120},
    {"field": "issue", "headerName": "Issue", "minWidth": 180},
    {"field": "owner", "headerName": "Owner", "minWidth": 180},
    {"field": "reconciled", "headerName": "Reconciliado", "width": 120},
    {"field": "status", "headerName": "Estado", "width": 120, "cellRenderer": "Status"},
]


def trend(delta):
    if delta > 0:
        return "increase"
    if delta < 0:
        return "decrease"
    return "neutral"


def fmt_pct(value):
    return f"{value:g}%"


def layout():
    return html.Div(
        className="validation__container",
        children=[
            html.Section(
                className="validation__top_section",
                children=[
                    PageHeader(icon="lucide:badge-check", title="Validação"),
                    html.P("Atualizado há 5 segundos", className="body-xs validation__updated_section"),
                ],
            ),
            html.Section(
                className="validation__content_section",
                children=[
                    dcc.Loading(
                        id="validation-loading",
                        type="default",
                        color="var(--primary-color-13)",
                        children=html.Div(id="validation-content"),
                    )
                ],
            ),
        ],
    )


@dash.callback(
    dash.Output("validation-content", "children"),
    dash.Input("url", "pathname"),
    prevent_initial_call=False,
)
def load_validation_content(_pathname):
    dashboard = get_validation_page_data()
    kpis = dashboard["kpis"]
    sap_processes = dashboard["sap_processes"]

    return [
        Section(
            title="Indicadores",
            content=[
                html.Div(
                    className="homepage__indicator_section-wrapper validation__indicator_section-wrapper",
                    children=[
                        IndicatorCard(
                            label_text="Necessita Validação",
                            label_tooltip="faturas",
                            rows=[
                                (
                                    kpis["pending_manual_validation"]["value"],
                                    "última semana",
                                    abs(kpis["pending_manual_validation"]["delta_pp"]),
                                    trend(kpis["pending_manual_validation"]["delta_pp"]),
                                )
                            ],
                            badge_unit="%",
                        ),
                        IndicatorCard(
                            label_text="Necessita Acompanhamento",
                            label_tooltip="faturas",
                            rows=[
                                (
                                    5,
                                    "última semana",
                                    abs(kpis["pending_manual_validation"]["delta_pp"]),
                                    trend(kpis["pending_manual_validation"]["delta_pp"]),
                                )
                            ],
                            badge_unit="%",
                        ),
                        IndicatorCard(
                            label_text="Ingeridas Automaticamente",
                            label_tooltip="faturas",
                            rows=[
                                (
                                    154,
                                    "última semana",
                                    abs(kpis["pending_manual_validation"]["delta_pp"]),
                                    trend(kpis["pending_manual_validation"]["delta_pp"]),
                                )
                            ],
                            badge_unit="%",
                        ),
                        IndicatorCard(
                            label_text="Devolvidas ao Fornecedor",
                            label_tooltip="faturas",
                            rows=[
                                (
                                    3,
                                    "última semana",
                                    abs(kpis["pending_manual_validation"]["delta_pp"]),
                                    trend(kpis["pending_manual_validation"]["delta_pp"]),
                                )
                            ],
                            badge_unit="%",
                        ),
                    ],
                )
            ],
            open=True,
        ),
        Section(
            title="Processos",
            content=[
                dcc.Loading(
                    id="validation-priority-processes-loading",
                    type="default",
                    color="var(--primary-color-13)",
                    children=TableV1(
                        data_frames=[{"df": sap_processes, "col_def": documents_col_def}],
                        grid_id="validation-priority-processes-table",
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
                )
            ],
            open=True,
        ),
    ]
