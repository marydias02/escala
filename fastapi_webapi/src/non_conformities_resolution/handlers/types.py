"""Shared shapes for issue handlers. Split out from `handlers/__init__.py` so a
handler module can import them without pulling in the full dispatch table (which
imports every handler) and risking a circular import.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from non_conformities_resolution.models.buyer_reply import BuyerReply


@dataclass
class HandlerOutcome:
    """What a handler did with one process's buyer reply.

    `resolved=True` means the issue is gone and `resolution_pipeline` should
    move on to REVALIDATE. `resolved=False` means the reply did not clear the
    issue (an unclear reply, a lookup that came back empty) and the process
    should fall through to STATUS_NEEDS_MANUAL.

    `bypassed=True` means the buyer accepted an amount mismatch outright (no
    new PO code involved) — `sap_processes.total_amount` already holds the
    invoice amount, so SAP just needs the instruction to accept it on this
    process. REVALIDATE passes this through to `sap_client.revalidate_process`
    so SAP's own check does not re-flag the mismatch it was just told to ignore.
    """

    resolved: bool
    detail: str = ""
    bypassed: bool = False


# process: the sap_processes row as a dict (from sap_queries.fetch_pipeline_processes).
# reply is None when RESOLVE calls a SOLVABLE_ISSUES handler directly, with no
# buyer reply behind it — only the STAGE 2 (buyer-replied) call site passes one.
Handler = Callable[[dict, Optional[BuyerReply]], Awaitable[HandlerOutcome]]


class MissingSapColumnError(NotImplementedError):
    """Raised when a handler needs to persist a value sap_processes has no
    column for yet (po_code, migo_ref, ...). Deliberately a distinct type, not a
    bare NotImplementedError, so `resolution_pipeline` can catch this specific
    case if it ever needs to route it differently from "handler crashed"."""
