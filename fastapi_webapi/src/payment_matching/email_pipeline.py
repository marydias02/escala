"""End-to-end per-message pipeline: INGEST one message -> READ its notes -> PERSIST.

`main` is the cron entrypoint: take the advisory lock, sync the mailbox delta
into `payment_email_messages`, claim the oldest pending rows and process them.
`main --test` skips all of that and runs the newest messages directly.

Persistence is NOT implemented — see `_persist`. `WRITE_TO_DB` is off and a run
writes only its working folder, so `--test` is the mode that works today.
"""

import argparse
import asyncio
import io
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import asyncpg

from config.settings import settings
from email_core.sync import (
    RUN_FAILED,
    RUN_RUNNING,
    RUN_SKIPPED,
    RUN_SUCCEEDED,
    MessageStore,
    SyncRunStore,
    SyncStats,
    load_claimed,
    sync_mailbox,
)
from payment_matching.config import (
    DEFAULT_FETCH_LIMIT,
    DELTA_PAGE_SIZE,
    EMAIL_MAX_WORKERS,
    ENABLE_TRACING,
    INGEST_LIMIT,
    INITIAL_SYNC_LOOKBACK,
    MAX_ATTEMPTS,
    MESSAGES_TABLE,
    MLFLOW_EXPERIMENT_EMAIL_PIPELINE,
    MSG_FAILED,
    MSG_PROCESSED,
    PAYMENT_RUN_LOCK_KEY,
    PROCESSED_EMAILS_DIR,
    WRITE_TO_DB,
)
from payment_matching.ingestion_pipeline import PaymentIngestionResult
from payment_matching.ingestion_pipeline import create_pipeline as create_ingestion_pipeline
from payment_matching.ingestion_pipeline import print_summary as print_ingestion_summary
from payment_matching.mailbox import payment_client
from payment_matching.note_pipeline import NotePipeline, NoteResult, print_note_result
from payment_matching.note_pipeline import create_pipeline as create_note_pipeline
from payment_matching.tracing import flush as flush_traces
from payment_matching.tracing import set_trace_tags, setup_tracing, span
from utils.llm_factory import LLMFactory


@dataclass
class MessageResult:
    """Outcome of running one message end to end."""

    source: str
    ingestion: PaymentIngestionResult
    notes: list[NoteResult] = field(default_factory=list)

    @property
    def extracted_notes(self) -> list[NoteResult]:
        return [n for n in self.notes if n.status == "extracted"]


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #


class PaymentEmailPipeline:
    """Composes the ingestion and note pipelines."""

    def __init__(self, ingestion, notes: NotePipeline):
        self.ingestion = ingestion
        self.notes = notes

    async def _persist(self, result: MessageResult) -> None:
        """Write one message's outcome to Postgres.

        TODO: not implemented — `payment_email_messages`,
        `email_payment_information` and `payment_note` have no migrations yet.

        The order is fixed and must be kept when this is filled in:

            1. upload the working folder to blob storage FIRST, so no row can
               reference a missing blob;
            2. INSERT email_payment_information — one row, carrying
               `body_pdf_path` and the body's values in `extraction_content`;
            3. INSERT payment_note — one row per (note, settled document) pair,
               all rows of one note in a single `insert_rows` call so a
               half-written note cannot read as settling less than it does;
            4. UPDATE payment_email_messages.status;
            5. delete the local working folder.
        """
        if not WRITE_TO_DB:
            return
        raise NotImplementedError("payment persistence is not implemented — the tables have no migrations yet")

    async def run(self, email, output_root: Path = PROCESSED_EMAILS_DIR) -> MessageResult:
        """Ingest one message, read its note candidates, persist.

        The whole message is one trace: every ingestion, segmentation and note
        span nests under this one.
        """
        source = email.message_id or email.subject

        with span(f"payment-email:{source}", "CHAIN") as message_span:
            message_span.set_inputs({"source": source, "subject": email.subject})
            set_trace_tags(message=source, model=self.notes.llm_factory.model)

            # --- INGEST ---------------------------------------------------------
            # Threaded: sync and LLM-bound, so it would otherwise pin the loop.
            ingestion = await asyncio.to_thread(self.ingestion.run, email, output_root)

            # --- NOTES ----------------------------------------------------------
            # Attachment splits only: the body PDF is evidence for the email row,
            # never an input to note extraction.
            notes: list[NoteResult] = []
            if ingestion.folder is not None and ingestion.note_candidates:
                paths = [ingestion.folder / name for name in ingestion.note_candidates]
                notes = await self.notes.run_batch(paths)

            result = MessageResult(source=source, ingestion=ingestion, notes=notes)

            set_trace_tags(
                payment_related=ingestion.is_payment_related,
                candidates=len(ingestion.note_candidates),
                notes=len(result.extracted_notes),
            )
            message_span.set_outputs(
                {
                    "payment_related": ingestion.is_payment_related,
                    "body_pdf": ingestion.body_pdf,
                    "candidates": len(ingestion.note_candidates),
                    "notes_extracted": len(result.extracted_notes),
                }
            )

            # --- PERSIST --------------------------------------------------------
            if WRITE_TO_DB:
                await self._persist(result)
            else:
                print("  💾 WRITE_TO_DB is off — not persisting")

            return result

    async def _run_safe(self, email, output_root: Path) -> MessageResult:
        """`run`, but a raised exception becomes a `failed` result."""
        source = email.message_id or email.subject
        print(f"\n{'=' * 70}\n📧 {email.subject}\n{'=' * 70}")
        started = time.perf_counter()

        try:
            result = await self.run(email, output_root)
        except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
            message = f"{type(exc).__name__}: {exc}"
            print(f"  ❌ Failed: {message}")
            failed = PaymentIngestionResult(source=source, status="failed", message=message)
            return MessageResult(source=source, ingestion=failed)

        print(f"  ⏱️  {time.perf_counter() - started:.1f}s")
        return result

    async def run_batch(
        self,
        emails: list,
        output_root: Path = PROCESSED_EMAILS_DIR,
        max_workers: int = EMAIL_MAX_WORKERS,
    ) -> list[MessageResult]:
        """Run messages concurrently.

        Payment messages carry no shared state, so they need no per-thread
        grouping — unlike invoice emails, which contend on thread position.
        """
        semaphore = asyncio.Semaphore(max_workers)

        async def one(email) -> MessageResult:
            async with semaphore:
                return await self._run_safe(email, output_root)

        return list(await asyncio.gather(*(one(e) for e in emails)))


def create_pipeline(llm_factory: LLMFactory | None = None) -> PaymentEmailPipeline:
    """Build a PaymentEmailPipeline, sharing one LLM factory across both phases."""
    if llm_factory is None:
        llm_factory = LLMFactory.from_settings(settings)

    return PaymentEmailPipeline(
        ingestion=create_ingestion_pipeline(llm_factory),
        notes=create_note_pipeline(llm_factory),
    )


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def print_message_summary(results: list[MessageResult]) -> None:
    """What each message yielded, after the shared ingestion tally."""
    print("\n" + "=" * 70)
    print("PAYMENT MESSAGES")
    print("=" * 70)
    for result in results:
        ingestion = result.ingestion
        marker = "💶" if ingestion.is_payment_related else "  "
        body = f", body={ingestion.body_pdf}" if ingestion.body_pdf else ""
        print(
            f"  {marker} {result.source} — payment={ingestion.is_payment_related}{body}, "
            f"{len(result.extracted_notes)} note(s) of {len(ingestion.note_candidates)} candidate(s)"
        )


async def _process_batch(emails: list) -> list[MessageResult]:
    """Run the messages through the pipeline and print the summaries."""
    print(f"Processing {len(emails)} message(s), {EMAIL_MAX_WORKERS} at a time")
    print(f"Output root: {PROCESSED_EMAILS_DIR}")

    pipeline = create_pipeline()
    started = time.perf_counter()
    results = await pipeline.run_batch(emails, PROCESSED_EMAILS_DIR)
    elapsed = time.perf_counter() - started

    for result in results:
        for note in result.notes:
            print_note_result(note)

    print_ingestion_summary([r.ingestion for r in results])
    print_message_summary(results)

    notes = sum(len(r.extracted_notes) for r in results)
    print(f"\n⏱️  Batch: {elapsed:.1f}s for {len(results)} message(s), {notes} note(s)")
    return results


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #


async def _finish_message(pool: asyncpg.Pool, email, result: MessageResult, run_id: uuid.UUID) -> str:
    """Write one message's outcome to its `payment_email_messages` row.

    TODO: not implemented alongside `_persist` — both need the payment tables.
    """
    raise NotImplementedError("payment persistence is not implemented — the tables have no migrations yet")


async def _run_test(limit: int) -> None:
    """`--test`: the newest `limit` messages, no cursor, no lock, no database."""
    emails = await payment_client().fetch_recent(limit=limit)
    if not emails:
        print("No messages in the mailbox.")
        return

    await _process_batch(emails)


async def _run_cron(pool: asyncpg.Pool) -> None:
    """The scheduled run: lock, SYNC, PROCESS, log.

    Mirrors the invoice cron over this mailbox and this messages table. It
    cannot complete until the payment tables exist — `_finish_message` raises —
    but the sync half is correct and the shape is settled.
    """
    client = payment_client()
    runs = SyncRunStore(client.mailbox.label)
    store = MessageStore(MESSAGES_TABLE, max_attempts=MAX_ATTEMPTS)

    # The lock is tied to this connection: it is released when the connection
    # goes, so a crash cannot leave it held. Nothing else runs on it.
    lock_conn = await pool.acquire()
    try:
        if not await lock_conn.fetchval("SELECT pg_try_advisory_lock($1)", PAYMENT_RUN_LOCK_KEY):
            await runs.start(RUN_SKIPPED)
            print("⏭️  Another run is still going — skipped")
            return

        # Read under the lock, so it is the cursor the previous run left behind.
        cursor = await runs.load_cursor()
        run_id = await runs.start(RUN_RUNNING, cursor)
        sync = SyncStats()
        try:
            # --- SYNC -------------------------------------------------------------
            sync = await sync_mailbox(
                pool,
                client,
                store,
                run_id,
                cursor,
                page_size=DELTA_PAGE_SIZE,
                initial_lookback=INITIAL_SYNC_LOOKBACK,
            )

            # --- PROCESS ----------------------------------------------------------
            reset = await store.reset_stale(pool)
            if reset:
                print(f"  ♻️  {reset} row(s) left at processing by a dead run — back to pending")

            claimed = await store.claim_pending(pool, INGEST_LIMIT)
            emails, gone = await load_claimed(client, claimed)
            await store.mark_gone(pool, gone, run_id)

            results = await _process_batch(emails)
            outcomes = [await _finish_message(pool, email, result, run_id) for email, result in zip(emails, results)]

            processed = outcomes.count(MSG_PROCESSED)
            failed = outcomes.count(MSG_FAILED)
            await runs.finish(pool, run_id, RUN_SUCCEEDED, sync, processed, failed, len(gone))
            print(f"\n✅ Run {run_id}: {processed} processed, {failed} failed, {len(gone)} gone")
        except Exception:
            await runs.finish(pool, run_id, RUN_FAILED, sync, error=traceback.format_exc())
            raise
    finally:
        await lock_conn.execute("SELECT pg_advisory_unlock($1)", PAYMENT_RUN_LOCK_KEY)
        await pool.release(lock_conn)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Payment mailbox ingestion: cron run by default.")
    parser.add_argument(
        "--test",
        action="store_true",
        help="process the newest message(s) directly, without the sync cursor",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_FETCH_LIMIT,
        help=f"how many messages --test pulls (default {DEFAULT_FETCH_LIMIT})",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if ENABLE_TRACING:
        setup_tracing(experiment_name=MLFLOW_EXPERIMENT_EMAIL_PIPELINE)
    else:
        print("ℹ️  ENABLE_TRACING is off — tracing disabled")

    if not WRITE_TO_DB:
        print("ℹ️  WRITE_TO_DB is off — persistence is not implemented yet (see _persist)")

    if not args.test:
        print("❌ The cron run needs the payment tables, which do not exist yet. Use --test.")
        return

    try:
        await _run_test(args.limit)
    finally:
        # Traces export asynchronously, so flush before the process exits.
        flush_traces()


if __name__ == "__main__":
    asyncio.run(main())
