from dash import Input, Output, callback, dcc, html
from dash_iconify import DashIconify


def Breadcrumb():
    return html.Nav(
        html.Ul(
            id="breadcrumb",
            className="breadcrumb",
        ),
        className="breadcrumb body-sm",
    )


def build_breadcrumb_items(pathname: str):
    if not pathname or pathname == "/":
        return [("Extraction", "/")]

    parts = pathname.strip("/").split("/")
    links = []
    for i in range(len(parts)):
        label = parts[i].replace("-", " ").capitalize()
        href = "/" + "/".join(parts[: i + 1])
        links.append((label, href))

    return [("Extraction", "/")] + links


def build_breadcrumb_content(label):
    if label == "Home":
        return [DashIconify(icon="lucide:scan-text"), html.Span(label, className="breadcrumb__text")]
    return html.Span(label, className="breadcrumb__text")


@callback(
    Output("breadcrumb", "children"),
    Input("url", "pathname"),
)
def update_breadcrumb(pathname):
    items = build_breadcrumb_items(pathname)
    has_middle = len(items) >= 3

    def make_arrow():
        return DashIconify(icon="lucide:chevron-right", className="breadcrumb__arrow")

    def make_element(label, href):
        link_classes = "breadcrumb__link"
        if label == "Home":
            link_classes += " breadcrumb__link--home"
        if href != pathname:
            return dcc.Link(build_breadcrumb_content(label), href=href, className=link_classes)
        return html.Span(build_breadcrumb_content(label), className=f"{link_classes} breadcrumb__active")

    breadcrumb_elements = []
    for idx, (label, href) in enumerate(items):
        is_last = idx == len(items) - 1
        is_middle = has_middle and 0 < idx < len(items) - 1
        li_class = "breadcrumb__item--middle" if is_middle else None
        li_children = [make_element(label, href)] + ([] if is_last else [make_arrow()])
        breadcrumb_elements.append(html.Li(li_children, className=li_class))

    if has_middle:
        ellipsis_li = html.Li(
            [html.Span("…", className="breadcrumb__ellipsis"), make_arrow()],
            className="breadcrumb__item--collapsed",
        )
        breadcrumb_elements.insert(1, ellipsis_li)

    return breadcrumb_elements
