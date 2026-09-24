"""Every Microsoft Graph mailbox call, bound to one mailbox.

Reading (delta sync, message fetch, attachments) and the write operations the
invoice pipeline needs (reply, forward, archive) both live here, because they
are the same resource under the same auth — splitting them would mean two places
deciding which mailbox a request targets.

The mailbox is the instance's own `MailboxConfig`, so two clients can read two
mailboxes in one process. That is the whole point of this class: the previous
module-level functions built every URL from a global that named a single
mailbox, which made a second use case impossible.

Nothing is persisted here — the mailbox itself is the durable copy. Each message
is read straight into memory and handed off; dedup is the caller's job, against
whatever table it records messages in.
"""

import asyncio
import re
from datetime import UTC, datetime
from email.utils import parseaddr
from pathlib import Path

import httpx
from loguru import logger

from email_core.attachments import expand_zip
from email_core.graph_auth import GRAPH_BASE, MailboxConfig, auth_headers, with_prefer
from email_core.models import EmailAttachment, LoadedEmail

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

MAX_SEND_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0


class DeltaResyncRequired(Exception):
    """Graph answered 410 Gone: the stored delta token has expired.

    The caller drops `sync_url` and restarts from an initial call filtered on
    the last received date; messages replayed that way are already recorded, so
    they hit the ON CONFLICT and vanish.
    """


def _extract_email_address(sender: dict | None) -> str:
    """Reduce a Graph `from` field to the bare email address.

    Graph already gives structured from/emailAddress/address, but falls back to
    parsing a raw string the same way in case that shape is ever missing.
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


def _to_loaded_email(message: dict, attachments: list[EmailAttachment]) -> LoadedEmail:
    return LoadedEmail(
        sender_email=_extract_email_address(message.get("from")),
        subject=(message.get("subject") or "").strip(),
        body=_collapse_blank_lines((message.get("body") or {}).get("content") or ""),
        reception_date=_received_date_iso(message),
        attachments=attachments,
        message_id=message["id"],
        thread_id=message.get("conversationId") or "",
    )


class GraphMailboxClient:
    """Graph operations against the one mailbox named by `mailbox`.

    Build one per mailbox. Credentials are cached per app registration inside
    `graph_auth`, so several clients on one registration share a token.
    """

    def __init__(self, mailbox: MailboxConfig):
        self.mailbox = mailbox

    @property
    def base(self) -> str:
        """`https://graph.microsoft.com/v1.0/users/{mailbox}` — the root of every request."""
        return f"{GRAPH_BASE}/{self.mailbox.user_path}"

    async def auth_headers(self) -> dict[str, str]:
        """Bearer + immutable-id headers for this mailbox's app registration."""
        return await auth_headers(self.mailbox.app)

    # -- reading -----------------------------------------------------------

    async def _graph_get_paged(
        self, client: httpx.AsyncClient, headers: dict, url: str, params: dict | None = None
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

    async def _fetch_attachment_bytes(
        self, client: httpx.AsyncClient, headers: dict, message_id: str, attachment_id: str
    ) -> bytes:
        response = await client.get(
            f"{self.base}/messages/{message_id}/attachments/{attachment_id}/$value",
            headers=headers,
        )
        response.raise_for_status()
        return response.content

    async def list_attachments(
        self, client: httpx.AsyncClient, headers: dict, message_id: str
    ) -> list[EmailAttachment]:
        """Real annexes only, with zips expanded in place.

        Attachments with no filename or no extension are dropped: without a name
        there is no reliable way to tell a document from body decoration.
        """
        params = {"$select": "id,name,contentType,isInline"}
        items = await self._graph_get_paged(
            client, headers, f"{self.base}/messages/{message_id}/attachments", params
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

            data = await self._fetch_attachment_bytes(client, headers, message_id, item["id"])
            if not data:
                continue

            if filename.lower().endswith(".zip"):
                attachments.extend(expand_zip(filename, data))
            else:
                attachments.append(EmailAttachment(filename=filename, data=data))

        return attachments

    async def fetch_delta_page(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        url: str | None,
        *,
        since: datetime,
        page_size: int,
        folder: str = "inbox",
    ) -> tuple[list[dict], str | None, bool]:
        """One page of the mailbox delta query: `(entries, next_url, is_delta_link)`.

        `url` is a stored `@odata.nextLink`/`@odata.deltaLink` — both opaque and
        already carrying their own query — or None to start an initial call bounded
        by `since`. Metadata only: no body and no attachments, so a page stays cheap.

        `is_delta_link` marks the end of the stream; the returned url is then the
        cursor to resume from on the next run rather than a page to fetch now.
        Raises `DeltaResyncRequired` on the 410 an expired token produces.
        """
        page_headers = with_prefer(headers, f"odata.maxpagesize={page_size}")

        if url is None:
            request_url = f"{self.base}/mailFolders/{folder}/messages/delta"
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

    async def fetch_message(
        self, client: httpx.AsyncClient, headers: dict, message_id: str
    ) -> LoadedEmail | None:
        """One full message — body and attachments — by id, or None if it is gone.

        None means Graph answered 404: a human deleted or moved the message out of
        reach between the delta page recording it and this call.
        """
        message_headers = with_prefer(headers, 'outlook.body-content-type="text"')
        response = await client.get(
            f"{self.base}/messages/{message_id}",
            headers=message_headers,
            params={"$select": _MESSAGE_SELECT},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        message = response.json()

        attachments: list[EmailAttachment] = []
        if message.get("hasAttachments"):
            attachments = await self.list_attachments(client, headers, message_id)

        # `id` is absent from this $select, so carry the id the caller asked for.
        message.setdefault("id", message_id)
        return _to_loaded_email(message, attachments)

    async def fetch_recent(
        self,
        limit: int,
        skip_message_ids: set[str] | None = None,
        *,
        folder: str = "inbox",
    ) -> list[LoadedEmail]:
        """The most recent `limit` messages, returned oldest first.

        Messages whose id is in `skip_message_ids` are skipped before their
        attachments are downloaded — that's the expensive part this avoids for
        already-processed mail. Nothing is written to disk.
        """
        skip_message_ids = skip_message_ids or set()
        headers = await self.auth_headers()
        list_headers = with_prefer(headers, 'outlook.body-content-type="text"')

        loaded_emails: list[LoadedEmail] = []
        skipped = 0
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{self.base}/mailFolders/{folder}/messages",
                headers=list_headers,
                params={
                    "$top": str(limit),
                    "$select": _MESSAGE_SELECT,
                    "$orderby": "receivedDateTime DESC",
                },
            )
            response.raise_for_status()
            messages = response.json().get("value", [])
            messages.reverse()

            for message in messages:
                if message["id"] in skip_message_ids:
                    skipped += 1
                    continue

                attachments: list[EmailAttachment] = []
                if message.get("hasAttachments"):
                    attachments = await self.list_attachments(client, headers, message["id"])

                loaded_emails.append(_to_loaded_email(message, attachments))

        logger.info(
            f"[{self.mailbox.label}] Fetched {len(messages)} message(s): "
            f"{skipped} skipped (already processed), {len(loaded_emails)} new"
        )
        return loaded_emails

    # -- writing -----------------------------------------------------------

    async def post(self, path: str, json: dict) -> httpx.Response:
        """POST to a path under this mailbox, retrying transient failures.

        5xx, timeouts and connection errors are retried with backoff; a 4xx is a
        permanent failure and raised immediately.
        """
        headers = await self.auth_headers()
        headers["Content-Type"] = "application/json"
        url = f"{self.base}/{path}"

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
