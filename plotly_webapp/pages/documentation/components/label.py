import dash
from dash import html

from components.label.label import Label
from utils.base.grid_system.grid import Container, Row, Col


dash.register_page(
    __name__,
    path="/components/label",
    title="Label",
)

layout = html.Div(
    [
        html.H1("Label Page", className="heading-1"),
        html.Br(),
        html.Br(),
        html.H2("Default Label - with or without icon", className="heading-2"),
        html.Br(),
        Container(
            [
                Row(
                    [
                        Col([Label(label_text="Label", show_icon=True)], style={"flex": "0 0 auto", "marginBottom": "0"}),
                        Col([Label(label_text="Label")], style={"flex": "0 0 auto", "marginBottom": "0"}),
                    ],
                    style={"gap": "var(--spacing-4)"},
                ),
            ],
            fluid=True,
        ),
        html.Br(),
    ]
)
