"""Standalone Harbor Dash app.

Run from the plotly_webapp folder with:
    .\.venv\Scripts\python.exe harbor_app.py

This app uses port 8051 so it can run alongside the main app on port 8050.
"""

import dash
from dash import Dash, dcc, html, page_container
from dash.dependencies import Input, Output, State
from dash_iconify import DashIconify
from dash.exceptions import PreventUpdate

from callbacks.layout import update_sidebar_logic
from components.button.button import Button
from components.footer.footer import Footer
from components.menu.menu import Menu
from components.sidebar_footer.sidebar_footer import SidebarFooter
app = Dash(
    __name__,
    title="Dashboard",
    use_pages=True,
    pages_folder="",
    suppress_callback_exceptions=True,
)

# Explicitly register only Harbor's pages. The original app's pages remain
# available to its own app, but are not part of this standalone application.
from pages import harbor_dashboard, ingestion, reconciliation  # noqa: E402,F401

dash.page_registry["pages.harbor_dashboard"]["layout"] = harbor_dashboard.layout
dash.page_registry["pages.ingestion"]["layout"] = ingestion.layout
dash.page_registry["pages.reconciliation"]["layout"] = reconciliation.layout


def dashboard_breadcrumb():
    """Breadcrumb shell whose items are populated from the current pathname."""
    return html.Nav(
        html.Ul(
            id="breadcrumb",
            className="breadcrumb",
        ),
        className="breadcrumb body-sm",
    )



def serve_layout():
    return html.Div(
        [
            html.Title("Dashboard", id="document-title"),
            dcc.Store(id="sidebar--state", data={"open": False}),
            html.Aside(
                className="app__sidebar",
                id="app__sidebar",
                children=[
                    html.Div(
                        className="sidebar__header",
                        children=[
                            html.Img(src="/assets/images/logo-2.svg", alt="Logo"),
                            html.Button(
                                DashIconify(
                                    icon="lucide:chevrons-left",
                                    className="sidebar__header-menu-icon",
                                ),
                                id="toggle-btn",
                                className="sidebar__header-menu-btn",
                            ),
                        ],
                    ),
                    html.Div(
                        className="sidebar__menu",
                        children=[
                            Menu(title="Dashboard", href="/", icon="lucide:layout-dashboard"),
                            Menu(title="Ingestão de Extratos", href="/ingestion", icon="lucide:file-up"),
                        ],
                    ),
                    html.Div(
                        className="sidebar__footer-wrapper",
                        children=[SidebarFooter(username="", avatar_size="s")],
                    ),
                ],
            ),
            html.Div(
                className="app__main-content",
                children=[
                    html.Header(
                        className="app__header",
                        children=[
                            Button("  ", variant="ghost", id="app__header-menuIcon", className="hide"),
                            dashboard_breadcrumb(),
                            html.Section(
                                className="app__header-actions",
                                children=[
                                    Button(icon="lucide:message-square-text", variant="ghost", id="comment-button"),
                                    Button(icon="lucide:star", variant="ghost", id="star-button"),
                                    Button(icon="lucide:ellipsis-vertical", variant="ghost", id="ellipsis-button"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="app__main",
                        children=[
                            dcc.Location(id="url", refresh="callback-nav"),
                            page_container,
                        ],
                    ),
                    Footer(client_name="Grupo Sousa ® 2026"),
                ],
            ),
        ],
        className="app",
        **{"data-theme": "custom-theme"},
    )


# Build the layout once because TableV1 registers its internal table callbacks
# while the page is being constructed. Rebuilding it on every layout request
# would register the same callback more than once.
app.layout = serve_layout()
# The Ingestion page is loaded dynamically, but its TableV1 callbacks are
# registered at import time. Include the page in Dash's validation layout so
# those callback component IDs are known before the user navigates to it.
app.validation_layout = html.Div(
    [app.layout, harbor_dashboard.layout, ingestion.layout, reconciliation.layout]
)


@app.callback(
    Output("app__sidebar", "className"),
    Output("app__header-menuIcon", "className"),
    Output("sidebar--state", "data"),
    Input("toggle-btn", "n_clicks"),
    Input("app__header-menuIcon", "n_clicks"),
    State("sidebar--state", "data"),
)
def update_sidebar(toggle_clicks, menu_clicks, current_state):
    return update_sidebar_logic(toggle_clicks, menu_clicks, current_state)


@app.callback(
    Output("url", "pathname"),
    Input("harbor-transactions-table", "cellClicked"),
    prevent_initial_call=True,
)
def open_reconciliation(cell_clicked):
    if not cell_clicked or cell_clicked.get("colId") == "scope":
        raise PreventUpdate
    return "/reconciliation"


@app.callback(
    Output("breadcrumb", "children"),
    Output("document-title", "children"),
    Input("url", "pathname"),
)
def update_navigation_labels(pathname):
    dashboard_link = dcc.Link(
        [
            DashIconify(icon="lucide:layout-dashboard"),
            html.Span("Dashboard", className="breadcrumb__text"),
        ],
        href="/",
        className="breadcrumb__link breadcrumb__link--home",
    )

    if pathname == "/ingestion":
        return [
            html.Li([dashboard_link, DashIconify(icon="lucide:chevron-right", className="breadcrumb__arrow")]),
            html.Li(
                html.Span("Ingestão de Extratos", className="breadcrumb__text"),
                className="breadcrumb__active",
            ),
        ], "Ingestão de Extratos"

    if pathname == "/reconciliation":
        return [
            html.Li([dashboard_link, DashIconify(icon="lucide:chevron-right", className="breadcrumb__arrow")]),
            html.Li(
                html.Span("Reconciliação de Pagamentos", className="breadcrumb__text"),
                className="breadcrumb__active",
            ),
        ], "Reconciliação de Pagamentos"

    return [html.Li(html.Span("Dashboard", className="breadcrumb__text"), className="breadcrumb__active")], "Dashboard"




if __name__ == "__main__":
    app.run(debug=True, port=8051)
