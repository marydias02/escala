"""A Flask session kept in Postgres and encrypted at rest.

Custom rather than Flask-Session: the table is owned by the backend's Alembic
migration 20260908_01, and Flask-Session's SQLAlchemy backend defines its own
shape and creates it itself, which collides head-on with that ownership.

The cookie carries only a signed session id; everything else — the identity
claims and the MSAL token cache, refresh token included — lives in the `data`
column as Fernet ciphertext.
"""

import json
import secrets
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from flask import g
from flask.sessions import SessionInterface, SessionMixin
from itsdangerous import BadSignature, URLSafeSerializer
from psycopg_pool import ConnectionPool
from werkzeug.datastructures import CallbackDict

# 48 bytes is 64 base64url characters with no padding — the column's full width.
SESSION_ID_BYTES = 48


class PostgresSession(CallbackDict, SessionMixin):
    """A session dictionary that remembers the row it came from."""

    def __init__(self, initial: dict | None = None, sid: str | None = None) -> None:
        CallbackDict.__init__(self, initial, lambda _: setattr(self, "modified", True))
        self.sid = sid
        self.modified = False


class PostgresSessionInterface(SessionInterface):
    def __init__(self, dsn: str, fernet_key: str, idle_timeout_seconds: int, cookie_salt: str) -> None:
        self._fernet = Fernet(fernet_key)
        self._idle_timeout = timedelta(seconds=idle_timeout_seconds)
        self._cookie_salt = cookie_salt
        self._pool = ConnectionPool(dsn, min_size=0, max_size=8, open=False)

    # -- storage ---------------------------------------------------------

    def _encrypt(self, session) -> bytes:
        return self._fernet.encrypt(json.dumps(dict(session)).encode())

    def _connections(self) -> ConnectionPool:
        if self._pool.closed:
            self._pool.open()
        return self._pool

    def _load(self, sid: str) -> bytes | None:
        with self._connections().connection() as conn:
            row = conn.execute(
                "SELECT data FROM webapp.sessions WHERE session_id = %s AND expires_at > now()",
                (sid,),
            ).fetchone()
        return bytes(row[0]) if row else None

    def _store(self, sid: str, data: bytes, expires_at: datetime) -> None:
        with self._connections().connection() as conn:
            conn.execute(
                "INSERT INTO webapp.sessions (session_id, data, expires_at) VALUES (%s, %s, %s)"
                " ON CONFLICT (session_id) DO UPDATE SET data = EXCLUDED.data,"
                " expires_at = EXCLUDED.expires_at, updated_at = now()",
                (sid, data, expires_at),
            )

    def _store_contents(self, sid: str, data: bytes) -> None:
        """Replace contents, leaving `expires_at` and `updated_at` alone."""
        with self._connections().connection() as conn:
            conn.execute("UPDATE webapp.sessions SET data = %s WHERE session_id = %s", (data, sid))

    def _delete(self, sid: str) -> None:
        with self._connections().connection() as conn:
            conn.execute("DELETE FROM webapp.sessions WHERE session_id = %s", (sid,))

    # -- cookie ----------------------------------------------------------

    def _serializer(self, app) -> URLSafeSerializer:
        return URLSafeSerializer(app.secret_key, salt=self._cookie_salt)

    def _read_sid(self, app, request) -> str | None:
        cookie = request.cookies.get(app.config["SESSION_COOKIE_NAME"])
        if not cookie:
            return None
        try:
            return self._serializer(app).loads(cookie)
        except BadSignature:
            return None

    # -- interface -------------------------------------------------------

    def open_session(self, app, request) -> PostgresSession:
        sid = self._read_sid(app, request)
        if sid is None:
            return PostgresSession()

        stored = self._load(sid)
        if stored is None:
            return PostgresSession()

        try:
            data = json.loads(self._fernet.decrypt(stored))
        except (InvalidToken, ValueError):
            return PostgresSession()

        return PostgresSession(data, sid=sid)

    def save_session(self, app, session, response) -> None:
        name = app.config["SESSION_COOKIE_NAME"]
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)

        if not session:
            if session.sid:
                self._delete(session.sid)
                response.delete_cookie(name, domain=domain, path=path)
            return

        if not g.get("session_activity", True) and session.sid:
            if session.modified:
                self._store_contents(session.sid, self._encrypt(session))
            return

        sid = session.sid or secrets.token_urlsafe(SESSION_ID_BYTES)
        expires_at = datetime.now(UTC) + self._idle_timeout
        self._store(sid, self._encrypt(session), expires_at)
        session.sid = sid

        response.set_cookie(
            name,
            self._serializer(app).dumps(sid),
            expires=expires_at,
            httponly=self.get_cookie_httponly(app),
            secure=self.get_cookie_secure(app),
            samesite=self.get_cookie_samesite(app),
            domain=domain,
            path=path,
        )
