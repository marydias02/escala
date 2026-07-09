
import dash
from dash import html
from dash_iconify import DashIconify

from typing import Optional, Union, Sequence , Tuple

from components.badge.badge import Badge


#####################################################
##### INDICATOR CARDS #####
#####################################################


def IndicatorCardExtra(
    *,
    title_icon: Optional[str] = None, #(optional)
    title_text: Optional[str] = None, #(optional)
    label_text: Optional[str] = None, #(optional)
    label_tooltip: Optional[str] = None, #(optional)
    rows: Sequence[Tuple[Union[str, float], str, Optional[str], Optional[str]]], #value , caption , optional badge value (or None) , optional badge delta (or None)
):
    if not rows:
        raise ValueError("IndicatorCard requires at least one row in `rows`.")
    
    root_class = "indicator-card"

    blocks = []

    # ------------ Title block optional ------------
    if title_text or title_icon:
        title_children = []
        if title_icon:
            title_children.append(DashIconify(icon=title_icon))
        if title_text:
            title_children.append(html.P(title_text))
        blocks.append(
            html.Div(
                className="indicator-card__title body-xs",
                children=title_children,
            )
        )

    # ------------ Label block optional ------------
    if label_text:
        label_children = [html.P(label_text)]

        # Only show icon when tooltip is defined
        if label_tooltip:
            label_children.append(
                html.Span(
                    title=label_tooltip or None, 
                    children=[DashIconify(icon="lucide:info")]
                )
            )

        blocks.append(
            html.Div(
                className="indicator-card__label body-xs" ,
                children=label_children,
            )
        )

    # ------------ Value block ------------

    sections = []
    for value, caption, badge_value, badge_delta in rows:
        value_children = [html.P(str(value), className="body-xl")]
        if badge_value is not None and badge_delta is not None:
            value_children.append(Badge(badge_value, badge_delta))

        sections.append(
            html.Div(
                className="indicator-card__content",
                children=[
                    html.Div(className="indicator-card__value", children=value_children),
                    html.P(caption, className="indicator-card__value-caption body-sm"),
                ],
            )
        )

    blocks.append(
        html.Div(
            className="indicator-card__content-wrapper", 
            children=sections
        )
    )


    return html.Div(className=root_class, children=blocks )







