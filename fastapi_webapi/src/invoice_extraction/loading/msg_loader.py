"""Read Outlook `.msg` files into the pipeline's `LoadedEmail` shape.

This is the offline half of Phase 1: the `.msg` files are treated as if a fetch
step had just deposited them. Live inbox fetching lives in `outlook_loader.py`.
"""

import io
import zipfile
from datetime import datetime
from pathlib import Path

import extract_msg

from invoice_extraction.config import (
    MAX_ZIP_FILES,
    MAX_ZIP_MEMBER_BYTES,
    MAX_ZIP_TOTAL_BYTES,
    ZIP_CHUNK_SIZE,
)
from invoice_extraction.models import EmailAttachment, LoadedEmail


def _is_inline_image(attachment) -> bool:
    """True for signature logos and other embedded body imagery.

    Outlook flags these `hidden`; they are inline decoration referenced by the HTML
    body, not documents the sender meant to attach. Across the sample set every
    hidden attachment was a jpg/png/gif logo and no PDF was ever hidden, so this
    keeps `number_annexes` meaningful rather than dominated by signature clutter.
    """
    return bool(getattr(attachment, "hidden", False))


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, budget: int) -> bytes:
    """Decompress one zip member, aborting if it outgrows its budget.

    Streams rather than calling `archive.read()`, and counts the bytes actually
    produced. A zip bomb declares a small `file_size` and expands to gigabytes, so
    the archive's own metadata cannot be the thing we check — only the running
    total of decompressed bytes is trustworthy.

    Raises ValueError once the member exceeds `budget`, before the oversized data
    is ever fully materialised.
    """
    limit = min(MAX_ZIP_MEMBER_BYTES, budget)
    chunks: list[bytes] = []
    size = 0

    with archive.open(info) as member:
        while chunk := member.read(ZIP_CHUNK_SIZE):
            size += len(chunk)
            if size > limit:
                raise ValueError(f"member exceeds {limit:,} bytes when decompressed")
            chunks.append(chunk)

    return b"".join(chunks)


def _expand_zip(filename: str, data: bytes) -> list[EmailAttachment]:
    """Expand a zip attachment into its member files.

    Zips are how bulk billing arrives — one member per invoice — so leaving them
    packed would silently drop every document inside.

    Member names are flattened to a basename, which defuses path traversal
    (`../../evil.pdf`) since callers write these straight to disk. Nested archives
    are deliberately not expanded recursively: that is the other half of zip-bomb
    protection, and a zip inside a zip is not a shape real invoices arrive in.
    """
    attachments: list[EmailAttachment] = []
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        # Not a readable archive — keep the original bytes rather than losing them.
        return [EmailAttachment(filename=filename, data=data)]

    total = 0
    with archive:
        for index, info in enumerate(archive.infolist()):
            if index >= MAX_ZIP_FILES:
                print(f"⚠️  {filename}: more than {MAX_ZIP_FILES} members, remainder skipped")
                break

            if info.is_dir():
                continue

            member_name = Path(info.filename).name
            if not member_name:
                continue

            try:
                member_data = _read_member(archive, info, budget=MAX_ZIP_TOTAL_BYTES - total)
            except (ValueError, zipfile.BadZipFile, OSError) as exc:
                print(f"⚠️  {filename}: skipping {member_name}: {exc}")
                continue

            total += len(member_data)
            attachments.append(EmailAttachment(filename=member_name, data=member_data))

            if total >= MAX_ZIP_TOTAL_BYTES:
                print(f"⚠️  {filename}: unpacked size limit reached, remainder skipped")
                break

    return attachments


def _collect_attachments(message) -> list[EmailAttachment]:
    """Real annexes only, with zips expanded in place.

    Attachments with no filename are dropped alongside the inline imagery: without
    a name there is no reliable way to tell a document from body decoration, and in
    the sample set they were all photos rather than accounting documents.
    """
    attachments: list[EmailAttachment] = []

    for raw in message.attachments:
        if _is_inline_image(raw):
            continue

        data = raw.data
        if not isinstance(data, bytes) or not data:
            # Embedded messages and other non-binary parts expose no usable bytes.
            continue

        filename = (raw.longFilename or raw.shortFilename or "").strip()
        if not filename or not Path(filename).suffix:
            continue

        if filename.lower().endswith(".zip"):
            attachments.extend(_expand_zip(filename, data))
        else:
            attachments.append(EmailAttachment(filename=filename, data=data))

    return attachments


def load_msg(msg_path: Path) -> LoadedEmail:
    """Parse one `.msg` file into a `LoadedEmail`.

    Inline signature images and unnamed attachments are dropped, zip attachments
    are expanded in place, and the reception date is normalised to ISO-8601.
    """
    msg_path = Path(msg_path)
    message = extract_msg.Message(str(msg_path))

    try:
        date = message.date
        reception_date = date.isoformat() if isinstance(date, datetime) else str(date or "")

        return LoadedEmail(
            sender_email=(message.sender or "").strip(),
            subject=(message.subject or "").strip(),
            body=message.body or "",
            reception_date=reception_date,
            attachments=_collect_attachments(message),
        )
    finally:
        message.close()
