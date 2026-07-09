from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import dash
from dash import html
from components.checkbox.checkbox import Checkbox

dash.register_page(
    __name__,
    path="/components/checkbox",
    title="Checkbox",
)


layout = html.Div(
    [
        html.H3("Checkbox with dcc.Checklist", className="body-md"),
        html.P(
            "Exemplos da versao com Label() dentro do checklist nativo.",
            className="body-sm",
        ),
        html.Div(
            [
                html.Div(),
                html.P("Unchecked", className="body-sm"),
                html.P("Checked", className="body-sm"),
            ],
            style={
                "display": "grid",
                "gridTemplateColumns": "220px max-content max-content",
                "columnGap": "var(--spacing-24)",
                "rowGap": "var(--spacing-12)",
                "alignItems": "center",
                "justifyContent": "start",
            },
        ),
        html.Div(
            [
                html.P("With icon in label", className="body-sm"),
                Checkbox(label_text="Label", show_icon=True, default_state="unchecked"),
                Checkbox(label_text="Label", show_icon=True, default_state="checked"),
                html.P("Without icon in label", className="body-sm"),
                Checkbox(label_text="Label", show_icon=False, default_state="unchecked"),
                Checkbox(label_text="Label", show_icon=False, default_state="checked"),
            ],
            style={
                "display": "grid",
                "gridTemplateColumns": "220px max-content max-content",
                "columnGap": "var(--spacing-24)",
                "rowGap": "var(--spacing-20)",
                "alignItems": "center",
                "justifyContent": "start",
                "marginTop": "var(--spacing-16)",
            },
        ),
    ],
    style={
        "display": "flex",
        "flexDirection": "column",
        "gap": "var(--spacing-16)",
    },
)
