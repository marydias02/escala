"""The invoice mailbox, built from settings.

One place turns `.env` into a `MailboxConfig`, so nothing further down reads
settings to find out which mailbox it is talking to. Payment matching has its
own equivalent; the two differ only in which address they name.
"""

from config.settings import settings
from email_core.graph_auth import GraphAppConfig, MailboxConfig
from email_core.graph_client import GraphMailboxClient


def graph_app() -> GraphAppConfig:
    """The app registration used for Graph. Shared with every other use case."""
    return GraphAppConfig(
        tenant_id=settings.GRAPH_TENANT_ID,
        client_id=settings.GRAPH_CLIENT_ID,
        client_secret=settings.GRAPH_CLIENT_SECRET,
    )


def invoice_mailbox() -> MailboxConfig:
    """The mailbox invoice extraction reads: `GRAPH_MAILBOX`, or `me` when delegated."""
    return MailboxConfig(app=graph_app(), address=settings.GRAPH_MAILBOX)


def invoice_client() -> GraphMailboxClient:
    """A Graph client bound to the invoice mailbox."""
    return GraphMailboxClient(invoice_mailbox())
