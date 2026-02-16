import sys
from argparse import Namespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sapporo.cli import generate_secret, hash_password, main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# === hash_password ===


def test_hash_password_with_password_flag_prints_hash(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(password="test-password-123")
    hash_password(args)
    captured = capsys.readouterr()
    assert "Password hash:" in captured.out
    assert "$argon2" in captured.out


def test_hash_password_interactive_matching_prints_hash(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(password=None)
    with patch("sapporo.cli.getpass", side_effect=["my-secret", "my-secret"]):
        hash_password(args)
    captured = capsys.readouterr()
    assert "Password hash:" in captured.out


def test_hash_password_interactive_mismatch_exits_with_error(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace(password=None)
    with patch("sapporo.cli.getpass", side_effect=["password1", "password2"]):
        with pytest.raises(SystemExit) as exc_info:
            hash_password(args)
        assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "do not match" in captured.err


def test_hash_password_output_is_valid_argon2_hash(capsys: pytest.CaptureFixture[str]) -> None:
    from argon2 import PasswordHasher

    args = Namespace(password="verify-me")
    hash_password(args)
    captured = capsys.readouterr()
    password_hash = captured.out.split("Password hash: ")[1].strip()

    ph = PasswordHasher()
    assert ph.verify(password_hash, "verify-me")


@settings(max_examples=20)
@given(password=st.text(min_size=1, max_size=50))
def test_hash_password_arbitrary_password_produces_valid_hash(password: str) -> None:
    from io import StringIO

    from argon2 import PasswordHasher

    args = Namespace(password=password)
    with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
        hash_password(args)
    output = mock_stdout.getvalue()
    password_hash = output.split("Password hash: ")[1].strip()

    ph = PasswordHasher()
    assert ph.verify(password_hash, password)


# === generate_secret ===


def test_generate_secret_prints_secret_key(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace()
    generate_secret(args)
    captured = capsys.readouterr()
    assert "Secret key:" in captured.out


def test_generate_secret_output_length_at_least_32_chars(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace()
    generate_secret(args)
    captured = capsys.readouterr()
    secret = captured.out.split("Secret key: ")[1].strip()
    assert len(secret) >= 32


def test_generate_secret_different_each_call(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace()
    generate_secret(args)
    out1 = capsys.readouterr().out.split("Secret key: ")[1].strip()

    generate_secret(args)
    out2 = capsys.readouterr().out.split("Secret key: ")[1].strip()

    assert out1 != out2


# === main (ArgumentParser) ===


def test_main_hash_password_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["sapporo-cli", "hash-password", "--password", "test123"]
    main()
    captured = capsys.readouterr()
    assert "Password hash:" in captured.out


def test_main_generate_secret_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["sapporo-cli", "generate-secret"]
    main()
    captured = capsys.readouterr()
    assert "Secret key:" in captured.out


def test_main_no_command_exits_with_error() -> None:
    sys.argv = ["sapporo-cli"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


# === main: additional argument parsing tests ===


def test_main_hash_password_passes_specific_password(capsys: pytest.CaptureFixture[str]) -> None:
    from argon2 import PasswordHasher

    sys.argv = ["sapporo-cli", "hash-password", "--password", "specific-pw"]
    main()
    captured = capsys.readouterr()
    password_hash = captured.out.split("Password hash: ")[1].strip()

    ph = PasswordHasher()
    assert ph.verify(password_hash, "specific-pw")


def test_main_hash_password_interactive_via_main(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["sapporo-cli", "hash-password"]
    with patch("sapporo.cli.getpass", side_effect=["interactive-pw", "interactive-pw"]):
        main()
    captured = capsys.readouterr()
    assert "Password hash:" in captured.out


def test_main_generate_secret_output_is_urlsafe_base64_43_chars(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["sapporo-cli", "generate-secret"]
    main()
    captured = capsys.readouterr()
    secret = captured.out.split("Secret key: ")[1].strip()

    # token_urlsafe(32) produces exactly 43 characters
    assert len(secret) == 43


def test_main_invalid_subcommand_exits_with_error() -> None:
    sys.argv = ["sapporo-cli", "nonexistent-command"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


def test_main_hash_password_numeric_string_password(capsys: pytest.CaptureFixture[str]) -> None:
    from argon2 import PasswordHasher

    sys.argv = ["sapporo-cli", "hash-password", "--password", "12345"]
    main()
    captured = capsys.readouterr()
    password_hash = captured.out.split("Password hash: ")[1].strip()

    ph = PasswordHasher()
    assert ph.verify(password_hash, "12345")


# === generate_secret: precise length test ===


def test_generate_secret_output_exactly_43_chars(capsys: pytest.CaptureFixture[str]) -> None:
    args = Namespace()
    generate_secret(args)
    captured = capsys.readouterr()
    secret = captured.out.split("Secret key: ")[1].strip()

    # secrets.token_urlsafe(32) produces exactly 43 characters
    assert len(secret) == 43


def test_generate_secret_calls_token_urlsafe_with_32(mocker: "MockerFixture") -> None:
    mocker.patch("sapporo.cli.secrets.token_urlsafe", return_value="a" * 43)
    args = Namespace()
    generate_secret(args)
    import sapporo.cli

    sapporo.cli.secrets.token_urlsafe.assert_called_once_with(32)


# === main: --help output verification ===


def test_main_help_contains_description_and_subcommand_help(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["sapporo-cli", "--help"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "CLI tools for sapporo-service." in captured.out
    assert "XXCLI" not in captured.out
    assert "Hash a password using argon2." in captured.out
    assert "XXHash" not in captured.out
    assert "Generate a cryptographically secure secret key." in captured.out
    assert "XXGenerate" not in captured.out


def test_main_hash_password_help_contains_password_argument_help(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["sapporo-cli", "hash-password", "--help"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    # argparse may wrap long help text, so check a stable substring
    assert "Password to hash" in captured.out
    assert "XXPassword" not in captured.out
    assert "--password" in captured.out
