"""Postgres side of the ETL: the watermark, and one sync per table."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import polars as pl

from lakehouse_etl.config import (
    BUSINESS_UNITS_TABLE,
    CLIENTS_TABLE,
    INVOICES_TABLE,
    PURCHASE_ORDERS_TABLE,
    SUPPLIERS_TABLE,
    UPSERT_CHUNK_SIZE,
)
from lakehouse_etl.transforms import BUSINESS_UNIT_COLUMNS, CLIENT_COLUMNS, SUPPLIER_COLUMNS
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
    table: str,
    id_column: str,
    rows: pl.DataFrame,
    delete_ids: list[str],
    columns: tuple[str, ...],
    dry_run: bool,
) -> SyncCounts:
    """Upsert a full extract, then delete the ids SAP flags inactive.

    Absence alone never deletes: it could be a partial read rather than a
    removal — it is reported.
    """
    counts = SyncCounts(table=table, extracted=rows.height + len(delete_ids))
    known = await existing_ids(table, id_column)
    counts.absent_from_source = len(known - set(rows.get_column(id_column).to_list()) - set(delete_ids))

    if not dry_run:
        counts.upserted = await upsert_rows(
            table,
            rows.to_dicts(),
            conflict_columns=[id_column],
            update_columns=[c for c in columns if c != id_column],
            chunk_size=UPSERT_CHUNK_SIZE,
        )
        counts.deleted = await delete_rows(table, id_column, delete_ids, chunk_size=UPSERT_CHUNK_SIZE)
    return counts


async def sync_suppliers(rows: pl.DataFrame, delete_ids: list[str], dry_run: bool = False) -> SyncCounts:
    return await _sync_dimension(SUPPLIERS_TABLE, "supplier_id", rows, delete_ids, SUPPLIER_COLUMNS, dry_run)


async def sync_business_units(rows: pl.DataFrame, delete_ids: list[str], dry_run: bool = False) -> SyncCounts:
    return await _sync_dimension(BUSINESS_UNITS_TABLE, "bu_id", rows, delete_ids, BUSINESS_UNIT_COLUMNS, dry_run)


async def sync_clients(rows: pl.DataFrame, dry_run: bool = False) -> SyncCounts:
    return await _sync_dimension(CLIENTS_TABLE, "client_id", rows, CLIENT_COLUMNS, dry_run)


async def sync_open_invoices(rows: pl.DataFrame, dry_run: bool = False) -> SyncCounts:
    """Mirror the open set: upsert what is open, delete what no longer is.

    The table holds open invoices only, so an invoice missing from the extract
    has been cleared. An empty extract over a non-empty table is far more likely
    a failed read than every invoice being paid overnight — refuse it.
    """
    counts = SyncCounts(table=INVOICES_TABLE, extracted=rows.height)
    known = await existing_ids(INVOICES_TABLE, "invoice_id")
    if rows.is_empty() and known:
        raise ValueError(f"Empty open-item extract; refusing to delete all {len(known)} rows of {INVOICES_TABLE}")

    cleared = sorted(known - set(rows.get_column("invoice_id").to_list()))
    if dry_run:
        print(f"  would delete {len(cleared)} cleared invoice(s)")
        return counts

    counts.upserted = await upsert_rows(
        INVOICES_TABLE,
        rows.to_dicts(),
        conflict_columns=["invoice_id"],
        chunk_size=UPSERT_CHUNK_SIZE,
    )
    counts.deleted = await delete_rows(INVOICES_TABLE, "invoice_id", cleared, chunk_size=UPSERT_CHUNK_SIZE)
    return counts


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
