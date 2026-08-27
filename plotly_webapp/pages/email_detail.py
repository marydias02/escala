import dash
from dash import html, dcc, Input, Output, State, callback_context, no_update, ALL
from dash_iconify import DashIconify
from dash.dcc import Tab
import requests

from assets.api_calls.extraction_api import (
    alter_document_details,
    get_document_details,
    get_document_email,
    get_next_priority_document,
)
from components.page_header.page_header import PageHeader
from components.banner.banner import TableBanner
from components.tabs.tabs import Tabs
from components.button.button import Button
from components.section.section import Section
from components.label.label import Label
from components.checkbox.checkbox import Checkbox
from components.cards.indicator_card.indicator_card import IndicatorCard
from components.right_drawer.right_drawer import RightDrawer, register_right_drawer_callbacks
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


def _action_banner_props(action):
    if action in {"Validação Manual"}:
        return "negative", "lucide:triangle-alert"
    if action in {"Retornado ao Fornecedor", "Encaminhar para Tesouraria"}:
        return "warning", "lucide:arrow-right"
    if action in {"Ingerir em SAP"}:
        return "positive", "lucide:check"
    return "neutral", None


dash.register_page(
    __name__,
    path_template="/detalhe/<ref_number>",
    title="Detalhe do Email",
)

register_right_drawer_callbacks(
    "email-detail-drawer",
    "email-detail-open-drawer",
)


def _build_email_drawer_content(document_id):
    if not document_id:
        return "Sem documento selecionado."

    try:
        email = get_document_email(str(document_id))
    except Exception:
        return "Não foi possível carregar o email."

    sender = email.get("sender_email") or "N/D"
    subject = email.get("email_subject") or "N/D"
    content = email.get("email_content") or "N/D"
    received = email.get("reception_date") or "N/D"

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
                            html.Span(str(received), className="right-sidebar__meta-value"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="right-sidebar__email-box",
                children=[
                    html.Div(subject, className="right-sidebar__email-subject"),
                    html.Div(
                        className="right-sidebar__email-body-box",
                        children=[
                            html.Div(content, className="right-sidebar__email-body"),
                        ],
                    ),
                ],
            ),
        ],
    )



def layout(ref_number=None, **_kwargs):
    """Render the route immediately; document data is populated by a callback."""
    return html.Div(
        [
            dcc.Store(id="email-detail-ref-number", data=str(ref_number)),
            dcc.Loading(
                id="email-detail-loading",
                type="default",
                color="var(--primary-color-13)",
                children=html.Div(id="email-detail-content"),
            ),
        ]
    )


@dash.callback(
    Output("email-detail-content", "children"),
    Input("email-detail-ref-number", "data"),
)
def load_email_detail(ref_number):
    return _build_email_detail(ref_number)


def _build_email_detail(ref_number):
    try:
        match = get_document_details(str(ref_number))
    except requests.RequestException:
        match = None

    if match:
        fields = match.get("fields", {})
        alerts = match.get("alerts", [])
        action = match.get("action")

        issue_date = fields.get("issue_date", {}).get("value")
        data_recepcao = (
            pd.to_datetime(issue_date, dayfirst=True).date()
            if issue_date
            else None
        )

        business_unit = fields.get("bu_name", {}).get("value")
        # bu_vat = fields.get("bu_vat", {}).get("value")
        
        supplier_name = fields.get("supplier_name", {}).get("value")
        supplier_vat = fields.get("supplier_vat", {}).get("value")
        
        total_amount = fields.get("total_amount", {}).get("value")
        vat_amount = fields.get("vat_amount", {}).get("value")
        base_amount = fields.get("base_amount", {}).get("value")
        currency = fields.get("currency", {}).get("value")

    else:
        fields = {}
        alerts = []
        action = None
        data_recepcao = None
        business_unit = None
        # bu_vat = None
        supplier_name = None
        supplier_vat = None
        total_amount = None
        currency = None

    return html.Div(
    [  
        dcc.Store(id="document_id_store", data=str(ref_number)),
        dcc.Store(id="document_fields_store", data=fields),
        dcc.Store(id="document_alerts_store", data=alerts),
        html.Div( 
            className="email_detail__container",
            children=[
                html.Section(
                    className="email_detail__top_section",
                    children=[
                      html.Section(
                        className="email_detail__top_left_section",
                        children = [
                            PageHeader(
                                title = f"Detalhe da fatura do fornecedor: {supplier_name}",  
                            ),
                            TableBanner(
                                message=action,
                                variant=_action_banner_props(action)[0],
                                icon=_action_banner_props(action)[1],
                            )
                        ]
                      ),
                      html.Section(
                        className="email_detail__top_right_section",
                            children = [
                              Button("Detalhes do Email", id="email-detail-open-drawer", icon="lucide:eye", variant="outline")
                            ]
                      )
                    ],                  
                ),
                html.Section(
                    className="email_detail__content_section",
                    children=[
                        # html.H1("Validação"),
                        # html.P("Extração dos campos da fatura original", className="body-sm subtitle"),
                        html.Section(
                          className="email_detail__inside_content_section",
                          children=[
                            html.Div(
                                "Backend indisponível. Verifique o servidor em localhost:8000.",
                                className="email_detail__backend_warning",
                            ) if match is None else html.Span(),
                            html.Section(
                              className="email_detail__content_left_section",
                              children=[
                                Section(
                                  title="Alertas",
                                  content=[
                                    html.Ul(
                                        className="email_detail__invoice_errors",
                                        children=[
                                            html.Li(
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.H4(a.split(":", 1)[0].strip(), className="body-sm"),
                                                                Label(a.split(":", 1)[1].strip() if ":" in a else ""),
                                                            ],
                                                            className="email_detail__invoice_text",
                                                        ),
                                                        html.Div(
                                                            [
                                                                Button(
                                                                    "Ok",
                                                                    id={
                                                                        "type": "email-detail-correction-button",
                                                                        "alert": a,
                                                                    },
                                                                    icon="lucide:check",
                                                                    variant="outline",
                                                                ) if a.split(":", 1)[0].strip() in {
                                                                    "Confiança baixa",
                                                                    "Nota de encomenda não encontrada",
                                                                    "NIF do fornecedor não encontrado",
                                                                } else None,
                                                                html.Div(
                                                                    DashIconify(icon="lucide:triangle-alert", className="email_detail__invoice_button_icon"),
                                                                ),
                                                            ],
                                                            className="email_detail__invoice_actions",
                                                        ),
                                                      ],
                                                    className="email_detail__invoice_item",
                                                )
                                            )
                                            for a in alerts
                                        ],
                                    )
                                  ],
                                  open=True
                                ),
                                html.Section(
                                  className="email_detail__field_extraction_section",
                                  children=[
                                      html.H1("Extração dos Campos"),
                                        html.Section(
                                            className="email_detail__field_grid",
                                            children=[
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                                        Label(label_text="Unidade de Negócio"),
                                                    
                                                        dcc.Input(id='bu_name', value=business_unit, type='text', className="email_detail__input"),
                                                    ],
                                                ),
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                                        Label(label_text="Nome do Fornecedor"),
                                                    
                                                        dcc.Input(id='supplier_name', value=supplier_name, type='text', className="email_detail__input"),
                                                    ],
                                                ),
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                                        Label(label_text="NIF do Fornecedor"),
                                                        
                                                        dcc.Input(id='supplier_vat', value=supplier_vat, type='text', className="email_detail__input"),
                                                    ],
                                                ),
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                                        Label(label_text="Data da Fatura"),
                                                        
                                                        dcc.DatePickerSingle(
                                                            id='issue_date',
                                                            date=data_recepcao,
                                                            className="email_detail__input"
                                                        )
                                                    ],
                                                ),
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                                        Label(label_text="Valor Total"),
                                                        
                                                        dcc.Input(id='total_amount', value=total_amount, type='number', className="email_detail__input"),
                                                    ],
                                                ),  
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                                        Label(label_text="Valor do IVA"),
                                                        
                                                        dcc.Input(id='vat_amount', value=vat_amount, type='number', className="email_detail__input"),
                                                    ],
                                                ),   
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                                        Label(label_text="Valor Base"),
                                                        
                                                        dcc.Input(id='base_amount', value=base_amount, type='number', className="email_detail__input"),
                                                    ],
                                                ),                                                                                                                                                 
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                                        Label(label_text="Moeda"),
                                                        
                                                        dcc.Dropdown(
                                                            id='currency',
                                                            options=['EUR', 'USD', 'CVE'],
                                                            value=currency,
                                                            clearable=False,
                                                            className="email_detail__input"
                                                        )
                                                    ],
                                                ),
                                                html.Div(
                                                    className="email_detail__field",
                                                    children=[
                                                        Label(label_text="Nota de Crédito"),
                                                        
                                                        Checkbox(id='credit_note', label_text="Sim")
                                                    ]
                                                )
                                            ]
                                        )
                                    ]
                                )
                              ]
                            ),
                            html.Section(
                              className="email_detail__content_right_section",
                              children=[
                                html.Iframe(
                                    id="document-pdf-viewer",
                                    src=f"/assets/pdf-viewer.html?file=/pdf/{ref_number}",
                                    style={
                                        "width": "100%",
                                        "height":"100%",
                                        "border": "none",
                                    },
                                )
                              ]
                            )
                          ]
                        )
                    ]
                ),
                html.Section(
                    className="email_detail__bottom_section",
                    children=[
                        Button("Exportar", icon="lucide:file-down", variant="outline"),
                        Button("Guardar", id="save-button", icon="lucide:circle-check", variant="outline"),
                        Button("Enviar para SAP", id="send-sap-button", icon="lucide:send"),
                        html.P(id="email-detail-update-status", className="body-sm email_detail__status"),
                    ]
                ),
                RightDrawer(
                    drawer_id="email-detail-drawer",
                    title="Detalhes do Email",
                    children=[
                        Section(
                            title="Conteúdo do Email",
                            content=html.Div(id="email-detail-drawer-email-content"),
                            open=True,
                        ),
                    ],
                ),
            ]           
        )
    ]
)


@dash.callback(
    Output("email-detail-drawer-email-content", "children"),
    Input("email-detail-open-drawer", "n_clicks"),
    State("document_id_store", "data"),
    prevent_initial_call=True,
)
def load_email_drawer_content(_clicks, document_id):
    return _build_email_drawer_content(document_id)


@dash.callback(
    Output("email-detail-update-status", "children", allow_duplicate=True),
    Output("email-detail-content", "children", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Input("save-button", "n_clicks"),
    Input("send-sap-button", "n_clicks"),
    State("document_id_store", "data"),
    State("document_fields_store", "data"),
    State("document_alerts_store", "data"),
    State("bu_name", "value"),
    State("supplier_name", "value"),
    State("supplier_vat", "value"),
    State("issue_date", "date"),
    State("total_amount", "value"),
    State("vat_amount", "value"),
    State("base_amount", "value"),
    State("currency", "value"),
    State("credit_note", "value"),
    prevent_initial_call=True,
)
def update_document_details(
    save_clicks,
    send_clicks,
    document_id,
    fields,
    alerts,
    bu_name,
    supplier_name,
    supplier_vat,
    issue_date,
    total_amount,
    vat_amount,
    base_amount,
    currency,
    credit_note,
):
    if not (save_clicks or send_clicks):
        raise dash.exceptions.PreventUpdate

    triggered = callback_context.triggered
    if not triggered:
        raise dash.exceptions.PreventUpdate

    if not document_id:
        return "Documento invalido", no_update

    button_id = triggered[0]["prop_id"].split(".")[0]
    updated_fields = fields.copy() if isinstance(fields, dict) else {}

    def update_field(name: str, value: object) -> None:
        existing = updated_fields.get(name)
        updated_fields[name] = {**(existing or {}), "value": value}

    if bu_name is not None:
        update_field("bu_name", bu_name)
    if supplier_name is not None:
        update_field("supplier_name", supplier_name)
    if supplier_vat is not None:
        update_field("supplier_vat", supplier_vat)
    if issue_date is not None:
        update_field("issue_date", issue_date)
    if total_amount is not None:
        update_field("total_amount", total_amount)
    if vat_amount is not None:
        update_field("vat_amount", vat_amount)
    if base_amount is not None:
        update_field("base_amount", base_amount)
    if currency is not None:
        update_field("currency", currency)
    if credit_note is not None:
        update_field("credit_note", bool(credit_note))

    missing_field_alert_map = {
        "Unidade de Negócio": bu_name,
        "Nome do Fornecedor": supplier_name,
        "NIF do Fornecedor": supplier_vat,
        "Data da Fatura": issue_date,
        "Valor Total": total_amount,
        "Valor do IVA": vat_amount,
        "Valor Base": base_amount,
        "Moeda": currency,
        "Nota de Crédito": credit_note,
    }

    def _is_filled(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return bool(value.strip())
        return True

    normalized_missing_field_alert_map = {
        key.strip().casefold(): value
        for key, value in missing_field_alert_map.items()
    }

    updated_alerts = list(alerts or [])
    if button_id in {"save-button", "send-sap-button"}:
        updated_alerts = [
            alert
            for alert in updated_alerts
            if not (
                alert.split(":", 1)[0].strip() == "Campo em falta"
                and _is_filled(
                    normalized_missing_field_alert_map.get(
                        alert.split(":", 1)[1].strip().casefold(),
                    )
                )
            )
        ]

    action = None
    status = None
    next_document_id = None

    if button_id == "send-sap-button":
        action = "Ingerir em SAP"
        status = "Criado"
        result = get_next_priority_document(document_id)
        next_document_id = result.get("next_document_id")
    elif button_id == "save-button":
        action = "Validação Manual"
        status = "Sob Revisão"

    try:
        alter_document_details(
            document_id,
            updated_alerts,
            updated_fields,
            action=action,
            status=status,
            last_modified_by="Mariana Dias",
        )
    except Exception as exc:
        return f"Erro ao guardar: {exc}", no_update

    if button_id == "send-sap-button":
        if next_document_id:
            return "Documento enviado para SAP", _build_email_detail(next_document_id), f"/detalhe/{next_document_id}"
        return "Documento enviado para SAP", _build_email_detail(document_id), no_update
    return "Documento guardado", _build_email_detail(document_id), no_update


@dash.callback(
    Output("document_alerts_store", "data"),
    Output("email-detail-content", "children", allow_duplicate=True),
    Output("email-detail-update-status", "children"),
    Input({"type": "email-detail-correction-button", "alert": ALL}, "n_clicks"),
    State("document_id_store", "data"),
    State("document_alerts_store", "data"),
    State("document_fields_store", "data"),
    prevent_initial_call=True,
)
def remove_alert_from_document(_clicks, document_id, alerts, fields):
    triggered = callback_context.triggered
    if not triggered or triggered[0]["prop_id"] == ".":
        raise dash.exceptions.PreventUpdate

    if not document_id:
        return no_update, no_update, "Documento invalido"

    triggered_id = callback_context.triggered_id
    if not isinstance(triggered_id, dict):
        raise dash.exceptions.PreventUpdate

    if not any(click_count for click_count in (_clicks or [])):
        raise dash.exceptions.PreventUpdate

    alert_to_remove = triggered_id.get("alert")
    if not alert_to_remove:
        raise dash.exceptions.PreventUpdate

    current_alerts = list(alerts or [])
    if alert_to_remove not in current_alerts:
        raise dash.exceptions.PreventUpdate

    updated_alerts = [alert for alert in current_alerts if alert != alert_to_remove]

    try:
        alter_document_details(
            document_id,
            updated_alerts,
            fields if isinstance(fields, dict) else {},
            last_modified_by="Mariana Dias",
        )
    except Exception as exc:
        return no_update, no_update, f"Erro ao remover alerta: {exc}"

    return updated_alerts, _build_email_detail(document_id), "Alerta removido"

