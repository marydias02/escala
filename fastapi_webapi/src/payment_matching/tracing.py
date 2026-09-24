"""Payment-matching tracing: stage names and span payloads.

The MLflow machinery itself (`span`, `setup_tracing`, redaction, ...) lives in
`utils.tracing_helper` and is shared. This module adds the vocabulary of THIS
pipeline and re-exports that machinery, so call sites import one module.

The span tree for one message:

    payment-email:<source>                  (CHAIN, the trace root)
      1-payment-email                       (LLM, body classification + extraction)
        ChatGoogleGenerativeAI              (from autolog)
      body-pdf                              (CHAIN, deterministic, no LLM)
      ingest:<attachment.pdf>               (CHAIN, one per attachment)
        2-segmentation                      (LLM, boundaries only)
      3-payment-note                        (LLM, multimodal, one per split PDF)
"""

from typing import Optional

from utils.tracing_helper import (
    MLFLOW_AVAILABLE,
    flush,
    is_enabled,
    set_span_attributes,
    set_trace_tags,
    span,
    traced,
)
from utils.tracing_helper import setup_tracing as _setup_tracing

EXPERIMENT_NAME = "payment_matching"

__all__ = [
    "EXPERIMENT_NAME",
    "MLFLOW_AVAILABLE",
    "STAGE_BODY_PDF",
    "STAGE_PAYMENT_EMAIL",
    "STAGE_PAYMENT_NOTE",
    "STAGE_SEGMENTATION",
    "flush",
    "is_enabled",
    "payment_email_summary",
    "payment_note_summary",
    "segmentation_summary",
    "set_span_attributes",
    "set_trace_tags",
    "setup_tracing",
    "span",
    "traced",
]


def setup_tracing(
    tracking_uri: Optional[str] = None,
    experiment_name: str = EXPERIMENT_NAME,
) -> bool:
    """Connect to MLflow under the payment-matching experiment."""
    return _setup_tracing(experiment_name, tracking_uri)


# --------------------------------------------------------------------------- #
# Stage names
# --------------------------------------------------------------------------- #
#
# Numbered so the UI's graph view shows the order of the pipeline rather than an
# unordered set of siblings.

STAGE_PAYMENT_EMAIL = "1-payment-email"
STAGE_SEGMENTATION = "2-segmentation"
STAGE_PAYMENT_NOTE = "3-payment-note"

# Off the numbered path: rendering the body to PDF happens only when the body
# carries note-grade information, so numbering it would imply a usual step.
STAGE_BODY_PDF = "body-pdf"


# --------------------------------------------------------------------------- #
# Span payloads
# --------------------------------------------------------------------------- #
#
# Autolog records the raw LLM exchange. These build the derived view worth
# reading back: what was extracted, with what confidence, and what the
# deterministic checks made of it.


def _field(confident) -> Optional[dict]:
    if confident is None:
        return None
    return {
        "value": confident.value,
        "confidence": confident.confidence,
        "evidence": getattr(confident, "evidence", None),
    }


def segmentation_summary(segmentation, problems: Optional[list] = None) -> dict:
    """A PaymentSegmentation as span output: the boundaries and their confidence.

    Paired with the coverage `problems`: a gap loses a document and an overlap
    duplicates one, so the boundaries are only meaningful next to the check run
    against them.
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


def payment_email_summary(info) -> dict:
    """A PaymentEmailInfo as span output: the classification and every field."""
    if info is None:
        return {"payment_email": None}

    summary: dict = {
        name: _field(getattr(info, name, None))
        for name in (
            "is_payment_related",
            "client_name",
            "total_amount_paid",
            "currency",
            "payment_reference",
            "payment_date",
        )
    }
    summary["invoice_numbers"] = [_field(number) for number in info.invoice_numbers]
    return summary


def payment_note_summary(note, problems: Optional[list] = None) -> dict:
    """A PaymentNoteDocument as span output: header, lines and what checked them.

    Paired with `problems` deliberately: the lines are only meaningful next to
    the sum-against-total check that ran on them.
    """
    if note is None:
        return {"payment_note": None}

    summary: dict = {
        name: _field(getattr(note, name, None))
        for name in (
            "is_payment_note",
            "payment_note_code",
            "client_name",
            "total_payment_note",
            "currency",
            "payment_date",
        )
    }
    summary["lines"] = [
        {
            "document_number": _field(line.document_number),
            "value_paid": _field(line.value_paid),
        }
        for line in note.lines
    ]
    summary["line_count"] = len(note.lines)
    summary["problems"] = problems or []
    return summary
