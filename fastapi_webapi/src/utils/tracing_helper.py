"""MLflow tracing machinery, shared by every pipeline.

Tracing is DEVELOPMENT instrumentation: it answers "what did the model see, what
did it answer, how confident was it". The client-facing record stays in Postgres.

Everything here degrades to a no-op when MLflow is unavailable or
`MLFLOW_TRACKING_URI` is unset, so a pipeline runs unchanged without it: tracing
must never be the reason a message fails to process.

Local development needs no license and no company server:

    mlflow server --backend-store-uri sqlite:///mlflow.db \
                  --default-artifact-root ./mlruns --port 5000

then set MLFLOW_TRACKING_URI=http://127.0.0.1:5000 in `.env`.

Stage names and the span-payload summaries belong to each use case, in its own
`tracing` module — the vocabularies differ and should not be forced together.
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


# True once setup_tracing() has successfully connected. Every helper below checks
# this, so an un-configured process silently produces no traces.
_ENABLED = False


# --------------------------------------------------------------------------- #
# keep file bytes out of the trace store
# --------------------------------------------------------------------------- #

# Our prompts hand the model whole PDFs and rendered page images as base64
# data-URIs (see `page_mode.document_content_parts`) — up to ~1.6MB per call,
# sent twice per document. We never want that in the trace store: left alone,
# MLflow 3.14's autolog lifts it out of a structured `{"type": "file"}`/
# `{"type": "image_url"}` part into its own attachment file under
# `mlruns/.../artifacts/attachments/`, which is what made local trace storage
# balloon into the hundreds of MB.
#
# `_FILE_BYTES_KEYS` below clears the bytes at the source, before autolog gets
# to write anything. This regex is the fallback for what that does NOT cover:
# a data-URI pasted into a plain text field. 200+ chars so ordinary short
# strings and inline icons are left alone.
_DATA_URI = re.compile(r"data:[\w.+-]+/[\w.+-]+;base64,[A-Za-z0-9+/=]{200,}")


# The two message-part keys our prompts use to carry file bytes: `file_data`
# for a whole PDF, `url` for a rendered page image. Cleared unconditionally,
# and before MLflow's autolog runs.
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


def setup_tracing(experiment_name: str, tracking_uri: Optional[str] = None) -> bool:
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
    """Tag the ACTIVE trace, making it filterable in the UI and search_traces."""
    if not _ENABLED:
        return
    try:
        mlflow.update_current_trace(tags={k: str(v) for k, v in tags.items() if v is not None})
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  Could not tag trace: {type(exc).__name__}: {exc}")


def set_span_attributes(**attributes) -> None:
    """Attach attributes to the currently-open span; a no-op when tracing is off.

    For facts discovered by a helper that owns no span of its own — the
    attribute lands on the enclosing stage span instead.
    """
    if not _ENABLED:
        return
    try:
        active = mlflow.get_current_active_span()
        if active is not None:
            active.set_attributes({k: v for k, v in attributes.items() if v is not None})
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  Could not set span attributes: {type(exc).__name__}: {exc}")
