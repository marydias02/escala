import uuid
from typing import Callable, Optional

import pandas as pd
from dash import Input, Output, State, callback


def register_primary_action_callback_v1(
    grid_id: str, df: pd.DataFrame, custom_callback: Optional[Callable] = None
) -> None:
    if custom_callback:
        custom_callback(grid_id, df)
    else:
        print(f"No custom callback provided for {grid_id}. Please provide a callback function.")
        pass


def create_new_row_callback_v1(grid_id: str, df):
    @callback(
        Output(grid_id, "rowData", allow_duplicate=True),
        Input(f"{grid_id}-primary-btn", "n_clicks"),
        State(grid_id, "rowData"),
        prevent_initial_call=True,
    )
    # Basic implementation, you might want to customize it further.
    def add_new_row(primary_btn_clicks, current_data):
        if not primary_btn_clicks:
            return current_data or df.to_dict("records")

        current_data = current_data or df.to_dict("records")

        if current_data and len(current_data) > 0:
            new_row = {}
            for field, value in current_data[0].items():
                if isinstance(value, (int, float)):
                    new_row[field] = 0
                elif isinstance(value, bool):
                    new_row[field] = False
                else:
                    new_row[field] = "-"
        else:
            new_row = {}

        if "id" not in new_row:
            new_row["id"] = str(uuid.uuid4())

        updated_data = [new_row] + current_data

        return updated_data


def create_export_csv_callback_v1(grid_id: str, df):
    @callback(
        Output(grid_id, "exportDataAsCsv", allow_duplicate=True),
        Input(f"{grid_id}-primary-btn", "n_clicks"),
        State(grid_id, "rowData"),
        prevent_initial_call=True,
    )
    def export_to_csv(primary_btn_clicks, current_data):
        if not primary_btn_clicks:
            return

        current_data = current_data or df.to_dict("records")
        
        export_df = pd.DataFrame(current_data)
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        filename = f"table_export_{timestamp}.csv"
        
        try:
            export_df.to_csv(filename, index=False)
            print(f"Data exported to {filename}")
        except Exception as e:
            print(f"Export failed: {str(e)}")
        
        return True