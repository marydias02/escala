
import dash
from dash import html
from dash_iconify import DashIconify

from components.banner.banner import Banner, TableBanner
from components.section.section import Section
from utils.base.grid_system.grid import Col, Container

dash.register_page(
    __name__,
    path="/components/breadcrumb",
    title="BreadCrumb",
)

layout = html.Div([
  html.H1("BreadCrumb Page", className="heading-1"),
  html.Br(),
  html.Br(),
  html.H2("This is the normal Breadcrumb that is shown on top of every Page", className="heading-2"),
  html.Br(),
  html.P("This is is defined on the general app layout page and is automatically rendered in each page", className="body-sm"),
  html.Br(),
  html.P([
        DashIconify(icon="lucide:house"),
        html.Span("Home"),
        DashIconify(icon="lucide:chevron-right", className="breadcrumb__arrow"),
        html.Span("Middle Page"),
        DashIconify(icon="lucide:chevron-right", className="breadcrumb__arrow"),
        html.Span("Current Page"),
    ],
    className="breadcrumb",
    style={"display":"flex" , "gap":"4px", "padding" : "8px", "border-radius":"8px" , "background":"var(--surface-light)"}
    ),
    html.Br(),
    html.Br(),
    html.H2("This is the colapsed Breadcrumb shown on smaller screens", className="heading-2"),
  html.Br(),
  html.P("When viewport width is less than 790px and the bredcrumb has 3 or more items it collapses to show only the first and last one. This width is defined on the component page and can be adjusted if necessary", className="body-sm"),
  html.Br(),
  html.P([
        DashIconify(icon="lucide:house"),
        html.Span("Home"),
        DashIconify(icon="lucide:chevron-right", className="breadcrumb__arrow"),
        html.Span("..."),
        DashIconify(icon="lucide:chevron-right", className="breadcrumb__arrow"),
        html.Span("Current Page"),
    ],
    className="breadcrumb",
    style={"display":"flex" , "gap":"4px", "padding" : "8px", "border-radius":"8px" , "background":"var(--surface-light)"}
    ),
])

