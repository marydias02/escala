import os

from dotenv import find_dotenv, load_dotenv
from loguru import logger

if f := find_dotenv():
    logger.debug("Loading environment at " + f)
    load_dotenv(f)
else:
    logger.trace("No .env file found")

# General

ENVIRONMENT = os.getenv("ENVIRONMENT", "prod")

DEBUG_MODE: bool = ENVIRONMENT == "dev"

BACKEND_BIND_HOST = os.getenv("BIND_HOST", "localhost")
BACKEND_PORT = int(os.getenv("BIND_PORT", "8080"))

BACKEND_CORS_ORIGINS = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:8050").split(",")

# Database

DB_SCHEME = os.getenv("DB_SCHEME", "postgresql")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

# The runtime uses raw asyncpg, which accepts only a plain `postgresql`/`postgres`
# scheme — not a SQLAlchemy-style driver suffix like `postgresql+asyncpg`. Strip
# any `+driver` so a `.env` written for SQLAlchemy still works here.
DB_SCHEME = DB_SCHEME.split("+", 1)[0]

DATABASE_URI = f"{DB_SCHEME}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# AUTHENTICATION
## OIDC
OIDC_METADATA_URL = os.getenv("OIDC_METADATA_URL")
CLIENT_ID = os.getenv("OIDC_CLIENT_ID")
AUDIENCE = os.getenv("OIDC_AUDIENCE") or CLIENT_ID
APP_SCOPES = os.getenv("OIDC_SCOPES", "openid profile")
JWKS_CACHE_TTL_SECONDS = int(os.getenv("OIDC_JWKS_CACHE_TTL_SECONDS", "3600"))

# AIRPY
AIRPY_STAGE_USERNAME = os.getenv("AIRPY_STAGE_USERNAME")
AIRPY_STAGE_PASSWORD = os.getenv("AIRPY_STAGE_PASSWORD")
