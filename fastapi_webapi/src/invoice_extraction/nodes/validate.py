from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from loguru import logger

from invoice_extraction.invoice_utils.llm_retry import invoke_with_retry
from invoice_extraction.models import InvoiceData, ValidationReport
from invoice_extraction.prompts import VALIDATION_SYSTEM_MESSAGE, build_validation_human_message
from invoice_extraction.tools import VALIDATION_TOOLS

# Safety net for a model that keeps calling tools instead of concluding.
MAX_TOOL_ROUNDS = 3

SHAPE_REQUEST = HumanMessage(
    content=(
        "Now return your validation as a single ValidationReport object, applying "
        "any corrections you identified above. Remember: bu_name/bu_vat are the "
        "client fields, supplier_id and bu_id are always null, and `notes` must be "
        "telegraphic."
    )
)


def _run_tool_calls(response: AIMessage) -> list[ToolMessage]:
    """Execute every tool call in `response` and wrap the results as ToolMessages."""
    tools_by_name = {tool.name: tool for tool in VALIDATION_TOOLS}

    tool_messages: list[ToolMessage] = []
    for tool_call in response.tool_calls:
        tool = tools_by_name.get(tool_call["name"])
        if tool is None:
            content = f"Unknown tool: {tool_call['name']}"
        else:
            try:
                content = str(tool.invoke(tool_call["args"]))
            except Exception as exc:  # noqa: BLE001 - report back to the model, don't crash
                content = f"Tool error: {type(exc).__name__}: {exc}"

        tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call["id"]))

    return tool_messages


def validate_document(
    llm: BaseChatModel,
    invoice: InvoiceData,
    parsed_text: Optional[str] = None,
) -> ValidationReport:
    """Validate extracted invoice data, using the registry tools, into a ValidationReport.

    Runs in two phases because a single call cannot both invoke tools and emit a
    schema reliably:

      1. Tool phase   — the model reasons with `bind_tools`, calling the VAT
                        registry as needed (capped at MAX_TOOL_ROUNDS).
      2. Shaping pass — the whole conversation is replayed through
                        `with_structured_output` to produce the report.
    """
    messages: list[BaseMessage] = [
        VALIDATION_SYSTEM_MESSAGE,
        build_validation_human_message(invoice, parsed_text=parsed_text),
    ]

    llm_with_tools = llm.bind_tools(VALIDATION_TOOLS)

    for round_number in range(1, MAX_TOOL_ROUNDS + 1):
        logger.info(f"LLM call → validation (tools, round {round_number})")
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not getattr(response, "tool_calls", None):
            break

        messages.extend(_run_tool_calls(response))

    structured_llm = llm.with_structured_output(ValidationReport)

    return invoke_with_retry(structured_llm, [*messages, SHAPE_REQUEST], stage="validation (shaping)")