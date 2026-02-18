import datetime
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import httpx
import jwt as pyjwt
import pytest
from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis import strategies as st

from sapporo.auth import (
    DEFAULT_JWT_EXPIRES_HOURS,
    MAX_JWT_EXPIRES_HOURS,
    SAPPORO_AUDIENCE,
    SAPPORO_SIGNATURE_ALGORITHM,
    _is_insecure_idp_allowed,
    _mask_username,
    _validate_https_url,
    clear_external_auth_caches,
    external_decode_token,
    fetch_endpoint_metadata,
    fetch_jwks,
    sanitize_username,
    spr_check_user,
    spr_create_access_token,
    spr_decode_token,
)

from .conftest import (
    _MOCK_IDP_ISSUER,
    _MOCK_IDP_METADATA,
    MockHttpxResponse,
    build_jwks_dict,
    create_signed_jwt,
    default_auth_config_dict,
    mock_get_config,
    write_auth_config,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

_TEST_PASSWORD = "sapporo-test-password"


def _setup_auth(mocker: "MockerFixture", tmp_path: Path, **overrides: object) -> None:
    """Set up auth config and mock get_config."""
    config = default_auth_config_dict()
    for key, value in overrides.items():
        if "." in key:
            parts = key.split(".")
            target = config
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
        else:
            config[key] = value
    auth_config_path = write_auth_config(tmp_path, config)

    from sapporo.auth import get_auth_config
    from sapporo.config import AppConfig

    app_config = AppConfig(auth_config=auth_config_path, debug=True)
    mock_get_config(mocker, app_config)
    # Clear after mock_get_config because importing sapporo.app (via mocker.patch)
    # triggers auth_depends_factory() which caches get_auth_config() at import time
    get_auth_config.cache_clear()


# === _mask_username ===


@pytest.mark.parametrize(
    ("username", "expected"),
    [
        ("", "***"),
        ("a", "***"),
        ("ab", "***"),
        ("abc", "***"),
        ("abcd", "abc***"),
        ("test-user", "tes***"),
        ("long-username@example.com", "lon***"),
    ],
)
def test_mask_username(username: str, expected: str) -> None:
    assert _mask_username(username) == expected


# === sanitize_username ===


@pytest.mark.parametrize(
    "username",
    [
        "user1",
        "user_name",
        "user-name",
        "user.name",
        "user@example.com",
        "a",
        "A" * 128,
    ],
)
def test_sanitize_username_with_valid_pattern_returns_same(username: str) -> None:
    assert sanitize_username(username) == username


def test_sanitize_username_with_path_traversal_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("../../../etc/passwd")
    assert exc_info.value.status_code == 400


def test_sanitize_username_with_slash_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("user/name")
    assert exc_info.value.status_code == 400


def test_sanitize_username_with_backslash_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("user\\name")
    assert exc_info.value.status_code == 400


def test_sanitize_username_with_empty_string_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("")
    assert exc_info.value.status_code == 400


def test_sanitize_username_with_129_chars_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("a" * 129)
    assert exc_info.value.status_code == 400


def test_sanitize_username_with_128_chars_succeeds() -> None:
    username = "a" * 128
    assert sanitize_username(username) == username


@given(
    st.from_regex(r"[a-zA-Z0-9_\-.@]{1,128}", fullmatch=True).filter(
        lambda s: ".." not in s and "/" not in s and "\\" not in s
    )
)
def test_sanitize_username_with_valid_pattern_always_accepted(username: str) -> None:
    assert sanitize_username(username) == username


@given(st.text())
@settings(max_examples=200)
def test_sanitize_username_never_returns_with_dotdot(s: str) -> None:
    try:
        result = sanitize_username(s)
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result
    except HTTPException:
        pass


# === spr_create_access_token ===


def test_spr_create_access_token_contains_required_claims(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(mocker, tmp_path, auth_enabled=True)
    token = spr_create_access_token("test-user", _TEST_PASSWORD)
    decoded = pyjwt.decode(token, options={"verify_signature": False})
    assert "exp" in decoded
    assert "iat" in decoded
    assert decoded["sub"] == "test-user"
    assert decoded["aud"] == SAPPORO_AUDIENCE


def test_spr_create_access_token_default_expiry_is_24h(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(
        mocker,
        tmp_path,
        auth_enabled=True,
        **{"sapporo_auth_config.expires_delta_hours": None},
    )
    token = spr_create_access_token("test-user", _TEST_PASSWORD)
    decoded = pyjwt.decode(token, options={"verify_signature": False})
    iat = datetime.datetime.fromtimestamp(decoded["iat"], tz=datetime.timezone.utc)
    exp = datetime.datetime.fromtimestamp(decoded["exp"], tz=datetime.timezone.utc)
    delta_hours = (exp - iat).total_seconds() / 3600
    assert delta_hours == pytest.approx(DEFAULT_JWT_EXPIRES_HOURS, abs=0.01)


def test_spr_create_access_token_caps_at_max_hours(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(
        mocker,
        tmp_path,
        auth_enabled=True,
        **{"sapporo_auth_config.expires_delta_hours": 999},
    )
    token = spr_create_access_token("test-user", _TEST_PASSWORD)
    decoded = pyjwt.decode(token, options={"verify_signature": False})
    iat = datetime.datetime.fromtimestamp(decoded["iat"], tz=datetime.timezone.utc)
    exp = datetime.datetime.fromtimestamp(decoded["exp"], tz=datetime.timezone.utc)
    delta_hours = (exp - iat).total_seconds() / 3600
    assert delta_hours == pytest.approx(MAX_JWT_EXPIRES_HOURS, abs=0.01)


# === spr_check_user ===


def test_spr_check_user_with_correct_password_succeeds(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(mocker, tmp_path)
    spr_check_user("test-user", _TEST_PASSWORD)  # Should not raise


def test_spr_check_user_with_wrong_password_raises_401(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(mocker, tmp_path)
    with pytest.raises(HTTPException) as exc_info:
        spr_check_user("test-user", "wrong-password")
    assert exc_info.value.status_code == 401


def test_spr_check_user_with_nonexistent_user_raises_401(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(mocker, tmp_path)
    with pytest.raises(HTTPException) as exc_info:
        spr_check_user("nonexistent-user", "any-password")
    assert exc_info.value.status_code == 401


# === spr_decode_token ===


def test_spr_decode_token_with_valid_token_succeeds(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(mocker, tmp_path, auth_enabled=True)
    token = spr_create_access_token("test-user", _TEST_PASSWORD)
    payload = spr_decode_token(token)
    assert payload.sub == "test-user"
    assert payload.aud == SAPPORO_AUDIENCE


def test_spr_decode_token_with_expired_token_raises_401(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(mocker, tmp_path)
    config = default_auth_config_dict()
    secret_key = config["sapporo_auth_config"]["secret_key"]

    expired_payload = {
        "sub": "test-user",
        "exp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        "iat": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=25),
        "aud": SAPPORO_AUDIENCE,
        "iss": "test",
    }
    expired_token = pyjwt.encode(expired_payload, secret_key, algorithm=SAPPORO_SIGNATURE_ALGORITHM)
    with pytest.raises(HTTPException) as exc_info:
        spr_decode_token(expired_token)
    assert exc_info.value.status_code == 401


def test_spr_decode_token_with_wrong_signature_raises_401(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(mocker, tmp_path)

    wrong_key_payload = {
        "sub": "test-user",
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "aud": SAPPORO_AUDIENCE,
        "iss": "test",
    }
    bad_token = pyjwt.encode(wrong_key_payload, "wrong-secret-key", algorithm=SAPPORO_SIGNATURE_ALGORITHM)
    with pytest.raises(HTTPException) as exc_info:
        spr_decode_token(bad_token)
    assert exc_info.value.status_code == 401


def test_spr_decode_token_with_wrong_audience_raises_401(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_auth(mocker, tmp_path)
    config = default_auth_config_dict()
    secret_key = config["sapporo_auth_config"]["secret_key"]

    wrong_aud_payload = {
        "sub": "test-user",
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "aud": "wrong-audience",
        "iss": "test",
    }
    bad_token = pyjwt.encode(wrong_aud_payload, secret_key, algorithm=SAPPORO_SIGNATURE_ALGORITHM)
    with pytest.raises(HTTPException) as exc_info:
        spr_decode_token(bad_token)
    assert exc_info.value.status_code == 401


# === _validate_https_url / _is_insecure_idp_allowed ===


def test_validate_https_url_with_https_succeeds() -> None:
    _validate_https_url("https://example.com", "Test URL")


def test_validate_https_url_with_http_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_https_url("http://example.com", "Test URL")
    assert exc_info.value.status_code == 400


def test_is_insecure_idp_allowed_default_is_false() -> None:
    assert not _is_insecure_idp_allowed()


def test_is_insecure_idp_allowed_with_env_true() -> None:
    os.environ["SAPPORO_ALLOW_INSECURE_IDP"] = "true"
    assert _is_insecure_idp_allowed()


def test_is_insecure_idp_allowed_with_env_one() -> None:
    os.environ["SAPPORO_ALLOW_INSECURE_IDP"] = "1"
    assert _is_insecure_idp_allowed()


def test_is_insecure_idp_allowed_with_env_yes() -> None:
    os.environ["SAPPORO_ALLOW_INSECURE_IDP"] = "yes"
    assert _is_insecure_idp_allowed()


def test_validate_https_url_with_insecure_allowed_accepts_http() -> None:
    os.environ["SAPPORO_ALLOW_INSECURE_IDP"] = "true"
    _validate_https_url("http://example.com", "Test URL")


# === External mode helpers ===


def _setup_external_auth(mocker: "MockerFixture", tmp_path: Path, **overrides: object) -> None:
    """Set up external auth config and mock get_config."""
    config = default_auth_config_dict()
    config["auth_enabled"] = True
    config["idp_provider"] = "external"
    for key, value in overrides.items():
        if "." in key:
            parts = key.split(".")
            target: dict[str, Any] = config
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
        else:
            config[key] = value
    auth_config_path = write_auth_config(tmp_path, config)

    from sapporo.auth import get_auth_config
    from sapporo.config import AppConfig

    clear_external_auth_caches()
    app_config = AppConfig(auth_config=auth_config_path, debug=True)
    mock_get_config(mocker, app_config)
    # Clear after mock_get_config because importing sapporo.app (via mocker.patch)
    # triggers auth_depends_factory() which caches get_auth_config() at import time
    get_auth_config.cache_clear()


def _mock_fetch_once(metadata_json: Any, jwks_json: Any) -> Any:
    """Return a side_effect function that routes metadata and JWKS URLs."""

    def side_effect(url: str) -> MockHttpxResponse:
        if ".well-known/openid-configuration" in url:
            return MockHttpxResponse(metadata_json)
        return MockHttpxResponse(jwks_json)

    return side_effect


# === fetch_endpoint_metadata cache ===


def test_fetch_endpoint_metadata_returns_cached_on_second_call(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    _, pub = rsa_keypair
    jwks = build_jwks_dict(pub)

    with patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)):
        first = fetch_endpoint_metadata()
        second = fetch_endpoint_metadata()
        assert first.issuer == second.issuer


def test_fetch_endpoint_metadata_cache_cleared_refetches(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    _, pub = rsa_keypair
    jwks = build_jwks_dict(pub)
    call_count = 0

    def counting_side_effect(url: str) -> MockHttpxResponse:
        nonlocal call_count
        if ".well-known/openid-configuration" in url:
            call_count += 1
            return MockHttpxResponse(_MOCK_IDP_METADATA)
        return MockHttpxResponse(jwks)

    with patch("sapporo.auth._fetch_once", side_effect=counting_side_effect):
        fetch_endpoint_metadata()
        assert call_count == 1
        clear_external_auth_caches()
        fetch_endpoint_metadata()
        assert call_count == 2


# === fetch_jwks cache ===


def test_fetch_jwks_returns_cached_on_second_call(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    _, pub = rsa_keypair
    jwks = build_jwks_dict(pub)

    with patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)):
        first = fetch_jwks()
        second = fetch_jwks()
        assert len(first.keys) == len(second.keys)


def test_fetch_jwks_force_refresh_bypasses_cache(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    _, pub = rsa_keypair
    jwks = build_jwks_dict(pub)
    jwks_call_count = 0

    def counting_side_effect(url: str) -> MockHttpxResponse:
        nonlocal jwks_call_count
        if ".well-known/openid-configuration" in url:
            return MockHttpxResponse(_MOCK_IDP_METADATA)
        jwks_call_count += 1
        return MockHttpxResponse(jwks)

    with patch("sapporo.auth._fetch_once", side_effect=counting_side_effect):
        fetch_jwks()
        assert jwks_call_count == 1
        fetch_jwks(force_refresh=True)
        assert jwks_call_count == 2


def test_clear_external_auth_caches_clears_both(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    _, pub = rsa_keypair
    jwks = build_jwks_dict(pub)
    metadata_count = 0
    jwks_count = 0

    def counting_side_effect(url: str) -> MockHttpxResponse:
        nonlocal metadata_count, jwks_count
        if ".well-known/openid-configuration" in url:
            metadata_count += 1
            return MockHttpxResponse(_MOCK_IDP_METADATA)
        jwks_count += 1
        return MockHttpxResponse(jwks)

    with patch("sapporo.auth._fetch_once", side_effect=counting_side_effect):
        fetch_endpoint_metadata()
        fetch_jwks()
        assert metadata_count == 1
        assert jwks_count == 1
        clear_external_auth_caches()
        fetch_endpoint_metadata()
        fetch_jwks()
        assert metadata_count == 2
        assert jwks_count == 2


# === Retry logic ===


def test_fetch_endpoint_metadata_retries_on_transient_error(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_external_auth(mocker, tmp_path)
    attempt = 0

    def flaky_side_effect(url: str) -> MockHttpxResponse:
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            msg = "Connection refused"
            raise httpx.ConnectError(msg)
        return MockHttpxResponse(_MOCK_IDP_METADATA)

    with patch("sapporo.auth._fetch_once", side_effect=flaky_side_effect), patch("sapporo.auth.time.sleep"):
        result = fetch_endpoint_metadata()
        assert result.issuer == _MOCK_IDP_ISSUER


def test_fetch_endpoint_metadata_raises_after_max_retries(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_external_auth(mocker, tmp_path)

    def always_fail(url: str) -> MockHttpxResponse:
        msg = "Connection refused"
        raise httpx.ConnectError(msg)

    with (
        patch("sapporo.auth._fetch_once", side_effect=always_fail),
        patch("sapporo.auth.time.sleep"),
        pytest.raises(HTTPException) as exc_info,
    ):
        fetch_endpoint_metadata()
    assert exc_info.value.status_code == 500


def test_fetch_jwks_retries_on_transient_error(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    _, pub = rsa_keypair
    jwks = build_jwks_dict(pub)
    attempt = 0

    def flaky_side_effect(url: str) -> MockHttpxResponse:
        nonlocal attempt
        if ".well-known/openid-configuration" in url:
            return MockHttpxResponse(_MOCK_IDP_METADATA)
        attempt += 1
        if attempt == 1:
            msg = "Connection refused"
            raise httpx.ConnectError(msg)
        return MockHttpxResponse(jwks)

    with patch("sapporo.auth._fetch_once", side_effect=flaky_side_effect), patch("sapporo.auth.time.sleep"):
        result = fetch_jwks()
        assert len(result.keys) == 1


def test_fetch_jwks_raises_after_max_retries(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_external_auth(mocker, tmp_path)
    call_count = 0

    def route_side_effect(url: str) -> MockHttpxResponse:
        nonlocal call_count
        if ".well-known/openid-configuration" in url:
            return MockHttpxResponse(_MOCK_IDP_METADATA)
        call_count += 1
        msg = "Connection refused"
        raise httpx.ConnectError(msg)

    with patch("sapporo.auth._fetch_once", side_effect=route_side_effect), patch("sapporo.auth.time.sleep"):
        # First populate metadata cache
        fetch_endpoint_metadata()
        clear_external_auth_caches()
        # Fetch metadata again so it's cached, then try JWKS
        fetch_endpoint_metadata()
        with pytest.raises(HTTPException) as exc_info:
            fetch_jwks()
        assert exc_info.value.status_code == 500


# === Key rotation ===


def test_external_decode_token_key_rotation_success(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any], rsa_keypair_2: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    priv1, pub1 = rsa_keypair
    _, pub2 = rsa_keypair_2

    # Sign with key 1, but initial JWKS only has key 2
    token = create_signed_jwt(priv1, kid="kid-1")
    old_jwks = build_jwks_dict(pub2, kid="kid-2")
    new_jwks = {"keys": old_jwks["keys"] + build_jwks_dict(pub1, kid="kid-1")["keys"]}

    refresh_count = 0

    def routing_side_effect(url: str) -> MockHttpxResponse:
        nonlocal refresh_count
        if ".well-known/openid-configuration" in url:
            return MockHttpxResponse(_MOCK_IDP_METADATA)
        refresh_count += 1
        if refresh_count == 1:
            return MockHttpxResponse(old_jwks)
        return MockHttpxResponse(new_jwks)

    with patch("sapporo.auth._fetch_once", side_effect=routing_side_effect), patch("sapporo.auth.time.sleep"):
        payload = external_decode_token(token)
        assert payload.sub == "test-user"


def test_external_decode_token_key_rotation_failure(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any], rsa_keypair_2: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    priv1, _ = rsa_keypair
    _, pub2 = rsa_keypair_2

    # Sign with key 1, but JWKS always only has key 2
    token = create_signed_jwt(priv1, kid="kid-1")
    jwks = build_jwks_dict(pub2, kid="kid-2")

    with (
        patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)),
        patch("sapporo.auth.time.sleep"),
        pytest.raises(HTTPException) as exc_info,
    ):
        external_decode_token(token)
    assert exc_info.value.status_code == 401


# === Algorithm restriction ===


def test_external_decode_token_with_hs256_raises_401(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    _, pub = rsa_keypair
    jwks = build_jwks_dict(pub)

    # HS256 token
    hs_token = pyjwt.encode(
        {
            "sub": "test-user",
            "iss": _MOCK_IDP_ISSUER,
            "aud": "account",
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        "secret",
        algorithm="HS256",
        headers={"kid": "test-kid-1"},
    )

    with (
        patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)),
        patch("sapporo.auth.time.sleep"),
        pytest.raises(HTTPException) as exc_info,
    ):
        external_decode_token(hs_token)
    assert exc_info.value.status_code == 401


def test_external_decode_token_with_rs256_succeeds(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    priv, pub = rsa_keypair
    jwks = build_jwks_dict(pub)
    token = create_signed_jwt(priv)

    with (
        patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)),
        patch("sapporo.auth.time.sleep"),
    ):
        payload = external_decode_token(token)
        assert payload.sub == "test-user"


def test_external_decode_token_without_kid_raises_401(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    priv, pub = rsa_keypair
    jwks = build_jwks_dict(pub)

    # Token without kid header
    no_kid_token = pyjwt.encode(
        {
            "sub": "test-user",
            "iss": _MOCK_IDP_ISSUER,
            "aud": "account",
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        priv,
        algorithm="RS256",
    )

    with (
        patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)),
        patch("sapporo.auth.time.sleep"),
        pytest.raises(HTTPException) as exc_info,
    ):
        external_decode_token(no_kid_token)
    assert exc_info.value.status_code == 401


def test_external_decode_token_malformed_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        external_decode_token("not.a.valid.jwt.at.all")
    assert exc_info.value.status_code == 401


def test_external_decode_token_empty_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        external_decode_token("")
    assert exc_info.value.status_code == 401


# === Issuer verification ===


def test_external_decode_token_wrong_issuer_raises_401(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    priv, pub = rsa_keypair
    jwks = build_jwks_dict(pub)
    token = create_signed_jwt(priv, issuer="https://evil.example.com/realms/fake")

    with (
        patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)),
        patch("sapporo.auth.time.sleep"),
        pytest.raises(HTTPException) as exc_info,
    ):
        external_decode_token(token)
    assert exc_info.value.status_code == 401


def test_external_decode_token_correct_issuer_succeeds(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    priv, pub = rsa_keypair
    jwks = build_jwks_dict(pub)
    token = create_signed_jwt(priv, issuer=_MOCK_IDP_ISSUER)

    with (
        patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)),
        patch("sapporo.auth.time.sleep"),
    ):
        payload = external_decode_token(token)
        assert payload.iss == _MOCK_IDP_ISSUER


# === Timeout ===


def test_fetch_endpoint_metadata_uses_timeout(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_external_auth(mocker, tmp_path)

    with patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, {})):
        fetch_endpoint_metadata()

    # Verify timeout is set in HTTPX_TIMEOUT constant
    from sapporo.auth import HTTPX_TIMEOUT

    assert HTTPX_TIMEOUT == 10.0


def test_fetch_jwks_uses_timeout(mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]) -> None:
    _setup_external_auth(mocker, tmp_path)
    _, pub = rsa_keypair
    jwks = build_jwks_dict(pub)

    with patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)):
        fetch_jwks()

    from sapporo.auth import HTTPX_TIMEOUT

    assert HTTPX_TIMEOUT == 10.0


# === Edge cases ===


def test_external_decode_token_expired_raises_401(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    priv, pub = rsa_keypair
    jwks = build_jwks_dict(pub)
    token = create_signed_jwt(priv, expired=True)

    with (
        patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)),
        patch("sapporo.auth.time.sleep"),
        pytest.raises(HTTPException) as exc_info,
    ):
        external_decode_token(token)
    assert exc_info.value.status_code == 401


def test_external_decode_token_wrong_audience_raises_401(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    priv, pub = rsa_keypair
    jwks = build_jwks_dict(pub)
    token = create_signed_jwt(priv, audience="wrong-audience")

    with (
        patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)),
        patch("sapporo.auth.time.sleep"),
        pytest.raises(HTTPException) as exc_info,
    ):
        external_decode_token(token)
    assert exc_info.value.status_code == 401


def test_external_decode_token_invalid_signature_raises_401(
    mocker: "MockerFixture", tmp_path: Path, rsa_keypair: tuple[Any, Any], rsa_keypair_2: tuple[Any, Any]
) -> None:
    _setup_external_auth(mocker, tmp_path)
    priv2, _ = rsa_keypair_2
    _, pub1 = rsa_keypair
    jwks = build_jwks_dict(pub1)

    # Sign with key 2, but JWKS has key 1 with the same kid
    token = create_signed_jwt(priv2, kid="test-kid-1")

    with (
        patch("sapporo.auth._fetch_once", side_effect=_mock_fetch_once(_MOCK_IDP_METADATA, jwks)),
        patch("sapporo.auth.time.sleep"),
        pytest.raises(HTTPException) as exc_info,
    ):
        external_decode_token(token)
    assert exc_info.value.status_code == 401
