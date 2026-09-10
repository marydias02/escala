"""End-to-end per-email pipeline: INGEST one email -> EXTRACT its own PDFs -> DECIDE -> PERSIST.

This sits on top of the two existing (synchronous) pipelines without changing them:

- `ingestion_pipeline` (Phase 1) turns one `.msg` into a folder of single-document
  PDFs plus `email_content.json`.
- `extraction_pipeline` (Phase 2) classifies / extracts / validates one PDF.

The DB is async (asyncpg), so this module is async and is driven by
`asyncio.run(main())`; the sync ingestion/extraction `.run()` calls happen inside
the async flow. Writes go through the generic helpers in `utils.utils_db`.

PERSIST also looks BACKWARDS: a new email can settle an EARLIER process on the
same thread — the supplier answered what we asked — so `close_prior_processes`
closes those instead of leaving them `Aberto` forever.

Booking documents to SAP is NOT part of this pipeline — see `sap_pipeline`,
which runs separately, in bulk, over every `fct_documents` row at
`action = "Ingerir em SAP", status = "Criado"` regardless of which email wrote
it. A document can reach that state well after its email was processed (e.g.
after manual review), so SAP booking cannot be an inline step here.
"""

import asyncio
import json
import shutil
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from config.settings import settings
from invoice_extraction.config import (
    DEFAULT_FETCH_LIMIT,
    DOC_STATUS_COMMUNICATED,
    DOC_STATUS_CREATED,
    DOC_STATUS_FAILED,
    DOC_STATUS_IGNORED,
    EMAIL_MAX_WORKERS,
    ENABLE_TRACING,
    EXTRACTION_MAX_WORKERS,
    INGEST_LIMIT,
    MANIFEST_NAME,
    MLFLOW_EXPERIMENT,
    PROCESSED_EMAILS_DIR,
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
from invoice_extraction.invoice_utils.email_sender import (
    archive_message,
    forward_to_treasury,
    reply_to_supplier,
)
from invoice_extraction.invoice_utils.outlook_loader import fetch_inbox_emails
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
# Orchestrator
# --------------------------------------------------------------------------- #


class EmailPipeline:
    """Composes the ingestion and extraction pipelines and writes to Postgres."""

    def __init__(self, ingestion: IngestionPipeline, extraction: ExtractionPipeline):
        self.ingestion = ingestion
        self.extraction = extraction

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
            send_result = await reply_to_supplier(
                message_id=message_id,
                subject=reply_subject,
                comment=result.decision.reply_body,
            )
            if send_result.status == "sent":
                print(f"  📧 Reply sent to supplier {sender_email!r} — subject={reply_subject!r}")
            else:
                print(
                    f"  ⚠️  Reply to supplier {sender_email!r} FAILED ({send_result.error}) — subject={reply_subject!r}"
                )
            print(f"            body={result.decision.reply_body!r}")
            outcome = DOC_STATUS_COMMUNICATED if send_result.status == "sent" else DOC_STATUS_CREATED
            for filename, decision in decisions_by_file.items():
                if decision.action == REPLY:
                    statuses[filename] = outcome

        if result.decision.should_forward_to_treasury and result.decision.treasury_body:
            treasury_email = settings.TREASURY_EMAIL or ""
            treasury_subject = f"Documentos para tesouraria - {manifest.get('email_subject', '')}"
            send_result = await forward_to_treasury(
                message_id=message_id,
                to=treasury_email,
                subject=treasury_subject,
                comment=result.decision.treasury_body,
            )
            if send_result.status == "sent":
                print(f"  📧 Forwarded to treasury {treasury_email!r} — subject={treasury_subject!r}")
            else:
                print(
                    f"  ⚠️  Forward to treasury {treasury_email!r} FAILED "
                    f"({send_result.error}) — subject={treasury_subject!r}"
                )
            print(f"            body={result.decision.treasury_body!r}")
            outcome = DOC_STATUS_COMMUNICATED if send_result.status == "sent" else DOC_STATUS_CREATED
            for filename, decision in decisions_by_file.items():
                if decision.action == TREASURY:
                    statuses[filename] = outcome

        if result.decision.should_archive:
            send_result = await archive_message(message_id)
            if send_result.status == "sent":
                print(f"  📦 Archived message — subject={manifest.get('email_subject', '')!r}")
            else:
                print(f"  ⚠️  Archive FAILED ({send_result.error}) — subject={manifest.get('email_subject', '')!r}")

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

        No dedup gate here: `main()` fetches only messages whose `message_id`
        is not already in the database, so every email reaching this method is
        ingested unconditionally.

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


async def main() -> None:
    install_buffering()

    if ENABLE_TRACING:
        setup_tracing(experiment_name=MLFLOW_EXPERIMENT)
    else:
        print("ℹ️  ENABLE_TRACING is off — tracing disabled")

    # Only open a pool when something will actually be written — the point of
    # WRITE_TO_DB=False is being able to run (and trace) with no database up.
    pool = await get_pool() if WRITE_TO_DB else None
    try:
        # Dedup happens once, here, before fetch — an empty skip set with
        # WRITE_TO_DB off keeps that mode able to run with no database up.
        processed = await _processed_message_ids() if WRITE_TO_DB else set()
        emails = await fetch_inbox_emails(limit=DEFAULT_FETCH_LIMIT, skip_message_ids=processed)
        if INGEST_LIMIT is not None:
            emails = emails[:INGEST_LIMIT]

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

        # Ingestion tally (reused), then the new email-level decisions.
        print_summary([r.ingestion for r in results])
        print_email_summary(results)

        # Wall time, since per-email times overlap and cannot be summed.
        documents = sum(len(r.extractions) for r in results)
        print(
            f"\n⏱️  Batch: {batch_elapsed:.1f}s for {len(results)} email(s), {documents} document(s) "
            f"({EMAIL_MAX_WORKERS} email x {EXTRACTION_MAX_WORKERS} doc workers)"
        )
    finally:
        # Traces export asynchronously, so flush before the process exits.
        flush_traces()
        if pool is not None:
            pool.terminate()


if __name__ == "__main__":
    asyncio.run(main())
