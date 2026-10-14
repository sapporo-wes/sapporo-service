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
function run_fake_docker() {{
    local -a cmd_arr=(docker run --rm --cidfile "${{engine_cid}}" fake-image sleep 20)
    _write_and_run cmd_arr
}}
function run_fake_args() {{
    printf '%s\n' "${{extra_docker_args[@]+"${{extra_docker_args[@]}}"}}" >"${{run_dir}}/extra_args.txt"
    local -a cmd_arr=(true)
    _write_and_run cmd_arr
}}
function generate_ro_crate() {{
    echo '{{}}' >"${{ro_crate}}"
}}
"""

# A fake docker CLI: "run" records a container id, writes the engine PID and ignores SIGTERM like an
# engine that does not stop on it; "inspect" reports the working directory; "stop" records its
# arguments and stops the engine.
FAKE_DOCKER = """#!/usr/bin/env bash
set -u
dir="${FAKE_DOCKER_DIR}"
case "${1:-}" in
run)
    shift
    cidfile=""
    while (($#)) && [[ "$1" != "fake-image" ]]; do
        if [[ "$1" == "--cidfile" ]]; then cidfile="$2"; shift; fi
        shift
    done
    (($#)) || exit 1
    shift
    echo "fakecontainerid" >"${cidfile}"
    trap "" TERM
    echo $$ >"${dir}/engine.pid"
    exec "$@"
    ;;
inspect)
    echo "${FAKE_DOCKER_WORKDIR}"
    ;;
stop)
    echo "$@" >>"${dir}/stop.log"
    kill -KILL "$(cat "${dir}/engine.pid")" 2>/dev/null || true
    ;;
*)
    exit 1
    ;;
esac
"""


def _script_with_fake_engines(tmp_path: Path, extra_script: str = "") -> Path:
    text = RUN_SH.read_text(encoding="utf-8")
    anchor = "trap 'desc_error' ERR\n"
    assert anchor in text
    script = tmp_path / "run.sh"
    script.write_text(text.replace(anchor, FAKE_ENGINES + extra_script + anchor, 1), encoding="utf-8")
    return script


def _prepare_run_dir(
    tmp_path: Path, engine: str, state: str = "QUEUED", wf_url: str = "https://example.com/wf.cwl"
) -> Path:
    request: dict[str, Any] = {
        "workflow_params": {},
        "workflow_type": "CWL",
        "workflow_type_version": "v1.2",
        "tags": {},
        "workflow_engine": engine,
        "workflow_engine_version": None,
        "workflow_engine_parameters": None,
        "workflow_url": wf_url,
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

    def __init__(
        self,
        tmp_path: Path,
        engine: str,
        state: str = "QUEUED",
        grace_seconds: int = 30,
        fake_docker_workdir: str | None = None,
        before_start: Callable[[Path], None] | None = None,
        extra_env: dict[str, str] | None = None,
        extra_script: str = "",
        wf_url: str = "https://example.com/wf.cwl",
    ) -> None:
        self.run_dir = _prepare_run_dir(tmp_path, engine, state, wf_url)
        if before_start is not None:
            before_start(self.run_dir)
        self.fake_docker_dir = tmp_path / "fake-docker"
        self.fake_docker_dir.mkdir(exist_ok=True)
        fake_docker = self.fake_docker_dir / "docker"
        fake_docker.write_text(FAKE_DOCKER, encoding="utf-8")
        fake_docker.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = (
            f"{self.fake_docker_dir}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"
        )
        env["SAPPORO_CANCEL_GRACE_SECONDS"] = str(grace_seconds)
        env["FAKE_DOCKER_DIR"] = str(self.fake_docker_dir)
        env["FAKE_DOCKER_WORKDIR"] = fake_docker_workdir or str(self.run_dir / RUN_DIR_STRUCTURE["exe_dir"])
        env.pop("SAPPORO_EXTRA_DOCKER_ARGS", None)
        env.update(extra_env or {})
        self.stderr_path = tmp_path / "run_sh.stderr"
        with self.stderr_path.open("w", encoding="utf-8") as stderr:
            self.process = subprocess.Popen(
                ["/bin/bash", str(_script_with_fake_engines(tmp_path, extra_script)), str(self.run_dir)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                start_new_session=True,
            )

    def wait_for_engine(self) -> int:
        _wait_until((self.run_dir / ENGINE_PID_FILE).exists)
        return _engine_pid(self.run_dir)

    def wait_for_docker_engine(self) -> int:
        pid_file = self.fake_docker_dir / "engine.pid"
        _wait_until(pid_file.exists)
        return int(pid_file.read_text(encoding="utf-8").strip())

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

    def _start(
        engine: str,
        state: str = "QUEUED",
        grace_seconds: int = 30,
        fake_docker_workdir: str | None = None,
        before_start: Callable[[Path], None] | None = None,
        **kwargs: Any,
    ) -> RunSh:
        instance = RunSh(tmp_path, engine, state, grace_seconds, fake_docker_workdir, before_start, **kwargs)
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


def test_run_sh_cancel_stops_docker_engine_container_by_id_with_the_grace_period(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_docker", grace_seconds=5)
    engine_pid = run.wait_for_docker_engine()
    assert (run.run_dir / "engine.cid").read_text(encoding="utf-8").strip() == "fakecontainerid"

    (run.run_dir / RUN_DIR_STRUCTURE["state"]).write_text("CANCELING", encoding="utf-8")
    started = time.monotonic()
    run.process.send_signal(signal.SIGUSR1)

    assert run.wait() == 138
    assert time.monotonic() - started < 4, "the container was not stopped; cancel waited for the grace period"
    assert not _alive(engine_pid)
    assert (run.fake_docker_dir / "stop.log").read_text(encoding="utf-8").split() == [
        "stop",
        "-t",
        "5",
        "fakecontainerid",
    ]
    assert _read(run.run_dir, "state") == "CANCELED"


def test_run_sh_cancel_ignores_container_id_not_started_for_this_run(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_docker", grace_seconds=1, fake_docker_workdir="/somewhere/else")
    run.wait_for_docker_engine()

    (run.run_dir / RUN_DIR_STRUCTURE["state"]).write_text("CANCELING", encoding="utf-8")
    run.process.send_signal(signal.SIGUSR1)

    assert run.wait() == 138
    assert not (run.fake_docker_dir / "stop.log").exists()
    assert _read(run.run_dir, "state") == "CANCELED"


def test_run_sh_writes_its_own_pid_after_setting_traps(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_sleep")
    run.wait_for_engine()

    assert _read(run.run_dir, "pid") == str(run.process.pid)

    (run.run_dir / RUN_DIR_STRUCTURE["state"]).write_text("CANCELING", encoding="utf-8")
    run.process.send_signal(signal.SIGUSR1)
    assert run.wait() == 138


def test_run_sh_replaces_a_symlinked_control_file_instead_of_writing_through_it(
    run_sh: Callable[..., RunSh], tmp_path: Path
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("QUEUED", encoding="utf-8")

    def link_state(run_dir: Path) -> None:
        state = run_dir / RUN_DIR_STRUCTURE["state"]
        state.unlink()
        state.symlink_to(target)

    run = run_sh("fake_ok", before_start=link_state)

    assert run.wait() == 0
    state = run.run_dir / RUN_DIR_STRUCTURE["state"]
    assert not state.is_symlink()
    assert _read(run.run_dir, "state") == "COMPLETE"
    assert target.read_text(encoding="utf-8") == "QUEUED"


# === docker run arguments of the bundled engines ===


def test_run_sh_passes_sapporo_extra_docker_args_to_every_run(run_sh: Callable[..., RunSh]) -> None:
    run = run_sh("fake_args", extra_env={"SAPPORO_EXTRA_DOCKER_ARGS": "-v /data:/data:ro  --memory 1g"})

    assert run.wait() == 0
    lines = (run.run_dir / "extra_args.txt").read_text(encoding="utf-8").splitlines()
    assert lines == ["-v", "/data:/data:ro", "--memory", "1g"]


def test_run_sh_uses_set_extra_docker_args_edited_by_the_administrator(run_sh: Callable[..., RunSh]) -> None:
    edited = """
function set_extra_docker_args() {
    extra_docker_args=(-v "/data/${wf_engine}:/data:ro")
}
"""
    run = run_sh(
        "fake_args", extra_env={"SAPPORO_EXTRA_DOCKER_ARGS": "-v /everything:/everything"}, extra_script=edited
    )

    assert run.wait() == 0
    lines = (run.run_dir / "extra_args.txt").read_text(encoding="utf-8").splitlines()
    assert lines == ["-v", "/data/fake_args:/data:ro"]


ENGINES_WITH_RUN_TMP = {"cwltool", "cromwell", "ep3", "streamflow"}


@pytest.mark.parametrize("engine", ["cwltool", "nextflow", "toil", "cromwell", "snakemake", "ep3", "streamflow"])
def test_run_sh_mounts_only_exe_outputs_and_run_tmp_into_the_engine_container(
    run_sh: Callable[..., RunSh], engine: str
) -> None:
    # The fake docker fails on the real engine images, so run.sh stops after writing cmd.txt.
    # A relative workflow_url keeps snakemake from downloading it.
    run = run_sh(engine, wf_url="Snakefile" if engine == "snakemake" else "wf.cwl")

    run.wait()
    rd = run.run_dir
    exe = rd / RUN_DIR_STRUCTURE["exe_dir"]
    outputs = rd / RUN_DIR_STRUCTURE["outputs_dir"]
    tmp = rd / "tmp"
    cmd = (rd / RUN_DIR_STRUCTURE["cmd"]).read_text(encoding="utf-8")

    assert cmd.startswith("docker run ")
    assert f"-v {exe}:{exe} " in cmd
    assert f"-v {outputs}:{outputs} " in cmd
    assert f"-v {rd}:{rd} " not in cmd
    assert "-v /tmp:/tmp " not in cmd
    assert "bash -c" not in cmd
    if engine in ENGINES_WITH_RUN_TMP:
        assert f"-v {tmp}:{tmp} " in cmd
        assert f"-e TMPDIR={tmp} " in cmd
    else:
        assert f"{tmp}" not in cmd
    if engine == "cromwell":
        assert f"-Djava.io.tmpdir={tmp} " in cmd
    if engine == "nextflow":
        assert f"NXF_HOME={exe}/nxf_home " in cmd
    assert tmp.is_dir()
