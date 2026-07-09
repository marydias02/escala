from dash import Dash, dcc, html, page_container
from dash.dependencies import Input, Output, State
from dash_iconify import DashIconify

from callbacks.layout import update_sidebar_logic
import callbacks.documentation.documentation
from components.breadcrumb.breadcrumb import Breadcrumb
from components.button.button import Button
from components.menu.menu import Menu
from components.sidebar_footer.sidebar_footer import SidebarFooter
from components.footer.footer import Footer
from components.select.select import Select


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
    title="Dash Template",
    update_title="Dash Template - Updating ...",
)

app.layout = html.Div(
    [
        dcc.Store(id="sidebar--state", data={"open": True}),
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
                    className="sidebar__dropdown",
                    children=[
                        Select(select_options=['Workspace A', 'Workspace B', 'Workspace C'],
                               placeholder="Select Workspace",
                               select_color_mode="custom_light",
                               select_background_color="var(--accent-sidebar)"
                               )
                    ],
                ),
                html.Div(
                    className="sidebar__menu",
                    children=[
                        Menu(title="Homepage", href="/", icon="lucide:home"),
                        Menu(title="Grid", href="/grid"),
                        Menu(title="Segmented Control", href="/components/segmented-control"),
                        Menu(title="Banner", href="/components/banner"),
                        Menu(title="Tabs", href="/components/tabs"),
                        Menu(title="Button", href="/components/button"),
                        Menu(title="Table", href="/components/table"),
                        Menu(title="Section", href="/components/section"),
                        Menu(title="Tag", href="/components/tag"),
                        Menu(title="Progress", href="/components/progress"),
                        Menu(title="Label", href="/components/label"),
                        Menu(title="Checkbox", href="/components/checkbox"),
                        Menu(title="Indicator Card", href="/components/cards/indicator-card"),
                        Menu(title="Page Card", href="/components/cards/page-card"),
                        Menu(title="Tutorial Card", href="/components/cards/tutorial-card"),
                        Menu(title="Workflow Card", href="/components/cards/workflow-card"),
                        Menu(title="Menu", href="/components/menu", icon="lucide:square-asterisk"),
                        Menu(
                            title="Menu with subpages",
                            children=[
                                dcc.Link("Item", href="/components/menu"),
                                dcc.Link("Extremely Long Item Here On the Nav", href="/components/menu"),
                            ],
                        ),
                        Menu(title="Sidebar Footer", href="/components/sidebar-footer"),
                        Menu(title="User Avatar", href="/components/avatar"),
                    ],
                ),
                html.Div(
                    className="sidebar__footer-wrapper",
                    children=[
                        SidebarFooter(
                            username="Elisa Sampaio",
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
                        dcc.Location(id="url", refresh=False),
                        page_container,
                    ],
                ),
                Footer(client_name="DesignSystem ® 2026")
            ],
        ),
    ],
    className="app",
    **{"data-theme": "custom-theme"},
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


if __name__ == "__main__":
    app.run(debug=True)
