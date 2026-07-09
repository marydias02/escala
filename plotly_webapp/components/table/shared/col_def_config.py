from components.table.shared.grid_config import formatter_currency, formatter_short


from typing import List, Dict, Tuple
import pandas as pd
from calendar import month_abbr


def create_monthly_column_def(col, year_cols):
    col_def = {
        "field": col,
        "hide": col == "2024",
        "filter": True,
        "editable": True,
        "width": 200,
    }

    if col == "Priority":
        col_def.update(
            {
                "cellRenderer": "Priority",
                "pinned": "left",
                "width": 125,
                "cellEditor": "agSelectCellEditor",
                "cellEditorParams": dict(function="priority_options()"),
                "headerComponent": "HeaderWithIcon",
                "headerComponentParams": {
                    "displayName": "Priority",
                    "icon": "lucide:flag-triangle-right",
                },
            }
        )
    elif col == "Consumers":
        col_def["valueFormatter"] = formatter_short
    if col in year_cols or col == "2024":
        col_def["valueFormatter"] = formatter_currency

    return col_def


def create_yearly_column_def(col, year_cols):
    col_def = {
        "field": col,
        "filter": True,
        "hide": col in year_cols,
        "editable": True,
        "width": 200,
    }

    if col == "Priority":
        col_def.update(
            {
                "cellRenderer": "Priority",
                "pinned": "left",
                "width": 125,
                "cellEditor": "agSelectCellEditor",
                "cellEditorParams": dict(function="priority_options()"),
                "headerComponent": "HeaderWithIcon",
                "headerComponentParams": {
                    "displayName": "Priority",
                    "icon": "lucide:flag-triangle-right",
                },
            }
        )
    elif col == "Consumers":
        col_def["valueFormatter"] = formatter_short
    if col in year_cols or col == "2024":
        col_def["valueFormatter"] = formatter_currency

    return col_def


def create_simple_table_column_defs(brand_cols, year_cols):
    return [
        {
            "headerName": "Brand Details",
            "children": [{"field": col, "pinned": "left", "width": 150, "filter": True} for col in brand_cols],
        },
        {
            "headerName": "2024",
            "children": [{"field": col, "valueFormatter": formatter_currency, "filter": True} for col in year_cols],
        },
    ]




def build_priority_base_df() -> pd.DataFrame:

    records = [
        {"Priority": "High",   "Date": "2024-01-01", "Value": 1200},
        {"Priority": "Low",    "Date": "2024-03-01", "Value":  900},
        {"Priority": "Medium", "Date": "2025-02-01", "Value": 1500},
        {"Priority": "Low",    "Date": "2025-05-01", "Value":  800},
        {"Priority": "High",   "Date": "2025-07-01", "Value": 1350},
    ]

    base = pd.DataFrame(records)
    base["Date"]  = pd.to_datetime(base["Date"])
    base["Year"]  = base["Date"].dt.year.astype(str)
    base["Month"] = base["Date"].dt.month
    base["Mon"]   = base["Month"].map(lambda m: month_abbr[m])

    return base

def build_yearly_view(base: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict]]:

    priority_col_def = {
        "field": "Priority",
        "cellRenderer": "Priority",
    }

    yearly_df = (
        base.pivot_table(
            index=["Date", "Priority"],
            columns="Year",
            values="Value",
            aggfunc="sum",
        )
        .reset_index()
        .sort_values(["Date", "Priority"])
    )

    # Insert Month label column (e.g. "Jan", "Feb")
    yearly_df.insert(1, "Month", yearly_df["Date"].dt.strftime("%b"))

    # Build columnDefs
    yearly_col_defs: List[Dict] = [
        priority_col_def,
        {"field": "Month"},
        {"field": "Date", "hide": True},
    ]

    for y in sorted(base["Year"].unique()):
        yearly_col_defs.append({"field": y})

    return yearly_df, yearly_col_defs

def build_monthly_view(base: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict]]:

    priority_col_def = {
        "field": "Priority",
        "cellRenderer": "Priority",
    }

    monthly_wide = (
        base.pivot_table(
            index=["Year", "Priority"],
            columns="Mon",
            values="Value",
            aggfunc="sum",
        )
        .reset_index()
        .sort_values(["Year", "Priority"])
    )

    mon_order = [month_abbr[m] for m in range(1, 13)]
    present   = [m for m in mon_order if m in monthly_wide.columns]

    monthly_df = monthly_wide[["Year", "Priority"] + present]

    monthly_col_defs: List[Dict] = [
        priority_col_def,
        {"field": "Year"},
    ] + [{"field": m} for m in present]

    return monthly_df, monthly_col_defs

def create_demo_tab_table() -> Tuple[
    pd.DataFrame, List[Dict],
    pd.DataFrame, List[Dict],
]:

    base = build_priority_base_df()
    yearly_df, yearly_col_defs   = build_yearly_view(base)
    monthly_df, monthly_col_defs = build_monthly_view(base)
    return yearly_df, yearly_col_defs, monthly_df, monthly_col_defs

