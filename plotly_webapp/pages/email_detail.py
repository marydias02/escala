import dash
import pandas as pd
import requests
from dash import ALL, Input, Output, State, callback_context, dcc, html, no_update
from dash_iconify import DashIconify
from requests import RequestException

from assets.api_calls.extraction_api import (
    alter_document_details,
    get_document_details,
    get_document_email,
    get_next_priority_document,
    search_business_units,
    search_purchase_orders,
    search_suppliers,
)
from auth.msal_client import get_access_token
from components.banner.banner import TableBanner
from components.button.button import Button
from components.checkbox.checkbox import Checkbox
from components.label.label import Label
from components.page_header.page_header import PageHeader
from components.right_drawer.right_drawer import RightDrawer, register_right_drawer_callbacks
from components.section.section import Section


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


def _build_email_drawer_content(token, document_id):
    if not document_id:
        return "Sem documento selecionado."

    try:
        email = get_document_email(token, str(document_id))
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
            dcc.Store(id="email-detail-export-trigger"),
            html.Div(id="email-detail-content"),
        ]
    )


@dash.callback(
    Output("email-detail-content", "children"),
    Input("email-detail-ref-number", "data"),
)
def load_email_detail(ref_number):
    return _build_email_detail(get_access_token(), ref_number)


def _party_options(rows, id_key):
    return [
        {
            "label": html.Div(
                [html.Strong(row.get("name") or ""), html.Small(f"{row.get(id_key) or ''} · {row.get('vat') or ''}")]
            ),
            "value": row.get(id_key),
            "_row": row,
        }
        for row in rows
    ]


@dash.callback(
    Output("bu_selector", "options"),
    Output("bu_name", "value"),
    Output("bu-selection", "data"),
    Output("bu_selector", "labels"),
    Input("bu_selector", "search_value"),
    Input("bu_selector", "value"),
    State("bu_selector", "options"),
    prevent_initial_call=True,
)
def update_bu_selector(search_value, selected, options):
    if selected:
        row = next((option.get("_row", {}) for option in (options or []) if option.get("value") == selected), {})
        return options or [], row.get("name"), {"id": row.get("bu_id", selected), "vat": row.get("vat")}, {"no_options_found": "A procurar..."}
    if not search_value or len(search_value.strip()) < 2:
        return [], no_update, no_update, {"no_options_found": "A procurar..."}
    rows = search_business_units(get_access_token(), search_value)
    return _party_options(rows, "bu_id"), no_update, no_update, {"no_options_found": "Não encontrado"}


@dash.callback(
    Output("supplier_selector", "options"),
    Output("supplier_name", "value"),
    Output("supplier-selection", "data"),
    Output("supplier_selector", "labels"),
    Input("supplier_selector", "search_value"),
    Input("supplier_selector", "value"),
    State("supplier_selector", "options"),
    prevent_initial_call=True,
)
def update_supplier_selector(search_value, selected, options):
    if selected:
        row = next((option.get("_row", {}) for option in (options or []) if option.get("value") == selected), {})
        return options or [], row.get("name"), {"id": row.get("supplier_id", selected), "vat": row.get("vat")}, {"no_options_found": "A procurar..."}
    if not search_value or len(search_value.strip()) < 3:
        return [], no_update, no_update, {"no_options_found": "A procurar..."}
    rows = search_suppliers(get_access_token(), search_value)
    return _party_options(rows, "supplier_id"), no_update, no_update, {"no_options_found": "Não encontrado"}


@dash.callback(
    Output("po_selector", "options"),
    Output("po_selector", "labels", allow_duplicate=True),
    Input("po_selector", "search_value"),
    State("po_selector", "value"),
    State("po_selector", "options"),
    prevent_initial_call=True,
)
def update_purchase_order_selector(search_value, selected, current_options):
    if not search_value or len(search_value.strip()) < 3:
        return no_update, {"no_options_found": "Não encontrado"}
    rows = search_purchase_orders(get_access_token(), search_value)
    po_options = [
        {
            "label": html.Div([
                html.Strong(row.get("po_code") or ""),
                html.Small(f"{row.get('supplier_name') or ''} · {row.get('bu_id') or ''}"),
            ]),
            "value": row.get("po_code"),
        }
        for row in rows
    ]
    selected = selected or []
    existing = {str(option.get("value")): option for option in (current_options or [])}
    merged = [
        existing.get(
            str(value),
            {"label": str(value), "value": value},
        )
        for value in selected
    ]
    merged_values = {str(option.get("value")) for option in merged}
    merged.extend(option for option in po_options if str(option.get("value")) not in merged_values)
    return merged, {"no_options_found": "Não encontrado", "select_all": "", "deselect_all": "Desmarcar todos"}


@dash.callback(
    Output("po_list", "value"),
    Input("po_selector", "value"),
    prevent_initial_call=True,
)
def update_purchase_order_value(selected):
    return ", ".join(str(value) for value in (selected or []))


dash.clientside_callback(
    """
    function (n_clicks, ref_number) {
        if (!n_clicks || !ref_number) {
            return window.dash_clientside.no_update;
        }

        const link = document.createElement("a");
        link.href = "/pdf/" + encodeURIComponent(ref_number);
        link.download = String(ref_number) + ".pdf";
        document.body.appendChild(link);
        link.click();
        link.remove();

        return window.dash_clientside.no_update;
    }
    """,
    Output("email-detail-export-trigger", "data"),
    Input("email-detail-export-button", "n_clicks"),
    State("email-detail-ref-number", "data"),
    prevent_initial_call=True,
)


def _build_email_detail(token, ref_number):
    document_lookup_failed = False
    try:
        match = get_document_details(token, str(ref_number))
    except requests.RequestException as exc:
        match = None
        document_lookup_failed = getattr(getattr(exc, "response", None), "status_code", None) != 404

    if match:
        fields = match.get("fields") or {}
        alerts = match.get("alerts", [])
        action = match.get("action")

        def field_value(name: str):
            field = fields.get(name)
            if isinstance(field, dict):
                return field.get("value")
            return None

        issue_date = field_value("issue_date")
        data_recepcao = pd.to_datetime(issue_date, dayfirst=True).date() if issue_date else None

        business_unit = field_value("bu_name")
        bu_id = field_value("bu_id")
        bu_vat = field_value("bu_vat")
        document_number = field_value("document_number")
        po_list = match.get("po_list") or []
        po_values = [po.get("value") if isinstance(po, dict) else po for po in po_list]

        supplier_name = field_value("supplier_name")
        supplier_id = field_value("supplier_id")
        supplier_vat = field_value("supplier_vat")

        total_amount = field_value("total_amount")
        vat_amount = field_value("vat_amount")
        currency = field_value("currency")

    else:
        fields = {}
        alerts = []
        action = None
        data_recepcao = None
        business_unit = None
        # bu_vat = None
        supplier_name = None
        supplier_id = None
        supplier_vat = None
        total_amount = None
        currency = None
        bu_id = None
        bu_vat = None
        document_number = None
        po_values = []

    def hydrate_party(search_fn, query, id_key):
        if not query:
            return None
        try:
            rows = search_fn(token, str(query), limit=10)
        except RequestException:
            return None
        if not rows:
            return None
        return next((row for row in rows if str(row.get(id_key)) == str(query)), rows[0])

    bu_match = hydrate_party(search_business_units, business_unit or bu_id or bu_vat, "bu_id")
    if bu_match:
        business_unit = business_unit or bu_match.get("name")
        bu_id = bu_id or bu_match.get("bu_id")
        bu_vat = bu_vat or bu_match.get("vat")

    supplier_match = hydrate_party(search_suppliers, supplier_name or supplier_id or supplier_vat, "supplier_id")
    if supplier_match:
        supplier_name = supplier_name or supplier_match.get("name")
        supplier_id = supplier_id or supplier_match.get("supplier_id")
        supplier_vat = supplier_vat or supplier_match.get("vat")

    return html.Div(
        [
            dcc.Store(id="document_id_store", data=str(ref_number)),
            dcc.Store(id="document_fields_store", data=fields),
            dcc.Store(id="document_alerts_store", data=alerts),
            dcc.Store(id="bu-selection", data={"id": bu_id, "vat": bu_vat}),
            dcc.Store(id="supplier-selection", data={"id": supplier_id, "vat": supplier_vat}),
            html.Div(
                className="email_detail__container",
                children=[
                    html.Section(
                        className="email_detail__top_section",
                        children=[
                            html.Section(
                                className="email_detail__top_left_section",
                                children=[
                                    PageHeader(
                                        title=f"Detalhe da fatura do fornecedor: {supplier_name}",
                                    ),
                                    TableBanner(
                                        message=action,
                                        variant=_action_banner_props(action)[0],
                                        icon=_action_banner_props(action)[1],
                                    ),
                                ],
                            ),
                            html.Section(
                                className="email_detail__top_right_section",
                                children=[
                                    Button(
                                        "Detalhes do Email",
                                        id="email-detail-open-drawer",
                                        icon="lucide:eye",
                                        variant="outline",
                                    )
                                ],
                            ),
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
                                    )
                                    if match is None
                                    else html.Span(),
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
                                                                                html.H4(
                                                                                    a.split(":", 1)[0].strip(),
                                                                                    className="body-sm",
                                                                                ),
                                                                                Label(
                                                                                    a.split(":", 1)[1].strip()
                                                                                    if ":" in a
                                                                                    else ""
                                                                                ),
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
                                                                                )
                                                                                if a.split(":", 1)[0].strip()
                                                                                in {
                                                                                    "Confiança baixa",
                                                                                    "Nota de encomenda não encontrada",
                                                                                    "NIF do fornecedor não encontrado",
                                                                                }
                                                                                else None,
                                                                                html.Div(
                                                                                    DashIconify(
                                                                                        icon="lucide:triangle-alert",
                                                                                        className="email_detail__invoice_button_icon",
                                                                                    ),
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
                                                open=True,
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
                                                                    dcc.Dropdown(
                                                                        id="bu_selector",
                                                                        value=bu_id,
                                                                        options=(
                                                                            [
                                                                                {
                                                                                    "label": html.Div(
                                                                                        [
                                                                                            html.Strong(business_unit),
                                                                                            html.Small(
                                                                                                f"{bu_id} · {bu_vat or ''}"
                                                                                            ),
                                                                                        ]
                                                                                    ),
                                                                                    "value": bu_id,
                                                                                }
                                                                            ]
                                                                            if bu_id
                                                                            else []
                                                                        ),
                                                                        searchable=True,
                                                                        clearable=True,
                                                                        placeholder="Pesquisar por nome, ID ou NIF...",
                                                                        labels={"no_options_found": "A procurar..."},
                                                                        debounce=True,
                                                                    ),
                                                                    dcc.Input(
                                                                        id="bu_name",
                                                                        value=business_unit,
                                                                        style={"display": "none"},
                                                                        type="text",
                                                                        className="email_detail__input",
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                className="email_detail__field",
                                                                children=[
                                                                    Label(label_text="Nome do Fornecedor"),
                                                                    dcc.Dropdown(
                                                                        id="supplier_selector",
                                                                        value=supplier_id,
                                                                        options=(
                                                                            [
                                                                                {
                                                                                    "label": html.Div(
                                                                                        [
                                                                                            html.Strong(supplier_name),
                                                                                            html.Small(
                                                                                                f"{supplier_id} · {supplier_vat or ''}"
                                                                                            ),
                                                                                        ]
                                                                                    ),
                                                                                    "value": supplier_id,
                                                                                }
                                                                            ]
                                                                            if supplier_id
                                                                            else []
                                                                        ),
                                                                        searchable=True,
                                                                        clearable=True,
                                                                        placeholder="Pesquisar por nome, ID ou NIF...",
                                                                        labels={"no_options_found": "A procurar..."},
                                                                        debounce=True,
                                                                    ),
                                                                    dcc.Input(
                                                                        id="supplier_name",
                                                                        value=supplier_name,
                                                                        style={"display": "none"},
                                                                        type="text",
                                                                        className="email_detail__input",
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                className="email_detail__field",
                                                                children=[
                                                                    Label(label_text="Número do Documento"),
                                                                    dcc.Input(
                                                                        id="document_number",
                                                                        value=document_number,
                                                                        type="text",
                                                                        className="email_detail__input",
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                className="email_detail__field",
                                                                children=[
                                                                    Label(label_text="Ordem de Compra"),
                                                                    dcc.Dropdown(
                                                                        id="po_selector",
                                                                        options=[{"label": str(po), "value": str(po)} for po in po_values if po],
                                                                        value=[str(po) for po in po_values if po],
                                                                        multi=True,
                                                                        searchable=True,
                                                                        clearable=True,
                                                                        labels={"no_options_found": "A procurar...", "select_all": "", "deselect_all": "Desmarcar todos"},
                                                                        placeholder="Insira pelo menos 3 dígitos",
                                                                    ),
                                                                    dcc.Input(
                                                                        id="po_list",
                                                                        value=", ".join(
                                                                            str(po) for po in po_values if po
                                                                        ),
                                                                        type="text",
                                                                        className="email_detail__input",
                                                                        style={"display": "none"},
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                className="email_detail__field",
                                                                children=[
                                                                    Label(label_text="Data da Fatura"),
                                                                    dcc.DatePickerSingle(
                                                                        id="issue_date",
                                                                        date=data_recepcao,
                                                                        className="email_detail__input email_detail__date_picker",
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                className="email_detail__field",
                                                                children=[
                                                                    Label(label_text="Valor Total"),
                                                                    dcc.Input(
                                                                        id="total_amount",
                                                                        value=total_amount,
                                                                        type="number",
                                                                        className="email_detail__input",
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                className="email_detail__field",
                                                                children=[
                                                                    Label(label_text="Valor do IVA"),
                                                                    dcc.Input(
                                                                        id="vat_amount",
                                                                        value=vat_amount,
                                                                        type="number",
                                                                        className="email_detail__input",
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                className="email_detail__field",
                                                                children=[
                                                                    Label(label_text="Moeda"),
                                                                    dcc.Dropdown(
                                                                        id="currency",
                                                                        options=["EUR", "USD", "CVE"],
                                                                        value=currency,
                                                                        clearable=False,
                                                                        className="email_detail__input email_detail__dropdown",
                                                                        labels={"no_options_found": "..."},
                                                                    ),
                                                                ],
                                                            ),
                                                            html.Div(
                                                                className="email_detail__field",
                                                                children=[
                                                                    Label(label_text="Nota de Crédito"),
                                                                    Checkbox(id="credit_note", label_text="Sim"),
                                                                ],
                                                            ),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    html.Section(
                                        className="email_detail__content_right_section",
                                        children=[
                                            html.Iframe(
                                                id="document-pdf-viewer",
                                                src=f"/assets/pdf-viewer.html?file=/pdf/{ref_number}",
                                                style={
                                                    "width": "100%",
                                                    "height": "100%",
                                                    "border": "none",
                                                },
                                            )
                                        ],
                                    ),
                                ],
                            )
                        ],
                    ),
                    html.Section(
                        className="email_detail__bottom_section",
                        children=[
                            Button(
                                "Exportar",
                                id="email-detail-export-button",
                                icon="lucide:file-down",
                                variant="outline",
                            ),
                            Button("Guardar", id="save-button", icon="lucide:circle-check", variant="outline"),
                            Button("Enviar para SAP", id="send-sap-button", icon="lucide:send"),
                            html.P(id="email-detail-update-status", className="body-sm email_detail__status"),
                        ],
                    ),
                    RightDrawer(
                        drawer_id="email-detail-drawer",
                        title="Detalhes do Email",
                        children=[
                            Section(
                                title="Conteúdo do Email",
                                content=dcc.Loading(
                                    id="email-detail-drawer-loading",
                                    type="default",
                                    color="var(--primary-color-13)",
                                    children=html.Div(id="email-detail-drawer-email-content"),
                                ),
                                open=True,
                            ),
                        ],
                    ),
                ],
            ),
        ]
    )


def _build_sap_success_toast(has_next_document: bool):
    message = (
        "O Documento foi enviado para SAP, passando ao próximo..."
        if has_next_document
        else "O Documento foi enviado para SAP"
    )
    return html.Div(
        [
            html.Div(className="email_detail__modal_backdrop"),
            html.Div(
                className="email_detail__modal",
                children=[
                    html.Div(
                        className="email_detail__modal_icon",
                        children=[DashIconify(icon="lucide:check", width=28)],
                    ),
                    html.P(message, className="email_detail__modal_message"),
                ],
            ),
        ],
        className="email_detail__toast email_detail__toast--modal",
    )


def _build_sap_loading_toast():
    return html.Div(
        [
            html.Div(className="email_detail__modal_backdrop"),
            html.Div(
                className="email_detail__modal",
                children=[
                    html.P(
                        "A enviar documento para SAP...",
                        className="email_detail__modal_message",
                    ),
                ],
            ),
        ],
        className="email_detail__toast email_detail__toast--modal",
    )


@dash.callback(
    Output("email-detail-drawer-email-content", "children"),
    Input("email-detail-open-drawer", "n_clicks"),
    State("document_id_store", "data"),
    prevent_initial_call=True,
)
def load_email_drawer_content(_clicks, document_id):
    return _build_email_drawer_content(get_access_token(), document_id)


@dash.callback(
    Output("email-detail-update-status", "children", allow_duplicate=True),
    Output("email-detail-content", "children", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Output("email-detail-toast-host", "children", allow_duplicate=True),
    Output("email-detail-toast-timer", "disabled", allow_duplicate=True),
    Output("email-detail-toast-timer", "n_intervals", allow_duplicate=True),
    Input("save-button", "n_clicks"),
    Input("send-sap-button", "n_clicks"),
    State("document_id_store", "data"),
    State("document_fields_store", "data"),
    State("document_alerts_store", "data"),
    State("bu_name", "value"),
    State("bu-selection", "data"),
    State("document_number", "value"),
    State("po_list", "value"),
    State("supplier_name", "value"),
    State("supplier-selection", "data"),
    State("issue_date", "date"),
    State("total_amount", "value"),
    State("vat_amount", "value"),
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
    bu_id,
    document_number,
    po_list,
    supplier_name,
    supplier_id,
    issue_date,
    total_amount,
    vat_amount,
    currency,
    credit_note,
):
    if not (save_clicks or send_clicks):
        raise dash.exceptions.PreventUpdate

    triggered = callback_context.triggered
    if not triggered:
        raise dash.exceptions.PreventUpdate

    if not document_id:
        return "Documento invalido", no_update, no_update, no_update, no_update, no_update

    button_id = triggered[0]["prop_id"].split(".")[0]
    token = get_access_token()
    updated_fields = fields.copy() if isinstance(fields, dict) else {}
    bu_id, bu_vat = (bu_id or {}).get("id"), (bu_id or {}).get("vat")
    supplier_id, supplier_vat = (supplier_id or {}).get("id"), (supplier_id or {}).get("vat")

    def update_field(name: str, value: object) -> None:
        existing = updated_fields.get(name)
        updated_fields[name] = {**(existing or {}), "value": value}

    if bu_name is not None:
        update_field("bu_name", bu_name)
    if bu_id is not None:
        update_field("bu_id", bu_id)
    if bu_vat is not None:
        update_field("bu_vat", bu_vat)
    if document_number is not None:
        update_field("document_number", document_number)
    if po_list is not None:
        po_values = [value.strip() for value in po_list.replace("\n", ",").split(",") if value.strip()]
        updated_fields["po_list"] = [{"value": value, "confidence": 1.0} for value in po_values]
    if supplier_name is not None:
        update_field("supplier_name", supplier_name)
    if supplier_id is not None:
        update_field("supplier_id", supplier_id)
    if supplier_vat is not None:
        update_field("supplier_vat", supplier_vat)
    if issue_date is not None:
        update_field("issue_date", issue_date)
    if total_amount is not None:
        update_field("total_amount", total_amount)
    if vat_amount is not None:
        update_field("vat_amount", vat_amount)
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
        key.strip().casefold(): value for key, value in missing_field_alert_map.items()
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
        try:
            result = get_next_priority_document(token, document_id)
        except RequestException:
            result = {}
        next_document_id = result.get("next_document_id")
    elif button_id == "save-button":
        action = "Validação Manual"
        status = "Sob Revisão"

    try:
        alter_document_details(
            token,
            document_id,
            updated_alerts,
            updated_fields,
            action=action,
            status=status,
            last_modified_by="Mariana Dias",
        )
    except Exception as exc:
        return f"Erro ao guardar: {exc}", no_update, no_update, no_update, no_update, no_update

    if button_id == "send-sap-button":
        if next_document_id:
            return (
                "Documento enviado para SAP",
                no_update,
                f"/detalhe/{next_document_id}",
                _build_sap_success_toast(True),
                False,
                0,
            )
        return (
            "Documento enviado para SAP",
            no_update,
            no_update,
            _build_sap_success_toast(False),
            False,
            0,
        )
    return "Documento guardado", no_update, no_update, no_update, no_update, no_update


@dash.callback(
    Output("document_alerts_store", "data"),
    Output("email-detail-content", "children", allow_duplicate=True),
    Output("email-detail-update-status", "children"),
    Output("email-detail-toast-host", "children", allow_duplicate=True),
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
        return no_update, no_update, "Documento invalido", no_update

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
    token = get_access_token()

    try:
        alter_document_details(
            token,
            document_id,
            updated_alerts,
            fields if isinstance(fields, dict) else {},
            last_modified_by="Mariana Dias",
        )
    except Exception as exc:
        return no_update, no_update, f"Erro ao remover alerta: {exc}", no_update

    return updated_alerts, _build_email_detail(token, document_id), "Alerta removido", no_update


@dash.callback(
    Output("email-detail-toast-host", "children", allow_duplicate=True),
    Output("email-detail-toast-timer", "disabled", allow_duplicate=True),
    Input("email-detail-toast-timer", "n_intervals"),
    prevent_initial_call=True,
)
def clear_sap_success_toast(_n_intervals):
    if not _n_intervals:
        raise dash.exceptions.PreventUpdate
    return None, True
