

import dash
from dash import html

from components.components_extra_design_system.components_extra_ds import IndicatorCardExtra



dash.register_page(
    __name__,
    path="/components/indicator-card-extra-ds",
    title="Indicator Card",
)


layout = html.Div(
  className="indicator-card-page__content-wrapper",
  children=
  [
    html.Div(
      className="indicator-card-page__card-container",
      children=
      [
        html.H1("Card with 1 Content Row, Label and Delta Badge", className="heading-1"),
        IndicatorCardExtra(
          label_text="Item Label",
          label_tooltip="extra info",
          rows=[("36%", "Expected SLA", "12%", "decrease")]
        ),
    ]),
    html.Div(
      className="indicator-card-page__card-container",
      children=
      [
        html.H1("Card with 2 Content Row, Label and 1 Delta Badge", className="heading-1"),
        IndicatorCardExtra(
          label_text="Item Label",
          label_tooltip="extra info",
          rows=[("13%", "Expected Setup", "2%", "increase"),
                ("20%", "Production Ratio", None, None),
                ]
        ),
      ]),
      html.Div(
      className="indicator-card-page__card-container",
      children=
      [
        html.H1("Card with 1 Content Row, Title with Icon and Delta Badge", className="heading-1"),
        IndicatorCardExtra(
          title_icon="lucide:users",
          title_text="Users",
          rows=[("22%", "Expected PM Utilization", "20%", "increase")]
        ),
      ]),
      html.Div(
      className="indicator-card-page__card-container",
      children=
      [
        html.H1("'Sailor' Example Card", className="heading-1"),
        IndicatorCardExtra(
        title_icon="lucide:file",
        title_text="Project",
        rows=[("Sailor", "Name", None , None),
              ("00003", "Code", None, None)]
      ),
      ])
  ]
)