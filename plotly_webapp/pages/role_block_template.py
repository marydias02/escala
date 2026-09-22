import dash
from dash import html
from flask import session

dash.register_page(
    __name__,
    path="/admin",
    title="Role test page",
)


def layout():
    """This page exists only as a template for blocking pages based on role"""
    if "admin" not in (session.get("user") or {}).get("roles", []):
        return html.Div("Sem permissão para aceder a esta página.")
    return html.Div("Página carregada com sucesso!.")
