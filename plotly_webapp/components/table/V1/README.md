# TableV1 Component

The initial iteration of the Table, now containing a filter_display_area in the header, to display currently selected filters.

### Core Props

#### `data_frames` (Required)

A list of dictionaries containing:

- `df`: The data source (DataFrame, list of dictionaries, json, empty)
- `col_def`: (Optional) AG Grid column definitions
  - Auto-generated if not provided
  - Supports custom formatters (e.g., currency)
  - Custom cells and headers available (see Priority column example)
  - Custom editors supported
  - Cell components defined in `scripts/` folder
- `tab`: (Optional) Value matching a dcc.Tab for tabbed views
  - Note: Consider data persistence strategy when using tabs with CRUD operationslt on AG Grid for Dash applications.

## Quick Start

The table requires only two props to function:

- `data_frames`: Your data source
- `grid_id`: A unique identifier for the table

All other props are optional and add additional functionality.

### Basic Example

```
TableV1(
    data_frames=[
        {"df": []},
    ],
    grid_id="table-api-empty",
),
```

**Table with all props:**

```
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
        "defaultColDef": {
          "filter": True,
          "sortable": True,
          "resizable": True,
          "flex":1,
        },
        "dataTypeDefinitions": {
          "number": {
            "baseDataType": "number",
            "extendsDataType": "number",
            "columnTypes": "leftAligned",
          }
        },
    },
    action_bar=action_bar,
    height={"mode": "px", "value": 480},
    overflow = "paginate",
    page_size = 20,
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
    secondary_actions=[
      ("Filter 2024", "lucide:filter", partial(create_quickfilter_secondary, value="High")),
      ("Priority Asc", "lucide:arrow-down-up", partial(create_sort_secondary, col_id="Priority", direction="asc")),
      ("Reset", "lucide:brush-cleaning", create_reset_secondary),
    ],
    note="Updated 5 days ago",
    enable_reset=True,
),
```

### Props details

- **data_frames**:
  - list of dicts with **df** (in the example, I'm using DataFrame),
  - optional **col_def** (AG Grid defs, auto-built if missing)
    - In the example, there's several examples using custom **formatters** (for currency, for instance), declared in the `grid_config.py` file.
    - **Custom cells and header** (on the Priority column - different colored cells and header with icon), and **custom editor** (Priority only edits between High, Medium and Low). The custom cells are defined in the `scripts/` folder. The current implementations are on `customTableCells.js`
  - optional **tab** - the dcc.Tab value associated with the current df.
    - If using tabs and CRUD operations at the same time, consider adding a way to maintain data between toggles.

```
{"df": some_pandas_df, "col_def": col_def }
{"df": [{"Priority": "High", "Consumers": 1200, "Date": "2025-10-09", "2024": 123.45}]}

# Empty list (API returns nothing yet) — provide col_def if you want visible headers
{
  "df": [],
  "col_def": [{"field": "Priority"}, {"field": "Consumers"}, {"field": "Date"}, {"field": "2024"}]
}

{"df": some_df, "tab": "overview"}
{"df": other_df, "tab": "details"}
```

- **grid_id**: base ID (default data-grid) used for the grid and all generated controls—keep it unique per table instance.
- **title**: heading text rendered in the table header.
- **dashGridOptions**: dict merged into defaults dash grid options, found in grid_config.py file. You can pass different row selections, data type definitions and your custom defaultColDef. Please check if the defaults suit your application, and change as needed or pass your using dashGridOptions!
- **tabs**: optional dcc.Tabs; re-wrapped with ID \<grid_id\>-tab-switcher and paired with the tab-switch callback. Each tab’s value must align with a data_frame\["tab"\].
  - That way, we guarantee the id is unique and associated with the current table.
  - The callbacks associated with tabs are found in tab_switch_callback.py
  - Default id: "{grid_id}-tab-switcher"
  - Currently, the tabs resets the filters and modifications to rowData.
- **primary_action**: (label, callback) tuple. Adds a primary button and registers you callback. You need both.
  - For the example, I made new row and export callbacks, but you can change them for whatever you need! You can see them/register your own callbacks at primary_action_callback.py
  - The default id for this button is "{grid_id}-primary-btn"
  - Right now the callbacks target rowData
- **action_bar**: Adds a bar at the bottom of the page, depending on row selection. You can modify this file to your liking, the current behaviours were made for the example, and you might need to change them to suit your app!

  - Currently it shows the number of selected rows, and deletes them in the rowData.
  - You can edit the callbacks at action_bar_callback.py
  - The default id for visibility is "{grid_id}-action-bar", the delete button is "{grid_id}-delete-btn", and the count is "{grid_id}-selection-count"
  - Right now the callbacks target rowData.
  - To use the action bar, you need to allow some sort of row selection. For instance:

    ```
    	dashGridOptions={
    		"rowSelection": "multiple",
    	},
    ```

- **banner**: optional dict { "text": str, "variant"?: MessageVariant, "icon"?: str } shown as a TableBanner, having the same properties.

  - variant can be positive, neutral, negative, warning, dark
  - icon should be from lucide-icon: https://icon-sets.iconify.design/lucide/
  - Example:

    ```
    banner={"text": "You can edit this table.", "variant": "positive", "icon": "lucide:check"},
    ```

- **note**: helper text displayed near the table title. It's more discreet than the banner.
- **enable_reset**: toggles the reset button and registers refresh callbacks driven by the original dataframe. Currently, it resets the table to the original state.
  - You can check and modify the callback at refresh_callback.py
  - The default id for the button is "{grid_id}-refresh-btn"
- **secondary_actions**: list of (label, icon, callback_factory) tuples. Adds icon-only header buttons and registers your function. They are displayed besides reset and primary button.
  - The label will be used for the id registration, by slugifying it (spaces become underscores)
  - The default id is "{grid_id}-secondary-{slug_label}-btn"
  - icon should be from lucide-icon: https://icon-sets.iconify.design/lucide/
- **height**: optional dict controlling table height and layout.
  - `{"mode": "auto"}` -> grows to content, no inner scroll.
  - `{"mode": "px", "value": 480}` -> fixed pixels (default behavior is 400px if value is omitted).
  - `{"mode": "vh", "value": 60}` -> percentage of viewport height (default behavior is 60vh if value is omitted).
  - `{"mode": "percent", "value": 100}` -> percentage of parent container's height (parent must define height/ default to 100% is value is omitted).
  - `{"mode": "rows", "value": 12}` -> approx N visible rows (default behavior is 12 if value is omitted).
  - `{"mode": "parent"}` -> fill parent; parent must define height (flex/grid).
- **overflow**: table body overflow behavior.
  - `"scroll"` -> internal scroll (default).
  - `"paginate"` -> AG Grid pagination (uses `page_size`).
  - `"clip"` -> hides overflow.
- **page_size**: number of rows per page when `overflow="paginate"`.

### Notes

- grid_ids should be unique, to avoid collisions
- If using tabs, make sure to associate the df + col_def to the wanted tab
- The numbers are right-aligned, due to the Figma design. If you need to tweak the default behaviours, please check grid_config.py or table_icons.py
