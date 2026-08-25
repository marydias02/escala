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
_dashboard_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="validation-api")
_dashboard_cache_lock = Lock()
_dashboard_cache: dict | None = None
_dashboard_cache_expires_at = 0.0


def _get_session() -> requests.Session:
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


def get_validation_dashboard() -> dict:
    return _request("GET", "/extraction/big-numbers").json()


def get_sap_processes():
    return _request("GET", "/validation/documents").json()


def get_validation_page_data(*, force_refresh: bool = False) -> dict:
    global _dashboard_cache, _dashboard_cache_expires_at

    with _dashboard_cache_lock:
        now = monotonic()
        if not force_refresh and _dashboard_cache is not None and now < _dashboard_cache_expires_at:
            return deepcopy(_dashboard_cache)

        futures = {
            "kpis": _dashboard_executor.submit(get_validation_dashboard),
            "sap_processes": _dashboard_executor.submit(get_sap_processes),
        }
        data = {name: future.result() for name, future in futures.items()}

        _dashboard_cache = data
        _dashboard_cache_expires_at = monotonic() + _DASHBOARD_CACHE_TTL_SECONDS
        return deepcopy(data)
