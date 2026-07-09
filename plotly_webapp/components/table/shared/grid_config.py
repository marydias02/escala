from typing import Any, Dict, List, Optional, Literal, TypedDict

import dash_ag_grid as dag
import pandas as pd

from .table_icons import default_icon_options

## ALL COLUMNS ARE ALIGNED TO THE LEFT BY DEFAULT
## ALIGNEMENT CAN BE CHANGED AD HOC
# DEFAULT_DATA_TYPE_DEFINITIONS: Dict[str, Any] = {
#     "number": {
#         "baseDataType": "number",
#         "extendsDataType": "number",
#         "columnTypes": "rightAligned",
#     },
# }

DEFAULT_GRID_OPTIONS: Dict[str, Any] = {
    "stopEditingWhenCellsLoseFocus": True,
    #"dataTypeDefinitions": DEFAULT_DATA_TYPE_DEFINITIONS,
}

# Note: This defines decimal/thousand separators and currency.
LOCALE_EURO = """d3.formatLocale({
  "decimal": ",",
  "thousands": "\\u00A0",
  "grouping": [3],
  "currency": ["", "\\u00A0€"]
})"""


def get_base_grid_options(**additional_options: Any) -> Dict[str, Any]:
    base_options = DEFAULT_GRID_OPTIONS.copy()
    base_options.update(additional_options)
    return base_options


def get_locale_formatter(format_pattern: str) -> Dict[str, str]:
    return {"function": f"{LOCALE_EURO}.format('{format_pattern}')(params.value)"}


# SOME COMMON FORMATTERS
formatter_currency = get_locale_formatter("$,.2f")  # 12 345,67 €
formatter_short = get_locale_formatter(".2s")  # 12345 -> 12k, 1250000 -> 1.3M
formatter_int = get_locale_formatter(",.0f")  # 12 346 (grouped, 0 decimals)
formatter_percent = get_locale_formatter(".1%")  # 0.123 -> 12,3 %



TableHeightMode = Literal["auto","px","vh","percent","rows","parent"]

class TableHeight(TypedDict, total=False):
    mode: TableHeightMode
    value: Optional[int]

TableOverflowMode = Literal["scroll", "paginate", "clip"]

def create_ag_grid(
    grid_id,
    data_frame,
    column_defs = None,
    dashGridOptions = None,
    *,
    height: Optional[TableHeight] = None,
    overflow: TableOverflowMode = "scroll",
    page_size: int = 25,
) -> dag.AgGrid:
    """
    height: default height is 400px
      - {"mode":"auto"}                             -> grows to content, no inner scroll
      - {"mode":"px", "value": 480}                 -> fixed pixels
      - {"mode":"vh", "value": 60}                  -> 60vh (viewport height)
      - {"mode":"percent", "value": 100}            -> 100% of parent (parent must have height)
      - {"mode":"rows", "value": 12}                -> approx N visible rows (no pagination)
      - {"mode":"parent"}                           -> fill parent; parent must define height (flex/grid)
    overflow:
      - "scroll"   -> overflow-y auto (default)
      - "paginate" -> AG Grid pagination
      - "clip"     -> overflow hidden
    page_size: used when overflow is set to 'paginate'
    """

    # Auto-generate column definitions if not provided
    if column_defs is None:
        column_defs = [{"field": col} for col in data_frame.columns]

    dash_grid_options = dict(dashGridOptions or {})

    # User defined col definitions
    user_default = dash_grid_options.get("defaultColDef", {})

    # Merge col defs default with user defined
    merged_defs = {
        **user_default,  
        "filterParams": {
            **user_default.get("filterParams", {}),
            "buttons": ["reset", "apply"],
            "closeOnApply": True,
        },
    }

    # Avoid conflicting defaultColDef from merged defenition and dashGridOptions
    dash_grid_options = {k: v for k, v in dash_grid_options.items() if k != "defaultColDef"}

    # Adjust height and overflow accordding to user defined mode

    height = height or {} # default 400px
    mode   = (height.get("mode") or "").lower()
    grid_style = {"width": "100%"}
    
    if overflow == "paginate":
        dash_grid_options["pagination"] = True
        dash_grid_options["paginationPageSize"] = page_size
        dash_grid_options["domLayout"] = "autoHeight"
    else:
        dash_grid_options["pagination"] = False
        if mode != "auto":  # autoHeight never scrolls internally
            if overflow == "scroll":
                grid_style["overflowY"] = "auto"
            elif overflow == "clip":
                grid_style["overflow"] = "hidden"
                dash_grid_options["domLayout"] = "autoHeight"

    
    # Necessary heights for 'Rows' calculation
    row_height     = int(dash_grid_options.get("rowHeight", 40))
    header_height  = int(dash_grid_options.get("headerHeight", 48))
    footer_height = int(dash_grid_options.get("footerHeight", 48))
    dash_grid_options["rowHeight"] = row_height
    dash_grid_options["headerHeight"] = header_height
    dash_grid_options["footerHeight"] = footer_height


    if mode == "auto":
        dash_grid_options["domLayout"] = "autoHeight"

    elif mode == "px":
        grid_style["height"] = f"{int(height.get('value', 400))}px"

    elif mode == "vh":
        grid_style["height"] = f"{int(height.get('value', 60))}vh"

    elif mode == "percent":
        grid_style["height"] = f"{int(height.get('value', 100))}%"

    elif mode == "rows":
        dash_grid_options["domLayout"] = "autoHeight"
        n = int(height.get("value", 10))
        grid_style["height"] = f"{header_height + n * row_height}px"

        if overflow == "paginate":
            num_rows = min(n, page_size)
            grid_style["height"] = f"{header_height + num_rows * row_height + footer_height}px"

    elif mode == "parent":
        grid_style["height"] = "100%"

   
    final_grid_options = {
        **default_icon_options,
        **get_base_grid_options(),
        **dash_grid_options,
    }


    return dag.AgGrid(
        rowData=data_frame.to_dict("records"),
        columnDefs=column_defs,
        defaultColDef=merged_defs,
        className="ag-theme-quartz",
        id=grid_id,
        dashGridOptions=final_grid_options,
        style=grid_style,
    )
