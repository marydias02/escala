"""Falta MIGO: verify the goods receipt exists in SAP, associate it, and persist
it locally on the process row (`sap_processes.migo_ref`).
"""

from non_conformities_resolution.handlers.types import HandlerOutcome
from non_conformities_resolution.models.buyer_reply import BuyerReply
from non_conformities_resolution.sap import sap_queries
from non_conformities_resolution.sap.sap_client import associate_migo, migo_exists


async def handle(process: dict, reply: BuyerReply) -> HandlerOutcome:
    if reply.intent != "migo_done":
        return HandlerOutcome(resolved=False, detail="buyer reply did not confirm a MIGO")

    reference_no = process["reference_no"]
    found_migo_ref = await migo_exists(reference_no)
    if not found_migo_ref:
        return HandlerOutcome(resolved=False, detail="no MIGO found in SAP for this process")

    result = await associate_migo(reference_no, found_migo_ref)
    if result.status != "ok":
        return HandlerOutcome(resolved=False, detail=result.error or "associate_migo failed")

    await sap_queries.set_migo_ref(reference_no, found_migo_ref)
    return HandlerOutcome(resolved=True, detail=f"MIGO {found_migo_ref!r} associated in SAP")
