"""Zip expansion shared by every attachment loader.

Attachments are untrusted input regardless of source or use case, so this lives
apart from any one loader. Moved verbatim from
`invoice_extraction.invoice_utils.attachments`; the limits now come from
`email_core.config` rather than the invoice config.
"""

import io
import zipfile
from pathlib import Path

from email_core.config import (
    MAX_ZIP_FILES,
    MAX_ZIP_MEMBER_BYTES,
    MAX_ZIP_TOTAL_BYTES,
    ZIP_CHUNK_SIZE,
)
from email_core.models import EmailAttachment


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


def expand_zip(filename: str, data: bytes) -> list[EmailAttachment]:
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
