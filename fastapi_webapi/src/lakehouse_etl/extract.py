"""Lakehouse reads for the ETL. Filters and projection push down to Delta."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

import polars as pl

from lakehouse_etl.config import PO_DATE_FLOOR, SAP_CLIENT, TEMPLATE_FLAG
from utils.sap_queries import query_business_partners, query_open_accounts_receivable
from utils.utils_lakehouse import scan_table

# BUT000 columns `build_clients` names a client from.
CLIENT_PARTNER_COLUMNS = (
    "PARTNER",
    "NAME_ORG1",
    "NAME_ORG2",
    "NAME_ORG3",
    "NAME_ORG4",
    "NAME_FIRST",
    "NAME_LAST",
    "NAME_GRP1",
    "NAME_GRP2",
    "BU_SORT1",
)

# BSEG columns `build_open_invoices` reads.
OPEN_ITEM_COLUMNS = (
    "BUKRS",
    "BELNR",
    "GJAHR",
    "BUZEI",
    "KUNNR",
    "BSCHL",
    "UMSKZ",
    "SHKZG",
    "WRBTR",
    "H_WAERS",
    "H_BLDAT",
    "H_BLART",
    "ZUONR",
    "VBELN",
    "NETDT",
    "REBZG",
    "REBZJ",
    "REBZZ",
    "REBZT",
)


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


def read_customers() -> pl.DataFrame:
    """KNA1, ~12.8k rows: every customer, posted to or not.

    No deletion filter, same as LFA1: an open item can still point at a
    customer flagged for deletion (LOEVM, 3 rows), and it needs a client row.
    """
    return (
        scan_table("KNA1")
        .filter(pl.col("MANDT") == SAP_CLIENT)
        .select("KUNNR", "NAME1", "NAME2", "NAME3", "NAME4", "STCEG", "STCD1")
        .collect()
    )


def read_client_partners() -> pl.DataFrame:
    """BUT000 name columns for every partner, readable column names.

    KNA1 cuts a name at 35 characters per line; BUT000 holds it whole, so it
    names the client. Deleted partners are kept: an open item can still point
    at one, and it needs a name.
    """
    return query_business_partners(columns=CLIENT_PARTNER_COLUMNS, exclude_deleted=False, limit=None)


def read_open_items() -> pl.DataFrame:
    """Every open customer line from BSEG — invoices, payments, credit memos,
    special G/L items — with readable column names. `build_open_invoices`
    picks the invoices out.
    """
    return query_open_accounts_receivable(columns=OPEN_ITEM_COLUMNS, limit=None)
