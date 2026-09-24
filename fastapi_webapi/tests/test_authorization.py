"""RBAC behaviour.

The 403-vs-401 distinction is the point: 401 tells a client to sign in again,
403 tells it not to bother. `test_missing_roles_claim_returns_403` is the
regression test for the unassigned-user hole closed in M3.
"""

import pytest

pytestmark = pytest.mark.usefixtures("fake_oidc")


def test_missing_roles_claim_returns_403(client, auth, mint_token):
    resp = client.get("/extraction/documents", headers=auth(mint_token(roles=None)))
    assert resp.status_code == 403
