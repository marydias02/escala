from dash import callback_context


def update_sidebar_logic(toggle_clicks, menu_clicks, current_state):
    ctx = callback_context

    if not ctx.triggered:
        return "app__sidebar", "app__header-menuIcon hide", {"open": True}

    is_open = current_state.get("open", False) if current_state else False
    new_state = not is_open

    if new_state:
        return "app__sidebar", "app__header-menuIcon hide", {"open": True}
    else:
        return (
            "app__sidebar sidebar--collapsed",
            "app__header-menuIcon body-sm button button--ghost button--md",
            {"open": False},
        )
