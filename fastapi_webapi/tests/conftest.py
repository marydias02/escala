"""Test harness for OIDC token validation and RBAC.

The suite mints its own RSA-signed JWTs and serves a local JWKS, so the real
validation code path in `api.dependencies.security` runs end to end with no
network call and no auth bypass in shipped code. Authorization-focused tests
instead swap a fixed claims dict in through `app.dependency_overrides`, a
mechanism that exists only inside a test process.
"""

import base64
import os
import time
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwt

# Pin OIDC config before `api.*` is imported. python-dotenv does not override an
# existing env var, so these win over any local .env. The metadata URL is a
# non-Microsoft, unroutable address: issuer validation stays enabled and the one
# discovery call made at import time fails fast and is swallowed by construction.
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ["OIDC_METADATA_URL"] = "http://localhost:9/oidc/.well-known/openid-configuration"
os.environ["OIDC_CLIENT_ID"] = "escala-test-client"
os.environ["OIDC_AUDIENCE"] = "escala-test-client"
os.environ["OIDC_SCOPES"] = "api://escala-test-client/access_as_user"
os.environ["OIDC_JWKS_CACHE_TTL_SECONDS"] = "3600"

from api.dependencies import security

TEST_AUDIENCE = "escala-test-client"
TEST_ISSUER = "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0"
JWKS_URI = "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/discovery/v2.0/keys"

_UNSET = object()


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class _Key:
    def __init__(self, kid: str) -> None:
        self.kid = kid
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.pem = self._private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

    def jwk(self) -> dict:
        numbers = self._private.public_key().public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self.kid,
            "n": _b64url_uint(numbers.n),
            "e": _b64url_uint(numbers.e),
        }


@pytest.fixture(scope="session")
def keys() -> dict[str, _Key]:
    """Three keys: two published in the JWKS, one never published (forgery)."""
    return {kid: _Key(kid) for kid in ("test-key-1", "test-key-2", "test-key-unpublished")}


@pytest.fixture(scope="session")
def jwks(keys) -> list[dict]:
    return [keys["test-key-1"].jwk(), keys["test-key-2"].jwk()]


@pytest.fixture
def mint_token(keys):
    """Factory for signed JWTs. `roles=None` omits the claim entirely."""

    def _mint(
        *,
        roles=_UNSET,
        aud: str = TEST_AUDIENCE,
        iss: str = TEST_ISSUER,
        kid: str = "test-key-1",
        sign_with: str | None = None,
        expires_in: int = 3600,
    ) -> str:
        now = datetime.now(UTC)
        claims = {
            "sub": "user-123",
            "name": "Test User",
            "preferred_username": "test.user@example.com",
            "aud": aud,
            "iss": iss,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
        }
        if roles is _UNSET:
            roles = ["User"]
        if roles is not None:
            claims["roles"] = roles
        signer = keys[sign_with or kid]
        return jwt.encode(claims, signer.pem, algorithm="RS256", headers={"kid": kid})

    return _mint


_CACHE_STORES = (
    "_discovery_cache",
    "_discovery_last_failed",
    "_jwks_cache",
    "_jwks_last_forced",
    "_jwks_last_failed",
)


def _clear_security_caches() -> None:
    for name in _CACHE_STORES:
        store = getattr(security, name, None)
        if store is not None:
            store.clear()


@pytest.fixture
def reset_security_caches():
    _clear_security_caches()
    yield
    _clear_security_caches()


@pytest.fixture
def oidc_urls() -> dict[str, str]:
    return {
        "metadata_url": os.environ["OIDC_METADATA_URL"],
        "issuer": TEST_ISSUER,
        "jwks_uri": JWKS_URI,
    }


@pytest.fixture
def fake_oidc(reset_security_caches, jwks, monkeypatch):
    """Serve the local key set and a synthetic issuer to the real decode path."""
    discovery = {
        "issuer": TEST_ISSUER,
        "jwks_uri": JWKS_URI,
        "authorization_endpoint": "https://login.microsoftonline.com/test/oauth2/v2.0/authorize",
        "token_endpoint": "https://login.microsoftonline.com/test/oauth2/v2.0/token",
        "scopes_supported": ["openid", "profile"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }
    monkeypatch.setattr(security, "oidc_discovery", lambda *a, **k: discovery)
    monkeypatch.setattr(security, "jwks_keys", lambda *a, **k: list(jwks))
    return discovery


@pytest.fixture
def app(fake_oidc):
    from api.main import app as fastapi_app

    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client(app) -> TestClient:
    # No `with` block: the DB lifespan never runs, so a test that reaches a
    # service must override it.
    return TestClient(app)


@pytest.fixture
def auth():
    return lambda token: {"Authorization": f"Bearer {token}"}


@pytest.fixture
def override_claims(app):
    def _override(claims: dict) -> None:
        app.dependency_overrides[security.openid_connect] = lambda: claims

    return _override


class _StubExtractionService:
    async def list_all_documents(self, limit: int = 100):
        return []


@pytest.fixture
def stub_extraction_service(app):
    from api.dependencies.services import get_extraction_service

    app.dependency_overrides[get_extraction_service] = lambda: _StubExtractionService()


class _StubSearchService:
    """Records the (q, limit) each route passed and returns a canned list."""

    def __init__(self, rows=None):
        self.rows = rows if rows is not None else []
        self.calls: list[tuple[str, str, int]] = []

    async def search_suppliers(self, q: str, limit: int = 10):
        return self._record("suppliers", q, limit)

    async def search_business_units(self, q: str, limit: int = 10):
        return self._record("business_units", q, limit)

    async def search_purchase_orders(self, q: str, limit: int = 10):
        return self._record("purchase_orders", q, limit)

    def _record(self, entity: str, q: str, limit: int):
        self.calls.append((entity, q, limit))
        return self.rows


@pytest.fixture
def stub_search_service(app):
    from api.dependencies.services import get_search_service

    stub = _StubSearchService()
    app.dependency_overrides[get_search_service] = lambda: stub
    return stub


class _StubAirService:
    async def upload_template(self, file_content: bytes) -> int:
        return 1


@pytest.fixture
def stub_air_service(app):
    from api.dependencies.services import get_air_service

    app.dependency_overrides[get_air_service] = lambda: _StubAirService()


@pytest.fixture
def counting_httpx(monkeypatch, jwks, oidc_urls):
    """Replace `security.httpx.get` with a per-URL call counter over a fake provider."""
    calls = {"discovery": 0, "jwks": 0}
    state = {"fail_discovery": False, "fail_jwks": False, "delay": 0.0}
    discovery_doc = {
        "issuer": oidc_urls["issuer"],
        "jwks_uri": oidc_urls["jwks_uri"],
        "authorization_endpoint": "https://example.test/authorize",
        "token_endpoint": "https://example.test/token",
        "scopes_supported": ["openid"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }

    class _Resp:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    def fake_get(url, *args, **kwargs):
        if state["delay"]:
            time.sleep(state["delay"])
        if url == oidc_urls["metadata_url"]:
            calls["discovery"] += 1
            if state["fail_discovery"]:
                raise security.httpx.ConnectError("discovery unreachable")
            return _Resp(discovery_doc)
        if url == oidc_urls["jwks_uri"]:
            calls["jwks"] += 1
            if state["fail_jwks"]:
                raise security.httpx.ConnectError("jwks unreachable")
            return _Resp({"keys": list(jwks)})
        raise AssertionError(f"unexpected URL fetched: {url}")

    monkeypatch.setattr(security.httpx, "get", fake_get)
    return calls, state
