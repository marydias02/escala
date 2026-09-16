from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Lock, local
from time import monotonic

import requests
from requests.adapters import HTTPAdapter

from config import BACKEND_BASE_URL

_REQUEST_TIMEOUT = 10
_DASHBOARD_CACHE_TTL_SECONDS = 20
_thread_local = local()
_dashboard_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="validation-api")
_dashboard_cache_lock = Lock()
_dashboard_cache: dict | None = None
_dashboard_cache_expires_at = 0.0


def _get_session() -> requests.Session:
    """Return one connection-pooled session per calling thread."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=8, pool_maxsize=8)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _thread_local.session = session
    return session


def _request(method: str, path: str, token: str, **kwargs) -> requests.Response:
    response = _get_session().request(
        method,
        f"{BACKEND_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=_REQUEST_TIMEOUT,
        **kwargs,
    )
    response.raise_for_status()
    return response


def get_big_numbers(token: str) -> dict:
    return _request("GET", "/validation/big-numbers", token).json()


def get_sap_processes(token: str):
    return _request("GET", "/validation/documents", token).json()


def get_process_messages(token: str, process_ref_no: str) -> list[dict]:
    return _request("GET", f"/validation/{process_ref_no}/messages", token).json()


def get_validation_page_data(token: str, *, force_refresh: bool = False) -> dict:
    """Fetch the validation page's resources concurrently and cache them briefly."""
    global _dashboard_cache, _dashboard_cache_expires_at

    with _dashboard_cache_lock:
        now = monotonic()
        if not force_refresh and _dashboard_cache is not None and now < _dashboard_cache_expires_at:
            return deepcopy(_dashboard_cache)

        futures = {
            "big_numbers": _dashboard_executor.submit(get_big_numbers, token),
            "sap_processes": _dashboard_executor.submit(get_sap_processes, token),
        }
        data = {name: future.result() for name, future in futures.items()}
        data["kpis"] = data["big_numbers"]

        _dashboard_cache = data
        _dashboard_cache_expires_at = monotonic() + _DASHBOARD_CACHE_TTL_SECONDS
        return deepcopy(data)
