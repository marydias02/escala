"""Mailbox delta sync and the message queue it feeds, over any messages table.

One run is: walk the Graph delta query, record every addition, then claim rows
to process. The cursor lives in `email_sync_runs`, keyed by mailbox, so two use
cases syncing two mailboxes never read each other's position.

Each delta page is committed together with the link Graph returned, so the
cursor never moves past a message that is not yet recorded. A crash between
pages just re-fetches the last page: its rows hit the primary key and vanish.

The messages table is a parameter (`MessageStore.table`), not a constant: the
two use cases record different columns and different lifecycles, but claim,
reset and finish identically.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import asyncpg
import httpx

from email_core.graph_client import DeltaResyncRequired, GraphMailboxClient
from utils.utils_db import insert_row, select

SYNC_RUNS_TABLE = "email_sync_runs"

# `email_sync_runs.status`. `skipped` is a run that found the lock held.
RUN_RUNNING = "running"
RUN_SUCCEEDED = "succeeded"
RUN_FAILED = "failed"
RUN_SKIPPED = "skipped"

# Message lifecycle. `gone` is terminal: Graph no longer has the message.
MSG_PENDING = "pending"
MSG_PROCESSING = "processing"
MSG_GONE = "gone"

# `(sync_url, last_received_at)` — where the next run resumes from.
Cursor = tuple[str | None, datetime | None]


@dataclass
class SyncStats:
    """What the sync phase did, for the run log."""

    pages_fetched: int = 0
    messages_seen: int = 0
    messages_new: int = 0
    resynced: bool = False


def delta_entry_row(entry: dict) -> tuple | None:
    """`(message_id, received_at, sender_email, subject, has_attachments)` for an
    addition, or None for a removal / malformed entry.

    Updates to known messages are not filtered here: they hit the primary key on
    insert and vanish there.
    """
    if "@removed" in entry or not entry.get("receivedDateTime"):
        return None
    received_at = datetime.fromisoformat(entry["receivedDateTime"].replace("Z", "+00:00"))
    sender = ((entry.get("from") or {}).get("emailAddress") or {}).get("address")
    return (
        entry["id"],
        received_at,
        sender,
        (entry.get("subject") or "").strip() or None,
        bool(entry.get("hasAttachments")),
    )


class SyncRunStore:
    """Reads and writes `email_sync_runs` — the run log and the delta cursor."""

    def __init__(self, mailbox: str):
        self.mailbox = mailbox

    async def load_cursor(self) -> Cursor:
        """The newest cursor recorded for this mailbox.

        Any status counts: a run that failed mid-sync still committed whole
        pages, each with a consistent cursor. Skipped runs never write one.
        """
        rows = await select(
            f"""
            SELECT sync_url, last_received_at FROM {SYNC_RUNS_TABLE}
            WHERE mailbox = $1 AND sync_url IS NOT NULL
            ORDER BY started_at DESC LIMIT 1
            """,
            [self.mailbox],
        )
        if not rows:
            return None, None
        return rows[0]["sync_url"], rows[0]["last_received_at"]

    async def start(self, status: str, cursor: Cursor = (None, None)) -> uuid.UUID:
        """Open a run row, copying the previous cursor forward so the row is a
        complete resume point even before its first page commits."""
        values: dict = {
            "mailbox": self.mailbox,
            "status": status,
            "sync_url": cursor[0],
            "last_received_at": cursor[1],
        }
        if status == RUN_SKIPPED:
            values["finished_at"] = datetime.now(UTC)
        return await insert_row(SYNC_RUNS_TABLE, values, returning="run_id")

    async def finish(
        self,
        pool: asyncpg.Pool,
        run_id: uuid.UUID,
        status: str,
        sync: SyncStats,
        processed: int = 0,
        failed: int = 0,
        gone: int = 0,
        error: str | None = None,
    ) -> None:
        await pool.execute(
            f"""
            UPDATE {SYNC_RUNS_TABLE}
            SET finished_at = now(), status = $2, resynced = $3, pages_fetched = $4,
                messages_seen = $5, messages_new = $6, messages_processed = $7,
                messages_failed = $8, messages_gone = $9, error = $10
            WHERE run_id = $1
            """,
            run_id, status, sync.resynced, sync.pages_fetched,
            sync.messages_seen, sync.messages_new, processed, failed, gone, error,
        )


class MessageStore:
    """The queue of synced messages, in one use case's own table.

    Every statement is scoped to `table`, so one use case's run cannot claim or
    reset another's rows — the reason the two use cases do not share a table.
    """

    def __init__(self, table: str, *, max_attempts: int):
        self.table = table
        self.max_attempts = max_attempts

    async def record_page(
        self, conn: asyncpg.Connection, rows: list[tuple], run_id: uuid.UUID
    ) -> int:
        """Insert one delta page's additions, returning how many were new."""
        new = 0
        for row in rows:
            outcome = await conn.execute(
                f"""
                INSERT INTO {self.table}
                    (message_id, received_at, sender_email, subject, has_attachments, first_seen_run_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (message_id) DO NOTHING
                """,
                *row, run_id,
            )
            new += outcome == "INSERT 0 1"
        return new

    async def reset_stale(self, pool: asyncpg.Pool) -> int:
        """Rows a crashed run left at `processing`, back to `pending` with no
        attempt counted.

        Safe because the advisory lock means only one run is ever live, so
        anything still `processing` when a run starts belongs to a dead run.
        """
        outcome = await pool.execute(
            f"UPDATE {self.table} SET status = $1, updated_at = now() WHERE status = $2",
            MSG_PENDING, MSG_PROCESSING,
        )
        return int(outcome.rsplit(" ", 1)[-1])

    async def claim_pending(self, pool: asyncpg.Pool, limit: int | None) -> list[str]:
        """Mark the oldest claimable rows `processing` and return their ids.

        Claimable: `pending`, or `failed` with attempts left. Oldest first, so a
        retry is picked before newer mail and the backlog drains in arrival order.
        """
        limit_clause = "" if limit is None else f"LIMIT {int(limit)}"
        async with pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch(
                f"""
                UPDATE {self.table}
                SET status = $1, updated_at = now()
                WHERE message_id IN (
                    SELECT message_id FROM {self.table}
                    WHERE status = $2 OR (status = $3 AND attempts < $4)
                    ORDER BY received_at
                    {limit_clause}
                )
                RETURNING message_id, received_at
                """,
                MSG_PROCESSING, MSG_PENDING, "failed", self.max_attempts,
            )
        return [row["message_id"] for row in sorted(rows, key=lambda r: r["received_at"])]

    async def mark_gone(self, pool: asyncpg.Pool, message_ids: list[str], run_id: uuid.UUID) -> None:
        """Graph no longer has these messages — terminal, nothing to retry."""
        for message_id in message_ids:
            print(f"  👻 Message no longer in the mailbox — marked gone: {message_id}")
            await pool.execute(
                f"""
                UPDATE {self.table} SET status = $2, processed_run_id = $3, updated_at = now()
                WHERE message_id = $1
                """,
                message_id, MSG_GONE, run_id,
            )


async def sync_mailbox(
    pool: asyncpg.Pool,
    client: GraphMailboxClient,
    store: MessageStore,
    run_id: uuid.UUID,
    cursor: Cursor,
    *,
    page_size: int,
    initial_lookback,
) -> SyncStats:
    """Record every mailbox addition since the last run.

    A 410 (expired token) drops the cursor and replays from `last_received_at`
    via the initial filtered call; the initial call itself cannot 410.
    """
    sync_url, last_received_at = cursor
    since = last_received_at or datetime.now(UTC) - initial_lookback
    stats = SyncStats()

    async with httpx.AsyncClient(timeout=60) as http:
        while True:
            try:
                entries, next_url, is_delta_link = await client.fetch_delta_page(
                    http, await client.auth_headers(), sync_url, since=since, page_size=page_size
                )
            except DeltaResyncRequired:
                if sync_url is None:
                    raise
                print(f"  🔁 Delta token expired — resyncing from {since.isoformat()}")
                stats.resynced = True
                sync_url = None
                continue

            stats.pages_fetched += 1
            stats.messages_seen += len(entries)
            rows = [row for row in map(delta_entry_row, entries) if row is not None]
            newest = max((row[1] for row in rows), default=None)

            async with pool.acquire() as conn, conn.transaction():
                stats.messages_new += await store.record_page(conn, rows, run_id)
                # GREATEST ignores NULLs, so an empty page leaves last_received_at alone.
                await conn.execute(
                    f"""
                    UPDATE {SYNC_RUNS_TABLE}
                    SET sync_url = $2, last_received_at = GREATEST(last_received_at, $3)
                    WHERE run_id = $1
                    """,
                    run_id, next_url, newest,
                )

            sync_url = next_url
            if is_delta_link:
                break

    print(
        f"  📡 Synced {client.mailbox.label}: {stats.pages_fetched} page(s), "
        f"{stats.messages_seen} change(s), {stats.messages_new} new message(s)"
    )
    return stats


async def load_claimed(
    client: GraphMailboxClient, message_ids: list[str]
) -> tuple[list, list[str]]:
    """Full messages for the claimed ids, in order, plus the ids Graph no longer has."""
    headers = await client.auth_headers()
    emails = []
    gone: list[str] = []
    async with httpx.AsyncClient(timeout=60) as http:
        for message_id in message_ids:
            email = await client.fetch_message(http, headers, message_id)
            if email is None:
                gone.append(message_id)
            else:
                emails.append(email)
    return emails, gone
