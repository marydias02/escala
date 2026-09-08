"""Tunable constants for the invoice extraction pipelines.

Paths and limits live here rather than being passed in at the call site, so both
pipelines read their configuration from one place. Application-wide settings
(credentials, model names) stay in `config.settings`.
"""

import math
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
# the message list request).
DEFAULT_FETCH_LIMIT = 1

# Of the emails fetched, only run the first N through the pipeline (None = all
# of them). A testing knob, independent of DEFAULT_FETCH_LIMIT
INGEST_LIMIT: int | None = 1

# Persist results to Postgres. Off lets the pipeline be exercised (and traced)
# with no database running, and keeps test runs out of fct_processes.
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

# How many documents within one email are extracted concurrently.
EXTRACTION_MAX_WORKERS = 3

# Deterministic parser settings, matching the notebook.
PARSER_KWARGS = {
    "max_pages_text": 10,
    "min_good_chars_per_page": 200,
    "min_font_size": 4,
}

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
