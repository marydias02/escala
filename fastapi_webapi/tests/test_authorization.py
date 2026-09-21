"""RBAC behaviour.

The 403-vs-401 distinction is the point: 401 tells a client to sign in again,
403 tells it not to bother. `test_missing_roles_claim_returns_403` is the
regression test for the unassigned-user hole closed in M3.
"""

import pytest

pytestmark = pytest.mark.usefixtures("fake_oidc")


TEMPLATE_UPLOAD = {"file": ("t.txt", b"x", "text/plain")}


def test_role_without_permission_returns_403(client, override_claims):
    # `user` may read runs but not create them (POST /air/template -> runs:create).
    override_claims({"sub": "u1", "name": "U", "roles": ["User"]})
    resp = client.post("/air/template", files=TEMPLATE_UPLOAD)
    assert resp.status_code == 403


def test_admin_role_may_create_runs(client, override_claims, stub_air_service):
    # The counterpart to the test above: runs:create is the *only* action separating
    # `admin` from `user`, so without this a policy denying it to everyone still passes.
    override_claims({"sub": "u2", "name": "A", "roles": ["Admin"]})
    resp = client.post("/air/template", files=TEMPLATE_UPLOAD)
    assert resp.status_code == 201


def test_missing_roles_claim_returns_403(client, auth, mint_token):
    resp = client.get("/extraction/documents", headers=auth(mint_token(roles=None)))
    assert resp.status_code == 403
