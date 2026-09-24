"""The payments mailbox, built from settings.

Same app registration as invoice extraction — `GraphAppConfig` compares equal,
so the two share one cached credential — differing only in the address read.
"""

from config.settings import settings
from email_core.graph_auth import MailboxConfig, graph_app_from_settings
from email_core.graph_client import GraphMailboxClient


def payment_mailbox() -> MailboxConfig:
    """The mailbox payment matching reads: `PAYMENT_GRAPH_MAILBOX`."""
    return MailboxConfig(app=graph_app_from_settings(), address=settings.PAYMENT_GRAPH_MAILBOX)


def payment_client() -> GraphMailboxClient:
    """A Graph client bound to the payments mailbox."""
    return GraphMailboxClient(payment_mailbox())
