from typing import cast

from langchain_core.language_models import BaseChatModel

from invoice_extraction.invoice_utils.llm_retry import invoke_with_retry
from invoice_extraction.tracing import span
from payment_matching.models import PaymentEmailInfo
from payment_matching.prompts import (
    PAYMENT_EMAIL_SYSTEM_MESSAGE,
    build_payment_email_human_message,
)

STAGE_PAYMENT_EMAIL = "1-payment-email"


def extract_payment_email(llm: BaseChatModel, subject: str, body: str) -> PaymentEmailInfo:
    """Classify one email body as payment-related and extract what it states."""
    structured_llm = llm.with_structured_output(PaymentEmailInfo)
    human_message = build_payment_email_human_message(subject, body)

    with span(STAGE_PAYMENT_EMAIL, "LLM") as stage_span:
        stage_span.set_inputs({"subject": subject, "body_chars": len(body or "")})
        info = invoke_with_retry(
            structured_llm, [PAYMENT_EMAIL_SYSTEM_MESSAGE, human_message], stage="payment email"
        )
        info = cast(PaymentEmailInfo, info)
        stage_span.set_outputs(
            {
                "is_payment_related": info.is_payment_related.value,
                "invoice_numbers": [n.value for n in info.invoice_numbers],
                "total_amount_paid": info.total_amount_paid.value if info.total_amount_paid else None,
            }
        )
        return info
