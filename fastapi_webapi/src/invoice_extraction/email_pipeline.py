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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import settings
from invoice_extraction.config import (
    FORCE_REINGEST,
    INGEST_LIMIT,
    MANIFEST_NAME,
    ORIGINAL_EMAILS_DIR,
    PROCESSED_EMAILS_DIR,
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
from invoice_extraction.models import DocumentClassification, ValidationReport
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
    """

    source: str
    ingestion: EmailIngestionResult
    extractions: list[PipelineResult] = field(default_factory=list)
    should_reply_to_supplier: bool = False
    reply_reason: str = ""
    process_id: Optional[str] = None
    already_processed: bool = False


# --------------------------------------------------------------------------- #
# Email-level decision — THE place to change the reply rule.
# --------------------------------------------------------------------------- #


def should_reply_to_supplier(
    ingestion: EmailIngestionResult,
    extractions: list[PipelineResult],
) -> tuple[bool, str]:
    """Decide whether to reply to the supplier — THE place to change this rule.

    Initial rule (revisable): reply when the email produced NO usable invoice.
    The single trigger is "no attachment reached 'validated'"; the reason then
    distinguishes the three no-invoice cases so wording (and, later, the action)
    can differ.

    `ingestion` is passed in — rather than just the extractions — so we can tell
    "no attachments" from "attachments but no PDF", and so a future body-aware
    rule has the email body (via `email_content.json`) to hand. The body is not
    used yet.
    """
    validated = [e for e in extractions if e.status == "validated"]
    if validated:
        return False, f"{len(validated)}/{len(extractions)} attachment(s) validated"

    # No usable invoice — pick the reason that describes why.
    if not ingestion.attachments:
        return True, "email had no attachments"
    if not any(a.status == "chunked" for a in ingestion.attachments):
        return True, "email had attachments but none was a PDF"
    return True, "PDF attachments present but none reached 'validated'"


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


def derive_status(result: PipelineResult) -> str:
    """Map a pipeline outcome to a document Status. Refine as lifecycle grows.

    validated -> Ingested (finished the pipeline)
    skipped   -> Failed   (gated out: not an invoice / not an original — not usable)
    failed    -> Failed   (a stage raised)
    """
    if result.status == "validated":
        return "Ingested"
    return "Failed"


def derive_action(result: PipelineResult, should_reply: bool) -> str:
    """Best-effort next action for a document — THE place to refine this mapping."""
    if result.status == "validated":
        return "Ingest in SAP"
    if should_reply:
        return "Sent back to Supplier"
    return "Validate Manually"


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


def build_alerts_list(ingestion: EmailIngestionResult, result: PipelineResult) -> list[str]:
    """Alerts for one document. Empty for now — THE place to wire real sources."""
    return []


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

        rows = [
            {
                "process_id": process_id,
                "document_type": document_type_label(extraction.classification),
                "action": derive_action(extraction, result.should_reply_to_supplier),
                "status": derive_status(extraction),
                "document_content": build_document_content(extraction.validation),
                "alerts_list": build_alerts_list(ingestion, extraction),
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
        """Ingest one email, extract its PDFs, decide, and persist to Postgres."""
        msg_path = Path(msg_path)
        source = msg_path.name

        # --- DEDUP (DB): parse the email's identity cheaply (no LLM) and skip if
        # it is already recorded. `.msg` parsing is cheap; the extra parse keeps
        # the existing ingestion pipeline untouched.
        if not force:
            try:
                email = load_msg(msg_path)
                if await _process_exists(
                    email.sender_email, email.subject, parse_reception_date(email.reception_date)
                ):
                    return EmailProcessingResult(
                        source=source,
                        ingestion=EmailIngestionResult(
                            source=source, status="skipped", message="already in database"
                        ),
                        already_processed=True,
                        reply_reason="skipped (already processed)",
                    )
            except Exception:  # noqa: BLE001 - dedup is best-effort; fall through to ingest
                pass

        # --- INGEST -----------------------------------------------------------
        ingestion = self.ingestion.run(msg_path, output_root, force=force)

        # An already-ingested (manifest-skip) or failed email yields no fresh PDFs.
        # Bundle and decide, but write nothing.
        if ingestion.status != "ingested":
            should_reply, reason = should_reply_to_supplier(ingestion, [])
            return EmailProcessingResult(
                source=source,
                ingestion=ingestion,
                should_reply_to_supplier=should_reply,
                reply_reason=reason,
                already_processed=(ingestion.status == "skipped"),
            )

        # --- EXTRACT (this email's own PDFs only) -----------------------------
        pdf_paths = _produced_pdf_paths(ingestion)
        extractions = self.extraction.run_batch(pdf_paths)

        # --- DECIDE -----------------------------------------------------------
        should_reply, reason = should_reply_to_supplier(ingestion, extractions)
        result = EmailProcessingResult(
            source=source,
            ingestion=ingestion,
            extractions=extractions,
            should_reply_to_supplier=should_reply,
            reply_reason=reason,
        )

        # --- PERSIST ----------------------------------------------------------
        await self._persist(result)
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
            try:
                result = await self.run(msg_path, output_root, force=force)
            except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
                message = f"{type(exc).__name__}: {exc}"
                print(f"  ❌ Failed: {message}")
                results.append(
                    EmailProcessingResult(
                        source=msg_path.name,
                        ingestion=EmailIngestionResult(
                            source=msg_path.name, status="failed", message=message
                        ),
                        reply_reason=f"processing failed: {message}",
                    )
                )
                continue

            if result.already_processed:
                print("  ⏭️  already processed")
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


def print_email_summary(results: list[EmailProcessingResult]) -> None:
    """Email-level decisions, on top of the existing ingestion summary."""
    print("\n" + "=" * 70)
    print("EMAIL DECISIONS")
    print("=" * 70)
    for result in results:
        if result.already_processed and not result.extractions:
            marker = "⏭️  skip "
        elif result.should_reply_to_supplier:
            marker = "✉️  REPLY"
        else:
            marker = "✅ ok   "
        print(f"  {marker}  {result.source} — {result.reply_reason}")


async def main() -> None:
    msg_paths = sorted(ORIGINAL_EMAILS_DIR.glob("*.msg"))
    if INGEST_LIMIT is not None:
        msg_paths = msg_paths[:INGEST_LIMIT]

    print(f"Processing {len(msg_paths)} email(s) from {ORIGINAL_EMAILS_DIR}")
    print(f"Output root: {PROCESSED_EMAILS_DIR}")

    pool = await get_pool()
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
        pool.terminate()


if __name__ == "__main__":
    asyncio.run(main())
