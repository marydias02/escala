import dash
from dash import ALL, Input, Output, State, clientside_callback, MATCH


clientside_callback(
    """
    function(n_clicks, id) {
        if (!n_clicks) return "";

        const el = document.getElementById(id.target);
        if (!el) return "";

        navigator.clipboard.writeText(el.innerText);
        return "";
    }
    """,
    Output({"type": "copy-button", "target": MATCH}, "data-dummy"),
    Input({"type": "copy-button", "target": MATCH}, "n_clicks"),
    Input({"type": "copy-button", "target": MATCH}, "id"),
)


