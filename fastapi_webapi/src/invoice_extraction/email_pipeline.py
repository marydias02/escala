"""End-to-end per-email pipeline: INGEST one email -> EXTRACT its own PDFs -> DECIDE -> PERSIST.

This sits on top of the two existing (synchronous) pipelines without changing them:

- `ingestion_pipeline` (Phase 1) turns one `.msg` into a folder of single-document
  PDFs plus `email_content.json`.
- `extraction_pipeline` (Phase 2) classifies / extracts / validates one PDF.

The DB is async (asyncpg), so this module is async and is driven by
`asyncio.run(main())`; the sync ingestion/extraction `.run()` calls happen inside
the async flow. Writes go through the generic helpers in `utils.utils_db`.

`main` is the cron entrypoint. One run is: take the advisory lock so runs never
overlap; SYNC — walk the Graph delta query over the inbox and record every new
message in `email_messages`; PROCESS — claim the oldest pending rows, fetch
them in full and run them through `EmailPipeline`. Each run is a row in
`email_sync_runs`, which also carries the delta cursor; see the 20260918_01
migration for the tables.

`main --test` skips all of that and runs the newest `DEFAULT_FETCH_LIMIT` inbox
messages directly, the way the pipeline was exercised before the cron existed.

PERSIST also looks BACKWARDS: a new email can settle an EARLIER process on the
same thread — the supplier answered what we asked — so `close_prior_processes`
closes those instead of leaving them `Aberto` forever.

Booking documents to SAP is NOT part of this pipeline — see `sap_pipeline`,
which runs separately, in bulk, over every `fct_documents` row at
`action = "Ingerir em SAP", status = "Criado"` regardless of which email wrote
it. A document can reach that state well after its email was processed (e.g.
after manual review), so SAP booking cannot be an inline step here.
"""

import argparse
import asyncio
import json
import shutil
import time
import traceback
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import httpx

from config.settings import settings
from invoice_extraction.config import (
    DEFAULT_FETCH_LIMIT,
    DELTA_PAGE_SIZE,
    DOC_STATUS_COMMUNICATED,
    DOC_STATUS_CREATED,
    DOC_STATUS_FAILED,
    DOC_STATUS_IGNORED,
    EMAIL_ACTIONS,
    EMAIL_MAX_WORKERS,
    ENABLE_TRACING,
    EXTRACTION_MAX_WORKERS,
    INGEST_LIMIT,
    INITIAL_SYNC_LOOKBACK,
    MANIFEST_NAME,
    MAX_ATTEMPTS,
    MLFLOW_EXPERIMENT,
    PROCESSED_EMAILS_DIR,
    RUN_LOCK_KEY,
    WRITE_TO_DB,
)
from invoice_extraction.decisions import (
    EMAIL_ARCHIVE,
    EMAIL_INBOX,
    EMAIL_REPLY,
    EMAIL_STATUS_CLOSED,
    EMAIL_STATUS_OPEN,
    EMAIL_TREASURY,
    IGNORE,
    INBOX,
    REPLY,
    TREASURY,
    DocumentAction,
    EmailDecision,
    build_alerts_list,
    close_prior_process,
    decide_email,
)
from invoice_extraction.extraction_pipeline import (
    ExtractionPipeline,
    PipelineResult,
)
from invoice_extraction.extraction_pipeline import (
    create_pipeline as create_extraction_pipeline,
)
from invoice_extraction.ingestion_pipeline import (
    EmailIngestionResult,
    IngestionPipeline,
    parse_reception_date,
    print_summary,
)
from invoice_extraction.ingestion_pipeline import (
    create_pipeline as create_ingestion_pipeline,
)
from email_core.graph_client import DeltaResyncRequired, GraphMailboxClient
from invoice_extraction.invoice_utils.email_sender import (
    archive_message,
    forward_to_treasury,
    reply_to_supplier,
)
from invoice_extraction.mailbox import invoice_client
from invoice_extraction.invoice_utils.reporting import (
    buffered_output,
    install_buffering,
    print_pipeline_result,
)
from invoice_extraction.models import DocumentClassification, EmailIntent, LoadedEmail, ValidationReport
from invoice_extraction.nodes import classify_email_intent
from invoice_extraction.tracing import (
    STAGE_DECISION,
    decision_summary,
    set_span_attributes,
    set_trace_tags,
    setup_tracing,
    span,
)
from invoice_extraction.tracing import (
    flush as flush_traces,
)
from utils.blob_storage import build_email_prefix, upload_email_folder
from utils.llm_factory import LLMFactory
from utils.utils_db import get_pool, insert_row, insert_rows, select, update_column

PROCESSES_TABLE = "fct_processes"
DOCUMENTS_TABLE = "fct_documents"
DOCUMENT_FIRST_ACTION_TABLE = "fct_document_first_action"

SYNC_RUNS_TABLE = "email_sync_runs"
MESSAGES_TABLE = "email_messages"

# `email_messages.status` lifecycle. `gone` is terminal: Graph no longer has the
# message, so there is nothing to retry.
MSG_PENDING = "pending"
MSG_PROCESSING = "processing"
MSG_PROCESSED = "processed"
MSG_FAILED = "failed"
MSG_GONE = "gone"

# `email_sync_runs.status`. `skipped` is a run that found the lock held.
RUN_RUNNING = "running"
RUN_SUCCEEDED = "succeeded"
RUN_FAILED = "failed"
RUN_SKIPPED = "skipped"

# The value-bearing ValidationReport fields (each a Checked[T] or None). `notes`
# and `po_list` are handled separately in build_document_content.
_CONTENT_FIELDS = [
    "supplier_name",
    "supplier_id",
    "supplier_vat",
    "document_number",
    "bu_name",
    "bu_id",
    "bu_vat",
    "issue_date",
    "base_amount",
    "vat_amount",
    "total_amount",
    "currency",
]


@dataclass
class EmailProcessingResult:
    """Outcome of running one email end to end.

    `decision` carries the email-level action, the reply text (if any) and the
    final per-document actions. See `invoice_extraction.decisions`.
    """

    source: str
    ingestion: EmailIngestionResult
    decision: EmailDecision
    extractions: list[PipelineResult] = field(default_factory=list)
    process_id: str | None = None


# --------------------------------------------------------------------------- #
# Result -> row mapping — clearly-marked, revisable business rules.
# --------------------------------------------------------------------------- #

_TYPE_LABELS = {
    "invoice": "Invoice",
    "billing_document": "Billing Document",
    "receipt": "Receipt",
    "credit_note": "Credit Note",
    "debit_note": "Debit Note",
    "other": "Other",
}
_STATE_LABELS = {
    "original": "Original",
    "proforma": "Proforma",
    "copy": "Duplicate",
    "cancelled": "Cancelled",
}


def document_type_label(classification: DocumentClassification | None) -> str:
    """Human-readable document type, e.g. "Invoice (Original)".

    A null state is treated as Original, matching the extraction gate's rule that
    an unstated document is the real thing rather than a copy.
    """
    if classification is None:
        return "Unknown"

    type_label = _TYPE_LABELS.get(classification.document_type.value, classification.document_type.value)
    state_value = classification.document_state.value if classification.document_state is not None else "original"
    state_label = _STATE_LABELS.get(state_value, state_value)
    return f"{type_label} ({state_label})"


def derive_status(result: PipelineResult, action: DocumentAction) -> str:
    """Map a document's outcome to a Status. Refine as the lifecycle grows.

    Most routed documents start life as "Criado": `EmailPipeline._send_followups`
    then carries out the document's email-level action (supplier reply, treasury
    forward) inline and overrides this with the outcome — "Comunicado" on
    success, left at "Criado" on failure.

    IGNORE and INBOX have no follow-up AND nothing pending - Ignorado

    Only a document that actually broke (a stage raised, so no classification) is
    "Failed" — the pipeline did not manage to route it at all.
    """
    if result.status == "failed":
        return DOC_STATUS_FAILED
    if action in (IGNORE, INBOX):
        return DOC_STATUS_IGNORED
    return DOC_STATUS_CREATED


def _checked_to_dict(checked) -> dict | None:
    """A Checked[T] field -> {"value", "confidence"}; None stays None."""
    if checked is None:
        return None
    return {"value": checked.value, "confidence": checked.confidence}


def build_document_content(validation: ValidationReport | None) -> dict:
    """Flatten a ValidationReport into the document_content JSONB payload.

    Each field keeps its {value, confidence} so the validator's confidence
    survives for later review/thresholding. `po_list` is a list of those.
    """
    if validation is None:
        return {}

    content: dict = {name: _checked_to_dict(getattr(validation, name)) for name in _CONTENT_FIELDS}
    content["po_list"] = [_checked_to_dict(po) for po in validation.po_list]
    return content


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _produced_pdf_paths(ingestion: EmailIngestionResult) -> list[Path]:
    """The exact PDFs this email produced, resolved from the ingestion result.

    Reading the paths off the result (rather than re-globbing the folder) keeps
    each email to its own PDFs and needs no filesystem guessing.
    """
    if ingestion.folder is None:
        return []
    return [
        ingestion.folder / name
        for attachment in ingestion.attachments
        if attachment.status == "chunked"
        for name in attachment.split_filenames
    ]


def _load_manifest(folder: Path | None) -> dict:
    """Read an email's `email_content.json`, or {} if it is missing/unreadable."""
    if folder is None:
        return {}
    try:
        return json.loads((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _discard_local_folder(folder: Path | None) -> None:
    """Delete one email's working folder, now that blob storage holds its artifacts.

    A failure is logged, not raised: the upload and the rows are already correct,
    so a folder left behind must not fail the email.
    """
    if folder is None or not folder.exists():
        return
    try:
        shutil.rmtree(folder)
    except OSError as exc:
        print(f"  ⚠️  Could not delete local folder {folder}: {type(exc).__name__}: {exc}")


async def _processed_message_ids() -> set[str]:
    """Every `message_id` already recorded in fct_processes.

    Fetched once per run and passed to `fetch_inbox_emails`, so the loader can
    skip attachment downloads entirely for known messages — cheaper than one
    query per email, and the DB is the only dedup authority now.
    """
    rows = await select(f"SELECT message_id FROM {PROCESSES_TABLE} WHERE message_id IS NOT NULL")
    return {row["message_id"] for row in rows}


async def _thread_message_count(thread_id: str | None) -> int | None:
    """This email's position in its thread: 1 for the first ingested, 2 for the second."""
    if not thread_id:
        return None
    rows = await select(f"SELECT count(*) AS n FROM {PROCESSES_TABLE} WHERE thread_id = $1", [thread_id])
    return int(rows[0]["n"]) + 1


# --------------------------------------------------------------------------- #
# Thread continuation — settling EARLIER processes
# --------------------------------------------------------------------------- #


async def _open_processes_in_thread(thread_id: str, exclude_process_id) -> list[dict]:
    """This thread's still-`Aberto` processes, minus the one just written.

    Only "Aberto": a "Requer Ação" process is waiting on a human, and a supplier
    answering does not discharge that, so it is left for them to close.
    """
    return await select(
        f"""
        SELECT process_id, email_action
        FROM {PROCESSES_TABLE}
        WHERE thread_id = $1 AND email_status = $2 AND process_id <> $3
        """,
        [thread_id, EMAIL_STATUS_OPEN, exclude_process_id],
    )


async def _document_states(process_id) -> list[tuple[str | None, str | None]]:
    """(action, status) for each of a process's documents."""
    rows = await select(f"SELECT action, status FROM {DOCUMENTS_TABLE} WHERE process_id = $1", [process_id])
    return [(row["action"], row["status"]) for row in rows]


async def close_prior_processes(thread_id: str | None, current_process_id) -> list[str]:
    """Close the earlier processes of this thread that the new email settles.

    A supplier answering on the thread is what an earlier `Retornado ao
    Fornecedor` was waiting for, so that process is revisited now rather than
    staying `Aberto` forever. `decisions.close_prior_process` holds the rule;
    this reads the candidates, applies it, and writes `Fechado`.

    Returns the process_ids actually closed, for the caller to log and trace.
    """
    if not thread_id:
        return []

    closed: list[str] = []
    for row in await _open_processes_in_thread(thread_id, current_process_id):
        documents = await _document_states(row["process_id"])
        if not close_prior_process(row["email_action"], documents):
            continue

        await update_column(PROCESSES_TABLE, "process_id", row["process_id"], "email_status", EMAIL_STATUS_CLOSED)
        closed.append(str(row["process_id"]))

    return closed


# --------------------------------------------------------------------------- #
# Inbox sync — the cron path (see the module docstring)
# --------------------------------------------------------------------------- #


@dataclass
class SyncStats:
    """What Phase A (SYNC) did, for the run log."""

    pages_fetched: int = 0
    messages_seen: int = 0
    messages_new: int = 0
    resynced: bool = False


Cursor = tuple[str | None, datetime | None]


def _sync_mailbox() -> str:
    """The mailbox a run syncs, as recorded in `email_sync_runs.mailbox`."""
    return invoice_client().mailbox.label


async def _load_cursor(mailbox: str) -> Cursor:
    """`(sync_url, last_received_at)` from the newest run that recorded a cursor.

    Any status counts: a run that failed mid-sync still committed whole pages,
    each with a consistent cursor. Skipped runs never write one.
    """
    rows = await select(
        f"""
        SELECT sync_url, last_received_at FROM {SYNC_RUNS_TABLE}
        WHERE mailbox = $1 AND sync_url IS NOT NULL
        ORDER BY started_at DESC LIMIT 1
        """,
        [mailbox],
    )
    if not rows:
        return None, None
    return rows[0]["sync_url"], rows[0]["last_received_at"]


async def _start_run(mailbox: str, status: str, cursor: Cursor = (None, None)) -> uuid.UUID:
    """Open a run row. The previous cursor is copied forward so the row is a
    complete resume point even before its first page commits."""
    values: dict = {"mailbox": mailbox, "status": status, "sync_url": cursor[0], "last_received_at": cursor[1]}
    if status == RUN_SKIPPED:
        values["finished_at"] = datetime.now(UTC)
    return await insert_row(SYNC_RUNS_TABLE, values, returning="run_id")


async def _finish_run(
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


def _delta_entry_row(entry: dict) -> tuple | None:
    """`(message_id, received_at, sender_email, subject)` for an addition, or None
    for a removal / malformed entry. Updates to known messages are not filtered
    here: they hit the primary key on insert and vanish there."""
    if "@removed" in entry or not entry.get("receivedDateTime"):
        return None
    received_at = datetime.fromisoformat(entry["receivedDateTime"].replace("Z", "+00:00"))
    sender = ((entry.get("from") or {}).get("emailAddress") or {}).get("address")
    return entry["id"], received_at, sender, (entry.get("subject") or "").strip() or None


async def _sync_inbox(
    pool: asyncpg.Pool, client: GraphMailboxClient, headers: dict, run_id: uuid.UUID, cursor: Cursor
) -> SyncStats:
    """Phase A: record every inbox addition since the last run in `email_messages`.

    Each delta page is committed together with the link Graph returned, on this
    run's own row, so the cursor never moves past a message that is not yet
    recorded. A crash between pages just re-fetches the last page: its rows hit
    the primary key and vanish.

    A 410 (expired token) drops the cursor and replays from `last_received_at`
    via the initial filtered call; the initial call itself cannot 410.
    """
    sync_url, last_received_at = cursor
    since = last_received_at or datetime.now(UTC) - INITIAL_SYNC_LOOKBACK
    stats = SyncStats()

    async with httpx.AsyncClient(timeout=60) as http:
        while True:
            try:
                entries, next_url, is_delta_link = await client.fetch_delta_page(
                    http, headers, sync_url, since=since, page_size=DELTA_PAGE_SIZE
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
            rows = [row for row in map(_delta_entry_row, entries) if row is not None]
            newest = max((row[1] for row in rows), default=None)

            async with pool.acquire() as conn, conn.transaction():
                for row in rows:
                    outcome = await conn.execute(
                        f"""
                        INSERT INTO {MESSAGES_TABLE} (message_id, received_at, sender_email, subject, first_seen_run_id)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (message_id) DO NOTHING
                        """,
                        *row, run_id,
                    )
                    stats.messages_new += outcome == "INSERT 0 1"
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
        f"  📡 Synced inbox: {stats.pages_fetched} page(s), {stats.messages_seen} change(s), "
        f"{stats.messages_new} new message(s)"
    )
    return stats


async def _reset_stale_processing(pool: asyncpg.Pool) -> int:
    """Rows a crashed run left at `processing`, back to `pending` with no attempt counted.

    Only one run is ever live (the advisory lock), so anything still
    `processing` when a run starts belongs to a run that died.
    """
    outcome = await pool.execute(
        f"UPDATE {MESSAGES_TABLE} SET status = $1, updated_at = now() WHERE status = $2",
        MSG_PENDING, MSG_PROCESSING,
    )
    return int(outcome.rsplit(" ", 1)[-1])


async def _claim_pending(pool: asyncpg.Pool, limit: int | None) -> list[str]:
    """Mark the oldest claimable rows `processing` and return their ids.

    Claimable: `pending`, or `failed` with attempts left. Oldest first, so a
    retry is picked before newer mail and the backlog drains in arrival order.
    """
    limit_clause = "" if limit is None else f"LIMIT {int(limit)}"
    async with pool.acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            f"""
            UPDATE {MESSAGES_TABLE}
            SET status = $1, updated_at = now()
            WHERE message_id IN (
                SELECT message_id FROM {MESSAGES_TABLE}
                WHERE status = $2 OR (status = $3 AND attempts < $4)
                ORDER BY received_at
                {limit_clause}
            )
            RETURNING message_id, received_at
            """,
            MSG_PROCESSING, MSG_PENDING, MSG_FAILED, MAX_ATTEMPTS,
        )
    return [row["message_id"] for row in sorted(rows, key=lambda r: r["received_at"])]


async def _load_claimed(
    client: GraphMailboxClient, headers: dict, message_ids: list[str]
) -> tuple[list[LoadedEmail], list[str]]:
    """Full messages for the claimed ids, in the given order, plus the ids Graph no longer has."""
    emails: list[LoadedEmail] = []
    gone: list[str] = []
    async with httpx.AsyncClient(timeout=60) as http:
        for message_id in message_ids:
            email = await client.fetch_message(http, headers, message_id)
            if email is None:
                gone.append(message_id)
            else:
                emails.append(email)
    return emails, gone


async def _mark_gone(pool: asyncpg.Pool, message_ids: list[str], run_id: uuid.UUID) -> None:
    for message_id in message_ids:
        print(f"  👻 Message no longer in the mailbox — marked gone: {message_id}")
        await pool.execute(
            f"""
            UPDATE {MESSAGES_TABLE} SET status = $2, processed_run_id = $3, updated_at = now()
            WHERE message_id = $1
            """,
            message_id, MSG_GONE, run_id,
        )


async def _finish_message(
    pool: asyncpg.Pool, email: LoadedEmail, result: EmailProcessingResult, run_id: uuid.UUID
) -> str:
    """Write one email's outcome to its `email_messages` row; returns the status written.

    Success is a `fct_processes` row (`process_id` set). A `skipped` ingestion
    (nothing usable in the email) writes no process either, but re-running it
    would give the same answer, so its attempts are pinned at the cap.
    """
    if result.process_id is not None:
        await pool.execute(
            f"""
            UPDATE {MESSAGES_TABLE}
            SET status = $2, process_id = $3, processed_run_id = $4, last_error = NULL, updated_at = now()
            WHERE message_id = $1
            """,
            email.message_id, MSG_PROCESSED, uuid.UUID(result.process_id), run_id,
        )
        return MSG_PROCESSED

    terminal = result.ingestion.status == "skipped"
    await pool.execute(
        f"""
        UPDATE {MESSAGES_TABLE}
        SET status = $2, attempts = CASE WHEN $4 THEN GREATEST(attempts + 1, $5) ELSE attempts + 1 END,
            last_error = $3, processed_run_id = $6, updated_at = now()
        WHERE message_id = $1
        """,
        email.message_id, MSG_FAILED, f"{result.ingestion.status}: {result.ingestion.message}",
        terminal, MAX_ATTEMPTS, run_id,
    )
    return MSG_FAILED


async def _upsert_processed(pool: asyncpg.Pool, emails: list[LoadedEmail], results: list[EmailProcessingResult]) -> None:
    """`--test` bookkeeping: record what it processed so the cron does not queue it again.

    Both run ids are left NULL: there is no cron run to point at.
    """
    for email, result in zip(emails, results):
        if result.process_id is None:
            continue
        await pool.execute(
            f"""
            INSERT INTO {MESSAGES_TABLE} (message_id, received_at, sender_email, subject, status, process_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (message_id) DO UPDATE
                SET status = EXCLUDED.status, process_id = EXCLUDED.process_id, updated_at = now()
            """,
            email.message_id, parse_reception_date(email.reception_date), email.sender_email,
            email.subject or None, MSG_PROCESSED, uuid.UUID(result.process_id),
        )


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #


class EmailPipeline:
    """Composes the ingestion and extraction pipelines and writes to Postgres."""

    def __init__(
        self,
        ingestion: IngestionPipeline,
        extraction: ExtractionPipeline,
        client: GraphMailboxClient | None = None,
    ):
        self.ingestion = ingestion
        self.extraction = extraction
        # The mailbox replies/forwards/archives act on — the same one the run read from.
        self.client = client or invoice_client()

    def _classify_body(self, email: LoadedEmail, ingestion: EmailIngestionResult) -> EmailIntent | None:
        """Classify the email body, for the cases where no usable PDF came out.

        Prefers the manifest ingestion just wrote; falls back to the
        `LoadedEmail` itself when there is no folder (ingestion failed).

        Best-effort: a classifier failure must not lose the whole email, so it
        degrades to None.
        """
        manifest = _load_manifest(ingestion.folder)
        subject = manifest.get("email_subject")
        body = manifest.get("email_content")

        if subject is None and body is None:
            subject, body = email.subject, email.body

        try:
            return classify_email_intent(self.extraction.llm, subject or "", body or "")
        except Exception as exc:  # noqa: BLE001 - a failed classification is not fatal
            print(f"  ⚠️  Email intent classification failed: {type(exc).__name__}: {exc}")
            return None

    async def _send_followups(self, result: EmailProcessingResult) -> dict[str, str]:
        """Carry out each document's email-level action (send) and return {filename: status}.

        The supplier reply and the treasury forward are each sent ONCE per
        email, as a Graph reply/forward on the original message (`message_id`
        from the manifest) — `decision.reply_body`/`decision.treasury_body`
        are already deduped/joined across every REPLY/TREASURY document

        INGEST documents are deliberately left at "Criado": ingestion done
        by SAP pipeline

        Failures (Mail.Send is not yet a granted Graph permission — see
        `invoice_utils.email_sender`) leave the returned status at "Criado".

        The archive move (`Arquivar`) runs last and independently of the
        returned dict: it acts on the message itself.
        """
        manifest = _load_manifest(result.ingestion.folder)
        decisions_by_file = {d.filename: d for d in result.decision.documents}
        statuses: dict[str, str] = {}
        message_id = manifest.get("message_id", "")

        if result.decision.should_reply and result.decision.reply_body:
            sender_email = manifest.get("sender_email", "")
            reply_subject = f"Re: {manifest.get('email_subject', '')}"
            if not EMAIL_ACTIONS:
                print(
                    f"  🚫 EMAIL_ACTIONS off — reply to supplier {sender_email!r} NOT sent "
                    f"— subject={reply_subject!r}"
                )
                sent = False
            else:
                send_result = await reply_to_supplier(
                    self.client,
                    message_id=message_id,
                    subject=reply_subject,
                    comment=result.decision.reply_body,
                )
                sent = send_result.status == "sent"
                if sent:
                    print(f"  📧 Reply sent to supplier {sender_email!r} — subject={reply_subject!r}")
                else:
                    print(
                        f"  ⚠️  Reply to supplier {sender_email!r} FAILED "
                        f"({send_result.error}) — subject={reply_subject!r}"
                    )
            print(f"            body={result.decision.reply_body!r}")
            outcome = DOC_STATUS_COMMUNICATED if sent else DOC_STATUS_CREATED
            for filename, decision in decisions_by_file.items():
                if decision.action == REPLY:
                    statuses[filename] = outcome

        if result.decision.should_forward_to_treasury and result.decision.treasury_body:
            treasury_email = settings.TREASURY_EMAIL or ""
            treasury_subject = f"Documentos para tesouraria - {manifest.get('email_subject', '')}"
            if not EMAIL_ACTIONS:
                print(
                    f"  🚫 EMAIL_ACTIONS off — forward to treasury {treasury_email!r} NOT sent "
                    f"— subject={treasury_subject!r}"
                )
                sent = False
            else:
                send_result = await forward_to_treasury(
                    self.client,
                    message_id=message_id,
                    to=treasury_email,
                    subject=treasury_subject,
                    comment=result.decision.treasury_body,
                )
                sent = send_result.status == "sent"
                if sent:
                    print(f"  📧 Forwarded to treasury {treasury_email!r} — subject={treasury_subject!r}")
                else:
                    print(
                        f"  ⚠️  Forward to treasury {treasury_email!r} FAILED "
                        f"({send_result.error}) — subject={treasury_subject!r}"
                    )
            print(f"            body={result.decision.treasury_body!r}")
            outcome = DOC_STATUS_COMMUNICATED if sent else DOC_STATUS_CREATED
            for filename, decision in decisions_by_file.items():
                if decision.action == TREASURY:
                    statuses[filename] = outcome

        if result.decision.should_archive:
            subject = manifest.get("email_subject", "")
            if not EMAIL_ACTIONS:
                print(f"  🚫 EMAIL_ACTIONS off — message NOT archived — subject={subject!r}")
            else:
                send_result = await archive_message(self.client, message_id)
                if send_result.status == "sent":
                    print(f"  📦 Archived message — subject={subject!r}")
                else:
                    print(f"  ⚠️  Archive FAILED ({send_result.error}) — subject={subject!r}")

        return statuses

    async def _persist(self, result: EmailProcessingResult, thread_message_count: int | None = None) -> None:
        """Write one fct_processes row, its fct_documents rows, and their
        fct_document_first_action rows — then settle what this email closes.

        `thread_message_count` is passed here

        `fct_document_first_action` is written once, immediately after
        `fct_documents`, from the same `action` values — before any follow-up
        or later manual review can change them — so it always reflects the
        document's ORIGINAL routing, unlike `fct_documents.action`.

        Each row's `document_id` is generated here so the whole batch can still
        go through one `insert_rows` call, yet every id is already known for
        UPDATE — no per-row INSERT round-trip needed just to read one back.

        Finally `close_prior_processes` revisits the EARLIER processes of this
        thread: an email arriving can be what one of them was waiting for, so its
        `email_status` is not frozen at what it was when it was processed.
        """
        ingestion = result.ingestion
        manifest = _load_manifest(ingestion.folder)

        thread_id = manifest.get("thread_id") or None

        # Upload BEFORE any write or send: raising here leaves no row pointing at a
        # missing blob, and no supplier/treasury email sent for an email we dropped.
        blob_prefix = None
        if ingestion.folder:
            blob_prefix = build_email_prefix(
                parse_reception_date(manifest.get("reception_date")),
                ingestion.folder.name,
            )
            keys = await asyncio.to_thread(upload_email_folder, ingestion.folder, blob_prefix)
            print(f"  ☁️  Uploaded {len(keys)} file(s) to {blob_prefix}/")

        # Insert the process WITHOUT an id — the DB generates process_id — and read
        # it back to use as the documents' foreign key.
        process_id = await insert_row(
            PROCESSES_TABLE,
            {
                "sender_email": manifest.get("sender_email", ""),
                "email_subject": manifest.get("email_subject"),
                "email_content": manifest.get("email_content"),
                "reception_date": parse_reception_date(manifest.get("reception_date")),
                "message_id": manifest.get("message_id"),
                "thread_id": thread_id,
                "thread_message_count": thread_message_count,
                "email_status": result.decision.status,
                "email_action": list(result.decision.actions),
            },
            returning="process_id",
        )
        result.process_id = str(process_id)

        # Each document's FINAL action (post-suppression) comes from the decision.
        # Paired by filename rather than by position so the two lists cannot drift.
        # The whole decision is kept, not just its action: `build_alerts_list`
        # reads the PO answer off it rather than repeating the lookups.
        decisions_by_file = {d.filename: d for d in result.decision.documents}

        document_ids = {extraction.filename: str(uuid.uuid4()) for extraction in result.extractions}

        # Links each extracted document to its fct_documents row, on the email span
        set_span_attributes(document_ids=document_ids)

        rows = []
        for extraction in result.extractions:
            # `decide_email` builds one decision per extraction, from this same
            # list, so every filename is present — indexed directly rather than
            # defaulted, so a broken invariant surfaces instead of silently
            # routing a document to manual review.
            decision = decisions_by_file[extraction.filename]
            rows.append(
                {
                    "document_id": document_ids[extraction.filename],
                    "process_id": process_id,
                    "document_type": document_type_label(extraction.classification),
                    "action": decision.action,
                    "status": derive_status(extraction, decision.action),
                    "document_content": build_document_content(extraction.validation),
                    "alerts_list": build_alerts_list(extraction, decision),
                    "created_by": "pipeline",
                    "file_path": f"{blob_prefix}/{extraction.filename}" if blob_prefix else None,
                }
            )
        # version, created_at/last_modified_at fall to DB defaults. document_id
        # is supplied explicitly (see docstring) rather than left to the
        # column's own gen_random_uuid() default.
        await insert_rows(DOCUMENTS_TABLE, rows, jsonb_columns=["document_content"])

        # One immutable row per document, capturing the action it was FIRST
        # routed to. Written here, once, from the same `rows` — never touched
        # again, unlike `fct_documents.action`, which manual review overwrites.
        first_action_rows = [
            {
                "document_id": row["document_id"],
                "process_id": row["process_id"],
                "first_action": row["action"],
            }
            for row in rows
        ]
        await insert_rows(DOCUMENT_FIRST_ACTION_TABLE, first_action_rows)

        # SEND/BOOK, then UPDATE the rows whose action actually resolved.
        followup_statuses = await self._send_followups(result)
        for filename, status in followup_statuses.items():
            document_id = document_ids.get(filename)
            if document_id is not None:
                await update_column(DOCUMENTS_TABLE, "document_id", document_id, "status", status)

        # This email arriving can be exactly what an earlier one on the thread was
        # waiting for. Last, so the row just written cannot count itself.
        closed = await close_prior_processes(thread_id, process_id)
        if closed:
            print(f"  🔒 Closed {len(closed)} earlier process(es) on this thread")
            set_span_attributes(closed_prior_processes=closed)

    async def run(
        self,
        email: LoadedEmail,
        output_root: Path = PROCESSED_EMAILS_DIR,
    ) -> EmailProcessingResult:
        """Ingest one email, extract its PDFs, decide, and persist to Postgres.

        No dedup gate here: `main()` only hands over messages it has already
        checked against the database, and `fct_processes.message_id` is unique,
        so every email reaching this method is ingested unconditionally.

        The whole email is one trace: every ingestion, extraction and decision
        span below nests under this one, so a single trace answers "what happened
        to this email, and why".
        """
        source = email.message_id or email.subject

        with span(f"email:{source}", "CHAIN") as email_span:
            email_span.set_inputs({"source": source})
            # `model` makes a model swap a filter dimension.
            set_trace_tags(email=source, model=self.extraction.llm_factory.openai_model)

            # --- INGEST ---------------------------------------------------------
            # Threaded: sync and LLM-bound, so it would otherwise pin the loop.
            ingestion = await asyncio.to_thread(self.ingestion.run, email, output_root)

            # A failed email yields no fresh PDFs. Bundle and decide, but write
            # nothing — no body classification either, since nothing could be read.
            if ingestion.status != "ingested":
                decision = decide_email(ingestion, [])
                set_trace_tags(action=", ".join(decision.actions), outcome=ingestion.status)
                email_span.set_outputs({"ingestion_status": ingestion.status, "decision": decision_summary(decision)})
                return EmailProcessingResult(
                    source=source,
                    ingestion=ingestion,
                    decision=decision,
                )

            # --- EXTRACT (this email's own PDFs only) ---------------------------
            pdf_paths = _produced_pdf_paths(ingestion)
            extractions = await self.extraction.run_batch(pdf_paths)

            # Counted once, here, because it both routes the email and is stored
            # with it — two counts could disagree if a sibling lands in between.
            thread_message_count = await _thread_message_count(email.thread_id or None)

            # --- DECIDE ---------------------------------------------------------
            # No usable PDF (A1/A2) is the only case the body can change, so the
            # extra LLM call is confined to it — threaded, since it blocks.
            intent = await asyncio.to_thread(self._classify_body, email, ingestion) if not extractions else None

            # A span of its own even though it is pure, LLM-free business logic:
            # the routing rules are the part most likely to be questioned, and
            # this records the inputs they saw alongside the answer they gave.
            with span(STAGE_DECISION, "CHAIN") as decision_span:
                decision_span.set_inputs(
                    {
                        "documents": [{"filename": e.filename, "status": e.status} for e in extractions],
                        "attachments": len(ingestion.attachments),
                        "thread_message_count": thread_message_count,
                    }
                )
                decision = decide_email(
                    ingestion,
                    extractions,
                    intent=intent,
                    thread_message_count=thread_message_count,
                )
                decision_span.set_outputs(decision_summary(decision))

            result = EmailProcessingResult(
                source=source,
                ingestion=ingestion,
                extractions=extractions,
                decision=decision,
            )

            # Tagging the trace with the outcome is what makes "every email that
            # went to Validate Manually" a one-line filter in the UI.
            set_trace_tags(
                action=", ".join(decision.actions),
                outcome="processed",
                documents=len(extractions),
            )
            email_span.set_outputs(
                {
                    "documents": len(extractions),
                    "decision": decision_summary(decision),
                }
            )

            # --- PERSIST --------------------------------------------------------
            if WRITE_TO_DB:
                await self._persist(result, thread_message_count)
                # Links the trace to its fct_processes row.
                set_trace_tags(process_id=result.process_id)
                _discard_local_folder(ingestion.folder)
            else:
                print("  💾 WRITE_TO_DB is off — not persisting")

            return result

    async def _run_safe(self, email: LoadedEmail, output_root: Path) -> EmailProcessingResult:
        """`run`, but a raised exception becomes a `failed` result instead of propagating."""
        source = email.message_id or email.subject

        # Buffered so concurrent emails print as blocks, not interleaved lines.
        with buffered_output():
            print(f"\n{'=' * 70}\n📧 {email.subject}\n{'=' * 70}")
            started = time.perf_counter()

            try:
                result = await self.run(email, output_root)
            except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
                message = f"{type(exc).__name__}: {exc}"
                print(f"  ❌ Failed: {message}")
                failed = EmailIngestionResult(source=source, status="failed", message=message)
                return EmailProcessingResult(
                    source=source,
                    ingestion=failed,
                    decision=decide_email(failed, []),
                )

            print(
                f"  ⏱️  {time.perf_counter() - started:.1f}s "
                f"({len(result.extractions)} docs, {EXTRACTION_MAX_WORKERS} workers)"
            )
            return result

    async def run_batch(
        self,
        emails: list[LoadedEmail],
        output_root: Path = PROCESSED_EMAILS_DIR,
        max_workers: int = EMAIL_MAX_WORKERS,
    ) -> list[EmailProcessingResult]:
        """Run emails concurrently, serializing those that share a thread.

        Emails on one thread contend on `thread_message_count` (a read-then-write
        `count(*) + 1`) and on `close_prior_processes`, so the thread — not the
        email — is the unit of concurrency: groups run in parallel, members of a
        group in order. Results come back in the caller's original order.
        """
        groups: dict[str, list[tuple[int, LoadedEmail]]] = defaultdict(list)
        for index, email in enumerate(emails):
            groups[email.thread_id or email.message_id or email.subject].append((index, email))

        semaphore = asyncio.Semaphore(max_workers)

        async def run_group(group: list[tuple[int, LoadedEmail]]) -> list[tuple[int, EmailProcessingResult]]:
            async with semaphore:
                return [(index, await self._run_safe(email, output_root)) for index, email in group]

        grouped = await asyncio.gather(*(run_group(g) for g in groups.values()))
        return [result for _index, result in sorted(pair for group in grouped for pair in group)]


def create_pipeline(llm_factory: LLMFactory | None = None) -> EmailPipeline:
    """Build an EmailPipeline, sharing one LLM factory across both phases."""
    if llm_factory is None:
        llm_factory = LLMFactory.from_settings(settings)

    return EmailPipeline(
        ingestion=create_ingestion_pipeline(llm_factory),
        extraction=create_extraction_pipeline(llm_factory),
    )


# Email-level markers. An email can carry several actions, so these are joined
# rather than looked up one-for-one.
_ACTION_MARKERS = {
    EMAIL_ARCHIVE: "📦 ARCHIVE",
    EMAIL_REPLY: "✉️  REPLY",
    EMAIL_TREASURY: "🏦 TREAS",
    EMAIL_INBOX: "📥 INBOX",
}


def print_email_summary(results: list[EmailProcessingResult]) -> None:
    """Email-level decisions, on top of the existing ingestion summary."""
    print("\n" + "=" * 70)
    print("EMAIL DECISIONS")
    print("=" * 70)
    for result in results:
        decision = result.decision
        marker = " + ".join(_ACTION_MARKERS.get(action, action) for action in decision.actions)
        print(f"  {marker}  {result.source} — {decision.reason}")

        # The reply that would go out, in the language it goes out in, and each
        # document's own action. The treasury forward has no per-document
        # reasons — its letter is fixed.
        for line in decision.reply_lines:
            print(f"            ↳ [{decision.language}] {line.get(decision.language, line)}")
        for document in decision.documents:
            print(f"            · {document.filename}: {document.action} ({document.reason})")


async def _process_batch(emails: list[LoadedEmail]) -> list[EmailProcessingResult]:
    """Run the emails through the pipeline and print the shared summaries."""
    print(f"Processing {len(emails)} email(s) from the inbox, {EMAIL_MAX_WORKERS} thread(s) at a time")
    print(f"Output root: {PROCESSED_EMAILS_DIR}")

    pipeline = create_pipeline()
    batch_started = time.perf_counter()
    results = await pipeline.run_batch(emails, PROCESSED_EMAILS_DIR)
    batch_elapsed = time.perf_counter() - batch_started

    # Per-document detail (reused reporter).
    for result in results:
        for extraction in result.extractions:
            print_pipeline_result(extraction)

    # Ingestion tally (reused), then the email-level decisions.
    print_summary([r.ingestion for r in results])
    print_email_summary(results)

    # Wall time, since per-email times overlap and cannot be summed.
    documents = sum(len(r.extractions) for r in results)
    print(
        f"\n⏱️  Batch: {batch_elapsed:.1f}s for {len(results)} email(s), {documents} document(s) "
        f"({EMAIL_MAX_WORKERS} email x {EXTRACTION_MAX_WORKERS} doc workers)"
    )
    return results


async def _run_test(pool: asyncpg.Pool | None) -> None:
    """`--test`: the newest DEFAULT_FETCH_LIMIT inbox messages, no cursor, no lock."""
    # Dedup happens once, here, before fetch — an empty skip set with
    # WRITE_TO_DB off keeps that mode able to run with no database up.
    processed = await _processed_message_ids() if pool is not None else set()
    emails = await invoice_client().fetch_recent(limit=DEFAULT_FETCH_LIMIT, skip_message_ids=processed)
    if INGEST_LIMIT is not None:
        emails = emails[:INGEST_LIMIT]

    results = await _process_batch(emails)
    if pool is not None:
        await _upsert_processed(pool, emails, results)


async def _run_cron(pool: asyncpg.Pool) -> None:
    """The scheduled run: lock, SYNC, PROCESS, log. See the module docstring."""
    client = invoice_client()
    mailbox = client.mailbox.label

    # The lock is tied to this connection: it is released when the connection
    # goes, so a crash cannot leave it held. Nothing else runs on it.
    lock_conn = await pool.acquire()
    try:
        if not await lock_conn.fetchval("SELECT pg_try_advisory_lock($1)", RUN_LOCK_KEY):
            await _start_run(mailbox, RUN_SKIPPED)
            print("⏭️  Another run is still going — skipped")
            return

        # Read under the lock, so it is the cursor the previous run left behind.
        cursor = await _load_cursor(mailbox)
        run_id = await _start_run(mailbox, RUN_RUNNING, cursor)
        sync = SyncStats()
        try:
            headers = await client.auth_headers()

            # --- SYNC -------------------------------------------------------------
            sync = await _sync_inbox(pool, client, headers, run_id, cursor)

            # --- PROCESS ----------------------------------------------------------
            reset = await _reset_stale_processing(pool)
            if reset:
                print(f"  ♻️  {reset} row(s) left at processing by a dead run — back to pending")

            claimed = await _claim_pending(pool, INGEST_LIMIT)
            emails, gone = await _load_claimed(client, headers, claimed)
            await _mark_gone(pool, gone, run_id)

            results = await _process_batch(emails)
            outcomes = [
                await _finish_message(pool, email, result, run_id) for email, result in zip(emails, results)
            ]

            processed = outcomes.count(MSG_PROCESSED)
            failed = outcomes.count(MSG_FAILED)
            await _finish_run(pool, run_id, RUN_SUCCEEDED, sync, processed, failed, len(gone))
            print(f"\n✅ Run {run_id}: {processed} processed, {failed} failed, {len(gone)} gone")
        except Exception:
            await _finish_run(pool, run_id, RUN_FAILED, sync, error=traceback.format_exc())
            raise
    finally:
        await lock_conn.execute("SELECT pg_advisory_unlock($1)", RUN_LOCK_KEY)
        await pool.release(lock_conn)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inbox ingestion: cron run by default.")
    parser.add_argument(
        "--test",
        action="store_true",
        help=f"process the newest {DEFAULT_FETCH_LIMIT} inbox message(s) directly, without the sync cursor",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    install_buffering()

    if ENABLE_TRACING:
        setup_tracing(experiment_name=MLFLOW_EXPERIMENT)
    else:
        print("ℹ️  ENABLE_TRACING is off — tracing disabled")

    if not EMAIL_ACTIONS:
        print("ℹ️  EMAIL_ACTIONS is off — replies, forwards and archives are logged only")

    if not WRITE_TO_DB and not args.test:
        print("❌ WRITE_TO_DB is off — the cron run needs the database for its cursor. Use --test.")
        return

    # Only open a pool when something will actually be written — the point of
    # WRITE_TO_DB=False is being able to run (and trace) with no database up.
    pool = await get_pool() if WRITE_TO_DB else None
    try:
        if args.test:
            await _run_test(pool)
        else:
            assert pool is not None
            await _run_cron(pool)
    finally:
        # Traces export asynchronously, so flush before the process exits.
        flush_traces()
        if pool is not None:
            pool.terminate()


if __name__ == "__main__":
    asyncio.run(main())
