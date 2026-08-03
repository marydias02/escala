"""Tunable constants for the invoice extraction pipelines.

Paths and limits live here rather than being passed in at the call site, so both
pipelines read their configuration from one place. Application-wide settings
(credentials, model names) stay in `config.settings`.
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent

# -- Paths -----------------------------------------------------------------

DOCS_DIR = BASE_DIR / "docs"

# Phase 1 input: raw emails, as if a fetch step had just deposited them.
ORIGINAL_EMAILS_DIR = DOCS_DIR / "original_emails"

# Phase 1 output / Phase 2 input: one folder per email, holding
# `email_content.json` plus one PDF per accounting document.
PROCESSED_EMAILS_DIR = DOCS_DIR / "processed_emails"

# -- Ingestion (Phase 1) ---------------------------------------------------

# Written last in each email folder, and therefore also the marker that the email
# was fully processed.
MANIFEST_NAME = "email_content.json"

# Re-ingest emails whose manifest already exists. Off by default so re-runs cost
# no LLM calls.
FORCE_REINGEST = True

# Only ingest the first N emails (None = all). Useful for a cheap smoke test.
INGEST_LIMIT: int | None = 1

# Persist results to Postgres. Off lets the pipeline be exercised (and traced)
# with no database running, and keeps test runs out of fct_processes — note that
# FORCE_REINGEST bypasses the DB dedup check, so with both on, every re-run would
# otherwise insert another process row for the same email.
WRITE_TO_DB = True

# Windows caps a full path at 260 characters by default. Email subjects in the
# sample set reach 111 characters, so folder names are truncated well short of it.
MAX_FOLDER_NAME = 80

# -- Zip expansion limits --------------------------------------------------
# Attachments are untrusted input. These bound what a malicious archive can cost
# us, and are enforced against bytes actually decompressed rather than against the
# archive's own declared sizes.

MAX_ZIP_FILES = 30
MAX_ZIP_MEMBER_BYTES = 15 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 100 * 1024 * 1024
ZIP_CHUNK_SIZE = 64 * 1024

# -- Extraction (Phase 2) --------------------------------------------------

# Deterministic parser settings, matching the notebook.
PARSER_KWARGS = {
    "max_pages_text": 10,
    "max_pages_vision": 4,
    "dpi": 100,
    "min_good_chars_per_page": 200,
    "min_font_size": 5,
}

# -- Validation / decisions -------------------------------------------------

# 0.7 keeps only the upper half of the validator's own "0.70-0.89 = probably
# correct but some ambiguity" band. Money-moving data, so ambiguity goes to a
# human.
MIN_CONFIDENCE = 0.7

# -- Tracing (MLflow) ------------------------------------------------------
# Development instrumentation only; see `invoice_extraction.tracing`. The
# tracking URI itself is read from the MLFLOW_TRACKING_URI environment variable
# (unset = tracing off), so pointing at a local server or at the company one is
# an .env change rather than a code change.

# Master switch, independent of MLFLOW_TRACKING_URI: flip off to run the
# pipeline with zero tracing overhead (e.g. a large batch) without touching
# the .env tracking URI.
ENABLE_TRACING = True

MLFLOW_EXPERIMENT = "invoice_extraction"