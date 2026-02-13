import pytest
from fastapi import HTTPException
from hypothesis import given
from hypothesis import strategies as st

from sapporo.exceptions import (
    raise_bad_request,
    raise_forbidden,
    raise_internal_error,
    raise_invalid_credentials,
    raise_invalid_token,
    raise_not_found,
    raise_unauthorized,
)


def test_raise_unauthorized_returns_401_with_detail() -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_unauthorized("test message")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "test message"


def test_raise_invalid_token_returns_401_with_fixed_message() -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_invalid_token()
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


def test_raise_invalid_credentials_returns_401_with_fixed_message() -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_invalid_credentials()
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid username or password"


def test_raise_bad_request_returns_400_with_detail() -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_bad_request("bad input")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "bad input"


def test_raise_not_found_returns_404_with_formatted_message() -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_not_found("Run ID", "abc-123")
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Run ID abc-123 not found."


def test_raise_forbidden_returns_403_with_detail() -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_forbidden("access denied")
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "access denied"


def test_raise_internal_error_returns_500_with_detail() -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_internal_error("server broke")
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "server broke"


@given(st.text(min_size=1))
def test_raise_unauthorized_with_arbitrary_detail_preserves_message(detail: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_unauthorized(detail)
    assert exc_info.value.detail == detail


@given(st.text(min_size=1), st.text(min_size=1))
def test_raise_not_found_with_arbitrary_inputs_formats_correctly(resource: str, identifier: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        raise_not_found(resource, identifier)
    assert exc_info.value.detail == f"{resource} {identifier} not found."
