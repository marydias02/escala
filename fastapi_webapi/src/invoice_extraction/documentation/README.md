# Invoice Extraction — Module Overview

High-level orientation for the `invoice_extraction` module. For the detailed, stage-by-stage
description of the existing pipeline (thresholds, gating rules, routing matrix), see
[process.html](process.html).

## What this module does

The module turns supplier emails fetched live from Outlook (via Microsoft Graph) into routed,
structured accounting documents. It is organized as two pipelines composed by one orchestrator:

- **Ingestion** (`ingestion_pipeline.py`) — `LOAD → SEGMENT → SPLIT → PERSIST`
  Fetches emails from the inbox (`invoice_utils/outlook_loader.py`), uses an LLM to find document
  boundaries inside each PDF attachment (an attachment can contain several distinct accounting
  documents back to back), splits it into one PDF per document, and writes `email_content.json` +
  the split PDFs to `docs/processed_emails/<YYYYMMDD-HHMMSS>_<email subject>/` — the timestamp
  is the email's own reception date, so reprocessing one email always yields the same folder.
  That folder is working storage: the orchestrator uploads it to blob storage and then deletes
  it. Deterministic page-count validation checks the LLM's segmentation before it's trusted.
  Dedup happens once, upstream in `email_pipeline.main()`, keyed on `message_id` — the loader is
  told which messages to skip so it never re-downloads attachments for an email already in the
  database.

- **Extraction** (`extraction_pipeline.py`) — `CLASSIFY → GATE → EXTRACT → PARSE → VALIDATE`
  Runs on one already-split PDF at a time. Detects up front whether the PDF is a scan
  (`invoice_utils/page_mode.py`) — if so the LLM stages get rendered page images instead of the
  PDF, since a scan's text layer is the scanner's own OCR. Then it classifies the document
  type/state/number, decides (deterministically) whether it's worth extracting, pulls out the
  structured fields, and cross-checks them against a parsed-text baseline to produce a
  `ValidationReport` with a confidence score per field. Validation also resolves
  `supplier_id`/`bu_id` against the SAP master data (`dim_suppliers` / `dim_business_units`) —
  VAT-first, name-fallback — so routing can tell a genuine registry miss from a low-confidence
  read.

- **Orchestration** (`email_pipeline.py`) — ties the two together per email: ingest → extract
  each PDF the email produced → make one email-level routing decision (`decisions.py`, aware of
  thread position — see below) → upload the email's folder to Azure Blob Storage
  (`utils/blob_storage.py`) → persist `fct_processes` / `fct_documents` /
  `fct_document_first_action` rows to Postgres, then send the supplier reply / treasury forward /
  archive move those decisions call for, and finally close any earlier process on the same thread
  that this email settles. The local working folder is deleted once the blob holds it. Emails run
  concurrently, grouped by thread so members of one thread stay in order.

- **SAP booking** (`sap_pipeline.py`) — a separate, standalone pipeline: bulk-books every
  `fct_documents` row at `action = "Ingerir em SAP", status = "Criado"`, regardless of which
  email wrote it. Deliberately decoupled from `email_pipeline` because a document can only reach
  that state well after its email was processed — e.g. a `Validação Manual` document cleared by a
  human reviewer — so booking cannot be an inline step of the email run.

Business routing rules live entirely in `decisions.py`, kept deliberately separate from the
pipelines so they can be read and changed without touching extraction logic. Two action
vocabularies: each **document** gets exactly one `DocumentAction` (Ingest in SAP / Sent back to
Supplier / Forward to Treasury / Validate Manually / Keep in Inbox / Ignore — has original), while
an **email** can warrant several `EmailAction`s at once (Reply to supplier / Forward to treasury /
Keep in Inbox / Archive), rolled up from its documents' actions. Documents are matched against the
other originals in the same email by `(document_type, document_number)` so a duplicate/proforma is
filed away rather than acted on twice, and a document from a supplier whose `is_financial` flag
requires one is checked for a resolvable purchase order before being booked. Supplier replies are
written in Portuguese or English, chosen from `dim_suppliers.preferred_language` and falling back
to the language read off the document at classification. A separate lifecycle axis, `email_status`
(Aberto / Fechado / Requer Ação), tracks whether anyone still owes the email something — an email
whose thread has run `THREAD_ESCALATION_COUNT` messages deep without converging stops being chased
automatically and is flagged `Requer Ação` for a human instead. A third layer,
`close_prior_process`, looks backwards: a supplier answering on a thread is what an earlier
`Retornado ao Fornecedor` process was waiting for, so that process is closed rather than left
`Aberto` forever. See [process.html](process.html) for the full case matrix.

SAP booking is intentionally **not** part of `email_pipeline` — see `sap_pipeline.py` below.


## Missing (NEXT STEPS)

- Sending information to SAP - `sap_pipeline.py` still calls the `book_in_sap` stub; needs a real
  SAP integration, plus something to trigger the pipeline on a schedule (no cron/scheduler exists
  in this repo yet)
- Connect with webapp

## Repository structure

```
invoice_extraction/
├── config.py                   # Tunable constants: paths, limits, MIN_CONFIDENCE, parser/scan kwargs
├── decisions.py                # Routing rules — the business logic, THE place to change them
├── email_pipeline.py           # Orchestrator: ingest + extract + decide + upload + persist, per email
├── sap_pipeline.py             # Standalone: bulk-book every action=Ingerir em SAP, status=Criado row
├── ingestion_pipeline.py       # Phase 1: LOAD -> SEGMENT -> SPLIT -> PERSIST
├── extraction_pipeline.py      # Phase 2: CLASSIFY -> GATE -> EXTRACT -> PARSE -> VALIDATE
├── tracing.py                  # MLflow tracing setup (dev instrumentation, no-op if unset)
├── nodes/                      # One LLM call per pipeline stage (segment, classify, extract, validate, classify_email)
├── prompts/                    # Prompt templates for each node
├── models/                     # Pydantic schemas (InvoiceData, ValidationReport, EmailContent, ...)
├── invoice_utils/              # Graph loader, PDF splitting/parsing/OCR, scan detection, senders, reporting
├── tools/                      # LLM tools (VAT/PO registry lookups) bound during validation
├── eval/                       # MLflow GenAI evaluation: dataset, predict fn, per-field scorers
├── docs/                       # Sample/test data + eval_ground_truth.json; pipeline working folders
├── documentation/              # This folder
├── notebooks/                  # Exploratory notebooks
├── tests/                      # Unit tests (decisions.py routing cases, blob/lakehouse access checks)
└── output/                     # Batch run artifacts
```

Outside the module: `utils/blob_storage.py` (Azure Blob upload/download for processed emails),
`utils/utils_db.py` (Postgres helpers), `utils/llm_factory.py`, and `scripts/build_trace_viewer.py`.

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
uv sync (.\.venv\Scripts\Activate.ps1)
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns --port 5000
```

Then set `MLFLOW_TRACKING_URI=http://127.0.0.1:5000` in `.env`. With tracing off (unset URI), the
pipelines run unchanged — tracing is dev instrumentation only and never blocks a run.
This can later be set to LTPlabs URI (if intended to run acessible to multiple users)

`ENABLE_TRACING` (config.py) is a second, independent master switch: flip it off to run with zero
tracing overhead without touching the `.env` tracking URI.

## Running the evaluation

`eval/` scores the extraction against a hand-labelled ground truth
(`docs/eval_ground_truth.json`) using MLflow GenAI evaluation — one scorer per field, plus the
extraction gate itself. Unlike tracing, this needs a real tracking server: datasets require a
backend store, so an unset `MLFLOW_TRACKING_URI` is a hard error here.

```powershell
cd fastapi_webapi
.venv/Scripts/python.exe -m invoice_extraction.eval.create_dataset
.venv/Scripts/python.exe -m invoice_extraction.eval.run_evaluation
```

Each scored row also leaves a full span tree, so a failed field is one click from the prompt that
produced it.