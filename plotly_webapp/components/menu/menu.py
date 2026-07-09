import re
from typing import Optional, List

from dash import dcc, html
from dash_iconify import DashIconify

from components.button.button import Button

def create_link(text: str) -> str:
    # example: text="My Page!" -> href="/my-page"
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return "/" + re.sub(r"[\s_-]+", "-", text)

def Menu(
    title: str = "Menu Title",
    href: Optional[str] = None,
    icon: Optional[str] = None,
    children: Optional[List[dcc.Link]] = None,
    open: Optional[bool] = False,
) :
    
    children = children or []
    href = href or create_link(title)

    menuWithoutSubpages = dcc.Link(
        [
            DashIconify(icon=icon, width=16, className="menu__header-icon") if icon else None,
            html.Span(title, className="menu__label"),
        ],
        href=href,
        className="menu menu__header menu__link",
    )

    menuWithSubpages = html.Details(
        [
            html.Summary(
                [
                    DashIconify(icon=icon, width=16, className="menu__header-icon") if icon else None,
                    html.H2(title),
                    DashIconify(
                        icon="lucide:chevron-down",
                        width=16,
                        className="menu__arrow menu__header-icon",
                    ),
                ],
                className="menu__header",
            ),
            html.Div(
                className="menu__dropdown",
                children=[
                    html.Ul(
                        className="menu__dropdown-list",
                        children=[
                            html.Li(item, className="menu__item")
                            for item in children
                        ],
                    ),
                ],
            ),
        ],
        open=open,
        className="menu",
    )

    return menuWithoutSubpages if not children else menuWithSubpages
