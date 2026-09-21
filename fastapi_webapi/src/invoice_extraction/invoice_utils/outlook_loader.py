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
from datetime import UTC, datetime
from email.utils import parseaddr
from pathlib import Path

import httpx
from loguru import logger

from invoice_extraction.invoice_utils.attachments import _expand_zip
from invoice_extraction.models import EmailAttachment, LoadedEmail
from utils.graph_auth import GRAPH_BASE, IMMUTABLE_ID_PREFER, get_graph_token, graph_user_path

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

# The delta page is metadata only — enough to record the message and order it.
_DELTA_SELECT = ",".join(
    [
        "id",
        "conversationId",
        "receivedDateTime",
        "from",
        "subject",
        "hasAttachments",
    ]
)


async def auth_headers() -> dict[str, str]:
    """Bearer + immutable-id headers, the base for every request in this module."""
    token = await get_graph_token()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Prefer": IMMUTABLE_ID_PREFER,
    }


def _with_prefer(headers: dict[str, str], preference: str) -> dict[str, str]:
    """Add a Prefer value, keeping the immutable-id one — Graph takes them comma-separated."""
    return {**headers, "Prefer": f"{headers['Prefer']}, {preference}"}


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
    list_headers = _with_prefer(headers, 'outlook.body-content-type="text"')
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


class DeltaResyncRequired(Exception):
    """Graph answered 410 Gone: the stored delta token has expired.

    The caller drops `sync_url` and restarts from an initial call filtered on
    the last received date; messages replayed that way are already recorded, so
    they hit the ON CONFLICT and vanish.
    """


async def fetch_inbox_delta_page(
    client: httpx.AsyncClient,
    headers: dict,
    url: str | None,
    *,
    since: datetime,
    page_size: int,
) -> tuple[list[dict], str | None, bool]:
    """One page of the inbox delta query: `(entries, next_url, is_delta_link)`.

    `url` is a stored `@odata.nextLink`/`@odata.deltaLink` — both opaque and
    already carrying their own query — or None to start an initial call bounded
    by `since`. Metadata only: no body and no attachments, so a page stays cheap.

    `is_delta_link` marks the end of the stream; the returned url is then the
    cursor to resume from on the next run rather than a page to fetch now.
    Raises `DeltaResyncRequired` on the 410 an expired token produces.
    """
    page_headers = _with_prefer(headers, f"odata.maxpagesize={page_size}")

    if url is None:
        request_url = f"{GRAPH_BASE}/{graph_user_path()}/mailFolders/inbox/messages/delta"
        params = {
            "$select": _DELTA_SELECT,
            "$filter": f"receivedDateTime ge {since.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        }
    else:
        request_url = url
        params = None

    response = await client.get(request_url, headers=page_headers, params=params)
    if response.status_code == 410:
        raise DeltaResyncRequired(response.text)
    response.raise_for_status()

    data = response.json()
    delta_link = data.get("@odata.deltaLink")
    next_link = data.get("@odata.nextLink")
    return data.get("value", []), delta_link or next_link, delta_link is not None


async def fetch_message(client: httpx.AsyncClient, headers: dict, message_id: str) -> LoadedEmail | None:
    """One full message — body and attachments — by id, or None if it is gone.

    None means Graph answered 404: a human deleted or moved the message out of
    reach between the delta page recording it and this call.
    """
    message_headers = _with_prefer(headers, 'outlook.body-content-type="text"')
    response = await client.get(
        f"{GRAPH_BASE}/{graph_user_path()}/messages/{message_id}",
        headers=message_headers,
        params={"$select": _MESSAGE_SELECT},
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    message = response.json()

    attachments: list[EmailAttachment] = []
    if message.get("hasAttachments"):
        attachments = await _list_attachments(client, headers, message_id)

    return LoadedEmail(
        sender_email=_extract_email_address(message.get("from")),
        subject=(message.get("subject") or "").strip(),
        body=_collapse_blank_lines((message.get("body") or {}).get("content") or ""),
        reception_date=_received_date_iso(message),
        attachments=attachments,
        message_id=message_id,
        thread_id=message.get("conversationId") or "",
    )


async def fetch_inbox_emails(
    limit: int, skip_message_ids: set[str] | None = None
) -> list[LoadedEmail]:
    """Fetch the most recent `limit` messages from the inbox, then process oldest first.

    Messages whose id is in `skip_message_ids` are skipped before their
    attachments are downloaded — that's the expensive part this avoids for
    already-processed mail. Nothing is written to disk; each `LoadedEmail`
    lives only in memory until the caller (ingestion) writes its output.
    """
    skip_message_ids = skip_message_ids or set()
    headers = await auth_headers()

    loaded_emails: list[LoadedEmail] = []
    skipped = 0
    async with httpx.AsyncClient(timeout=60) as client:
        messages = await _list_messages(client, headers, top=limit)
        messages.reverse()

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
