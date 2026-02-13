import datetime
import os
from pathlib import Path
from typing import TYPE_CHECKING

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
    _validate_https_url,
    sanitize_username,
    spr_check_user,
    spr_create_access_token,
    spr_decode_token,
)

from .conftest import default_auth_config_dict, mock_get_config, write_auth_config

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

    get_auth_config.cache_clear()
    app_config = AppConfig(auth_config=auth_config_path, debug=True)
    mock_get_config(mocker, app_config)


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
