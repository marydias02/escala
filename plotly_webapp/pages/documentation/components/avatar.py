import dash
from dash import html

from components.avatar.avatar import Avatar
from components.section.section import Section
from utils.base.grid_system.grid import Col, Container, Row

dash.register_page(
    __name__,
    path="/components/avatar",
    title="User Avatar",
)

layout = html.Div([
    html.H1("User Avatar Component", className="heading-1"),
    html.Br(),
    html.P("Variants: Avatar can display a user image when available. If no image is provided, the user's initials will be used and a background color will be assigned. When no username is provided, a generic user silhouette is used instead."),
    html.Br(),
    html.P("Sizes: s, m"),
    html.Br(),
    Container([
        Row([
            Col([
                Avatar(
                    username="Carolina Melim",
                    size="m",
                    img_src="/assets/images/user-photo.jpg",
                ),
            ], xs=12, md=2, lg=2),
            Col([
                Avatar(
                    username="Carolina Melim",
                    size="m",
                ),
            ], xs=12, md=2, lg=2),
            Col([
                Avatar(
                    username="",
                    size="m",
                ),
            ], xs=12, md=2, lg=2),
        ]),
        html.Br(),
        Row([
            Col([
                Avatar(
                    username="Carolina Melim",
                    size="s",
                    img_src="/assets/images/user-photo.jpg",
                ),
            ], xs=12, md=2, lg=2),
            Col([
                Avatar(
                    username="Carolina Melim",
                    size="s",
                ),
            ], xs=12, md=2, lg=2),
            Col([
                Avatar(
                    username="",
                    size="s",
                ),
            ], xs=12, md=2, lg=2),
        ]),
    ]),
    html.Br(),
    Section(
        title="Code Example",
        content=html.Pre(
            """
from components.avatar.avatar import Avatar

Avatar(
    username="Carolina Melim",
    size="s",
)

Avatar(
    username="Carolina Melim",
    size="s",
    img_src="/assets/images/user-photo.jpg",
),
            """
        ),
    ),    
])