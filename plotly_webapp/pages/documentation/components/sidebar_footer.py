import dash
from dash import html

from components.sidebar_footer.sidebar_footer import SidebarFooter
from components.section.section import Section
from utils.base.grid_system.grid import Container

dash.register_page(
    __name__,
    path="/components/sidebar-footer",
    title="Sidebar Footer",
)

layout = html.Div([
        html.H1("Sidebar Footer Component", className="heading-1"),
        html.Br(),
        Container([
            SidebarFooter(
                username="Elisa Sampaio",
                avatar_size="s",
            ),
        ], fluid=True, style={'background': 'var(--accent-sidebar)'}),
        html.Br(),
        Section(
            title="Code Example",
            content=html.Pre(
                """
from components.sidebar_footer.sidebar_footer import SidebarFooter

SidebarFooter(
    username="Elisa Sampaio",
)

SidebarFooter(
    username="Elisa Sampaio",
    avatar_size="s",
    avatar_image="/assets/images/user-photo.jpg",
)
                """
            )
        )
    ])
