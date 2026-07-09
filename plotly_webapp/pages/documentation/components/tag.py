import dash
from dash import html

from components.tag.tag import Tag

dash.register_page(
    __name__,
    path="/components/tag",
    title="Tag",
)

layout = html.Div(
    [
        Tag("Default", icon="lucide:square-asterisk", size="xs", id="tag-default-xs"),
        Tag("Standard", icon="lucide:square-asterisk", variant="fill", size="xs", id="tag-standard-xs"),
        Tag("Positive", icon="lucide:square-asterisk", variant="positive", size="xs", id="tag-positive-xs"),
        Tag("Mild", icon="lucide:square-asterisk", variant="mild", size="xs", id="tag-mild-xs"),
        Tag("Negative", icon="lucide:square-asterisk", variant="negative", size="xs", id="tag-negative-xs"),
        Tag("Default", icon="lucide:square-asterisk", size="2xs", id="tag-default-2xs"),
        Tag("Standard", icon="lucide:square-asterisk", variant="fill", size="2xs", id="tag-standard-2xs"),
        Tag("Positive", icon="lucide:square-asterisk", variant="positive", size="2xs", id="tag-positive-2xs"),
        Tag("Mild", icon="lucide:square-asterisk", variant="mild", size="2xs", id="tag-mild-2xs"),
        Tag("Negative", icon="lucide:square-asterisk", variant="negative", size="2xs", id="tag-negative-2xs"),
        Tag("Default", icon="lucide:square-asterisk", size="xs", id="tag-default-xs-disabled", disabled=True),
        Tag(
            "Standard",
            icon="lucide:square-asterisk",
            variant="fill",
            size="xs",
            id="tag-standard-xs-disabled",
            disabled=True,
        ),
        Tag(
            "Positive",
            icon="lucide:square-asterisk",
            variant="positive",
            size="xs",
            id="tag-positive-xs-disabled",
            disabled=True,
        ),
        Tag("Mild", icon="lucide:square-asterisk", variant="mild", size="xs", id="tag-mild-xs-disabled", disabled=True),
        Tag(
            "Negative",
            icon="lucide:square-asterisk",
            variant="negative",
            size="xs",
            id="tag-negative-xs-disabled",
            disabled=True,
        ),
        Tag("Default", icon="lucide:square-asterisk", size="2xs", id="tag-default-2xs-disabled", disabled=True),
        Tag(
            "Standard",
            icon="lucide:square-asterisk",
            variant="fill",
            size="2xs",
            id="tag-standard-2xs-disabled",
            disabled=True,
        ),
        Tag(
            "Positive",
            icon="lucide:square-asterisk",
            variant="positive",
            size="2xs",
            id="tag-positive-2xs-disabled",
            disabled=True,
        ),
        Tag(
            "Mild", icon="lucide:square-asterisk", variant="mild", size="2xs", id="tag-mild-2xs-disabled", disabled=True
        ),
        Tag(
            "Negative",
            icon="lucide:square-asterisk",
            variant="negative",
            size="2xs",
            id="tag-negative-2xs-disabled",
            disabled=True,
        ),
    ],
    style={
        "display": "flex",
        "flexDirection": "column",
        "gap": "20px",
        "alignItems": "start",
    },
)
