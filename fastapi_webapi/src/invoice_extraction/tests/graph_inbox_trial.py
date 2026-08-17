"""Trial: fetch a few emails from the signed-in user's own inbox via Graph.

Standalone script, same pattern as `lakehouse_access.py` — run directly to
sanity-check the Graph device-code auth and the raw fetch, independent of the
ingestion pipeline. Saves raw messages to `ORIGINAL_EMAILS_DIR` so a later run
of `email_pipeline.py` could, in principle, pick them up (once ingestion also
knows how to read the JSON shape instead of only `.msg` files — that wiring is
a follow-up, not part of this trial).

Run from `fastapi_webapi/`:
    python -m invoice_extraction.tests.graph_inbox_trial
"""

import asyncio

from loguru import logger

from invoice_extraction.config import ORIGINAL_EMAILS_DIR
from invoice_extraction.loading import fetch_inbox_emails

FETCH_LIMIT = 1


async def main() -> None:
    logger.info("Signing in to Microsoft Graph (device code)...")
    logger.info(f"Fetching up to {FETCH_LIMIT} message(s) from your own inbox")

    emails = await fetch_inbox_emails(ORIGINAL_EMAILS_DIR, limit=FETCH_LIMIT)

    logger.info(f"Fetched {len(emails)} email(s), raw copies saved under {ORIGINAL_EMAILS_DIR}")
    for email in emails:
        logger.info(
            f"  - {email.reception_date} | {email.sender_email} | {email.subject!r} "
            f"({len(email.attachments)} attachment(s))"
        )


if __name__ == "__main__":
    asyncio.run(main())
