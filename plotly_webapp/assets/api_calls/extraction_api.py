from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Lock, local
from time import monotonic

import requests
from requests.adapters import HTTPAdapter

BASE_URL = "http://localhost:8000"

HEADERS = {"X-API-KEY": "4TOaTIKu64Dea4Kj0YmEH3bOF3K1ip9005NmXweWyes"}

_REQUEST_TIMEOUT = 10
_DASHBOARD_CACHE_TTL_SECONDS = 20
_thread_local = local()
_dashboard_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="extraction-api")
_dashboard_cache_lock = Lock()
_dashboard_cache: dict | None = None
_dashboard_cache_expires_at = 0.0


def _get_session() -> requests.Session:
    """Return one connection-pooled session per calling thread."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)
        adapter = HTTPAdapter(pool_connections=8, pool_maxsize=8)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _thread_local.session = session
    return session


def _request(method: str, path: str, **kwargs) -> requests.Response:
    response = _get_session().request(
        method,
        f"{BASE_URL}{path}",
        timeout=_REQUEST_TIMEOUT,
        **kwargs,
    )
    response.raise_for_status()
    return response


def get_big_numbers():
    return _request("GET", "/extraction/big-numbers").json()


def get_priority_documents():
    rows = _request("GET", "/extraction/priority-documents").json()

    for row in rows:
        created_at = row.get("created_at")
        if created_at:
            row["created_at"] = created_at[:16].replace("T", " ")

    return rows


def get_all_documents():
    rows = _request("GET", "/extraction/documents").json()

    for row in rows:
        created_at = row.get("created_at")
        if created_at:
            row["created_at"] = created_at[:16].replace("T", " ")

    return rows


def get_pending_documents():
    rows = _request("GET", "/extraction/pending-documents").json()

    for row in rows:
        created_at = row.get("created_at")
        if created_at:
            row["created_at"] = created_at[:16].replace("T", " ")

    return rows


def get_document_details(doc_id: str):
    return _request("GET", f"/extraction/documents/{doc_id}").json()


def get_document_email(doc_id: str):
    data = _request("GET", f"/extraction/documents/{doc_id}/email").json()
    reception_date = data.get("reception_date")
    if reception_date:
        data["reception_date"] = reception_date[:16].replace("T", " ")

    return data


def alter_document_details(
    document_id: str,
    alerts_list: list[str],
    document_content: dict,
    action: str | None = None,
    status: str | None = None,
    last_modified_by: str | None = None,
):
    payload = {
        "document_id": document_id,
        "alerts_list": alerts_list,
        "document_content": document_content,
    }
    if action is not None:
        payload["action"] = action
    if status is not None:
        payload["status"] = status
    if last_modified_by is not None:
        payload["last_modified_by"] = last_modified_by

    response = _request(
        "PATCH",
        "/extraction",
        json=payload,
    )
    invalidate_dashboard_cache()
    return response.json()


def get_next_priority_document(document_id: str):
    return _request("GET", f"/extraction/next-priority-document/{document_id}").json()


def invalidate_dashboard_cache() -> None:
    """Discard cached dashboard data after a document-changing action."""
    global _dashboard_cache, _dashboard_cache_expires_at

    with _dashboard_cache_lock:
        _dashboard_cache = None
        _dashboard_cache_expires_at = 0.0


def get_extraction_dashboard(*, force_refresh: bool = False) -> dict:
    """Fetch independent dashboard resources concurrently and cache them briefly."""
    global _dashboard_cache, _dashboard_cache_expires_at

    with _dashboard_cache_lock:
        now = monotonic()
        if not force_refresh and _dashboard_cache is not None and now < _dashboard_cache_expires_at:
            return deepcopy(_dashboard_cache)

        futures = {
            "kpis": _dashboard_executor.submit(get_big_numbers),
            "priority_documents": _dashboard_executor.submit(get_priority_documents),
            "all_documents": _dashboard_executor.submit(get_all_documents),
            "pending_documents": _dashboard_executor.submit(get_pending_documents),
        }
        dashboard = {name: future.result() for name, future in futures.items()}

        _dashboard_cache = dashboard
        _dashboard_cache_expires_at = monotonic() + _DASHBOARD_CACHE_TTL_SECONDS
        return deepcopy(dashboard)
