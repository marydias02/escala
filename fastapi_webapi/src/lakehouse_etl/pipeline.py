"""Cron entrypoint: sync dim_suppliers, dim_business_units, dim_clients,
fct_purchase_orders and fct_invoices from the lakehouse.

Suppliers, business units and clients are extracted whole each run; EKKO is
incremental on a LASTCHANGEDATETIME watermark read back from
`fct_purchase_orders.source_changed_at` (see the 20260921_01 migration).
fct_invoices mirrors the open customer items: re-extracted whole, and an
invoice no longer open is deleted.

    python -m lakehouse_etl.pipeline [--full] [--dry-run] [--tables a,b]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback

from lakehouse_etl import extract, load, transforms
from lakehouse_etl.config import LAKEHOUSE_RUN_LOCK_KEY
from utils.utils_db import get_pool

TABLE_KEYS = ("business_units", "suppliers", "clients", "purchase_orders", "invoices")


async def _sync_business_units(dry_run: bool) -> load.SyncCounts:
    t001 = await asyncio.to_thread(extract.read_business_units)
    rows, delete_ids = transforms.build_business_units(t001)
    return await load.sync_business_units(rows, delete_ids, dry_run)


async def _sync_suppliers(dry_run: bool) -> tuple[load.SyncCounts, list[str]]:
    lfa1 = await asyncio.to_thread(extract.read_suppliers)
    but000 = await asyncio.to_thread(extract.read_partners)
    rows, delete_ids = transforms.build_suppliers(lfa1, but000)
    return await load.sync_suppliers(rows, delete_ids, dry_run), transforms.unmatched_financial_names(rows)


async def _sync_clients(dry_run: bool) -> load.SyncCounts:
    kna1 = await asyncio.to_thread(extract.read_customers)
    partners = await asyncio.to_thread(extract.read_client_partners)
    return await load.sync_clients(transforms.build_clients(kna1, partners), dry_run)


async def _sync_invoices(dry_run: bool) -> load.SyncCounts:
    open_items = await asyncio.to_thread(extract.read_open_items)
    invoices = transforms.build_open_invoices(open_items)
    orphans = transforms.orphan_invoice_references(open_items, invoices)
    if orphans:
        # Netted against nothing: their invoice is cleared or not an invoice line.
        print(f"  ⚠️  {len(orphans)} open payment/credit memo line(s) point at no open invoice, e.g.:")
        for reference_id in orphans[:5]:
            print(f"       {reference_id}")
    return await load.sync_open_invoices(invoices, dry_run)


async def _sync_purchase_orders(full: bool, dry_run: bool) -> load.SyncCounts:
    since = None if full else await load.current_watermark()
    print(f"  watermark: {'(full extract)' if since is None else since}")
    ekko = await asyncio.to_thread(extract.read_purchase_orders, since)
    rows, delete_codes = transforms.build_purchase_orders(ekko)
    return await load.sync_purchase_orders(rows, delete_codes, dry_run)


async def run_sync(
    tables: tuple[str, ...] = TABLE_KEYS, full: bool = False, dry_run: bool = False
) -> tuple[list[load.SyncCounts], list[str]]:
    """Sync each table, dims before facts so a new PO's supplier (or a new
    invoice's client) already exists.

    A table that raises is reported and the rest still run: the watermark makes
    a partial run self-healing, so finishing the others is strictly better.
    """
    results: list[load.SyncCounts] = []
    unmatched: list[str] = []

    for key in TABLE_KEYS:
        if key not in tables:
            continue
        print(f"\n▶ {key}")
        try:
            if key == "business_units":
                results.append(await _sync_business_units(dry_run))
            elif key == "suppliers":
                counts, unmatched = await _sync_suppliers(dry_run)
                results.append(counts)
            elif key == "clients":
                results.append(await _sync_clients(dry_run))
            elif key == "purchase_orders":
                results.append(await _sync_purchase_orders(full, dry_run))
            else:
                results.append(await _sync_invoices(dry_run))
        except Exception:  # noqa: BLE001 - keep the run alive, inspect after
            print(traceback.format_exc())
            results.append(load.SyncCounts(table=key, failed=True))
    return results, unmatched


def print_summary(results: list[load.SyncCounts], unmatched: list[str], dry_run: bool) -> None:
    print("\n" + "=" * 70)
    print("LAKEHOUSE SYNC" + (" (dry run — nothing written)" if dry_run else ""))
    print("=" * 70)
    for counts in results:
        if counts.failed:
            print(f"  ❌ {counts.table}: failed")
            continue
        line = f"  ✅ {counts.table}: {counts.extracted} extracted, {counts.upserted} upserted"
        if counts.deleted:
            line += f", {counts.deleted} deleted"
        if counts.absent_from_source:
            line += f", {counts.absent_from_source} in DB but absent from source (kept)"
        print(line)

    if unmatched:
        # The lists key on a display name SAP can edit; a name that matches
        # nothing means a supplier silently lost its is_financial flag.
        print(f"\n  ⚠️  {len(unmatched)} financial-list name(s) matched no supplier:")
        for name in unmatched:
            print(f"       {name}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync SAP master data and open items from the lakehouse.")
    parser.add_argument("--full", action="store_true", help="ignore the watermark and re-extract every PO")
    parser.add_argument("--dry-run", action="store_true", help="extract and report, write nothing")
    parser.add_argument(
        "--tables",
        default=",".join(TABLE_KEYS),
        help=f"comma-separated subset of: {', '.join(TABLE_KEYS)}",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    tables = tuple(name.strip() for name in args.tables.split(",") if name.strip())
    unknown = set(tables) - set(TABLE_KEYS)
    if unknown:
        print(f"❌ Unknown table(s): {', '.join(sorted(unknown))}")
        sys.exit(2)

    pool = await get_pool()
    # The lock is tied to this connection: it is released when the connection
    # goes, so a crash cannot leave it held.
    lock_conn = await pool.acquire()
    try:
        if not await lock_conn.fetchval("SELECT pg_try_advisory_lock($1)", LAKEHOUSE_RUN_LOCK_KEY):
            print("⏭️  Another lakehouse sync is still running — skipped")
            return

        results, unmatched = await run_sync(tables, full=args.full, dry_run=args.dry_run)
        print_summary(results, unmatched, args.dry_run)
        if any(counts.failed for counts in results):
            sys.exit(1)
    finally:
        await lock_conn.execute("SELECT pg_advisory_unlock($1)", LAKEHOUSE_RUN_LOCK_KEY)
        await pool.release(lock_conn)
        pool.terminate()


if __name__ == "__main__":
    asyncio.run(main())
