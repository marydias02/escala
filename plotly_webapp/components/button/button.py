from typing import Any, Dict, Literal, Optional, Union

from dash import html
from dash_iconify import DashIconify

Variant = Literal["primary", "ghost", "outline", "ghost secondary"]
Size = Literal["2xs", "xs", "s", "m"]


def Button(
    *children: Any,
    icon: Optional[str] = None,
    variant: Variant = "primary",
    size: Size = "m",
    id: Union[str, Dict[str, Any]] = "button",
    loading: bool = False,
    destructive: bool = False,
    className: Optional[str] = None,
    **kwargs: Any,
) -> html.Button:
    button_children = []

    if icon:
        button_children.append(DashIconify(icon=icon, className="visually-hidden" if loading else ""))

    if children:
        button_children.append(html.Span(children, className="visually-hidden" if loading else ""))

    if loading:
        button_children.append(DashIconify(icon="lucide:loader-2", className="loading"))

    classes = [
        f"button button--{variant}",
        "body-sm",
        f"button--{size}",
    ]
    if loading:
        classes.append("button--loading")
    if destructive:
        classes.append("button--destructive")
    if className:
        classes.append(className)
    btn_class = " ".join(classes)

    return html.Button(children=button_children, id=id, className=btn_class, **kwargs)
