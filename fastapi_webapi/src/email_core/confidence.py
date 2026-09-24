"""Confidence/evidence wrappers shared by every extraction schema.

Moved verbatim from `invoice_extraction.models.common`, which now re-exports
them. Both use cases state extracted values the same way, so a reviewer reads
one convention rather than two.
"""

from pydantic import BaseModel, Field


class Confident[T](BaseModel):
    """A field value paired with the model's self-reported confidence and evidence.

    - value:      the extracted value (typed T)
    - confidence: 0..1 self-reported certainty this value is correct given the source
    - evidence:   verbatim snippet from the source text supporting the value
                  (used to verify the value is grounded, not hallucinated)
    """

    value: T
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Your certainty (0-1) that `value` is correct given ONLY the source text.",
    )
    evidence: str = Field(
        description="Short verbatim snippet copied from the source text that supports `value`.",
    )


class Checked[T](BaseModel):
    """A post-validation value paired with the validator's confidence.

    Same shape as `Confident` minus `evidence`. The validation stage re-states
    the evidence it was given rather than producing new snippets, so carrying
    evidence through a second time only burns tokens.
    """

    value: T
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Your certainty (0-1) that `value` is correct after validation.",
    )


def drop_empty_confident_fields(data):
    """Coerce degenerate Confident/Checked objects to None.

    The prompts ask the model to return null for fields it cannot find, but the
    model sometimes signals "unknown" by returning an object with no `value`
    (evidence="", confidence=0) instead. `value` is required, so that shape
    raises a ValidationError and loses the whole document. Normalize it to the
    null the schema expects, keeping the prompt instruction as a hint rather
    than a load-bearing constraint.
    """
    if isinstance(data, dict):
        return {k: (None if isinstance(v, dict) and v.get("value") in (None, "") else v) for k, v in data.items()}
    return data
