import dash
from dash import html
from dash_iconify import DashIconify

from components.banner.banner import Banner, TableBanner
from components.section.section import Section
from utils.base.grid_system.grid import Col, Container

dash.register_page(
    __name__,
    path="/components/banner",
    title="Banner",
)

layout = Container(
    Col(
        [
            html.H1("Banner Component", className="heading-1"),
            html.Br(),
            html.H2("Table Banners", className="heading-2"),
            TableBanner(message="This is a table-level alert message.", icon="lucide:triangle-alert"),
            TableBanner(
                message="This is a table-level positive banner.",
                variant="positive",
                icon="lucide:check",
            ),
            TableBanner(
                message="This is a table-level dark banner.",
                variant="dark",
            ),
            html.Br(),
            html.H2("Full Banners", className="heading-2"),
            Banner(
                header="Some message here",
                description="This is a description of the alert message.",
                variant="neutral",
                buttons=[{"label": "Primary", "id": "primary-btn"}, {"label": "Secondary", "id": "secondary-btn"}],
                id={"type": "banner", "index": "banner-1"},
            ),
            Banner(
                header="Some message here",
                description="This is a description of the alert message.",
                variant="dark",
                icon="lucide:home",
                buttons=[{"label": "Primary", "id": "primary-btn"}],
            ),
            Banner(
                header="Some message here",
                description="This is a description of the alert message.",
                variant="positive",
                icon="lucide:check",
                buttons=[{"label": "Primary", "id": "primary-btn"}, {"label": "Secondary", "id": "secondary-btn"}],
                dismissable=False,
            ),
            Banner(
                header="Some message here",
                variant="warning",
                icon="lucide:triangle-alert",
            ),
            Banner(
                header="Some message here",
                variant="warning",
            ),
            Banner(
                header="Some message here",
                variant="positive",
                dismissable=False,
            ),
            Banner(
                header="Some message here",
                description="This is a description of the alert message.",
                variant="negative",
                icon="lucide:trash",
                dismissable=False,
            ),
            Section(
                title="Code Examples",
                content=html.Pre(
                    """
# Table Banner
from components.banner.banner import TableBanner

TableBanner(
    message="This is a table-level alert message.",
    icon="lucide:triangle-alert",
    variant="warning"  # optional: neutral, positive, warning, negative, dark
)

# Full Banner
from components.banner.banner import Banner

Banner(
    header="Some message here",
    description="This is a description of the alert message.",
    variant="positive",
    icon="lucide:check",
    buttons=[
        {"label": "Primary", "id": "primary-btn"}, 
        {"label": "Secondary", "id": "secondary-btn"}
    ],
    dismissable=True,  # default: True
    id="banner-1"
)
                    """,
                    className="banner banner--neutral",
                    style={"width": "100%", "box-sizing": "border-box"},
                ),
            ),
        ],
        style={"display": "flex", "flex-direction": "column", "gap": "var(--spacing-12)"},
    )
)
