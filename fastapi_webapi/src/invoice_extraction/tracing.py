"""MLflow tracing for the email ingestion + extraction pipelines.

Tracing is DEVELOPMENT instrumentation: it answers "what did the model see, what
did it answer, how confident was it, and why did the email get routed the way it
did". The client-facing record of a processed email stays in Postgres
(`fct_processes` / `fct_documents`) — nothing here is meant to be shown to a
customer.

Everything in this module degrades to a no-op when MLflow is unavailable or
`MLFLOW_TRACKING_URI` is unset, so the pipelines run unchanged without it. That
is deliberate: tracing must never be the reason an email fails to process.

Local development needs no license and no company server:

    mlflow server --backend-store-uri sqlite:///mlflow.db \
                  --default-artifact-root ./mlruns --port 5000

then set MLFLOW_TRACKING_URI=http://127.0.0.1:5000 in `.env`. Moving to the
company server later is a change of that one variable plus the two auth ones.

The span tree for one email:

    email:<source>                          (CHAIN, the trace root)
      ingest:<attachment.pdf>               (CHAIN, one per attachment)
        1-chunking                          (LLM)
          ChatOpenAI                        (from autolog)
      extract:<document.pdf>                (CHAIN, one per split document)
        2-classification                    (LLM)
        3-parsing                           (PARSER, deterministic, no LLM)
        4-extraction                        (LLM)
        5-validation                        (LLM)
          5a-validation:tools               (CHAIN, the bind_tools loop)
            verify_client_nif               (TOOL)
            verify_supplier_nif             (TOOL)
          5b-validation:shaping             (LLM)
          5c-validation:swap                (CHAIN, deterministic, no LLM)
          5d-validation:registry            (CHAIN, deterministic, no LLM)
      6-decision                            (CHAIN, pure business rules)

The numbered STAGE_* spans exist because `mlflow.langchain.autolog()` names its
spans after the LangChain class it intercepted (`ChatOpenAI`,
`RunnableSequence`, ...), never after the pipeline step. Those names cannot be
changed — `LiveSpan.name` has no setter — and a span processor can only mutate a
span, not drop it. So the readable graph is built by wrapping each stage in a
span of our own: the plumbing still appears, but underneath a meaningful parent.
Distinct names also stop the UI from collapsing every LLM call in the email into
one badged node.
"""

import functools
import os
import re
from typing import Callable, Optional

# MLflow is an optional dependency: import failure disables tracing rather than
# breaking the pipeline.
try:
    import mlflow
    from mlflow.entities import SpanType

    MLFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when mlflow is absent
    mlflow = None
    SpanType = None
    MLFLOW_AVAILABLE = False


EXPERIMENT_NAME = "invoice_extraction"

# --------------------------------------------------------------------------- #
# Stage names — the pipeline's data flow, as it should read in the graph.
# --------------------------------------------------------------------------- #
#
# Numbered so the UI's graph view shows the order of the pipeline rather than an
# unordered set of siblings. Defined here (not at each call site) so the sequence
# can be read in one place and cannot drift out of order.

STAGE_CHUNKING = "1-chunking"
STAGE_CLASSIFICATION = "2-classification"
STAGE_PARSING = "3-parsing"
STAGE_EXTRACTION = "4-extraction"
STAGE_VALIDATION = "5-validation"
STAGE_VALIDATION_TOOLS = "5a-validation:tools"
STAGE_VALIDATION_SHAPING = "5b-validation:shaping"
STAGE_VALIDATION_SWAP = "5c-validation:swap"
STAGE_VALIDATION_REGISTRY = "5d-validation:registry"
STAGE_DECISION = "6-decision"

# Off the numbered path on purpose: the body classifier runs only on the
# no-usable-PDF branch, so numbering it would imply a step that usually is absent.
STAGE_EMAIL_INTENT = "email-intent"

# True once setup_tracing() has successfully connected. Every helper below checks
# this, so an un-configured process silently produces no traces.
_ENABLED = False


# --------------------------------------------------------------------------- #
# keep file bytes out of the trace store
# --------------------------------------------------------------------------- #

# Our prompts hand the model whole PDFs and rendered page images as base64
# data-URIs (see `page_mode.document_content_parts` and
# `prompts.segmentation`) — up to ~1.6MB per call, sent twice per document.
# We never want that in the trace store: left alone, MLflow 3.14's autolog
# lifts it out of a structured `{"type": "file"}`/`{"type": "image_url"}` part
# into its own attachment file under `mlruns/.../artifacts/attachments/`,
# which is what made local trace storage balloon into the hundreds of MB.
#
# `_FILE_BYTES_KEYS` below clears the bytes at the source, before autolog gets
# to write anything. This regex is the fallback for what that does NOT cover:
# a data-URI pasted into a plain text field. 200+ chars so ordinary short
# strings and inline icons are left alone.
_DATA_URI = re.compile(r"data:[\w.+-]+/[\w.+-]+;base64,[A-Za-z0-9+/=]{200,}")


# The two message-part keys our prompts use to carry file bytes (see
# `page_mode.document_content_parts` and `prompts.segmentation`): `file_data`
# for a whole PDF, `url` for a rendered page image. Cleared unconditionally —
# we never want these bytes in the trace store — and before MLflow's autolog
# runs, since that is the step that would otherwise lift them out into a
# standalone attachment file under `mlruns/.../artifacts/attachments/`.
_FILE_BYTES_KEYS = {"file_data", "url"}


def _redact(obj, parent_key: Optional[str] = None):
    """Recursively strip file bytes and inline base64 data-URIs from a span payload.

    Walks lists as well as dicts: a chat-model span's `inputs` is a *list* of
    message dicts, not a dict, so a `.items()`-only walk would miss it entirely.
    """
    if isinstance(obj, str):
        if parent_key in _FILE_BYTES_KEYS:
            return None
        return _DATA_URI.sub(lambda m: f"<base64 stripped ({len(m.group(0))} chars)>", obj)
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _redact(value, parent_key=key) for key, value in obj.items()}
    return obj


def _strip_base64(span) -> None:
    """Span processor: keep raw PDF bytes out of the trace store."""
    inputs = span.inputs
    if inputs is not None:
        redacted = _redact(inputs)
        if redacted != inputs:
            span.set_inputs(redacted)

    outputs = span.outputs
    if outputs is not None:
        redacted = _redact(outputs)
        if redacted != outputs:
            span.set_outputs(redacted)


# --------------------------------------------------------------------------- #
# setup
# --------------------------------------------------------------------------- #


def setup_tracing(
    tracking_uri: Optional[str] = None,
    experiment_name: str = EXPERIMENT_NAME,
) -> bool:
    """Connect to MLflow and turn tracing on. Returns whether it is enabled.

    Resolves the URI from `settings` (i.e. `.env`) and then the environment. An
    unset URI means "tracing off" rather than "log to ./mlruns", because a silent
    local write is a worse default than doing nothing.

    Safe to call more than once; a connection failure is reported and swallowed.
    """
    global _ENABLED

    if not MLFLOW_AVAILABLE:
        print("ℹ️  mlflow not installed — tracing disabled")
        return False

    if not tracking_uri:
        # `.env` is loaded into Settings rather than into os.environ, so settings
        # comes first; the env var still works for a one-off override.
        try:
            from config.settings import settings

            tracking_uri = settings.MLFLOW_TRACKING_URI
        except Exception:  # noqa: BLE001 - settings must not be able to break tracing
            tracking_uri = None
        tracking_uri = tracking_uri or os.environ.get("MLFLOW_TRACKING_URI")

    if not tracking_uri:
        print("ℹ️  MLFLOW_TRACKING_URI not set — tracing disabled")
        return False

    try:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)

        # Order matters: register the processor before autolog starts producing
        # spans, so no un-redacted span can be exported.
        mlflow.tracing.configure(span_processors=[_strip_base64])

        # Our LLM calls all go through langchain's ChatOpenAI
        # (`utils.llm_factory`), so this — not litellm.autolog() — is what
        # produces the LLM spans, with prompts, responses and token usage.
        mlflow.langchain.autolog()
    except Exception as exc:  # noqa: BLE001 - tracing must never break the pipeline
        print(f"⚠️  MLflow tracing unavailable ({type(exc).__name__}: {exc}) — continuing without it")
        return False

    _ENABLED = True
    print(f"📊 Tracing → {tracking_uri} (experiment: {experiment_name})")
    return True


def is_enabled() -> bool:
    """Whether tracing is active. Cheap enough to call per span."""
    return _ENABLED


def flush() -> None:
    """Wait for queued traces to reach the server.

    Trace export is asynchronous, so a short-lived script can exit with traces
    still in the queue. Call this before the process ends.
    """
    if not _ENABLED:
        return
    try:
        mlflow.flush_trace_async_logging()
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  Could not flush traces: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------- #
# span helpers
# --------------------------------------------------------------------------- #


class _NullSpan:
    """Stand-in span used when tracing is off, so call sites need no branching."""

    def set_inputs(self, *args, **kwargs) -> None: ...
    def set_outputs(self, *args, **kwargs) -> None: ...
    def set_attribute(self, *args, **kwargs) -> None: ...
    def set_attributes(self, *args, **kwargs) -> None: ...
    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


def span(name: str, span_type: str = "CHAIN", **attributes):
    """Context manager for one span; a no-op when tracing is off.

        with span("extract:invoice.pdf", "CHAIN") as s:
            s.set_outputs({"status": "validated"})
    """
    if not _ENABLED:
        return _NullSpan()

    try:
        return mlflow.start_span(
            name=name,
            span_type=getattr(SpanType, span_type, span_type),
            attributes=attributes or None,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  Could not open span {name!r}: {type(exc).__name__}: {exc}")
        return _NullSpan()


def traced(name: Optional[str] = None, span_type: str = "CHAIN") -> Callable:
    """Decorator wrapping a function in a span. No-op when tracing is off.

    Used for functions whose default input/output capture is already useful.
    Where the interesting values are computed inside (a decision, a confidence),
    prefer the `span()` context manager and set the outputs explicitly.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not _ENABLED:
                return func(*args, **kwargs)
            traced_func = mlflow.trace(
                func,
                name=name or func.__name__,
                span_type=getattr(SpanType, span_type, span_type),
            )
            return traced_func(*args, **kwargs)

        return wrapper

    return decorator


def set_trace_tags(**tags) -> None:
    """Tag the ACTIVE trace, making it filterable in the UI and search_traces.

    Tagging the email trace with its decision is what turns "show me every email
    that went to Validate Manually" into a one-line filter.
    """
    if not _ENABLED:
        return
    try:
        mlflow.update_current_trace(tags={k: str(v) for k, v in tags.items() if v is not None})
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  Could not tag trace: {type(exc).__name__}: {exc}")


def set_span_attributes(**attributes) -> None:
    """Attach attributes to the currently-open span; a no-op when tracing is off.

    For facts discovered by a helper that owns no span of its own — the
    attribute lands on the enclosing STAGE_* span instead.
    """
    if not _ENABLED:
        return
    try:
        active = mlflow.get_current_active_span()
        if active is not None:
            active.set_attributes({k: v for k, v in attributes.items() if v is not None})
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  Could not set span attributes: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------- #
# Span payloads — what we actually want to read back
# --------------------------------------------------------------------------- #
#
# Autolog records the raw LLM exchange. These build the DERIVED view that makes a
# trace worth opening: per-field confidences, what blocked ingestion, and the
# routing decision with its reply text.


def segmentation_summary(segmentation, problems: Optional[list] = None) -> dict:
    """A DocumentSegmentation as span output: the boundaries and their confidence.

    Paired with the coverage `problems` deliberately: a gap loses a document and
    an overlap duplicates one, so the boundaries are only meaningful next to the
    check that was run against them.
    """
    if segmentation is None:
        return {"segmentation": None}

    return {
        "documents": [
            {
                "start_page": boundary.start_page,
                "end_page": boundary.end_page,
                "confidence": boundary.confidence,
            }
            for boundary in segmentation.documents
        ],
        "count": len(segmentation.documents),
        "problems": problems or [],
    }


def invoice_data_summary(invoice) -> dict:
    """An InvoiceData as span output: raw extracted values, before validation.

    Kept next to `validation_summary` in the trace so the two can be compared —
    that pair is what shows whether the validator corrected something (a
    supplier/client swap, a misread total) or simply passed the extraction
    through.
    """
    if invoice is None:
        return {"invoice_data": None}

    def field(confident) -> Optional[dict]:
        if confident is None:
            return None
        return {
            "value": confident.value,
            "confidence": confident.confidence,
            "evidence": confident.evidence,
        }

    summary: dict = {
        name: field(getattr(invoice, name, None))
        for name in (
            "supplier_name",
            "supplier_vat",
            "client_name",
            "client_vat",
            "issue_date",
            "base_amount",
            "vat_amount",
            "total_amount",
            "currency",
        )
    }
    summary["purchase_order"] = [field(po) for po in invoice.purchase_order]
    return summary


def classification_summary(classification) -> dict:
    """A DocumentClassification as span output: value, confidence and evidence.

    Every field is a `Confident[...]`, so each carries the verbatim snippet the
    model based itself on — the fastest way to tell a genuine "DUPLICADO" stamp
    from a hallucinated one.

    `document_number` is here rather than in `invoice_data_summary` because it is
    read at classification: the routing rules match duplicates against their
    originals on it, and a proforma never reaches extraction. When a duplicate
    was NOT suppressed, this field and its evidence are where to look first.
    """
    if classification is None:
        return {"classification": None}

    def field(confident) -> Optional[dict]:
        if confident is None:
            return None
        return {
            "value": confident.value,
            "confidence": confident.confidence,
            "evidence": confident.evidence,
        }

    return {
        "document_type": field(classification.document_type),
        "document_state": field(classification.document_state),
        "document_number": field(classification.document_number),
        "document_exception": field(classification.document_exception),
        "language": field(classification.language),
    }


def validation_summary(validation) -> dict:
    """A ValidationReport as span output: every field's value + confidence.

    This is the highest-value thing in the whole trace during development — it is
    what tells you whether a bad routing decision came from a bad extraction or
    from the rules on top of it. `min_confidence` surfaces the weakest field
    without having to scan them all.
    """
    if validation is None:
        return {"validation": None}

    summary: dict = {}
    confidences: list[float] = []

    for name in (
        "supplier_name",
        "supplier_id",
        "supplier_vat",
        "document_number",
        "bu_name",
        "bu_id",
        "bu_vat",
        "issue_date",
        "base_amount",
        "vat_amount",
        "total_amount",
        "currency",
    ):
        checked = getattr(validation, name, None)
        if checked is None:
            summary[name] = None
            continue
        summary[name] = {"value": checked.value, "confidence": checked.confidence}
        confidences.append(checked.confidence)

    summary["po_list"] = [
        {"value": po.value, "confidence": po.confidence} for po in validation.po_list
    ]
    summary["min_confidence"] = min(confidences) if confidences else None
    summary["notes"] = getattr(validation, "notes", None)
    return summary


def decision_summary(decision) -> dict:
    """An EmailDecision as span output: the action, the reply, the per-doc detail.

    Mirrors what `print_email_summary` prints to the console, in a form that
    survives in the trace and can be filtered on later.
    """
    if decision is None:
        return {"decision": None}

    return {
        "actions": list(decision.actions),
        "email_status": decision.status,
        "reason": decision.reason,
        "reply_lines": decision.reply_lines,
        "reply_language": decision.language,
        "should_reply": decision.should_reply,
        "should_forward_to_treasury": decision.should_forward_to_treasury,
        "intent": (
            {
                "is_invoice_delivery": decision.intent.is_invoice_delivery.value,
                "has_invoice_link": decision.intent.has_invoice_link.value,
            }
            if decision.intent is not None
            else None
        ),
        "documents": [
            {
                "filename": document.filename,
                "action": document.action,
                "reason": document.reason,
                "reply_text": document.reply_text,
            }
            for document in decision.documents
        ],
    }
