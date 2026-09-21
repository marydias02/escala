"""Lakehouse reads for the ETL. Filters and projection push down to Delta."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import polars as pl

from lakehouse_etl.config import PO_DATE_FLOOR, SAP_CLIENT, TEMPLATE_FLAG
from utils.utils_lakehouse import scan_table


def read_suppliers() -> pl.DataFrame:
    """LFA1, ~8473 rows.

    No deletion filter: LOEVM and NODEL are empty on every row, so the table
    carries no deletion signal. SPERR (87 rows) is a posting block and CONFS
    (597) a confirmation state — neither means the supplier is gone.
    """
    return (
        scan_table("LFA1")
        .filter(pl.col("MANDT") == SAP_CLIENT)
        .select("LIFNR", "NAME1", "NAME2", "NAME3", "NAME4", "STCEG", "STCD1", "LAND1")
        .collect()
    )


def read_partners() -> pl.DataFrame:
    """BUT000, for the supplier's preferred language.

    Its client column is CLIENT, not MANDT as on the other three tables.
    """
    return scan_table("BUT000").filter(pl.col("CLIENT") == SAP_CLIENT).select("PARTNER", "BU_LANGU").collect()


def read_business_units() -> pl.DataFrame:
    """T001, 137 rows: everything SAP does not flag as a template."""
    return (
        scan_table("T001")
        .filter((pl.col("MANDT") == SAP_CLIENT) & (pl.col("XTEMPLT") != TEMPLATE_FLAG))
        .select("BUKRS", "BUTXT", "STCEG", "LAND1")
        .collect()
    )


def read_purchase_orders(since: Optional[Decimal] = None) -> pl.DataFrame:
    """EKKO past the date floor, changed at or after `since` (None = all).

    `>=` not `>`: LASTCHANGEDATETIME has ties (two pairs in scope), and `>` would
    drop a row sharing the previous run's max. Re-reading it is free under upsert.

    LOEKZ and MEMORY are selected, not filtered — the caller needs them to know
    what to delete.
    """
    lf = scan_table("EKKO").filter((pl.col("MANDT") == SAP_CLIENT) & (pl.col("BEDAT") >= PO_DATE_FLOOR))
    if since is not None:
        lf = lf.filter(pl.col("LASTCHANGEDATETIME") >= since)
    return lf.select(
        "EBELN", "LIFNR", "BUKRS", "BEDAT", "RLWRT", "WAERS", "LASTCHANGEDATETIME", "LOEKZ", "MEMORY"
    ).collect()
