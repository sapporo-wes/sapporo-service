# pylint: disable=C0415, W0613, W0621, W1406

from pathlib import Path, PosixPath

import pytest

test_cases = [
    ("My cool movie.mov", Path("My_cool_movie.mov")),  # Filename with spaces
    ("../../../etc/passwd", Path("etc/passwd")),  # Relative path
    ("/foo/bar", Path("foo/bar")),  # Absolute path
    (u"i contain cool \xfcml\xe4uts.txt", Path("i_contain_cool_umlauts.txt")),  # Filename with umlauts
    ("/フーfoo/バーbar", Path("foo/bar")),  # Filename in Japanese
    ("/||/|foo/bar", Path("foo/bar")),  # Filename with pipe characters
    ("/&&/&foo/bar", Path("foo/bar")),  # Filename with ampersands
    ("/＆foo/bar", Path("foo/bar")),  # Filename with full-width ampersands
    (".", Path("")),  # Filename with only a dot
    ("..", Path("")),  # Filename with only two dots
    ("/", Path("")),  # Root directory
    (".foo", PosixPath(".foo")),  # Hidden file
    ("._.DS_STORE", PosixPath("._.DS_STORE")),  # DS_STORE file
    ("test_case_with_...dots", Path("test_case_with_dots")),  # Filename with multiple dots
    ("test_case_with_special_chars_!@#$%^&*()", Path("test_case_with_special_chars_")),  # Filename with special characters
    ("filename_with_underscores_and-hyphens", Path("filename_with_underscores_and-hyphens")),  # Filename with underscores and hyphens
]


@pytest.mark.parametrize("test_input,expected", test_cases)
def test_secure_filepath(test_input: str, expected: Path) -> None:
    from sapporo.utils import secure_filepath

    assert secure_filepath(test_input) == expected
