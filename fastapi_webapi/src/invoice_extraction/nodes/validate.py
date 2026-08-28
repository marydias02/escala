from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from loguru import logger

from invoice_extraction.config import failed_confidence
from invoice_extraction.invoice_utils.llm_retry import invoke_with_retry
from invoice_extraction.models import InvoiceData, ValidationReport
from invoice_extraction.models.common import Checked
from invoice_extraction.prompts import VALIDATION_SYSTEM_MESSAGE, build_validation_human_message
from invoice_extraction.tools import VALIDATION_TOOLS
from invoice_extraction.tracing import (
    STAGE_VALIDATION,
    STAGE_VALIDATION_SHAPING,
    STAGE_VALIDATION_TOOLS,
    span,
    validation_summary,
)

# Safety net for a model that keeps calling tools instead of concluding.
MAX_TOOL_ROUNDS = 3

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


def _reconcile_amounts(report: ValidationReport) -> ValidationReport:
    """Apply `base + vat = total`, deterministically — the LLM reads, it does not compute.

    One missing amount is derived from the other two.
    Three that disagree are left as is and total_amount's confidence is 
    dropped below MIN_CONFIDENCE so the gate stops it and the reviewer knows where to look.
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
            "total_amount",
            Checked[float](value=total.value, confidence=confidence),
            f"amounts do not reconcile: {base.value:.2f} + {vat.value:.2f} != "
            f"{total.value:.2f}; kept as read, total_amount confidence {confidence:.2f}",
        )

    if vat is None and base is not None and total is not None:
        field, value = "vat_amount", round(total.value - base.value, 2)
    elif total is None and base is not None and vat is not None:
        field, value = "total_amount", round(base.value + vat.value, 2)
    elif base is None and total is not None and vat is not None:
        field, value = "base_amount", round(total.value - vat.value, 2)
    else:
        # Two or more missing: one equation cannot fill two unknowns.
        return report

    # A derived value is only as good as its weakest input.
    confidence = min(f.confidence for f in (base, vat, total) if f is not None)
    return _noted(
        report,
        field,
        Checked[float](value=value, confidence=confidence),
        f"{field} derived as {value:.2f} @{confidence:.2f} (base + vat = total)",
    )


def _noted(
    report: ValidationReport, field: str, checked: Checked[float], note: str
) -> ValidationReport:
    """Set one field and append the note explaining it, for the reviewer."""
    logger.info(note)
    return report.model_copy(
        update={field: checked, "notes": f"{report.notes.strip()} {note}".strip()}
    )


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
    parsed_text: Optional[str] = None,
    document_number: Optional[str] = None,
) -> ValidationReport:
    """Validate extracted invoice data, using the registry tools, into a ValidationReport.

    Runs in two phases because a single call cannot both invoke tools and emit a
    schema reliably:

      1. Tool phase   — the model reasons with `bind_tools`, calling the VAT
                        registry as needed (capped at MAX_TOOL_ROUNDS).
      2. Shaping pass — the whole conversation is replayed through
                        `with_structured_output` to produce the report.

    `document_number` comes from the CLASSIFICATION stage, not from `invoice` —
    it is read there so duplicates can be matched before extraction runs. It is
    still validated here, since the report is what reaches the database.
    """
    messages: list[BaseMessage] = [
        VALIDATION_SYSTEM_MESSAGE,
        build_validation_human_message(
            invoice, parsed_text=parsed_text, document_number=document_number
        ),
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
                    "hit_cap": rounds == MAX_TOOL_ROUNDS
                    and bool(getattr(response, "tool_calls", None)),
                }
            )

        structured_llm = llm.with_structured_output(ValidationReport)

        with span(STAGE_VALIDATION_SHAPING, "LLM") as shaping_span:
            report = invoke_with_retry(
                structured_llm, [*messages, SHAPE_REQUEST], stage="validation (shaping)"
            )
            report = _reconcile_amounts(report)
            shaping_span.set_outputs(validation_summary(report))

        stage_span.set_outputs(validation_summary(report))
        return report