"""Trial: fetch a few emails from the signed-in user's own inbox via Graph.

Standalone script, same pattern as `lakehouse_access.py` — run directly to
sanity-check the Graph device-code auth and the raw fetch, independent of the
ingestion pipeline. Nothing is persisted; each email lives only in memory for
the duration of this run.

Run from `fastapi_webapi/`:
    python -m invoice_extraction.tests.graph_inbox_trial
"""

import asyncio

from loguru import logger

from invoice_extraction.invoice_utils.outlook_loader import fetch_inbox_emails

FETCH_LIMIT = 1


async def main() -> None:
    logger.info("Signing in to Microsoft Graph (device code)...")
    logger.info(f"Fetching up to {FETCH_LIMIT} message(s) from your own inbox")

    emails = await fetch_inbox_emails(limit=FETCH_LIMIT)

    logger.info(f"Fetched {len(emails)} email(s)")
    for email in emails:
        logger.info(
            f"  - {email.reception_date} | {email.sender_email} | {email.subject!r} "
            f"({len(email.attachments)} attachment(s))"
        )


if __name__ == "__main__":
    asyncio.run(main())
