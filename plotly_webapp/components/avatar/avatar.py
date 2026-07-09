from typing import Literal, Optional

from dash import html
from dash_iconify import DashIconify

Size = Literal["s", "m"]

def get_initials(username: str):
    parts = username.split()
    
    # Two or more names
    return parts[0][0].upper() + parts[-1][0].upper()

def Avatar(
    username: str,
    size: Size = "s",
    img_src: str = "",
) :
    
    classes = [
        "user-avatar",
        f"user-avatar--{size}",
    ]

    children = []
    if img_src and img_src != "":
        children.append(html.Img(src=img_src, alt="user avatar"))
    elif username is None or username=="":
        children.append(DashIconify(icon="lucide:user", width=14))
    else:
        children.append(get_initials(username))

    classes = " ".join(classes)

    return html.Div(
        children=children,
        className=classes,
    )