"""Replace dim_suppliers / dim_business_units / fct_purchase_orders with real SAP data.

Reads LFA1, BUT000, T001 and EKKO from the Azure Lakehouse and truncates + reloads
the three master-data tables from them. The previous (dummy) rows are assumed to
already be preserved elsewhere (e.g. *_dummy tables) before running this script.

    python scripts/seed_sap_real_data.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import polars as pl
from loguru import logger

from config.settings import settings
from utils.utils_db import get_pool, insert_rows


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


async def main() -> None:
    # df_lfa1 = _read_table("LFA1")
    # df_but000 = _read_table("BUT000")
    # df_t001 = _read_table("T001")
    df_ekko = _read_table("EKKO")

    # dim_suppliers = (
    #     df_lfa1.select(
    #         pl.col("LIFNR").alias("supplier_id"),
    #         pl.col("NAME1").alias("name"),
    #         pl.coalesce(pl.col("STCEG"), pl.col("STCD1")).alias("vat"),
    #         pl.col("LAND1").alias("country"),
    #     )
    #     .join(
    #         df_but000.select(pl.col("PARTNER").alias("supplier_id"), pl.col("BU_LANGU").alias("preferred_language")),
    #         on="supplier_id",
    #         how="left",
    #     )
    #     .with_columns(pl.lit(0).alias("is_financial"))
    #     .unique(subset="supplier_id", keep="first")
    # )

    # dim_business_units = df_t001.select(
    #     pl.col("BUKRS").alias("bu_id"),
    #     pl.col("BUTXT").alias("name"),
    #     pl.col("STCEG").alias("vat"),
    #     pl.col("LAND1").alias("country"),
    # ).unique(subset="bu_id", keep="first")

    fct_purchase_orders = (
        df_ekko.filter(pl.col("BEDAT") >= "20260101")
        .select(
            pl.col("EBELN").alias("po_code"),
            pl.col("LIFNR").alias("supplier_id"),
            pl.col("BUKRS").alias("bu_id"),
            pl.col("BEDAT").str.strptime(pl.Date, "%Y%m%d").alias("date"),
            pl.col("RLWRT").alias("value"),
            pl.col("WAERS").alias("currency"),
        )
        .unique(subset="po_code", keep="first")
    )
    logger.info(f"{fct_purchase_orders.height} fct_purchase_orders rows to insert")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE fct_purchase_orders")
        # "dim_business_units, dim_suppliers")

    # n_suppliers = await insert_rows("dim_suppliers", dim_suppliers.to_dicts())
    # n_bus = await insert_rows("dim_business_units", dim_business_units.to_dicts())
    n_pos = await insert_rows("fct_purchase_orders", fct_purchase_orders.to_dicts())
    logger.info(f"Inserted {n_pos} fct_purchase_orders rows.")


if __name__ == "__main__":
    asyncio.run(main())
