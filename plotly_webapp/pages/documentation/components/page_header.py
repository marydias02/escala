import dash
from dash import html

from components.button.button import Button
from components.page_header.page_header import PageHeader

dash.register_page(
    __name__,
    path="/components/page-header",
    title="Page Header",
)

layout = html.Div(
    [
        html.Div(
            [
                html.H1("This is a basic Page Header", className="heading-2"),
                PageHeader(title="Dashboard"),
            ],
            style={"display": "flex", "flexDirection": "column", "gap": "12px"},
        ),
        html.Div(
            [
                html.H1("This is a Page Header with subtitle", className="heading-2"),
                PageHeader(title="Sales Overview", subtitle="Last 30 days"),
            ],
            style={"display": "flex", "flexDirection": "column", "gap": "12px"},
        ),
        html.Div(
            [
                html.H1("This is a Page Header with icon", className="heading-2"),
                PageHeader(title="Notifications", icon="lucide:bell"),
            ],
            style={"display": "flex", "flexDirection": "column", "gap": "12px"},
        ),
        html.Div(
            [
                html.H1("This is a Page Header with subtitle and icon", className="heading-2"),
                PageHeader(
                    title="Revenue",
                    subtitle="Quarterly performance",
                    icon="lucide:chart-line",
                ),
            ],
            style={"display": "flex", "flexDirection": "column", "gap": "12px"},
        ),
    ],
    style={
        "display": "flex",
        "flexDirection": "column",
        "gap": "36px",
        "padding": "0px 16px",
    },
)
