# Invoice Extraction — Module Overview

High-level orientation for the `invoice_extraction` module. For the detailed, stage-by-stage
description of the existing pipeline (thresholds, gating rules, routing matrix), see
[process.html](process.html).

## What this module does

The module turns raw supplier emails (`.msg`) into routed, structured accounting documents.
It is organized as two pipelines composed by one orchestrator:

- **Ingestion** (`ingestion_pipeline.py`) — `LOAD → SEGMENT → SPLIT → PERSIST`
  Parses one `.msg` file, uses an LLM to find document boundaries inside each PDF attachment
  (an attachment can contain several distinct accounting documents back to back), splits it into
  one PDF per document, and writes `email_content.json` + the split PDFs to
  `docs/processed_emails/<email subject>/`. Deterministic page-count validation checks the
  LLM's segmentation before it's trusted.

- **Extraction** (`extraction_pipeline.py`) — `CLASSIFY → EXTRACT → VALIDATE`
  Runs on one already-split PDF at a time. Classifies the document type/state/number, decides
  (deterministically) whether it's worth extracting, pulls out the structured fields, and
  cross-checks them against a parsed-text baseline to produce a `ValidationReport` with a
  confidence score per field.

- **Orchestration** (`email_pipeline.py`) — ties the two together per email: ingest → extract
  each PDF the email produced → make one email-level routing decision
  (`decisions.py`) → persist `fct_processes` / `fct_documents` rows to Postgres.

Business routing rules live entirely in `decisions.py`, kept deliberately separate from the
pipelines so they can be read and changed without touching extraction logic. Two action
vocabularies: each **document** gets exactly one `DocumentAction` (Ingest in SAP / Sent back to
Supplier / Forward to Treasury / Validate Manually / Keep in Inbox / Ignore — has original), while
an **email** can warrant several `EmailAction`s at once (Reply to supplier / Forward to treasury /
Keep in Inbox / Archive), rolled up from its documents' actions. Documents are matched against the
other originals in the same email by `(document_type, document_number)` so a duplicate/proforma is
filed away rather than acted on twice, and a document from a PO-required supplier is checked for a
resolvable purchase order before being booked. See [process.html](process.html) for the full case
matrix.


## Missing (NEXT STEPS)

- True email ingestion - connect to outlook inbox instead of reading from folder
- Saving intermediate emails after ingestion in client folder
- Sending information to SAP - end process
- Connect with webapp

## Repository structure

```
invoice_extraction/
├── config.py                  # Tunable constants: paths, limits, MIN_CONFIDENCE, parser kwargs
├── decisions.py                # Routing rules — the business logic, THE place to change them
├── email_pipeline.py           # Orchestrator: ingest + extract + decide + persist, per email
├── ingestion_pipeline.py       # Phase 1: LOAD -> SEGMENT -> SPLIT -> PERSIST
├── extraction_pipeline.py      # Phase 2: CLASSIFY -> EXTRACT -> VALIDATE
├── tracing.py                  # MLflow tracing setup (dev instrumentation, no-op if unset)
├── loading/                    # .msg parsing (Outlook loader)
├── nodes/                      # One LLM call per pipeline stage (segment, classify, extract, validate, classify_email)
├── prompts/                    # Prompt templates for each node
├── models/                     # Pydantic schemas (InvoiceData, ValidationReport, EmailContent, ...)
├── invoice_utils/               # PDF splitting/parsing helpers, reporting
├── tools/                      # LLM tools (VAT/PO registry lookups) bound during validation
├── docs/                       # Sample/test data — original emails, processed output, split PDFs
├── documentation/              # This folder
├── notebooks/                  # Exploratory notebooks
└── output/                     # Batch run artifacts
```

## Running the trace viewer

Traces are captured in MLflow during pipeline runs (see [Running MLflow](#running-mlflow-locally)
below). `scripts/build_trace_viewer.py` reads the MLflow SQLite backend plus the source PDFs on
disk and builds a single self-contained `trace_viewer.html` — no server, shareable by email or
USB stick. It relabels stages into business language and strips confidence scores, token costs,
evidence strings and raw prompts by default (`--include-internals` restores them for internal
review).

```powershell
cd fastapi_webapi
.venv/Scripts/python.exe scripts/build_trace_viewer.py
```

Output defaults to `fastapi_webapi/trace_viewer.html`; use `--out <path>` to change it.

## Running MLflow locally

Pipeline runs export traces to MLflow if `MLFLOW_TRACKING_URI` is set (in `.env`). To run a local
MLflow server backed by SQLite:

```powershell
cd .\fastapi_webapi\
uv sync
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns --port 5000
```

Then set `MLFLOW_TRACKING_URI=http://127.0.0.1:5000` in `.env`. With tracing off (unset URI), the
pipelines run unchanged — tracing is dev instrumentation only and never blocks a run.
This can later be set to LTPlabs URI (if intended to run acessible to multiple users)