# components/progress/progress.py
from dash import html


def Progress(value: int = 0, size: str = "sm", id: str = "progress"):
    size_class = f"progress-{size}"

    return html.Div(
        [
            html.Span(f"{value}%", id=f"{id}", className=f"body-{size}"),
            html.Div(
                id=f"{id}",
                className=f"progress-ring {size_class}",
                style={
                    "--value": str(value),
                },
            ),
        ],
        id=id,
        style={"display": "flex", "alignItems": "center", "gap": "8px"},
    )
