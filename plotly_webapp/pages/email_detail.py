import dash
from dash import html, dcc, Input, Output, State, callback_context, no_update
from dash_iconify import DashIconify
from dash.dcc import Tab
import requests

from components.page_header.page_header import PageHeader
from components.banner.banner import TableBanner
from components.tabs.tabs import Tabs
from components.button.button import Button
from components.section.section import Section
from components.label.label import Label
from components.checkbox.checkbox import Checkbox
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

from assets.api_calls.extraction_api import (
    alter_document_details,
    get_document_details,
    get_next_priority_document,
)


dash.register_page(
    __name__,
    path_template="/detalhe/<ref_number>",
    title="Detalhe do Email",
)



def layout(ref_number=None, **kwargs):
    try:
        match = get_document_details(str(ref_number))
    except requests.RequestException:
        match = None

    if match:
        fields = match.get("fields", {})
        alerts = match.get("alerts", [])
        action = match.get("action")
        status = match.get("status")

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
        status = None
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
        dcc.Store(
            id="document_manual_validation_store",
            data=action in {
                "Validate Manually",
                "Validar Manualmente",
                "Validação Manual",
                "Necessita de Validação",
            }
            and status == "Pending",
        ),
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
                                title = f"Número de Referência: {ref_number}",  
                            ),
                            TableBanner(
                                message="Carregada em SAP",
                                variant = "positive",
                                icon = "lucide:check"
                            )
                        ]
                      ),
                      html.Section(
                        className="email_detail__top_right_section",
                            children = [
                              Button("Detalhes do Email", icon="lucide:eye", variant="outline")
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
                                                        #     [
                                                        #         Button("Correção", icon="lucide:chevron-right", variant="outline"),
                                                        #         TableBanner(
                                                        #             message="",
                                                        #             variant="positive",
                                                        #             icon="lucide:check",
                                                        #         ),
                                                        #     ],
                                                        #     className="email_detail__invoice_button_icon",
                                                            DashIconify(icon="lucide:triangle-alert", className="email_detail__invoice_button_icon")
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
                                    src="/assets/pdf-viewer.html?file=/assets/invoices/Fatura-Exemplo-pdf.pdf",
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
                        dcc.Link(
                            Button("Próxima Fatura", id="next-document-button", icon="lucide:arrow-right"),
                            id="next-document-link",
                            href="#",
                            className="email_detail__next_link",
                        ),
                        html.P(id="email-detail-update-status", className="body-sm email_detail__status"),
                    ]
                ),
            ]           
        )
    ]
)


@dash.callback(
    Output("next-document-link", "href"),
    Output("next-document-link", "style"),
    Input("document_id_store", "data"),
)
def configure_next_document_button(document_id):
    if not document_id:
        return "#", {"display": "none"}

    result = get_next_priority_document(document_id)
    next_document_id = result.get("next_document_id")
    if not result.get("eligible") or not next_document_id:
        return "#", {"display": "none"}

    return f"/detalhe/{next_document_id}", {}


@dash.callback(
    Output("email-detail-update-status", "children"),
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
    triggered = callback_context.triggered
    if not triggered:
        raise dash.exceptions.PreventUpdate

    if not document_id:
        return "Documento invalido"

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

    button_id = triggered[0]["prop_id"].split(".")[0]
    action = None
    status = None

    if button_id == "send-sap-button":
        action = "Ingerir em SAP"
        status = "Created"
    elif button_id == "save-button":
        action = "ValidaA\x15A\u015fo Manual"
        status = "Sob RevisA\u015fo"

    try:
        alter_document_details(
            document_id,
            alerts or [],
            updated_fields,
            action=action,
            status=status,
            last_modified_by="Mariana Dias",
        )
    except Exception as exc:
        return f"Erro ao guardar: {exc}"

    if button_id == "send-sap-button":
        return "Documento enviado para SAP"
    return "Documento guardado"

