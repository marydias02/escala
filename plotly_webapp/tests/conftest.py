"""Test harness for the Dash app's OIDC sign-in.

Two kinds of test share these fixtures. Route and guard tests replace MSAL's
`ConfidentialClientApplication` with a mock and keep sessions in a signed cookie,
so they run anywhere. Session-store tests need a real Postgres and are skipped
unless `TEST_DATABASE_URI` names one — see `test_session_store.py`.

No auth bypass exists in shipped code: what these tests substitute is the
identity provider and, for the cookie-backed tests, Flask's own default session
interface. Both are test-process constructs.
"""

import os
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from flask import Flask, jsonify, session
from flask.sessions import SecureCookieSessionInterface

# Pin the frontend config before `config` is imported. python-dotenv does not
# override an existing env var, so these win over any local .env.
TEST_TENANT = "00000000-0000-0000-0000-000000000000"
TEST_CLIENT_ID = "escala-test-client"
TEST_AUTHORITY = f"https://login.microsoftonline.com/{TEST_TENANT}"
TEST_SCOPE = f"api://{TEST_CLIENT_ID}/access_as_user"
TEST_FERNET_KEY = Fernet.generate_key().decode()

os.environ["BACKEND_BASE_URL"] = "http://backend.test"
os.environ["OIDC_AUTHORITY"] = TEST_AUTHORITY
os.environ["OIDC_CLIENT_ID"] = TEST_CLIENT_ID
os.environ["OIDC_CLIENT_SECRET"] = "escala-test-secret"
os.environ["OIDC_SCOPES"] = TEST_SCOPE
os.environ["OIDC_REDIRECT_URI"] = "http://localhost:8050/authorized"
os.environ["OIDC_POST_LOGOUT_REDIRECT_URI"] = "http://localhost:8050/"
os.environ["SESSION_IDLE_TIMEOUT_SECONDS"] = "28800"
os.environ["SESSION_ENCRYPTION_KEY"] = TEST_FERNET_KEY
os.environ["FLASK_SECRET_KEY"] = "escala-test-flask-secret"

TEST_CLAIMS = {
    "name": "Ana Silva",
    "preferred_username": "ana.silva@example.com",
    "roles": ["user"],
    "oid": "user-123",
}


@pytest.fixture
def msal_app(monkeypatch):
    """A mocked `ConfidentialClientApplication`, wired for the happy path.

    Patches `build_msal_app` rather than the `msal` module, so every caller in
    `auth` — the routes and the silent-refresh path alike — gets this object.
    """
    from auth import msal_client

    client = MagicMock(name="ConfidentialClientApplication")
    client.initiate_auth_code_flow.return_value = {
        "auth_uri": f"{TEST_AUTHORITY}/oauth2/v2.0/authorize?client_id={TEST_CLIENT_ID}",
        "state": "flow-state-123",
        "code_verifier": "verifier",
        "redirect_uri": os.environ["OIDC_REDIRECT_URI"],
    }
    client.acquire_token_by_auth_code_flow.return_value = {
        "access_token": "access-token-from-code",
        "id_token_claims": dict(TEST_CLAIMS),
    }
    client.get_accounts.return_value = [{"home_account_id": "home-123"}]
    client.acquire_token_silent.return_value = {"access_token": "access-token-silent"}

    monkeypatch.setattr(msal_client, "build_msal_app", lambda cache=None: client)
    return client


@pytest.fixture
def make_app(msal_app):
    """Build a bare Flask app carrying the auth layer and two guarded routes.

    Deliberately not the Dash app: the guard, the routes and the session
    interface are plain Flask, and importing `app.py` would drag the whole page
    tree in for no gain. `/_dash-update-component` is declared here because it is
    the path the guard must answer with JSON rather than a redirect.
    """

    def factory(session_interface=None):
        server = Flask(__name__)
        from auth.routes import register_auth

        register_auth(server)
        # Cookie sessions by default: routing behaviour is the subject, storage
        # is `test_session_store.py`'s.
        server.session_interface = session_interface or SecureCookieSessionInterface()

        @server.route("/")
        def index():
            return jsonify({"user": session.get("user")})

        @server.route("/_dash-update-component", methods=["POST"])
        def dash_update():
            return jsonify({"response": {}})

        return server

    return factory


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def signed_in(client):
    """Put a completed sign-in in the session, as `/authorized` would leave it."""

    def _sign_in(claims: dict | None = None):
        with client.session_transaction() as session:
            session["user"] = dict(claims or TEST_CLAIMS)
        return client

    return _sign_in
