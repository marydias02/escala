from datetime import datetime
from typing import Any, Dict, Optional

from dash import Input, Output, callback, html
from dash_iconify import DashIconify


def register_filter_display_callback_v1(grid_id: str) -> None:
    @callback(
        Output(f"{grid_id}-filter-display", "children"),
        Input(grid_id, "filterModel"),
        prevent_initial_call=True,
    )
    def display_active_filters(filter_model: Optional[Dict[str, Any]]):
        filter_chips = []
        for column, filter_config in (filter_model or {}).items():
            chip_text = _format_filter_text(filter_config)
            if chip_text:
                icon = _get_column_icon_for_filter(column, filter_config)

                chip = html.Div(
                    [
                        icon,
                        html.Span(
                            [
                                html.Span(f"{column}: "),
                                html.Span(chip_text, className="filters__filter-chip__value"),
                            ],
                            className="body-sm",
                        ),
                    ],
                    className="filters__filter-chip",
                )
                filter_chips.append(chip)

        if not filter_chips:
            return

        return html.Div(filter_chips, className="table-header__active-filters visible filter-model")


def _format_filter_text(filter_config: Dict[str, Any]) -> str:
    # print(filter_config) FIXME: Print to show the filter object
    if filter_config.get("filterType") == "date":

        def fmt(d):
            if not d:
                return None
            try:
                return datetime.fromisoformat(str(d)).date().isoformat()
            except Exception:
                return str(d)[:10]

        a = fmt(filter_config.get("dateFrom"))
        b = fmt(filter_config.get("dateTo"))

        if filter_config.get("type") == "inRange":
            if a and b:
                return f"{a} to {b}"
            return a or b or "filtered"
        return a or b or "filtered"

    # Boolean, if rendered as string
    if filter_config.get("filterType") == "text":
        value = filter_config.get("type")
        if value is not None:
            if str(value).lower() in ("true", "false"):
                return str(value).lower()

    if filter_config.get("type") == "blank":
        return "is blank"
    if filter_config.get("type") == "notBlank":
        return "is not blank"

    # Handle multiple conditions (e.g., for 'OR'/'AND' filters)
    if "conditions" in filter_config and isinstance(filter_config["conditions"], list):
        operator = filter_config.get("operator", "OR")
        condition_texts = []
        for cond in filter_config["conditions"]:
            cond_text = _format_filter_text(cond)
            if cond_text:
                condition_texts.append(cond_text)
        if condition_texts:
            return f" {operator} ".join(condition_texts)

    # Can remove the helper text such as "contains", "equals", etc, by removing filter_type from below
    value = filter_config.get("filter")
    filter_type = filter_config.get("type")

    if value is not None and filter_type:
        formatted_filter_type = "".join((" " + c.lower()) if c.isupper() else c for c in str(filter_type)).strip()
        return f"{formatted_filter_type} {value}"
    if value is not None:
        return str(value)

    return "filtered"


def _get_column_icon_for_filter(column_name: str, filter_type: Dict[str, Any]) -> DashIconify:
    type = filter_type.get("filterType")
    value = filter_type.get("type")

    if value == "true" or value == "false":
        return DashIconify(icon="lucide:circle-dashed", width=16)

    if type:
        ft = type.lower()
        by_type = {
            "date": "lucide:calendar",
            "number": "lucide:hash",
            "text": "lucide:case-sensitive",
            "boolean": "lucide:circle-dashed",
        }
        return DashIconify(icon=by_type.get(ft, "lucide:filter"), width=16)

    # Fallback: infer from column name
    col_lower = column_name.lower()
    if any(p in col_lower for p in ["date", "time", "datetime", "timestamp", "created", "updated"]):
        return DashIconify(icon="lucide:calendar", width=16)
    if any(p in col_lower for p in ["id", "count", "amount", "price", "value", "score", "year", "2024", "2023"]):
        return DashIconify(icon="lucide:hash", width=16)
    if any(p in col_lower for p in ["priority", "status", "state", "active", "enabled", "is_", "has_"]):
        return DashIconify(icon="lucide:circle-dashed", width=16)
    return DashIconify(icon="lucide:case-sensitive", width=16)
