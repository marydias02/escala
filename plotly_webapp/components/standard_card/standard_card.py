from typing import Any, Dict, Literal, Union

from dash import html
from dash_iconify import DashIconify

from components.button.button import Button

Variant = Literal["clickable", "not clickable"]


def StandardCard(
    text: str,
    icon: str,
    description: str,
    button_name: str,
    button_href: str,
    button_id: Union[str, Dict[str, Any]],
    variant: Variant = "clickable",
) -> html.Div:
    classes = ["standard_card"]

    if variant == "not clickable":
        classes.append("standard_card--not-clickable")

    return html.Div(
        [
            html.Div(
                [
                    DashIconify(icon="lucide:" + icon, width=14),
                    html.P(text, className="body-sm"),
                ],
                className="standard_card__header",
            ),
            html.Span(description, className="standard_card__description"),
            Button(html.A(button_name, href=button_href, target="_self"), id=button_id, variant="outline", size="xs"),
        ],
        className=" ".join(classes),
    )
