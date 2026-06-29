from functools import lru_cache
from urllib.parse import urlparse

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader, OAuth2AuthorizationCodeBearer
from jose import ExpiredSignatureError, JWTError, jwt
from jose.exceptions import JWTClaimsError
from typing_extensions import Annotated, Any

import api.properties as props
from api.properties import AUDIENCE

# API KEY ===================================================================

ph = PasswordHasher()

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)


def verify_api_key(api_key: str = Depends(api_key_header)):
    try:
        if not api_key:
            raise HTTPException(status_code=401, detail="Not Authenticated")
        ph.verify(props.HASHED_API_KEY, api_key)
        return True
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid API Key")


## OPENID CONNECT =======================================================
@lru_cache(maxsize=1)
def oidc_discovery(metadata_url):
    response = httpx.get(metadata_url)
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=1)
def jwks_keys(metadata_url):
    response = httpx.get(oidc_discovery(metadata_url)["jwks_uri"])
    response.raise_for_status()
    return response.json()["keys"]


def is_not_microsoft_multitenant(issuer):  # Used for setting defaults only
    return not any(
        issuer.startswith(f"https://login.microsoftonline.com/{t}") for t in ("common", "organizations", "consumers")
    )


class OpenIdConnectAuthorizationCodeBearer(OAuth2AuthorizationCodeBearer):
    def __init__(
        self,
        metadata_url=props.OIDC_METADATA_URL,
        audience=AUDIENCE,
        scheme_name=None,
        validate_iss: bool = None,
        validate_aud: bool = True,
        scopes=None,
    ):
        self._audience = audience
        self.metadata_url = metadata_url
        self._validate_iss = validate_iss if validate_iss is not None else is_not_microsoft_multitenant(metadata_url)
        self._validate_aud = validate_aud

        if not scheme_name:
            try:
                scheme_name = urlparse(metadata_url).hostname or "OIDC"
            except ValueError:
                scheme_name = "OIDC"

        super().__init__(
            scheme_name=scheme_name,
            description="Leave secret input blank!",
            authorizationUrl=oidc_discovery(self.metadata_url)["authorization_endpoint"],
            tokenUrl=oidc_discovery(self.metadata_url)["token_endpoint"],
            scopes=scopes or {k: "" for k in oidc_discovery(self.metadata_url)["scopes_supported"]},
        )

    async def decode_verified_token(self, token: str) -> dict[str, Any]:
        try:
            discovery = oidc_discovery(self.metadata_url)
            jwk_keys = jwks_keys(self.metadata_url)

            algos = discovery.get("id_token_signing_alg_values_supported", ["RS256"])
            issuer = discovery["issuer"]

            return jwt.decode(
                token,
                jwk_keys,
                algorithms=algos,
                audience=self._audience,
                issuer=issuer,
                options={"verify_aud": self._validate_aud, "verify_iss": self._validate_iss},
            )
        except (ExpiredSignatureError, JWTError, JWTClaimsError) as e:
            raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})

    async def __call__(self, request: Request) -> dict:
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(status_code=401, detail="Not Authenticated", headers={"WWW-Authenticate": "Bearer"})
        schema, token = authorization.split(" ")
        if schema != "Bearer":
            raise HTTPException(
                status_code=401, detail="Expected Bearer Authentication", headers={"WWW-Authenticate": "Bearer"}
            )
        return await self.decode_verified_token(token)


openid_connect = OpenIdConnectAuthorizationCodeBearer(scopes={k: "" for k in props.APP_SCOPES.split(" ")})

ValidAccessToken = Annotated[dict, Depends(openid_connect)]

swagger_security_kwargs: dict[str, Any] = dict(
    swagger_ui_oauth2_redirect_url="/oauth2-redirect",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": props.CLIENT_ID,
        "scopes": props.APP_SCOPES.split(" "),
    },
)


# Authorization (Access control)
#
# This section implements a simple role-based access control (RBAC) a very scalable and easy to use model for authorization.
#
# Key concepts:
# - `policy`: defining what and how subjects perform can actions on each resources. Their format is derived from your application design (not the client's security infrastructure).
# - `subject`: the authenticated user (in our case, the decoded and validated token).
# - `isSubjectAuthorized(...)`: checks if subject allowed bt the policy to perform the action on the resource.
# - `hasAuthorizationFor(action, resource)`: returns a FastAPI dependency version of isSubjectAuthorized.

# You might need a more sophisticated approach called Attribute-Based-Access-Control (ABAC) that expands this by adding context-aware rules (example user can access the items they created only).
# You can easly adapt this by changing the way you define the `policy` to include rules (functions/lambdas) and changing the `isSubjectAuthorized(...)` to evaluate them.

policy = {
    "admin": {
        "items": {"create", "read", "update", "delete", "assignUsers"},
        "users": {"create", "read", "update", "delete", "updateSelf"},
    },
    "user": {
        "items": {"read", "update"},
        "users": {"read", "updateSelf"},
    },
    "unassigned": {
        "items": {"read"},
        "users": {"read"},
    },
}


def is_subject_authorized(subject: dict, action: str, resource: str, **context) -> bool:
    user_roles = subject.get("roles", {"unassigned"})

    for role in user_roles:
        allowed_actions = policy.get(role, {}).get(resource, set())
        if action in allowed_actions:
            return True

    return False


def raise_for_unauthorized(subject: dict, action: str, resource: str, **context):
    if not is_subject_authorized(subject, action, resource, **context):
        raise HTTPException(status_code=403, detail="Forbidden")


def has_authorization_for(action: str, resource: str, **context) -> type[Depends]:
    def authorization_dependency(token_claims: dict = Depends(openid_connect)) -> dict:
        raise_for_unauthorized(token_claims, action, resource, **context)
        return token_claims

    return Depends(authorization_dependency)
