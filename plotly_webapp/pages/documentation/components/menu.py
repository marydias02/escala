import dash
from dash import html, dcc

from components.menu.menu import Menu
from components.section.section import Section
from utils.base.grid_system.grid import Col, Container

dash.register_page(
    __name__,
    path="/components/menu",
    title="Menu",
)

layout = html.Div(
    [
        html.H1("Menu Component", className="heading-1"),
        html.Br(),
        html.H2("Menu without subpages", className="heading-2"),
        html.Br(),
        Container([
            Menu(
                title="Menu without subpages",
                href="/components/menu",
            ),
            Menu(
                title="Menu without subpages",
                icon="lucide:square-asterisk",
                href="/components/menu",
            ),
        ], fluid=True, style={'background': 'var(--accent-sidebar)', 'padding-inline': 'var(--spacing-6)'}),
        html.Br(),
        html.H2("Menu with subpages", className="heading-2"),
        html.Br(),
        Container([
            Menu(
                title="Menu with subpages",
                children=[
                    dcc.Link("Item", href="/components/menu"),
                    dcc.Link("Extremely Long Item Here On the Nav", href="/components/menu"),
                ]
            ),
            Menu(
                title="Menu with subpages",
                icon="lucide:square-asterisk",
                children=[
                    dcc.Link("Item", href="/components/menu"),
                    dcc.Link("Extremely Long Item Here On the Nav", href="/components/menu"),
                ]
            ),
        ], fluid=True, style={'background': 'var(--accent-sidebar)', 'padding-inline': 'var(--spacing-6)'}),
        html.Br(),
        Section(
            title="Code Examples",
            content=html.Pre(
                """
# Menu without subpages
from components.menu.menu import Menu

Menu(
    title="Menu without subpages",
    href="/components/menu",
),
Menu(
    title="Menu without subpages",
    icon="lucide:square-asterisk",
    href="/components/menu",
),

# Menu with subpages
from components.menu.menu import Menu

Menu(
    title="Menu with subpages",
    children=[
        dcc.Link("Item", href="/components/menu"),
        dcc.Link("Extremely Long Item Here On the Nav", href="/components/menu"),
    ]
),
Menu(
    title="Menu with subpages",
    icon="lucide:square-asterisk",
    children=[
        dcc.Link("Item", href="/components/menu"),
        dcc.Link("Extremely Long Item Here On the Nav", href="/components/menu"),
    ]
),
                """,
                className="banner banner--neutral",
            )
        )
    ]
)