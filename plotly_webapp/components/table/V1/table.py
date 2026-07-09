from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import pandas as pd
from dash import dcc, html

from callbacks.table.V1.action_bar_callbacks import register_action_bar_callbacks_v1
from callbacks.table.V1.filter_display_callback import register_filter_display_callback_v1
from callbacks.table.V1.primary_action_callback import register_primary_action_callback_v1
from callbacks.table.V1.refresh_callback import register_refresh_callback_v1
from callbacks.table.V1.secondary_actions_callback import register_secondary_actions_callbacks_v1
from callbacks.table.V1.tab_switch_callback import register_tab_switch_callback_v1
from components.table.shared.grid_config import create_ag_grid
from components.table.shared.types import MessageConfig, TableDataFrame

from .table_header import create_table_header_section


def normalize_data_frame(
        data_config: TableDataFrame) -> TableDataFrame:
    df_obj = data_config["df"]

    # Convert to DataFrame if needed
    if isinstance(df_obj, list):
        if not df_obj:
            # Empty list - create empty DataFrame with proper columns
            columns = (
                    [c.get("field") for c in
                     data_config.get("col_def", []) if
                     "field" in c] or
                    list(data_config.get("columns", []))
            )
            df = pd.DataFrame(columns=columns)
        else:
            # JSON records
            df = pd.json_normalize(df_obj) if isinstance(df_obj[0],
                                                         dict) else pd.DataFrame(
                df_obj)
    elif isinstance(df_obj, pd.DataFrame):
        df = df_obj
    else:
        raise ValueError(
            f"Unsupported data type: {type(df_obj)}. Expected DataFrame or list of dicts.")

    # Generate column definitions if missing
    col_def = data_config.get("col_def")
    if not col_def:
        columns = list(df.columns) or list(
            data_config.get("columns", []))
        col_def = [{"field": col} for col in columns]

    return {
        **data_config,
        "df": df,
        "col_def": col_def,
        "tab": data_config.get("tab")
    }


def Table(
        data_frames: List[TableDataFrame],
        grid_id: str = "data-grid",
        title: Optional[str] = None,
        dashGridOptions: Optional[Dict[str, Any]] = None,
        tabs: Optional[dcc.Tabs] = None,
        primary_action: Optional[Tuple[str, Callable]] = None,
        action_bar: Optional[Callable[[str], html.Aside]] = None,
        banner: Optional[MessageConfig] = None,
        note: Optional[str] = None,
        enable_reset: bool = False,
        secondary_actions: Optional[
            List[Tuple[str, str, Callable]]] = None,
        height: Optional[dict] = None,
        overflow: str = "scroll",
        page_size: int = 25,
) -> html.Div:
    """
    height:
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
    """
     
    if not data_frames:
        raise ValueError("data_frames must be a non-empty list")

    # Normalize all data frames upfront
    normalized_data_frames = []
    for i, data_config in enumerate(data_frames):
        if not isinstance(data_config,
                          dict) or "df" not in data_config:
            raise ValueError(
                f"data_frames[{i}] must be a dictionary with 'df' key")

        try:
            normalized_data_frames.append(
                normalize_data_frame(data_config))
        except Exception as e:
            raise ValueError(
                f"Error processing data_frames[{i}]: {e}")

    primary_data_config = normalized_data_frames[0]
    primary_df = primary_data_config["df"]

    if action_bar is not None:
        register_action_bar_callbacks_v1(grid_id, primary_df)

    primary_action_msg = None
    primary_action_fn = None

    if primary_action:
        primary_action_msg, primary_action_fn = primary_action
        register_primary_action_callback_v1(grid_id, primary_df,
                                            primary_action_fn)

    if tabs is not None:
        tabs = dcc.Tabs(
            id=f"{grid_id}-tab-switcher",
            value=getattr(tabs, "value", None),
            className="segmented-control segmented-control--small",
            children=getattr(tabs, "children", []),
        )
        register_tab_switch_callback_v1(
            grid_id,
            normalized_data_frames,
            dashGridOptions=dashGridOptions,
            height=height,
            overflow=overflow,
            page_size=page_size,)

    if enable_reset:
        register_refresh_callback_v1(grid_id, primary_df)

    if secondary_actions:
        register_secondary_actions_callbacks_v1(grid_id, primary_df,
                                                secondary_actions)

    register_filter_display_callback_v1(grid_id)

    return build_table_layout(
        normalized_data_frames,
        grid_id,
        title,
        tabs,
        primary_action_msg or "",
        banner,
        action_bar,
        dashGridOptions,
        note or "",
        enable_reset,
        secondary_actions,
        height=height,
        overflow=overflow,
        page_size=page_size,
    )


def build_table_body(
        grid_id: str,
        data_frame: pd.DataFrame,
        column_defs: Optional[List[Dict[str, Any]]] = None,
        action_bar: Optional[Callable[[str], html.Aside]] = None,
        dashGridOptions: Optional[Dict[str, Any]] = None,
        height: Optional[dict] = None,
        overflow: str = "scroll",
        page_size: int = 25,
) -> html.Div:
    grid_component = create_ag_grid(
        grid_id=grid_id,
        data_frame=data_frame,
        column_defs=column_defs,
        dashGridOptions=dashGridOptions,
        height=height,
        overflow=overflow,
        page_size=page_size,

    )

    table_body_container = html.Div([grid_component],
                                    id=f"{grid_id}-table-body")

    container_children: list = [table_body_container]

    if action_bar is not None:
        container_children.append(action_bar(grid_id))

    return html.Div(container_children)


def build_table_layout(
        data_frames: List[TableDataFrame],
        grid_id: str = "data-grid",
        title: Optional[str] = None,
        tabs: Optional[dcc.Tabs] = None,
        primary_action: Optional[str] = None,
        banner: Optional[MessageConfig] = None,
        action_bar: Optional[Callable[[str], html.Aside]] = None,
        dashGridOptions: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        enable_reset: bool = False,
        secondary_actions: Optional[
            List[Tuple[str, str, Callable]]] = None,
        height: Optional[dict] = None,
        overflow: str = "scroll",
        page_size: int = 25,
) -> html.Div:
    primary_data_config = data_frames[0]
    primary_df = primary_data_config["df"]
    primary_column_defs = primary_data_config.get("col_def")

    layout_components = []

    if action_bar is not None:
        layout_components.append(action_bar(grid_id))

    has_header_content = any([
        title,
        tabs,
        primary_action,
        banner,
        note,
        enable_reset,
        secondary_actions,
    ])

    secondary_actions_for_header = None
    if secondary_actions:
        secondary_actions_for_header = [(label, icon) for
                                        label, icon, _ in
                                        secondary_actions]

    if has_header_content:
        header_class_name = "table-header"
    else:
        header_class_name = "table-header table-header--filters-only"

    layout_components.append(
        create_table_header_section(
            grid_id,
            title,
            tabs,
            primary_action,
            banner,
            note,
            enable_reset,
            secondary_actions_for_header,
            class_name=header_class_name,
        )
    )


    layout_components.append(
        build_table_body(
            grid_id, 
            primary_df, 
            primary_column_defs,
            None, 
            dashGridOptions,
            height=height, 
            overflow=overflow, 
            page_size=page_size))
    return html.Div(layout_components, className="table-container")
