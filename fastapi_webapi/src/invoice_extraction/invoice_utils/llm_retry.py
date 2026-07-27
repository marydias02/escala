from typing import Optional

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, HumanMessage
from loguru import logger
from pydantic import ValidationError

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


def invoke_with_retry(structured_llm, messages: list[BaseMessage], stage: Optional[str] = None):
    """Invoke a structured-output LLM, retrying once on a parse failure.

    Some models reply with prose instead of JSON. A single retry with an explicit
    "JSON only" reminder appended recovers most of those, and is cheaper than
    losing the document. Transport errors are left to propagate — they will not
    improve on a plain retry.

    `stage` labels the pipeline step (chunking, classification, ...) so the
    otherwise-opaque HTTP log line that follows can be traced to a stage.
    """
    if stage:
        logger.info(f"LLM call → {stage}")
    try:
        return structured_llm.invoke(messages)
    except PARSE_ERRORS:
        if stage:
            logger.info(f"LLM call → {stage} (retry: JSON-only)")
        return structured_llm.invoke([*messages, JSON_ONLY_NUDGE])