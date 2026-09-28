"""SAP tables -> dim_/fct_ rows. Pure polars, no I/O."""

from __future__ import annotations

import polars as pl

from lakehouse_etl.config import BOTH_SUPPLIERS, FINANCIAL_SUPPLIERS, PO_HELD_FLAG
from utils.utils_lakehouse import active_business_unit, active_supplier

# Columns written to each table. The generated columns (id_norm, vat_norm,
# vat_core, name_norm) are deliberately absent — Postgres rejects writes to them.
SUPPLIER_COLUMNS = ("supplier_id", "name", "vat", "country", "preferred_language", "is_financial")
BUSINESS_UNIT_COLUMNS = ("bu_id", "name", "vat", "country")
PURCHASE_ORDER_COLUMNS = ("po_code", "supplier_id", "bu_id", "date", "value", "currency", "source_changed_at")


def full_name() -> pl.Expr:
    """Join LFA1 NAME1-NAME4; SAP splits long names across the 35-char lines."""
    lines = []
    for col in ("NAME1", "NAME2", "NAME3", "NAME4"):
        trimmed = pl.col(col).cast(pl.String).str.strip_chars()
        # Blank dot-only placeholder lines (one supplier uses "." to fill NAME3/NAME4)
        lines.append(pl.when(trimmed.str.contains(r"^\.+$")).then(None).otherwise(trimmed))
    return (
        pl.concat_str(lines, separator=" ", ignore_nulls=True)
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
        .alias("name")
    )


def classify_is_financial() -> pl.Expr:
    """0 = logistics, 1 = financial, 2 = both. Matched on the display name."""
    return (
        pl.when(pl.col("name").is_in(BOTH_SUPPLIERS))
        .then(2)
        .when(pl.col("name").is_in(FINANCIAL_SUPPLIERS))
        .then(1)
        .otherwise(0)
        .alias("is_financial")
    )


def unmatched_financial_names(suppliers: pl.DataFrame) -> list[str]:
    """Listed names that matched no supplier. The lists key on a display name
    SAP can edit, so drift is silent without this.
    """
    known = set(suppliers.get_column("name").to_list())
    return sorted(name for name in [*FINANCIAL_SUPPLIERS, *BOTH_SUPPLIERS] if name not in known)


def _split_active(df: pl.DataFrame, active: pl.Expr, id_column: str) -> tuple[pl.DataFrame, list[str]]:
    """(active rows, ids of the inactive rows to delete)."""
    rows = df.filter(active)
    kept = rows.get_column(id_column).unique().to_list()
    gone = df.filter(~active & ~pl.col(id_column).is_in(kept)).get_column(id_column)
    return rows, gone.unique().sort().to_list()


def build_suppliers(lfa1: pl.DataFrame, but000: pl.DataFrame) -> tuple[pl.DataFrame, list[str]]:
    """LFA1 (+ BUT000 for the language) -> (dim_suppliers rows, blocked supplier_ids to delete)."""
    lfa1, delete_ids = _split_active(lfa1, active_supplier(), "LIFNR")
    rows = (
        lfa1.select(
            pl.col("LIFNR").alias("supplier_id"),
            full_name(),
            pl.coalesce(pl.col("STCEG"), pl.col("STCD1")).alias("vat"),
            pl.col("LAND1").alias("country"),
        )
        .join(
            but000.select(
                pl.col("PARTNER").alias("supplier_id"),
                # Blank on most rows; store a null rather than an empty string.
                pl.col("BU_LANGU").replace("", None).alias("preferred_language"),
            ),
            on="supplier_id",
            how="left",
        )
        .with_columns(classify_is_financial())
        .unique(subset="supplier_id", keep="first")
        .select(SUPPLIER_COLUMNS)
    )
    return rows, delete_ids


def build_business_units(t001: pl.DataFrame) -> tuple[pl.DataFrame, list[str]]:
    """T001 -> (dim_business_units rows, obsolete bu_ids to delete).

    The extract is already one client, so a duplicate bu_id means that filter
    stopped working — raise rather than silently collapse it the way the seed
    script's .unique() did.
    """
    t001, delete_ids = _split_active(t001, active_business_unit(), "BUKRS")
    rows = t001.select(
        pl.col("BUKRS").alias("bu_id"),
        pl.col("BUTXT").alias("name"),
        pl.col("STCEG").alias("vat"),
        pl.col("LAND1").alias("country"),
    ).select(BUSINESS_UNIT_COLUMNS)

    duplicates = rows.group_by("bu_id").len().filter(pl.col("len") > 1)
    if duplicates.height:
        ids = ", ".join(sorted(duplicates.get_column("bu_id").to_list()))
        raise ValueError(f"Duplicate bu_id in T001 extract: {ids}")
    return rows, delete_ids


def build_purchase_orders(ekko: pl.DataFrame) -> tuple[pl.DataFrame, list[str]]:
    """EKKO -> (rows to upsert, po_codes to delete).

    Deleted are the cancelled (LOEKZ) and the held, never-posted drafts (MEMORY).
    """
    gone = pl.col("LOEKZ").fill_null("").ne("") | pl.col("MEMORY").fill_null("").eq(PO_HELD_FLAG)
    delete_codes = ekko.filter(gone).get_column("EBELN").unique().sort().to_list()

    rows = (
        ekko.filter(~gone)
        .select(
            pl.col("EBELN").alias("po_code"),
            pl.col("LIFNR").alias("supplier_id"),
            pl.col("BUKRS").alias("bu_id"),
            pl.col("BEDAT").str.strptime(pl.Date, "%Y%m%d").alias("date"),
            pl.col("RLWRT").alias("value"),
            pl.col("WAERS").alias("currency"),
            pl.col("LASTCHANGEDATETIME").alias("source_changed_at"),
        )
        .unique(subset="po_code", keep="first")
        # Ascending, so MAX(source_changed_at) over the committed rows is always
        # a safe resume point. This is what replaces a run-log cursor table.
        .sort("source_changed_at")
        .select(PURCHASE_ORDER_COLUMNS)
    )
    return rows, delete_codes
