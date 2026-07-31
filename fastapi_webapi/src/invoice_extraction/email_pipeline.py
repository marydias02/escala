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
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import settings
from invoice_extraction.config import (
    ENABLE_TRACING,
    FORCE_REINGEST,
    INGEST_LIMIT,
    MANIFEST_NAME,
    MLFLOW_EXPERIMENT,
    ORIGINAL_EMAILS_DIR,
    PROCESSED_EMAILS_DIR,
    WRITE_TO_DB,
)
from invoice_extraction.decisions import (
    EMAIL_ARCHIVE,
    EMAIL_INBOX,
    EMAIL_REPLY,
    EMAIL_TREASURY,
    IGNORE,
    INGEST,
    MANUAL,
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
from invoice_extraction.invoice_utils.reporting import print_pipeline_result
from invoice_extraction.loading import load_msg
from invoice_extraction.models import DocumentClassification, EmailIntent, ValidationReport
from invoice_extraction.nodes import classify_email_intent
from invoice_extraction.tracing import (
    STAGE_DECISION,
    decision_summary,
    set_trace_tags,
    setup_tracing,
    span,
)
from invoice_extraction.tracing import (
    flush as flush_traces,
)
from utils.llm_factory import LLMFactory
from utils.utils_db import get_pool, insert_row, insert_rows, select

PROCESSES_TABLE = "fct_processes"
DOCUMENTS_TABLE = "fct_documents"

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

    already_processed marks an email skipped because its process was already in
    the database, or skipped by ingestion's on-disk manifest marker.

    `decision` carries the email-level action, the reply text (if any) and the
    final per-document actions. See `invoice_extraction.decisions`.
    """

    source: str
    ingestion: EmailIngestionResult
    decision: EmailDecision
    extractions: list[PipelineResult] = field(default_factory=list)
    process_id: Optional[str] = None
    already_processed: bool = False


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


def derive_status(result: PipelineResult, action: str) -> str:
    """Map a document's outcome to a Status. Refine as the lifecycle grows.

    Driven by the DECIDED ACTION rather than the raw pipeline status, because the
    two disagree in the ordinary case: a receipt bound for treasury and a proforma
    bound back to the supplier both leave the pipeline as "skipped", yet neither
    is a failure — the pipeline did its job and routed them.

    Only a document that actually broke (a stage raised, so no classification) is
    "Failed"; everything routed somewhere is "Pending" until that action happens.

    An IGNORE document is the exception to that last part: nothing is ever going
    to happen to a duplicate whose original we already hold, so calling it
    "Pending" would leave a row that never resolves.
    """
    if action == INGEST:
        return "Ingested"
    if action == IGNORE:
        return "Ignored"
    if result.status == "failed":
        return "Failed"
    return "Pending"


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


async def _process_exists(sender_email: str, email_subject: str, reception_date: Optional[datetime]) -> bool:
    """Is an email with this natural identity already recorded in fct_processes?

    process_id is DB-generated, so identity is (sender, subject, reception_date).
    A NULL reception_date is matched with IS NOT DISTINCT FROM so it compares equal.
    """
    rows = await select(
        f"""
        SELECT 1 FROM {PROCESSES_TABLE}
        WHERE sender_email = $1
          AND email_subject IS NOT DISTINCT FROM $2
          AND reception_date IS NOT DISTINCT FROM $3
        LIMIT 1
        """,
        [sender_email, email_subject, reception_date],
    )
    return len(rows) > 0


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #


class EmailPipeline:
    """Composes the ingestion and extraction pipelines and writes to Postgres."""

    def __init__(self, ingestion: IngestionPipeline, extraction: ExtractionPipeline):
        self.ingestion = ingestion
        self.extraction = extraction

    def _classify_body(
        self, msg_path: Path, ingestion: EmailIngestionResult
    ) -> Optional[EmailIntent]:
        """Classify the email body, for the cases where no usable PDF came out.

        Prefers the manifest ingestion just wrote; falls back to re-parsing the
        `.msg` when there is no folder (an email with no attachments may not get
        one). Returns None if neither source yields a body — `decide_email` then
        leaves the email in the inbox rather than guessing.

        Best-effort: a classifier failure must not lose the whole email, so it
        degrades to None.
        """
        manifest = _load_manifest(ingestion.folder)
        subject = manifest.get("email_subject")
        body = manifest.get("email_content")

        if subject is None and body is None:
            try:
                email = load_msg(msg_path)
                subject, body = email.subject, email.body
            except Exception as exc:  # noqa: BLE001 - fall back to "unknown intent"
                print(f"  ⚠️  Could not read body for intent: {type(exc).__name__}: {exc}")
                return None

        try:
            return classify_email_intent(self.extraction.llm, subject or "", body or "")
        except Exception as exc:  # noqa: BLE001 - a failed classification is not fatal
            print(f"  ⚠️  Email intent classification failed: {type(exc).__name__}: {exc}")
            return None

    async def _persist(self, result: EmailProcessingResult) -> None:
        """Write one fct_processes row and its fct_documents rows."""
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
            },
            returning="process_id",
        )
        result.process_id = str(process_id)

        # Each document's FINAL action (post-suppression) comes from the decision.
        # Paired by filename rather than by position so the two lists cannot drift.
        actions = {d.filename: d.action for d in result.decision.documents}

        rows = [
            {
                "process_id": process_id,
                "document_type": document_type_label(extraction.classification),
                "action": actions.get(extraction.filename, MANUAL),
                "status": derive_status(extraction, actions.get(extraction.filename, MANUAL)),
                "document_content": build_document_content(extraction.validation),
                "alerts_list": build_alerts_list(extraction),
                "created_by": "pipeline",
            }
            for extraction in result.extractions
        ]
        # document_id, version, created_at/last_modified_at fall to DB defaults.
        await insert_rows(DOCUMENTS_TABLE, rows, jsonb_columns=["document_content"])

    async def run(
        self,
        msg_path: Path,
        output_root: Path = PROCESSED_EMAILS_DIR,
        force: bool = FORCE_REINGEST,
    ) -> EmailProcessingResult:
        """Ingest one email, extract its PDFs, decide, and persist to Postgres.

        The whole email is one trace: every ingestion, extraction and decision
        span below nests under this one, so a single trace answers "what happened
        to this email, and why".
        """
        msg_path = Path(msg_path)
        source = msg_path.name

        with span(f"email:{source}", "CHAIN") as email_span:
            email_span.set_inputs({"source": source, "force": force})
            set_trace_tags(email=source)

            # --- DEDUP (DB): parse the email's identity cheaply (no LLM) and skip
            # if it is already recorded. `.msg` parsing is cheap; the extra parse
            # keeps the existing ingestion pipeline untouched.
            if not force:
                try:
                    email = load_msg(msg_path)
                    if await _process_exists(
                        email.sender_email, email.subject, parse_reception_date(email.reception_date)
                    ):
                        skipped = EmailIngestionResult(
                            source=source, status="skipped", message="already in database"
                        )
                        decision = decide_email(skipped, [])
                        set_trace_tags(action=", ".join(decision.actions), outcome="already_processed")
                        email_span.set_outputs(
                            {"already_processed": True, "decision": decision_summary(decision)}
                        )
                        return EmailProcessingResult(
                            source=source,
                            ingestion=skipped,
                            decision=decision,
                            already_processed=True,
                        )
                except Exception:  # noqa: BLE001 - dedup is best-effort; fall through to ingest
                    pass

            # --- INGEST ---------------------------------------------------------
            ingestion = self.ingestion.run(msg_path, output_root, force=force)

            # An already-ingested (manifest-skip) or failed email yields no fresh
            # PDFs. Bundle and decide, but write nothing. No body classification
            # here: a skip is already-decided work and a failure means nothing
            # could be read.
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
                    already_processed=(ingestion.status == "skipped"),
                )

            # --- EXTRACT (this email's own PDFs only) ---------------------------
            pdf_paths = _produced_pdf_paths(ingestion)
            extractions = self.extraction.run_batch(pdf_paths)

            # --- DECIDE ---------------------------------------------------------
            # No usable PDF (A1/A2) is the only case the body can change, so the
            # extra LLM call is confined to it.
            intent = self._classify_body(msg_path, ingestion) if not extractions else None

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
            else:
                print("  💾 WRITE_TO_DB is off — not persisting")

            return result

    async def run_batch(
        self,
        msg_paths: list[Path],
        output_root: Path = PROCESSED_EMAILS_DIR,
        force: bool = FORCE_REINGEST,
    ) -> list[EmailProcessingResult]:
        """Run several emails, isolating failures so one bad email cannot kill the run."""
        results: list[EmailProcessingResult] = []

        for msg_path in msg_paths:
            msg_path = Path(msg_path)
            print(f"\n{'=' * 70}\n📧 {msg_path.name}\n{'=' * 70}")
            started = time.perf_counter()
            try:
                result = await self.run(msg_path, output_root, force=force)
            except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
                message = f"{type(exc).__name__}: {exc}"
                print(f"  ❌ Failed: {message}")
                failed = EmailIngestionResult(
                    source=msg_path.name, status="failed", message=message
                )
                results.append(
                    EmailProcessingResult(
                        source=msg_path.name,
                        ingestion=failed,
                        decision=decide_email(failed, []),
                    )
                )
                continue

            if result.already_processed:
                print("  ⏭️  already processed")
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
        if result.already_processed and not result.extractions:
            marker = "⏭️  skip "
        else:
            marker = " + ".join(
                _ACTION_MARKERS.get(action, action) for action in decision.actions
            )
        print(f"  {marker}  {result.source} — {decision.reason}")

        # The reply that would go out, and each document's own action.
        for line in decision.reply_lines:
            print(f"            ↳ {line}")
        for document in decision.documents:
            print(f"            · {document.filename}: {document.action} ({document.reason})")


async def main() -> None:
    msg_paths = sorted(ORIGINAL_EMAILS_DIR.glob("*.msg"))
    if INGEST_LIMIT is not None:
        msg_paths = msg_paths[:INGEST_LIMIT]

    print(f"Processing {len(msg_paths)} email(s) from {ORIGINAL_EMAILS_DIR}")
    print(f"Output root: {PROCESSED_EMAILS_DIR}")

    if ENABLE_TRACING:
        setup_tracing(experiment_name=MLFLOW_EXPERIMENT)
    else:
        print("ℹ️  ENABLE_TRACING is off — tracing disabled")

    # Only open a pool when something will actually be written — the point of
    # WRITE_TO_DB=False is being able to run (and trace) with no database up.
    pool = await get_pool() if WRITE_TO_DB else None
    try:
        pipeline = create_pipeline()
        results = await pipeline.run_batch(msg_paths, PROCESSED_EMAILS_DIR, force=FORCE_REINGEST)

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
