import sys
from typing import Any, Optional

from invoice_extraction.models import DocumentClassification, InvoiceData, ValidationReport

# Windows consoles default to cp1252, which cannot encode the status emoji. Fall
# back to ASCII markers there rather than crashing the whole report.
_SUPPORTS_UNICODE = (getattr(sys.stdout, "encoding", "") or "").lower().startswith("utf")

_ICONS = {
    "doc": "📄" if _SUPPORTS_UNICODE else "[doc]",
    "high": "🟢" if _SUPPORTS_UNICODE else "[++]",
    "mid": "🟡" if _SUPPORTS_UNICODE else "[+ ]",
    "low": "🔴" if _SUPPORTS_UNICODE else "[! ]",
    "none": "⚪" if _SUPPORTS_UNICODE else "[  ]",
    "skip": "⏭️" if _SUPPORTS_UNICODE else "[skip]",
}


def _confidence_icon(confidence: float | None) -> str:
    if confidence is None:
        return _ICONS["none"]
    if confidence >= 0.9:
        return _ICONS["high"]
    if confidence >= 0.7:
        return _ICONS["mid"]
    return _ICONS["low"]


def _print_field(label: str, field: Any) -> None:
    """
    Pretty-print one Confident[T] / Checked[T] field.

    Expected shape:
        field.value
        field.confidence
        field.evidence  (optional — Checked has none)
    """
    if field is None:
        print(f"{label:<15} {'-':<35}")
        return

    value = str(field.value) if field.value is not None else "-"
    confidence = getattr(field, "confidence", None)

    if confidence is None:
        print(f"{label:<15}{value:<40}")
    else:
        print(f"{label:<15}{value:<40}{_confidence_icon(confidence)} {confidence:.2f}")

    evidence = getattr(field, "evidence", None)
    if evidence:
        print(f"{'':15}evidence: {evidence}")


def _print_list_field(label: str, fields: list) -> None:
    """Print a list of Confident/Checked values (purchase orders)."""
    if not fields:
        print(f"{label:<15} {'-':<35}")
        return
    for i, field in enumerate(fields):
        _print_field(label if i == 0 else "", field)


def print_classification_result(filename: str, classification: DocumentClassification) -> None:
    print("=" * 80)
    print(f"{_ICONS['doc']} {filename}")
    print("=" * 80)

    print("\nClassification")
    print("-" * 14)
    _print_field("Type", classification.document_type)
    _print_field("State", classification.document_state)


def print_extraction_result(
    filename: str,
    classification: DocumentClassification,
    invoice: Optional[InvoiceData],
) -> None:
    print("=" * 80)
    print(f"{_ICONS['doc']} {filename}")
    print("=" * 80)

    if invoice is None:
        state = (
            classification.document_state.value
            if classification.document_state is not None
            else "no state"
        )
        print(
            f"\n{_ICONS['skip']}  No extraction - classified as "
            f"{classification.document_type.value} / {state}."
        )
        return

    print("\nParties")
    print("-" * 7)
    _print_field("Supplier", invoice.supplier_name)
    _print_field("Supplier VAT", invoice.supplier_vat)
    _print_field("Document number", invoice.document_number)
    _print_field("Client", invoice.client_name)
    _print_field("Client VAT", invoice.client_vat)

    print("\nAmounts")
    print("-" * 7)
    _print_field("Issue date", invoice.issue_date)
    _print_field("Base", invoice.base_amount)
    _print_field("VAT", invoice.vat_amount)
    _print_field("Total", invoice.total_amount)
    _print_field("Currency", invoice.currency)
    _print_list_field("PO", invoice.purchase_order)


def print_validation_result(filename: str, validation: Optional[ValidationReport]) -> None:
    print("=" * 80)
    print(f"{_ICONS['doc']} {filename}")
    print("=" * 80)

    if validation is None:
        print(f"\n{_ICONS['skip']}  No validation.")
        return

    print("\nValidated parties")
    print("-" * 17)
    _print_field("Supplier", validation.supplier_name)
    _print_field("Supplier ID", validation.supplier_id)
    _print_field("Supplier VAT", validation.supplier_vat)
    _print_field("Document number", validation.document_number)
    _print_field("BU", validation.bu_name)
    _print_field("BU ID", validation.bu_id)
    _print_field("BU VAT", validation.bu_vat)

    print("\nValidated amounts")
    print("-" * 17)
    _print_field("Issue date", validation.issue_date)
    _print_field("Base", validation.base_amount)
    _print_field("VAT", validation.vat_amount)
    _print_field("Total", validation.total_amount)
    _print_field("Currency", validation.currency)
    _print_list_field("PO", validation.po_list)

    print("\nNotes")
    print("-" * 5)
    print(validation.notes)


def print_pipeline_result(result) -> None:
    """Print a full PipelineResult (classification + extraction + validation)."""
    print("#" * 80)
    print(f"# {result.filename}  [{result.status}]")
    print("#" * 80)
    print(result.message)
    print()

    if result.classification is not None:
        print_classification_result(result.filename, result.classification)
        print()
        print_extraction_result(result.filename, result.classification, result.invoice_data)
        print()

    if result.validation is not None:
        print_validation_result(result.filename, result.validation)
        print()
