import pandas as pd
from dash import Input, Output, callback
from dash.exceptions import PreventUpdate


def register_refresh_callback_v1(grid_id: str, original_df: pd.DataFrame) -> None:
    @callback(
        Output(f"{grid_id}-refresh-btn", "disabled"),
        [
            Input(grid_id, "rowData"),
            Input(grid_id, "filterModel"),
        ],
        prevent_initial_call=True,
    )
    def toggle_refresh_btn_visibility(current_row_data, current_filter_model):
        if current_row_data is None:
            return True  # Disable button

        if current_filter_model and len(current_filter_model) > 0:
            return False  # Enable button (filters applied)

        original_data = original_df.to_dict("records")

        # Check if data has changed
        if len(current_row_data) != len(original_data):
            return False  # Enable button (data changed)

        # Compare each row
        for row_cur, row_orig in zip(current_row_data, original_data):
            if row_cur != row_orig:
                return False  # Enable button (data changed)

        return True  # Disable button (no changes and no filters)

    @callback(
        [
            Output(grid_id, "rowData", allow_duplicate=True),
            Output(grid_id, "filterModel", allow_duplicate=True),
        ],
        Input(f"{grid_id}-refresh-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def refresh_table_v1(refresh_clicks):
        if refresh_clicks:
            original_data = original_df.to_dict("records")
            empty_filter_model = {}
            return original_data, empty_filter_model

        raise PreventUpdate
