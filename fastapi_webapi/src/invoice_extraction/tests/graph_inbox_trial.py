"""Trial: fetch a few emails from the signed-in user's own inbox via Graph.

Standalone script, same pattern as `lakehouse_access.py` — run directly to
sanity-check the Graph device-code auth and the raw fetch, independent of the
ingestion pipeline. Nothing is persisted; each email lives only in memory for
the duration of this run.

Starts with a diagnostic pass straight against Graph (inbox folder item
counts, then a filter-free message listing) so a 0-result fetch below can be
told apart from an empty inbox, a wrong `GRAPH_MAILBOX`, or a permissions
problem. Only hits endpoints covered by Mail.Read/Mail.ReadWrite — no
/users/{mailbox} profile lookup, since that needs User.Read.All/
Directory.Read.All and 403s even when mail access is fine.

Run from `fastapi_webapi/`:
    python -m invoice_extraction.tests.graph_inbox_trial
"""

import asyncio

import httpx
from loguru import logger

from config.settings import settings
from invoice_extraction.invoice_utils.outlook_loader import fetch_inbox_emails
from utils.graph_auth import GRAPH_BASE, get_graph_token, graph_user_path

FETCH_LIMIT = 1


async def _diagnose() -> None:
    mailbox = settings.GRAPH_MAILBOX
    path = graph_user_path()
    logger.info(f"GRAPH_MAILBOX setting: {mailbox!r}")
    logger.info(f"Resolved Graph path: {path!r}")

    token = await get_graph_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=30) as client:
        # Inbox folder metadata - item counts independent of the messages query.
        folder_resp = await client.get(f"{GRAPH_BASE}/{path}/mailFolders/inbox", headers=headers)
        logger.info(f"GET /{path}/mailFolders/inbox -> {folder_resp.status_code}")
        if folder_resp.status_code == 200:
            folder_data = folder_resp.json()
            logger.info(
                f"  totalItemCount={folder_data.get('totalItemCount')} "
                f"unreadItemCount={folder_data.get('unreadItemCount')}"
            )
        else:
            logger.error(f"Inbox folder lookup failed: {folder_resp.text}")

        # Raw, filter-free message listing.
        msg_resp = await client.get(
            f"{GRAPH_BASE}/{path}/mailFolders/inbox/messages",
            headers=headers,
            params={"$top": "5", "$select": "subject,receivedDateTime,from"},
        )
        logger.info(f"GET /{path}/mailFolders/inbox/messages -> {msg_resp.status_code}")
        if msg_resp.status_code == 200:
            values = msg_resp.json().get("value", [])
            logger.info(f"  {len(values)} message(s) returned")
            for m in values:
                sender = (m.get("from") or {}).get("emailAddress", {}).get("address")
                logger.info(f"    - {m.get('receivedDateTime')} | {sender} | {m.get('subject')!r}")
        else:
            logger.error(f"Message listing failed: {msg_resp.text}")


async def main() -> None:
    await _diagnose()

    logger.info(f"Fetching up to {FETCH_LIMIT} message(s) from the inbox")

    emails = await fetch_inbox_emails(limit=FETCH_LIMIT)

    logger.info(f"Fetched {len(emails)} email(s)")
    for email in emails:
        logger.info(
            f"  - {email.reception_date} | {email.sender_email} | {email.subject!r} "
            f"({len(email.attachments)} attachment(s))"
        )


if __name__ == "__main__":
    asyncio.run(main())
