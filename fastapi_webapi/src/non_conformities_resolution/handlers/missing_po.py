"""Falta PC: the buyer told us the PO reference; write it to SAP and persist it
locally on the process row (`sap_processes.po_code`).
"""

from non_conformities_resolution.handlers.types import HandlerOutcome
from non_conformities_resolution.models.buyer_reply import BuyerReply
from non_conformities_resolution.sap import sap_queries
from non_conformities_resolution.sap.sap_client import update_process_po


async def handle(process: dict, reply: BuyerReply) -> HandlerOutcome:
    if reply.intent != "po_provided" or not reply.po_code:
        return HandlerOutcome(resolved=False, detail="buyer reply did not contain a usable PO code")

    reference_no = process["reference_no"]
    result = await update_process_po(reference_no, reply.po_code)
    if result.status != "ok":
        return HandlerOutcome(resolved=False, detail=result.error or "update_process_po failed")

    await sap_queries.set_po_code(reference_no, reply.po_code)
    return HandlerOutcome(resolved=True, detail=f"PO code {reply.po_code!r} written to SAP")
