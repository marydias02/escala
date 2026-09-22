"""Run one document through the pipeline and flatten the result for scoring.

MLflow calls `predict_fn(**inputs)`, so the parameter name here must match the
`inputs` key written by `create_dataset` — both are `pdf_path`.

The dataset carries a path, not the PDF itself: records must be JSON, and a
document is far too large to live in the tracking store (the same reason
`tracing` strips base64 out of spans).
"""

from typing import Any

from invoice_extraction.config import DOCS_DIR
from invoice_extraction.extraction_pipeline import create_pipeline, should_extract

# One pipeline (and one chat model) reused across every record in the run.
_pipeline = create_pipeline()

# Ground-truth key -> ValidationReport attribute. The report calls the client
# fields `bu_*`, so the labels are mapped rather than read straight off.
_VALIDATED_FIELDS = {
    "supplier_vat": "supplier_vat",
    "client_vat": "bu_vat",
    "issue_date": "issue_date",
    "base_amount": "base_amount",
    "vat_amount": "vat_amount",
    "total_amount": "total_amount",
    "currency": "currency",
}


def _value(confident) -> Any | None:
    """Unwrap a Confident/Checked field to its bare value."""
    return None if confident is None else confident.value


def predict_extraction(pdf_path: str) -> dict:
    """The pipeline as MLflow sees it: a path in, a flat dict of values out.

    Scores come from `ValidationReport` rather than `InvoiceData` because that
    is the pipeline's final answer — the value a correction would have fixed.
    """
    result = _pipeline.run(DOCS_DIR / pdf_path)

    flat: dict[str, Any] = {
        "status": result.status,
        "should_extract": False,
        "document_type": None,
        "document_state": None,
        "document_number": None,
        "document_exception": None,
    }

    if result.classification is not None:
        flat["should_extract"] = should_extract(result.classification)
        flat["document_type"] = _value(result.classification.document_type)
        flat["document_state"] = _value(result.classification.document_state)
        flat["document_number"] = _value(result.classification.document_number)
        flat["document_exception"] = _value(result.classification.document_exception)

    if result.validation is not None:
        for label, attribute in _VALIDATED_FIELDS.items():
            flat[label] = _value(getattr(result.validation, attribute, None))
        flat["purchase_order"] = [po.value for po in result.validation.po_list]

    return flat
