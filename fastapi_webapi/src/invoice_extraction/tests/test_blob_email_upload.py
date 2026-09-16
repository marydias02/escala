"""Round-trips one fake email folder through utils.blob_storage, then cleans up."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from utils.blob_storage import (
    build_email_prefix,
    download_document_bytes,
    get_container_client,
    upload_email_folder,
)

if __name__ == "__main__":
    logger.info("🎯 Testing email folder upload to Azure Blob Storage")

    reception_date = datetime(2026, 3, 14, 9, 30, tzinfo=timezone.utc)
    pdf_bytes = b"%PDF-1.4\n% fake pdf for test_blob_email_upload\n"
    manifest_bytes = b'{"email_subject": "test_blob_email_upload"}'

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "TEST_ blob email upload"
        folder.mkdir()
        (folder / "email_content.json").write_bytes(manifest_bytes)
        (folder / "doc_1.pdf").write_bytes(pdf_bytes)

        prefix = build_email_prefix(reception_date, folder.name)
        logger.info(f"Built prefix '{prefix}'")
        assert prefix.startswith("processed_emails/2026/03/"), f"Unexpected partition in {prefix!r}"

        keys = upload_email_folder(folder, prefix)
        logger.info(f"Uploaded {len(keys)} file(s): {keys}")
        assert len(keys) == 2, f"Expected 2 uploaded files, got {keys}"

    pdf_key = f"{prefix}/doc_1.pdf"
    logger.info(f"Downloading '{pdf_key}' to verify the round trip")
    downloaded = download_document_bytes(pdf_key)
    assert downloaded == pdf_bytes, "Downloaded PDF does not match what was uploaded"
    logger.info("Downloaded bytes match the uploaded PDF")

    container = get_container_client()
    for key in keys:
        logger.info(f"Deleting blob '{key}'")
        container.delete_blob(key)

    logger.info("Email folder upload test completed successfully")
