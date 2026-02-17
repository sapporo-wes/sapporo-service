import json
import signal
import zipfile
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sapporo.config import RUN_DIR_STRUCTURE, AppConfig
from sapporo.schemas import RunRequest, State
from tests.unit.conftest import (
    create_run_dir,
    make_run_request_form,
    make_upload_file,
    mock_get_config,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


# === Helper ===


def _setup_config(mocker: "MockerFixture", tmp_path: Path) -> AppConfig:
    config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, config)
    return config


# === resolve_run_dir ===


def test_resolve_run_dir_returns_path_with_two_char_prefix(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_run_dir

    run_id = "abcdef12-3456-7890-abcd-ef1234567890"
    result = resolve_run_dir(run_id)
    assert result.parent.name == "ab"
    assert result.name == run_id


def test_resolve_run_dir_returns_resolved_absolute_path(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_run_dir

    result = resolve_run_dir("abcdef12-3456-7890-abcd-ef1234567890")
    assert result.is_absolute()


# === resolve_content_path ===


@pytest.mark.parametrize(
    ("key", "expected_suffix"),
    [
        ("state", "state.txt"),
        ("run_request", "run_request.json"),
        ("exe_dir", "exe"),
        ("outputs_dir", "outputs"),
        ("stdout", "stdout.log"),
        ("stderr", "stderr.log"),
        ("pid", "run.pid"),
        ("cmd", "cmd.txt"),
        ("system_logs", "system_logs.json"),
    ],
)
def test_resolve_content_path_returns_correct_subpath_for_each_key(
    mocker: "MockerFixture", tmp_path: Path, key: str, expected_suffix: str
) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_content_path

    run_id = "abcdef12-3456-7890-abcd-ef1234567890"
    result = resolve_content_path(run_id, key)  # type: ignore[arg-type]
    assert str(result).endswith(expected_suffix)


# === write_file / read_file roundtrip ===


def test_write_file_state_writes_enum_value_string(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_content_path, write_file

    run_id = "aabbccdd-0000-0000-0000-000000000001"
    run_dir = tmp_path / run_id[:2] / run_id
    run_dir.mkdir(parents=True)

    write_file(run_id, "state", State.RUNNING)
    content = resolve_content_path(run_id, "state").read_text(encoding="utf-8")
    assert content == "RUNNING"


def test_write_file_json_key_writes_indented_json(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_content_path, write_file

    run_id = "aabbccdd-0000-0000-0000-000000000002"
    run_dir = tmp_path / run_id[:2] / run_id
    run_dir.mkdir(parents=True)

    data = {"key": "value", "num": 42}
    write_file(run_id, "runtime_info", data)
    content = resolve_content_path(run_id, "runtime_info").read_text(encoding="utf-8")
    assert json.loads(content) == data
    assert "\n" in content  # indented


def test_write_file_wf_params_string_passes_through(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_content_path, write_file

    run_id = "aabbccdd-0000-0000-0000-000000000003"
    run_dir = tmp_path / run_id[:2] / run_id
    run_dir.mkdir(parents=True)
    run_dir.joinpath("exe").mkdir(parents=True)

    raw_str = '{"input": "file.txt"}'
    write_file(run_id, "wf_params", raw_str)
    content = resolve_content_path(run_id, "wf_params").read_text(encoding="utf-8")
    assert content == raw_str


def test_write_file_plain_text_key_writes_str(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_content_path, write_file

    run_id = "aabbccdd-0000-0000-0000-000000000004"
    run_dir = tmp_path / run_id[:2] / run_id
    run_dir.mkdir(parents=True)

    write_file(run_id, "start_time", "2024-01-01T00:00:00Z")
    content = resolve_content_path(run_id, "start_time").read_text(encoding="utf-8")
    assert content == "2024-01-01T00:00:00Z"


def test_write_file_creates_parent_directories(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_content_path, write_file

    run_id = "aabbccdd-0000-0000-0000-000000000005"
    # Do NOT pre-create directories
    write_file(run_id, "state", State.UNKNOWN)
    assert resolve_content_path(run_id, "state").exists()


def test_read_file_dir_key_returns_none(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file

    run_id = "aabbccdd-0000-0000-0000-000000000006"
    create_run_dir(tmp_path, run_id)
    assert read_file(run_id, "exe_dir") is None
    assert read_file(run_id, "outputs_dir") is None


def test_read_file_nonexistent_returns_none(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file

    run_id = "aabbccdd-0000-0000-0000-000000000007"
    create_run_dir(tmp_path, run_id)
    assert read_file(run_id, "pid") is None


def test_read_file_run_request_returns_runrequest_model(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file

    run_id = "aabbccdd-0000-0000-0000-000000000008"
    create_run_dir(tmp_path, run_id)
    result = read_file(run_id, "run_request")
    assert isinstance(result, RunRequest)


def test_read_file_cmd_returns_shlex_split_list(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000009"
    create_run_dir(tmp_path, run_id)
    resolve_content_path(run_id, "cmd").write_text("docker run --rm image:latest", encoding="utf-8")
    result = read_file(run_id, "cmd")
    assert result == ["docker", "run", "--rm", "image:latest"]


def test_read_file_pid_returns_int(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000010"
    create_run_dir(tmp_path, run_id)
    resolve_content_path(run_id, "pid").write_text("12345", encoding="utf-8")
    assert read_file(run_id, "pid") == 12345


def test_read_file_exit_code_returns_int(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000011"
    create_run_dir(tmp_path, run_id)
    resolve_content_path(run_id, "exit_code").write_text("0", encoding="utf-8")
    assert read_file(run_id, "exit_code") == 0


def test_read_file_stdout_returns_raw_string(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000012"
    create_run_dir(tmp_path, run_id)
    resolve_content_path(run_id, "stdout").write_text("some output\nline2", encoding="utf-8")
    result = read_file(run_id, "stdout")
    assert result == "some output\nline2"


def test_read_file_system_logs_returns_json_list(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file

    run_id = "aabbccdd-0000-0000-0000-000000000013"
    create_run_dir(tmp_path, run_id)
    result = read_file(run_id, "system_logs")
    assert result == []


def test_read_file_fallback_json_parse(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000014"
    create_run_dir(tmp_path, run_id)
    resolve_content_path(run_id, "wf_engine_params").write_text('{"k": "v"}', encoding="utf-8")
    result = read_file(run_id, "wf_engine_params")
    assert result == {"k": "v"}


def test_read_file_fallback_raw_string(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_file, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000015"
    create_run_dir(tmp_path, run_id)
    resolve_content_path(run_id, "wf_engine_params").write_text("--some-flag", encoding="utf-8")
    result = read_file(run_id, "wf_engine_params")
    assert result == "--some-flag"


# === read_state ===


def test_read_state_existing_file_returns_state_enum(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_state

    run_id = "aabbccdd-0000-0000-0000-000000000016"
    create_run_dir(tmp_path, run_id, state="RUNNING")
    result = read_state(run_id)
    assert result == State.RUNNING


def test_read_state_missing_file_returns_unknown(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import read_state

    result = read_state("nonexistent-run-id-0000-000000000000")
    assert result == State.UNKNOWN


# === dump_runtime_info ===


def test_dump_runtime_info_contains_version_and_base_url(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import dump_runtime_info

    info = dump_runtime_info("test-run-id")
    assert "run_id" in info
    assert info["run_id"] == "test-run-id"
    assert "sapporo_version" in info
    assert "base_url" in info
    assert isinstance(info["sapporo_version"], str)
    assert isinstance(info["base_url"], str)


# === wf_engine_params_to_str ===


def test_wf_engine_params_to_str_with_explicit_params(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import wf_engine_params_to_str

    req = make_run_request_form(workflow_engine_parameters={"--outdir": "/tmp/out"})
    result = wf_engine_params_to_str(req)
    assert "--outdir" in result
    assert "/tmp/out" in result


def test_wf_engine_params_to_str_with_none_uses_defaults(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import wf_engine_params_to_str

    # Mock create_service_info to return a service info with default params
    mock_si = MagicMock()
    mock_si.default_workflow_engine_parameters = {}
    mocker.patch("sapporo.run.create_service_info", return_value=mock_si)

    req = make_run_request_form(workflow_engine_parameters=None)
    result = wf_engine_params_to_str(req)
    assert isinstance(result, str)


def test_wf_engine_params_to_str_empty_values_filtered(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import wf_engine_params_to_str

    req = make_run_request_form(workflow_engine_parameters={"--flag": "", "--outdir": "/tmp"})
    result = wf_engine_params_to_str(req)
    assert "--flag" in result
    assert "/tmp" in result
    # Empty value is filtered, so no double spaces
    assert "  " not in result


@settings(max_examples=20)
@given(
    keys=st.lists(st.text(min_size=1, max_size=10, alphabet="abcdefghij-_"), min_size=0, max_size=5),
    values=st.lists(st.text(min_size=0, max_size=10, alphabet="abcdefghij/._"), min_size=0, max_size=5),
)
def test_wf_engine_params_to_str_arbitrary_params_no_empty_tokens(keys: list[str], values: list[str]) -> None:
    from sapporo.run import wf_engine_params_to_str

    params = dict(zip(keys, values, strict=False))
    req = make_run_request_form(workflow_engine_parameters=params or None)

    if params:
        result = wf_engine_params_to_str(req)
        # No empty tokens: no leading/trailing/double spaces
        tokens = result.split(" ")
        for token in tokens:
            assert token != "" or result == ""


# === write_wf_attachment ===


def test_write_wf_attachment_writes_uploaded_files(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_content_path, write_wf_attachment

    run_id = "aabbccdd-0000-0000-0000-000000000020"
    create_run_dir(tmp_path, run_id)

    upload = make_upload_file("input.txt", b"hello world")
    req = make_run_request_form(workflow_attachment=[upload])
    write_wf_attachment(run_id, req)

    written = resolve_content_path(run_id, "exe_dir") / "input.txt"
    assert written.exists()
    assert written.read_bytes() == b"hello world"


def test_write_wf_attachment_preserves_subdirectory(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_content_path, write_wf_attachment

    run_id = "aabbccdd-0000-0000-0000-000000000021"
    create_run_dir(tmp_path, run_id)

    upload = make_upload_file("subdir/input.txt", b"nested")
    req = make_run_request_form(workflow_attachment=[upload])
    write_wf_attachment(run_id, req)

    written = resolve_content_path(run_id, "exe_dir") / "subdir" / "input.txt"
    assert written.exists()
    assert written.read_bytes() == b"nested"


def test_write_wf_attachment_skips_empty_filename(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import resolve_content_path, write_wf_attachment

    run_id = "aabbccdd-0000-0000-0000-000000000022"
    create_run_dir(tmp_path, run_id)

    upload = make_upload_file("", b"should be skipped")
    upload.filename = ""
    req = make_run_request_form(workflow_attachment=[upload])
    write_wf_attachment(run_id, req)

    exe_dir = resolve_content_path(run_id, "exe_dir")
    # Only the pre-existing workflow_params.json should exist
    files = list(exe_dir.iterdir())
    assert all(f.name == "workflow_params.json" for f in files if f.is_file())


# === download_wf_attachment (httpx mock) ===


def test_download_wf_attachment_fetches_http_url(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import download_wf_attachment, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000023"
    create_run_dir(tmp_path, run_id)

    mock_response = MagicMock()
    mock_response.content = b"downloaded content"
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response

    mocker.patch("sapporo.run.httpx.Client", return_value=mock_client)

    req = make_run_request_form(
        workflow_attachment_obj=[{"file_name": "helper.cwl", "file_url": "https://example.com/helper.cwl"}]
    )
    download_wf_attachment(run_id, req)

    written = resolve_content_path(run_id, "exe_dir") / "helper.cwl"
    assert written.exists()
    assert written.read_bytes() == b"downloaded content"


def test_download_wf_attachment_skips_non_http_scheme(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import download_wf_attachment, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000024"
    create_run_dir(tmp_path, run_id)

    req = make_run_request_form(
        workflow_attachment_obj=[{"file_name": "local.txt", "file_url": "ftp://example.com/local.txt"}]
    )
    download_wf_attachment(run_id, req)

    written = resolve_content_path(run_id, "exe_dir") / "local.txt"
    assert not written.exists()


def test_download_wf_attachment_http_error_raises_exception(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    import httpx

    from sapporo.run import download_wf_attachment

    run_id = "aabbccdd-0000-0000-0000-000000000025"
    create_run_dir(tmp_path, run_id)

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=mock_response
    )

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response

    mocker.patch("sapporo.run.httpx.Client", return_value=mock_client)

    req = make_run_request_form(
        workflow_attachment_obj=[{"file_name": "missing.cwl", "file_url": "https://example.com/missing.cwl"}]
    )
    with pytest.raises(Exception, match="Failed to download"):
        download_wf_attachment(run_id, req)


def test_download_wf_attachment_connection_error_raises_exception(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import download_wf_attachment

    run_id = "aabbccdd-0000-0000-0000-000000000026"
    create_run_dir(tmp_path, run_id)

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.side_effect = ConnectionError("Connection refused")

    mocker.patch("sapporo.run.httpx.Client", return_value=mock_client)

    req = make_run_request_form(
        workflow_attachment_obj=[{"file_name": "helper.cwl", "file_url": "https://example.com/helper.cwl"}]
    )
    with pytest.raises(Exception, match="Failed to download"):
        download_wf_attachment(run_id, req)


# === fork_run (Popen mock) ===


def test_fork_run_calls_popen_with_run_sh(mocker: "MockerFixture", tmp_path: Path) -> None:
    config = _setup_config(mocker, tmp_path)
    from sapporo.run import fork_run

    run_id = "aabbccdd-0000-0000-0000-000000000030"
    create_run_dir(tmp_path, run_id)

    mock_process = MagicMock()
    mock_process.pid = 9999
    mock_popen = mocker.patch("sapporo.run.Popen", return_value=mock_process)

    fork_run(run_id)

    mock_popen.assert_called_once()
    call_args = mock_popen.call_args
    assert str(config.run_sh) in call_args[0][0][1]


def test_fork_run_sets_state_to_queued(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import fork_run, read_state

    run_id = "aabbccdd-0000-0000-0000-000000000031"
    create_run_dir(tmp_path, run_id)

    mock_process = MagicMock()
    mock_process.pid = 9999
    mocker.patch("sapporo.run.Popen", return_value=mock_process)

    fork_run(run_id)
    assert read_state(run_id) == State.QUEUED


def test_fork_run_writes_pid_file(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import fork_run, read_file

    run_id = "aabbccdd-0000-0000-0000-000000000032"
    create_run_dir(tmp_path, run_id)

    mock_process = MagicMock()
    mock_process.pid = 12345
    mocker.patch("sapporo.run.Popen", return_value=mock_process)

    fork_run(run_id)
    assert read_file(run_id, "pid") == 12345


def test_fork_run_does_not_write_pid_when_none(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import fork_run, read_file

    run_id = "aabbccdd-0000-0000-0000-000000000033"
    create_run_dir(tmp_path, run_id)

    mock_process = MagicMock()
    mock_process.pid = None
    mocker.patch("sapporo.run.Popen", return_value=mock_process)

    fork_run(run_id)
    assert read_file(run_id, "pid") is None


# === post_run_task ===


def test_post_run_task_success_calls_download_and_fork(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import post_run_task

    run_id = "aabbccdd-0000-0000-0000-000000000034"
    create_run_dir(tmp_path, run_id)

    mock_download = mocker.patch("sapporo.run.download_wf_attachment")
    mock_fork = mocker.patch("sapporo.run.fork_run")

    req = make_run_request_form()
    post_run_task(run_id, req)

    mock_download.assert_called_once_with(run_id, req)
    mock_fork.assert_called_once_with(run_id)


def test_post_run_task_exception_sets_system_error(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import post_run_task, read_file, read_state

    run_id = "aabbccdd-0000-0000-0000-000000000035"
    create_run_dir(tmp_path, run_id)

    mocker.patch("sapporo.run.download_wf_attachment", side_effect=RuntimeError("download failed"))

    req = make_run_request_form()
    post_run_task(run_id, req)

    assert read_state(run_id) == State.SYSTEM_ERROR
    system_logs = read_file(run_id, "system_logs")
    assert len(system_logs) > 0
    assert "download failed" in system_logs[0]


# === append_system_logs ===


def test_append_system_logs_appends_to_empty_list(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import append_system_logs, read_file

    run_id = "aabbccdd-0000-0000-0000-000000000036"
    create_run_dir(tmp_path, run_id)

    append_system_logs(run_id, "first log entry")
    result = read_file(run_id, "system_logs")
    assert result == ["first log entry"]


def test_append_system_logs_appends_to_existing_list(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import append_system_logs, read_file

    run_id = "aabbccdd-0000-0000-0000-000000000037"
    create_run_dir(tmp_path, run_id)

    append_system_logs(run_id, "first")
    append_system_logs(run_id, "second")
    result = read_file(run_id, "system_logs")
    assert result == ["first", "second"]


# === prepare_run_dir ===


def test_prepare_run_dir_creates_directory_structure(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import prepare_run_dir, resolve_content_path, resolve_run_dir

    run_id = "aabbccdd-0000-0000-0000-000000000040"
    req = make_run_request_form()
    prepare_run_dir(run_id, req, None)

    assert resolve_run_dir(run_id).exists()
    assert resolve_content_path(run_id, "exe_dir").exists()
    assert resolve_content_path(run_id, "outputs_dir").exists()


def test_prepare_run_dir_writes_initial_files(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import prepare_run_dir, read_file, read_state

    run_id = "aabbccdd-0000-0000-0000-000000000041"
    req = make_run_request_form()
    prepare_run_dir(run_id, req, None)

    assert read_state(run_id) == State.INITIALIZING
    assert read_file(run_id, "start_time") is not None
    assert read_file(run_id, "runtime_info") is not None
    assert read_file(run_id, "run_request") is not None
    assert read_file(run_id, "system_logs") == []


def test_prepare_run_dir_with_username_writes_username_file(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import prepare_run_dir, read_file

    run_id = "aabbccdd-0000-0000-0000-000000000042"
    req = make_run_request_form()
    prepare_run_dir(run_id, req, "alice")

    assert read_file(run_id, "username") == "alice"


def test_prepare_run_dir_without_username_skips_username_file(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import prepare_run_dir, read_file

    run_id = "aabbccdd-0000-0000-0000-000000000043"
    req = make_run_request_form()
    prepare_run_dir(run_id, req, None)

    assert read_file(run_id, "username") is None


# === dump_outputs_list ===


def test_dump_outputs_list_writes_outputs_json(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import dump_outputs_list, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000050"
    rd = create_run_dir(tmp_path, run_id)

    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    (outputs_dir / "result.txt").write_text("result data", encoding="utf-8")

    dump_outputs_list(rd)

    outputs_json = rd / RUN_DIR_STRUCTURE["outputs"]
    assert outputs_json.exists()
    data = json.loads(outputs_json.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["file_name"] == "result.txt"
    assert "result.txt" in data[0]["file_url"]


def test_dump_outputs_list_empty_outputs_dir(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import dump_outputs_list

    run_id = "aabbccdd-0000-0000-0000-000000000051"
    rd = create_run_dir(tmp_path, run_id)

    dump_outputs_list(rd)

    outputs_json = rd / RUN_DIR_STRUCTURE["outputs"]
    data = json.loads(outputs_json.read_text(encoding="utf-8"))
    assert data == []


def test_dump_outputs_list_nested_files(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import dump_outputs_list, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000052"
    rd = create_run_dir(tmp_path, run_id)

    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    subdir = outputs_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested", encoding="utf-8")

    dump_outputs_list(rd)

    outputs_json = rd / RUN_DIR_STRUCTURE["outputs"]
    data = json.loads(outputs_json.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert "subdir/nested.txt" in data[0]["file_name"]


# === list_files ===


def test_list_files_returns_all_files_recursively(tmp_path: Path) -> None:
    from sapporo.run import list_files

    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "b.txt").write_text("b", encoding="utf-8")

    result = list(list_files(tmp_path))
    names = {f.name for f in result}
    assert names == {"a.txt", "b.txt"}


def test_list_files_empty_dir_returns_empty(tmp_path: Path) -> None:
    from sapporo.run import list_files

    result = list(list_files(tmp_path))
    assert result == []


# === glob_all_run_ids ===


def test_glob_all_run_ids_finds_all_runs(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import glob_all_run_ids

    create_run_dir(tmp_path, "aabbccdd-0000-0000-0000-000000000060")
    create_run_dir(tmp_path, "bbccddee-0000-0000-0000-000000000061")

    run_ids = glob_all_run_ids()
    assert set(run_ids) == {"aabbccdd-0000-0000-0000-000000000060", "bbccddee-0000-0000-0000-000000000061"}


def test_glob_all_run_ids_empty_run_dir(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import glob_all_run_ids

    assert glob_all_run_ids() == []


# === cancel_run_task (os.kill mock) ===


def test_cancel_run_task_initializing_sets_canceling(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import cancel_run_task, read_state

    run_id = "aabbccdd-0000-0000-0000-000000000070"
    create_run_dir(tmp_path, run_id, state="INITIALIZING")

    cancel_run_task(run_id)
    assert read_state(run_id) == State.CANCELING


def test_cancel_run_task_queued_sends_sigusr1(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import cancel_run_task, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000071"
    create_run_dir(tmp_path, run_id, state="QUEUED")
    resolve_content_path(run_id, "pid").write_text("99999", encoding="utf-8")

    mock_kill = mocker.patch("sapporo.run.os.kill")
    cancel_run_task(run_id)

    mock_kill.assert_called_once_with(99999, signal.SIGUSR1)


def test_cancel_run_task_running_sends_sigusr1(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import cancel_run_task, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000072"
    create_run_dir(tmp_path, run_id, state="RUNNING")
    resolve_content_path(run_id, "pid").write_text("88888", encoding="utf-8")

    mock_kill = mocker.patch("sapporo.run.os.kill")
    cancel_run_task(run_id)

    mock_kill.assert_called_once_with(88888, signal.SIGUSR1)


def test_cancel_run_task_no_pid_sets_unknown(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import cancel_run_task, read_state

    run_id = "aabbccdd-0000-0000-0000-000000000073"
    create_run_dir(tmp_path, run_id, state="RUNNING")
    # No pid file

    cancel_run_task(run_id)
    assert read_state(run_id) == State.UNKNOWN


def test_cancel_run_task_complete_does_nothing(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import cancel_run_task, read_state

    run_id = "aabbccdd-0000-0000-0000-000000000074"
    create_run_dir(tmp_path, run_id, state="COMPLETE")

    cancel_run_task(run_id)
    assert read_state(run_id) == State.COMPLETE


# === delete_run_task ===


def test_delete_run_task_removes_files_except_keepfiles(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import KEEP_FILES, delete_run_task, resolve_run_dir

    run_id = "aabbccdd-0000-0000-0000-000000000080"
    create_run_dir(tmp_path, run_id, state="COMPLETE", end_time="2024-01-01T01:00:00Z")

    delete_run_task(run_id)

    run_dir = resolve_run_dir(run_id)
    remaining = {p.name for p in run_dir.iterdir()}
    # state.txt, start_time.txt, end_time.txt should remain
    for keep in KEEP_FILES:
        assert keep in remaining


def test_delete_run_task_sets_state_to_deleted(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import delete_run_task, read_state

    run_id = "aabbccdd-0000-0000-0000-000000000081"
    create_run_dir(tmp_path, run_id, state="COMPLETE")

    delete_run_task(run_id)

    assert read_state(run_id) == State.DELETED


# === outputs_zip_stream ===


def test_outputs_zip_stream_produces_valid_zip(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import outputs_zip_stream, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000090"
    create_run_dir(tmp_path, run_id)

    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    (outputs_dir / "result.txt").write_text("hello", encoding="utf-8")

    stream, content_length = outputs_zip_stream(run_id)
    data = b"".join(stream)
    assert content_length == len(data)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        assert any("result.txt" in name for name in names)


def test_outputs_zip_stream_uses_custom_name(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import outputs_zip_stream, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000091"
    create_run_dir(tmp_path, run_id)

    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    (outputs_dir / "out.txt").write_text("data", encoding="utf-8")

    stream, content_length = outputs_zip_stream(run_id, "my_project")
    data = b"".join(stream)
    assert content_length == len(data)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        assert any(name.startswith("my_project/") for name in names)


def test_outputs_zip_stream_includes_empty_dirs(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import outputs_zip_stream, resolve_content_path

    run_id = "aabbccdd-0000-0000-0000-000000000092"
    create_run_dir(tmp_path, run_id)

    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    (outputs_dir / "empty_dir").mkdir()

    stream, content_length = outputs_zip_stream(run_id)
    data = b"".join(stream)
    assert content_length == len(data)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        assert any("empty_dir/" in name for name in names)


def test_outputs_zip_stream_empty_outputs(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import outputs_zip_stream

    run_id = "aabbccdd-0000-0000-0000-000000000093"
    create_run_dir(tmp_path, run_id)

    stream, content_length = outputs_zip_stream(run_id)
    data = b"".join(stream)
    assert content_length == len(data)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        # zipstream-ng includes a root directory entry even for empty dirs
        file_names = [n for n in zf.namelist() if not n.endswith("/")]
        assert file_names == []


# === bulk_delete_run_tasks ===


def test_bulk_delete_run_tasks_deletes_multiple_runs(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import bulk_delete_run_tasks, read_state

    ids = ["aabbccdd-0000-0000-0000-0000000000a0", "aabbccdd-0000-0000-0000-0000000000a1"]
    for rid in ids:
        create_run_dir(tmp_path, rid, state="COMPLETE")

    bulk_delete_run_tasks(ids)

    for rid in ids:
        assert read_state(rid) == State.DELETED


def test_bulk_delete_run_tasks_one_failure_raises(mocker: "MockerFixture", tmp_path: Path) -> None:
    _setup_config(mocker, tmp_path)
    from sapporo.run import bulk_delete_run_tasks

    ids = ["aabbccdd-0000-0000-0000-0000000000b0", "aabbccdd-0000-0000-0000-0000000000b1"]
    for rid in ids:
        create_run_dir(tmp_path, rid, state="COMPLETE")

    def failing_delete(run_id: str) -> None:
        if run_id == ids[1]:
            msg = "Simulated failure"
            raise RuntimeError(msg)
        from sapporo.run import cancel_run_task, write_file

        cancel_run_task(run_id)
        write_file(run_id, "state", State.DELETED)

    mocker.patch("sapporo.run.delete_run_task", side_effect=failing_delete)

    with pytest.raises(Exception, match="Failed to delete run"):
        bulk_delete_run_tasks(ids)


# === remove_old_runs ===


def test_remove_old_runs_with_none_days_does_nothing(mocker: "MockerFixture", tmp_path: Path) -> None:
    config = AppConfig(run_dir=tmp_path, run_remove_older_than_days=None)
    mock_get_config(mocker, config)
    from sapporo.run import remove_old_runs

    mock_list_old = mocker.patch("sapporo.database.list_old_runs_db")
    remove_old_runs()
    mock_list_old.assert_not_called()


def test_remove_old_runs_deletes_old_entries(mocker: "MockerFixture", tmp_path: Path) -> None:
    config = AppConfig(run_dir=tmp_path, run_remove_older_than_days=7)
    mock_get_config(mocker, config)
    from sapporo.run import remove_old_runs

    mock_run = MagicMock()
    mock_run.run_id = "aabbccdd-0000-0000-0000-0000000000c0"
    create_run_dir(tmp_path, mock_run.run_id, state="COMPLETE")

    mocker.patch("sapporo.database.list_old_runs_db", return_value=[mock_run])

    remove_old_runs()

    from sapporo.run import read_state

    assert read_state(mock_run.run_id) == State.DELETED
