"""Inspect raw SAP lakehouse values for the columns feeding dim_/fct_ tables.

Prints max string length and a few sample values per column, so we can tell
whether real SAP data (e.g. zero-padded LIFNR/BUKRS/EBELN) fits the existing
dim_suppliers / dim_business_units / fct_purchase_orders column widths before
loading it with seed_sap_real_data.py.

    python scripts/inspect_sap_real_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import polars as pl  # noqa: E402
from loguru import logger  # noqa: E402

from config.settings import settings  # noqa: E402


def _read_table(table_name: str) -> pl.DataFrame:
    table_uri = f"{settings.LAKEHOUSE_TABLES_PATH.rstrip('/')}/{table_name}"
    logger.info(f"Querying '{table_name}' table at {table_uri}")
    return pl.read_delta(
        table_uri,
        storage_options={
            "azure_tenant_id": settings.AZURE_TENANT_ID,
            "azure_client_id": settings.AZURE_CLIENT_ID,
            "azure_client_secret": settings.AZURE_CLIENT_SECRET,
            "use_fabric_endpoint": "true",
        },
    )


def _report(df: pl.DataFrame, table_name: str, columns: list[str]) -> None:
    logger.info(f"--- {table_name} ---")
    for col in columns:
        lengths = df.select(pl.col(col).cast(pl.String).str.len_chars().alias("len"))
        max_len = lengths.select(pl.col("len").max()).item()
        samples = df.select(pl.col(col)).head(5).to_series().to_list()
        logger.info(f"{col}: max_len={max_len} samples={samples}")


def main() -> None:
    df_lfa1 = _read_table("LFA1")
    _report(df_lfa1, "LFA1", ["LIFNR", "NAME1", "STCEG", "STCD1", "LAND1"])

    df_but000 = _read_table("BUT000")
    _report(df_but000, "BUT000", ["PARTNER", "BU_LANGU"])

    df_t001 = _read_table("T001")
    _report(df_t001, "T001", ["BUKRS", "BUTXT", "STCEG", "LAND1"])

    df_ekko = _read_table("EKKO")
    _report(df_ekko, "EKKO", ["EBELN", "LIFNR", "BUKRS", "BEDAT", "RLWRT", "WAERS"])


if __name__ == "__main__":
    main()
