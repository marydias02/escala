from typing import Any, Dict, List, Optional

from dash import Input, Output, callback

from components.table.shared.grid_config import create_ag_grid
from components.table.shared.types import TableDataFrame


def register_tab_switch_callback_v1(
    grid_id: str, 
    data_frames: List[TableDataFrame], 
    dashGridOptions: Optional[Dict[str, Any]] = None,
    *,
    height: Optional[dict] = None,
    overflow: str = "scroll",
    page_size: int = 25,

) -> None:
    @callback(
        [Output(f"{grid_id}-table-body", "children"), Output(grid_id, "filterModel")],
        Input(f"{grid_id}-tab-switcher", "value"),
        prevent_initial_call=False,
    )
    def switch_tab(selected_tab_value):
        selected_data_config = None
        for data_config in data_frames:
            if data_config.get("tab") == selected_tab_value:
                selected_data_config = data_config
                break

        if selected_data_config is None:
            selected_data_config = data_frames[0]

        updated_column_defs = selected_data_config.get("col_def")
        selected_df = selected_data_config["df"]

        ag_grid = create_ag_grid(
            grid_id=grid_id,
            data_frame=selected_df,
            column_defs=updated_column_defs,
            dashGridOptions=dashGridOptions,
            height=height,
            overflow=overflow,
            page_size=page_size,
        )

        return ag_grid, {}
