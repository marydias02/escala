from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, HumanMessage
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


def invoke_with_retry(structured_llm, messages: list[BaseMessage]):
    """Invoke a structured-output LLM, retrying once on a parse failure.

    Some models reply with prose instead of JSON. A single retry with an explicit
    "JSON only" reminder appended recovers most of those, and is cheaper than
    losing the document. Transport errors are left to propagate — they will not
    improve on a plain retry.
    """
    try:
        return structured_llm.invoke(messages)
    except PARSE_ERRORS:
        return structured_llm.invoke([*messages, JSON_ONLY_NUDGE])