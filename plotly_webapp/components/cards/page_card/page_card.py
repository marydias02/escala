from typing import Optional, Literal
from dash import html
from dash_iconify import DashIconify

Variant = Literal["primary", "compact"]


def PageCard(
    icon: str,
    title: str,
    description: Optional[str] = None,
    variant: Variant = "primary",
) -> html.Div:

    page_card_children = []

    # variant 1 of page card - layout with description
    if variant == "primary":

        page_card_children.append(
            html.Div(
                DashIconify(icon="lucide:" + icon, width = 14),
                className="page-card__icon-wrap",
            )
        )

        body_children = [html.H3(title, className="page-card__title")]
        if description:
            body_children.append(html.P(description, className="page-card__description"))

        page_card_children.append(html.Div(body_children, className="page-card__body"))
        card_class = "page-card"

    # variant 2 of page card - compact layout
    else:

        page_card_children.append(
            html.Div(
                [
                    html.Div(
                        DashIconify(icon="lucide:" + icon, width = 14),
                        className="page-card__icon-wrap",
                    ),
                    html.H3(title, className="page-card__title"),
                ],
                className="page-card__header",
            )
        )
        card_class = "page-card page-card--compact"

    return html.Div(page_card_children, className=card_class)
