

import dash
from dash import html

from components.cards.workflow_card.workflow_card import WorkflowCard


dash.register_page(
    __name__,
    path="/components/cards/workflow-card",
    title="Workflow Card",
)

example_team = [
    {"username": "Elisa Sampaio", "progress": 50, "is_you": True},
    {"username": "Jamie Santos", "progress": 100},
    {"username": "Nico Zamidi", "progress": 25},
]

layout = html.Div(
  className="workflow-card-page__content-wrapper",
  children=
  [
    html.Div(
      className="workflow-card-page__card-container",
      children=
      [
        html.H1("Basic Card with all components", className="heading-1"),
        WorkflowCard(
          title="Card Title",
          description="Secondary text here",
          tag_text="Due today",
          tag_icon="circle-alert",
          tag_variant="mild",
          overall_progress= 75,
          team=example_team,
          table_title="Team Progress"
        ),
    ]),
    html.Div(
      className="workflow-card-page__card-container",
      children=
      [
        html.H1("Basic Card without overall progress", className="heading-1"),
        WorkflowCard(
          title="Card Title",
          description="Secondary text here",
          tag_text="Due today",
          tag_icon="circle-alert",
          tag_variant="mild",
          team=example_team,
          table_title="Team Progress"
        ),
    ]),
    html.Div(
      className="workflow-card-page__card-container",
      children=
      [
        html.H1("Basic Card with no tag", className="heading-1"),
        WorkflowCard(
          title="Card Title",
          description="Secondary text here",
          overall_progress= 75,
          team=example_team,
          table_title="Team Progress"
        ),
    ]),      
  ]
)