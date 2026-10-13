"""Behavioural tests for sapporo/run.sh.

The tests start the real run.sh with fake engine functions appended, so that no workflow engine
and no container runtime is needed. Each fake engine records its own PID so that the test can check
whether cancel really stopped it.
"""

import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from sapporo.config import RUN_DIR_STRUCTURE
from tests.unit.conftest import create_run_dir

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="run.sh requires jq")

RUN_SH = Path(__file__).resolve().parents[2] / "sapporo" / "run.sh"
RUN_ID = "aabbccdd-0000-0000-0000-0000000000a0"
ENGINE_PID_FILE = "engine.pid"

# Appended before the trap setup of run.sh. The sleeping engines write their PID and then replace
# themselves with sleep, so that the PID stays valid for the whole engine lifetime.
FAKE_ENGINES = f"""
function run_fake_ok() {{
    local -a cmd_arr=(true)
    _write_and_run cmd_arr
}}
function run_fake_fail() {{
    local -a cmd_arr=(false)
    _write_and_run cmd_arr
}}
function run_fake_err() {{
    mkdir "${{run_dir}}/no/such/parent"
}}
function run_fake_sleep() {{
    local -a cmd_arr=(bash -c 'echo $$ >"${{0}}"; exec sleep 20' "${{run_dir}}/{ENGINE_PID_FILE}")
    _write_and_run cmd_arr
}}
function run_fake_stubborn() {{
    local -a cmd_arr=(bash -c 'trap "" TERM; echo $$ >"${{0}}"; exec sleep 20' "${{run_dir}}/{ENGINE_PID_FILE}")
    _write_and_run cmd_arr
}}
function generate_ro_crate() {{
    echo '{{}}' >"${{ro_crate}}"
}}
"""


def _script_with_fake_engines(tmp_path: Path) -> Path:
    text = RUN_SH.read_text(encoding="utf-8")
    anchor = "trap 'desc_error' ERR\n"
    assert anchor in text
    script = tmp_path / "run.sh"
    script.write_text(text.replace(anchor, FAKE_ENGINES + anchor, 1), encoding="utf-8")
    return script


def _prepare_run_dir(tmp_path: Path, engine: str, state: str = "QUEUED") -> Path:
    request: dict[str, Any] = {
        "workflow_params": {},
        "workflow_type": "CWL",
        "workflow_type_version": "v1.2",
        "tags": {},
        "workflow_engine": engine,
        "workflow_engine_version": None,
        "workflow_engine_parameters": None,
        "workflow_url": "https://example.com/wf.cwl",
        "workflow_attachment": [],
        "workflow_attachment_obj": [],
    }
    return create_run_dir(tmp_path / "runs", RUN_ID, state=state, run_request_dict=request, wf_engine_params_content="")


def _read(run_dir: Path, key: Any) -> str | None:
    path = run_dir / RUN_DIR_STRUCTURE[key]
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def _wait_until(predicate: Callable[[], bool], timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    msg = "Condition was not met in time"
    raise AssertionError(msg)


def _engine_pid(run_dir: Path) -> int:
    return int((run_dir / ENGINE_PID_FILE).read_text(encoding="utf-8").strip())


def _alive(pid: int) -> bool:
    """Whether the process still runs. A zombie waiting to be reaped counts as not alive."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        return stat.read_text(encoding="utf-8").rsplit(")", 1)[1].split()[0] != "Z"
    return True


class RunSh:
    """Start run.sh for a run directory and clean up its process group afterwards."""

    def __init__(self, tmp_path: Path, engine: str, state: str = "QUEUED", grace_seconds: int = 30) -> None:
        self.run_dir = _prepare_run_dir(tmp_path, engine, state)
        env = os.environ.copy()
        env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"
        env["SAPPORO_CANCEL_GRACE_SECONDS"] = str(grace_seconds)
        env.pop("SAPPORO_EXTRA_DOCKER_ARGS", None)
        self.stderr_path = tmp_path / "run_sh.stderr"
        with self.stderr_path.open("w", encoding="utf-8") as stderr:
            self.process = subprocess.Popen(
                ["/bin/bash", str(_script_with_fake_engines(tmp_path)), str(self.run_dir)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                start_new_session=True,
            )

    def wait_for_engine(self) -> int:
        _wait_until((self.run_dir / ENGINE_PID_FILE).exists)
        return _engine_pid(self.run_dir)

    def wait(self, timeout: float = 15.0) -> int:
        try:
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            msg = f"run.sh did not exit in time; stderr: {self.stderr_path.read_text(encoding='utf-8')}"
            raise AssertionError(msg) from None

    def close(self) -> None:
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=5)


@pytest.fixture
def run_sh(tmp_path: Path) -> Iterator[Callable[..., RunSh]]:
    started: list[RunSh] = []

    def _start(engine: str, state: str = "QUEUED", grace_seconds: int = 30) -> RunSh:
        instance = RunSh(tmp_path, engine, state, grace_seconds)
        started.append(instance)
        return instance

    yield _start

    for instance in started:
        instance.close()


def test_run_sh_complete_writes_outcome_and_outputs(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_ok")

    assert run.wait() == 0
    assert _read(run.run_dir, "state") == "COMPLETE"
    assert _read(run.run_dir, "exit_code") == "0"
    assert _read(run.run_dir, "end_time")
    assert _read(run.run_dir, "cmd") == "true"
    assert (run.run_dir / RUN_DIR_STRUCTURE["outputs"]).exists()
    assert (run.run_dir / RUN_DIR_STRUCTURE["ro_crate"]).exists()


def test_run_sh_engine_failure_writes_executor_error_and_ro_crate(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_fail")

    run.wait()
    assert _read(run.run_dir, "state") == "EXECUTOR_ERROR"
    assert _read(run.run_dir, "exit_code") == "1"
    assert (run.run_dir / RUN_DIR_STRUCTURE["ro_crate"]).exists()


def test_run_sh_unexpected_failure_in_engine_function_writes_system_error(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_err")

    run.wait()
    assert _read(run.run_dir, "state") == "SYSTEM_ERROR"
    assert _read(run.run_dir, "exit_code") == "1"
    assert _read(run.run_dir, "end_time")


def test_run_sh_unknown_engine_writes_executor_error(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("no_such_engine")

    run.wait()
    assert _read(run.run_dir, "state") == "EXECUTOR_ERROR"
    assert _read(run.run_dir, "exit_code") == "1"


def test_run_sh_cancel_stops_engine_and_keeps_canceled(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_sleep")
    engine_pid = run.wait_for_engine()
    assert _read(run.run_dir, "state") == "RUNNING"

    (run.run_dir / RUN_DIR_STRUCTURE["state"]).write_text("CANCELING", encoding="utf-8")
    run.process.send_signal(signal.SIGUSR1)

    assert run.wait() == 138
    assert not _alive(engine_pid)
    assert _read(run.run_dir, "state") == "CANCELED"
    assert _read(run.run_dir, "exit_code") == "138"
    end_time = _read(run.run_dir, "end_time")
    assert end_time

    time.sleep(1.0)
    assert _read(run.run_dir, "state") == "CANCELED"
    assert _read(run.run_dir, "end_time") == end_time


def test_run_sh_cancel_kills_engine_that_ignores_sigterm_after_grace_period(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_stubborn", grace_seconds=1)
    engine_pid = run.wait_for_engine()

    (run.run_dir / RUN_DIR_STRUCTURE["state"]).write_text("CANCELING", encoding="utf-8")
    run.process.send_signal(signal.SIGUSR1)

    assert run.wait() == 138
    assert not _alive(engine_pid)
    assert _read(run.run_dir, "state") == "CANCELED"


def test_run_sh_sigterm_stops_engine_and_writes_system_error(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_sleep")
    engine_pid = run.wait_for_engine()

    run.process.send_signal(signal.SIGTERM)

    assert run.wait() == 143
    assert not _alive(engine_pid)
    assert _read(run.run_dir, "state") == "SYSTEM_ERROR"
    assert _read(run.run_dir, "exit_code") == "143"


def test_run_sh_canceled_before_start_does_not_run_engine(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_sleep", state="CANCELING")

    run.wait()
    assert _read(run.run_dir, "state") == "CANCELED"
    assert _read(run.run_dir, "exit_code") == "138"
    assert not (run.run_dir / ENGINE_PID_FILE).exists()
