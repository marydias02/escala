from typing import Any, Dict, Literal, Optional, Union, Sequence

from dash import html
from dash_iconify import DashIconify


def _with_optional_id(props: dict, component_id: Optional[Union[str, dict]]) -> dict:
    """Return props unchanged if id is None; otherwise inject the id."""
    return props if component_id is None else {**props, "id": component_id}


def PageHeader(
        *,
        title: str = "Template Page", 
        icon: Optional[str] = None,
        subtitle: Optional[str] = None,
        title_id: Optional[Union[str, dict]] = None,
        subtitle_id: Optional[Union[str, dict]] = None,
        **kwargs: Any,
    ) -> html.Header:
    
    if icon is None and subtitle is None:
        page__header_class = "page__header--compact"
        icon_wrapper_class = "page__header-icon-wrapper"
        text_wrapper_class = "page__header-text-wrapper"
    elif icon is None and subtitle is not None:
        page__header_class = "page__header--compact"
        icon_wrapper_class = "page__header-icon-wrapper"
        text_wrapper_class = "page__header-text-wrapper"
    elif icon is not None and subtitle is None:
        page__header_class = "page__header--compact"
        icon_wrapper_class = "page__header-icon-wrapper--solo"
        text_wrapper_class = "page__header-text-wrapper"
    else:
        page__header_class = "page__header"
        icon_wrapper_class = "page__header-icon-wrapper"
        text_wrapper_class = "page__header-text-wrapper"

    if icon is None and subtitle is None:
        main_header = html.Div(
                className=page__header_class,
                children=[
                    html.H1(
                        title,
                        className="heading-1",
                        **_with_optional_id({}, title_id),
                    ),
                ],
            )
        
    elif icon is None and subtitle is not None:
        main_header = html.Div(
                className=page__header_class,
                children=[
                    html.Div(
                        className=text_wrapper_class,
                        children=[
                            html.H1(
                                title,
                                className="heading-1",
                                **_with_optional_id({}, title_id),
                            ),
                            html.P(
                                subtitle,
                                className="body-md",
                                **_with_optional_id({}, subtitle_id),
                            ),
                        ],
                    ),
                ]
            )
        
    elif icon is not None and subtitle is None:
        main_header = html.Div(
                className=page__header_class,
                children=[
                    html.Div(
                        className=icon_wrapper_class,
                        children=[
                            DashIconify(
                                icon=icon,
                                className="page__header-icon"
                            )
                        ],
                    ),
                    html.Div(
                        className=text_wrapper_class,
                        children=[
                            html.H1(
                                title,
                                className="heading-1",
                                **_with_optional_id({}, title_id),
                            ),
                        ],
                    ),
                ]
            )
        
    else:
        main_header = html.Div(
                className=page__header_class,
                children=[
                    html.Div(
                        className=icon_wrapper_class,
                        children=[
                            DashIconify(
                                icon=icon,
                                className="page__header-icon"
                            )
                        ],
                    ),
                    html.Div(
                        className=text_wrapper_class,
                        children=[
                            html.H1(
                                title,
                                className="heading-1",
                                **_with_optional_id({}, title_id),
                            ),
                            html.P(
                                subtitle,
                                className="body-md",
                                **_with_optional_id({}, subtitle_id),
                            ),
                        ],
                    ),
                ]
            )
    
    children: list[Any] = [main_header]

    return html.Header(children=children, **kwargs)

# if tag_children is None:
#     tag_children_list: Sequence[Any] = []
# elif isinstance(tag_children, (list, tuple)):
#     tag_children_list = tag_children
# else:
#     tag_children_list = [tag_children]

# html.Div(
#     className="page__header-progress-wrapper",
#     children=[
#         Tag(
#             *tag_children_list,
#             icon=tag_icon,
#             variant=tag_variant,
#             size=tag_size,
#             id=tag_id,
#             disabled=tag_disabled,
#             className=tag_className,
#             **(tag_kwargs or {}),
#         ),
#         Progress(value=progress_value, size=progress_size ,id=progress_id),
#     ],
# ),

