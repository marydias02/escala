"""Microsoft Graph sign-in, and which mailbox a caller is reading.

Delegated (`DeviceCodeCredential`) acts as the signed-in user: no client secret,
needs its own public client app registration with "Allow public client flows"
enabled and the `Mail.Read`, 'Mail.Send' and 'Mail.ReadWrite'

App-only (`ClientSecretCredential`) reads a configured mailbox directly, with no
human at a browser — needed for unattended runs. It requires **Mail.Read/Send
ReadWrite as an Application permission with admin consent**
(the delegated Mail.Read above is not sufficient for `/users/{mailbox}/`).

Both credential classes only ship sync `get_token`, so it runs in a thread via
`asyncio.to_thread` to avoid blocking the event loop.

Moved here from `utils.graph_auth` and made mailbox-parametric: the mailbox is
now a value a caller passes (`MailboxConfig`), not a module-level global read
from settings. That is what lets invoice extraction and payment matching read
two different mailboxes in one process. Credentials are still cached and shared,
keyed by app registration, so the two use cases acquire one token between them.
"""

import asyncio
from dataclasses import dataclass

from azure.identity import ClientSecretCredential, DeviceCodeCredential

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Default message ids change when a message moves folders.  Immutable ids survive the move.
IMMUTABLE_ID_PREFER = 'IdType="ImmutableId"'


@dataclass(frozen=True)
class GraphAppConfig:
    """The Azure AD app registration used to sign in to Graph.

    `client_secret` unset means delegated device-code sign-in; set means
    app-only client-credentials.

    Frozen and hashable so it can key the credential cache directly: two use
    cases configured from the same app registration compare equal and therefore
    share one credential — and one token acquisition — without either knowing
    the other exists.
    """

    tenant_id: str | None
    client_id: str | None
    client_secret: str | None = None
    scope: str = GRAPH_SCOPE

    @property
    def is_app_only(self) -> bool:
        return bool(self.client_secret)


@dataclass(frozen=True)
class MailboxConfig:
    """Which mailbox to read, and the app registration to read it with.

    `address` unset means delegated mode, where Graph resolves `/me` to whoever
    signed in. App-only mode has no signed-in user, so it must name a mailbox.
    """

    app: GraphAppConfig
    address: str | None = None

    @property
    def user_path(self) -> str:
        """The Graph URL segment identifying whose mailbox to read.

        `users/{address}` in app-only mode, `me` in delegated mode — the only
        place the two auth flows differ at the request level.
        """
        if self.app.is_app_only and self.address:
            return f"users/{self.address}"
        return "me"

    @property
    def label(self) -> str:
        """How this mailbox is identified in logs and in `email_sync_runs.mailbox`."""
        return self.address or "me"


def graph_app_from_settings() -> GraphAppConfig:
    """The app registration in `.env`, shared by every use case.

    Imported lazily so this module stays importable without settings loaded.
    """
    from config.settings import settings

    return GraphAppConfig(
        tenant_id=settings.GRAPH_TENANT_ID,
        client_id=settings.GRAPH_CLIENT_ID,
        client_secret=settings.GRAPH_CLIENT_SECRET,
    )


_credentials: dict[GraphAppConfig, ClientSecretCredential | DeviceCodeCredential] = {}


def _build_credential(app: GraphAppConfig) -> ClientSecretCredential | DeviceCodeCredential:
    if not app.tenant_id or not app.client_id:
        raise RuntimeError(
            "GRAPH_TENANT_ID / GRAPH_CLIENT_ID are not set. Register an Azure AD app "
            "and add its tenant/client IDs to .env. App-only access to a shared "
            "mailbox additionally needs GRAPH_CLIENT_SECRET and Mail.Read granted as "
            "an Application permission with admin consent."
        )

    if app.is_app_only:
        return ClientSecretCredential(
            tenant_id=app.tenant_id,
            client_id=app.client_id,
            client_secret=app.client_secret,
        )
    return DeviceCodeCredential(tenant_id=app.tenant_id, client_id=app.client_id)


def get_credential(app: GraphAppConfig) -> ClientSecretCredential | DeviceCodeCredential:
    """The cached credential for one app registration, built on first use.

    Cached per app registration rather than per mailbox: the credential proves
    who the *application* is, and one app-only token carries access to every
    mailbox its Application permissions cover. Two mailboxes on one registration
    therefore share a credential and its in-process token cache.
    """
    credential = _credentials.get(app)
    if credential is None:
        credential = _build_credential(app)
        _credentials[app] = credential
    return credential


async def get_graph_token(app: GraphAppConfig) -> str:
    """A bearer token for Microsoft Graph, for one app registration.

    Tokens are cached in-process by the credential itself for its lifetime —
    call again within the same run and it won't prompt/re-auth a second time.
    """
    credential = get_credential(app)
    token = await asyncio.to_thread(credential.get_token, app.scope)
    return token.token


async def auth_headers(app: GraphAppConfig) -> dict[str, str]:
    """Bearer + immutable-id headers, the base for every Graph request."""
    token = await get_graph_token(app)
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Prefer": IMMUTABLE_ID_PREFER,
    }


def with_prefer(headers: dict[str, str], preference: str) -> dict[str, str]:
    """Add a Prefer value, keeping the immutable-id one — Graph takes them comma-separated."""
    return {**headers, "Prefer": f"{headers['Prefer']}, {preference}"}
