from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sapporo.utils import (
    dt_to_time_str,
    now_str,
    sapporo_version,
    secure_filepath,
    time_str_to_dt,
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
        (".", Path()),
        ("..", Path()),
        ("/", Path()),
        (".foo", Path(".foo")),
        ("._.DS_STORE", Path("._.DS_STORE")),
        ("test_case_with_...dots", Path("test_case_with_dots")),
        ("test_case_with_special_chars_!@#$%^&*()", Path("test_case_with_special_chars_")),
        ("filename_with_underscores_and-hyphens", Path("filename_with_underscores_and-hyphens")),
    ],
)
def test_secure_filepath_with_known_inputs_returns_expected(test_input: str, expected: Path) -> None:
    assert secure_filepath(test_input) == expected


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
def test_secure_filepath_never_contains_dotdot(filepath: str) -> None:
    result = secure_filepath(filepath)
    for part in result.parts:
        assert ".." not in part


@given(st.text())
def test_secure_filepath_never_starts_with_slash(filepath: str) -> None:
    result_str = str(result) if (result := secure_filepath(filepath)).parts else ""
    assert not result_str.startswith("/")


@given(st.text())
def test_secure_filepath_never_crashes(filepath: str) -> None:
    result = secure_filepath(filepath)
    assert isinstance(result, Path)
