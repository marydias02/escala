from datetime import datetime

import dash
from dash import dcc, html

from assets.api_calls.validation_api import get_process_messages, get_validation_page_data
from auth.msal_client import get_access_token
from components.cards.indicator_card.indicator_card import IndicatorCard
from components.page_header.page_header import PageHeader
from components.right_drawer.right_drawer import RightDrawer
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
    {
        "field": "is_financial",
        "headerName": "Financeiro",
        "width": 120,
        "cellDataType": "text",
        "valueFormatter": {"function": "params.value ? 'Sim' : 'Não'"},
    },
    {"field": "issue", "headerName": "Issue", "minWidth": 180},
    {"field": "owner", "headerName": "Owner", "minWidth": 150},
    {
        "field": "reconciled",
        "headerName": "Reconciliado",
        "width": 150,
        "valueFormatter": {"function": "params.value ? 'Sim' : 'Não'"},
    },
    {"field": "status", "headerName": "Estado", "width": 280, "cellRenderer": "SAPStatus"},
]


def trend(delta):
    if delta > 0:
        return "increase"
    if delta < 0:
        return "decrease"
    return "neutral"


def fmt_pct(value):
    return f"{value:g}%"


def _format_message_timestamp(value: str) -> str:
    if not value:
        return ""

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value

    return parsed.strftime("%Y-%m-%d %H:%M")


def _message_bubble(message: dict) -> html.Div:
    sender = (message.get("sender") or "").strip()
    recipient = (message.get("recipient") or "").strip()
    content = message.get("content") or ""
    timestamp = message.get("timestamp") or ""
    is_system_sender = sender.casefold() == "system"

    return html.Div(
        className="validation__message validation__message--system"
        if is_system_sender
        else "validation__message validation__message--user",
        children=[
            html.Div(content, className="validation__message-content"),
            html.Div(_format_message_timestamp(timestamp), className="validation__message-timestamp"),
        ],
    )


def _build_messages_section(messages: list[dict]) -> Section:
    participants = []
    for message in messages or []:
        sender = (message.get("sender") or "").strip()
        recipient = (message.get("recipient") or "").strip()
        participant = recipient if sender.casefold() == "system" else sender
        if participant and participant not in participants:
            participants.append(participant)

    top_line = " / ".join(participants) if participants else "Sem destinatário identificado"
    message_children = (
        [_message_bubble(message) for message in messages]
        if messages
        else [
            html.Div(
                "Sem mensagens para este processo.",
                className="validation__message-empty",
            )
        ]
    )

    return Section(
        title="Mensagens",
        content=[
            html.Div(
                className="right-sidebar__content",
                children=[
                    html.Div(
                        className="right-sidebar__meta-box validation__messages-shell",
                        children=[
                            html.Div(
                                top_line,
                                className="right-sidebar__message-participant body-sm",
                            ),
                            html.Div(
                                className="right-sidebar__email-body-box validation__messages-box",
                                children=message_children,
                            ),
                        ],
                    ),
                ],
            )
        ],
        open=True,
    )


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
    dashboard = get_validation_page_data(get_access_token())
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
                            label_text="Não Conformes",
                            label_tooltip="faturas não conformes recebidas esta semana",
                            rows=[
                                (
                                    kpis["non_conforming_received"]["value"],
                                    "última semana",
                                    abs(kpis["non_conforming_received"]["delta_pp"]),
                                    trend(kpis["non_conforming_received"]["delta_pp"]),
                                )
                            ],
                            badge_unit="%",
                        ),
                        IndicatorCard(
                            label_text="Necessita Validação",
                            label_tooltip="faturas pendentes de validação manual neste momento; a diferença percentual foi calculada no início da semana",
                            rows=[
                                (
                                    kpis["needs_manual_validation"]["value"],
                                    "última semana",
                                    abs(kpis["needs_manual_validation"]["delta_pp"]),
                                    trend(kpis["needs_manual_validation"]["delta_pp"]),
                                )
                            ],
                            badge_unit="%",
                        ),
                        IndicatorCard(
                            label_text="Necessita Acompanhamento",
                            label_tooltip="faturas em resolução pelo Buyer neste momento; a diferença percentual foi calculada no início da semana",
                            rows=[
                                (
                                    kpis["with_buyer"]["value"],
                                    "última semana",
                                    abs(kpis["with_buyer"]["delta_pp"]),
                                    trend(kpis["with_buyer"]["delta_pp"]),
                                )
                            ],
                            badge_unit="%",
                        ),
                        IndicatorCard(
                            label_text="Processadas pelo Agente",
                            label_tooltip="total de faturas processadas pelo agente esta semana",
                            rows=[
                                (
                                    kpis["processed_by_agent"]["value"],
                                    "última semana",
                                    abs(kpis["processed_by_agent"]["delta_pp"]),
                                    trend(kpis["processed_by_agent"]["delta_pp"]),
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
        RightDrawer(
            drawer_id="validation-drawer",
            title="Comunicação em SAP",
            children=[html.Div(id="validation-drawer-content")],
        ),
    ]


@dash.callback(
    dash.Output("validation-drawer", "className"),
    dash.Output("validation-drawer-content", "children"),
    dash.Input("validation-priority-processes-table", "selectedRows"),
    dash.Input("validation-drawer-close", "n_clicks"),
    prevent_initial_call=False,
)
def toggle_validation_drawer(selected_rows, close_clicks):
    triggered_id = dash.callback_context.triggered_id

    if triggered_id == "validation-drawer-close":
        return "right-sidebar sidebar--collapsed", dash.no_update

    if selected_rows:
        process_ref_no = selected_rows[0].get("reference_no")
        messages = get_process_messages(get_access_token(), str(process_ref_no)) if process_ref_no else []
        return "right-sidebar", _build_messages_section(messages)

    return "right-sidebar sidebar--collapsed", dash.no_update
