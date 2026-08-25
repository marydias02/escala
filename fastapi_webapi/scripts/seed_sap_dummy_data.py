"""Populate sap_processes / sap_messages with dummy data for local dev.

Inserts one sap_processes row per (status, issue) combination the
non-conformities-resolution pipeline cares about, plus matching sap_messages
rows engineered so `parse_buyer_reply` (see
`non_conformities_resolution/nodes/read_buyer_reply.py`) classifies them with
confidence >= config.BUYER_REPLY_MIN_CONFIDENCE. This exercises RESOLVE, APPLY
REPLY and RECONCILE without needing a real SAP feed.

Only appends rows — does not touch or clear existing data.

    python scripts/seed_sap_dummy_data.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loguru import logger  # noqa: E402

from non_conformities_resolution.resolution_rules import (  # noqa: E402
    ISSUE_AMOUNT_MISMATCH,
    ISSUE_MESSAGES,
    ISSUE_NO_MIGO,
    ISSUE_NO_PO,
    ISSUE_WRONG_VAT,
    STATUS_AUTO,
    STATUS_BUYER_REPLIED,
    STATUS_BY_AGENT,
    STATUS_MANUAL,
    STATUS_NEEDS_MANUAL,
    STATUS_NEW,
    STATUS_WITH_BUYER,
)
from utils.utils_db import insert_rows  # noqa: E402

NOW = datetime.now(timezone.utc)

SYSTEM = "system"


def _process(
    reference_no: str,
    *,
    supplier_id: str,
    bu_id: str,
    total_amount: float,
    status: str,
    issue: str | None,
    last_interaction: str | None = None,
    last_interaction_datetime: datetime | None = None,
    reconciled: bool | None = None,
) -> dict:
    return {
        "reference_no": reference_no,
        "supplier_id": supplier_id,
        "bu_id": bu_id,
        "total_amount": total_amount,
        "document_date": (NOW - timedelta(days=10)).date(),
        "is_financial": False,
        "last_interaction": last_interaction,
        "last_interaction_datetime": last_interaction_datetime,
        "status": status,
        "issue": issue,
        "owner": "agent",
        "reconciled": reconciled,
    }


def _message(
    internal_id: str, *, process_ref_no: str, content: str, sender: str, recipient: str, timestamp: datetime
) -> dict:
    return {
        "internal_id": internal_id,
        "timestamp": timestamp,
        "sender": sender,
        "recipient": recipient,
        "content": content,
        "process_ref_no": process_ref_no,
    }


def _buyer_email(supplier_id: str) -> str:
    return f"buyer{supplier_id}@example.com"


processes: list[dict] = [
    # -- STATUS_NEW: one per issue, picked up by RESOLVE on the next run -----
    _process(
        "SEED-NOPO-NEW",
        supplier_id="100000001",
        bu_id="0001",
        total_amount=1250.00,
        status=STATUS_NEW,
        issue=ISSUE_NO_PO,
    ),
    _process(
        "SEED-NOMIGO-NEW",
        supplier_id="100000002",
        bu_id="0001",
        total_amount=875.50,
        status=STATUS_NEW,
        issue=ISSUE_NO_MIGO,
    ),
    _process(
        "SEED-MISMATCH-NEW",
        supplier_id="100000003",
        bu_id="0002",
        total_amount=430.00,
        status=STATUS_NEW,
        issue=ISSUE_AMOUNT_MISMATCH,
    ),
    _process(
        "SEED-VAT-NEW",
        supplier_id="100000004",
        bu_id="0002",
        total_amount=99.90,
        status=STATUS_NEW,
        issue=ISSUE_WRONG_VAT,
    ),
    # -- STATUS_BUYER_REPLIED: picked up by RESOLVE -> APPLY REPLY -----------
    # last_interaction_datetime is in the past; the matching buyer reply below
    # is timestamped after it, as fetch_buyer_replies expects.
    _process(
        "SEED-NOPO-REPLIED",
        supplier_id="100000005",
        bu_id="0003",
        total_amount=2100.00,
        status=STATUS_BUYER_REPLIED,
        issue=ISSUE_NO_PO,
        last_interaction="agent",
        last_interaction_datetime=NOW - timedelta(days=2),
    ),
    _process(
        "SEED-NOMIGO-REPLIED",
        supplier_id="100000006",
        bu_id="0003",
        total_amount=560.00,
        status=STATUS_BUYER_REPLIED,
        issue=ISSUE_NO_MIGO,
        last_interaction="agent",
        last_interaction_datetime=NOW - timedelta(days=2),
    ),
    # amount-mismatch bypass: the one path that resolves cleanly end-to-end
    # (no MissingSapColumnError) -> should land on STATUS_BY_AGENT.
    _process(
        "SEED-MISMATCH-BYPASS",
        supplier_id="100000007",
        bu_id="0004",
        total_amount=610.25,
        status=STATUS_BUYER_REPLIED,
        issue=ISSUE_AMOUNT_MISMATCH,
        last_interaction="agent",
        last_interaction_datetime=NOW - timedelta(days=2),
    ),
    # amount-mismatch with a new PO number: hits update_process_po and raises
    # MissingSapColumnError (swallowed, logged) -- exercises that branch too.
    _process(
        "SEED-MISMATCH-NEWPO",
        supplier_id="100000008",
        bu_id="0004",
        total_amount=980.00,
        status=STATUS_BUYER_REPLIED,
        issue=ISSUE_AMOUNT_MISMATCH,
        last_interaction="agent",
        last_interaction_datetime=NOW - timedelta(days=2),
    ),
    # -- STATUS_WITH_BUYER: waiting on the buyer; RECONCILE should flip this
    # to STATUS_BUYER_REPLIED once it sees the newer buyer reply below.
    _process(
        "SEED-NOPO-WAITING",
        supplier_id="100000009",
        bu_id="0005",
        total_amount=340.00,
        status=STATUS_WITH_BUYER,
        issue=ISSUE_NO_PO,
        last_interaction="agent",
        last_interaction_datetime=NOW - timedelta(days=3),
    ),
    # -- reconciled outside the pipeline: RECONCILE should force STATUS_MANUAL
    _process(
        "SEED-RECONCILED-MANUAL",
        supplier_id="100000010",
        bu_id="0005",
        total_amount=75.00,
        status=STATUS_NEW,
        issue=ISSUE_NO_PO,
        reconciled=True,
    ),
    # -- already-terminal processes: static end states, nothing left to do,
    # no buyer conversation to seed.
    _process(
        "SEED-AUTO-01",
        supplier_id="100000011",
        bu_id="0006",
        total_amount=210.00,
        status=STATUS_AUTO,
        issue=None,
        last_interaction="sap",
        last_interaction_datetime=NOW - timedelta(days=5),
        reconciled=True,
    ),
    _process(
        "SEED-BYAGENT-01",
        supplier_id="100000012",
        bu_id="0006",
        total_amount=1180.40,
        status=STATUS_BY_AGENT,
        issue=ISSUE_AMOUNT_MISMATCH,
        last_interaction="agent",
        last_interaction_datetime=NOW - timedelta(days=4),
        reconciled=True,
    ),
    _process(
        "SEED-MANUAL-01",
        supplier_id="100000013",
        bu_id="0007",
        total_amount=305.75,
        status=STATUS_MANUAL,
        issue=ISSUE_NO_MIGO,
        last_interaction="buyer",
        last_interaction_datetime=NOW - timedelta(days=6),
        reconciled=True,
    ),
    # -- waiting for a human: RESOLVE fell through here (unclear issue / low
    # confidence reply / no handler); pipeline leaves it alone from now on.
    _process(
        "SEED-NEEDSMANUAL-01",
        supplier_id="100000014",
        bu_id="0007",
        total_amount=142.20,
        status=STATUS_NEEDS_MANUAL,
        issue=ISSUE_WRONG_VAT,
        last_interaction="agent",
        last_interaction_datetime=NOW - timedelta(days=1),
    ),
]

# For every process still waiting on a reply (STATUS_WITH_BUYER /
# STATUS_BUYER_REPLIED with a buyer reply below), also seed the system->buyer
# message the pipeline itself would have sent to open that conversation
# (see resolution_rules.ISSUE_MESSAGES), timestamped before last_interaction.
system_messages: list[dict] = [
    _message(
        f"SEED-MSG-SYS-{ref}",
        process_ref_no=ref,
        content=ISSUE_MESSAGES[issue],
        sender=SYSTEM,
        recipient=_buyer_email(supplier_id),
        timestamp=NOW - timedelta(days=2, hours=1),
    )
    for ref, issue, supplier_id in (
        ("SEED-NOPO-REPLIED", ISSUE_NO_PO, "100000005"),
        ("SEED-NOMIGO-REPLIED", ISSUE_NO_MIGO, "100000006"),
        ("SEED-MISMATCH-BYPASS", ISSUE_AMOUNT_MISMATCH, "100000007"),
        ("SEED-MISMATCH-NEWPO", ISSUE_AMOUNT_MISMATCH, "100000008"),
        ("SEED-NOPO-WAITING", ISSUE_NO_PO, "100000009"),
    )
]

buyer_reply_messages: list[dict] = [
    _message(
        "SEED-MSG-NOPO-REPLIED",
        process_ref_no="SEED-NOPO-REPLIED",
        content="Boa tarde, o numero da PC e 1234567890, obrigado.",
        sender=_buyer_email("100000005"),
        recipient=SYSTEM,
        timestamp=NOW - timedelta(days=1),
    ),
    _message(
        "SEED-MSG-NOMIGO-REPLIED",
        process_ref_no="SEED-NOMIGO-REPLIED",
        content="Ja fizemos a receçao efetuada no sistema, pode validar.",
        sender=_buyer_email("100000006"),
        recipient=SYSTEM,
        timestamp=NOW - timedelta(days=1),
    ),
    _message(
        "SEED-MSG-MISMATCH-BYPASS",
        process_ref_no="SEED-MISMATCH-BYPASS",
        content="Confirmo bypass do valor, pode avancar com o consumo.",
        sender=_buyer_email("100000007"),
        recipient=SYSTEM,
        timestamp=NOW - timedelta(days=1),
    ),
    _message(
        "SEED-MSG-MISMATCH-NEWPO",
        process_ref_no="SEED-MISMATCH-NEWPO",
        content="Pedido de compra alterado, novo PC 9876543210.",
        sender=_buyer_email("100000008"),
        recipient=SYSTEM,
        timestamp=NOW - timedelta(days=1),
    ),
    _message(
        "SEED-MSG-NOPO-WAITING",
        process_ref_no="SEED-NOPO-WAITING",
        content="Ainda estamos a confirmar o numero da PC com o fornecedor.",
        sender=_buyer_email("100000009"),
        recipient=SYSTEM,
        timestamp=NOW - timedelta(hours=6),
    ),
]

messages: list[dict] = system_messages + buyer_reply_messages


async def main() -> None:
    n_processes = await insert_rows("sap_processes", processes)
    n_messages = await insert_rows("sap_messages", messages)
    logger.info(f"Inserted {n_processes} sap_processes rows and {n_messages} sap_messages rows.")


if __name__ == "__main__":
    asyncio.run(main())
