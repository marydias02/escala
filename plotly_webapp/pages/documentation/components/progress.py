import dash
from dash import html

from components.progress.progress import Progress

dash.register_page(
    __name__,
    path="/components/progress",
    title="Progress",
)

layout = html.Div(
    [
        html.Div(
            [
                Progress(value=0, id="progress-zero"),
                Progress(value=25, id="progress-25"),
                Progress(value=50, id="progress-50"),
                Progress(value=75, id="progress-75"),
                Progress(value=100, id="progress-100"),
            ],
            style={"display": "flex", "gap": "20px"},
        ),
        html.Div(
            [
                Progress(value=0, size="xs", id="progress-xs-zero"),
                Progress(value=25, size="xs", id="progress-xs-25"),
                Progress(value=50, size="xs", id="progress-xs-50"),
                Progress(value=75, size="xs", id="progress-xs-75"),
                Progress(value=100, size="xs", id="progress-xs-100"),
            ],
            style={"display": "flex", "gap": "25px", "marginTop": "20px"},
        ),
    ]
)
