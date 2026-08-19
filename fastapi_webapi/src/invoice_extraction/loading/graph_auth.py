"""Delegated Microsoft Graph sign-in via device code.

Separate from the `ClientSecretCredential` used for Lakehouse/SQL access
(`invoice_extraction/tests/lakehouse_access.py`): that's app-only, this is
delegated (acts as the signed-in user, no client secret). Needs its own public
client app registration with "Allow public client flows" enabled and the
`Mail.Read` delegated permission granted.

The device flow prints a URL and a short code to the console; sign in with a
browser using your normal account, and the token comes back here. Tokens are
cached in-process for the lifetime of the credential — call `get_graph_token`
again within the same run and it won't prompt a second time.

`DeviceCodeCredential` only ships as a sync class (the device-code prompt is
inherently a blocking console interaction), so `get_token` runs in a thread via
`asyncio.to_thread` to avoid blocking the event loop while the user signs in.
"""

import asyncio

from azure.identity import DeviceCodeCredential

from config.settings import settings

GRAPH_SCOPE = "https://graph.microsoft.com/.default"

_credential: DeviceCodeCredential | None = None


def _get_credential() -> DeviceCodeCredential:
    global _credential
    if _credential is None:
        if not settings.GRAPH_TENANT_ID or not settings.GRAPH_CLIENT_ID:
            raise RuntimeError(
                "GRAPH_TENANT_ID / GRAPH_CLIENT_ID are not set. Register a public "
                "client Azure AD app (delegated Mail.Read permission, "
                "'Allow public client flows' = Yes) and add its tenant/client IDs "
                "to .env."
            )
        _credential = DeviceCodeCredential(
            tenant_id=settings.GRAPH_TENANT_ID,
            client_id=settings.GRAPH_CLIENT_ID,
        )
    return _credential


async def get_graph_token() -> str:
    """Return a bearer token for Microsoft Graph, prompting a device-code sign-in
    the first time it's needed."""
    credential = _get_credential()
    token = await asyncio.to_thread(credential.get_token, GRAPH_SCOPE)
    return token.token
