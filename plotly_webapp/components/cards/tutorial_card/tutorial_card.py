from typing import Optional, Sequence, Dict, Any, Union
from uuid import uuid4

from dash import dcc, html

from components.button.button import Button
from callbacks.tutorial_card.tutorial_card import dismiss_tutorial_card, next_tutorial_card_page  # noqa: F401


def _build_tutorial_content(
    *,
    title: str,
    description: Optional[str] = None,
    step_text: Optional[str] = None,
    button_text: Optional[str] = None,
    close_icon: str = "lucide:x",
    card_id: Optional[Dict[str, Any]] = None,
) -> list:

    text_children = [html.H3(title, className="tutorial-card__title")]
    if description:
        text_children.append(
            html.P(description, className="tutorial-card__description")
        )

    footer_children = []
    if step_text:
        footer_children.append(html.Span(step_text, className="tutorial-card__steps"))
    if button_text:
        footer_children.append(
            Button(
                button_text,
                id={**card_id, "subtype": "next"} if card_id else "tutorial-card-next",
                variant="primary",
                size="m",
            )
        )

    content: list = [
        html.Div(
            className="tutorial-card__body",
            children=[
                html.Div(
                    className="tutorial-card__body-content",
                    children=text_children,
                ),
                Button(
                    icon=close_icon,
                    variant="ghost",
                    size="s",
                    id={**card_id, "subtype": "close"} if card_id else "tutorial-card-close",
                    className="tutorial-card__close",
                    type="button",
                    **{"aria-label": "Close tutorial"},
                ),
            ],
        ),
    ]
    if footer_children:
        content.append(
            html.Div(className="tutorial-card__footer", children=footer_children)
        )
    return content


def _resolve_card_id(id: Optional[Union[str, Dict[str, Any]]]) -> Dict[str, Any]:
    if id is None:
        return {"type": "tutorial_card", "index": str(uuid4())}
    if isinstance(id, str):
        return {"type": "tutorial_card", "index": id}
    return id


def TutorialSequence(
    *,
    cards: Sequence[Dict[str, Any]],
    current_index: int = 0,
    close_icon: str = "lucide:x",
) -> Dict[str, Optional[str]]:

    if not cards:
        raise ValueError("TutorialSequence requires at least one card.")

    if current_index < 0 or current_index >= len(cards):
        raise IndexError("current_index out of range for TutorialSequence.")

    total = len(cards)
    card_data = cards[current_index]

    step_text = f"{current_index + 1} of {total}" if total > 1 else None
    button_text = "Next" if current_index < total - 1 else None

    return {
        "title": card_data["title"],
        "description": card_data.get("description"),
        "step_text": step_text,
        "button_text": button_text,
        "close_icon": close_icon,
    }


def TutorialUnique(
    *,
    title: str,
    description: Optional[str] = None,
    close_icon: str = "lucide:x",
    id: Optional[Union[str, Dict[str, Any]]] = None,
) -> html.Div:
    card_id = _resolve_card_id(id)
    content = [
        html.Div(
            className="tutorial-card__body",
            children=[
                html.Div(
                    className="tutorial-card__body-content",
                    children=[
                        html.H3(title, className="tutorial-card__title"),
                        *(
                            [html.P(description, className="tutorial-card__description")]
                            if description
                            else []
                        ),
                    ],
                ),
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
        )
    ]

    return html.Div(
        className="tutorial-card tutorial-card__surface",
        id=card_id,
        children=content,
    )



def TutorialCard(
    *,
    cards: Optional[Sequence[Dict[str, Any]]] = None,
    current_index: int = 0,
    title: Optional[str] = None,
    description: Optional[str] = None,
    step_text: Optional[str] = None,
    button_text: Optional[str] = None,
    close_icon: str = "lucide:x",
    id: Optional[Union[str, Dict[str, Any]]] = None,
) -> html.Div:
    """
    Single entry point. If `cards` is provided, renders a sequence with automatic step text.
    Otherwise renders a single TutorialCard using the provided fields.
    """

    card_id = _resolve_card_id(id)

    if cards is not None:
        resolved = TutorialSequence(
            cards=cards,
            current_index=current_index,
            close_icon=close_icon,
        )
        content = _build_tutorial_content(
            title=resolved["title"],
            description=resolved["description"],
            step_text=resolved["step_text"],
            button_text=resolved["button_text"],
            close_icon=resolved["close_icon"] or close_icon,
            card_id=card_id,
        )

        return html.Div(
            className="tutorial-card",
            id=card_id,
            children=[
                dcc.Store(
                    id={**card_id, "subtype": "state"},
                    data={
                        "cards": list(cards),
                        "current_index": current_index,
                        "close_icon": close_icon,
                    },
                ),
                html.Div(
                    id={**card_id, "subtype": "content"},
                    className="tutorial-card__surface",
                    children=content,
                ),
            ],
        )

    return TutorialUnique(
        title=title,
        description=description,
        close_icon=close_icon,
        id=card_id,
    )
