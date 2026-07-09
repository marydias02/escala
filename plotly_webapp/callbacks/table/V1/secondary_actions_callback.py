from typing import Callable, List, Tuple

import pandas as pd


def register_secondary_actions_callbacks_v1(
    grid_id: str,
    primary_df: pd.DataFrame,
    secondary_actions: List[Tuple[str, str, Callable]],
) -> None:
    for label, icon, callback_fn in secondary_actions:
        # Slugify the label to match the ID generation in table_header.py
        slug_label = label.lower().replace(" ", "-").replace("/", "-")
        button_id = f"{grid_id}-secondary-{slug_label}-btn"
        if callback_fn:
            callback_fn(button_id, grid_id, primary_df)
        else:
            print(f"No callback provided for secondary action {label}. Please provide a callback function.")


def create_export_csv_secondary(button_id: str, grid_id: str, df: pd.DataFrame):
    from dash import Input, Output, callback

    @callback(
        Output(grid_id, "exportDataAsCsv", allow_duplicate=True),
        Input(button_id, "n_clicks"),
        prevent_initial_call=True,
    )
    def export_csv_secondary(n_clicks):
        if n_clicks:
            return True
        return False
    

### EXAMPLE CALLBACKS FOR SECONDARY ACTIONS

# Quick filter - filters data according to a specified value (independent of the column)
def create_quickfilter_secondary(
        button_id:str, 
        grid_id:str, 
        df: pd.DataFrame, 
        value:str = "2024"
    ):
    from dash import Input, Output, callback
    @callback(
        Output(grid_id, "quickFilterText"),
        Input(button_id, "n_clicks"),
        prevent_initial_call=True,
    )
    def _(_n):
        return value


# Sort - sorts data according to specified column and direction
def create_sort_secondary(
        button_id:str, 
        grid_id:str, 
        df: pd.DataFrame, 
        col_id:str = "Priority", 
        direction:str = "asc"
    ):
    from dash import Input, Output, callback
    @callback(
        Output(grid_id, "columnState"),
        Input(button_id, "n_clicks"),
        prevent_initial_call=True,
    )
    def _(_n):
        return [{"colId": col_id, "sort": direction}]
    

# Reset quick filter
def create_reset_secondary(
        button_id:str, 
        grid_id:str, 
        df: pd.DataFrame,
    ):
    from dash import Input, Output, callback

    @callback(
        Output(grid_id, "quickFilterText", allow_duplicate=True),
        Output(grid_id, "columnState", allow_duplicate=True),
        Output(grid_id, "sortModel", allow_duplicate=True),
        Input(button_id, "n_clicks"),
        prevent_initial_call=True,
    )
    def _(_n):
        return "", [], []
    
