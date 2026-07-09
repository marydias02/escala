from dash import html

from components.button.button import Button


def action_bar(grid_id: str) -> html.Aside:
    return html.Aside(
        [
            html.Span("0", id=f"{grid_id}-selection-count", className="action-bar__selection-count body-xs"),
            html.Span("selected", className="body-sm"),
            Button(
                "Disabled",
                icon="lucide:x",
                variant="outline",
                className="action-bar__btn",
                disabled=True,
            ),
            Button(
                "Placeholder",
                icon="lucide:circle-check-big",
                variant="outline",
                className="action-bar__btn",
            ),
            Button(
                "Delete",
                icon="lucide:trash-2",
                variant="outline",
                destructive=True,
                className="action-bar__btn",
                id=f"{grid_id}-delete-btn",
            ),
            Button(
                icon="lucide:x",
                variant="ghost",
                className="action-bar__btn",
                id=f"{grid_id}-close-selection",
            ),
        ],
        id=f"{grid_id}-action-bar",
        className="action-bar hidden",
    )