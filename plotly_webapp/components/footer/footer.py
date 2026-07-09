from dash import html


def Footer (
    client_name: str,
) -> html.Footer :

  return html.Footer(
          className="app__footer",
          children=[
            html.P(
              client_name,
              className="app__footer-text",
            ),
            html.Div(
                className="app__footer-logo-wrapper",
                children=[
                    html.P(
                        "Powered by ",
                        className="app__footer-text",
                    ),
                    html.A(
                        href="https://www.ltplabs.com",
                        target="_blank",
                        children=[
                            html.Span(className="app__footer-logo"),
                        ],
                        className="app__footer-link",
                    )
                ],
            ),
          ],
        )



