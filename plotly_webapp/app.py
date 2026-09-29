import requests
from dash import Dash, dcc, html, page_container
from dash.dependencies import Input, Output, State
from dash_iconify import DashIconify
from flask import Response, redirect, session

import config
from auth.msal_client import get_access_token
from auth.routes import register_auth
from callbacks.layout import update_sidebar_logic
from components.breadcrumb.breadcrumb import Breadcrumb
from components.button.button import Button
from components.footer.footer import Footer
from components.menu.menu import Menu
from components.sidebar_footer.sidebar_footer import SidebarFooter

AG_GRID_THEME_STYLESHEETS = [
    "https://unpkg.com/ag-grid-community@31.3.1/styles/ag-grid.css",
    "https://unpkg.com/ag-grid-community@31.3.1/styles/ag-theme-quartz.css",
]


external_stylesheets = [
    "./assets/css/components/table.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",
    *AG_GRID_THEME_STYLESHEETS,
]

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=external_stylesheets,
    title="ESCALA",
    update_title="ESCALA - Updating ...",
    suppress_callback_exceptions=True,
)

# `server` is what gunicorn is pointed at, and what the auth layer attaches to.
server = app.server
register_auth(server)


@server.before_request
def redirect_incomplete_email_detail_url():
    """Redirect the detail base path to the app home page.

    ``/detalhe`` is only valid when it includes a document reference.  This
    server-side guard handles direct browser requests without assuming a
    particular host or port.
    """
    from flask import request

    if request.path.rstrip("/") == "/detalhe":
        return redirect("/")

    return None


def serve_layout():
    """Built per page load rather than once at import, so the sidebar can carry
    the signed-in user's own name instead of a constant."""
    user = session.get("user") or {}

    return html.Div(
        [
            dcc.Store(id="sidebar--state", data={"open": False}),
            # Roles are exposed for controls that need to hide themselves. Hiding is
            # presentation only — enforcement is the API's job and a hidden button is
            # not a permission. Nothing is gated today: with the current endpoints
            # `admin` and `user` differ only in POST /air/run and /air/template,
            # which this app never calls.
            dcc.Store(id="user--roles", data=user.get("roles", [])),
            dcc.Store(id="auth--logout"),
            # A 302 is useless to an in-flight Dash callback, so the guard answers
            # those with JSON and this poll does the navigating when a session ends.
            # Sixty seconds: often enough that nobody sits on a dead page, rare
            # enough that four workers are not reading the database per user per second.
            dcc.Interval(id="auth--heartbeat", interval=60_000),
            html.Div(id="email-detail-toast-host", className="email_detail__toast_host"),
            dcc.Interval(
                id="email-detail-toast-timer",
                interval=3000,
                disabled=True,
                n_intervals=0,
                max_intervals=1,
            ),
            dcc.Interval(
                id="email-detail-save-status-timer",
                interval=10_000,
                disabled=True,
                n_intervals=0,
                max_intervals=1,
            ),
            html.Aside(
                className="app__sidebar",
                id="app__sidebar",
                children=[
                    html.Div(
                        className="sidebar__header",
                        children=[
                            html.Img(
                                src="/assets/images/logo-2.svg",
                                alt="Logo",
                            ),
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
                            Menu(title="Extração", href="/", icon="lucide:scan-text"),
                            Menu(title="Validação", href="/validation", icon="lucide:badge-check"),
                            Menu(title="Dashboard", href="/harbor", icon="lucide:layout-dashboard"),
                            Menu(title="Ingestão de Extratos", href="/ingestion", icon="lucide:file-up"),
                            # Menu(title="Template", href="/home", icon="lucide:file-text"),
                            # Menu(title="Grid", href="/grid"),
                            # Menu(title="Segmented Control", href="/components/segmented-control"),
                            # Menu(title="Banner", href="/components/banner"),
                            # Menu(title="Tabs", href="/components/tabs"),
                            # Menu(title="Button", href="/components/button"),
                            # Menu(title="Table", href="/components/table"),
                            # Menu(title="Section", href="/components/section"),
                            # Menu(title="Tag", href="/components/tag"),
                            # Menu(title="Progress", href="/components/progress"),
                            # Menu(title="Label", href="/components/label"),
                            # Menu(title="Checkbox", href="/components/checkbox"),
                            # Menu(title="Indicator Card", href="/components/cards/indicator-card"),
                            # Menu(title="Page Card", href="/components/cards/page-card"),
                            # Menu(title="Tutorial Card", href="/components/cards/tutorial-card"),
                            # Menu(title="Workflow Card", href="/components/cards/workflow-card"),
                            # Menu(title="Menu", href="/components/menu", icon="lucide:square-asterisk"),
                            # # Menu(
                            # #     title="Menu with subpages",
                            # #     children=[
                            # #         dcc.Link("Item", href="/components/menu"),
                            # #         dcc.Link("Extremely Long Item Here On the Nav", href="/components/menu"),
                            # #     ],
                            # # ),
                            # Menu(title="Sidebar Footer", href="/components/sidebar-footer"),
                            # # Menu(title="User Avatar", href="/components/avatar"),
                        ],
                    ),
                    html.Div(
                        className="sidebar__footer-wrapper",
                        children=[
                            SidebarFooter(
                                username=user.get("name") or "",
                                avatar_size="s",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="app__main-content",
                children=[
                    html.Header(
                        className="app__header",
                        children=[
                            Button(
                                "  ",
                                variant="ghost",
                                id="app__header-menuIcon",
                                className="hide",
                            ),
                            Breadcrumb(),
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


app.layout = serve_layout


app.clientside_callback(
    """
    function (pathname) {
        if (pathname && pathname.replace(/\\/$/, '') === '/detalhe') {
            return '/';
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("url", "href", allow_duplicate=True),
    Input("url", "pathname"),
    prevent_initial_call=True,
)


""" CALLBACKS """


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


# The session ends server-side; this poll is what turns that into a sign-in
# prompt rather than a page that quietly stops updating.
app.clientside_callback(
    """
    function (n_intervals) {
        fetch('/auth/status', {credentials: 'same-origin'})
            .then(function (r) { return r.json(); })
            .then(function (d) { if (!d.authenticated) { window.location.href = '/login'; } })
            .catch(function () {});
        return window.dash_clientside.no_update;
    }
    """,
    Output("auth--heartbeat", "disabled"),
    Input("auth--heartbeat", "n_intervals"),
    prevent_initial_call=True,
)


app.clientside_callback(
    """
    function (n_clicks) {
        if (n_clicks) { window.location.href = '/logout'; }
        return window.dash_clientside.no_update;
    }
    """,
    Output("auth--logout", "data"),
    Input("sidebar-user-logout", "n_clicks"),
    prevent_initial_call=True,
)


@server.route("/pdf/<document_id>")
def proxy_document_pdf(document_id):
    """Fetch a document's PDF from the FastAPI backend and stream it back.
    Kept server-side rather than pointed at directly: the backend requires an
    Authorization header, which a browser <iframe src> request can't attach.
    The iframe request is same-origin, so it carries the session cookie, passes
    the guard, and this forwards that user's own token.
    """
    resp = requests.get(
        f"{config.BACKEND_BASE_URL}/extraction/documents/{document_id}/pdf",
        headers={"Authorization": f"Bearer {get_access_token()}"},
        timeout=10,
    )
    if resp.status_code == 404:
        return Response(status=404)
    resp.raise_for_status()
    return Response(resp.content, mimetype="application/pdf")


if __name__ == "__main__":
    app.run(debug=True)
