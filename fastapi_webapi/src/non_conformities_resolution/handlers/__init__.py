"""Dispatch table from issue -> handler, so `resolution_pipeline` looks a handler
up rather than branching with if/elif on the issue string.

Each handler exposes `async def handle(process: dict, reply: BuyerReply) ->
HandlerOutcome`. Keep the map in sync with `resolution_rules.BUYER_ISSUES` — an
issue missing here is not a bug (`resolve_process` falls back to sending the
buyer message / manual validation), but one present here with no matching entry
in BUYER_ISSUES would never be reached.
"""

from non_conformities_resolution import resolution_rules
from non_conformities_resolution.handlers.amount_mismatch import handle as handle_amount_mismatch
from non_conformities_resolution.handlers.missing_migo import handle as handle_missing_migo
from non_conformities_resolution.handlers.missing_po import handle as handle_missing_po
from non_conformities_resolution.handlers.types import Handler, HandlerOutcome

HANDLERS: dict[str, Handler] = {
    resolution_rules.ISSUE_NO_PO: handle_missing_po,
    resolution_rules.ISSUE_NO_MIGO: handle_missing_migo,
    resolution_rules.ISSUE_AMOUNT_MISMATCH: handle_amount_mismatch,
}

__all__ = ["HANDLERS", "Handler", "HandlerOutcome"]
