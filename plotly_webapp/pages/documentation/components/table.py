import dash
from dash import html
from dash.dcc import Tab, Tabs

from callbacks.table.V1.primary_action_callback import (
    create_export_csv_callback_v1,
    create_new_row_callback_v1,
)
from callbacks.table.V1.secondary_actions_callback import (
    create_export_csv_secondary,
)
from components.table.shared.action_bar import action_bar
from components.table.shared.col_def_config import (
    create_monthly_column_def,
    create_simple_table_column_defs,
    create_yearly_column_def,
)
from components.table.V1.table import Table as TableV1
from utils.table.data_loader import (
    get_brand_and_year_columns,
    load_group_table_data,
    load_main_table_data,
)

dash.register_page(
    __name__,
    path="/components/table",
    title="Table",
)


df = load_main_table_data()
df2 = load_group_table_data()

brand_cols, year_cols = get_brand_and_year_columns(list(df2.columns))

monthly_column_defs = [create_monthly_column_def(col, year_cols) for col in df.columns]
yearly_column_defs = [create_yearly_column_def(col, year_cols) for col in df.columns]
simple_table_column_defs = create_simple_table_column_defs(brand_cols, year_cols)

layout = html.Div(
    [
        TableV1(
            data_frames=[
                {"df": df, "col_def": monthly_column_defs, "tab": "monthly"},
                {"df": df, "col_def": yearly_column_defs, "tab": "yearly"},
            ],
            grid_id="mvp-table-1",
            title="Tabbed Table",
            dashGridOptions={
                "rowSelection": {
                    "mode": "multiRow",
                    "enableClickSelection": True,
                },
            },
            action_bar=action_bar,
            tabs=Tabs(
                value="monthly",
                children=[
                    Tab(
                        label="Monthly",
                        value="monthly",
                        className="lucide--table-2",
                    ),
                    Tab(
                        label="Yearly",
                        value="yearly",
                        className="lucide--table-2",
                    ),
                ],
            ),
            banner={"text": "You can edit this table.", "variant": "positive", "icon": "lucide:check"},
            primary_action=("Export CSV", create_export_csv_callback_v1),
            note="Updated 5 days ago",
            enable_reset=True,
        ),
        TableV1(
            data_frames=[
                {"df": df2, "col_def": simple_table_column_defs},
            ],
            grid_id="mvp-table-2-export",
            title="Grouped Table",
            primary_action=("New Row", create_new_row_callback_v1),
            secondary_actions=[("Export CSV", "lucide:download", create_export_csv_secondary)],
            action_bar=action_bar,
            note="This table is not editable, but can be exported.",
            dashGridOptions={
                "rowSelection": {
                    "mode": "singleRow",
                    "headerCheckbox": False,
                    "checkboxes": False,
                    "enableClickSelection": True,
                },
            },
        ),
        TableV1(
            data_frames=[
                {
                    "df": [
                        {"Priority": "High", "Date": "2025-10-09", "2024": 12345.67},
                        {"Priority": "Low", "Date": "2025-10-08", "2024": 890.12},
                    ]
                },
            ],
            grid_id="table-json",
            title="Simple json table, all auto-generated",
            note="This table has no optional props.",
            action_bar=action_bar,
            secondary_actions=[("Export CSV", "lucide:download", create_export_csv_secondary)],
            dashGridOptions={
                "rowSelection": {
                    "mode": "singleRow",
                    "headerCheckbox": False,
                    "checkboxes": False,
                    "enableClickSelection": True,
                },
            },
        ),
        TableV1(
            data_frames=[
                {"df": []},
            ],
            grid_id="table-api-empty",
            title="This table has no data. It can be populated via api",
            note="This table has no optional props.",
        ),
    ],
)
