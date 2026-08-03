import dash
from dash import html
from dash_iconify import DashIconify

from typing import Optional, Union, Sequence , Tuple, Literal

from components.badge.badge import Badge

Delta = Literal["increase", "decrease"]

def IndicatorCard(
    *,
    label_text: Optional[str] = None,
    label_tooltip: Optional[str] = None,
    rows: Sequence[Tuple[Union[str, float], Optional[str], Optional[str], Optional[Delta]]],
) -> html.Div:
    """
    rows:
      - "value"         -> Card Value
      - "caption"       -> Card Description
      - "badge value"   -> optional badge component: value
      - "badge delta"   -> optional badge component: delta string "increase" or "decrease"
    """
    
    if not rows:
        raise ValueError("IndicatorCard requires at least one row in `rows`.")
    
    root_class = "indicator-card"

    blocks = []

    # ------------ Label block optional ------------
    if label_text:
        label_children = [html.P(label_text)]

        # Only show icon when tooltip is defined
        if label_tooltip:
            label_children.append(
                html.Span(
                    title=label_tooltip or None, 
                    children=[DashIconify(icon="lucide:info", width=13)]
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
        value_block = html.Div(
            children=[
                html.P(str(value), className="body-xl"),
            ],
            className="indicator-card__value",
        )

        footer_children = []

        if badge_value is not None and badge_delta is not None:
            footer_children.append(Badge(badge_value, badge_delta))

        if caption is not None:
            footer_children.append(
                html.P(caption, className="body-xs indicator-card__caption")
            )

        section_children = [value_block]

        if footer_children:
            section_children.append(
                html.Div(
                    className="indicator-card__footer",
                    children=footer_children,
                )
            )

        sections.append(
            html.Div(
                className="indicator-card__content",
                children=section_children,
            )
        )

    blocks.append(
        html.Div(
            className="indicator-card__content-wrapper", 
            children=sections
        )
    )


    return html.Div(className=root_class, children=blocks )





