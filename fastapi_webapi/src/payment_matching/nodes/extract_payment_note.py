from typing import cast

from langchain_core.language_models import BaseChatModel

from email_core.documents import LoadedDocument
from payment_matching.models import PaymentNoteDocument
from payment_matching.prompts import (
    PAYMENT_NOTE_SYSTEM_MESSAGE,
    build_payment_note_human_message,
)
from payment_matching.tracing import STAGE_PAYMENT_NOTE, payment_note_summary, span
from utils.llm_retry import invoke_with_retry


def extract_payment_note(
    llm: BaseChatModel, doc: LoadedDocument, *, scanned: bool = False
) -> PaymentNoteDocument:
    """Classify one document as a payment note and read what it settles.

    The document goes to the model as page images when scanned, as the PDF
    otherwise.
    """
    structured_llm = llm.with_structured_output(PaymentNoteDocument)
    human_message = build_payment_note_human_message(doc, scanned=scanned)

    with span(STAGE_PAYMENT_NOTE, "LLM") as stage_span:
        stage_span.set_inputs(
            {"filename": doc.filename, "input_mode": "image" if scanned else "pdf"}
        )
        note = invoke_with_retry(
            structured_llm, [PAYMENT_NOTE_SYSTEM_MESSAGE, human_message], stage="payment note"
        )
        note = cast(PaymentNoteDocument, note)
        stage_span.set_outputs(payment_note_summary(note))
        return note
