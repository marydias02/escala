"""Falta PC: the buyer told us the PO reference; write it to SAP.

`sap_processes` has no `po_code` column today, so persisting it locally is not
possible yet — that raises `MissingSapColumnError` with a TODO naming the
migration this needs, rather than silently dropping the value. The SAP-side
write (`sap_client.update_process_po`) still runs and is stubbed independently.
"""

from non_conformities_resolution.handlers.types import HandlerOutcome, MissingSapColumnError
from non_conformities_resolution.models.buyer_reply import BuyerReply
from non_conformities_resolution.sap.sap_client import update_process_po


async def handle(process: dict, reply: BuyerReply) -> HandlerOutcome:
    if reply.intent != "po_provided" or not reply.po_code:
        return HandlerOutcome(resolved=False, detail="buyer reply did not contain a usable PO code")

    reference_no = process["reference_no"]
    result = await update_process_po(reference_no, reply.po_code)
    if result.status != "ok":
        return HandlerOutcome(resolved=False, detail=result.error or "update_process_po failed")

    # TODO(migration): sap_processes has no po_code column. Once the real SAP
    # field name is known, persist reply.po_code onto the process row here —
    # e.g. `await sap_queries.set_po_code(reference_no, reply.po_code)`.
    raise MissingSapColumnError(
        "sap_processes has no po_code column; add it in a migration once the SAP "
        "field name is known, then persist reply.po_code here."
    )
