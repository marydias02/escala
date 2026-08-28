"""Fetch emails from a live Outlook inbox via Microsoft Graph.

Live counterpart to `msg_loader.py` (deleted — see the ingestion wiring plan):
hits Microsoft Graph directly and produces the same `LoadedEmail` shape, so the
rest of the pipeline (ingestion, extraction) doesn't care which loader an email
came from.

Nothing is persisted here — the inbox itself is the durable copy. Each message
is read straight into memory and handed off; dedup is by `message_id` against
`fct_processes`, not by anything written to disk.

Auth (delegated device-code, or app-only client-credentials) is via
`utils.graph_auth`; `graph_user_path()` there resolves whether requests target
`/me/` or `/users/{mailbox}/`.
"""

import re
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path

import httpx
from loguru import logger

from invoice_extraction.invoice_utils.attachments import _expand_zip
from invoice_extraction.models import EmailAttachment, LoadedEmail
from utils.graph_auth import GRAPH_BASE, get_graph_token, graph_user_path

_MESSAGE_SELECT = ",".join(
    [
        "id",
        "conversationId",
        "subject",
        "from",
        "receivedDateTime",
        "hasAttachments",
        "body",
    ]
)


def _extract_email_address(sender: dict | None) -> str:
    """Reduce a Graph `from` field to the bare email address.

    Mirrors `msg_loader._extract_email_address`: Graph already gives structured
    from/emailAddress/address, but falls back to parsing a raw string the same
    way in case that shape is ever missing.
    """
    if not sender:
        return ""
    address = ((sender.get("emailAddress") or {}).get("address") or "").strip()
    if address:
        return address
    _, parsed = parseaddr(str(sender))
    return parsed.strip()


def _collapse_blank_lines(text: str) -> str:
    """Squash runs of consecutive newlines down to a single one, for readability."""
    return re.sub(r"\n{2,}", "\n", text.replace("\r\n", "\n"))


def _received_date_iso(message: dict) -> str:
    raw = message.get("receivedDateTime") or ""
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return raw


async def _graph_get_paged(
    client: httpx.AsyncClient, headers: dict, url: str, params: dict | None = None
) -> list[dict]:
    """GET `url`, following `@odata.nextLink` until exhausted.

    `params` is only sent on the first request — `nextLink` is an absolute URL
    that already carries its own query string, so later requests pass none.
    """
    out: list[dict] = []
    next_url: str | None = url
    while next_url:
        response = await client.get(next_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        out.extend(data.get("value", []))
        next_url = data.get("@odata.nextLink")
        params = None
    return out


async def _list_messages(client: httpx.AsyncClient, headers: dict, top: int) -> list[dict]:
    params = {"$top": str(top), "$select": _MESSAGE_SELECT, "$orderby": "receivedDateTime DESC"}
    list_headers = {**headers, "Prefer": 'outlook.body-content-type="text"'}
    response = await client.get(
        f"{GRAPH_BASE}/{graph_user_path()}/mailFolders/inbox/messages",
        headers=list_headers,
        params=params,
    )
    response.raise_for_status()
    return response.json().get("value", [])


async def _fetch_attachment_bytes(client: httpx.AsyncClient, headers: dict, message_id: str, attachment_id: str) -> bytes:
    response = await client.get(
        f"{GRAPH_BASE}/{graph_user_path()}/messages/{message_id}/attachments/{attachment_id}/$value",
        headers=headers,
    )
    response.raise_for_status()
    return response.content


async def _list_attachments(client: httpx.AsyncClient, headers: dict, message_id: str) -> list[EmailAttachment]:
    """Real annexes only, with zips expanded in place.

    Attachments with no filename or no extension are dropped, mirroring
    `msg_loader._collect_attachments`: without a name there is no reliable way
    to tell a document from body decoration.
    """
    params = {"$select": "id,name,contentType,isInline"}
    items = await _graph_get_paged(
        client, headers, f"{GRAPH_BASE}/{graph_user_path()}/messages/{message_id}/attachments", params
    )

    attachments: list[EmailAttachment] = []
    for item in items:
        if item.get("isInline"):
            continue
        if item.get("@odata.type") != "#microsoft.graph.fileAttachment":
            # Item/reference attachments have no downloadable bytes.
            continue

        filename = (item.get("name") or "").strip()
        if not filename or not Path(filename).suffix:
            continue

        data = await _fetch_attachment_bytes(client, headers, message_id, item["id"])
        if not data:
            continue

        if filename.lower().endswith(".zip"):
            attachments.extend(_expand_zip(filename, data))
        else:
            attachments.append(EmailAttachment(filename=filename, data=data))

    return attachments


async def fetch_inbox_emails(
    limit: int, skip_message_ids: set[str] | None = None
) -> list[LoadedEmail]:
    """Fetch the most recent `limit` messages from the inbox, newest first.

    Messages whose id is in `skip_message_ids` are skipped before their
    attachments are downloaded — that's the expensive part this avoids for
    already-processed mail. Nothing is written to disk; each `LoadedEmail`
    lives only in memory until the caller (ingestion) writes its output.
    """
    skip_message_ids = skip_message_ids or set()
    token = await get_graph_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    loaded_emails: list[LoadedEmail] = []
    skipped = 0
    async with httpx.AsyncClient(timeout=60) as client:
        messages = await _list_messages(client, headers, top=limit)

        for message in messages:
            message_id = message["id"]
            if message_id in skip_message_ids:
                skipped += 1
                continue

            attachments: list[EmailAttachment] = []
            if message.get("hasAttachments"):
                attachments = await _list_attachments(client, headers, message_id)

            body = _collapse_blank_lines((message.get("body") or {}).get("content") or "")
            loaded_emails.append(
                LoadedEmail(
                    sender_email=_extract_email_address(message.get("from")),
                    subject=(message.get("subject") or "").strip(),
                    body=body,
                    reception_date=_received_date_iso(message),
                    attachments=attachments,
                    message_id=message_id,
                    thread_id=message.get("conversationId") or "",
                )
            )

    logger.info(
        f"Fetched {len(messages)} message(s): {skipped} skipped (already processed), "
        f"{len(loaded_emails)} new"
    )
    return loaded_emails
