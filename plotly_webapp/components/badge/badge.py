
from dash import html
from dash_iconify import DashIconify
from typing import Literal


Delta = Literal["increase","decrease"]

def Badge(
        value: str, 
        delta: Delta ='increase'
    ) -> html.Div:

    delta = delta.lower()

    if delta == "increase":
        icon_name = "tabler:caret-up-filled"
        delta_class = "badge--delta-increase"
    else:
        icon_name = "tabler:caret-down-filled"
        delta_class = "badge--delta-decrease"

    badge_class = f"body-xs badge {delta_class}"

    return html.Div(
        className=badge_class,
        children=[
            DashIconify(icon=icon_name),
            html.P(value)
        ]
    )
