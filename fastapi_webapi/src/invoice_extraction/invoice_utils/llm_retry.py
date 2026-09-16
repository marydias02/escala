from typing import Optional

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import Runnable
from loguru import logger
from pydantic import ValidationError

from invoice_extraction.tracing import set_span_attributes

# Parse failures we want to retry (prose instead of JSON), as opposed to
# transport/HTTP errors which won't improve on a plain retry.
PARSE_ERRORS = (ValidationError, OutputParserException, ValueError)

JSON_ONLY_NUDGE = HumanMessage(
    content=(
        "Your previous reply could not be parsed. Respond again with ONLY a single "
        "JSON object that matches the required schema — no prose, no Markdown, no "
        "code fences."
    )
)


def invoke_with_retry[T](
    structured_llm: Runnable[list[BaseMessage], T], messages: list[BaseMessage], stage: Optional[str] = None
) -> T:
    """Invoke a structured-output LLM, retrying once on a parse failure.

    Some models reply with prose instead of JSON. A single retry with an explicit
    "JSON only" reminder appended recovers most of those, and is cheaper than
    losing the document. Transport errors are left to propagate — they will not
    improve on a plain retry.

    `stage` labels the pipeline step (chunking, classification, ...) so the
    otherwise-opaque HTTP log line that follows can be traced to a stage.

    `retried` goes on the enclosing stage span: a retry is otherwise invisible
    in the trace, so its doubled token cost cannot be attributed.
    """
    if stage:
        logger.info(f"LLM call → {stage}")
    try:
        result = structured_llm.invoke(messages)
    except PARSE_ERRORS as exc:
        set_span_attributes(retried=True, retry_reason=f"{type(exc).__name__}: {exc}")
        if stage:
            logger.info(f"LLM call → {stage} (retry: JSON-only)")
        return structured_llm.invoke([*messages, JSON_ONLY_NUDGE])

    set_span_attributes(retried=False)
    return result