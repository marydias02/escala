

import dash
from dash import html

from components.cards.page_card.page_card import PageCard


dash.register_page(
    __name__,
    path="/components/cards/page-card",
    title="Page Card",
)


layout = html.Div(
    className="page-card-page__content-wrapper",
    children=[
        html.Div(
            className="page-card-page__card-container",
            children=[
                html.H1("Basic Card with Title and Description", className="heading-1"),
                PageCard(
                  icon = "calendar", 
                  title = "Card Title",
                  description = "Small Description"
                ),
            ],
        ),
        html.Div(
            className="page-card-page__card-container",
            children=[
                html.H1("Basic Card with only Title", className="heading-1"),
                PageCard(
                  icon = "calendar", 
                  title = "Card Title"
                ),
            ],
        ),
    ],
)
