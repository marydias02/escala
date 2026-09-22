"""The per-user token must not ride on shared state.

Two mechanical forms of one rule. The `requests.Session` objects are per thread
and long-lived, and under `gunicorn -w 4` those threads serve whoever comes
next — so a token baked into `session.headers` is one user's credential attached
to another user's request. And the dashboard functions run on a module-level
`ThreadPoolExecutor` with no Flask request context, so the token cannot be read
down there: it has to be read once in the request thread and passed as an
ordinary argument.
"""

from unittest.mock import MagicMock, patch

import pytest

from assets.api_calls import extraction_api, validation_api

API_MODULES = pytest.mark.parametrize("module", [extraction_api, validation_api], ids=["extraction", "validation"])


def _clear_caches():
    for module in (extraction_api, validation_api):
        module._dashboard_cache = None
        module._dashboard_cache_expires_at = 0.0


@pytest.fixture(autouse=True)
def clean_dashboard_cache():
    _clear_caches()
    yield
    _clear_caches()


@API_MODULES
def test_no_shared_session_carries_an_authorization_header(module):
    assert "Authorization" not in module._get_session().headers


@API_MODULES
def test_the_module_no_longer_exposes_a_process_wide_header_dict(module):
    # `app.py` imported HEADERS; leaving it behind is a working import that
    # silently reintroduces the shared credential.
    assert not hasattr(module, "HEADERS")


@API_MODULES
def test_the_token_is_attached_per_call(module):
    session = MagicMock()
    with patch.object(module, "_get_session", return_value=session):
        module._request("GET", "/whatever", "token-for-ana")
        module._request("GET", "/whatever", "token-for-bruno")

    first, second = session.request.call_args_list
    assert first.kwargs["headers"]["Authorization"] == "Bearer token-for-ana"
    assert second.kwargs["headers"]["Authorization"] == "Bearer token-for-bruno"


@API_MODULES
def test_the_backend_url_comes_from_configuration(module):
    session = MagicMock()
    with patch.object(module, "_get_session", return_value=session):
        module._request("GET", "/extraction/big-numbers", "a-token")

    assert session.request.call_args.args[1] == "http://backend.test/extraction/big-numbers"


def test_extraction_dashboard_carries_the_token_across_the_thread_pool():
    calls = {}

    def record(name):
        def load(token):
            calls[name] = token
            return []

        return load

    with (
        patch.object(extraction_api, "get_big_numbers", side_effect=record("kpis")),
        patch.object(extraction_api, "get_priority_documents", side_effect=record("priority")),
        patch.object(extraction_api, "get_all_documents", side_effect=record("all")),
        patch.object(extraction_api, "get_pending_processes", side_effect=record("pending")),
    ):
        extraction_api.get_extraction_dashboard("token-for-ana")

    assert calls == dict.fromkeys(("kpis", "priority", "all", "pending"), "token-for-ana")


def test_validation_dashboard_carries_the_token_across_the_thread_pool():
    calls = {}

    def record(name):
        def load(token):
            calls[name] = token
            return {}

        return load

    with (
        patch.object(validation_api, "get_big_numbers", side_effect=record("big_numbers")),
        patch.object(validation_api, "get_sap_processes", side_effect=record("sap_processes")),
    ):
        validation_api.get_validation_page_data("token-for-ana")

    assert calls == {"big_numbers": "token-for-ana", "sap_processes": "token-for-ana"}
