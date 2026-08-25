"""SAP write side — STUBS for now`."""

from dataclasses import dataclass
from typing import Literal, Optional

from loguru import logger

from non_conformities_resolution import config

ActionStatus = Literal["ok", "failed"]


@dataclass
class SapActionResult:
    status: ActionStatus
    reference_no: str
    detail: Optional[str] = None
    error: Optional[str] = None


def _stub_result(reference_no: str, detail: str) -> SapActionResult:
    logger.info(f"  🏦 [STUB] SAP no-op ({config.SAP_ENABLED=}): {detail}")
    return SapActionResult(status="ok", reference_no=reference_no, detail=detail)


async def update_process_po(reference_no: str, po_code: str) -> SapActionResult:
    """Write the buyer-provided PO code onto the SAP process. STUB: always ok."""
    return _stub_result(reference_no, f"update_process_po(po_code={po_code!r})")


async def migo_exists(reference_no: str) -> Optional[str]:
    """The MIGO reference associated with this process in SAP, or None if it has
    none yet. STUB: always reports one exists, so the happy path is exercisable."""
    logger.info(f"  🏦 [STUB] migo_exists({reference_no!r}) -> assuming found")
    return "STUB-MIGO"


async def associate_migo(reference_no: str, migo_ref: str) -> SapActionResult:
    """Link a MIGO document to the SAP process. STUB: always ok."""
    return _stub_result(reference_no, f"associate_migo(migo_ref={migo_ref!r})")


async def send_message_to_buyer(reference_no: str, content: str) -> SapActionResult:
    """Post a message to the buyer in SAP. STUB: always ok."""
    return _stub_result(reference_no, f"send_message_to_buyer(content={content!r})")


async def consume_process(reference_no: str, amount: Optional[float] = None) -> SapActionResult:
    """Consume/settle the process in SAP, optionally against a specific amount
    (a bypass or a corrected PO value). STUB: always ok."""
    return _stub_result(reference_no, f"consume_process(amount={amount!r})")


async def revalidate_process(reference_no: str, bypassed: bool = False) -> list[str]:
    """Re-check a process against SAP and return its remaining issues, if any.

    `bypassed=True` means the buyer accepted an amount mismatch outright (see
    `HandlerOutcome.bypassed`) — SAP needs that instruction or it would just
    re-flag the same mismatch it was told to ignore.

    An empty list means clean — ready to consume. STUB: always clean, so the
    "no error left" branch in resolution_pipeline is exercisable without SAP.
    """
    logger.info(f"  🏦 [STUB] revalidate_process({reference_no!r}, {bypassed=}) -> no remaining issues")
    return []
