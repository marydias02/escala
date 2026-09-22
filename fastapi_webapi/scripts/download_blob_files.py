"""Download blobs from the invoice container by their key (fct_documents.file_path).

Keys are the container-relative paths the pipeline writes, e.g.
`processed_emails/<YYYY>/<MM>/<email folder>/<file>`. Files land under the output
directory mirroring the key's folder structure.

    python scripts/download_blob_files.py                      # the KEYS below
    python scripts/download_blob_files.py <key> [<key> ...]    # explicit keys
    python scripts/download_blob_files.py --prefix processed_emails/2026/09/<folder>
    python scripts/download_blob_files.py --out C:/tmp/blobs <key>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from azure.core.exceptions import ResourceNotFoundError  # noqa: E402
from loguru import logger  # noqa: E402

from utils.blob_storage import download_document_bytes, get_container_client  # noqa: E402

# Default keys, used when none are passed on the command line.
KEYS = [
    "processed_emails/2026/09/20260915-145715_Fatura n 48000001188_LOGISLINK/01_Fatura n 48000001188_LOGISLINK_001.pdf",
    "processed_emails/2026/09/20260915-145715_Fatura n 48000001188_LOGISLINK/01_Fatura n 48000001188_LOGISLINK_002.pdf",
    "processed_emails/2026/09/20260915-145715_Fatura n 48000001188_LOGISLINK/01_Fatura n 48000001188_LOGISLINK_003.pdf",
    "processed_emails/2026/09/20260915-145715_Fatura n 48000001188_LOGISLINK/01_Fatura n 48000001188_LOGISLINK_004.pdf",
]

DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "downloads"


def list_keys(prefix: str) -> list[str]:
    """Every blob key under `prefix` — lets you pull a whole email folder."""
    return [blob.name for blob in get_container_client().list_blobs(name_starts_with=prefix)]


def download(key: str, out_dir: Path) -> Path | None:
    """Write one blob under `out_dir`, mirroring its key path. None if absent."""
    target = out_dir / key
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = download_document_bytes(key)
    except ResourceNotFoundError:
        logger.error(f"Not found: {key}")
        return None
    target.write_bytes(data)
    logger.info(f"{key} -> {target} ({len(data):,} bytes)")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keys", nargs="*", help="blob keys to download (default: the KEYS in this script)")
    parser.add_argument("--prefix", help="download every blob under this prefix instead")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="output directory")
    args = parser.parse_args()

    if args.prefix:
        keys = list_keys(args.prefix)
        if not keys:
            logger.error(f"No blobs under prefix: {args.prefix}")
            return 1
    else:
        keys = args.keys or KEYS

    failures = sum(download(key, args.out) is None for key in keys)
    logger.info(f"Downloaded {len(keys) - failures}/{len(keys)} file(s) to {args.out}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
