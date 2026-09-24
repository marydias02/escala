"""Naming and reserving one email's working folder.

The folder is scratch space between "bytes arrived from Graph" and "artifacts
are in blob storage": a pipeline writes its PDFs and manifest here, uploads the
folder, then deletes it. Blob storage is the durable copy.

Moved from `invoice_extraction.ingestion_pipeline`, unchanged.
"""

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from email_core.models import LoadedEmail

# Characters Windows forbids in a path component.
INVALID_PATH_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

# Windows caps a full path at 260 characters by default. Email subjects in the
# sample set reach 111 characters, so folder names are truncated well short of it.
MAX_FOLDER_NAME = 80


def parse_reception_date(value: str | None) -> datetime | None:
    """Parse an ISO-8601 reception date to a datetime, or None.

    A malformed/empty string becomes None rather than failing a later insert.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def sanitize_folder_name(name: str, fallback: str = "email", limit: int = MAX_FOLDER_NAME) -> str:
    """Turn an email subject into a safe, bounded directory name.

    Subjects carry accents, doubled spaces and characters Windows rejects outright.
    Normalising here (rather than at write time) keeps the folder name predictable.
    """
    name = unicodedata.normalize("NFC", name)
    name = re.sub(INVALID_PATH_CHARS, "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    # Windows silently drops trailing dots and spaces from directory names, which
    # would make the folder we create and the folder we later look for differ.
    name = name.rstrip(". ")

    if len(name) > limit:
        name = name[:limit].rstrip(". ")

    return name or fallback


def email_folder_name(email: LoadedEmail, limit: int = MAX_FOLDER_NAME) -> str:
    """`YYYYMMDD-HHMMSS_subject` for one email, bounded by `limit`.

    The timestamp comes from the email's own reception date, not from now(), so
    reprocessing one email always produces the same name. It sorts the output
    directory chronologically and distinguishes same-subject emails by something
    readable, leaving `reserve_folder`'s `_2` suffix for the genuine collision
    of one subject received in one second.
    """
    received = parse_reception_date(email.reception_date)
    if received is None:
        return sanitize_folder_name(email.subject, limit=limit)

    prefix = received.strftime("%Y%m%d-%H%M%S")
    # Budget the prefix out of the cap rather than adding it on top.
    subject = sanitize_folder_name(email.subject, limit=limit - len(prefix) - 1)
    return f"{prefix}_{subject}"


def reserve_folder(root: Path, name: str) -> Path:
    """`root/name`, suffixed `_2`, `_3`... if taken. Creates the folder to reserve it.

    `mkdir(exist_ok=False)` is one atomic syscall: it either creates the
    directory or raises `FileExistsError`. Testing `.exists()` first would leave
    a window in which two concurrent emails both see the name free and then
    share a folder — overwriting each other's manifest, and with it the
    `message_id` that outbound replies are addressed to.
    """
    for suffix in range(1, 1000):
        candidate = root / (name if suffix == 1 else f"{name}_{suffix}")
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue

    raise RuntimeError(f"Could not find a free folder name for {name!r} under {root}")
