"""Standalone pipeline: book every pending document into SAP, in bulk.

This is deliberately separate from `email_pipeline`. That pipeline only ever
sees documents at the moment their email is processed, but a document can also
reach `action = "Ingerir em SAP"` later — e.g. one routed to `MANUAL` (Validação
Manual) and only cleared for SAP after a human reviews it and flips its
`action`/`status` outside this codebase. This pipeline does not care how a row
got to `action = INGEST, status = "Criado"`; it just finds every such row and
books it.

Run standalone (`python sap_pipeline.py` / `asyncio.run(main())`), the same
convention as `email_pipeline`/`extraction_pipeline`/`ingestion_pipeline` —
there is no scheduler/cron in this repo yet, so this is invoked manually or by
whatever will eventually trigger it.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from invoice_extraction.decisions import INGEST
from invoice_extraction.invoice_utils.sap_sender import book_in_sap
from utils.utils_db import get_pool, select, update_column

DOCUMENTS_TABLE = "fct_documents"

STATUS_PENDING = "Criado"
STATUS_BOOKED = "Ingerido"


@dataclass
class SapBookingOutcome:
    document_id: str
    document_number: Optional[str]
    status: str


async def fetch_pending_documents() -> list[dict]:
    """Every fct_documents row ready to book: action = INGEST, status = "Criado"."""
    return await select(
        f"""
        SELECT document_id, document_type, document_content
        FROM {DOCUMENTS_TABLE}
        WHERE action = $1 AND status = $2
        """,
        [INGEST, STATUS_PENDING],
    )


def _document_number(document_content: Optional[dict]) -> Optional[str]:
    """Pull document_number back out of the stored {value, confidence} shape."""
    if not document_content:
        return None
    field = document_content.get("document_number")
    if not field:
        return None
    return field.get("value")


async def book_document(row: dict) -> SapBookingOutcome:
    """Book one already-persisted document and report the outcome (does not write)."""
    document_content = row.get("document_content") or {}
    document_number = _document_number(document_content)

    book_result = await book_in_sap(
        document_number=document_number,
        document_type=row.get("document_type") or "Unknown",
        document_content=document_content,
    )
    status = STATUS_BOOKED if book_result.status == "booked" else STATUS_PENDING
    return SapBookingOutcome(
        document_id=str(row["document_id"]), document_number=document_number, status=status
    )


async def run() -> list[SapBookingOutcome]:
    """Book every pending document and advance the ones that succeed. Isolates failures per row."""
    rows = await fetch_pending_documents()
    outcomes: list[SapBookingOutcome] = []

    for row in rows:
        try:
            outcome = await book_document(row)
        except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
            print(f"  ❌ {row['document_id']}: {type(exc).__name__}: {exc}")
            continue

        if outcome.status == STATUS_BOOKED:
            await update_column(
                DOCUMENTS_TABLE, "document_id", outcome.document_id, "status", outcome.status
            )
        outcomes.append(outcome)

    return outcomes


def print_summary(outcomes: list[SapBookingOutcome]) -> None:
    print("\n" + "=" * 70)
    print("SAP BOOKING")
    print("=" * 70)
    booked = sum(1 for o in outcomes if o.status == STATUS_BOOKED)
    print(f"  {booked}/{len(outcomes)} booked")
    for outcome in outcomes:
        marker = "✅" if outcome.status == STATUS_BOOKED else "⏳"
        print(f"  {marker} {outcome.document_id} (doc #{outcome.document_number})")


async def main() -> None:
    pool = await get_pool()
    try:
        outcomes = await run()
        print_summary(outcomes)
    finally:
        pool.terminate()


if __name__ == "__main__":
    asyncio.run(main())
