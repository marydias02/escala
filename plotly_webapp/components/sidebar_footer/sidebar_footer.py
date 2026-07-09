from dash import html
from dash_iconify import DashIconify

from typing import Optional

from components.button.button import Button
from components.avatar.avatar import Avatar

def SidebarFooter(
    username: str,
    avatar_size: Optional[str] = None,
    avatar_image: Optional[str] = None,
) -> html.Footer:
    return html.Footer(
        [
            html.Div(
                [
                    Avatar(
                        username=username,
                        size=avatar_size,
                        img_src=avatar_image,
                    ),
                    html.Span(username, className="sidebar-footer__username"),
                ],
                className="sidebar-footer__user",
            ),
            html.Div(
                [
                    Button(
                        DashIconify(
                            icon="lucide:settings",
                            width=16,
                            className="sidebar__header-menu-icon",
                        ),
                        size="s",
                        variant="ghost",
                        id="sidebar-user-settings",
                        className="sidebar-footer__settings-btn",
                    ),
                    Button(
                        DashIconify(
                            icon="lucide:log-out",
                            width=16,
                            className="sidebar__header-menu-icon",
                        ),
                        size="s",
                        variant="ghost",
                        id="sidebar-user-logout",
                        className="sidebar-footer__logout-btn",
                    ),
                ],
                className="sidebar-footer__icons",
            ),
        ],
        className="sidebar-footer",
    )