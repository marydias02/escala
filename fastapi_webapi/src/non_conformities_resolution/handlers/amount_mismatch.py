"""Valor FT <> Valor PC: the buyer either accepts the difference (bypass) or
tells us the PO changed. Both paths write a fact (or nothing) to SAP and let
REVALIDATE decide whether the process is now clean enough to consume — the
same shape as `missing_po`/`missing_migo`; none of them call `consume_process`
directly.

"PO changed" is ambiguous on its own and splits two ways:
- a NEW PO number was given -> functionally identical to Falta PC's "buyer
  gave us the PO"; write it with `update_process_po`, same missing-column gap
  as `missing_po.handle`.
- no PO number, just "the PO/PC was altered" -> the PO number itself did not
  change, only its value in SAP did. There is nothing for us to write; SAP
  already has the update, so REVALIDATE just needs to re-check.
"""

from non_conformities_resolution.handlers.types import HandlerOutcome, MissingSapColumnError
from non_conformities_resolution.models.buyer_reply import BuyerReply
from non_conformities_resolution.sap.sap_client import update_process_po


async def handle(process: dict, reply: BuyerReply) -> HandlerOutcome:
    reference_no = process["reference_no"]

    if reply.intent == "bypass":
        # No PO code to write — sap_processes.total_amount already holds the
        # mismatched amount; SAP just needs to know the buyer accepted it.
        # REVALIDATE reads this flag and passes it to revalidate_process.
        return HandlerOutcome(
            resolved=True, detail="buyer accepted the difference (bypass)", bypassed=True
        )

    if reply.intent == "po_changed":
        if not reply.po_code:
            # The PO number itself is unchanged, only its value in SAP is —
            # nothing to write here; REVALIDATE re-checks against SAP directly.
            return HandlerOutcome(
                resolved=True, detail="buyer says the PO value was updated in SAP; re-checking"
            )

        result = await update_process_po(reference_no, reply.po_code)
        if result.status != "ok":
            return HandlerOutcome(resolved=False, detail=result.error or "update_process_po failed")

        # TODO(migration): sap_processes has no po_code column. Once the real
        # SAP field name is known, persist reply.po_code onto the process row
        # here — same gap as missing_po.handle.
        raise MissingSapColumnError(
            "sap_processes has no po_code column; add it in a migration once the SAP "
            "field name is known, then persist reply.po_code here."
        )

    return HandlerOutcome(resolved=False, detail="buyer reply neither bypassed nor pointed at a PO change")
