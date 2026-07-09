import dash
from dash import html
from dash.dcc import Tab

from components.segmented_control.segmented_control import (
    SegmentedControl,
)
from components.section.section import Section
from utils.base.grid_system.grid import Col

dash.register_page(
    __name__,
    path="/components/segmented-control",
    title="Segmented Control",
)


MediumSegmentedControl = SegmentedControl(
    value="dashboard",
    size="medium",
    children=[
        Tab(
            label="Dashboard",
            value="dashboard",
            className="lucide--layout-dashboard",
            children=html.Section(
                "Your custom content here",
                style={"padding": "1rem", "background": "var(--warning-background)", "border-radius": "4px", "margin-top": "1rem"},
            ),
        ),
        Tab(
            label="Analytics",
            value="analytics",
            className="lucide--chart-no-axes-combined",
            children=html.Section(
                "Analytics content here",
                style={"padding": "1rem", "background": "var(--positive-background)", "border-radius": "4px", "margin-top": "1rem"},
            ),
        ),
        Tab(
            label="About",
            value="about",
            className="lucide--file-text",
            children=html.Section(
                "About content here",
                style={
                    "padding": "1rem",
                    "background": "var(--negative-background)",
                    "border-radius": "4px",
                    "margin-top": "1rem",
                },
            ),
        ),
    ],
)

SmallSegmentedControl = SegmentedControl(
    id="segmented-tabs-small",
    value="data",
    size="small",
    children=[
        Tab(
            label="Data",
            value="data",
            className="lucide--table-2",
            children=html.Section(
                [
                    html.Br(),
                    html.P("This is the Data tab content. It shows data-related information."),
                ]
            ),
        ),
        Tab(
            label="Insights",
            value="insights",
            className="lucide--lightbulb",
            children=html.Section(
                [
                    html.Br(),
                    html.P("This is the Insights tab content. It provides analytical insights."),
                ]
            ),
        ),
    ],
)

layout = Col(
    [
        html.H1("Segmented Control Component", className="heading-1"),
        html.H2("Medium", className="heading-2"),
        MediumSegmentedControl,
        html.H2("Small", className="heading-2"),
        SmallSegmentedControl,
        Section(
            title="Code Example",
            content=html.Pre(
                """
from components.segmented_control.segmented_control import SegmentedControl
from dash.dcc import Tab

SegmentedControl(
    children=[
        Tab(
            label="Dashboard",
            value="dashboard", 
            className="lucide--layout-dashboard",
            children=html.Div("Your custom content here")
        ),
        Tab(
            label="Analytics",
            value="analytics",
            className="lucide--chart-line",
            disabled=True
        )
    ],
    value="dashboard",
    size="medium"
)
        """,
                className="banner banner--neutral",
                style={"width": "100%", "box-sizing": "border-box"},
            ),
        ),
    ],
    style={"display": "grid", "gap": "2rem"},
)
