"""Invoice extraction pipeline: CLASSIFY -> EXTRACT -> VALIDATE.

The pipeline starts from an already-split PDF: one file == one accounting
document. Email ingestion and multi-document splitting are handled upstream by
`ingestion_pipeline`, which writes those files under `PROCESSED_EMAILS_DIR`.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from langchain_core.language_models import BaseChatModel

from config.settings import settings
from invoice_extraction.config import (
    EXTRACTION_MAX_WORKERS,
    PARSER_KWARGS,
    PROCESSED_EMAILS_DIR,
    RENDER_DPI,
)
from invoice_extraction.invoice_utils.documents import load_document
from invoice_extraction.invoice_utils.page_mode import is_scanned_pdf
from invoice_extraction.invoice_utils.pdf_parser import build_attachment_evidence
from invoice_extraction.models import (
    DocumentClassification,
    InvoiceData,
    ValidationReport,
    document_number_of,
)
from invoice_extraction.nodes import classify_document, extract_document, validate_document
from invoice_extraction.tracing import STAGE_PARSING, set_trace_tags, span
from utils.llm_factory import LLMFactory

# Document types worth extracting on their own. Anything else is an accounting
# document we do not process here (shipping documents, POs, ...).
EXTRACTABLE_TYPES = ("invoice", "billing_document", "credit_note", "debit_note")


@dataclass
class PipelineResult:
    """Outcome of running one document through the pipeline.

    status:
        validated — went through all three stages
        skipped   — gated out at classification (not an invoice, or not an original)
        failed    — a stage raised; `message` carries the error
    """

    filename: str
    status: Literal["validated", "skipped", "failed"]
    classification: DocumentClassification | None = None
    invoice_data: InvoiceData | None = None
    validation: ValidationReport | None = None
    message: str = ""


def _is_original(classification: DocumentClassification) -> bool:
    """A null document_state reads as "original".

    Real documents rarely print the word "Original", so only an explicit copy /
    proforma / cancelled counts as non-original.
    """
    return classification.document_state is None or classification.document_state.value == "original"


def _is_exception_receipt(classification: DocumentClassification) -> bool:
    """A receipt carrying an exception (condominio / insurance / bank extract).

    These are booked in SAP like invoices (cases C1-C3 in `decisions`), so they
    need their amounts read even though the type is not invoice-like.
    """
    return classification.document_type.value == "receipt" and classification.document_exception is not None


def should_extract(classification: DocumentClassification) -> bool:
    """Deterministic gate: invoice-like Originals, plus exception receipts.

    The receipt branch is what feeds cases C1-C3 in `decisions.decide_document`:
    those receipts are ingested, and a document cannot be ingested without its
    fields having been extracted and validated first.
    """
    if _is_exception_receipt(classification):
        return True

    return classification.document_type.value in EXTRACTABLE_TYPES and _is_original(classification)


def _gate_message(classification: DocumentClassification) -> str:
    """The user-facing reason a document was gated out."""
    doc_type = classification.document_type.value

    if doc_type == "receipt":
        return "document is a receipt with no exception"

    if doc_type not in EXTRACTABLE_TYPES:
        return "document not invoice"

    state = classification.document_state.value if classification.document_state is not None else "no state"
    return f"document is invoice, but it is {state}"


class ExtractionPipeline:
    def __init__(self, llm_factory: LLMFactory, llm: BaseChatModel | None = None):
        self.llm_factory = llm_factory
        # One chat model reused across all three stages; each node applies its own
        # structured-output / tool binding on top.
        self.llm = llm or llm_factory.create_chat_model()

    def run(self, pdf_path: Path) -> PipelineResult:
        """Run one already-split document through classification, extraction and validation."""
        pdf_path = Path(pdf_path)
        doc = load_document(pdf_path)

        # Scan's embedded text layer is the scanner's own OCR
        # classification and extraction get page images instead of the PDF
        scanned, coverage = is_scanned_pdf(pdf_path)

        with span(f"extract:{doc.filename}", "CHAIN") as document_span:
            document_span.set_inputs(
                {
                    "filename": doc.filename,
                    "path": str(pdf_path),
                    "input_mode": "image" if scanned else "pdf",
                    "image_coverage": round(coverage, 2),
                    "render_dpi": RENDER_DPI if scanned else None,
                }
            )
            set_trace_tags(input_mode="image" if scanned else "pdf")

            # --- CLASSIFICATION -----------------------------------------------
            # The `2-classification` span (and its summary) is created inside the
            # node itself, so nothing is recorded here.
            classification = classify_document(self.llm, doc, scanned=scanned)

            # --- GATE ---------------------------------------------------------
            if not should_extract(classification):
                message = _gate_message(classification)
                print(message)
                document_span.set_outputs({"status": "skipped", "message": message})
                return PipelineResult(
                    filename=doc.filename,
                    status="skipped",
                    classification=classification,
                    message=message,
                )

            # --- EXTRACTION ---------------------------------------------------
            invoice_data = extract_document(self.llm, doc, classification, scanned=scanned)

            # --- PARSING (deterministic, no LLM) ------------------------------
            # Feeds the validator ground truth to check the extraction against.
            # Non-fatal: a parser failure just means validating without parsed text.
            # Traced separately because autolog cannot see a non-LLM step, and
            # "the validator had no parsed text to check against" is a common
            # root cause of a low-confidence result.
            with span(STAGE_PARSING, "PARSER") as parse_span:
                try:
                    evidence = build_attachment_evidence(pdf_path, scanned=scanned, **PARSER_KWARGS)
                    parsed_text = evidence.get("extracted_text") or None
                except Exception as exc:  # noqa: BLE001 - validation still works without it
                    print(f"⚠️  Could not parse {doc.filename}: {type(exc).__name__}: {exc}")
                    parsed_text = None
                    parse_span.set_outputs({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
                else:
                    parse_span.set_outputs(
                        {
                            "ok": True,
                            "source": evidence.get("source"),
                            "chars": len(parsed_text) if parsed_text else 0,
                            "text": parsed_text,
                        }
                    )

            # --- VALIDATION ---------------------------------------------------
            # The document number comes from classification, not extraction — see
            # `DocumentClassification.document_number`.
            validation = validate_document(
                self.llm,
                invoice_data,
                parsed_text=parsed_text,
                document_number=document_number_of(classification),
                document_exception=(
                    classification.document_exception.value if classification.document_exception else None
                ),
            )

            # The full report lives on the `5-validation` span; this is the
            # document-level roll-up, so it stays short.
            document_span.set_outputs(
                {
                    "status": "validated",
                    "document_type": classification.document_type.value,
                }
            )

            return PipelineResult(
                filename=doc.filename,
                status="validated",
                classification=classification,
                invoice_data=invoice_data,
                validation=validation,
                message="ok",
            )

    def _run_safe(self, pdf_path: Path) -> PipelineResult:
        """`run`, but a raised exception becomes a `failed` result instead of propagating."""
        try:
            return self.run(pdf_path)
        except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
            message = f"{type(exc).__name__}: {exc}"
            print(f"❌ Failed {pdf_path.name}: {message}")
            return PipelineResult(
                filename=pdf_path.name,
                status="failed",
                message=message,
            )

    async def run_batch(self, pdf_paths: list[Path], max_workers: int = EXTRACTION_MAX_WORKERS) -> list[PipelineResult]:
        """Run several documents concurrently, isolating failures so one bad file cannot kill the batch.

        Each document runs on its own thread via `asyncio.to_thread`, bounded by
        `max_workers` — I/O parallelism over blocking LLM calls, not CPU work.
        `to_thread` copies contextvars, so tracing is correct. Order is preserved:
        `asyncio.gather` returns results in argument.
        """
        semaphore = asyncio.Semaphore(max_workers)

        async def one(pdf_path: Path) -> PipelineResult:
            async with semaphore:
                return await asyncio.to_thread(self._run_safe, Path(pdf_path))

        return list(await asyncio.gather(*(one(p) for p in pdf_paths)))


def create_pipeline(
    llm_factory: LLMFactory | None = None,
) -> ExtractionPipeline:
    if llm_factory is None:
        llm_factory = LLMFactory.from_settings(settings)

    return ExtractionPipeline(llm_factory=llm_factory)


async def _main() -> None:
    from invoice_extraction.invoice_utils.reporting import print_pipeline_result

    pipeline = create_pipeline()

    # Phase 1 (ingestion_pipeline) writes one folder per email, each holding the
    # single-document PDFs cut from that email's attachments. The recursive glob is
    # what lets this consume that layout without caring how it is nested.
    pdf_paths = sorted(PROCESSED_EMAILS_DIR.glob("**/*.pdf"))

    print(f"Running {len(pdf_paths)} document(s) from {PROCESSED_EMAILS_DIR}\n")

    for result in await pipeline.run_batch(pdf_paths):
        print_pipeline_result(result)


if __name__ == "__main__":
    asyncio.run(_main())
