"""Read side from DB with SAP data"""

from typing import Any, Optional

from non_conformities_resolution.resolution_rules import PIPELINE_STATUSES, TERMINAL_STATUSES
from utils.utils_db import get_pool, select, update_column

PROCESSES_TABLE = "sap_processes"
MESSAGES_TABLE = "sap_messages"


def _sql_list(values: tuple[str, ...]) -> str:
    """('a', 'b') as a SQL list literal: 'a', 'b'."""
    return ", ".join(f"'{value}'" for value in values)


async def fetch_pipeline_processes(limit: Optional[int] = None) -> list[dict[str, Any]]:
    """Every process the pipeline should act on this run.

    Filters to PIPELINE_STATUSES and orders buyer-replied processes first, per
    the spec ("start with the processes with a buyer response").
    """
    buyer_replied_status = PIPELINE_STATUSES[0]
    query = f"""
        SELECT *
        FROM {PROCESSES_TABLE}
        WHERE status IN ({_sql_list(PIPELINE_STATUSES)})
        ORDER BY (status = '{buyer_replied_status}') DESC, last_interaction_datetime ASC NULLS FIRST
    """
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    return await select(query)


async def fetch_reconcile_candidates() -> list[dict[str, Any]]:
    """Every non-terminal process, plus whether a newer buyer message exists.

    `has_newer_buyer_message` is computed in SQL as an EXISTS against
    sap_messages, so reconciliation is one query rather than one per row. See
    `_is_from_buyer_sql` for what "from the buyer" means here, and its caveats.
    """
    query = f"""
        SELECT
            p.reference_no,
            p.status,
            p.issue,
            p.reconciled,
            p.last_interaction,
            p.last_interaction_datetime,
            EXISTS (
                SELECT 1
                FROM {MESSAGES_TABLE} m
                WHERE m.process_ref_no = p.reference_no
                  AND ({_is_from_buyer_sql("m")})
                  AND (
                        p.last_interaction_datetime IS NULL
                        OR m.timestamp > p.last_interaction_datetime
                      )
            ) AS has_newer_buyer_message
        FROM {PROCESSES_TABLE} p
        WHERE p.status NOT IN ({_sql_list(TERMINAL_STATUSES)})
    """
    return await select(query)


def _is_from_buyer_sql(alias: str) -> str:
    """SQL fragment for "this sap_messages row came from the buyer".

    When the system user is configured, a message from the buyer is
    any message that was not sent by the system user. Until then, consider all
    """
    return f"{alias}.sender IS NOT NULL"


async def fetch_buyer_replies(reference_no: str, since=None) -> list[dict[str, Any]]:
    """sap_messages rows for a process, optionally only those after `since`."""
    since_clause = f"AND timestamp > '{since}'" if since is not None else ""
    query = f"""
        SELECT * FROM {MESSAGES_TABLE}
        WHERE process_ref_no = '{reference_no}' {since_clause}
        ORDER BY timestamp ASC
    """
    return await select(query)


async def set_status(reference_no: str, status: str) -> None:
    """Advance a process's status. Does not touch last_interaction*—see
    `record_interaction` for that, since not every status change is ours."""
    await update_column(PROCESSES_TABLE, "reference_no", reference_no, "status", status)


async def set_po_code(reference_no: str, po_code: str) -> None:
    """Persist the buyer-provided PO code onto the process (missing_po, amount_mismatch)."""
    await update_column(PROCESSES_TABLE, "reference_no", reference_no, "po_code", po_code)


async def set_migo_ref(reference_no: str, migo_ref: str) -> None:
    """Persist the MIGO reference found in SAP onto the process (missing_migo)."""
    await update_column(PROCESSES_TABLE, "reference_no", reference_no, "migo_ref", migo_ref)


async def record_interaction(reference_no: str, owner: str, timestamp) -> None:
    """Stamp `last_interaction` / `last_interaction_datetime` after we act on a
    process (e.g. sending a message to the buyer), so the next reconciliation
    pass can tell a genuinely new buyer message from one we already handled."""
    query = f"""
        UPDATE {PROCESSES_TABLE}
        SET last_interaction = '{owner}', last_interaction_datetime = '{timestamp}'
        WHERE reference_no = '{reference_no}'
    """
    pool = await get_pool()
    await pool.execute(query)
