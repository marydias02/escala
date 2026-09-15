import re
import unicodedata

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from loguru import logger
from rapidfuzz import fuzz

from invoice_extraction.config import MIN_CONFIDENCE, failed_confidence
from invoice_extraction.invoice_utils.llm_retry import invoke_with_retry
from invoice_extraction.models import InvoiceData, ValidationReport
from invoice_extraction.models.common import Checked
from invoice_extraction.prompts import VALIDATION_SYSTEM_MESSAGE, build_validation_human_message
from invoice_extraction.tools import VALIDATION_TOOLS
from invoice_extraction.tools.vat_registry import PartyRepository, business_units, suppliers
from invoice_extraction.tracing import (
    STAGE_VALIDATION,
    STAGE_VALIDATION_REGISTRY,
    STAGE_VALIDATION_SHAPING,
    STAGE_VALIDATION_TOOLS,
    span,
    validation_summary,
)
from utils.utils_db import normalize_key, select_sync

# Below this, two names are considered unrelated rather than a match.
NAME_MATCH_THRESHOLD = 0.85

# Drop punctuation from words
_INNER_PUNCTUATION = re.compile(r"[.,]")

# Everything else non-alphanumeric collapses to a single space, preserving it
_WORD_BREAK = re.compile(r"[^a-z0-9]+")

# Safety net for a model that keeps calling tools instead of concluding.
MAX_TOOL_ROUNDS = 3


# Confidence stamped on a party resolved by fuzzy name matching
FUZZY_MATCH_CONFIDENCE = min(round(MIN_CONFIDENCE + 0.1, 2), 1)

# Cents, to absorb float error on amounts the model returns as floats.
AMOUNT_TOLERANCE = 0.01

SHAPE_REQUEST = HumanMessage(
    content=(
        "Now return your validation as a single ValidationReport object, applying "
        "any corrections you identified above. Remember: bu_name/bu_vat are the "
        "client fields, supplier_id and bu_id are always null, and `notes` must be "
        "telegraphic."
    )
)


def _normalize_name(name: str) -> str:
    """Lowercase, accent-stripped, punctuation-normalized form of a company name.

    Construções S.A. -> construcoes sa
    """
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    tight = _INNER_PUNCTUATION.sub("", without_accents.lower())
    return _WORD_BREAK.sub(" ", tight).strip()


def _reconcile_amounts(report: ValidationReport) -> ValidationReport:
    """Apply `base + vat = total`, deterministically — the LLM reads, it does not compute.

    One missing amount is derived from the other two.
    Three that disagree are left as is and total_amount's confidence is
    dropped below MIN_CONFIDENCE so the gate stops it and the reviewer knows where to look.
    If only total exists, base = total and vat = 0
    """
    base, vat, total = report.base_amount, report.vat_amount, report.total_amount

    if base is not None and vat is not None and total is not None:
        if abs(base.value + vat.value - total.value) <= AMOUNT_TOLERANCE:
            return report
        # Which pair is right is unknowable here, so nothing is corrected — only
        # flagged, below MIN_CONFIDENCE, which REQUIRED_FIELDS turns into a block.
        confidence = failed_confidence()
        return _noted(
            report,
            {"total_amount": Checked[float](value=total.value, confidence=confidence)},
            f"amounts do not reconcile: {base.value:.2f} + {vat.value:.2f} != "
            f"{total.value:.2f}; kept as read, total_amount confidence {confidence:.2f}",
        )

    if vat is None and base is not None and total is not None:
        field, value = "vat_amount", round(total.value - base.value, 2)
    elif total is None and base is not None and vat is not None:
        field, value = "total_amount", round(base.value + vat.value, 2)
    elif base is None and total is not None and vat is not None:
        field, value = "base_amount", round(total.value - vat.value, 2)
    elif base is None and vat is None and total is not None:
        # A zero total with nothing else read is an empty or unparsed document,
        # not a zero-VAT one: flagged below MIN_CONFIDENCE instead of derived.
        if total.value == 0:
            confidence = failed_confidence()
            return _noted(
                report,
                {
                    "base_amount": Checked[float](value=0.0, confidence=confidence),
                    "vat_amount": Checked[float](value=0.0, confidence=confidence),
                    "total_amount": Checked[float](value=0.0, confidence=confidence),
                },
                f"only amount read is a zero total; base/vat set to 0.00 at "
                f"confidence {confidence:.2f} so the gate stops it",
            )
        confidence = total.confidence
        return _noted(
            report,
            {
                "base_amount": Checked[float](value=total.value, confidence=confidence),
                "vat_amount": Checked[float](value=0.0, confidence=confidence),
            },
            f"base/vat absent; assumed zero-VAT: vat_amount 0.00, base_amount {total.value:.2f} @{confidence:.2f}",
        )
    else:
        # Two or more missing: one equation cannot fill two unknowns.
        return report

    # A derived value is only as good as its weakest input.
    confidence = min(f.confidence for f in (base, vat, total) if f is not None)
    return _noted(
        report,
        {field: Checked[float](value=value, confidence=confidence)},
        f"{field} derived as {value:.2f} @{confidence:.2f} (base + vat = total)",
    )


def _noted(report: ValidationReport, fields: dict[str, Checked[float]], note: str) -> ValidationReport:
    """Set the given fields and append the note explaining them, for the reviewer."""
    logger.info(note)
    return report.model_copy(update={**fields, "notes": f"{report.notes.strip()} {note}".strip()})


def _best_name_match(table: str, id_column: str, name: str) -> tuple[dict, float] | None:
    """The `table` row whose name best matches `name`, paired with its match
    confidence — or None below NAME_MATCH_THRESHOLD.

    Scored with `token_sort_ratio` on normalized names (see `_normalize_name`),
    which tolerates word-order and formatting differences.

    A tie breaks on plain Levenshtein `ratio`. If still tied, break on first row and log
    """
    rows = select_sync(f"SELECT {id_column}, name, vat FROM {table}", [])
    if not rows:
        return None

    target = _normalize_name(name)
    scored = [(fuzz.token_sort_ratio(target, _normalize_name(row["name"])), row) for row in rows]

    best_score = max(score for score, _row in scored)
    if best_score < NAME_MATCH_THRESHOLD * 100:
        return None

    # An exact normalized match (100) is as certain as a VAT hit; anything
    # below that, down to the threshold, is a guess.
    confidence = 1.0 if best_score == 100 else FUZZY_MATCH_CONFIDENCE

    best = [row for score, row in scored if score == best_score]
    if len(best) == 1:
        return best[0], confidence

    best_by_ratio = sorted(best, key=lambda row: fuzz.ratio(target, _normalize_name(row["name"])), reverse=True)
    top_ratio = fuzz.ratio(target, _normalize_name(best_by_ratio[0]["name"]))
    tied = [row for row in best_by_ratio if fuzz.ratio(target, _normalize_name(row["name"])) == top_ratio]

    if len(tied) > 1:
        logger.warning(
            f"{table}: {len(tied)} names tied at token_sort={best_score:.0f}/ratio="
            f"{top_ratio:.0f} for {name!r}; picking {tied[0]['name']!r}"
        )

    return tied[0], confidence


def _closest_within(rows: list[dict], name: str | None) -> dict:
    """The row whose name is closest to `name`, among rows a VAT already
    confirmed. No threshold: every candidate holds the VAT, so one of them is
    right and the name only says which.

    With no name, or a tie, the smallest id wins so the pick is stable.
    """
    if not name:
        return min(rows, key=lambda row: row["id"])

    target = _normalize_name(name)
    scored = [(fuzz.token_sort_ratio(target, _normalize_name(row["name"])), row) for row in rows]

    best_score = max(score for score, _row in scored)
    best = [row for score, row in scored if score == best_score]
    if len(best) == 1:
        return best[0]

    by_ratio = sorted(best, key=lambda row: fuzz.ratio(target, _normalize_name(row["name"])), reverse=True)
    top_ratio = fuzz.ratio(target, _normalize_name(by_ratio[0]["name"]))
    tied = sorted(
        (row for row in by_ratio if fuzz.ratio(target, _normalize_name(row["name"])) == top_ratio),
        key=lambda row: row["id"],
    )

    if len(tied) > 1:
        logger.warning(
            f"{len(tied)} names tied at token_sort={best_score:.0f}/ratio={top_ratio:.0f} "
            f"for {name!r}; picking the smallest id {tied[0]['id']!r}"
        )

    return tied[0]


def _find_party(
    repository: PartyRepository, table: str, id_column: str, vat: str | None, name: str | None
) -> tuple[dict, float] | None:
    """One party matching `vat`, or failing that the closest `name` match above
    NAME_MATCH_THRESHOLD, paired with the confidence the match deserves. None if
    neither hits.

    VAT first: it is the unique, normalized key every other lookup in this
    package already keys on (see `vat_registry.py`, `po_confirmation.py`). SAP
    registers branches and vessels under one company's VAT, so a VAT can return
    several — `name` picks between them. Name alone is the fallback for a
    document whose VAT was missed or misread.
    """
    normalized_vat = normalize_key(vat)
    if normalized_vat:
        rows = repository.by_vat(normalized_vat)
        if rows:
            return _closest_within(rows, name), 1.0

    if name:
        return _best_name_match(table, id_column, name)

    return None


def _resolve_party(
    report: ValidationReport, prefix: str, repository: PartyRepository, table: str, id_column: str
) -> ValidationReport:
    """Fill `{prefix}_id` and overwrite `{prefix}_name`/`{prefix}_vat` with the
    registry's own values.

    A VAT match or an exact (post-normalization) name match is stamped at
    confidence 1.0; a fuzzy name match - confidence at FUZZY_MATCH_CONFIDENCE

    No match: the report is returned unchanged (id stays null, extracted
    name/vat are kept) — which will get flagged in decisions.py
    """
    vat = getattr(report, f"{prefix}_vat")
    name = getattr(report, f"{prefix}_name")

    found = _find_party(repository, table, id_column, vat.value if vat else None, name.value if name else None)
    if found is None:
        return report
    row, confidence = found

    # The lakehouse rows are keyed `id`; the name-only fallback still returns
    # Postgres rows keyed on the table's own id column.
    party_id = row["id"] if "id" in row else row[id_column]

    return report.model_copy(
        update={
            f"{prefix}_id": Checked[str](value=str(party_id), confidence=confidence),
            f"{prefix}_name": Checked[str](value=row["name"], confidence=confidence),
            f"{prefix}_vat": Checked[str](value=row["vat"], confidence=confidence),
        }
    )


def resolve_registry_ids(report: ValidationReport) -> ValidationReport:
    """Fill supplier_id/bu_id from the SAP master data, deterministically.

    VAT-first, name-fallback — the LLM cannot derive registry id,
    and registry is source of truth for the name and VAT

    Never raises. A failed lookup just leaves that party's id/name/vat as they were.
    """
    try:
        report = _resolve_party(report, "supplier", suppliers, "dim_suppliers", "supplier_id")
        report = _resolve_party(report, "bu", business_units, "dim_business_units", "bu_id")
    except Exception as exc:  # noqa: BLE001 - a lookup blip must not break validation
        logger.warning(f"Registry lookup failed, leaving ids unresolved: {exc!r}")
    return report


def _run_tool_calls(response: AIMessage) -> list[ToolMessage]:
    """Execute every tool call in `response` and wrap the results as ToolMessages."""
    tools_by_name = {tool.name: tool for tool in VALIDATION_TOOLS}

    tool_messages: list[ToolMessage] = []
    for tool_call in response.tool_calls:
        tool = tools_by_name.get(tool_call["name"])

        # One TOOL span per execution, named after the tool, so the registry
        # lookups show up as their own nodes in the graph rather than being
        # invisible inside the validation stage.
        with span(tool_call["name"], "TOOL") as tool_span:
            tool_span.set_inputs(tool_call["args"])

            if tool is None:
                content = f"Unknown tool: {tool_call['name']}"
            else:
                try:
                    content = str(tool.invoke(tool_call["args"]))
                except Exception as exc:  # noqa: BLE001 - report back to the model, don't crash
                    content = f"Tool error: {type(exc).__name__}: {exc}"

            tool_span.set_outputs(content)

        tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call["id"]))

    return tool_messages


def validate_document(
    llm: BaseChatModel,
    invoice: InvoiceData,
    parsed_text: str | None = None,
    document_number: str | None = None,
) -> ValidationReport:
    """Validate extracted invoice data, using the registry tools, into a ValidationReport.

    Runs in two phases because a single call cannot both invoke tools and emit a
    schema reliably:

      1. Tool phase   — the model reasons with `bind_tools`, calling the VAT
                        registry as needed (capped at MAX_TOOL_ROUNDS).
      2. Shaping pass — the whole conversation is replayed through
                        `with_structured_output` to produce the report.
      3. Registry phase — supplier and bu information is fetched from the db
                        according to their vat and/or name

    `document_number` comes from the CLASSIFICATION stage, not from `invoice` —
    it is read there so duplicates can be matched before extraction runs. It is
    still validated here, since the report is what reaches the database.
    """
    messages: list[BaseMessage] = [
        VALIDATION_SYSTEM_MESSAGE,
        build_validation_human_message(invoice, parsed_text=parsed_text, document_number=document_number),
    ]

    llm_with_tools = llm.bind_tools(VALIDATION_TOOLS)

    # One parent span for the whole stage, with a child per phase. The tool phase
    # is traced here rather than in `invoke_with_retry` because it never goes
    # through it: that helper retries PARSE failures from `with_structured_output`,
    # which is meaningless against `bind_tools` — the model is reasoning, not
    # emitting a schema. A span there would miss every tool round.
    with span(STAGE_VALIDATION, "LLM") as stage_span:
        stage_span.set_inputs({"has_parsed_text": parsed_text is not None})

        with span(STAGE_VALIDATION_TOOLS) as tools_span:
            rounds = 0
            for round_number in range(1, MAX_TOOL_ROUNDS + 1):
                logger.info(f"LLM call → validation (tools, round {round_number})")
                rounds = round_number
                response = llm_with_tools.invoke(messages)
                messages.append(response)

                if not getattr(response, "tool_calls", None):
                    break

                messages.extend(_run_tool_calls(response))

            # `hit_cap` distinguishes a model that concluded from one that was cut
            # off still asking for tools — the latter means MAX_TOOL_ROUNDS is too
            # low, or the model is stuck in a loop.
            tools_span.set_outputs(
                {
                    "rounds": rounds,
                    "max_rounds": MAX_TOOL_ROUNDS,
                    "hit_cap": rounds == MAX_TOOL_ROUNDS and bool(getattr(response, "tool_calls", None)),
                }
            )

        structured_llm = llm.with_structured_output(ValidationReport)

        with span(STAGE_VALIDATION_SHAPING, "LLM") as shaping_span:
            report = invoke_with_retry(structured_llm, [*messages, SHAPE_REQUEST], stage="validation (shaping)")
            report = _reconcile_amounts(report)
            shaping_span.set_outputs(validation_summary(report))

        with span(STAGE_VALIDATION_REGISTRY) as registry_span:
            report = resolve_registry_ids(report)
            registry_span.set_outputs(validation_summary(report))

        stage_span.set_outputs(validation_summary(report))
        return report
