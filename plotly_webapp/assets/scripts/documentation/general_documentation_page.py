from dash import html, dcc

from components.section.section import Section
from components.button.button import Button

def SectionHeader(title, id=None, subtitle=None):
    children = [html.H2(title, className="heading-2", id=id)]
    if subtitle:
        children.append(html.H3(subtitle, className="heading-3"))
    return html.Div(className="component-page__headers", children=children)


def ExampleSection(
    preview,
    code: str,
    code_id: str | None = None,
    section_id: str | None = None,
):
  derived_code_id = code_id or (f"code-{section_id}" if section_id else None)
  if not derived_code_id:
    raise ValueError("ExampleSection requires either a code_id or a section_id.")
  return html.Div(
    className="component-section",
    children=[
      html.Div(
        className="component-wrapper",
        children=preview,
      ),
      Section(
        title="Code",
        extra_element=Button(
          icon="lucide:copy",
          variant="ghost secondary",
          size="2xs",
          id={
            "type": "copy-button",
            "target": derived_code_id,
          },
        ),
        content=[
          html.Pre(code, id=derived_code_id),
        ],
      ),
    ],
  )


def PropertyItem(name, type_str, description):
    return html.Div(
        className="property__wrapper",
        children=[
            html.P(name, className="body-sm property__title"),
            html.P(type_str, className="body-sm property__characteristics"),
            html.P(description, className="body-sm property__text"),
        ],
    )


def PropertiesSection(properties: list[dict]):
  return html.Div(
        className="property__section",
        children=[
            PropertyItem(p["name"], p["type"], p["description"])
            for p in properties
        ],
    )


def DocumentationPage(
    title: str,
    toc_links: list[tuple[str, str]],
    content_sections: list,
):
    return html.Div(
      className="component-page",
      children=[
        dcc.Location(id=f"{title.lower()}-page-location", refresh=False),

        # Table of contents
        html.Div(
          className="component-page__table-contents",
          children=[
            html.P(
                "On This Page",
                className="component-page__table-contents-title heading-2",
            ),
            html.Ul(
                className="component-page__table-contents-list",
                children=[
                  html.Li(
                    html.A(
                      text,
                      href=f"#{section}",
                      id={
                        "type": "component-page-toc-link",
                        "section": section,
                      },
                      className="component-page__table-contents-link body-sm",
                    )
                  )
                  for text, section in toc_links
                ],
            ),
          ],
        ),

        # Main content
        html.Div(
            className="component-page__content",
            children=content_sections,
        ),
      ],
    )
