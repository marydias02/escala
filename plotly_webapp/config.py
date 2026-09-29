"""Frontend configuration: one module-level constant per environment variable.

Follows `fastapi_webapi/src/api/properties.py` in style on purpose. Nothing
tenant-specific, environment-specific or timing-related is hardcoded anywhere
else, so moving to another Entra registration is a secret change plus a
redeploy, with no code edit.
"""

import os

from dotenv import find_dotenv, load_dotenv

if dotenv_path := find_dotenv():
    load_dotenv(dotenv_path)

# Backend

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000").rstrip("/")

# Optional feature flags. Only an explicit "true" enables Harbor navigation.
DISPLAY_HARBOR = os.getenv("display_harbor", "").strip().lower() == "true"

# OIDC

OIDC_AUTHORITY = os.getenv("OIDC_AUTHORITY", "").rstrip("/")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET")

# The full scope URI (`api://<client-id>/access_as_user`), never `openid profile`:
# those three MSAL adds itself, and asking for them alone yields a token whose
# audience is Microsoft Graph, which the backend correctly rejects.
OIDC_SCOPES = os.getenv("OIDC_SCOPES", "").split()

OIDC_REDIRECT_URI = os.getenv("OIDC_REDIRECT_URI", "http://localhost:8050/authorized")
OIDC_POST_LOGOUT_REDIRECT_URI = os.getenv("OIDC_POST_LOGOUT_REDIRECT_URI", "http://localhost:8050/")

# Entra's v2 end-session endpoint, derived rather than read from the discovery
# document: signing out must not depend on a network call on the way out.
OIDC_LOGOUT_ENDPOINT = f"{OIDC_AUTHORITY}/oauth2/v2.0/logout"

# Sessions

SESSION_IDLE_TIMEOUT_SECONDS = int(os.getenv("SESSION_IDLE_TIMEOUT_SECONDS", "28800"))
SESSION_ENCRYPTION_KEY = os.getenv("SESSION_ENCRYPTION_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

# Namespaces the session-id cookie's signature, so a signature made for anything
# else signed with FLASK_SECRET_KEY cannot be replayed as a session id. Not a
# secret.
SESSION_COOKIE_SALT = os.getenv("SESSION_COOKIE_SALT", "escala-session")

# Database (used for the auth)

DB_SCHEME = os.getenv("DB_SCHEME", "postgresql")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

# psycopg accepts only a plain `postgresql`/`postgres` scheme, not a
# SQLAlchemy-style driver suffix; strip any `+driver` so one `.env` serves both.
DB_SCHEME = DB_SCHEME.split("+", 1)[0]

DATABASE_URI = f"{DB_SCHEME}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
