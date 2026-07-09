from typing import Tuple

import pandas as pd


def load_main_table_data() -> pd.DataFrame:
    df = pd.read_csv("./assets/data/data.csv")

    # Load group data to calculate 2024 column
    df2 = pd.read_csv("./assets/data/data group.csv")
    brand_cols, year_cols = get_brand_and_year_columns(list(df2.columns))
    df["2024"] = df[year_cols].sum(axis=1)

    return df


def load_group_table_data() -> pd.DataFrame:
    return pd.read_csv("./assets/data/data group.csv")


def get_brand_and_year_columns(columns: list[str]) -> Tuple[list[str], list[str]]:
    year_cols = [col for col in columns if col.isdigit() and 1 <= int(col) <= 12]
    brand_cols = [col for col in columns if col not in year_cols]
    return brand_cols, year_cols