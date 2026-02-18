import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from sapporo.config import RUN_DIR_STRUCTURE, AppConfig
from sapporo.run_io import (
    dump_runtime_info,
    glob_all_run_ids,
    read_file,
    read_state,
    resolve_content_path,
    write_file,
)
from sapporo.schemas import State
from tests.unit.conftest import create_run_dir, mock_get_config

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


# === glob_all_run_ids ===


class TestGlobAllRunIds:
    def test_returns_run_ids_from_disk(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid1 = "aabbccdd-0000-0000-0000-000000000001"
        rid2 = "aabbccdd-0000-0000-0000-000000000002"
        create_run_dir(tmp_path, rid1)
        create_run_dir(tmp_path, rid2)

        run_ids = glob_all_run_ids()
        assert set(run_ids) == {rid1, rid2}

    def test_empty_dir_returns_empty_list(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        assert glob_all_run_ids() == []

    def test_ignores_dirs_without_run_request(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        # Create a directory structure that looks like a run but has no run_request.json
        fake_run_id = "aabbccdd-0000-0000-0000-000000000099"
        fake_dir = tmp_path / fake_run_id[:2] / fake_run_id
        fake_dir.mkdir(parents=True)
        (fake_dir / "state.txt").write_text("COMPLETE", encoding="utf-8")

        assert glob_all_run_ids() == []


# === dump_runtime_info ===


class TestDumpRuntimeInfo:
    def test_contains_required_fields(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        info = dump_runtime_info("test-run-id")
        assert info["run_id"] == "test-run-id"
        assert "sapporo_version" in info
        assert "base_url" in info

    def test_run_id_matches_input(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-1111-2222-3333-444444444444"
        info = dump_runtime_info(rid)
        assert info["run_id"] == rid


# === read_file ===


class TestReadFile:
    def test_read_state_key_delegates_to_read_state(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000010"
        create_run_dir(tmp_path, rid, state="RUNNING")

        result = read_file(rid, "state")
        assert result == State.RUNNING

    def test_read_run_request_returns_run_request_model(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000011"
        create_run_dir(tmp_path, rid)

        result = read_file(rid, "run_request")
        assert result is not None
        assert result.workflow_type == "CWL"

    def test_read_cmd_returns_list(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000012"
        create_run_dir(tmp_path, rid, cmd="/bin/bash run.sh /path/to/run")

        result = read_file(rid, "cmd")
        assert isinstance(result, list)
        assert result[0] == "/bin/bash"

    def test_read_pid_returns_int(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000013"
        rd = create_run_dir(tmp_path, rid)
        rd.joinpath(RUN_DIR_STRUCTURE["pid"]).write_text("12345", encoding="utf-8")

        result = read_file(rid, "pid")
        assert result == 12345

    def test_read_pid_invalid_returns_none(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000014"
        rd = create_run_dir(tmp_path, rid)
        rd.joinpath(RUN_DIR_STRUCTURE["pid"]).write_text("not-a-number", encoding="utf-8")

        result = read_file(rid, "pid")
        assert result is None

    def test_read_exit_code_returns_int(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000015"
        create_run_dir(tmp_path, rid, exit_code="0")

        result = read_file(rid, "exit_code")
        assert result == 0

    def test_read_ro_crate_returns_dict(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000016"
        rd = create_run_dir(tmp_path, rid)
        ro_crate = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": []}
        rd.joinpath(RUN_DIR_STRUCTURE["ro_crate"]).write_text(json.dumps(ro_crate), encoding="utf-8")

        result = read_file(rid, "ro_crate")
        assert result["@context"] == "https://w3id.org/ro/crate/1.1/context"

    def test_read_nonexistent_file_returns_none(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000017"
        create_run_dir(tmp_path, rid)

        result = read_file(rid, "exit_code")
        assert result is None

    def test_read_dir_key_returns_none(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000018"
        create_run_dir(tmp_path, rid)

        assert read_file(rid, "exe_dir") is None
        assert read_file(rid, "outputs_dir") is None


# === read_state ===


class TestReadState:
    def test_returns_state_from_file(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000020"
        create_run_dir(tmp_path, rid, state="COMPLETE")

        assert read_state(rid) == State.COMPLETE

    def test_missing_file_returns_unknown(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        # Run directory exists but state file does not
        rid = "aabbccdd-0000-0000-0000-000000000021"
        rd = tmp_path / rid[:2] / rid
        rd.mkdir(parents=True)

        assert read_state(rid) == State.UNKNOWN

    @pytest.mark.parametrize("state_str", ["RUNNING", "QUEUED", "INITIALIZING", "CANCELING", "DELETED"])
    def test_all_valid_states(self, mocker: "MockerFixture", tmp_path: Path, state_str: str) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = f"aabbccdd-0000-0000-0000-00000000{state_str[:4].lower()}"
        create_run_dir(tmp_path, rid, state=state_str)

        assert read_state(rid) == State(state_str)


# === write_file / read_file roundtrip ===


class TestWriteReadRoundtrip:
    def test_state_roundtrip(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000030"
        create_run_dir(tmp_path, rid)

        write_file(rid, "state", State.EXECUTOR_ERROR)
        assert read_state(rid) == State.EXECUTOR_ERROR

    def test_system_logs_roundtrip(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000031"
        create_run_dir(tmp_path, rid)

        logs = ["log entry 1", "log entry 2"]
        write_file(rid, "system_logs", logs)
        result = read_file(rid, "system_logs")
        assert result == logs


# === resolve_content_path ===


class TestResolveContentPath:
    def test_returns_expected_path(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        config = AppConfig(run_dir=tmp_path)
        mock_get_config(mocker, config)

        rid = "aabbccdd-0000-0000-0000-000000000040"
        path = resolve_content_path(rid, "state")
        assert path.name == "state.txt"
        assert rid in str(path)
