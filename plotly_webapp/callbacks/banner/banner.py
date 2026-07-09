from dash import MATCH, Input, Output, State, callback


@callback(
    Output({"type": "banner", "index": MATCH}, "className"),
    Input({"type": "banner", "index": MATCH, "subtype": "close"}, "n_clicks"),
    State({"type": "banner", "index": MATCH}, "className"),
    prevent_initial_call=True,
)
def dismiss_banner(n_clicks, current_class):
    if n_clicks:
        return current_class + " banner--dismissed"
    return current_class
