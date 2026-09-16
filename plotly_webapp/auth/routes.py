"""Sign-in routes and the request guard.

The distinction this module exists to draw is between a browser navigation,
which may be redirected to sign-in, and an XHR to `/_dash-update-component`,
which may not: Dash follows a 302 and then receives an HTML sign-in page where it
expected JSON, showing the user a broken screen instead of a sign-in prompt. So
XHR paths get a JSON 401 carrying no `Location` at all, and the `dcc.Interval`
heartbeat in `app.py` does the navigating.

No auth bypass exists here for development or tests: the test suite substitutes
the identity provider, which is a test-process construct. An environment
variable that disabled the guard would be reachable from a running server.
"""

import json
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken
from flask import Flask, g, jsonify, redirect, request, session, url_for

import config
from auth import msal_client
from auth.session_store import PostgresSessionInterface

PUBLIC_PATHS = frozenset({"/login", "/authorized", "/logout", "/auth/status", "/health"})
PUBLIC_PREFIXES = ("/assets/",)

AUTH_FLOW_COOKIE = "escala_auth_flow"
AUTH_FLOW_COOKIE_PATH = "/authorized"

AUTH_FLOW_TTL_SECONDS = 600


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


def _wants_json() -> bool:
    return request.path.startswith("/_dash-") or request.is_json


def _safe_next(path: str | None) -> str:
    """Same-site paths only — an absolute URL here would be an open redirect."""
    if path and path.startswith("/") and not path.startswith("//"):
        return path
    return "/"


def _refuse():
    if _wants_json():
        return jsonify({"error": "unauthenticated", "login_url": url_for("auth_login")}), 401
    # `full_path` keeps a deep link's query string; Flask always appends the "?".
    return redirect(url_for("auth_login", next=request.full_path.rstrip("?")))


def _seal_auth_flow(fernet: Fernet, flow: dict, next_path: str) -> str:
    return fernet.encrypt(json.dumps({"flow": flow, "next": next_path}).encode()).decode()


def _unseal_auth_flow(fernet: Fernet, cookie: str | None) -> dict | None:
    """The stashed handshake, or `None` if it is absent, tampered with or stale."""
    if not cookie:
        return None
    try:
        return json.loads(fernet.decrypt(cookie.encode(), ttl=AUTH_FLOW_TTL_SECONDS))
    except (InvalidToken, ValueError):
        return None


def _forget_auth_flow(response):
    """One use only: the callback spends the cookie whether or not it succeeds."""
    response.delete_cookie(
        AUTH_FLOW_COOKIE,
        path=AUTH_FLOW_COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="None",
    )
    return response


def register_auth(server: Flask) -> None:
    """Attach /login, /authorized, /logout, /auth/status and the before_request guard."""
    server.secret_key = config.FLASK_SECRET_KEY
    flow_fernet = Fernet(config.SESSION_ENCRYPTION_KEY)
    server.session_interface = PostgresSessionInterface(
        dsn=config.DATABASE_URI,
        fernet_key=config.SESSION_ENCRYPTION_KEY,
        idle_timeout_seconds=config.SESSION_IDLE_TIMEOUT_SECONDS,
        cookie_salt=config.SESSION_COOKIE_SALT,
    )

    @server.before_request
    def require_signed_in_user():
        if _is_public(request.path):
            return None
        if not session.get("user"):
            return _refuse()
        if msal_client.get_access_token() is None:
            # An expired or revoked refresh token. Nothing to salvage: end the
            # session here rather than let callbacks call the backend without one.
            session.clear()
            return _refuse()
        return None

    @server.route("/login")
    def auth_login():
        flow = msal_client.build_msal_app().initiate_auth_code_flow(
            scopes=config.OIDC_SCOPES,
            redirect_uri=config.OIDC_REDIRECT_URI,
            response_mode="form_post",
        )
        response = redirect(flow["auth_uri"])
        response.set_cookie(
            AUTH_FLOW_COOKIE,
            _seal_auth_flow(flow_fernet, flow, _safe_next(request.args.get("next"))),
            max_age=AUTH_FLOW_TTL_SECONDS,
            path=AUTH_FLOW_COOKIE_PATH,
            httponly=True,
            secure=True,
            samesite="None",
        )
        return response

    @server.route("/authorized", methods=["POST"])
    def auth_authorized():
        stashed = _unseal_auth_flow(flow_fernet, request.cookies.get(AUTH_FLOW_COOKIE))
        if not stashed:
            # The redirect URI hit directly with no /login before it, or a
            # handshake left unfinished for longer than its lifetime.
            return jsonify({"error": "no_auth_flow"}), 401

        cache = msal_client.load_cache()
        try:
            result = msal_client.build_msal_app(cache).acquire_token_by_auth_code_flow(
                stashed["flow"], request.form.to_dict()
            )
        except ValueError:
            # MSAL raises on a state mismatch: a replayed or tampered callback.
            result = {"error": "invalid_state"}

        if "access_token" not in result:
            # A 401, not a redirect back to /login, which would loop.
            session.clear()
            refusal = jsonify({"error": result.get("error", "sign_in_failed")})
            refusal.status_code = 401
            return _forget_auth_flow(refusal)

        msal_client.save_cache(cache)
        claims = result.get("id_token_claims") or {}
        session["user"] = {
            "name": claims.get("name"),
            "preferred_username": claims.get("preferred_username"),
            "roles": claims.get("roles") or [],
            "oid": claims.get("oid"),
        }
        return _forget_auth_flow(redirect(stashed.get("next", "/")))

    @server.route("/auth/status")
    def auth_status():
        # The one route exempt from sliding the idle window; see `save_session`.
        g.session_activity = False
        if not session.get("user"):
            return jsonify({"authenticated": False})
        if msal_client.get_access_token() is None:
            # A revoked refresh token leaves the session row perfectly healthy, so
            # without this the heartbeat reports a live session until the user next
            # touches a guarded route — which is exactly what it exists to prevent.
            session.clear()
            return jsonify({"authenticated": False})
        return jsonify({"authenticated": True})

    @server.route("/logout")
    def auth_logout():
        session.clear()
        # Clearing the local session alone is not signing out: the next visit
        # would sign the user straight back in silently.
        query = urlencode({"post_logout_redirect_uri": config.OIDC_POST_LOGOUT_REDIRECT_URI})
        return redirect(f"{config.OIDC_LOGOUT_ENDPOINT}?{query}")
