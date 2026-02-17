import sys
from argparse import Namespace
from pathlib import Path
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
    mock_token = mocker.patch("sapporo.cli.secrets.token_urlsafe", return_value="a" * 43)
    args = Namespace()
    generate_secret(args)
    mock_token.assert_called_once_with(32)


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


# === generate-ro-crate ===


def test_generate_ro_crate_nonexistent_dir_exits_with_error(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["sapporo-cli", "generate-ro-crate", "/nonexistent/path"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "does not exist" in captured.err


def test_generate_ro_crate_file_not_dir_exits_with_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("hello")
    sys.argv = ["sapporo-cli", "generate-ro-crate", str(file_path)]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "is not a directory" in captured.err


def test_generate_ro_crate_calls_generate_with_correct_path(tmp_path: Path, mocker: "MockerFixture") -> None:
    mock_fn = mocker.patch("sapporo.cli._validate_run_dir", return_value=tmp_path)
    mock_generate = mocker.patch("sapporo.ro_crate.generate_ro_crate")
    sys.argv = ["sapporo-cli", "generate-ro-crate", str(tmp_path)]
    main()
    mock_fn.assert_called_once_with(str(tmp_path))
    mock_generate.assert_called_once_with(str(tmp_path))


# === dump-outputs ===


def test_dump_outputs_nonexistent_dir_exits_with_error(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["sapporo-cli", "dump-outputs", "/nonexistent/path"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "does not exist" in captured.err


def test_dump_outputs_calls_dump_with_correct_path(tmp_path: Path, mocker: "MockerFixture") -> None:
    mock_fn = mocker.patch("sapporo.cli._validate_run_dir", return_value=tmp_path)
    mock_dump = mocker.patch("sapporo.run.dump_outputs_list")
    sys.argv = ["sapporo-cli", "dump-outputs", str(tmp_path)]
    main()
    mock_fn.assert_called_once_with(str(tmp_path))
    mock_dump.assert_called_once_with(str(tmp_path))


# === generate-openapi ===


def test_generate_openapi_with_output_flag(
    tmp_path: Path, mocker: "MockerFixture", capsys: pytest.CaptureFixture[str]
) -> None:
    output_file = tmp_path / "spec.yml"
    mock_app = mocker.MagicMock()
    mock_app.openapi.return_value = {"openapi": "3.0.0"}
    mocker.patch("sapporo.app.create_app", return_value=mock_app)
    mocker.patch("sapporo.config.dump_openapi_schema", return_value="openapi: '3.0.0'\n")
    mocker.patch("sapporo.config.get_config")

    sys.argv = ["sapporo-cli", "generate-openapi", "--output", str(output_file)]
    main()

    assert output_file.exists()
    assert output_file.read_text() == "openapi: '3.0.0'\n"
    captured = capsys.readouterr()
    assert "OpenAPI spec written to:" in captured.out


def test_generate_openapi_default_output_path(
    tmp_path: Path, mocker: "MockerFixture", capsys: pytest.CaptureFixture[str]
) -> None:
    mock_app = mocker.MagicMock()
    mock_app.openapi.return_value = {"openapi": "3.0.0"}
    mocker.patch("sapporo.app.create_app", return_value=mock_app)
    mocker.patch("sapporo.config.dump_openapi_schema", return_value="openapi: '3.0.0'\n")
    mocker.patch("sapporo.config.get_config")
    mocker.patch("sapporo.config.SAPPORO_WES_SPEC_VERSION", "2.1.0")
    mocker.patch.object(Path, "write_text")
    mocker.patch.object(Path, "mkdir")

    sys.argv = ["sapporo-cli", "generate-openapi"]
    main()

    captured = capsys.readouterr()
    assert "sapporo-wes-spec-2.1.0.yml" in captured.out


def test_generate_openapi_restores_sys_argv(mocker: "MockerFixture") -> None:
    mock_app = mocker.MagicMock()
    mocker.patch("sapporo.app.create_app", return_value=mock_app)
    mocker.patch("sapporo.config.dump_openapi_schema", return_value="openapi: '3.0.0'\n")
    mocker.patch("sapporo.config.get_config")
    mocker.patch.object(Path, "write_text")
    mocker.patch.object(Path, "mkdir")

    original = ["sapporo-cli", "generate-openapi"]
    sys.argv = original[:]
    main()

    assert sys.argv == original


# === help: new subcommands ===


def test_main_help_contains_new_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    sys.argv = ["sapporo-cli", "--help"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "generate-ro-crate" in captured.out
    assert "dump-outputs" in captured.out
    assert "generate-openapi" in captured.out
