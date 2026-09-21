"""Tunable constants for the invoice extraction pipelines.

Paths and limits live here rather than being passed in at the call site, so both
pipelines read their configuration from one place. Application-wide settings
(credentials, model names) stay in `config.settings`.
"""

import math
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent

# -- Paths -----------------------------------------------------------------

DOCS_DIR = BASE_DIR / "docs"

# Phase 1 output / Phase 2 input: one folder per email, holding
# `email_content.json` plus one PDF per accounting document.
PROCESSED_EMAILS_DIR = DOCS_DIR / "processed_emails"

# -- Ingestion (Phase 1) ---------------------------------------------------

# Written last in each email folder, and therefore also the marker that the email
# was fully processed.
MANIFEST_NAME = "email_content.json"

# How many messages fetch_inbox_emails pulls from Graph per run (the `$top` on
# the message list request). `email_pipeline --test` only — the cron run pages a
# delta query instead and never uses this.
DEFAULT_FETCH_LIMIT = 1

# How much LLM work one run does: at most N emails are processed per run (None =
# every claimable row). Arrivals above it build a backlog in `email_messages`
# that drains on quieter runs; it is a throughput cap, not a fetch limit.
INGEST_LIMIT: int | None = 100

# Persist results to Postgres. Off lets the pipeline be exercised (and traced)
# with no database running, and keeps test runs out of fct_processes.
WRITE_TO_DB = True

# Actually send the supplier reply, treasury forward and archive move. Off logs
# what would have been sent, leaving the mailbox untouched.
EMAIL_ACTIONS = False

# Windows caps a full path at 260 characters by default. Email subjects in the
# sample set reach 111 characters, so folder names are truncated well short of it.
MAX_FOLDER_NAME = 80

# -- Inbox sync (cron path) ------------------------------------------------
# `email_pipeline.main` walks a Graph delta query over the inbox, records each
# addition in `email_messages`, then processes from that table. See the
# 20260918_01 migration.

# `Prefer: odata.maxpagesize` on the delta call. Metadata only (no body, no
# attachments), so a page is cheap and this is just how often the cursor commits.
DELTA_PAGE_SIZE = 50

# A `failed` row is retried until it has been attempted this many times.
MAX_ATTEMPTS = 3

# How far back the very first delta call reaches, before any cursor exists.
# Every message inside this window is queued, so keep it short.
INITIAL_SYNC_LOOKBACK = timedelta(minutes=10)

# Key for the `pg_try_advisory_lock` that keeps runs from overlapping. Arbitrary
# but fixed: a second run that cannot take it exits as `skipped`.
RUN_LOCK_KEY = 3_141_592

# -- Zip expansion limits --------------------------------------------------
# Attachments are untrusted input. These bound what a malicious archive can cost
# us, and are enforced against bytes actually decompressed rather than against the
# archive's own declared sizes.

MAX_ZIP_FILES = 30
MAX_ZIP_MEMBER_BYTES = 15 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 100 * 1024 * 1024
ZIP_CHUNK_SIZE = 64 * 1024

# -- Extraction (Phase 2) --------------------------------------------------

# How many documents within one email are extracted concurrently.
EXTRACTION_MAX_WORKERS = 3

# How many email threads run concurrently; multiplies with EXTRACTION_MAX_WORKERS.
EMAIL_MAX_WORKERS = 7

# Deterministic parser settings, matching the notebook.
PARSER_KWARGS = {
    "max_pages_text": 10,
    "min_good_chars_per_page": 200,
    "min_font_size": 4,
}

# -- Scanned documents (vision path) ---------------------------------------
# A scanned page is one large image XObject covering the sheet. It can contain text,
# often incorrect. If the scanned coverage is above a treshold, should be read as image

SCANNED_COVERAGE_THRESHOLD = 1.0

# A scanned bundle can open with a clean cover sheet, so look past page 1.
COVERAGE_SCAN_PAGES = 5

# 72 DPI already reads correctly on the known scans; 110 is margin for finer print.
RENDER_DPI = 110

# Caps the number of pages sent as images (usually info is at start)
RENDER_MAX_PAGES = 5

# -- Validation / decisions -------------------------------------------------

# 0.7 keeps only the upper half of the validator's own "0.70-0.89 = probably
# correct but some ambiguity" band. Money-moving data, so ambiguity goes to a
# human.
MIN_CONFIDENCE = 0.7


def failed_confidence(min_confidence: float = MIN_CONFIDENCE) -> float:
    """The confidence to stamp on a field a deterministic check has failed.
    Always the nearest 0.05 below the minimum confidence"""
    return round(math.floor((min_confidence - 1e-12) / 0.05) * 0.05, 2)


# A thread on its Nth message has not converged: the earlier exchanges did not
# land, so a human reads it rather than the supplier being chased again.
THREAD_ESCALATION_COUNT = 3

# -- Document status vocabulary --------------------------------------------
# What reaches `fct_documents.status`. Written by `email_pipeline`, advanced by
# `sap_pipeline`, read back by `invoice_utils.persist_db`.

DOC_STATUS_CREATED = "Criado"  # routed, nothing carried out yet
DOC_STATUS_BOOKED = "Ingerido"  # booked into SAP
DOC_STATUS_COMMUNICATED = "Comunicado"  # reply/forward sent
DOC_STATUS_IGNORED = "Ignorado"  # nothing was ever owed
DOC_STATUS_FAILED = "Failed"  # pipeline broke on it

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
