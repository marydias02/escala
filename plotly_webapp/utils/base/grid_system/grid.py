from dash import html

BREAKPOINTS = {
    "xs": 0,
    "sm": 640,
    "md": 768,
    "lg": 1024,
    "xl": 1280,
}


def Container(children, fluid=False, **kwargs):
    base_style = {"margin": "0 auto", "padding": "0", "width": "100%", "maxWidth": "100%"}
    if fluid:
        base_style["maxWidth"] = "100%"

    style = {**base_style, **kwargs.get("style", {})}
    return html.Div(children=children, style=style, **{k: v for k, v in kwargs.items() if k != "style"})


def Row(children, no_gutter=False, **kwargs):
    style = {
        "display": "flex",
        "flexWrap": "wrap",
    }
    if not no_gutter:
        style.update(
            {
                "marginLeft": "-7.5px",
                "marginRight": "-7.5px",
            }
        )
    style.update(kwargs.get("style", {}))
    return html.Div(children=children, style=style, **{k: v for k, v in kwargs.items() if k != "style"})


def Col(children, span=None, xs=None, sm=None, md=None, lg=None, xl=None, no_gutter=False, **kwargs):
    class_names = []
    existing_classes = kwargs.get("className", "").split() if kwargs.get("className") else []

    breakpoint_values = {"xs": xs, "sm": sm, "md": md, "lg": lg, "xl": xl}

    for breakpoint, value in breakpoint_values.items():
        if value is not None:
            class_names.append(f"col-{breakpoint}-{value}")

    if not class_names:
        if span:
            class_names.append(f"col-xs-{span}")
        else:
            style = {
                "flex": "1 1 0%",
                "paddingLeft": "7.5px" if not no_gutter else "0",
                "paddingRight": "7.5px" if not no_gutter else "0",
                **kwargs.get("style", {}),
            }
            return html.Div(
                children=children,
                style=style,
                className=" ".join(existing_classes),
                **{k: v for k, v in kwargs.items() if k not in ["style", "className"]},
            )

    base_style = {
        "position": "relative",
        "width": "100%",
        "boxSizing": "border-box",
        "marginBottom": "15px",
        **kwargs.get("style", {}),
    }

    if not no_gutter:
        base_style.update(
            {
                "paddingLeft": "7.5px",
                "paddingRight": "7.5px",
            }
        )

    base_style.update(kwargs.get("style", {}))

    all_classes = existing_classes + class_names
    return html.Div(
        children=children,
        style=base_style,
        className=" ".join(all_classes),
        **{k: v for k, v in kwargs.items() if k not in ["style", "className"]},
    )
