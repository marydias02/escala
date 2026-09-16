"""Token acquisition against Entra.

MSAL validates the ID token it receives, which is what makes `session["user"]`
trustworthy, but never the access token: that is opaque to a client and is
verified by the FastAPI service that receives it. The token cache lives in the
Flask session, so it is encrypted at rest and vanishes when the user signs out.
"""

import msal
from flask import g, session

import config


def build_msal_app(cache: msal.SerializableTokenCache | None = None) -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        config.OIDC_CLIENT_ID,
        authority=config.OIDC_AUTHORITY,
        client_credential=config.OIDC_CLIENT_SECRET,
        token_cache=cache,
    )


def load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if serialized := session.get("token_cache"):
        cache.deserialize(serialized)
    return cache


def save_cache(cache: msal.SerializableTokenCache) -> None:
    """Persist the cache back to the session, but only when MSAL changed it.

    Serialization is a leaky abstraction the caller has to manage; writing
    unconditionally would mark every session dirty on every request.
    """
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()


def get_access_token() -> str | None:
    """The user's access token, refreshed silently if near expiry.

    Must be called from a Flask request context. `acquire_token_silent` returns
    the cached token when it is still good and redeems the refresh token when it
    is not.
    `None` means the refresh token is gone or was rejected — the session is over.

    Memoised on `g` so the guard and every callback it protects share one MSAL
    call per request.
    """
    if "access_token" in g:
        return g.access_token

    cache = load_cache()
    client = build_msal_app(cache)
    accounts = client.get_accounts()
    result = client.acquire_token_silent(config.OIDC_SCOPES, account=accounts[0]) if accounts else None
    save_cache(cache)

    g.access_token = (result or {}).get("access_token")
    return g.access_token
