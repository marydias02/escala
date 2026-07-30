"""Email ingestion pipeline: LOAD -> SEGMENT -> SPLIT -> PERSIST.

Phase 1 of invoice processing. It turns raw emails into the input the extraction
pipeline expects: a folder per email holding `email_content.json` plus one PDF per
accounting document.

It classifies nothing and extracts nothing. The only judgement call it makes is
where one document ends and the next begins — and even that is checked
deterministically before the result is trusted.
"""

import base64
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from langchain_core.language_models import BaseChatModel

from config.settings import settings
from invoice_extraction.config import (
    FORCE_REINGEST,
    INGEST_LIMIT,
    MANIFEST_NAME,
    MAX_FOLDER_NAME,
    ORIGINAL_EMAILS_DIR,
    PROCESSED_EMAILS_DIR,
)
from invoice_extraction.invoice_utils.pdf_splitter import (
    count_pages,
    ensure_readable,
    split_pdf,
    validate_segmentation,
)
from invoice_extraction.loading import load_msg
from invoice_extraction.models import EmailAttachment, EmailContent, LoadedEmail
from invoice_extraction.nodes import segment_document
from invoice_extraction.tracing import span
from utils.llm_factory import LLMFactory

# Characters Windows forbids in a path component.
INVALID_PATH_CHARS = r'[<>:"/\\|?*\x00-\x1f]'


@dataclass
class AttachmentResult:
    """Outcome of ingesting one attachment."""

    filename: str
    status: Literal["chunked", "stored", "failed"]
    total_pages: int = 0
    split_filenames: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class EmailIngestionResult:
    """Outcome of ingesting one email.

    status:
        ingested — parsed, attachments split, manifest written
        skipped  — already processed (manifest present) and re-ingest not forced
        failed   — the email could not be processed; `message` carries the error
    """

    source: str
    status: Literal["ingested", "skipped", "failed"]
    folder: Optional[Path] = None
    attachments: list[AttachmentResult] = field(default_factory=list)
    message: str = ""

    @property
    def number_chunked_pdfs(self) -> int:
        return sum(len(a.split_filenames) for a in self.attachments)

    @property
    def problems(self) -> list[str]:
        """Segmentation coverage problems across every attachment."""
        return [f"{a.filename}: {problem}" for a in self.attachments for problem in a.problems]


def sanitize_folder_name(name: str, fallback: str = "email") -> str:
    """Turn an email subject into a safe, bounded directory name.

    Subjects carry accents, doubled spaces and characters Windows rejects outright.
    Normalising here (rather than at write time) keeps the folder name predictable,
    which matters because its presence is what makes re-runs idempotent.
    """
    name = unicodedata.normalize("NFC", name)
    name = re.sub(INVALID_PATH_CHARS, "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    # Windows silently drops trailing dots and spaces from directory names, which
    # would make the folder we create and the folder we later look for differ.
    name = name.rstrip(". ")

    if len(name) > MAX_FOLDER_NAME:
        name = name[:MAX_FOLDER_NAME].rstrip(". ")

    return name or fallback


def _unique_folder(root: Path, name: str) -> Path:
    """`root/name`, suffixed `_2`, `_3`... if that name is already taken."""
    candidate = root / name
    if not candidate.exists():
        return candidate

    for suffix in range(2, 1000):
        candidate = root / f"{name}_{suffix}"
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Could not find a free folder name for {name!r} under {root}")


class IngestionPipeline:
    def __init__(self, llm_factory: LLMFactory, llm: Optional[BaseChatModel] = None):
        self.llm_factory = llm_factory
        self.llm = llm or llm_factory.create_chat_model()

    # -- attachments -------------------------------------------------------

    def ingest_attachment(self, attachment: EmailAttachment, folder: Path) -> AttachmentResult:
        """Split one attachment into single-document PDFs, or store it as-is.

        Non-PDFs are written untouched: they are counted as annexes but nothing
        here can meaningfully segment them.
        """
        if not attachment.is_pdf:
            (folder / attachment.filename).write_bytes(attachment.data)
            return AttachmentResult(filename=attachment.filename, status="stored", message="not a pdf")

        with span(f"ingest:{attachment.filename}", "CHAIN") as attachment_span:
            attachment_span.set_inputs(
                {"filename": attachment.filename, "bytes": len(attachment.data)}
            )

            # Some senders produce PDFs with a broken xref table. Repair those up front
            # so the page count, the model and the splitter all see the same valid bytes.
            pdf_data = ensure_readable(attachment.data)
            repaired = pdf_data is not attachment.data
            if repaired:
                print(f"  🔧 {attachment.filename}: repaired a malformed PDF before splitting")

            # The page count is deterministic and authoritative — the model is never
            # asked for it, because VLMs cannot count pages reliably.
            total_pages = count_pages(pdf_data)

            encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")
            segmentation = segment_document(
                self.llm,
                encoded_pdf=encoded_pdf,
                filename=attachment.filename,
                total_pages=total_pages,
            )

            # Never trust the boundaries without checking them against the real page
            # count: a gap loses a document, an overlap duplicates one.
            problems = validate_segmentation(segmentation.documents, total_pages)
            if problems:
                print(f"  ⚠️  {attachment.filename}: segmentation coverage issues")
                for problem in problems:
                    print(f"       - {problem}")

            splits = split_pdf(pdf_data, attachment.filename, segmentation.documents)
            for split in splits:
                (folder / split.filename).write_bytes(split.pdf_bytes)

            # The boundaries the model chose, next to the problems they caused —
            # the pair you need when a document comes out cut in the wrong place.
            attachment_span.set_outputs(
                {
                    "total_pages": total_pages,
                    "repaired": repaired,
                    "documents": [
                        {
                            "start_page": boundary.start_page,
                            "end_page": boundary.end_page,
                            "confidence": boundary.confidence,
                        }
                        for boundary in segmentation.documents
                    ],
                    "split_filenames": [s.filename for s in splits],
                    "problems": problems,
                }
            )

            message = f"{len(splits)} document(s) from {total_pages} page(s)"
            return AttachmentResult(
                filename=attachment.filename,
                status="chunked",
                total_pages=total_pages,
                split_filenames=[s.filename for s in splits],
                problems=problems,
                message=f"{message} (repaired)" if repaired else message,
            )

    # -- emails ------------------------------------------------------------

    def ingest_email(self, email: LoadedEmail, folder: Path, source: str) -> EmailIngestionResult:
        """Write one already-parsed email and its split attachments to `folder`."""
        folder.mkdir(parents=True, exist_ok=True)

        results: list[AttachmentResult] = []
        for attachment in email.attachments:
            try:
                results.append(self.ingest_attachment(attachment, folder))
            except Exception as exc:  # noqa: BLE001 - one bad attachment must not lose the email
                message = f"{type(exc).__name__}: {exc}"
                print(f"  ❌ {attachment.filename}: {message}")
                results.append(AttachmentResult(filename=attachment.filename, status="failed", message=message))

        result = EmailIngestionResult(source=source, status="ingested", folder=folder, attachments=results)

        content = EmailContent(
            sender_email=email.sender_email,
            email_subject=email.subject,
            email_content=email.body,
            reception_date=email.reception_date,
            number_annexes=len(email.attachments),
            number_chunked_pdfs=result.number_chunked_pdfs,
        )

        # Written last, on purpose: this file is the "done" marker that `run` checks,
        # so a crash part-way through leaves the email unmarked and it retries cleanly.
        (folder / MANIFEST_NAME).write_text(content.model_dump_json(indent=2), encoding="utf-8")

        return result

    def run(
        self,
        msg_path: Path,
        output_root: Path = PROCESSED_EMAILS_DIR,
        force: bool = FORCE_REINGEST,
    ) -> EmailIngestionResult:
        """Ingest one `.msg` file into `output_root/<sanitised subject>/`."""
        msg_path = Path(msg_path)
        output_root = Path(output_root)

        # Resolve the target folder from the filename before parsing, so the skip
        # check costs nothing when the email was already processed.
        folder_name = sanitize_folder_name(msg_path.stem)
        existing = output_root / folder_name

        if not force and (existing / MANIFEST_NAME).exists():
            return EmailIngestionResult(
                source=msg_path.name,
                status="skipped",
                folder=existing,
                message="already ingested",
            )

        email = load_msg(msg_path)
        folder = existing if existing.exists() else _unique_folder(output_root, folder_name)

        return self.ingest_email(email, folder, source=msg_path.name)

    def run_batch(
        self,
        msg_paths: list[Path],
        output_root: Path = PROCESSED_EMAILS_DIR,
        force: bool = FORCE_REINGEST,
    ) -> list[EmailIngestionResult]:
        """Ingest several emails, isolating failures so one bad file cannot kill the batch."""
        results: list[EmailIngestionResult] = []

        for msg_path in msg_paths:
            msg_path = Path(msg_path)
            print(f"\n📧 {msg_path.name}")
            try:
                result = self.run(msg_path, output_root, force=force)
            except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
                message = f"{type(exc).__name__}: {exc}"
                print(f"  ❌ Failed: {message}")
                results.append(EmailIngestionResult(source=msg_path.name, status="failed", message=message))
                continue

            if result.status == "skipped":
                print("  ⏭️  already ingested")
            else:
                for attachment in result.attachments:
                    print(f"  • {attachment.filename} — {attachment.message}")

            results.append(result)

        return results


def create_pipeline(llm_factory: Optional[LLMFactory] = None) -> IngestionPipeline:
    if llm_factory is None:
        llm_factory = LLMFactory.from_settings(settings)

    return IngestionPipeline(llm_factory=llm_factory)


def print_summary(results: list[EmailIngestionResult]) -> None:
    ingested = [r for r in results if r.status == "ingested"]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]
    chunked = sum(r.number_chunked_pdfs for r in results)
    problems = [(r.source, p) for r in results for p in r.problems]

    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    print(f"  emails ingested : {len(ingested)}")
    print(f"  emails skipped  : {len(skipped)}")
    print(f"  emails failed   : {len(failed)}")
    print(f"  PDFs produced   : {chunked}")

    if failed:
        print("\n  Failures:")
        for result in failed:
            print(f"    - {result.source}: {result.message}")

    if problems:
        print("\n  Segmentation coverage problems:")
        for source, problem in problems:
            print(f"    - {source} / {problem}")
    else:
        print("\n  ✅ No segmentation coverage problems.")


def main() -> None:
    msg_paths = sorted(ORIGINAL_EMAILS_DIR.glob("*.msg"))
    if INGEST_LIMIT is not None:
        msg_paths = msg_paths[:INGEST_LIMIT]

    print(f"Ingesting {len(msg_paths)} email(s) from {ORIGINAL_EMAILS_DIR}")
    print(f"Output root: {PROCESSED_EMAILS_DIR}")

    pipeline = create_pipeline()
    results = pipeline.run_batch(msg_paths, PROCESSED_EMAILS_DIR, force=FORCE_REINGEST)
    print_summary(results)


if __name__ == "__main__":
    main()
