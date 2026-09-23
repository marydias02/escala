from typing import cast

from langchain_core.language_models import BaseChatModel

from payment_matching.models import PaymentSegmentation
from payment_matching.prompts import (
    build_segmentation_human_message,
    build_segmentation_system_message,
)
from payment_matching.tracing import STAGE_SEGMENTATION, segmentation_summary, span
from utils.llm_retry import invoke_with_retry


def segment_payment_document(
    llm: BaseChatModel,
    encoded_pdf: str,
    filename: str,
    total_pages: int,
) -> PaymentSegmentation:
    """Find the boundaries of the independent documents inside one PDF.

    `total_pages` must come from pypdf, never from the model. Returns boundaries
    only; callers run `validate_segmentation` on the result before trusting it.
    """
    structured_llm = llm.with_structured_output(PaymentSegmentation)
    system_message = build_segmentation_system_message(total_pages)
    human_message = build_segmentation_human_message(filename, encoded_pdf, total_pages)

    with span(STAGE_SEGMENTATION, "LLM") as stage_span:
        # `encoded_pdf` is deliberately not an input: the autolog child span
        # already records the prompt.
        stage_span.set_inputs({"filename": filename, "total_pages": total_pages})
        segmentation = invoke_with_retry(
            structured_llm, [system_message, human_message], stage="segmentation"
        )
        segmentation = cast(PaymentSegmentation, segmentation)
        stage_span.set_outputs(segmentation_summary(segmentation))
        return segmentation
