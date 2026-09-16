from langchain_core.language_models import BaseChatModel

from invoice_extraction.invoice_utils.llm_retry import invoke_with_retry
from invoice_extraction.models import EmailIntent
from invoice_extraction.prompts import (
    EMAIL_INTENT_SYSTEM_MESSAGE,
    build_email_intent_human_message,
)
from invoice_extraction.tracing import STAGE_EMAIL_INTENT, span


def classify_email_intent(llm: BaseChatModel, subject: str, body: str) -> EmailIntent:
    """Classify one email body: is it about an invoice, and does it link to one?

    Text-only — unlike `classify_document` there is no PDF to attach, because this
    runs precisely when the email produced no usable PDF.
    """
    structured_llm = llm.with_structured_output(EmailIntent)
    human_message = build_email_intent_human_message(subject, body)

    with span(STAGE_EMAIL_INTENT, "LLM") as stage_span:
        stage_span.set_inputs({"subject": subject, "body_chars": len(body or "")})
        intent = invoke_with_retry(structured_llm, [EMAIL_INTENT_SYSTEM_MESSAGE, human_message], stage="email intent")
        stage_span.set_outputs(
            {
                "is_invoice_delivery": intent.is_invoice_delivery.value,
                "has_invoice_link": intent.has_invoice_link.value,
            }
        )
        return intent
