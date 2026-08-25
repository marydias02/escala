"""Falta MIGO: verify the goods receipt exists in SAP and associate it.

`sap_processes` has no `migo_ref` column today, so persisting it locally is not
possible yet. 
"""

from non_conformities_resolution.handlers.types import HandlerOutcome, MissingSapColumnError
from non_conformities_resolution.models.buyer_reply import BuyerReply
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

    # TODO(migration): sap_processes has no migo_ref column. Once the real SAP
    # field name is known, persist found_migo_ref onto the process row here.
    raise MissingSapColumnError(
        "sap_processes has no migo_ref column; add it in a migration once the SAP "
        "field name is known, then persist found_migo_ref here."
    )
