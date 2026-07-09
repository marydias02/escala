from dash import html
 
from typing import Any, Dict, List, Literal, Optional, Union

from components.avatar.avatar import Avatar
from components.progress.progress import Progress
from components.tag.tag import Tag
 
 
def build_team_block(
    team: Optional[List[Dict]] = None,
    table_title: Optional[str] = None,
) -> List:

    team_children: List = []
    if not team:
        return team_children

    if table_title:
        team_children.append(
            html.P(table_title, className="workflow-card__section-title")
        )

    team_rows = []
    for member in team:
        username = member.get("username", "")
        prog = int(member.get("progress", 0))
        img_src = member.get("img_src", "")
        is_you = bool(member.get("is_you", False))

        member_name = (
            [
                html.Span(
                    username,
                    className="workflow-card__user-name",
                ),
                html.Span(
                    " (You)",
                    className="workflow-card__user-name workflow-card__user-name--you",
                ),
            ]
            if is_you
            else username
        )

        member_row = html.Div(
            [
                html.Div(
                    [
                        Avatar(username=username, size="s", img_src=img_src),
                        html.Div(
                            member_name,
                            className="workflow-card__member-name",
                        ),
                    ],
                    className="workflow-card__member-left workflow-card__user-id",
                ),
                Progress(value=prog, size="sm"),
            ],
            className="workflow-card__member-row workflow-card__user",
        )
        team_rows.append(member_row)

    team_children.append(
        html.Div(team_rows, className="workflow-card__users")
    )

    return team_children

TagVariant = Literal["positive", "negative", "outline", "mild", "fill"]

def WorkflowCard(
    # title + description
    title: str,
    description: Optional[str] = None,
    # tag
    tag_icon: Optional[str] = None,
    tag_text: Optional[str] = None,
    tag_variant: Optional[TagVariant] = None,
    # progress table
    overall_progress: Optional[int] = None,
    team: Optional[List[Dict]] = None,
    table_title: Optional[str] = None,
) -> html.Div:
    """
    team: list[dict], where each item represents a team member:
        - username (str): name to be displayed in the card
        - progress (int): user's progress (ex: 50)
        - img_src (str | None): URL/path to the user's avatar
        - is_you (bool): True in case of being the current user
    Exemplo:
    [
        {"username": "Ana Pires", "progress": 50, "img_src": "/assets/ana.png", "is_you": True},
        {"username": "Filipe Castro", "progress": 20, "img_src": None, "is_you": False},
    ]
    """


    header_children = []

    if tag_text:
        header_children.append(
                Tag(
                    tag_text,
                    icon=tag_icon,
                    variant=tag_variant or "outline",
                    size="2xs",
                ),
            )

    if overall_progress is not None:
        header_children.append(
                Progress(value=overall_progress, size="sm"),
            )

    has_tag = bool(tag_text)
    has_overall_progress = overall_progress is not None

    header_group_class = "workflow-card__header-group"
    if has_tag and has_overall_progress:
        header_group_class += " workflow-card__header-group--between"
    elif has_overall_progress and not has_tag:
        header_group_class += " workflow-card__header-group--end"

    header_block = (
        html.Div(header_children, className=header_group_class)
        if header_children
        else None
    )
 
    content_children = [html.H2(title, className="workflow-card__title")]
 
    if description:
        content_children.append(
            html.P(description, className="workflow-card__description")
        )

    team_children = build_team_block(team, table_title)


    blocks = []
    if header_block is not None:
        header_class = "workflow-card__header"
        blocks.append(html.Div(header_block, className=header_class))
    blocks.append(html.Div(content_children, className="workflow-card__content"))
    blocks.append(html.Div(team_children, className="workflow-card__team"))

    return html.Div(children=blocks, className="workflow-card")
 
