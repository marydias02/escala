"""Azure Blob Storage access for processed email artifacts.

The pipeline uploads one folder per email (`email_content.json` plus one PDF per
document) and stores the relative key in `fct_documents.file_path`; the API reads
the PDF back by that key. Keys are partitioned by reception year/month:

    processed_emails/<YYYY>/<MM>/<email folder>/<filename>

The container is not part of the key — it comes from settings — so the same path
resolves in any environment.

All functions are synchronous; async callers wrap them in `asyncio.to_thread`.
One sync client serves both the pipeline and the API. Moving the read path to an
`azure.storage.blob.aio` client would change only `download_document_bytes`.
"""

from datetime import datetime, timezone
from pathlib import Path

from azure.identity import AzureCliCredential, ClientSecretCredential
from azure.storage.blob import ContainerClient

from config.settings import settings

PROCESSED_EMAILS_PREFIX = "processed_emails"

_container_client: ContainerClient | None = None


def _get_credential():
    """The Azure credential for blob access: app registration, or `az login` locally."""
    if settings.AZURE_FLG_USE_APP_REGISTRATION:
        missing = [
            name
            for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
            if not getattr(settings, name)
        ]
        if missing:
            raise ValueError(f"Missing blob storage credentials in settings: {', '.join(missing)}")
        return ClientSecretCredential(
            settings.AZURE_TENANT_ID,
            settings.AZURE_CLIENT_ID,
            settings.AZURE_CLIENT_SECRET,
        )
    return AzureCliCredential()


def get_container_client() -> ContainerClient:
    """The invoice document container, cached — the client holds a connection and token pool."""
    global _container_client
    if _container_client is None:
        missing = [name for name in ("BLOB_STORAGE_ENDPOINT", "BLOB_CONTAINER_NAME") if not getattr(settings, name)]
        if missing:
            raise ValueError(f"Missing blob storage settings: {', '.join(missing)}")
        _container_client = ContainerClient(
            account_url=settings.BLOB_STORAGE_ENDPOINT,
            container_name=settings.BLOB_CONTAINER_NAME,
            credential=_get_credential(),
        )
    return _container_client


def build_email_prefix(reception_date: datetime | None, folder_name: str) -> str:
    """The blob prefix for one email folder, partitioned by reception year/month.

    Reception date, not upload date, so a late-processed email files under the
    period it belongs to. No usable date falls back to today.
    """
    stamp = reception_date or datetime.now(timezone.utc)
    return f"{PROCESSED_EMAILS_PREFIX}/{stamp:%Y}/{stamp:%m}/{folder_name}"


def upload_email_folder(folder: Path, prefix: str) -> list[str]:
    """Upload every file in one email folder under `prefix`, returning the keys written.

    Called before the pipeline's DB writes, so raising here means no row can
    reference a missing blob. Overwrites, so re-running an email replaces it.
    """
    container = get_container_client()
    keys = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        key = f"{prefix}/{path.name}"
        with path.open("rb") as handle:
            container.upload_blob(name=key, data=handle, overwrite=True)
        keys.append(key)
    return keys


def download_document_bytes(key: str) -> bytes:
    """One blob's bytes, by the key stored in `fct_documents.file_path`.

    Raises `ResourceNotFoundError` if absent; callers translate it.
    """
    return get_container_client().download_blob(key).readall()
