"""`PostgresSessionInterface` against a real database.

Skipped unless `TEST_DATABASE_URI` names a Postgres carrying migration
20260908_01. That variable is deliberately separate from the app's own
`DB_*`: these tests delete from `webapp.sessions`, which must never happen by
accident against a database somebody is signed in to.

    TEST_DATABASE_URI=postgresql://user:pw@localhost:5432/escala uv run pytest -q

Two guards stand between that variable and a mass sign-out, and both refuse
rather than delete. The first fails the run outright when `TEST_DATABASE_URI`
resolves to the same host, port and database as the app's own `DB_*` — a
misconfiguration to fix, so it fails loudly and before the connection is opened.
The second skips when `webapp.sessions` is **not empty** at setup: a populated
table means live sessions, and deleting them signs those people out; a busy
database is a condition to come back from, not an error. Having proved the table
started empty, the teardown delete provably removes only rows these tests made.

Nothing at the database level stops these tests from reaching
the application tables. The guards above are the only thing that does.

The two behaviours here that are easy to get wrong, and are therefore each
asserted directly: an undecryptable row means "no session", not `500` — that is
what a rotated `SESSION_ENCRYPTION_KEY` looks like, and it must sign everyone out
cleanly rather than break the site for everyone at once; and `/auth/status` must
not slide the idle window, or the sixty-second heartbeat keeps every open tab
alive forever and `SESSION_IDLE_TIMEOUT_SECONDS` becomes dead code.
"""

import json
import os
from urllib.parse import urlparse

import pytest
from conftest import TEST_FERNET_KEY
from cryptography.fernet import Fernet
from flask import g, session

psycopg = pytest.importorskip("psycopg")

DATABASE_URI = os.getenv("TEST_DATABASE_URI")
IDLE_TIMEOUT_SECONDS = 28800
TEST_COOKIE_SALT = "escala-session-test"

pytestmark = pytest.mark.skipif(
    not DATABASE_URI,
    reason="set TEST_DATABASE_URI to a Postgres carrying migration 20260908_01",
)


def _endpoint(dsn: str) -> tuple:
    parsed = urlparse(dsn)
    return parsed.hostname, parsed.port, parsed.path


def _is_the_apps_own_database(dsn: str) -> bool:
    try:
        import config
    except ImportError:
        return False
    return _endpoint(dsn) == _endpoint(config.DATABASE_URI)


@pytest.fixture
def db():
    # `fail`, not `skip`: this is a misconfiguration to correct, not an
    # environment that happens to be unsuitable today. The refusal comes before
    # the connection, so a wrong DSN is never even opened.
    if _is_the_apps_own_database(DATABASE_URI):
        pytest.fail(
            "TEST_DATABASE_URI names the same database as the app's own DB_* configuration."
            " These tests delete from webapp.sessions; point them at a database the app does"
            " not use.",
            pytrace=False,
        )

    with psycopg.connect(DATABASE_URI, autocommit=True) as conn:
        # Refuse rather than delete: rows here are people's live sessions, and
        # wiping them signs every one of them out.
        live = conn.execute("SELECT count(*) FROM webapp.sessions").fetchone()[0]
        if live:
            pytest.skip(
                f"webapp.sessions holds {live} row(s) — refusing to delete live sessions."
                " Point TEST_DATABASE_URI at a database with no sessions in it."
            )

        yield conn
        # Safe as a bulk delete only because the table was empty above.
        conn.execute("DELETE FROM webapp.sessions")


def only_row(db):
    row = db.execute("SELECT session_id, data, expires_at, created_at, updated_at FROM webapp.sessions").fetchone()
    assert row is not None, "expected exactly one session row"
    return {
        "session_id": row[0],
        "data": row[1],
        "expires_at": row[2],
        "created_at": row[3],
        "updated_at": row[4],
    }


def row_count(db):
    return db.execute("SELECT count(*) FROM webapp.sessions").fetchone()[0]


@pytest.fixture
def client(db, make_app):
    from auth.session_store import PostgresSessionInterface

    server = make_app(
        PostgresSessionInterface(
            dsn=DATABASE_URI,
            fernet_key=TEST_FERNET_KEY,
            idle_timeout_seconds=IDLE_TIMEOUT_SECONDS,
            cookie_salt=TEST_COOKIE_SALT,
        )
    )

    @server.route("/non-activity-write")
    def non_activity_write():
        """Stand-in for the heartbeat's silent token refresh.

        `/auth/status` writes the session only when MSAL rewrites its cache, which
        the mocked provider never does — so the interaction is driven directly:
        a request that is not user activity, that modifies the session.
        """
        g.session_activity = False
        session["token_cache"] = "refreshed-by-the-heartbeat"
        return "", 204

    return server.test_client()


class TestRoundTrip:
    def test_a_dictionary_survives_across_requests(self, client):
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva", "roles": ["user"]}

        assert client.get("/").get_json()["user"] == {"name": "Ana Silva", "roles": ["user"]}

    def test_one_row_per_session(self, client, db):
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva"}

        client.get("/")
        client.get("/")

        assert row_count(db) == 1

    def test_the_session_id_is_the_full_column_width(self, client, db):
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva"}

        assert len(only_row(db)["session_id"]) == 64


class TestEncryption:
    def test_data_is_stored_as_ciphertext(self, client, db):
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva"}
            session["token_cache"] = "a-refresh-token-lives-in-here"

        stored = only_row(db)["data"]

        assert isinstance(stored, (bytes, memoryview))
        assert b"a-refresh-token-lives-in-here" not in bytes(stored)
        assert b"Ana Silva" not in bytes(stored)

    def test_the_ciphertext_decrypts_to_the_session(self, client, db):
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva"}

        plaintext = Fernet(TEST_FERNET_KEY).decrypt(bytes(only_row(db)["data"]))

        assert json.loads(plaintext)["user"] == {"name": "Ana Silva"}

    def test_an_undecryptable_row_is_treated_as_no_session(self, client, db):
        # What a rotated SESSION_ENCRYPTION_KEY looks like from here.
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva"}
        db.execute("UPDATE webapp.sessions SET data = %s", (b"not-a-fernet-token",))

        response = client.get("/")

        assert response.status_code == 302
        assert urlparse(response.headers["Location"]).path == "/login"


class TestExpiry:
    def test_a_row_past_expires_at_is_absent(self, client, db):
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva"}
        db.execute("UPDATE webapp.sessions SET expires_at = now() - interval '1 second'")

        response = client.get("/")

        assert response.status_code == 302
        assert urlparse(response.headers["Location"]).path == "/login"

    def test_a_real_request_slides_the_idle_window(self, client, db):
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva"}
        db.execute(
            "UPDATE webapp.sessions SET updated_at = now() - interval '1 hour', expires_at = now() + interval '1 hour'"
        )
        before = only_row(db)

        assert client.get("/").status_code == 200

        after = only_row(db)
        assert after["updated_at"] > before["updated_at"]
        assert after["expires_at"] > before["expires_at"]

    def test_a_non_activity_write_persists_contents_without_sliding_the_window(self, client, db):
        # The heartbeat checks the token, and a check can renew it. Persisting that
        # renewal must not also renew the idle window: at an eight-hour timeout and
        # an hourly token, a tab left open would otherwise never time out at all.
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva"}
        db.execute(
            "UPDATE webapp.sessions SET updated_at = now() - interval '1 hour', expires_at = now() + interval '1 hour'"
        )
        before = only_row(db)

        assert client.get("/non-activity-write").status_code == 204

        after = only_row(db)
        assert after["expires_at"] == before["expires_at"]
        assert after["updated_at"] == before["updated_at"]
        assert after["data"] != before["data"]
        stored = json.loads(Fernet(TEST_FERNET_KEY).decrypt(bytes(after["data"])))
        assert stored["token_cache"] == "refreshed-by-the-heartbeat"

    def test_the_heartbeat_does_not_slide_the_idle_window(self, client, db):
        with client.session_transaction() as session:
            session["user"] = {"name": "Ana Silva"}
        db.execute(
            "UPDATE webapp.sessions SET updated_at = now() - interval '1 hour', expires_at = now() + interval '1 hour'"
        )
        before = only_row(db)

        assert client.get("/auth/status").get_json()["authenticated"] is True

        after = only_row(db)
        assert after["updated_at"] == before["updated_at"]
        assert after["expires_at"] == before["expires_at"]


class TestSignInAndOutWriteTheTable:
    def test_authorized_creates_a_row(self, client, db):
        assert row_count(db) == 0

        assert client.get("/login").status_code == 302
        assert row_count(db) == 0

        client.post("/authorized", data={"code": "auth-code", "state": "flow-state-123"})

        assert row_count(db) == 1
        assert json.loads(Fernet(TEST_FERNET_KEY).decrypt(bytes(only_row(db)["data"])))["user"]["name"] == "Ana Silva"

    def test_logout_deletes_the_row(self, client, db):
        client.get("/login")
        client.post("/authorized", data={"code": "auth-code", "state": "flow-state-123"})
        assert row_count(db) == 1

        client.get("/logout")

        assert row_count(db) == 0
