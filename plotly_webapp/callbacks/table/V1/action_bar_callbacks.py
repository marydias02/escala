import pandas as pd
from dash import Input, Output, State, callback


def register_action_bar_callbacks_v1(grid_id: str, df: pd.DataFrame) -> None:
    @callback(
        Output(grid_id, "selectedRows", allow_duplicate=True),
        [
            Input(f"{grid_id}-close-selection", "n_clicks"),
            Input(f"{grid_id}-delete-btn", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def clear_selection(close_clicks, delete_clicks):
        return []

    @callback(
        Output(grid_id, "rowData", allow_duplicate=True),
        Input(f"{grid_id}-delete-btn", "n_clicks"),
        [
            State(grid_id, "rowData"),
            State(grid_id, "selectedRows"),
        ],
        prevent_initial_call=True,
    )
    def delete_selected_rows(delete_clicks, current_row_data, selected_rows):
        if not delete_clicks or not selected_rows or not current_row_data:
            return current_row_data or df.to_dict("records")

        # Find indices in the current rowData that match selected rows
        # This works on the example/client, you might need to adjust it for your needs
        indices_to_delete = []
        for selected_row in selected_rows:
            for i, row in enumerate(current_row_data):
                if row == selected_row and i not in indices_to_delete:
                    indices_to_delete.append(i)
                    break

        updated_data = [row for i, row in enumerate(current_row_data) if i not in indices_to_delete]

        return updated_data

    @callback(
        Output(f"{grid_id}-selection-count", "children"),
        Input(grid_id, "selectedRows"),
        prevent_initial_call=False,
    )
    def update_selection_count(selected_rows):
        return str(len(selected_rows) if selected_rows else 0)

    @callback(
        Output(f"{grid_id}-action-bar", "className"),
        Input(grid_id, "selectedRows"),
        prevent_initial_call=False,
    )
    def toggle_action_bar_visibility(selected_rows):
        if selected_rows and len(selected_rows) > 0:
            return "action-bar"
        return "action-bar hidden"