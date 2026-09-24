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

from email_core.graph_client import GraphMailboxClient
from invoice_extraction.mailbox import invoice_mailbox

FETCH_LIMIT = 1


async def _diagnose(mailbox_client: GraphMailboxClient) -> None:
    path = mailbox_client.mailbox.user_path
    logger.info(f"Mailbox address: {mailbox_client.mailbox.address!r}")
    logger.info(f"Resolved Graph path: {path!r}")
    logger.info(f"App-only auth: {mailbox_client.mailbox.app.is_app_only}")

    headers = await mailbox_client.auth_headers()

    async with httpx.AsyncClient(timeout=30) as client:
        # Inbox folder metadata - item counts independent of the messages query.
        folder_resp = await client.get(f"{mailbox_client.base}/mailFolders/inbox", headers=headers)
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
            f"{mailbox_client.base}/mailFolders/inbox/messages",
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
    mailbox_client = GraphMailboxClient(invoice_mailbox())
    await _diagnose(mailbox_client)

    logger.info(f"Fetching up to {FETCH_LIMIT} message(s) from the inbox")

    emails = await mailbox_client.fetch_recent(limit=FETCH_LIMIT)

    logger.info(f"Fetched {len(emails)} email(s)")
    for email in emails:
        logger.info(
            f"  - {email.reception_date} | {email.sender_email} | {email.subject!r} "
            f"({len(email.attachments)} attachment(s))"
        )


if __name__ == "__main__":
    asyncio.run(main())
