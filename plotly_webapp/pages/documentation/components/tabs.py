import dash
from dash import html
from dash.dcc import Tab

from components.section.section import Section
from components.tabs.tabs import Tabs
from utils.base.grid_system.grid import Col

dash.register_page(
    __name__,
    path="/components/tabs",
    title="Tabs",
)


MediumTabs = Tabs(
    value="overview",
    size="medium",
    children=[
        Tab(
            label="Overview",
            value="overview",
            className="lucide--layout-dashboard",
            children=html.Section(
                "Your custom content here",
                style={
                    "padding": "1rem",
                    "background": "var(--negative-background)",
                    "border-radius": "4px",
                    "margin-top": "1rem",
                },
            ),
        ),
        Tab(
            label="Analytics",
            value="analytics",
            className="lucide--chart-no-axes-combined",
            children=html.Section(
                "Your custom content here",
                style={
                    "padding": "1rem",
                    "background": "var(--warning-background)",
                    "border-radius": "4px",
                    "margin-top": "1rem",
                },
            ),
        ),
        Tab(
            label="Insights",
            value="insights",
            className="lucide--lightbulb",
            children=html.Section(
                "Your custom content here",
                style={
                    "padding": "1rem",
                    "background": "var(--positive-background)",
                    "border-radius": "4px",
                    "margin-top": "1rem",
                },
            ),
        ),
        Tab(
            label="Reports",
            value="reports",
            className="lucide--file-text",
            disabled=True,
            children=html.Section(
                "This tab is disabled. Enable it by setting 'disabled' to False.",
                style={
                    "padding": "1rem",
                    "background": "var(--warning-background)",
                    "border-radius": "4px",
                    "margin-top": "1rem",
                },
            ),
        ),
    ],
)

SmallTabs = Tabs(
    id="tabs-small",
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
        html.H1("Tabs Component", className="heading-1"),
        html.H2("Medium", className="heading-2"),
        MediumTabs,
        html.H2("Small", className="heading-2"),
        SmallTabs,
        Section(
            title="Code Example",
            content=html.Pre(
                """
                    from components.tabs.tabs import Tabs
                    from dash.dcc import Tab

                    Tabs(
                        children=[
                            Tab(
                                label="Overview",
                                value="overview", 
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
                        value="overview",
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
