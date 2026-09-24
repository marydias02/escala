"""Payment note extraction: DETECT -> EXTRACT.

Runs on one already-split PDF at a time — an attachment candidate produced by
`ingestion_pipeline`, never the body PDF. Detects whether the PDF is a scan and
hands it to the model as page images or as the PDF itself, then reads the note's
header and the documents it settles.

No OCR and no deterministic checks: the model sees the document directly, and
whether its lines sum to its own total is recorded rather than judged.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from langchain_core.language_models import BaseChatModel

from config.settings import settings
from email_core.documents import load_document
from email_core.pdf.page_mode import is_scanned_pdf
from payment_matching.config import NOTE_MAX_WORKERS
from payment_matching.models import PaymentNoteDocument
from payment_matching.nodes import extract_payment_note
from payment_matching.tracing import span
from utils.llm_factory import LLMFactory


@dataclass
class NoteResult:
    """Outcome of reading one candidate PDF.

    status:
        extracted — classified a payment note and read
        skipped   — classified as something other than a payment note
        failed    — a stage raised; `message` carries the error
    """

    filename: str
    status: Literal["extracted", "skipped", "failed"]
    note: PaymentNoteDocument | None = None
    scanned: bool = False
    message: str = ""

    @property
    def line_count(self) -> int:
        return len(self.note.lines) if self.note else 0


class NotePipeline:
    def __init__(self, llm_factory: LLMFactory, llm: BaseChatModel | None = None):
        self.llm_factory = llm_factory
        self.llm = llm or llm_factory.create_chat_model()

    def run(self, pdf_path: Path) -> NoteResult:
        """Read one candidate PDF as a payment note."""
        pdf_path = Path(pdf_path)
        doc = load_document(pdf_path)

        # A scan's embedded text layer is the scanner's own OCR, so the model
        # gets page images instead of the PDF.
        scanned, coverage = is_scanned_pdf(pdf_path)

        with span(f"note:{doc.filename}", "CHAIN") as note_span:
            note_span.set_inputs(
                {
                    "filename": doc.filename,
                    "input_mode": "image" if scanned else "pdf",
                    "image_coverage": round(coverage, 2),
                }
            )

            note = extract_payment_note(self.llm, doc, scanned=scanned)

            if not note.is_payment_note.value:
                message = "not a payment note"
                note_span.set_outputs({"status": "skipped", "message": message})
                return NoteResult(
                    filename=doc.filename,
                    status="skipped",
                    note=note,
                    scanned=scanned,
                    message=message,
                )

            note_span.set_outputs({"status": "extracted", "lines": len(note.lines)})
            return NoteResult(
                filename=doc.filename,
                status="extracted",
                note=note,
                scanned=scanned,
                message=f"{len(note.lines)} document(s) settled",
            )

    def _run_safe(self, pdf_path: Path) -> NoteResult:
        """`run`, but a raised exception becomes a `failed` result."""
        try:
            return self.run(pdf_path)
        except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
            message = f"{type(exc).__name__}: {exc}"
            print(f"  ❌ Failed {Path(pdf_path).name}: {message}")
            return NoteResult(filename=Path(pdf_path).name, status="failed", message=message)

    async def run_batch(
        self, pdf_paths: list[Path], max_workers: int = NOTE_MAX_WORKERS
    ) -> list[NoteResult]:
        """Read several candidates concurrently, isolating failures.

        Each document runs on its own thread via `asyncio.to_thread`, bounded by
        `max_workers` — I/O parallelism over blocking LLM calls. `to_thread`
        copies contextvars, so tracing is correct, and `gather` preserves order.
        """
        semaphore = asyncio.Semaphore(max_workers)

        async def one(pdf_path: Path) -> NoteResult:
            async with semaphore:
                return await asyncio.to_thread(self._run_safe, Path(pdf_path))

        return list(await asyncio.gather(*(one(p) for p in pdf_paths)))


def create_pipeline(llm_factory: LLMFactory | None = None) -> NotePipeline:
    if llm_factory is None:
        llm_factory = LLMFactory.from_settings(settings)

    return NotePipeline(llm_factory=llm_factory)


def print_note_result(result: NoteResult) -> None:
    """One candidate's outcome, with its header fields and settled documents."""
    marker = {"extracted": "✅", "skipped": "⏭️ ", "failed": "❌"}.get(result.status, "  ")
    mode = "image" if result.scanned else "pdf"
    print(f"\n{marker} {result.filename} [{mode}] — {result.message}")

    note = result.note
    if note is None or result.status != "extracted":
        return

    def value(confident):
        return confident.value if confident is not None else None

    print(f"     code     : {value(note.payment_note_code)}")
    print(f"     client   : {value(note.client_name)}  vat={value(note.client_vat)}")
    print(f"     bu       : {value(note.bu_name)}  vat={value(note.bu_vat)}")
    print(f"     total    : {value(note.total_payment_note)} {value(note.currency) or ''}")
    print(f"     date     : {value(note.payment_date)}")
    for line in note.lines:
        print(f"       · {value(line.document_number)}  {value(line.value_paid)}")
