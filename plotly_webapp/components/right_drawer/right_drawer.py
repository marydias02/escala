from typing import Optional

import dash
from dash import Input, Output, State, callback_context, html
from dash_iconify import DashIconify


def RightDrawer(
    *,
    drawer_id: str,
    title: str,
    children: Optional[list] = None,
) -> html.Aside:
    children = children or []
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
