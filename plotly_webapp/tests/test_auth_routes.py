"""The sign-in routes and the before_request guard.

Every test drives the real routes with MSAL mocked. The distinction these assert
over and over is between a browser navigation, which may be redirected to
sign-in, and an XHR to `/_dash-update-component`, which may not: Dash follows a
302 and then receives an HTML sign-in page where it expected JSON, which shows
the user a broken screen rather than a sign-in prompt.
"""

from urllib.parse import parse_qs, urlparse

from conftest import TEST_AUTHORITY, TEST_SCOPE


def complete_sign_in(client, next_path="/"):
    """Drive /login then the `form_post` callback, as a browser would."""
    assert client.get("/login", query_string={"next": next_path}).status_code == 302
    return client.post("/authorized", data={"code": "auth-code", "state": "flow-state-123"})


def flow_cookie(response):
    return next(c for c in response.headers.getlist("Set-Cookie") if c.startswith("escala_auth_flow="))


class TestUnauthenticatedAccess:
    def test_browser_request_to_guarded_path_redirects_to_login(self, client):
        response = client.get("/")

        assert response.status_code == 302
        location = urlparse(response.headers["Location"])
        assert location.path == "/login"
        assert parse_qs(location.query)["next"] == ["/"]

    def test_deep_link_is_preserved_as_the_next_path(self, client):
        response = client.get("/validation")

        assert response.status_code == 302
        assert parse_qs(urlparse(response.headers["Location"]).query)["next"] == ["/validation"]

    def test_dash_update_component_gets_json_401_and_never_a_redirect(self, client):
        response = client.post("/_dash-update-component", json={"output": "x.children"})

        assert response.status_code == 401
        assert "Location" not in response.headers
        assert response.is_json
        assert response.get_json()["error"] == "unauthenticated"

    def test_assets_are_public(self, client):
        # 404 rather than 302: the guard let the request reach routing, and this
        # bare app has no static file to serve.
        assert client.get("/assets/css/app.css").status_code == 404

    def test_auth_status_is_public_and_reports_no_session(self, client):
        response = client.get("/auth/status")

        assert response.status_code == 200
        assert response.get_json()["authenticated"] is False


class TestSignIn:
    def test_login_redirects_to_the_provider(self, client, msal_app):
        response = client.get("/login")

        assert response.status_code == 302
        assert response.headers["Location"].startswith(f"{TEST_AUTHORITY}/oauth2/v2.0/authorize")

        _, kwargs = msal_app.initiate_auth_code_flow.call_args
        assert kwargs["redirect_uri"] == "http://localhost:8050/authorized"

    def test_login_asks_for_the_code_by_form_post(self, client, msal_app):
        client.get("/login")

        _, kwargs = msal_app.initiate_auth_code_flow.call_args
        assert kwargs["response_mode"] == "form_post"

    def test_login_stashes_the_flow_where_a_cross_site_post_carries_it(self, client):
        cookie = flow_cookie(client.get("/login"))

        assert "SameSite=None" in cookie
        assert "Secure" in cookie
        assert "HttpOnly" in cookie
        assert "Path=/authorized" in cookie

    def test_login_leaves_no_session_behind(self, client):
        client.get("/login")

        with client.session_transaction() as session:
            assert not session

    def test_login_requests_the_full_api_scope(self, client, msal_app):
        # `openid profile` alone yields a Graph-audience token the backend
        # correctly rejects; MSAL adds those three itself, so they must not be
        # listed here either.
        client.get("/login")

        args, kwargs = msal_app.initiate_auth_code_flow.call_args
        scopes = kwargs.get("scopes", args[0] if args else None)
        assert scopes == [TEST_SCOPE]
        assert not {"openid", "profile", "offline_access"} & set(scopes)

    def test_authorized_stores_the_identity_and_returns_to_the_requested_path(self, client):
        response = complete_sign_in(client, next_path="/validation")

        assert response.status_code == 302
        assert urlparse(response.headers["Location"]).path == "/validation"

        with client.session_transaction() as session:
            assert session["user"]["name"] == "Ana Silva"
            assert session["user"]["roles"] == ["user"]

    def test_authorized_refuses_a_failed_code_exchange(self, client, msal_app):
        msal_app.acquire_token_by_auth_code_flow.return_value = {
            "error": "invalid_grant",
            "error_description": "AADSTS70008",
        }

        response = complete_sign_in(client)

        assert response.status_code == 401
        with client.session_transaction() as session:
            assert "user" not in session

    def test_authorized_without_a_stashed_flow_is_refused(self, client):
        # A bare hit on the redirect URI, with no /login before it.
        response = client.post("/authorized", data={"code": "auth-code", "state": "spoofed"})

        assert response.status_code == 401
        with client.session_transaction() as session:
            assert "user" not in session

    def test_the_callback_cannot_be_replayed(self, client):
        complete_sign_in(client)

        replay = client.post("/authorized", data={"code": "auth-code", "state": "flow-state-123"})

        assert replay.status_code == 401
        assert replay.get_json()["error"] == "no_auth_flow"


class TestGuardedAccess:
    def test_signed_in_browser_request_is_served(self, signed_in):
        assert signed_in().get("/").status_code == 200

    def test_signed_in_dash_callback_is_served(self, signed_in):
        response = signed_in().post("/_dash-update-component", json={"output": "x.children"})

        assert response.status_code == 200

    def test_auth_status_reports_a_live_session(self, signed_in):
        assert signed_in().get("/auth/status").get_json()["authenticated"] is True

    def test_a_failed_silent_refresh_ends_the_session(self, signed_in, msal_app):
        # Not merely "the token is stale": `acquire_token_silent` returning None
        # is what an expired refresh token looks like, and the session is over.
        msal_app.acquire_token_silent.return_value = None
        client = signed_in()

        response = client.post("/_dash-update-component", json={"output": "x.children"})

        assert response.status_code == 401
        with client.session_transaction() as session:
            assert "user" not in session

    def test_the_guard_refreshes_near_expiry_without_a_new_sign_in(self, signed_in, msal_app):
        client = signed_in()

        assert client.get("/").status_code == 200
        assert msal_app.acquire_token_silent.called


class TestSignOut:
    def test_logout_redirects_to_the_provider_end_session_endpoint(self, signed_in):
        response = signed_in().get("/logout")

        assert response.status_code == 302
        location = urlparse(response.headers["Location"])
        assert f"{location.scheme}://{location.netloc}{location.path}".startswith(
            f"{TEST_AUTHORITY}/oauth2/v2.0/logout"
        )
        assert parse_qs(location.query)["post_logout_redirect_uri"] == ["http://localhost:8050/"]

    def test_logout_clears_the_local_session(self, signed_in):
        client = signed_in()

        client.get("/logout")

        with client.session_transaction() as session:
            assert "user" not in session

    def test_after_logout_a_guarded_path_asks_for_sign_in_again(self, signed_in):
        client = signed_in()

        client.get("/logout")

        response = client.get("/")
        assert response.status_code == 302
        assert urlparse(response.headers["Location"]).path == "/login"
