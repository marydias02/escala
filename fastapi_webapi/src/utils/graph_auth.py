"""Microsoft Graph sign-in: delegated device-code, or app-only client-credentials.

Delegated (`DeviceCodeCredential`) acts as the signed-in user: no client secret,
needs its own public client app registration with "Allow public client flows"
enabled and the `Mail.Read`, 'Mail.Send' and 'Mail.ReadWrite'

App-only (`ClientSecretCredential`) reads a configured mailbox directly, with no
human at a browser — needed for unattended runs. It requires **Mail.Read/Send
ReadWrite as an Application permission with admin consent**
(the delegated Mail.Read above is not sufficient for `/users/{mailbox}/`).

Both credential classes only ship sync `get_token`, so it runs in a thread via
`asyncio.to_thread` to avoid blocking the event loop.
"""

import asyncio

from azure.identity import ClientSecretCredential, DeviceCodeCredential

from config.settings import settings

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_delegated_credential: DeviceCodeCredential | None = None
_app_only_credential: ClientSecretCredential | None = None


def _is_app_only() -> bool:
    return bool(settings.GRAPH_CLIENT_SECRET and settings.GRAPH_MAILBOX)


def _get_delegated_credential() -> DeviceCodeCredential:
    global _delegated_credential
    if _delegated_credential is None:
        if not settings.GRAPH_TENANT_ID or not settings.GRAPH_CLIENT_ID:
            raise RuntimeError(
                "GRAPH_TENANT_ID / GRAPH_CLIENT_ID are not set. Register a public "
                "client Azure AD app (delegated Mail.Read permission, "
                "'Allow public client flows' = Yes) and add its tenant/client IDs "
                "to .env."
            )
        _delegated_credential = DeviceCodeCredential(
            tenant_id=settings.GRAPH_TENANT_ID,
            client_id=settings.GRAPH_CLIENT_ID,
        )
    return _delegated_credential


def _get_app_only_credential() -> ClientSecretCredential:
    global _app_only_credential
    if _app_only_credential is None:
        if not settings.GRAPH_TENANT_ID or not settings.GRAPH_CLIENT_ID or not settings.GRAPH_CLIENT_SECRET:
            raise RuntimeError(
                "GRAPH_TENANT_ID / GRAPH_CLIENT_ID are not set alongside GRAPH_CLIENT_SECRET / GRAPH_MAILBOX."
            )
        _app_only_credential = ClientSecretCredential(
            tenant_id=settings.GRAPH_TENANT_ID,
            client_id=settings.GRAPH_CLIENT_ID,
            client_secret=settings.GRAPH_CLIENT_SECRET,
        )
    return _app_only_credential


async def get_graph_token() -> str:
    """Return a bearer token for Microsoft Graph.

    App-only when `GRAPH_CLIENT_SECRET` and `GRAPH_MAILBOX` are both set;
    otherwise delegated device-code, prompting a sign-in the first time it's
    needed. Tokens are cached in-process for the lifetime of the credential —
    call again within the same run and it won't prompt/re-auth a second time.
    """
    credential = _get_app_only_credential() if _is_app_only() else _get_delegated_credential()
    token = await asyncio.to_thread(credential.get_token, GRAPH_SCOPE)
    return token.token


def graph_user_path() -> str:
    """The Graph URL segment identifying whose mailbox to read.

    `users/{mailbox}` in app-only mode, `me` in delegated mode — the only place
    the two auth flows differ at the request level.
    """
    if _is_app_only():
        return f"users/{settings.GRAPH_MAILBOX}"
    return "me"
