import dash
from dash import html

from utils.base.grid_system.grid import Col, Container, Row

dash.register_page(
    __name__,
    path="/grid",
    title="Grid",
)

layout = html.Div([
    html.Div([
        html.H2("1. Container Normal com Gutter",
                style={'margin': '20px 0'}),
        Container([
            Row([
                Col([
                    html.Div([
                        html.H3("Coluna 1"),
                        html.P("Com gutter normal")
                    ], style={'background': 'lightblue'})
                ], xs=12, md=6, lg=4),

                Col([
                    html.Div([
                        html.H3("Coluna 2"),
                        html.P("Com gutter normal")
                    ], style={'background': 'lightblue'})
                ], xs=12, md=6, lg=4),

                Col([
                    html.Div([
                        html.H3("Coluna 3"),
                        html.P("Com gutter normal")
                    ], style={'background': 'lightblue'})
                ], xs=12, md=12, lg=4),
            ]),
        ])
    ]),

    # Container fluid
    html.Div([
        html.H2("2. Container Fluid", style={'margin': '20px 0'}),
        Container([
            Row([
                Col([
                    html.Div([
                        html.H3("Fluid Container"),
                        html.P("Ocupa toda a largura disponível")
                    ], )
                ], xs=12),
            ]),
        ], fluid=True, style={'background': 'green'}),
    ]),

    # Sem gutter
    html.Div([
        html.H2("3. Row/Col sem Gutter", style={'margin': '20px 0'}),
        Container([
            Row([
                Col([
                    html.Div([
                        html.H3("Sem Espaço 1"),
                        html.P("no_gutter=True")
                    ], )
                ], xs=6, no_gutter=True, style={'background': 'lightcoral'}),

                Col([
                    html.Div([
                        html.H3("Sem Espaço 2"),
                        html.P("no_gutter=True")
                    ], )
                ], xs=6, no_gutter=True, style={'background': 'lightcoral'}),
            ], no_gutter=True),
        ])
    ]),
])
