

import dash
from dash import html

from components.cards.tutorial_card.tutorial_card import TutorialCard


dash.register_page(
    __name__,
    path="/components/cards/tutorial-card",
    title="Tutorial Card",
)


layout = html.Div(
    className="tutorial-card-page__content-wrapper",
    children=[
        html.Div(
            className="tutorial-card-page__card-container",
            children=[
                html.H1("Basic Card with a single page", className="heading-1"),
                TutorialCard(
                    title="Complex Tooltip",
                    description="This is a tooltip text, lorem ipsum sit dolor amet avec consecteteur.",
                ),
            ],
        ),
        html.Div(
            className="tutorial-card-page__card-container",
            children=[
                html.H1("Basic Card with multiple pages", className="heading-1"),
                TutorialCard(
                    cards=[
                        {
                            "title": "Complex Tooltip 1",
                            "description": "This is a tooltip text 1, lorem ipsum sit dolor amet avec consecteteur.",
                        },
                        {
                            "title": "Complex Tooltip 2",
                            "description": "This is a tooltip text 2, lorem ipsum sit dolor amet avec consecteteur.",
                        },
                    ],
                ),
            ],
        ),
        html.Div(
            className="tutorial-card-page__card-container",
            children=[
                html.H1("Basic Card with no description and a single page", className="heading-1"),
                TutorialCard(
                    cards=[
                        {
                            "title": "Complex Tooltip 1"
                        },
                    ],
                ),
            ],
        ),
        html.Div(
            className="tutorial-card-page__card-container",
            children=[
                html.H1("Basic Card with no description and multiple pages", className="heading-1"),
                TutorialCard(
                    cards=[
                        {
                            "title": "Complex Tooltip 1"
                        },
                        {
                            "title": "Complex Tooltip 2"
                        },
                    ],
                ),
            ],
        ),
    ],
)
