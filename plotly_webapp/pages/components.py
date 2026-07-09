import dash
from dash import html

from components.page_header.page_header import PageHeader
from components.standard_card.standard_card import StandardCard
from utils.base.grid_system.grid import Col, Container, Row

app = dash.Dash(__name__)

dash.register_page(
    __name__,
    path="/components",
    title="Components",
)


layout = html.Div(
    [
        html.Div(
            className="homepage__container",
            children=[
                PageHeader(
                    icon="lucide:puzzle",
                    title="Components",
                    subtitle="A system behind every LTP experience",
                ),
                Container(
                    [
                        Row(
                            [
                                Col(
                                    [
                                        StandardCard(
                                            text="Avatar",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/avatar",
                                            button_id="avatar-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Banner",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/banner",
                                            button_id="banner-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Button",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/button",
                                            button_id="button-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Indicator Card",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/indicator-card",
                                            button_id="indicator-card-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Menu",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/menu",
                                            button_id="menu-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Progress",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/progress",
                                            button_id="progress-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Section",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/section",
                                            button_id="section-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Segmented Control",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/segmented-control",
                                            button_id="segmented-control-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Table",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/table",
                                            button_id="table-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Tabs",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/tabs",
                                            button_id="tabs-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                                Col(
                                    [
                                        StandardCard(
                                            text="Tag",
                                            icon="link-2",
                                            description="Reusable button with consistent styling for triggering user actions",
                                            button_name="View more",
                                            button_href="/components/tag",
                                            button_id="tag-component",
                                        ),
                                    ],
                                    xs=12,
                                    md=6,
                                    lg=4,
                                ),
                            ]
                        ),
                    ]
                ),
            ],
        ),
    ]
)
