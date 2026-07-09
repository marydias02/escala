from typing import Literal, Optional, Union

from dash import dcc, html

from components.label.label import Label

Default_State = Literal["unchecked", "checked"]


def Checkbox(
    label_text: Optional[str] = None,
    show_icon: bool = False,
    default_state: Default_State = "unchecked",
    id: Optional[Union[str, dict]] = None,
) -> html.Div:
    option_label = (
        Label(
            label_text=label_text,
            show_icon=show_icon,
            as_label=False,
        )
        if (label_text or show_icon)
        else ""
    )

    checklist_props = {
        "className": "checkbox__checklist",
        "inputClassName": "checkbox__input",
        "labelClassName": "checkbox__option-label",
        "options": [
            {
                "label": option_label,
                "value": "checked",
            }
        ],
        "value": ["checked"] if default_state == "checked" else [],
    }
    if id is not None:
        checklist_props["id"] = id

    return html.Div(
        className="checkbox",
        children=[
            dcc.Checklist(**checklist_props)
        ],
    )
