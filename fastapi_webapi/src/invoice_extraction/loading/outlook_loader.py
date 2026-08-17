"""Fetch emails from a live Outlook inbox via Microsoft Graph.

Live counterpart to `msg_loader.py`: instead of parsing `.msg` files already on
disk, this hits Microsoft Graph directly and produces the same `LoadedEmail`
shape, so the rest of the pipeline (ingestion, extraction) doesn't care which
loader an email came from.

Auth is delegated (device-code sign-in as the calling user), scoped to
`Mail.Read`, via `invoice_extraction.loading.graph_auth`. This only ever reads
`/me/messages` — the signed-in user's own mailbox — which is the trial scope.
Reading another mailbox (e.g. a shared Grupo Sousa inbox) needs application
permissions and client-credentials auth instead; that's a later phase.
"""

import json
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

import httpx

from invoice_extraction.loading.graph_auth import get_graph_token
from invoice_extraction.models import EmailAttachment, LoadedEmail

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_MESSAGE_SELECT = ",".join(
    [
        "id",
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


def _received_date_iso(message: dict) -> str:
    raw = message.get("receivedDateTime") or ""
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return raw


async def _list_messages(client: httpx.AsyncClient, headers: dict, top: int) -> list[dict]:
    params = {"$top": str(top), "$select": _MESSAGE_SELECT, "$orderby": "receivedDateTime DESC"}
    response = await client.get(f"{GRAPH_BASE}/me/messages", headers=headers, params=params)
    response.raise_for_status()
    return response.json().get("value", [])


async def _list_attachments(client: httpx.AsyncClient, headers: dict, message_id: str) -> list[EmailAttachment]:
    params = {"$select": "id,name,contentType,isInline"}
    response = await client.get(
        f"{GRAPH_BASE}/me/messages/{message_id}/attachments", headers=headers, params=params
    )
    response.raise_for_status()

    attachments: list[EmailAttachment] = []
    for item in response.json().get("value", []):
        if item.get("isInline"):
            continue
        odata_type = item.get("@odata.type", "")
        if odata_type != "#microsoft.graph.fileAttachment":
            # Item/reference attachments have no downloadable bytes in this call.
            continue

        detail = await client.get(
            f"{GRAPH_BASE}/me/messages/{message_id}/attachments/{item['id']}",
            headers=headers,
        )
        detail.raise_for_status()
        content_bytes = detail.json().get("contentBytes")
        if not content_bytes:
            continue

        import base64

        filename = item.get("name") or "attachment"
        attachments.append(EmailAttachment(filename=filename, data=base64.b64decode(content_bytes)))

    return attachments


def _save_raw_message(message: dict, out_dir: Path) -> Path:
    """Persist the raw Graph payload, matching the "as if a fetch step had just
    deposited them" role that `.msg` files play for `msg_loader.py`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = out_dir / f"{timestamp}_{message['id'][:16]}.json"
    out_path.write_text(json.dumps(message, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


async def fetch_inbox_emails(out_dir: Path, limit: int = 5) -> list[LoadedEmail]:
    """Fetch the most recent `limit` messages from the signed-in user's own inbox.

    Each raw Graph message is saved to `out_dir` (mirroring `ORIGINAL_EMAILS_DIR`'s
    role for `.msg` files) and parsed into a `LoadedEmail` for the pipeline.
    """
    token = await get_graph_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    loaded_emails: list[LoadedEmail] = []
    async with httpx.AsyncClient(timeout=60) as client:
        messages = await _list_messages(client, headers, top=limit)

        for message in messages:
            _save_raw_message(message, out_dir)

            attachments: list[EmailAttachment] = []
            if message.get("hasAttachments"):
                attachments = await _list_attachments(client, headers, message["id"])

            body = (message.get("body") or {}).get("content") or ""
            loaded_emails.append(
                LoadedEmail(
                    sender_email=_extract_email_address(message.get("from")),
                    subject=(message.get("subject") or "").strip(),
                    body=body,
                    reception_date=_received_date_iso(message),
                    attachments=attachments,
                )
            )

    return loaded_emails
