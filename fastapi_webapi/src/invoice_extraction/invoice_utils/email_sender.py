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

See https://learn.microsoft.com/en-us/graph/api/message-reply,
https://learn.microsoft.com/en-us/graph/api/message-forward and
https://learn.microsoft.com/en-us/graph/api/message-move.
"""

import asyncio
from dataclasses import dataclass
from typing import Literal, Optional

import httpx

from utils.graph_auth import GRAPH_BASE, get_graph_token, graph_user_path

MAX_SEND_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0


@dataclass
class SendResult:
    status: Literal["sent", "failed"]
    to: str
    subject: str
    error: Optional[str] = None


async def _post(url: str, json: dict) -> httpx.Response:
    """POST to Graph, retrying transient failures (5xx, timeouts, connection
    errors) with backoff. A 4xx is a permanent failure and raised immediately
    """
    token = await get_graph_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, headers=headers, json=json)
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500 or attempt == MAX_SEND_ATTEMPTS:
                raise
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == MAX_SEND_ATTEMPTS:
                raise

        await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise AssertionError("unreachable")  # loop always returns or raises


async def reply_to_supplier(message_id: str, subject: str, comment: str) -> SendResult:
    """Reply to the sender of `message_id` via Graph. `subject` is carried
    through to the SendResult/log only — Graph derives the actual reply
    subject (`Re: ...`) from the original message, not from anything passed
    here.
    """
    if not message_id:
        return SendResult(status="failed", to="", subject=subject, error="no message_id")

    try:
        await _post(
            f"{GRAPH_BASE}/{graph_user_path()}/messages/{message_id}/reply",
            {"comment": comment},
        )
    except httpx.HTTPStatusError as exc:
        return SendResult(
            status="failed",
            to="",
            subject=subject,
            error=f"{exc.response.status_code}: {exc.response.text}",
        )
    except Exception as exc:  # noqa: BLE001 - any failure here must not crash the pipeline
        return SendResult(status="failed", to="", subject=subject, error=str(exc))

    return SendResult(status="sent", to="", subject=subject)


async def forward_to_treasury(message_id: str, to: str, subject: str, comment: str) -> SendResult:
    """Forward `message_id` — with its original attachments, carried over by
    Graph automatically — to `to`. `subject` is carried through to the
    SendResult/log only — Graph derives the actual forwarded subject
    (`Fwd: ...`) from the original message, not from anything passed here.
    """
    if not message_id:
        return SendResult(status="failed", to=to, subject=subject, error="no message_id")
    if not to:
        return SendResult(status="failed", to=to, subject=subject, error="no recipient address")

    try:
        await _post(
            f"{GRAPH_BASE}/{graph_user_path()}/messages/{message_id}/forward",
            {"comment": comment, "toRecipients": [{"emailAddress": {"address": to}}]},
        )
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


async def archive_message(message_id: str) -> SendResult:
    """Move `message_id` to the Archive folder via Graph. `subject`/`to` on the
    returned SendResult are left blank — archiving has neither.
    """
    if not message_id:
        return SendResult(status="failed", to="", subject="", error="no message_id")

    try:
        await _post(
            f"{GRAPH_BASE}/{graph_user_path()}/messages/{message_id}/move",
            {"destinationId": "archive"},
        )
    except httpx.HTTPStatusError as exc:
        return SendResult(
            status="failed",
            to="",
            subject="",
            error=f"{exc.response.status_code}: {exc.response.text}",
        )
    except Exception as exc:  # noqa: BLE001 - any failure here must not crash the pipeline
        return SendResult(status="failed", to="", subject="", error=str(exc))

    return SendResult(status="sent", to="", subject="")
