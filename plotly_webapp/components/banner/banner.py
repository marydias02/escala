import logging
from typing import Any, Dict, Literal, Optional, Sequence, TypedDict, Union
from uuid import uuid4

from dash import html
from dash_iconify import DashIconify

from callbacks.banner.banner import dismiss_banner
from components.button.button import Button

MessageVariant = Literal["warning", "positive", "neutral", "dark", "negative"]


class BannerButton(TypedDict):
    label: str
    id: Union[str, Dict[str, Any]]


def TableBanner(
    message: str,
    variant: MessageVariant = "warning",
    icon: Optional[str] = None,
) -> html.Aside:
    return html.Aside(
        [
            DashIconify(icon=icon, width=14) if icon else None,
            html.P(message),
        ],
        className=f"banner banner--table banner--{variant} body-sm",
    )


def Banner(
    header: str,
    description: Optional[str] = None,
    variant: MessageVariant = "warning",
    icon: Optional[str] = None,
    buttons: Optional[Sequence[BannerButton]] = None,
    dismissable: Optional[bool] = True,
    id: Optional[Union[str, Dict[str, Any]]] = None,
) -> html.Aside:
    if buttons and len(buttons) > 2:
        logging.warning("Banner supports a maximum of 2 buttons")
        raise ValueError("Banner supports a maximum of 2 buttons")

    if id is None:
        banner_id = {"type": "banner", "index": str(uuid4())}
    elif isinstance(id, str):
        banner_id = {"type": "banner", "index": id}
    else:
        banner_id = id

    footer = None
    if buttons:
        footer = html.Footer(
            [
                Button(
                    button["label"],
                    id=button["id"],
                    variant="primary" if i == 0 else "outline",
                    size="xs",
                    className="banner__button",
                )
                for i, button in enumerate(buttons)
            ],
            className="banner__footer",
        )

    close_button = (
        Button(
            icon="lucide:x",
            size="xs",
            variant="ghost",
            id={**banner_id, "subtype": "close"},
            className="banner__close-button",
        )
        if dismissable
        else None
    )

    has_buttons = bool(buttons and len(buttons) > 0)
    centered = (description is None) and (not has_buttons) and bool(close_button)
    extra_class = "banner__centered" if centered else ""

    return html.Aside(
        [
            html.Main(
                [
                    html.Div(
                        [
                            html.Header(
                                [
                                    DashIconify(icon=icon, width=14) if icon else None,
                                    html.P(header),
                                ],
                                className="banner__header",
                            ),
                            html.P(description, className="banner__description") if description else None,
                        ]
                    ),
                    footer,
                ],
                className="banner__content",
            ),
            close_button,
        ],
        className=f"banner banner--{variant} body-sm {extra_class}",
        id=banner_id,
    )
