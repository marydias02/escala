from typing import Optional

import dash
from dash import Input, Output, State, callback_context, html
from dash_iconify import DashIconify

from assets.api_calls.extraction_api import get_document_email
from components.section.section import Section


def RightDrawer(
    *,
    drawer_id: str,
    title: str,
    children: Optional[list] = None,
) -> html.Aside:
    children = children or [
        Section(
            title="Resumo da Interação",
            content=html.Div(id=f"{drawer_id}-interaction-content"),
        ),
        Section(
            title="Conteúdo do Email",
            content=html.Div(id=f"{drawer_id}-email-content"),
        ),
    ]
    base_style = {
        "position": "fixed",
        "top": "0",
        "right": "0",
        "height": "100vh",
        "width": "360px",
        "zIndex": "30",
        "overflowY": "auto",
        "overflowX": "hidden",
    }
    return html.Aside(
        id=drawer_id,
        className="right-sidebar sidebar--collapsed",
        style=base_style,
        children=[
            html.Div(
                className="right-sidebar__header",
                children=[
                    html.Button(
                        DashIconify(
                            icon="lucide:chevrons-right",
                            className="right-sidebar__close-icon",
                        ),
                        id=f"{drawer_id}-close",
                        type="button",
                        className="right-sidebar__close",
                    ),
                    html.H3(title, className="right-sidebar__title"),
                ],
            ),
            html.Div(className="right-sidebar__body", children=children),
        ],
    )


def register_right_drawer_callbacks(
    drawer_id: str,
    toggle_button_id: str,
    document_id_store_id: Optional[str] = None,
) -> None:
    close_button_id = f"{drawer_id}-close"

    @dash.callback(
        Output(drawer_id, "className"),
        Input(toggle_button_id, "n_clicks"),
        Input(close_button_id, "n_clicks"),
        State(drawer_id, "className"),
        prevent_initial_call=True,
    )
    def toggle_drawer(toggle_clicks, close_clicks, current_class_name):
        triggered = callback_context.triggered
        if not triggered:
            raise dash.exceptions.PreventUpdate

        trigger_id = triggered[0]["prop_id"].split(".")[0]
        class_name = current_class_name or "right-sidebar sidebar--collapsed"

        if trigger_id == toggle_button_id:
            if "sidebar--collapsed" in class_name:
                return class_name.replace("sidebar--collapsed", "").strip()
            return f"{class_name} sidebar--collapsed".strip()

        return "right-sidebar sidebar--collapsed"

    if document_id_store_id is None:
        return

    @dash.callback(
        Output(f"{drawer_id}-email-content", "children"),
        Input(document_id_store_id, "data"),
    )
    def load_email_content(document_id):
        if not document_id:
            return "Sem documento selecionado."

        try:
            email = get_document_email(str(document_id))
        except Exception:
            return "Não foi possível carregar o email."

        sender = email.get("sender_email") or "N/D"
        subject = email.get("email_subject") or "N/D"
        received = email.get("reception_date") or "N/D"

        return html.Div(
            [
                html.Div([html.Strong("Remetente: "), html.Span(sender)]),
                html.Div([html.Strong("Assunto: "), html.Span(subject)]),
                html.Div([html.Strong("Recebido em: "), html.Span(str(received))]),
            ]
        )
