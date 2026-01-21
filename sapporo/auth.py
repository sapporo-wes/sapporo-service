import datetime
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional

import httpx
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jwt import PyJWKSet
from pydantic import BaseModel, ConfigDict
from starlette.requests import Request

from sapporo.config import get_config
from sapporo.exceptions import (raise_bad_request, raise_internal_error,
                                raise_invalid_credentials, raise_invalid_token,
                                raise_unauthorized)
from sapporo.utils import user_agent

# Password hasher instance
_password_hasher = PasswordHasher()

# Username validation pattern: alphanumeric, underscore, hyphen, dot, at-sign
# Max length 128 characters to prevent abuse
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-.@]{1,128}$")

# === Schema ===


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    username: str


class AuthUser(BaseModel):
    username: str
    password_hash: str


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


class HTTPBearerCustom:
    def __init__(self, scheme_name: str, description: str) -> None:
        self.scheme_name = scheme_name
        self.description = description
        self.model = type(
            "HTTPBearer",
            (),
            {"__annotations__": {"scheme_name": str, "description": str}},
        )

    async def __call__(self, request: Request) -> str:
        authorization = request.headers.get("Authorization")
        scheme, credentials = get_authorization_scheme_param(authorization)
        if not (authorization and scheme and credentials):
            raise_unauthorized("Authorization header is missing or invalid.")
        if scheme.lower() != "bearer":
            raise_unauthorized("Invalid authentication scheme.")
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
            raise_bad_request("Token creation is not allowed for public client mode.")


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


def sanitize_username(username: str) -> str:
    """
    Sanitize and validate a username from external sources.

    Validates that the username:
    - Contains only allowed characters (alphanumeric, _, -, ., @)
    - Is not empty and not too long (max 128 characters)
    - Does not contain path traversal sequences

    Args:
        username: The username to sanitize

    Returns:
        The sanitized username

    Raises:
        HTTPException 400: If username is invalid
    """
    # Check for path traversal attempts
    if ".." in username or "/" in username or "\\" in username:
        raise_bad_request("Invalid username: contains forbidden characters")

    # Validate against allowed pattern
    if not _USERNAME_PATTERN.match(username):
        raise_bad_request(
            "Invalid username: must contain only alphanumeric characters, "
            "underscore, hyphen, dot, or at-sign, and be 1-128 characters long"
        )

    return username


def extract_username(payload: TokenPayload) -> str:
    """Extract and sanitize username from token payload."""
    payload_dict = payload.model_dump()
    if "preferred_username" in payload_dict:
        username = str(payload_dict["preferred_username"])
    else:
        username = payload.sub

    return sanitize_username(username)


# === Sapporo Mode Functions ===


# JWT expiration constants
DEFAULT_JWT_EXPIRES_HOURS = 24  # Default expiration if not specified
MAX_JWT_EXPIRES_HOURS = 168  # Maximum allowed expiration (1 week)


def spr_create_access_token(username: str, password: str) -> str:
    """
    Create a JWT access token for the authenticated user.

    JWT tokens always have an expiration time for security:
    - If expires_delta_hours is None, uses default (24 hours)
    - If expires_delta_hours exceeds maximum, caps at 168 hours (1 week)
    """
    spr_check_user(username, password)

    auth_config = get_auth_config()
    secret_key = auth_config.sapporo_auth_config.secret_key
    expires_delta = auth_config.sapporo_auth_config.expires_delta_hours

    # Enforce expiration: use default if None, cap at maximum
    if expires_delta is None:
        expires_delta = DEFAULT_JWT_EXPIRES_HOURS
    expires_delta = min(expires_delta, MAX_JWT_EXPIRES_HOURS)

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
    """
    Check if username and password are valid.

    Uses argon2 for constant-time password comparison to prevent timing attacks.
    """
    auth_config = get_auth_config()

    # Find user by username
    target_user = None
    for user in auth_config.sapporo_auth_config.users:
        if user.username == username:
            target_user = user
            break

    if target_user is None:
        # Perform a dummy hash verification to prevent timing attacks
        # that could reveal whether a username exists
        try:
            _password_hasher.verify("$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy", password)
        except Exception:  # nosec B110  # pylint: disable=broad-exception-caught
            pass
        raise_invalid_credentials()

    try:
        _password_hasher.verify(target_user.password_hash, password)
    except VerifyMismatchError:
        raise_invalid_credentials()


def spr_decode_token(token: str) -> TokenPayload:
    auth_config = get_auth_config()
    secret_key = auth_config.sapporo_auth_config.secret_key
    try:
        return TokenPayload.model_validate(jwt.decode(token, secret_key, algorithms=[SAPPORO_SIGNATURE_ALGORITHM], audience=SAPPORO_AUDIENCE))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise_invalid_token()


def check_valid_username(username: str) -> None:
    auth_config = get_auth_config()
    if username not in [user.username for user in auth_config.sapporo_auth_config.users]:
        raise_unauthorized("Invalid username")


# === External Mode Functions ===


def _is_insecure_idp_allowed() -> bool:
    """Check if insecure (HTTP) IdP connections are allowed via environment variable."""
    return os.environ.get("SAPPORO_ALLOW_INSECURE_IDP", "").lower() in ("true", "1", "yes")


def _validate_https_url(url: str, context: str) -> None:
    """Validate that a URL uses HTTPS protocol unless insecure connections are explicitly allowed."""
    if not _is_insecure_idp_allowed() and not url.startswith("https://"):
        raise_bad_request(
            f"{context} must use HTTPS for security. "
            f"Got: {url}. "
            "Set SAPPORO_ALLOW_INSECURE_IDP=true to allow insecure connections (not recommended for production)."
        )


@lru_cache(maxsize=None)
def fetch_endpoint_metadata() -> ExternalEndpointMetadata:
    auth_config = get_auth_config()
    idp_url = auth_config.external_config.idp_url

    # Validate HTTPS for IdP URL
    _validate_https_url(idp_url, "External IdP URL")

    well_known_url = f"{idp_url}/.well-known/openid-configuration"
    try:
        with httpx.Client() as client:
            res = client.get(well_known_url, follow_redirects=True, headers={"User-Agent": user_agent()})
            res.raise_for_status()
            metadata = ExternalEndpointMetadata.model_validate(res.json())

            # Also validate endpoints returned by the IdP
            _validate_https_url(metadata.token_endpoint, "Token endpoint")
            _validate_https_url(metadata.jwks_uri, "JWKS URI")
            _validate_https_url(metadata.authorization_endpoint, "Authorization endpoint")

            return metadata
    except (httpx.HTTPError, ValueError, KeyError):
        raise_internal_error("Failed to fetch IdP metadata from the well-known endpoint")


async def external_create_access_token(username: str, password: str) -> str:
    auth_config = get_auth_config()
    token_url = fetch_endpoint_metadata().token_endpoint
    data: Dict[str, Optional[str]] = {
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
            return str(res.json().get("access_token", ""))
    except (httpx.HTTPError, ValueError, KeyError):
        raise_invalid_credentials()


def external_decode_token(token: str) -> TokenPayload:
    jwks = fetch_jwks()

    # Extract the kid and alg from the token header
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header["kid"]
    alg = unverified_header["alg"]

    jwk_key = next((k.key for k in jwks.keys if k.key_id == kid), None)
    if jwk_key is None:
        raise_invalid_token()

    auth_config = get_auth_config()
    jwt_audience = auth_config.external_config.jwt_audience

    try:
        return TokenPayload.model_validate(
            jwt.decode(token, jwk_key, algorithms=[alg], audience=jwt_audience)
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        raise_invalid_token()


@lru_cache(maxsize=None)
def fetch_jwks() -> PyJWKSet:
    jwks_uri = fetch_endpoint_metadata().jwks_uri
    try:
        with httpx.Client() as client:
            res = client.get(jwks_uri, follow_redirects=True, headers={"User-Agent": user_agent()})
            res.raise_for_status()
            return PyJWKSet.from_dict(res.json())
    except (httpx.HTTPError, ValueError, KeyError):
        raise_internal_error("Failed to fetch JWKS from the IdP")
