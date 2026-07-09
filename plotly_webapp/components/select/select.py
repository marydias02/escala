import dash
from dash import html, dcc

from typing import Any, Dict, Literal, Optional, Union, List


SelectColorMode = Literal["default", "custom_light"]



def Select(
    *,
    select_options: Union[Dict[str, Any], List[Dict[str, Any]]],
    value: Optional[Union[str, Dict[str, Any], List[Any]]] = None,
    placeholder: Optional[str] = None,
    multi: bool = False,
    clearable: bool = True,
    closeOnSelect: bool = True,
    disabled: bool = False,
    searchable: bool = True,
    id_select: Optional[str] = None,
    wrapper_className: Optional[str] = None,
    select_color_mode: SelectColorMode = "default",
    select_background_color: Optional[str] = None,
    label: Optional[str] = None,
    additional_message: Optional[str] = None,
    has_error: bool = False,
    error_message: Optional[str] = None,
    **kwargs: Any,
) -> html.Div:
    """
    Reusable select component :
    - select_options: dictionary with label, value and disabled bool
    - value: optional 'lable' from the select options that appears selected as defualt

    Different select options:
    - placeholder
    - multi
    - clearable
    - closeOnSelect
    - disabled
    - searchable

    IDs and Additional Classes:
    - id_select
    - wrapper_className

    Select Color:
    - select_color_mode: can be default or custom_light
    - select_background_color: when select_color_mode="custom_light" the background color needs to be defined as var(--color)

    Optional Messages:
    - optional label
    - optonal additional message bellow the select
    - optional error state and message that can be activated with the has_error boolean
    """

    if isinstance(select_options, dict):
        options_treated = [{"label": k, "value": v, "disabled": False}
        for k, v in select_options.items()
        ]
    elif isinstance(select_options, list):
        if all(not isinstance(opt, dict) for opt in select_options):
            options_treated = [
                {"label": str(opt), "value": opt, "disabled": False}
                for opt in select_options
            ]

        else:
            options_treated = select_options
    else:
        raise ValueError("select_options must be a dict or a list")

    value_treated = None

    if value is None:
        value_treated = None

    elif isinstance(value, dict):
        vals = list(value.values())
        value_treated = vals if multi else (vals[0] if vals else None)

    elif isinstance(value, str):
        value_treated = [value] if multi else value

    elif isinstance(value, list):
        value_treated = value

    dropdown_args: Dict[str, Any] = {
        "options": options_treated,
        "placeholder": placeholder,
        "clearable": clearable,
        "multi": multi,
        "closeOnSelect": closeOnSelect,
        "disabled": disabled,
        "searchable": searchable,
        **kwargs,
    }

    if value_treated is not None:
        dropdown_args["value"] = value_treated

    if id_select is not None:
        dropdown_args["id"] = id_select

    # --- Select Colors ---
    wrapper_classes: List[str] = ["select"]  # base

    if select_color_mode == "custom_light":
        wrapper_classes.append("select--light")

    if has_error:
        wrapper_classes.append("select--error")

    if wrapper_className:
        wrapper_classes.append(wrapper_className)

    wrapper_class_str = " ".join(wrapper_classes)

    wrapper_style = {}

    if select_color_mode == "default":
        wrapper_style["--select-background"] = "var(--white)"

    elif select_color_mode == "custom_light":
        if select_background_color is None:
            raise ValueError(
                "Light select_color_mode requires 'select_background_color' (a CSS color variable)."
            )
        wrapper_style["--select-background"] = select_background_color

    # --- Compile all elements ---
    children: List[Any] = []

    label_id = f"{id_select}-label" if id_select else None
    additional_message_id = f"{id_select}-additional-message" if id_select else None
    error_message_id = f"{id_select}-error-message" if id_select else None

    if label is not None:
        label_props: Dict[str, Any] = {"className": "select-label"}
        if label_id is not None:
            label_props["id"] = label_id
        children.append(html.P(label, **label_props))

    children.append(dcc.Dropdown(**dropdown_args))

    if additional_message is not None:
        add_msg_props: Dict[str, Any] = {"className": "select-additional_message"}
        if additional_message_id is not None:
            add_msg_props["id"] = additional_message_id
        children.append(html.P(additional_message, **add_msg_props))

    if has_error and error_message is not None:
        error_msg_props: Dict[str, Any] = {"className": "select--error-message"}
        if error_message_id is not None:
            error_msg_props["id"] = error_message_id
        children.append(html.P(error_message, **error_msg_props))


    return html.Div(children=children, className=wrapper_class_str, style=wrapper_style)


