"""Outbound email — supplier replies and treasury forwards.

Stub today: no Mail.Send permission exists yet (only delegated Mail.Read is
granted — see invoice_extraction.loading.graph_auth /
invoice_extraction.loading.outlook_loader). send_email logs what it would
send and returns a SendResult so callers can already branch on success/failure
before the real Microsoft Graph sendMail call exists.
"""

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class SendResult:
    status: Literal["sent", "failed"]
    to: str
    subject: str
    error: Optional[str] = None


async def send_email(to: str, subject: str, body: str) -> SendResult:
    """Send one email. STUB: logs the message, always returns status="sent"."""
    print(f"  📧 [STUB] would send email to={to!r} subject={subject!r}")
    print(f"            body={body!r}")
    return SendResult(status="sent", to=to, subject=subject)
