from typing import List, Optional, Tuple

from dash import dcc, html

from components.banner.banner import TableBanner
from components.button.button import Button
from components.table.shared.types import MessageConfig


def create_table_actions_section(
    grid_id: str,
    primary_action: Optional[str] = None,
    banner: Optional[MessageConfig] = None,
    note: Optional[str] = None,
    enable_reset: bool = False,
    secondary_actions: Optional[List[Tuple[str, str]]] = None,
) -> html.Section:
    initial_content = []

    if banner:
        message_text = banner.get("text")
        message_variant = banner.get("variant", "warning")
        message_icon = banner.get("icon")
        initial_content.append(TableBanner(message_text, message_variant, icon=message_icon))

    if note:
        initial_content.append(html.Span(note, className="body-xs table-header__text-frame"))

    header_actions = []

    if enable_reset:
        header_actions.append(
            Button(
                icon="lucide:refresh-ccw",
                size="xs",
                variant="ghost secondary",
                id=f"{grid_id}-refresh-btn",
                disabled=True,
                title="Reset Table",
            )
        )

    if secondary_actions:
        for item in secondary_actions:
            label, icon = item[:2]
            slug_label = label.lower().replace(" ", "-").replace("/", "-")
            header_actions.append(
                Button(
                    icon=icon,
                    size="xs",
                    variant="ghost secondary",
                    id=f"{grid_id}-secondary-{slug_label}-btn",
                    title=label,
                )
            )

    if primary_action:
        header_actions.append(Button(primary_action, size="xs", id=f"{grid_id}-primary-btn"))

    if header_actions:
        header_actions_section = html.Div(
            header_actions,
            className="table-header__actions__icons",
        )
        initial_content.append(header_actions_section)

    return html.Section(
        initial_content,
        className="table-header__actions",
    )


def create_table_header_section(
    grid_id: str,
    title: Optional[str] = None,
    tabs: Optional[dcc.Tabs] = None,
    primary_action: Optional[str] = None,
    banner: Optional[MessageConfig] = None,
    note: Optional[str] = None,
    enable_reset: bool = False,
    secondary_actions: Optional[List[Tuple[str, str]]] = None,
    class_name: str = "table-header",
) -> html.Header:
    header_children = []

    if title:
        title_section = html.Div(
            [
                html.H1(title, className="heading-3"),
                create_table_actions_section(grid_id, primary_action, banner, note, enable_reset, secondary_actions),
            ],
            className="table-header__title",
        )
        header_children.append(title_section)
    else:
        header_children.append(
            create_table_actions_section(grid_id, primary_action, banner, note, enable_reset, secondary_actions)
        )

    tab_switcher = tabs if tabs else None

    if tab_switcher is not None:
        header_children.append(tab_switcher)

    filter_display = html.Div(id=f"{grid_id}-filter-display")
    header_children.append(filter_display)

    return html.Header(
        header_children,
        className=class_name,
    )
