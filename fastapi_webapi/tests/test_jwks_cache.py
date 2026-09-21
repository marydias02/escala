"""JWKS / discovery cache behaviour.

These drive `openid_connect.decode_verified_token` directly with `httpx.get`
replaced by a call counter, so they assert *counts of fetches* rather than which
key verified -- python-jose ignores `kid` when selecting a key, so a
"right key was used" assertion would pass vacuously.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from api.dependencies import security


def _expired_timestamp() -> float:
    return time.monotonic() - security.props.JWKS_CACHE_TTL_SECONDS - 60


def _decode(token: str):
    return asyncio.run(security.openid_connect.decode_verified_token(token))


def _prime(mint_token) -> None:
    """Populate both caches with one successful validation."""
    _decode(mint_token(roles=["User"]))


def test_unknown_kid_triggers_exactly_one_refetch(reset_security_caches, counting_httpx, mint_token):
    calls, _ = counting_httpx
    _prime(mint_token)
    assert calls == {"discovery": 1, "jwks": 1}

    forged = mint_token(kid="test-key-unpublished", sign_with="test-key-unpublished")
    with pytest.raises(HTTPException):
        _decode(forged)
    assert calls["jwks"] == 2
    assert calls["discovery"] == 1

    # The refetch floor suppresses a second forced hit from another unknown kid.
    with pytest.raises(HTTPException):
        _decode(mint_token(kid="still-unknown", sign_with="test-key-unpublished"))
    assert calls["jwks"] == 2


def test_garbage_expired_and_forged_tokens_trigger_no_refetch(reset_security_caches, counting_httpx, mint_token):
    calls, _ = counting_httpx
    _prime(mint_token)
    assert calls["jwks"] == 1

    bad_tokens = [
        "not-a-jwt",
        mint_token(roles=["User"], expires_in=-10),
        mint_token(roles=["User"], kid="test-key-1", sign_with="test-key-unpublished"),
    ]
    for token in bad_tokens:
        with pytest.raises(HTTPException):
            _decode(token)
    assert calls["jwks"] == 1


def test_concurrent_cold_start_fetches_each_cache_once(reset_security_caches, counting_httpx, mint_token):
    calls, state = counting_httpx
    state["delay"] = 0.05
    token = mint_token(roles=["User"])

    # The barrier is what makes this test about locking. Without it a slow thread pool
    # lets the first thread populate both caches before the last one starts, and the
    # counts come out at 1 whether or not the double-checked locking exists.
    workers = 8
    barrier = threading.Barrier(workers)

    def _decode_together(_):
        barrier.wait(timeout=5)
        return security.openid_connect._decode(token)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_decode_together, range(workers)))

    assert all(claims["sub"] == "user-123" for claims in results)
    assert calls == {"discovery": 1, "jwks": 1}


def test_failed_discovery_refresh_serves_stale_document(reset_security_caches, counting_httpx, mint_token, oidc_urls):
    _, state = counting_httpx
    _prime(mint_token)

    url = oidc_urls["metadata_url"]
    _, cached_doc = security._discovery_cache[url]
    security._discovery_cache[url] = (_expired_timestamp(), cached_doc)
    state["fail_discovery"] = True

    assert security.oidc_discovery(url) == cached_doc
    assert url in security._discovery_last_failed


def test_failed_jwks_refresh_serves_stale_keys(reset_security_caches, counting_httpx, mint_token, oidc_urls):
    calls, state = counting_httpx
    _prime(mint_token)

    url = oidc_urls["metadata_url"]
    _, cached_keys = security._jwks_cache[url]
    security._jwks_cache[url] = (_expired_timestamp(), cached_keys)
    state["fail_jwks"] = True

    assert security.jwks_keys(url) == cached_keys
    assert calls["jwks"] == 2
    assert security.jwks_keys(url) == cached_keys
    assert calls["jwks"] == 2


@pytest.mark.parametrize("failing_fetch", ["fail_discovery", "fail_jwks"])
def test_transport_failure_with_nothing_cached_returns_503(
    reset_security_caches, counting_httpx, mint_token, failing_fetch
):
    _, state = counting_httpx
    state[failing_fetch] = True

    with pytest.raises(HTTPException) as excinfo:
        _decode(mint_token(roles=["User"]))
    assert excinfo.value.status_code == 503
