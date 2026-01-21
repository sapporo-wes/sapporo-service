# pylint: disable=C0415, W0613, W0621

"""\
Tests for authentication and security features.

Some tests (like external IdP integration) require external services
and may be skipped in basic test runs.
"""


import json
from typing import Any, Dict

import pytest
from argon2 import PasswordHasher

from .conftest import anyhow_get_test_client, post_run, wait_for_run
from .test_run_cwltool import remote_wf_run_request

# Generate a password hash for testing
_ph = PasswordHasher()
_TEST_PASSWORD = "sapporo-dev-password"
_TEST_PASSWORD_HASH = _ph.hash(_TEST_PASSWORD)


def default_auth_config() -> Dict[str, Any]:
    """Default auth config with password hash (not plaintext)."""
    return {
        "auth_enabled": False,
        "idp_provider": "sapporo",
        "sapporo_auth_config": {
            "secret_key": "sapporo_secret_key_please_change_this",
            "expires_delta_hours": 24,
            "users": [
                {
                    "username": "sapporo-dev-user",
                    "password_hash": _TEST_PASSWORD_HASH
                }
            ]
        },
        "external_config": {
            "idp_url": "http://sapporo-keycloak-dev:8080/realms/sapporo-dev",
            "jwt_audience": "account",
            "client_mode": "public",
            "client_id": "sapporo-service-dev",
            "client_secret": "example-client-secret"
        }
    }


def test_no_auth_get_runs(mocker, tmpdir):  # type: ignore
    from sapporo.config import AppConfig

    auth_config = tmpdir.joinpath("auth_config.json")
    with auth_config.open("w", encoding="utf-8") as f:
        f.write(json.dumps(default_auth_config()))
    app_config = AppConfig(auth_config=auth_config)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = client.get("/runs")
    assert response.status_code == 200


def test_no_auth_post_runs(mocker, tmpdir):  # type: ignore
    from sapporo.config import AppConfig

    auth_config = tmpdir.joinpath("auth_config.json")
    with auth_config.open("w", encoding="utf-8") as f:
        f.write(json.dumps(default_auth_config()))
    app_config = AppConfig(auth_config=auth_config)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = post_run(client, **remote_wf_run_request)  # type: ignore
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]
    wait_for_run(client, run_id)


# === Password Hashing Tests ===


def test_password_hash_verification():  # type: ignore
    """Test that password hashing works correctly."""
    from sapporo.auth import _password_hasher

    password = "test_password_123"
    hashed = _password_hasher.hash(password)

    # Verify correct password
    _password_hasher.verify(hashed, password)

    # Verify wrong password raises exception
    from argon2.exceptions import VerifyMismatchError
    with pytest.raises(VerifyMismatchError):
        _password_hasher.verify(hashed, "wrong_password")


def test_auth_with_hashed_password(mocker, tmpdir):  # type: ignore
    """Test authentication with hashed password."""
    from sapporo.config import AppConfig

    config = default_auth_config()
    config["auth_enabled"] = True

    auth_config = tmpdir.joinpath("auth_config.json")
    with auth_config.open("w", encoding="utf-8") as f:
        f.write(json.dumps(config))

    # Use debug mode to bypass weak secret_key check
    app_config = AppConfig(auth_config=auth_config, debug=True)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    # Test successful authentication
    response = client.post(
        "/token",
        data={
            "username": "sapporo-dev-user",
            "password": _TEST_PASSWORD,
        }
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Test failed authentication with wrong password
    response = client.post(
        "/token",
        data={
            "username": "sapporo-dev-user",
            "password": "wrong_password",
        }
    )
    assert response.status_code == 401


# === Username Validation Tests ===


def test_username_sanitization():  # type: ignore
    """Test username sanitization function."""
    from fastapi import HTTPException

    from sapporo.auth import sanitize_username

    # Valid usernames
    assert sanitize_username("user1") == "user1"
    assert sanitize_username("user_name") == "user_name"
    assert sanitize_username("user-name") == "user-name"
    assert sanitize_username("user.name") == "user.name"
    assert sanitize_username("user@example.com") == "user@example.com"

    # Invalid usernames should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("../../../etc/passwd")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("user/name")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("user\\name")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("")
    assert exc_info.value.status_code == 400

    # Too long username
    with pytest.raises(HTTPException) as exc_info:
        sanitize_username("a" * 129)
    assert exc_info.value.status_code == 400


# === JWT Expiration Tests ===


def test_jwt_always_has_expiration(mocker, tmpdir):  # type: ignore
    """Test that JWT tokens always have an expiration time."""
    from sapporo.config import AppConfig

    config = default_auth_config()
    config["auth_enabled"] = True
    config["sapporo_auth_config"]["expires_delta_hours"] = None  # Try to create token without expiration

    auth_config = tmpdir.joinpath("auth_config.json")
    with auth_config.open("w", encoding="utf-8") as f:
        f.write(json.dumps(config))

    app_config = AppConfig(auth_config=auth_config, debug=True)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    response = client.post(
        "/token",
        data={
            "username": "sapporo-dev-user",
            "password": _TEST_PASSWORD,
        }
    )
    assert response.status_code == 200
    token_data = response.json()

    # Decode and verify the token has an expiration
    import jwt
    decoded = jwt.decode(
        token_data["access_token"],
        options={"verify_signature": False}
    )
    assert "exp" in decoded
    assert decoded["exp"] is not None


# === Page Token Signature Tests ===


def test_page_token_signature(mocker, tmpdir):  # type: ignore
    """Test that page tokens are signed and verified."""
    from sapporo.config import AppConfig

    auth_config = tmpdir.joinpath("auth_config.json")
    with auth_config.open("w", encoding="utf-8") as f:
        f.write(json.dumps(default_auth_config()))
    app_config = AppConfig(auth_config=auth_config)
    client = anyhow_get_test_client(app_config, mocker, tmpdir)

    # Create some runs to get a page token
    for _ in range(3):
        response = post_run(client, **remote_wf_run_request)  # type: ignore
        assert response.status_code == 200

    # Get runs with page_size=1 to get a next_page_token
    response = client.get("/runs?page_size=1")
    assert response.status_code == 200
    data = response.json()

    if data.get("next_page_token"):
        next_token = data["next_page_token"]

        # Valid token should work
        response = client.get(f"/runs?page_token={next_token}")
        assert response.status_code == 200

        # Tampered token should fail
        tampered_token = next_token[:-5] + "XXXXX"
        response = client.get(f"/runs?page_token={tampered_token}")
        assert response.status_code == 400


# === HTTPS Validation Tests ===


def test_https_validation_for_external_idp():  # type: ignore
    """Test that external IdP URLs are validated for HTTPS."""
    import os

    from fastapi import HTTPException

    from sapporo.auth import _is_insecure_idp_allowed, _validate_https_url

    # Save original env var
    original_value = os.environ.get("SAPPORO_ALLOW_INSECURE_IDP")

    try:
        # Without bypass, HTTP should be rejected
        if "SAPPORO_ALLOW_INSECURE_IDP" in os.environ:
            del os.environ["SAPPORO_ALLOW_INSECURE_IDP"]

        assert not _is_insecure_idp_allowed()

        with pytest.raises(HTTPException) as exc_info:
            _validate_https_url("http://example.com", "Test URL")
        assert exc_info.value.status_code == 400

        # HTTPS should be accepted
        _validate_https_url("https://example.com", "Test URL")  # Should not raise

        # With bypass enabled
        os.environ["SAPPORO_ALLOW_INSECURE_IDP"] = "true"
        assert _is_insecure_idp_allowed()
        _validate_https_url("http://example.com", "Test URL")  # Should not raise

    finally:
        # Restore original env var
        if original_value is not None:
            os.environ["SAPPORO_ALLOW_INSECURE_IDP"] = original_value
        elif "SAPPORO_ALLOW_INSECURE_IDP" in os.environ:
            del os.environ["SAPPORO_ALLOW_INSECURE_IDP"]


# === User Isolation Tests ===


def test_user_isolation_in_state_counts(mocker, tmpdir):  # type: ignore
    """Test that system_state_counts can be filtered by username."""
    from sapporo.config import AppConfig
    from sapporo.database import add_run_db, system_state_counts
    from sapporo.schemas import RunSummary, State

    auth_config = tmpdir.joinpath("auth_config.json")
    with auth_config.open("w", encoding="utf-8") as f:
        f.write(json.dumps(default_auth_config()))
    app_config = AppConfig(auth_config=auth_config, run_dir=tmpdir)

    # Initialize
    from .conftest import clear_cache, mock_get_config
    mock_get_config(mocker, app_config)
    clear_cache()

    from sapporo.database import init_db
    init_db()

    # Add runs for different users
    run1 = RunSummary(
        run_id="test-run-1",
        state=State.COMPLETE,
        start_time="2024-01-01T00:00:00Z",
        end_time="2024-01-01T01:00:00Z",
        tags={},
    )
    add_run_db(run1, username="user1")

    run2 = RunSummary(
        run_id="test-run-2",
        state=State.RUNNING,
        start_time="2024-01-01T00:00:00Z",
        end_time=None,
        tags={},
    )
    add_run_db(run2, username="user2")

    # All runs
    counts_all = system_state_counts()
    assert counts_all["COMPLETE"] == 1
    assert counts_all["RUNNING"] == 1

    # User1 only
    counts_user1 = system_state_counts(username="user1")
    assert counts_user1["COMPLETE"] == 1
    assert counts_user1["RUNNING"] == 0

    # User2 only
    counts_user2 = system_state_counts(username="user2")
    assert counts_user2["COMPLETE"] == 0
    assert counts_user2["RUNNING"] == 1
