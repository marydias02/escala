"""Tunable constants for the payment-matching pipelines."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).parent

# -- Paths -----------------------------------------------------------------

DOCS_DIR = BASE_DIR / "docs"

# Working folder per message: the body PDF and any payment-note PDFs, before upload.
PROCESSED_EMAILS_DIR = DOCS_DIR / "processed_emails"

MANIFEST_NAME = "email_content.json"

# -- Blob storage ----------------------------------------------------------

# Key prefix for payment artifacts, keeping them apart from `processed_emails/`.
BLOB_PREFIX = "payment_emails"

# Reserved name for the PDF rendered from an email body, so it cannot collide
# with an attachment's `NN_` prefix.
BODY_PDF_NAME = "_body.pdf"

# -- Mailbox sync ----------------------------------------------------------

SYNC_RUNS_TABLE = "email_sync_runs"
MESSAGES_TABLE = "payment_email_messages"

# `Prefer: odata.maxpagesize` on the delta call.
DELTA_PAGE_SIZE = 50

# A `failed` row is retried until it has been attempted this many times.
MAX_ATTEMPTS = 3

# How far back the very first delta call reaches, before any cursor exists.
INITIAL_SYNC_LOOKBACK = timedelta(minutes=10)

# pg_try_advisory_lock key. Distinct from the invoice cron's RUN_LOCK_KEY
# (3_141_592) and the lakehouse ETL's (2_718_281), so the jobs never block
# each other.
PAYMENT_RUN_LOCK_KEY = 1_618_033

# How many messages `--test` pulls from Graph per run.
DEFAULT_FETCH_LIMIT = 2

# At most N messages processed per run (None = every claimable row).
INGEST_LIMIT: int | None = 2

# How many messages run concurrently. Payment messages carry no thread-position
# state, so they need no per-thread serialization.
EMAIL_MAX_WORKERS = 7

# How many note candidates within one message are read concurrently.
NOTE_MAX_WORKERS = 3

# Persistence is not implemented — the payment tables have no migrations yet.
# See `email_pipeline._persist`. Off lets the pipeline run and trace with no
# database up, which is how `--test` is exercised.
WRITE_TO_DB = False

# -- Body-to-PDF gate ------------------------------------------------------

# A body shorter than this is a stub (signature, forwarded header) rather than a
# payment note, whatever else was extracted from it.
MIN_BODY_PDF_CHARS = 50

# -- Payment notes ---------------------------------------------------------

# How far the rows of one note may sum away from its stated total before the
# note is Blocked. Money is NUMERIC, so this covers the document's own rounding.
AMOUNT_TOLERANCE = Decimal("0.01")

# -- Status vocabularies ---------------------------------------------------

# `payment_email_messages.status`
MSG_PENDING = "pending"
MSG_PROCESSING = "processing"
MSG_PROCESSED = "processed"
MSG_FAILED = "failed"
MSG_GONE = "gone"
MSG_SKIPPED = "skipped"

# `email_sync_runs.status`
RUN_RUNNING = "running"
RUN_SUCCEEDED = "succeeded"
RUN_FAILED = "failed"
RUN_SKIPPED = "skipped"

# `email_payment_information.status`
INFO_EXTRACTED = "extracted"
INFO_NOT_PAYMENT = "not_payment"
INFO_PARTIAL = "partial"
INFO_FAILED = "failed"

# `payment_note.status`
NOTE_USABLE = "Usable"
NOTE_USED = "Used"
NOTE_BLOCKED = "Blocked"

# -- Tracing ---------------------------------------------------------------

ENABLE_TRACING = True
MLFLOW_EXPERIMENT = "payment_matching"
