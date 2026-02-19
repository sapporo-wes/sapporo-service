import socket
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from hypothesis import given
from hypothesis import strategies as st

from sapporo.utils import (
    dt_to_time_str,
    mask_sensitive,
    now_str,
    sapporo_version,
    secure_filepath,
    tail_file,
    time_str_to_dt,
    validate_url_not_metadata_service,
)

# === now_str ===


def test_now_str_returns_rfc3339_utc_format() -> None:
    result = now_str()
    assert result.endswith("Z")
    dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
    assert dt.tzinfo is not None


def test_now_str_returns_seconds_precision() -> None:
    result = now_str()
    # RFC 3339 seconds precision: "2022-01-01T00:00:00Z" (20 chars)
    assert len(result) == 20


# === time_str_to_dt / dt_to_time_str round-trip ===


def test_time_str_to_dt_parses_rfc3339_with_z() -> None:
    dt = time_str_to_dt("2024-01-15T10:30:00Z")
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 15
    assert dt.hour == 10
    assert dt.minute == 30
    assert dt.second == 0
    assert dt.tzinfo is not None


def test_dt_to_time_str_formats_utc_with_z() -> None:
    dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    result = dt_to_time_str(dt)
    assert result == "2024-01-15T10:30:00Z"


@given(
    st.datetimes(
        min_value=datetime(2000, 1, 1),  # noqa: DTZ001 (hypothesis requires naive min_value)
        max_value=datetime(2099, 12, 31),  # noqa: DTZ001 (hypothesis requires naive max_value)
        timezones=st.just(timezone.utc),
    )
)
def test_time_str_round_trip_preserves_seconds(dt: datetime) -> None:
    dt_truncated = dt.replace(microsecond=0)
    result = time_str_to_dt(dt_to_time_str(dt_truncated))
    assert result == dt_truncated


# === sapporo_version ===


def test_sapporo_version_returns_nonempty_string() -> None:
    version = sapporo_version()
    assert isinstance(version, str)
    assert len(version) > 0


# === secure_filepath ===


# Existing test cases from tests/py_tests/test_secure_filepath.py
@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        ("My cool movie.mov", Path("My_cool_movie.mov")),
        ("../../../etc/passwd", Path("etc/passwd")),
        ("/foo/bar", Path("foo/bar")),
        ("i contain cool \xfcml\xe4uts.txt", Path("i_contain_cool_umlauts.txt")),
        ("/\u30d5\u30fcfoo/\u30d0\u30fcbar", Path("foo/bar")),
        ("/||/|foo/bar", Path("foo/bar")),
        ("/&&/&foo/bar", Path("foo/bar")),
        ("/\uff06foo/bar", Path("foo/bar")),
        (".foo", Path(".foo")),
        ("._.DS_STORE", Path("._.DS_STORE")),
        ("test_case_with_...dots", Path("test_case_with_dots")),
        ("test_case_with_special_chars_!@#$%^&*()", Path("test_case_with_special_chars_")),
        ("filename_with_underscores_and-hyphens", Path("filename_with_underscores_and-hyphens")),
    ],
)
def test_secure_filepath_with_known_inputs_returns_expected(test_input: str, expected: Path) -> None:
    assert secure_filepath(test_input) == expected


@pytest.mark.parametrize("test_input", [".", "..", "/"])
def test_secure_filepath_with_empty_result_raises_400(test_input: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        secure_filepath(test_input)
    assert exc_info.value.status_code == 400


# Path traversal cases
def test_secure_filepath_with_path_traversal_strips_dotdot() -> None:
    result = secure_filepath("../../secret/file.txt")
    assert ".." not in str(result)


def test_secure_filepath_with_null_bytes_strips_them() -> None:
    result = secure_filepath("file\x00name.txt")
    assert "\x00" not in str(result)


def test_secure_filepath_with_triple_dots_strips_them() -> None:
    result = secure_filepath("foo/.../bar")
    assert "..." not in str(result)


# PBT: Security invariants
@given(st.text())
def test_secure_filepath_never_has_dotdot_component(filepath: str) -> None:
    try:
        result = secure_filepath(filepath)
    except HTTPException:
        return
    for part in result.parts:
        assert part != ".."


@given(st.text())
def test_secure_filepath_never_starts_with_slash(filepath: str) -> None:
    try:
        result = secure_filepath(filepath)
    except HTTPException:
        return
    result_str = str(result) if result.parts else ""
    assert not result_str.startswith("/")


@given(st.text())
def test_secure_filepath_never_crashes(filepath: str) -> None:
    try:
        result = secure_filepath(filepath)
        assert isinstance(result, Path)
    except HTTPException:
        pass  # Only HTTPException(400) is expected from secure_filepath


# === tail_file ===


def test_tail_file_returns_last_n_lines(tmp_path: Path) -> None:
    f = tmp_path / "log.txt"
    f.write_text("\n".join(f"line{i}" for i in range(100)), encoding="utf-8")
    result = tail_file(f, n_lines=3)
    assert result == "line97\nline98\nline99"


def test_tail_file_with_empty_file_returns_empty_string(tmp_path: Path) -> None:
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    assert tail_file(f) == ""


def test_tail_file_with_nonexistent_file_returns_empty_string(tmp_path: Path) -> None:
    assert tail_file(tmp_path / "nonexistent.txt") == ""


def test_tail_file_with_fewer_lines_than_requested(tmp_path: Path) -> None:
    f = tmp_path / "short.txt"
    f.write_text("only\ntwo", encoding="utf-8")
    result = tail_file(f, n_lines=10)
    assert result == "only\ntwo"


# === mask_sensitive ===


def test_mask_sensitive_replaces_specified_keys() -> None:
    obj = {"username": "alice", "password": "secret", "host": "localhost"}
    result = mask_sensitive(obj, {"password"})
    assert result == {"username": "alice", "password": "***", "host": "localhost"}


def test_mask_sensitive_recurses_into_nested_dicts() -> None:
    obj = {"db": {"host": "localhost", "password": "secret"}, "name": "app"}
    result = mask_sensitive(obj, {"password"})
    assert result == {"db": {"host": "localhost", "password": "***"}, "name": "app"}


def test_mask_sensitive_does_not_modify_original() -> None:
    obj = {"password": "secret"}
    mask_sensitive(obj, {"password"})
    assert obj["password"] == "secret"


def test_mask_sensitive_with_no_matching_keys_returns_copy() -> None:
    obj = {"a": 1, "b": 2}
    result = mask_sensitive(obj, {"password"})
    assert result == {"a": 1, "b": 2}


# === read_run_dir_file ===


def test_read_run_dir_file_returns_json_for_json_content(tmp_path: Path) -> None:
    import sapporo.config
    from sapporo.utils import read_run_dir_file

    # Create a state file with JSON content
    state_file = tmp_path / "state.txt"
    state_file.write_text('"COMPLETE"', encoding="utf-8")

    orig = sapporo.config.RUN_DIR_STRUCTURE.copy()
    sapporo.config.RUN_DIR_STRUCTURE["state"] = "state.txt"
    try:
        result = read_run_dir_file(tmp_path, "state")
        assert result == "COMPLETE"
    finally:
        sapporo.config.RUN_DIR_STRUCTURE.update(orig)


def test_read_run_dir_file_returns_plain_text_for_non_json(tmp_path: Path) -> None:
    import sapporo.config
    from sapporo.utils import read_run_dir_file

    plain_file = tmp_path / "stdout.txt"
    plain_file.write_text("hello world\n", encoding="utf-8")

    orig = sapporo.config.RUN_DIR_STRUCTURE.copy()
    sapporo.config.RUN_DIR_STRUCTURE["stdout"] = "stdout.txt"
    try:
        result = read_run_dir_file(tmp_path, "stdout")
        assert result == "hello world\n"
    finally:
        sapporo.config.RUN_DIR_STRUCTURE.update(orig)


def test_read_run_dir_file_returns_none_for_missing_file(tmp_path: Path) -> None:
    from sapporo.utils import read_run_dir_file

    result = read_run_dir_file(tmp_path, "state")
    assert result is None


def test_read_run_dir_file_returns_none_for_dir_key(tmp_path: Path) -> None:
    from sapporo.utils import read_run_dir_file

    result = read_run_dir_file(tmp_path, "exe_dir")
    assert result is None


# === validate_url_not_metadata_service ===


def test_validate_url_public_url_passes() -> None:
    validate_url_not_metadata_service("https://example.com/file.txt")


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8080/file.txt",
        "http://127.0.0.1/file.txt",
        "http://10.0.0.1/file.txt",
        "http://192.168.1.1/file.txt",
    ],
)
def test_validate_url_private_ips_are_allowed(url: str) -> None:
    validate_url_not_metadata_service(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.0.1/metadata",
    ],
)
def test_validate_url_link_local_ip_is_blocked(url: str) -> None:
    with pytest.raises(ValueError, match="link-local"):
        validate_url_not_metadata_service(url)


def test_validate_url_dns_rebinding_to_link_local_is_blocked() -> None:
    fake_addrinfo = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0)),
    ]
    with (
        patch("sapporo.utils.socket.getaddrinfo", return_value=fake_addrinfo),
        pytest.raises(ValueError, match="link-local"),
    ):
        validate_url_not_metadata_service("http://evil.example.com/steal")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file.txt",
        "gopher://example.com/",
    ],
)
def test_validate_url_non_http_scheme_is_blocked(url: str) -> None:
    with pytest.raises(ValueError, match="http or https"):
        validate_url_not_metadata_service(url)


def test_validate_url_dns_resolution_failure_passes() -> None:
    with patch("sapporo.utils.socket.getaddrinfo", side_effect=socket.gaierror("DNS failed")):
        validate_url_not_metadata_service("http://nonexistent.example.com/file.txt")
