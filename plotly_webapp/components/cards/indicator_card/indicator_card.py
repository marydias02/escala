from typing import Literal, Optional, Sequence, Tuple, Union

from dash import html
from dash_iconify import DashIconify

from components.badge.badge import Badge

Delta = Literal["increase", "decrease"]
BadgeUnit = Literal["%", "pp"]
BadgeValue = Union[str, float]


def _format_badge_value(value: BadgeValue, unit: BadgeUnit) -> str:
    """Add the selected unit, replacing a unit already present in the value."""
    text = str(value).strip()

    if text.endswith("pp"):
        text = text[:-2].rstrip()
    elif text.endswith("%"):
        text = text[:-1].rstrip()

    separator = " " if unit == "pp" else ""
    return f"{text}{separator}{unit}"


def IndicatorCard(
    *,
    label_text: Optional[str] = None,
    label_tooltip: Optional[str] = None,
    rows: Sequence[Tuple[Union[str, float], Optional[str], Optional[BadgeValue], Optional[Delta]]],
    badge_unit: BadgeUnit = "%",
) -> html.Div:
    """
    rows:
      - "value"         -> Card Value
      - "caption"       -> Card Description
      - "badge value"   -> optional badge component: value (without a unit)
      - "badge delta"   -> optional badge component: delta string "increase" or "decrease"

    badge_unit controls whether badge values are displayed as percentages ("%")
    or percentage points ("pp").
    """
    
    if not rows:
        raise ValueError("IndicatorCard requires at least one row in `rows`.")

    if badge_unit not in ("%", "pp"):
        raise ValueError("IndicatorCard `badge_unit` must be either '%' or 'pp'.")
    
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
            footer_children.append(Badge(_format_badge_value(badge_value, badge_unit), badge_delta))

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





