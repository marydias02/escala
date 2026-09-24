"""Invoice-extraction tracing: stage names and span payloads.

The MLflow machinery itself (`span`, `setup_tracing`, redaction, ...) lives in
`utils.tracing_helper` and is shared. This module adds the vocabulary of THIS
pipeline and re-exports that machinery, so call sites import one module.

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

EXPERIMENT_NAME = "invoice_extraction"

__all__ = [
    "EXPERIMENT_NAME",
    "MLFLOW_AVAILABLE",
    "STAGE_CHUNKING",
    "STAGE_CLASSIFICATION",
    "STAGE_DECISION",
    "STAGE_EMAIL_INTENT",
    "STAGE_EXTRACTION",
    "STAGE_PARSING",
    "STAGE_VALIDATION",
    "STAGE_VALIDATION_REGISTRY",
    "STAGE_VALIDATION_SHAPING",
    "STAGE_VALIDATION_SWAP",
    "STAGE_VALIDATION_TOOLS",
    "classification_summary",
    "decision_summary",
    "flush",
    "invoice_data_summary",
    "is_enabled",
    "segmentation_summary",
    "set_span_attributes",
    "set_trace_tags",
    "setup_tracing",
    "span",
    "traced",
    "validation_summary",
]


def setup_tracing(
    tracking_uri: Optional[str] = None,
    experiment_name: str = EXPERIMENT_NAME,
) -> bool:
    """Connect to MLflow under the invoice-extraction experiment."""
    return _setup_tracing(experiment_name, tracking_uri)


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
