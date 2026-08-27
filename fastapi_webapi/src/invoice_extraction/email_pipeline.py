"""End-to-end per-email pipeline: INGEST one email -> EXTRACT its own PDFs -> DECIDE -> PERSIST.

This sits on top of the two existing (synchronous) pipelines without changing them:

- `ingestion_pipeline` (Phase 1) turns one `.msg` into a folder of single-document
  PDFs plus `email_content.json`.
- `extraction_pipeline` (Phase 2) classifies / extracts / validates one PDF.

Running them separately means extraction sees a flat glob of every PDF and can
never reason about a whole email at once, and nothing records what was processed.
This orchestrator restores the per-email view: for each email it extracts exactly
the PDFs that email produced, makes one email-level decision ("reply to the
supplier because no usable invoice came out?"), and writes the outcome to
Postgres — one `fct_processes` row per email, one `fct_documents` row per PDF.

The DB is async (asyncpg), so this module is async and is driven by
`asyncio.run(main())`; the sync ingestion/extraction `.run()` calls happen inside
the async flow. Writes go through the generic helpers in `utils.utils_db`.

Booking documents to SAP is NOT part of this pipeline — see `sap_pipeline`,
which runs separately, in bulk, over every `fct_documents` row at
`action = "Ingerir em SAP", status = "Criado"` regardless of which email wrote
it. A document can reach that state well after its email was processed (e.g.
after manual review), so SAP booking cannot be an inline step here.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import settings
from invoice_extraction.config import (
    DEFAULT_FETCH_LIMIT,
    ENABLE_TRACING,
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
    EMAIL_TREASURY,
    IGNORE,
    INBOX,
    MANUAL,
    REPLY,
    TREASURY,
    DocumentAction,
    EmailDecision,
    build_alerts_list,
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
    print_summary,
)
from invoice_extraction.ingestion_pipeline import (
    create_pipeline as create_ingestion_pipeline,
)
from invoice_extraction.invoice_utils.email_sender import forward_to_treasury, reply_to_supplier
from invoice_extraction.invoice_utils.outlook_loader import fetch_inbox_emails
from invoice_extraction.invoice_utils.reporting import print_pipeline_result
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
    process_id: Optional[str] = None


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


def document_type_label(classification: Optional[DocumentClassification]) -> str:
    """Human-readable document type, e.g. "Invoice (Original)".

    A null state is treated as Original, matching the extraction gate's rule that
    an unstated document is the real thing rather than a copy.
    """
    if classification is None:
        return "Unknown"

    type_label = _TYPE_LABELS.get(
        classification.document_type.value, classification.document_type.value
    )
    state_value = (
        classification.document_state.value
        if classification.document_state is not None
        else "original"
    )
    state_label = _STATE_LABELS.get(state_value, state_value)
    return f"{type_label} ({state_label})"


def derive_status(result: PipelineResult, action: DocumentAction) -> str:
    """Map a document's outcome to a Status. Refine as the lifecycle grows.

    Most routed documents start life as "Criado": `EmailPipeline._send_followups`
    then carries out the document's email-level action (supplier reply, treasury
    forward) inline and overrides this with the outcome — "Comunicado" on
    success, left at "Criado" on failure. INGEST has no inline follow-up — SAP
    booking is `sap_pipeline`'s job, run separately in bulk — so it also stays
    at "Criado", same as MANUAL, which has no follow-up because a human has not
    looked at it yet.

    IGNORE and INBOX have no follow-up AND nothing pending: there is no action
    left to carry out (a duplicate whose original is already in the email;
    a cancelled or unprocessed document type), so the row is terminal from the
    moment it is written. Those go straight to "Ignorado" rather than sitting
    in "Criado" indistinguishable from documents still awaiting one.

    Only a document that actually broke (a stage raised, so no classification) is
    "Failed" — the pipeline did not manage to route it at all.
    """
    if result.status == "failed":
        return "Failed"
    if action in (IGNORE, INBOX):
        return "Ignorado"
    return "Criado"


# NOTE: the per-document action is no longer derived here. It comes from
# `decisions.decide_email`, which computes each document's action and then
# suppresses the ones the email as a whole does not warrant.


def _checked_to_dict(checked) -> Optional[dict]:
    """A Checked[T] field -> {"value", "confidence"}; None stays None."""
    if checked is None:
        return None
    return {"value": checked.value, "confidence": checked.confidence}


def build_document_content(validation: Optional[ValidationReport]) -> dict:
    """Flatten a ValidationReport into the document_content JSONB payload.

    Each field keeps its {value, confidence} so the validator's confidence
    survives for later review/thresholding. `po_list` is a list of those.
    """
    if validation is None:
        return {}

    content: dict = {
        name: _checked_to_dict(getattr(validation, name)) for name in _CONTENT_FIELDS
    }
    content["po_list"] = [_checked_to_dict(po) for po in validation.po_list]
    return content


def parse_reception_date(value: Optional[str]) -> Optional[datetime]:
    """Parse the manifest's ISO-8601 reception date to a datetime, or None.

    `fct_processes.reception_date` is a timestamptz; asyncpg maps a datetime
    straight through. A malformed/empty string becomes NULL (the column is
    nullable) rather than failing the insert.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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


def _load_manifest(folder: Optional[Path]) -> dict:
    """Read an email's `email_content.json`, or {} if it is missing/unreadable."""
    if folder is None:
        return {}
    try:
        return json.loads((folder / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


async def _processed_message_ids() -> set[str]:
    """Every `message_id` already recorded in fct_processes.

    Fetched once per run and passed to `fetch_inbox_emails`, so the loader can
    skip attachment downloads entirely for known messages — cheaper than one
    query per email, and the DB is the only dedup authority now.
    """
    rows = await select(f"SELECT message_id FROM {PROCESSES_TABLE} WHERE message_id IS NOT NULL")
    return {row["message_id"] for row in rows}


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #


class EmailPipeline:
    """Composes the ingestion and extraction pipelines and writes to Postgres."""

    def __init__(self, ingestion: IngestionPipeline, extraction: ExtractionPipeline):
        self.ingestion = ingestion
        self.extraction = extraction

    def _classify_body(
        self, email: LoadedEmail, ingestion: EmailIngestionResult
    ) -> Optional[EmailIntent]:
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

        Called from `_persist` AFTER every document row already exists at its
        day-one status ("Criado", see `derive_status`) — "Criado" is a real,
        queryable row, not a value only ever held in memory before being
        overwritten. This just decides which rows to UPDATE, and to what. A
        filename absent from the returned dict is left exactly as inserted.

        The supplier reply and the treasury forward are each sent ONCE per
        email, as a Graph reply/forward on the original message (`message_id`
        from the manifest) — `decision.reply_body`/`decision.treasury_body`
        are already deduped/joined across every REPLY/TREASURY document by
        `decisions.py` — not once per document. The reply is gated on
        `decision.should_reply` rather than on `decision.documents`, so it
        also fires for the no-usable-PDF case (an email-level REPLY with zero
        fct_documents rows) — there is simply nothing in the returned dict to
        apply that status to there, since no document row exists.

        INGEST documents are deliberately left at "Criado" here: booking to
        SAP is not an email-level action and can happen well after this email
        was processed (e.g. once a MANUAL document clears human review), so it
        is `sap_pipeline`'s job, run separately, in bulk, over every row at
        `action = INGEST, status = "Criado"` regardless of which email wrote it.

        Failures (Mail.Send is not yet a granted Graph permission — see
        `invoice_utils.email_sender`) leave the returned status at "Criado",
        so an email whose reply/forward could not be sent stays visible as
        outstanding rather than being marked done.
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
                    f"  ⚠️  Reply to supplier {sender_email!r} FAILED "
                    f"({send_result.error}) — subject={reply_subject!r}"
                )
            print(f"            body={result.decision.reply_body!r}")
            outcome = "Comunicado" if send_result.status == "sent" else "Criado"
            for filename, decision in decisions_by_file.items():
                if decision.action == REPLY:
                    statuses[filename] = outcome

        if result.decision.should_forward_to_treasury and result.decision.treasury_body:
            send_result = await forward_to_treasury(
                message_id=message_id,
                to=settings.TREASURY_EMAIL or "",
                subject=f"Documentos para tesouraria - {manifest.get('email_subject', '')}",
                comment=result.decision.treasury_body,
            )
            outcome = "Comunicado" if send_result.status == "sent" else "Criado"
            for filename, decision in decisions_by_file.items():
                if decision.action == TREASURY:
                    statuses[filename] = outcome

        return statuses

    async def _persist(self, result: EmailProcessingResult) -> None:
        """Write one fct_processes row, its fct_documents rows, and their
        fct_document_first_action rows.

        Every document is inserted first at its day-one status (`derive_status`
        — "Criado", or "Failed" if the pipeline broke on it): a real row, not
        just an in-memory value. `_send_followups` then carries out each
        document's email-level action and UPDATEs the rows it advances
        (REPLY/TREASURY -> "Comunicado"). INGEST rows stay at "Criado" here —
        SAP booking is `sap_pipeline`'s job, run separately in bulk. Two real
        writes per advanced document, deliberately — "Criado" stays an
        observable state, not a value overwritten before ever reaching the
        database.

        `fct_document_first_action` is written once, immediately after
        `fct_documents`, from the same `action` values — before any follow-up
        or later manual review can change them — so it always reflects the
        document's ORIGINAL routing, unlike `fct_documents.action`.

        Each row's `document_id` is generated here (rather than left to the
        column's DB-side default) so the whole batch can still go through one
        `insert_rows` call, yet every id is already known for the follow-up
        UPDATE — no per-row INSERT round-trip needed just to read one back.
        """
        ingestion = result.ingestion
        manifest = _load_manifest(ingestion.folder)

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
            },
            returning="process_id",
        )
        result.process_id = str(process_id)

        # Each document's FINAL action (post-suppression) comes from the decision.
        # Paired by filename rather than by position so the two lists cannot drift.
        actions = {d.filename: d.action for d in result.decision.documents}

        document_ids = {extraction.filename: str(uuid.uuid4()) for extraction in result.extractions}

        # Links each extracted document to its fct_documents row, on the email span
        set_span_attributes(document_ids=document_ids)

        rows = []
        for extraction in result.extractions:
            action = actions.get(extraction.filename, MANUAL)
            rows.append(
                {
                    "document_id": document_ids[extraction.filename],
                    "process_id": process_id,
                    "document_type": document_type_label(extraction.classification),
                    "action": action,
                    "status": derive_status(extraction, action),
                    "document_content": build_document_content(extraction.validation),
                    "alerts_list": build_alerts_list(extraction),
                    "created_by": "pipeline",
                    "file_path": f"{ingestion.folder.name}/{extraction.filename}" if ingestion.folder else None,
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
            ingestion = self.ingestion.run(email, output_root)

            # A failed email yields no fresh PDFs. Bundle and decide, but write
            # nothing — no body classification either, since nothing could be read.
            if ingestion.status != "ingested":
                decision = decide_email(ingestion, [])
                set_trace_tags(action=", ".join(decision.actions), outcome=ingestion.status)
                email_span.set_outputs(
                    {"ingestion_status": ingestion.status, "decision": decision_summary(decision)}
                )
                return EmailProcessingResult(
                    source=source,
                    ingestion=ingestion,
                    decision=decision,
                )

            # --- EXTRACT (this email's own PDFs only) ---------------------------
            pdf_paths = _produced_pdf_paths(ingestion)
            extractions = self.extraction.run_batch(pdf_paths)

            # --- DECIDE ---------------------------------------------------------
            # No usable PDF (A1/A2) is the only case the body can change, so the
            # extra LLM call is confined to it.
            intent = self._classify_body(email, ingestion) if not extractions else None

            # A span of its own even though it is pure, LLM-free business logic:
            # the routing rules are the part most likely to be questioned, and
            # this records the inputs they saw alongside the answer they gave.
            with span(STAGE_DECISION, "CHAIN") as decision_span:
                decision_span.set_inputs(
                    {
                        "documents": [
                            {"filename": e.filename, "status": e.status} for e in extractions
                        ],
                        "attachments": len(ingestion.attachments),
                    }
                )
                decision = decide_email(ingestion, extractions, intent=intent)
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
                await self._persist(result)
                # Links the trace to its fct_processes row.
                set_trace_tags(process_id=result.process_id)
            else:
                print("  💾 WRITE_TO_DB is off — not persisting")

            return result

    async def run_batch(
        self,
        emails: list[LoadedEmail],
        output_root: Path = PROCESSED_EMAILS_DIR,
    ) -> list[EmailProcessingResult]:
        """Run several emails, isolating failures so one bad email cannot kill the run."""
        results: list[EmailProcessingResult] = []

        for email in emails:
            source = email.message_id or email.subject
            print(f"\n{'=' * 70}\n📧 {email.subject}\n{'=' * 70}")
            started = time.perf_counter()
            try:
                result = await self.run(email, output_root)
            except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
                message = f"{type(exc).__name__}: {exc}"
                print(f"  ❌ Failed: {message}")
                failed = EmailIngestionResult(source=source, status="failed", message=message)
                results.append(
                    EmailProcessingResult(
                        source=source,
                        ingestion=failed,
                        decision=decide_email(failed, []),
                    )
                )
                continue

            print(f"  ⏱️  {time.perf_counter() - started:.1f}s")
            results.append(result)

        return results


def create_pipeline(llm_factory: Optional[LLMFactory] = None) -> EmailPipeline:
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

        # The reply and/or treasury forward that would go out, and each
        # document's own action.
        for line in decision.reply_lines:
            print(f"            ↳ {line}")
        for line in decision.treasury_lines:
            print(f"            ↳ {line}")
        for document in decision.documents:
            print(f"            · {document.filename}: {document.action} ({document.reason})")


async def main() -> None:
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

        print(f"Processing {len(emails)} email(s) from the inbox")
        print(f"Output root: {PROCESSED_EMAILS_DIR}")

        pipeline = create_pipeline()
        results = await pipeline.run_batch(emails, PROCESSED_EMAILS_DIR)

        # Per-document detail (reused reporter).
        for result in results:
            for extraction in result.extractions:
                print_pipeline_result(extraction)

        # Ingestion tally (reused), then the new email-level decisions.
        print_summary([r.ingestion for r in results])
        print_email_summary(results)
    finally:
        # Traces export asynchronously, so flush before the process exits.
        flush_traces()
        if pool is not None:
            pool.terminate()


if __name__ == "__main__":
    asyncio.run(main())
