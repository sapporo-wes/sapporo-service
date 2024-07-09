import datetime
from functools import lru_cache
from typing import Any, List, Literal, Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jwt import PyJWKSet
from pydantic import BaseModel, ConfigDict
from starlette.requests import Request

from sapporo.config import get_config
from sapporo.utils import user_agent

# === Schema ===


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    username: str


class AuthUser(BaseModel):
    username: str
    password: str


SAPPORO_AUDIENCE = "account"
SAPPORO_SIGNATURE_ALGORITHM = "HS256"


class SapporoAuthConfig(BaseModel):
    secret_key: str
    expires_delta_hours: Optional[int]
    users: List[AuthUser]


class ExternalAuthConfig(BaseModel):
    idp_url: str  # Access to {idp_url}/.well-known/openid-configuration, accessible from the Sapporo
    jwt_audience: str  # e.g., "account"
    client_mode: Literal["confidential", "public"]
    client_id: Optional[str]
    client_secret: Optional[str]


class AuthConfig(BaseModel):
    auth_enabled: bool
    idp_provider: Literal["sapporo", "external"]
    sapporo_auth_config: SapporoAuthConfig
    external_config: ExternalAuthConfig


class TokenPayload(BaseModel):
    sub: str
    exp: Optional[datetime.datetime]
    iat: Optional[datetime.datetime]
    aud: str
    iss: str

    model_config = ConfigDict(
        extra="allow"
    )


class ExternalEndpointMetadata(BaseModel):
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str

    model_config = ConfigDict(
        extra="ignore"
    )


# === General Functions ===


@lru_cache(maxsize=None)
def get_auth_config() -> AuthConfig:
    with get_config().auth_config.open(mode="r", encoding="utf-8") as f:
        auth_config = AuthConfig.model_validate_json(f.read())
    return auth_config


class HTTPBearerCustom(HTTPBearer):
    async def __call__(self, request: Request) -> str:
        authorization = request.headers.get("Authorization")
        scheme, credentials = get_authorization_scheme_param(authorization)
        if not (authorization and scheme and credentials):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header is missing or invalid.",
            )
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme.",
            )
        return credentials


http_bearer_custom = HTTPBearerCustom(
    scheme_name="JWT Bearer",
    description="Include JWT as Bearer in the Authorization header for authentication. Please input JWT token.",
)
password_bearer = OAuth2PasswordBearer(tokenUrl="/token")


def auth_depends_factory() -> Any:
    """\
    Function to inject authorization into each endpoint.
    Use like `token: Optional[str] = auth_depends_factory`.
    """
    auth_config = get_auth_config()
    if auth_config.auth_enabled:
        if auth_config.idp_provider == "sapporo":
            return Depends(password_bearer)
        else:
            if auth_config.external_config.client_mode == "confidential":
                return Depends(password_bearer)
            else:
                return Depends(http_bearer_custom)

    # do nothing
    return Depends(lambda: None)


def is_create_token_endpoint_enabled() -> None:
    auth_config = get_auth_config()
    if auth_config.idp_provider == "external":
        if auth_config.external_config.client_mode == "public":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token creation is not allowed for public client mode.",
            )


async def create_access_token(username: str, password: str) -> str:
    auth_config = get_auth_config()
    if auth_config.idp_provider == "sapporo":
        return spr_create_access_token(username, password)
    return await external_create_access_token(username, password)


def decode_token(token: str) -> TokenPayload:
    auth_config = get_auth_config()
    if auth_config.idp_provider == "sapporo":
        payload = spr_decode_token(token)
        check_valid_username(payload.sub)
        return payload
    return external_decode_token(token)


def extract_username(payload: TokenPayload) -> str:
    payload_dict = payload.model_dump()
    if "preferred_username" in payload_dict:
        return str(payload_dict["preferred_username"])
    return payload.sub


# === Sapporo Mode Functions ===


def spr_create_access_token(username: str, password: str) -> str:
    spr_check_user(username, password)

    auth_config = get_auth_config()
    secret_key = auth_config.sapporo_auth_config.secret_key
    expires_delta = auth_config.sapporo_auth_config.expires_delta_hours

    iat, exp = None, None
    if expires_delta is not None:
        iat = datetime.datetime.now(datetime.timezone.utc)
        exp = iat + datetime.timedelta(hours=expires_delta)

    payload = TokenPayload(
        sub=username,
        exp=exp,
        iat=iat,
        aud=SAPPORO_AUDIENCE,
        iss=f"{get_config().base_url}/auth",
    )

    return jwt.encode(payload.model_dump(), secret_key, algorithm=SAPPORO_SIGNATURE_ALGORITHM)


def spr_check_user(username: str, password: str) -> None:
    auth_config = get_auth_config()
    for user in auth_config.sapporo_auth_config.users:
        if user.username == username and user.password == password:
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
    )


def spr_decode_token(token: str) -> TokenPayload:
    auth_config = get_auth_config()
    secret_key = auth_config.sapporo_auth_config.secret_key
    try:
        return TokenPayload.model_validate(jwt.decode(token, secret_key, algorithms=[SAPPORO_SIGNATURE_ALGORITHM], audience=SAPPORO_AUDIENCE))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e


def check_valid_username(username: str) -> None:
    auth_config = get_auth_config()
    if username not in [user.username for user in auth_config.sapporo_auth_config.users]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username",
        )


# === External Mode Functions ===


@lru_cache(maxsize=None)
def fetch_endpoint_metadata() -> ExternalEndpointMetadata:
    auth_config = get_auth_config()
    idp_url = auth_config.external_config.idp_url
    well_known_url = f"{idp_url}/.well-known/openid-configuration"
    try:
        with httpx.Client() as client:
            res = client.get(well_known_url, follow_redirects=True, headers={"User-Agent": user_agent()})
            res.raise_for_status()
            return ExternalEndpointMetadata.model_validate(res.json())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch IdP metadata from the well-known endpoint",
        ) from e


async def external_create_access_token(username: str, password: str) -> str:
    auth_config = get_auth_config()
    token_url = fetch_endpoint_metadata().token_endpoint
    data = {
        "grant_type": "password",
        "client_id": auth_config.external_config.client_id,
        "client_secret": auth_config.external_config.client_secret,
        "username": username,
        "password": password,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": user_agent(),
    }

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(token_url, data=data, headers=headers, follow_redirects=True)
            res.raise_for_status()
            return res.json()["access_token"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        ) from e


def external_decode_token(token: str) -> TokenPayload:
    jwks = fetch_jwks()

    # Extract the kid and alg from the token header
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header["kid"]
    alg = unverified_header["alg"]

    jwk_key = next((k.key for k in jwks.keys if k.key_id == kid), None)
    if jwk_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    auth_config = get_auth_config()
    jwt_audience = auth_config.external_config.jwt_audience

    try:
        return TokenPayload.model_validate(
            jwt.decode(token, jwk_key, algorithms=[alg], audience=jwt_audience)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e


@lru_cache(maxsize=None)
def fetch_jwks() -> PyJWKSet:
    jwks_uri = fetch_endpoint_metadata().jwks_uri
    try:
        with httpx.Client() as client:
            res = client.get(jwks_uri, follow_redirects=True, headers={"User-Agent": user_agent()})
            res.raise_for_status()
            return PyJWKSet.from_dict(res.json())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch JWKS from the IdP",
        ) from e
