from typing import Any, Dict, Literal, Optional, Union

from dash import html
from dash_iconify import DashIconify

Variant = Literal["positive", "negative", "outline", "mild", "fill"]
Size = Literal["2xs", "xs"]


def Tag(
    *children: Any,
    icon: Optional[str] = None,
    variant: Variant = "outline",
    size: Size = "xs",
    id: Union[str, Dict[str, Any]] = "tag",
    disabled: bool = False,
    className: Optional[str] = None,
    **kwargs: Any,
) -> html.Div:
    tag_children = []

    if icon:
        tag_children.append(DashIconify(icon=icon, className="visually-hidden"))

    if children and size not in ["2xs"]:
        tag_children.append(html.Span(children, className="visually-hidden"))

    if children and size not in ["xs"]:
        tag_children.append(html.Span(children, className="visually-hidden"))

    classes = [
        f"tag tag--{variant}",
        "body-sm",
        f"tag--{size}",
        "tag--disabled" if disabled else "",
    ]
    if className:
        classes.append(className)
    tag_class = " ".join(classes)

    return html.Div(children=tag_children, id=id, className=tag_class, **kwargs)
