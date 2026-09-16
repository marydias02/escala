import time
from threading import Lock
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import ExpiredSignatureError, JWTError, jwt
from jose.exceptions import JWTClaimsError
from loguru import logger

import api.properties as props
from api.properties import AUDIENCE

## OPENID CONNECT =======================================================
# Provider metadata is cached for props.JWKS_CACHE_TTL_SECONDS. MIN_REFETCH_SECONDS
# floors how often anything off-schedule -- an unknown kid, a failed refresh --
# may go back to the provider.
MIN_REFETCH_SECONDS = 300

_discovery_cache: dict[str, tuple[float, dict]] = {}
_discovery_last_failed: dict[str, float] = {}
_discovery_lock = Lock()


def _cached_discovery(metadata_url, now):
    """The cached document while it may still be served, else None."""
    cached = _discovery_cache.get(metadata_url)
    if not cached:
        return None
    last_failed = _discovery_last_failed.get(metadata_url)
    if last_failed is not None and now - last_failed < MIN_REFETCH_SECONDS:
        return cached[1]
    if now - cached[0] < props.JWKS_CACHE_TTL_SECONDS:
        return cached[1]
    return None


def oidc_discovery(metadata_url):
    document = _cached_discovery(metadata_url, time.monotonic())
    if document is not None:
        return document
    with _discovery_lock:
        # Re-check: a thread that held the lock before us may have just refreshed,
        # which is what keeps a cold start from stampeding the provider.
        now = time.monotonic()
        document = _cached_discovery(metadata_url, now)
        if document is not None:
            return document
        try:
            response = httpx.get(metadata_url)
            response.raise_for_status()
            document = response.json()
        except Exception as exc:
            # A stale document still names a usable issuer and jwks_uri, so a transient
            # provider outage must not take otherwise-valid tokens down with it.
            cached = _discovery_cache.get(metadata_url)
            if cached:
                _discovery_last_failed[metadata_url] = now
                logger.warning(f"OIDC discovery refresh failed ({metadata_url!r}): {exc}. Serving cached document.")
                return cached[1]
            raise
        _discovery_cache[metadata_url] = (now, document)
        _discovery_last_failed.pop(metadata_url, None)
        return document


_jwks_cache: dict[str, tuple[float, list]] = {}
_jwks_last_forced: dict[str, float] = {}
_jwks_last_failed: dict[str, float] = {}
_jwks_lock = Lock()


def _cached_jwks(metadata_url, now, force_refresh):
    """The cached keys while they may still be served, else None."""
    cached = _jwks_cache.get(metadata_url)
    if not cached:
        return None
    fetched_at, keys = cached
    last_failed = _jwks_last_failed.get(metadata_url)
    if last_failed is not None and now - last_failed < MIN_REFETCH_SECONDS:
        return keys
    if force_refresh:
        last_forced = _jwks_last_forced.get(metadata_url)
        if last_forced is not None and now - last_forced < MIN_REFETCH_SECONDS:
            return keys
        return None
    if now - fetched_at < props.JWKS_CACHE_TTL_SECONDS:
        return keys
    return None


def cached_jwks_kids(metadata_url) -> set:
    """Key ids already held, without triggering a fetch."""
    cached = _jwks_cache.get(metadata_url)
    return {key.get("kid") for key in cached[1]} if cached else set()


def jwks_keys(metadata_url, force_refresh: bool = False):
    keys = _cached_jwks(metadata_url, time.monotonic(), force_refresh)
    if keys is not None:
        return keys
    # Ordering note: this lock is always taken before _discovery_lock, never after.
    with _jwks_lock:
        now = time.monotonic()
        keys = _cached_jwks(metadata_url, now, force_refresh)
        if keys is not None:
            return keys
        try:
            response = httpx.get(oidc_discovery(metadata_url)["jwks_uri"])
            response.raise_for_status()
            keys = response.json()["keys"]
        except Exception as exc:
            cached = _jwks_cache.get(metadata_url)
            if cached:
                _jwks_last_failed[metadata_url] = now
                logger.warning(f"JWKS refresh failed ({metadata_url!r}): {exc}. Serving cached keys.")
                return cached[1]
            raise
        if force_refresh:
            _jwks_last_forced[metadata_url] = now
        _jwks_cache[metadata_url] = (time.monotonic(), keys)
        _jwks_last_failed.pop(metadata_url, None)
        return keys


def is_not_microsoft_multitenant(metadata_url):  # Used for setting defaults only
    return not any(
        metadata_url.startswith(f"https://login.microsoftonline.com/{t}")
        for t in ("common", "organizations", "consumers")
    )


class OpenIdConnectAuthorizationCodeBearer(OAuth2AuthorizationCodeBearer):
    def __init__(
        self,
        metadata_url=props.OIDC_METADATA_URL,
        audience=AUDIENCE,
        scheme_name=None,
        validate_iss: bool = None,
        validate_aud: bool = True,
        scopes=None,
    ):
        self._audience = audience
        self.metadata_url = metadata_url
        self._validate_iss = validate_iss if validate_iss is not None else is_not_microsoft_multitenant(metadata_url)
        self._validate_aud = validate_aud

        if not scheme_name:
            try:
                scheme_name = urlparse(metadata_url).hostname or "OIDC"
            except ValueError:
                scheme_name = "OIDC"

        # Discovery is a network call. Do NOT let it fail app startup: when the
        # OIDC provider is unset/unreachable (e.g. no provider configured yet),
        # construct with empty endpoints so API-key routes still work. OIDC-protected
        # routes re-run discovery at call time via decode_verified_token(), so they
        # will surface the error only when actually used.
        try:
            discovery = oidc_discovery(self.metadata_url)
            authorization_url = discovery["authorization_endpoint"]
            token_url = discovery["token_endpoint"]
            discovered_scopes = scopes or {k: "" for k in discovery["scopes_supported"]}
        except Exception as exc:  # noqa: BLE001 - startup must not depend on OIDC reachability
            logger.warning(
                f"OIDC discovery unavailable ({self.metadata_url!r}): {exc}. OIDC routes will fail until reachable."
            )
            authorization_url = ""
            token_url = ""
            discovered_scopes = scopes or {}

        super().__init__(
            scheme_name=scheme_name,
            description="Leave secret input blank!",
            authorizationUrl=authorization_url,
            tokenUrl=token_url,
            scopes=discovered_scopes,
        )

    def _decode(self, token: str, force_refresh: bool = False) -> dict[str, Any]:
        discovery = oidc_discovery(self.metadata_url)
        jwk_keys = jwks_keys(self.metadata_url, force_refresh=force_refresh)
        algos = discovery.get("id_token_signing_alg_values_supported", ["RS256"])
        return jwt.decode(
            token,
            jwk_keys,
            algorithms=algos,
            audience=self._audience,
            issuer=discovery["issuer"],
            options={"verify_aud": self._validate_aud, "verify_iss": self._validate_iss},
        )

    def _signed_by_unknown_key(self, token: str) -> bool:
        """Whether the token names a signing key we have not fetched yet."""
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except JWTError:
            return False  # Malformed beyond the header; refetching cannot help.
        return kid is not None and kid not in cached_jwks_kids(self.metadata_url)

    async def decode_verified_token(self, token: str) -> dict[str, Any]:
        # _decode does blocking I/O on a cache miss; keep it off the event loop.
        try:
            return await run_in_threadpool(self._decode, token)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail="Authentication provider unavailable") from e
        except (ExpiredSignatureError, JWTClaimsError) as e:
            raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})
        except JWTError as e:
            if not self._signed_by_unknown_key(token):
                raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})

        try:
            return await run_in_threadpool(self._decode, token, force_refresh=True)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail="Authentication provider unavailable") from e
        except (ExpiredSignatureError, JWTError, JWTClaimsError) as e:
            raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})

    async def __call__(self, request: Request) -> dict:
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(status_code=401, detail="Not Authenticated", headers={"WWW-Authenticate": "Bearer"})
        schema, token = authorization.split(" ")
        if schema != "Bearer":
            raise HTTPException(
                status_code=401, detail="Expected Bearer Authentication", headers={"WWW-Authenticate": "Bearer"}
            )
        return await self.decode_verified_token(token)


openid_connect = OpenIdConnectAuthorizationCodeBearer(scopes={k: "" for k in props.APP_SCOPES.split(" ")})

ValidAccessToken = Annotated[dict, Depends(openid_connect)]

swagger_security_kwargs: dict[str, Any] = dict(
    swagger_ui_oauth2_redirect_url="/oauth2-redirect",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": props.CLIENT_ID,
        "scopes": props.APP_SCOPES.split(" "),
    },
)


# Authorization (Access control)
#
# This section implements a simple role-based access control (RBAC) a very scalable and easy to use model for authorization.
#
# Key concepts:
# - `policy`: defining what and how subjects perform can actions on each resources. Their format is derived from your application design (not the client's security infrastructure).
# - `subject`: the authenticated user (in our case, the decoded and validated token).
# - `isSubjectAuthorized(...)`: checks if subject allowed bt the policy to perform the action on the resource.
# - `hasAuthorizationFor(action, resource)`: returns a FastAPI dependency version of isSubjectAuthorized.

# You might need a more sophisticated approach called Attribute-Based-Access-Control (ABAC) that expands this by adding context-aware rules (example user can access the items they created only).
# You can easly adapt this by changing the way you define the `policy` to include rules (functions/lambdas) and changing the `isSubjectAuthorized(...)` to evaluate them.

policy = {
    "admin": {
        "documents": {"read", "update"},
        "processes": {"read"},
        "runs": {"read", "create"},
    },
    "user": {
        "documents": {"read", "update"},
        "processes": {"read"},
        "runs": {"read"},
    },
}


def is_subject_authorized(subject: dict, action: str, resource: str, **context) -> bool:
    user_roles = subject.get("roles", {"unassigned"})

    for role in user_roles:
        allowed_actions = policy.get(role, {}).get(resource, set())
        if action in allowed_actions:
            return True

    return False


def raise_for_unauthorized(subject: dict, action: str, resource: str, **context):
    if not is_subject_authorized(subject, action, resource, **context):
        raise HTTPException(status_code=403, detail="Forbidden")


def has_authorization_for(action: str, resource: str, **context) -> type[Depends]:
    def authorization_dependency(token_claims: dict = Depends(openid_connect)) -> dict:
        raise_for_unauthorized(token_claims, action, resource, **context)
        return token_claims

    return Depends(authorization_dependency)
