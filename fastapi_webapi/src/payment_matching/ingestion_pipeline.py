"""Payment email ingestion: LOAD -> BODY -> SEGMENT -> SPLIT -> PERSIST.

Turns one message into a working folder holding `email_content.json`, the body
rendered to PDF when it carries note-grade information, and one PDF per
candidate payment note cut out of the attachments.

It decides nothing about payments beyond whether the body is worth keeping as a
document; classifying a candidate as a payment note and reading it is
`note_pipeline`'s job.
"""

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from langchain_core.language_models import BaseChatModel

from config.settings import settings
from email_core.email_pdf import render_email_pdf
from email_core.folders import email_folder_name, reserve_folder
from email_core.models import EmailAttachment, EmailContent, LoadedEmail
from email_core.pdf.splitter import (
    count_pages,
    ensure_readable,
    split_pdf,
    validate_segmentation,
)
from payment_matching.config import (
    BODY_PDF_NAME,
    MANIFEST_NAME,
    MIN_BODY_PDF_CHARS,
    PROCESSED_EMAILS_DIR,
)
from payment_matching.models import PaymentEmailInfo
from payment_matching.nodes import extract_payment_email, segment_payment_document
from payment_matching.tracing import STAGE_BODY_PDF, span
from utils.llm_factory import LLMFactory


@dataclass
class AttachmentResult:
    """Outcome of ingesting one attachment.

    status:
        chunked     — split into one or more candidate payment notes
        unsupported — not a PDF, recorded and skipped
        failed      — could not be read; `message` carries the error
    """

    filename: str
    status: Literal["chunked", "unsupported", "failed"]
    total_pages: int = 0
    split_filenames: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class PaymentIngestionResult:
    """Outcome of ingesting one message.

    status:
        ingested — parsed, attachments split, manifest written
        failed   — the message could not be processed; `message` carries the error
    """

    source: str
    status: Literal["ingested", "failed"]
    folder: Path | None = None
    info: PaymentEmailInfo | None = None
    attachments: list[AttachmentResult] = field(default_factory=list)
    body_pdf: str | None = None
    message: str = ""

    @property
    def is_payment_related(self) -> bool:
        return self.info is not None and self.info.is_payment_related.value

    @property
    def note_candidates(self) -> list[str]:
        """The split PDFs to read as payment notes: attachments only.

        `body_pdf` is excluded. The body's facts are already extracted into
        `info`; re-reading a rendering of the same text would cost a second call
        and could only disagree with the first.
        """
        return [name for a in self.attachments for name in a.split_filenames]

    @property
    def problems(self) -> list[str]:
        return [f"{a.filename}: {problem}" for a in self.attachments for problem in a.problems]


def should_render_body(info: PaymentEmailInfo, body: str) -> tuple[bool, str]:
    """Whether the body is worth keeping as evidence, and why not.

    The body is saved only when it can be matched against later: it announces a
    payment AND names the invoices that payment settles. A body announcing a
    payment whose detail lives entirely in an attachment adds nothing to look
    up. The length floor catches a body that passes both but is really a
    forwarded header stub.
    """
    if not info.is_payment_related.value:
        return False, "not payment related"
    if not info.invoice_numbers:
        return False, "no invoice numbers in the body"
    if len(body or "") < MIN_BODY_PDF_CHARS:
        return False, f"body under {MIN_BODY_PDF_CHARS} chars"
    return True, ""


class PaymentIngestionPipeline:
    def __init__(self, llm_factory: LLMFactory, llm: BaseChatModel | None = None):
        self.llm_factory = llm_factory
        self.llm = llm or llm_factory.create_chat_model()

    # -- body --------------------------------------------------------------

    def render_body(self, email: LoadedEmail, info: PaymentEmailInfo, folder: Path) -> str | None:
        """Write the body as a PDF when it carries note-grade information.

        Returns the filename written, or None. Best-effort: a rendering failure
        loses the body document, never the message.
        """
        with span(STAGE_BODY_PDF, "CHAIN") as body_span:
            wanted, reason = should_render_body(info, email.body)
            body_span.set_inputs({"body_chars": len(email.body or "")})

            if not wanted:
                print(f"  📄 Body not kept as a document — {reason}")
                body_span.set_outputs({"rendered": False, "reason": reason})
                return None

            try:
                data = render_email_pdf(
                    sender=email.sender_email,
                    subject=email.subject,
                    body=email.body,
                    received=email.reception_date,
                    message_id=email.message_id,
                )
            except Exception as exc:  # noqa: BLE001 - a failed render must not lose the message
                message = f"{type(exc).__name__}: {exc}"
                print(f"  ⚠️  Could not render the body to PDF: {message}")
                body_span.set_outputs({"rendered": False, "error": message})
                return None

            (folder / BODY_PDF_NAME).write_bytes(data)
            print(f"  📄 Body kept as {BODY_PDF_NAME} ({len(data):,} bytes)")
            body_span.set_outputs({"rendered": True, "bytes": len(data), "filename": BODY_PDF_NAME})
            return BODY_PDF_NAME

    # -- attachments -------------------------------------------------------

    def ingest_attachment(self, attachment: EmailAttachment, folder: Path, index: int = 1) -> AttachmentResult:
        """Split one PDF attachment into candidate payment notes.

        `index` is the attachment's position in the message, prefixed onto every
        name written, so two attachments called `nota.pdf` cannot overwrite each
        other's splits.
        """
        prefix = f"{index:02d}_"

        if not attachment.is_pdf:
            return AttachmentResult(
                filename=attachment.filename,
                status="unsupported",
                message="not a pdf",
            )

        with span(f"ingest:{attachment.filename}", "CHAIN") as attachment_span:
            attachment_span.set_inputs({"filename": attachment.filename, "bytes": len(attachment.data)})

            # Some senders produce PDFs with a broken xref table. Repair those up
            # front so the page count, the model and the splitter see the same bytes.
            pdf_data = ensure_readable(attachment.data)
            repaired = pdf_data is not attachment.data
            if repaired:
                print(f"  🔧 {attachment.filename}: repaired a malformed PDF before splitting")

            total_pages = count_pages(pdf_data)

            segmentation = segment_payment_document(
                self.llm,
                encoded_pdf=base64.b64encode(pdf_data).decode("utf-8"),
                filename=attachment.filename,
                total_pages=total_pages,
            )

            # Never trust the boundaries without checking them against the real
            # page count: a gap loses a document, an overlap duplicates one.
            problems = validate_segmentation(segmentation.documents, total_pages)
            if problems:
                print(f"  ⚠️  {attachment.filename}: segmentation coverage issues")
                for problem in problems:
                    print(f"       - {problem}")

            splits = split_pdf(pdf_data, attachment.filename, segmentation.documents)
            split_filenames = [f"{prefix}{split.filename}" for split in splits]
            for split, filename in zip(splits, split_filenames):
                (folder / filename).write_bytes(split.pdf_bytes)

            attachment_span.set_outputs(
                {
                    "total_pages": total_pages,
                    "repaired": repaired,
                    "split_filenames": split_filenames,
                    "problems": problems,
                }
            )

            message = f"{len(splits)} candidate(s) from {total_pages} page(s)"
            return AttachmentResult(
                filename=attachment.filename,
                status="chunked",
                total_pages=total_pages,
                split_filenames=split_filenames,
                problems=problems,
                message=f"{message} (repaired)" if repaired else message,
            )

    # -- messages ----------------------------------------------------------

    def ingest_email(self, email: LoadedEmail, folder: Path, source: str) -> PaymentIngestionResult:
        """Write one message, its body PDF and its split attachments to `folder`."""
        folder.mkdir(parents=True, exist_ok=True)

        info = extract_payment_email(self.llm, email.subject or "", email.body or "")
        body_pdf = self.render_body(email, info, folder)

        results: list[AttachmentResult] = []
        for index, attachment in enumerate(email.attachments, start=1):
            try:
                result = self.ingest_attachment(attachment, folder, index)
            except Exception as exc:  # noqa: BLE001 - one bad attachment must not lose the message
                message = f"{type(exc).__name__}: {exc}"
                print(f"  ❌ {attachment.filename}: {message}")
                result = AttachmentResult(filename=attachment.filename, status="failed", message=message)
            results.append(result)

        candidates = sum(len(r.split_filenames) for r in results)
        content = EmailContent(
            sender_email=email.sender_email,
            email_subject=email.subject,
            email_content=email.body,
            reception_date=email.reception_date,
            number_annexes=len(email.attachments),
            number_chunked_pdfs=candidates,
            message_id=email.message_id,
            thread_id=email.thread_id,
        )

        # Written last: a crash part-way through leaves this file missing, so the
        # folder is visibly incomplete rather than looking finished.
        (folder / MANIFEST_NAME).write_text(content.model_dump_json(indent=2), encoding="utf-8")

        return PaymentIngestionResult(
            source=source,
            status="ingested",
            folder=folder,
            info=info,
            attachments=results,
            body_pdf=body_pdf,
        )

    def run(
        self,
        email: LoadedEmail,
        output_root: Path = PROCESSED_EMAILS_DIR,
    ) -> PaymentIngestionResult:
        """Ingest one message into `output_root/<reception timestamp>_<subject>/`."""
        output_root = Path(output_root)
        folder = reserve_folder(output_root, email_folder_name(email))
        source = email.message_id or email.subject

        return self.ingest_email(email, folder, source=source)


def create_pipeline(llm_factory: LLMFactory | None = None) -> PaymentIngestionPipeline:
    if llm_factory is None:
        llm_factory = LLMFactory.from_settings(settings)

    return PaymentIngestionPipeline(llm_factory=llm_factory)


def print_summary(results: list[PaymentIngestionResult]) -> None:
    ingested = [r for r in results if r.status == "ingested"]
    failed = [r for r in results if r.status == "failed"]
    payment_related = [r for r in ingested if r.is_payment_related]
    candidates = sum(len(r.note_candidates) for r in results)
    problems = [(r.source, p) for r in results for p in r.problems]

    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    print(f"  messages ingested : {len(ingested)}")
    print(f"  messages failed   : {len(failed)}")
    print(f"  payment related   : {len(payment_related)}")
    print(f"  note candidates   : {candidates}")

    if failed:
        print("\n  Failures:")
        for result in failed:
            print(f"    - {result.source}: {result.message}")

    unsupported = [(r.source, a.filename) for r in results for a in r.attachments if a.status == "unsupported"]
    if unsupported:
        print("\n  Unsupported attachments (recorded, not processed):")
        for source, filename in unsupported:
            print(f"    - {source} / {filename}")

    if problems:
        print("\n  Segmentation coverage problems:")
        for source, problem in problems:
            print(f"    - {source} / {problem}")
