from typing import Optional

from dash import html
from dash_iconify import DashIconify


def Label(
    label_text: Optional[str] = None,
    icon: Optional[str] = None,
    show_icon: bool = False,
    as_label: bool = True,
):
    """
    Args:
        label_text: Text shown in the label
        icon: Iconify icon name, replaces the default icon if set
        show_icon: When True, shows a default icon
        as_label: When False, renders a span instead of a label
    """
    label_children = []

    if label_text:
        label_children.append(html.P(label_text, className="label__text"))

    if show_icon or icon:
        label_children.append(
            DashIconify(
                icon=icon or "lucide:circle-question-mark",
                width=11,
                height=11,
            )
        )

    wrapper = html.Label if as_label else html.Span

    return wrapper(className="label label--default", children=label_children)
