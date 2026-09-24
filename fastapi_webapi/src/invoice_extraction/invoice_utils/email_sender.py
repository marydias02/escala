"""Outbound email — supplier replies and treasury forwards, via Microsoft Graph
`reply` / `forward` on the original message.

Both act on the message the email pipeline already read (`message_id`, saved
in the manifest), not a freshly composed one:

- `reply_to_supplier` -> `POST /messages/{id}/reply`, addressed back to the
  original sender automatically (Graph reads it off the message being replied
  to), threaded, subject prefixed `Re:` by Graph itself.
- `forward_to_treasury` -> `POST /messages/{id}/forward`, which carries the
  original attachments along automatically — the receipts treasury needs are
  already on the source message, so nothing is re-attached here.
- `archive_message` -> `POST /messages/{id}/move` to the well-known `archive`
  folder. Well-known folder names (`archive`, `inbox`, `deleteditems`, ...) are
  valid `destinationId` values directly — no folder-id lookup needed.

`comment` in both requests is a short note Graph inserts above the original
message, which it quotes below automatically — not a full replacement body
(only `/reply` even offers that, via `message.body`, and `/forward` has no
equivalent), so the supplier/treasury see our note plus the original message
for context, same as any manual reply/forward.

Each function takes the `GraphMailboxClient` to act through, which is what binds
the request to a mailbox; the client also owns the POST retry.

See https://learn.microsoft.com/en-us/graph/api/message-reply,
https://learn.microsoft.com/en-us/graph/api/message-forward and
https://learn.microsoft.com/en-us/graph/api/message-move.
"""

import html
from dataclasses import dataclass
from typing import Literal, Optional

import httpx

from email_core.graph_client import GraphMailboxClient


@dataclass
class SendResult:
    status: Literal["sent", "failed"]
    to: str
    subject: str
    error: Optional[str] = None


def _as_html(text: str) -> str:
    """Graph inserts `comment` into an HTML body, so newlines collapse without <br>."""
    return html.escape(text).replace("\n", "<br>")


async def _send(client: GraphMailboxClient, path: str, payload: dict, *, to: str, subject: str) -> SendResult:
    """POST one message action, turning any failure into a `failed` SendResult.

    Nothing raised here may reach the pipeline: a send that fails leaves the
    document at its pre-send status, which is a recoverable outcome, whereas an
    exception would lose the whole email.
    """
    try:
        await client.post(path, payload)
    except httpx.HTTPStatusError as exc:
        return SendResult(
            status="failed",
            to=to,
            subject=subject,
            error=f"{exc.response.status_code}: {exc.response.text}",
        )
    except Exception as exc:  # noqa: BLE001 - any failure here must not crash the pipeline
        return SendResult(status="failed", to=to, subject=subject, error=str(exc))

    return SendResult(status="sent", to=to, subject=subject)


async def reply_to_supplier(
    client: GraphMailboxClient, message_id: str, subject: str, comment: str
) -> SendResult:
    """Reply to the sender of `message_id` via Graph. `subject` is carried
    through to the SendResult/log only — Graph derives the actual reply
    subject (`Re: ...`) from the original message, not from anything passed
    here.
    """
    if not message_id:
        return SendResult(status="failed", to="", subject=subject, error="no message_id")

    return await _send(
        client,
        f"messages/{message_id}/reply",
        {"comment": _as_html(comment)},
        to="",
        subject=subject,
    )


async def forward_to_treasury(
    client: GraphMailboxClient, message_id: str, to: str, subject: str, comment: str
) -> SendResult:
    """Forward `message_id` — with its original attachments, carried over by
    Graph automatically — to `to`. `subject` is carried through to the
    SendResult/log only — Graph derives the actual forwarded subject
    (`Fwd: ...`) from the original message, not from anything passed here.
    """
    if not message_id:
        return SendResult(status="failed", to=to, subject=subject, error="no message_id")
    if not to:
        return SendResult(status="failed", to=to, subject=subject, error="no recipient address")

    return await _send(
        client,
        f"messages/{message_id}/forward",
        {"comment": _as_html(comment), "toRecipients": [{"emailAddress": {"address": to}}]},
        to=to,
        subject=subject,
    )


async def archive_message(client: GraphMailboxClient, message_id: str) -> SendResult:
    """Move `message_id` to the Archive folder via Graph. `subject`/`to` on the
    returned SendResult are left blank — archiving has neither.
    """
    if not message_id:
        return SendResult(status="failed", to="", subject="", error="no message_id")

    return await _send(
        client,
        f"messages/{message_id}/move",
        {"destinationId": "archive"},
        to="",
        subject="",
    )
