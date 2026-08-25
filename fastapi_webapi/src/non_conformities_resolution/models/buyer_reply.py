"""The shape of a parsed buyer reply. class so it can be used for structured output, if needed"""

from dataclasses import dataclass
from typing import Literal, Optional

BuyerIntent = Literal["po_provided", "migo_done", "bypass", "po_changed", "unclear"]


@dataclass
class BuyerReply:
    """One buyer message, interpreted against the issue it responds to.

    Only the field relevant to `intent` is expected to be set:
    - po_provided / po_changed -> po_code
    - migo_done                -> migo_ref
    - bypass                   -> new_amount (optional; None means "advance as-is")
    - unclear                  -> none of the above; the process needs a human.
    """

    intent: BuyerIntent
    po_code: Optional[str] = None
    migo_ref: Optional[str] = None
    new_amount: Optional[float] = None
    raw_content: str = ""
    confidence: float = 0.0
