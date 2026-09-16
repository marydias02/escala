import pytest

pytestmark = pytest.mark.usefixtures("fake_oidc")

PROTECTED_PATH = "/extraction/documents"


def test_valid_token_returns_200(client, auth, mint_token, stub_extraction_service):
    resp = client.get(PROTECTED_PATH, headers=auth(mint_token(roles=["user"])))
    assert resp.status_code == 200
    assert resp.json() == []


def test_missing_authorization_header_returns_401_with_challenge(client):
    resp = client.get(PROTECTED_PATH)
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


def test_expired_token_returns_401(client, auth, mint_token):
    resp = client.get(PROTECTED_PATH, headers=auth(mint_token(roles=["user"], expires_in=-10)))
    assert resp.status_code == 401


def test_wrong_audience_returns_401(client, auth, mint_token):
    resp = client.get(PROTECTED_PATH, headers=auth(mint_token(roles=["user"], aud="some-other-api")))
    assert resp.status_code == 401


def test_wrong_issuer_returns_401(client, auth, mint_token):
    resp = client.get(
        PROTECTED_PATH,
        headers=auth(mint_token(roles=["user"], iss="https://sts.windows.net/00000000-0000-0000-0000-000000000000/")),
    )
    assert resp.status_code == 401


def test_token_signed_by_unpublished_key_returns_401(client, auth, mint_token):
    token = mint_token(roles=["user"], kid="test-key-1", sign_with="test-key-unpublished")
    resp = client.get(PROTECTED_PATH, headers=auth(token))
    assert resp.status_code == 401
