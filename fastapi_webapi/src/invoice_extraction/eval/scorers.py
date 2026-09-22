"""Field-level scorers: deterministic code checks, no LLM judge.

A VAT number is right or it is not, so every check here is an equality test —
free, instant and reproducible. A judge would only be worth its cost for
something subjective (does `evidence` really support the value?).

Two MLflow constraints shape the return values:
  - "yes"/"no", never "pass"/"fail" — the latter is silently cast to None and
    vanishes from the metrics with no error.
  - None means "not applicable", so the record is skipped rather than failed.
    That is what keeps a gated-out proforma, which has no amounts to check,
    from dragging down the amount scores.
"""

from typing import Any, Optional

from mlflow.genai.scorers import scorer

from invoice_extraction.eval.config import AMOUNT_TOLERANCE


def _verdict(matched: bool) -> str:
    return "yes" if matched else "no"


def _text_match(got: Any, want: Any) -> bool:
    """Compare as text, ignoring case and whitespace."""
    if got is None or want is None:
        return got == want
    return "".join(str(got).split()).casefold() == "".join(str(want).split()).casefold()


def _score_text(outputs: dict, expectations: dict, field: str) -> Optional[str]:
    if field not in expectations:
        return None
    return _verdict(_text_match(outputs.get(field), expectations[field]))


def _score_amount(outputs: dict, expectations: dict, field: str) -> Optional[str]:
    if field not in expectations:
        return None
    got, want = outputs.get(field), expectations[field]
    if got is None or want is None:
        return _verdict(got == want)
    return _verdict(abs(float(got) - float(want)) <= AMOUNT_TOLERANCE)


# --- classification -------------------------------------------------------


@scorer
def gate_correct(outputs, expectations):
    """The extraction gate. A wrong call here voids every field downstream."""
    if "should_extract" not in expectations:
        return None
    return _verdict(outputs.get("should_extract") == expectations["should_extract"])


@scorer
def document_type_correct(outputs, expectations):
    return _score_text(outputs, expectations, "document_type")


@scorer
def document_state_correct(outputs, expectations):
    """A null state reads as "original", so the two are scored as equal."""
    if "document_state" not in expectations:
        return None

    def normalize(value):
        return "original" if value is None else value

    return _verdict(
        _text_match(normalize(outputs.get("document_state")),
                    normalize(expectations["document_state"]))
    )


@scorer
def document_number_correct(outputs, expectations):
    return _score_text(outputs, expectations, "document_number")


@scorer
def document_exception_correct(outputs, expectations):
    """Only scored where the label says so — most documents carry no exception."""
    return _score_text(outputs, expectations, "document_exception")


# --- extracted fields -----------------------------------------------------


@scorer
def supplier_vat_correct(outputs, expectations):
    return _score_text(outputs, expectations, "supplier_vat")


@scorer
def client_vat_correct(outputs, expectations):
    return _score_text(outputs, expectations, "client_vat")


@scorer
def issue_date_correct(outputs, expectations):
    return _score_text(outputs, expectations, "issue_date")


@scorer
def currency_correct(outputs, expectations):
    return _score_text(outputs, expectations, "currency")


@scorer
def base_amount_correct(outputs, expectations):
    return _score_amount(outputs, expectations, "base_amount")


@scorer
def vat_amount_correct(outputs, expectations):
    return _score_amount(outputs, expectations, "vat_amount")


@scorer
def total_amount_correct(outputs, expectations):
    return _score_amount(outputs, expectations, "total_amount")


@scorer
def purchase_order_correct(outputs, expectations):
    """Order-insensitive: the PO set matters, the sequence does not."""
    if "purchase_order" not in expectations:
        return None
    got = outputs.get("purchase_order") or []
    return _verdict(
        {str(p).strip() for p in got}
        == {str(p).strip() for p in expectations["purchase_order"]}
    )


ALL_SCORERS = [
    gate_correct,
    document_type_correct,
    document_state_correct,
    document_number_correct,
    document_exception_correct,
    supplier_vat_correct,
    client_vat_correct,
    issue_date_correct,
    currency_correct,
    base_amount_correct,
    vat_amount_correct,
    total_amount_correct,
    purchase_order_correct,
]
