from dash import MATCH, Input, Output, State, callback, no_update, html

from components.button.button import Button

@callback(
    Output({"type": "tutorial_card", "index": MATCH}, "className"),
    Input({"type": "tutorial_card", "index": MATCH, "subtype": "close"}, "n_clicks"),
    State({"type": "tutorial_card", "index": MATCH}, "className"),
    prevent_initial_call=True,
)
def dismiss_tutorial_card(n_clicks, current_class):
    if not n_clicks:
        return no_update

    base_class = current_class or "tutorial-card"
    if "tutorial-card--dismissed" in base_class:
        return base_class

    return f"{base_class} tutorial-card--dismissed"


def _build_tutorial_content(
    *,
    title: str,
    description: str | None,
    step_text: str | None,
    button_text: str | None,
    close_icon: str,
    card_id: dict,
) -> list:
    text_children = [html.H3(title, className="tutorial-card__title")]
    if description:
        text_children.append(html.P(description, className="tutorial-card__description"))

    footer_children = []
    if step_text:
        footer_children.append(html.Span(step_text, className="tutorial-card__steps"))
    if button_text:
        footer_children.append(
            Button(
                button_text,
                id={**card_id, "subtype": "next"},
                variant="primary",
                size="m",
            )
        )

    return [
        html.Div(
            className="tutorial-card__body",
            children=[
                html.Div(className="tutorial-card__body-content", children=text_children),
                Button(
                    icon=close_icon,
                    variant="ghost",
                    size="s",
                    id={**card_id, "subtype": "close"},
                    className="tutorial-card__close",
                    type="button",
                    **{"aria-label": "Close tutorial"},
                ),
            ],
        ),
        html.Div(className="tutorial-card__footer", children=footer_children),
    ]


@callback(
    Output({"type": "tutorial_card", "index": MATCH, "subtype": "state"}, "data"),
    Output({"type": "tutorial_card", "index": MATCH, "subtype": "content"}, "children"),
    Input({"type": "tutorial_card", "index": MATCH, "subtype": "next"}, "n_clicks"),
    State({"type": "tutorial_card", "index": MATCH, "subtype": "state"}, "data"),
    State({"type": "tutorial_card", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def next_tutorial_card_page(n_clicks, state_data, card_id):
    if not n_clicks or not state_data:
        return no_update, no_update

    cards = state_data.get("cards")
    if not cards:
        return no_update, no_update

    current_index = state_data.get("current_index", 0)
    if current_index >= len(cards) - 1:
        return no_update, no_update

    next_index = current_index + 1
    card_data = cards[next_index]
    total = len(cards)

    step_text = f"{next_index + 1} of {total}" if total > 1 else None
    button_text = "Next" if next_index < total - 1 else None
    close_icon = state_data.get("close_icon", "lucide:x")

    new_state = {
        **state_data,
        "current_index": next_index,
    }

    content = _build_tutorial_content(
        title=card_data["title"],
        description=card_data.get("description"),
        step_text=step_text,
        button_text=button_text,
        close_icon=close_icon,
        card_id=card_id,
    )

    return new_state, content
