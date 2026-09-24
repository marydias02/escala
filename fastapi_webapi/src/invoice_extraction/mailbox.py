"""The invoice mailbox, built from settings.

One place turns `.env` into a `MailboxConfig`, so nothing further down reads
settings to find out which mailbox it is talking to.
"""

from config.settings import settings
from email_core.graph_auth import MailboxConfig, graph_app_from_settings
from email_core.graph_client import GraphMailboxClient


def invoice_mailbox() -> MailboxConfig:
    """The mailbox invoice extraction reads: `GRAPH_MAILBOX`, or `me` when delegated."""
    return MailboxConfig(app=graph_app_from_settings(), address=settings.GRAPH_MAILBOX)


def invoice_client() -> GraphMailboxClient:
    """A Graph client bound to the invoice mailbox."""
    return GraphMailboxClient(invoice_mailbox())
