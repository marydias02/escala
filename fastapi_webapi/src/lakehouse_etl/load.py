"""Postgres side of the ETL: the watermark, and one sync per table."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import polars as pl

from lakehouse_etl.config import (
    BUSINESS_UNITS_TABLE,
    PURCHASE_ORDERS_TABLE,
    SUPPLIERS_TABLE,
    UPSERT_CHUNK_SIZE,
)
from lakehouse_etl.transforms import BUSINESS_UNIT_COLUMNS, SUPPLIER_COLUMNS
from utils.utils_db import delete_rows, select, upsert_rows


@dataclass
class SyncCounts:
    """What one table's sync did."""

    table: str
    extracted: int = 0
    upserted: int = 0
    deleted: int = 0
    absent_from_source: int = 0
    failed: bool = False


async def current_watermark() -> Optional[Decimal]:
    """The largest committed EKKO LASTCHANGEDATETIME. None = cold start."""
    rows = await select(f"SELECT MAX(source_changed_at) AS watermark FROM {PURCHASE_ORDERS_TABLE}")
    return rows[0]["watermark"] if rows else None


async def existing_ids(table: str, id_column: str) -> set[str]:
    """Every key currently in `table`."""
    rows = await select(f"SELECT {id_column} FROM {table}")
    return {row[id_column] for row in rows}


async def _sync_dimension(
    table: str, id_column: str, rows: pl.DataFrame, columns: tuple[str, ...], dry_run: bool
) -> SyncCounts:
    """Upsert a full extract. Never deletes: the sources carry no deletion flag,
    so absence could be a partial read rather than a removal — it is reported.
    """
    counts = SyncCounts(table=table, extracted=rows.height)
    known = await existing_ids(table, id_column)
    counts.absent_from_source = len(known - set(rows.get_column(id_column).to_list()))

    if not dry_run:
        counts.upserted = await upsert_rows(
            table,
            rows.to_dicts(),
            conflict_columns=[id_column],
            update_columns=[c for c in columns if c != id_column],
            chunk_size=UPSERT_CHUNK_SIZE,
        )
    return counts


async def sync_suppliers(rows: pl.DataFrame, dry_run: bool = False) -> SyncCounts:
    return await _sync_dimension(SUPPLIERS_TABLE, "supplier_id", rows, SUPPLIER_COLUMNS, dry_run)


async def sync_business_units(rows: pl.DataFrame, dry_run: bool = False) -> SyncCounts:
    return await _sync_dimension(BUSINESS_UNITS_TABLE, "bu_id", rows, BUSINESS_UNIT_COLUMNS, dry_run)


async def sync_purchase_orders(rows: pl.DataFrame, delete_codes: list[str], dry_run: bool = False) -> SyncCounts:
    """Upsert, then delete — a PO that arrives as both an update and a
    cancellation must end deleted, not resurrected.
    """
    counts = SyncCounts(table=PURCHASE_ORDERS_TABLE, extracted=rows.height + len(delete_codes))
    if dry_run:
        return counts

    counts.upserted = await upsert_rows(
        PURCHASE_ORDERS_TABLE,
        rows.to_dicts(),
        conflict_columns=["po_code"],
        chunk_size=UPSERT_CHUNK_SIZE,
    )
    counts.deleted = await delete_rows(PURCHASE_ORDERS_TABLE, "po_code", delete_codes, chunk_size=UPSERT_CHUNK_SIZE)
    return counts
