from typing import Any, Dict, Optional, Union, Sequence

from dash import html

from components.button.button import Button


def Section(
    title: str = "Section Title",
    description: Optional[str] = None,
    extra_element: Optional[Union[Any, Sequence[Any]]] = None,  # Buttons, Badges, etc. This will be rendered in the rightmost area.
    content: Any = None,
    open: Optional[bool] = False,  # The default initial state of the Section. Open/Close.
    id: Union[str, Dict[str, Any]] = "section-id",
) -> html.Details:
    
    return html.Details(
        [
            html.Summary(
                [
                    Button(
                        icon="f7:arrowtriangle-down-fill",
                        variant="ghost secondary",
                        className="section__arrow",
                    ),
                    html.Header(
                        [
                            html.H2(title, className="heading-2"),
                            description and html.P(description, className="section__description body-sm"),
                        ],
                        className="section__title",
                    ),
                    html.Aside(
                        children=extra_element,
                        className= "section__extra-elements",
                    ),
                ],
                className="section__header",
            ),
            html.Div(
                content,
                className="section__content",
            ),
        ],
        open=open,
        id=id,
        className="section",
    )
