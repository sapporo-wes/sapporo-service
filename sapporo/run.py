import contextlib
import json
import logging
import os
import shutil
import signal
import time
import traceback
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import Popen
from threading import Thread
from urllib import parse

import httpx
from zipstream import ZipStream

from sapporo.config import RUN_DIR_STRUCTURE, get_config
from sapporo.factory import create_service_info
from sapporo.run_io import (
    dump_runtime_info,
    glob_all_run_ids,
    read_file,
    read_state,
    resolve_content_path,
    resolve_run_dir,
    write_file,
)

__all__ = [
    "dump_runtime_info",
    "glob_all_run_ids",
    "read_file",
    "read_state",
    "resolve_content_path",
    "resolve_run_dir",
    "write_file",
]
from sapporo.schemas import RunRequestForm, State
from sapporo.utils import now_str, secure_filepath, user_agent, validate_url_not_metadata_service
from sapporo.validator import validate_wf_engine_param_token

LOGGER = logging.getLogger(__name__)


def recover_orphaned_runs() -> None:
    """Recover runs orphaned by a previous process crash.

    At startup, any run in a non-terminal state is an orphan because
    all child processes from the previous sapporo instance are dead.
    Marks them as SYSTEM_ERROR with appropriate logging.
    """
    run_ids = glob_all_run_ids()
    terminal_states = {
        State.COMPLETE,
        State.EXECUTOR_ERROR,
        State.SYSTEM_ERROR,
        State.CANCELED,
        State.DELETED,
        State.UNKNOWN,
    }

    recovered = 0
    for run_id in run_ids:
        state = read_state(run_id)
        if state in terminal_states:
            continue
        LOGGER.warning(
            "Recovering orphaned run: run_id=%s, previous_state=%s",
            run_id,
            state.value,
        )
        write_file(run_id, "state", State.SYSTEM_ERROR)
        write_file(run_id, "end_time", now_str())
        append_system_logs(
            run_id,
            f"Recovered orphaned run (previous state: {state.value}). "
            "The sapporo process was restarted while this run was active.",
        )
        recovered += 1

    if recovered > 0:
        LOGGER.info("Recovered %d orphaned run(s)", recovered)


def prepare_run_dir(run_id: str, run_request: RunRequestForm, username: str | None) -> None:
    run_dir = resolve_run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    exe_dir = resolve_content_path(run_id, "exe_dir")
    # 0o775: DinD workflow engine containers may run as non-root users.
    # Group-writable is sufficient when sapporo and engine share a group.
    exe_dir.mkdir(parents=True, exist_ok=True)
    exe_dir.chmod(0o775)
    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.chmod(0o775)

    write_file(run_id, "state", State.INITIALIZING)
    write_file(run_id, "start_time", now_str())
    write_file(run_id, "runtime_info", dump_runtime_info(run_id))
    write_file(run_id, "run_request", run_request.model_dump())
    write_file(run_id, "wf_params", run_request.workflow_params)
    write_file(run_id, "wf_engine_params", wf_engine_params_to_str(run_request))
    write_file(run_id, "system_logs", [])

    if username is not None:
        write_file(run_id, "username", username)

    write_wf_attachment(run_id, run_request)


def wf_engine_params_to_str(run_request: RunRequestForm) -> str:
    params: list[str] = []
    wf_engine = run_request.workflow_engine
    wf_engine_params = run_request.workflow_engine_parameters
    if wf_engine_params is None:
        service_info = create_service_info()
        default_wf_engine_params = service_info.default_workflow_engine_parameters.get(wf_engine or "", [])
        for param in default_wf_engine_params:
            params.append(param.name or "")
            params.append(param.default_value or "")
    else:
        for key, value in wf_engine_params.items():
            str_key = str(key)
            str_value = str(value)
            validate_wf_engine_param_token(str_key)
            validate_wf_engine_param_token(str_value)
            params.append(str_key)
            params.append(str_value)

    return " ".join([param for param in params if param != ""])


def write_wf_attachment(run_id: str, run_request: RunRequestForm) -> None:
    exe_dir = resolve_content_path(run_id, "exe_dir")
    for file in run_request.workflow_attachment:
        if file.filename:
            file_path = exe_dir.joinpath(secure_filepath(file.filename)).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open(mode="wb") as buffer:
                shutil.copyfileobj(file.file, buffer)


def download_wf_attachment(run_id: str, run_request: RunRequestForm) -> None:
    exe_dir = resolve_content_path(run_id, "exe_dir")
    for obj in run_request.workflow_attachment_obj:
        name = obj.file_name
        url = obj.file_url
        parsed_url = parse.urlparse(url)
        if parsed_url.scheme in ["http", "https"]:
            try:
                validate_url_not_metadata_service(url)
            except ValueError as e:
                msg = f"Blocked download of workflow attachment {obj}: {e}"
                raise Exception(msg) from e
            file_path = exe_dir.joinpath(secure_filepath(name)).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with httpx.Client() as client:
                    res = client.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": user_agent()})
                    res.raise_for_status()
                    with file_path.open(mode="wb") as f:
                        f.write(res.content)
            except httpx.HTTPStatusError as e:
                # Because it is a background task, raise Exception instead of HTTPException
                msg = f"Failed to download workflow attachment {obj}: {res.status_code} {res.text}"
                raise Exception(msg) from e
            except Exception as e:
                # Because it is a background task, raise Exception instead of HTTPException
                msg = f"Failed to download workflow attachment {obj}: {e}"
                raise Exception(msg) from e


def fork_run(run_id: str) -> None:
    run_dir = resolve_run_dir(run_id)
    stdout = resolve_content_path(run_id, "stdout")
    stderr = resolve_content_path(run_id, "stderr")
    cmd = ["/bin/bash", str(get_config().run_sh), str(run_dir)]
    write_file(run_id, "state", State.QUEUED)
    with stdout.open(mode="w", encoding="utf-8") as f_stdout, stderr.open(mode="w", encoding="utf-8") as f_stderr:
        process = Popen(
            cmd, cwd=str(run_dir), env=os.environ.copy(), encoding="utf-8", stdout=f_stdout, stderr=f_stderr
        )
    if process.pid is not None:
        write_file(run_id, "pid", process.pid)
    # Reap the child process in a background thread to prevent zombie processes
    reaper = Thread(target=process.wait, daemon=True)
    reaper.start()
    LOGGER.debug("Run forked: run_id=%s, pid=%d", run_id, process.pid or -1)


def post_run_task(run_id: str, run_request: RunRequestForm) -> None:
    """Run in the background after issuing a run_id in POST /runs."""
    try:
        download_wf_attachment(run_id, run_request)
        fork_run(run_id)
    except Exception as e:
        LOGGER.exception("Background task failed for run %s", run_id)
        write_file(run_id, "state", State.SYSTEM_ERROR)
        write_file(run_id, "end_time", now_str())
        error_msg = "".join(traceback.TracebackException.from_exception(e).format())
        append_system_logs(run_id, error_msg)


def append_system_logs(run_id: str, log: str) -> None:
    system_logs = read_file(run_id, "system_logs") or []
    system_logs.append(log)
    write_file(run_id, "system_logs", system_logs)


# Called from run.sh
def dump_outputs_list(run_dir: str | Path) -> None:
    run_dir = Path(run_dir).resolve()
    with run_dir.joinpath(RUN_DIR_STRUCTURE["runtime_info"]).open(mode="r", encoding="utf-8") as f:
        runtime_info = json.load(f)
    run_id = runtime_info.get("run_id", run_dir.name)
    base_url = runtime_info["base_url"]
    outputs_dir = run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"])
    output_files = sorted(list_files(outputs_dir))
    outputs = []
    for file in output_files:
        file_name = str(file.relative_to(outputs_dir))
        outputs.append({"file_name": file_name, "file_url": f"{base_url}/runs/{run_id}/outputs/{file_name}"})
    with run_dir.joinpath(RUN_DIR_STRUCTURE["outputs"]).open(mode="w", encoding="utf-8") as f:
        json.dump(outputs, f, indent=2)


def list_files(dir_: Path) -> Iterable[Path]:
    for root, _, files in os.walk(dir_):
        for file in files:
            yield Path(root).joinpath(file)


def cancel_run_task(run_id: str) -> None:
    LOGGER.debug("Run cancelled: run_id=%s", run_id)
    state = read_state(run_id)
    if state == State.INITIALIZING:
        # The process is doing in fastapi's background task. This task has no stop feature.
        # So, write CANCELING to the state.
        # Then, when run.sh is executed, check the state and do not run the job.
        write_file(run_id, "state", State.CANCELING)
    elif state in [State.QUEUED, State.RUNNING]:
        # The process is doing in run.sh. Send SIGUSR1 to the process.
        write_file(run_id, "state", State.CANCELING)
        pid: int | None = read_file(run_id, "pid")
        if pid is not None:
            try:
                os.kill(pid, signal.SIGUSR1)
            except ProcessLookupError:
                LOGGER.warning("Process %d not found when canceling run %s", pid, run_id)
            except PermissionError:
                LOGGER.warning("Permission denied when canceling run %s (pid=%d)", run_id, pid)
        else:
            write_file(run_id, "state", State.UNKNOWN)


KEEP_FILES = [
    RUN_DIR_STRUCTURE["state"],
    RUN_DIR_STRUCTURE["start_time"],
    RUN_DIR_STRUCTURE["end_time"],
]


def _wait_for_process_exit(pid: int, timeout: float = 30.0) -> bool:
    """Wait for a process to exit, sending SIGKILL on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.5)
    # Timeout: force kill
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)
    return False


def delete_run_task(run_id: str) -> None:
    LOGGER.debug("Run deleted: run_id=%s", run_id)
    # 1. Cancel the run if it is running.
    cancel_run_task(run_id)

    # 1.5 Wait for the process to exit before deleting files.
    pid: int | None = read_file(run_id, "pid")
    if pid is not None and not _wait_for_process_exit(pid):
        LOGGER.warning("Process %d did not exit in time for run %s, sent SIGKILL", pid, run_id)

    # 2. Transition to DELETING immediately (non-blocking).
    write_file(run_id, "state", State.DELETING)

    # 3. Delete run-related files.
    run_dir = resolve_run_dir(run_id)
    for path in run_dir.glob("*"):
        if path.name in KEEP_FILES:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    # 4. Record the deletion.
    write_file(run_id, "state", State.DELETED)


def outputs_zip_stream(run_id: str, name: str | None = None) -> tuple[Iterable[bytes], int]:
    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    base_dir_name = name or f"sapporo_{run_id}_outputs"
    zs = ZipStream.from_path(outputs_dir, arcname=base_dir_name, sized=True)
    return iter(zs), len(zs)


def ro_crate_zip_stream(run_id: str) -> tuple[Iterable[bytes], int]:
    run_dir = resolve_run_dir(run_id)
    base_dir_name = f"sapporo_{run_id}_ro_crate"
    zs = ZipStream.from_path(run_dir, arcname=base_dir_name, sized=True)
    return iter(zs), len(zs)


def bulk_delete_run_tasks(run_ids: list[str]) -> None:
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_run_id = {executor.submit(delete_run_task, rid): rid for rid in run_ids}
        for future in as_completed(future_to_run_id):
            rid = future_to_run_id[future]
            try:
                future.result()
            except Exception as e:
                msg = f"Failed to delete run {rid}"
                raise Exception(msg) from e


def remove_old_runs() -> None:
    # Avoid circular import
    from sapporo.database import list_old_runs_db

    older_than_days = get_config().run_remove_older_than_days
    if older_than_days is None:
        return

    old_runs = list_old_runs_db(older_than_days)
    if not old_runs:
        return

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_run_id = {executor.submit(delete_run_task, run.run_id): run.run_id for run in old_runs}
        for future in as_completed(future_to_run_id):
            run_id = future_to_run_id[future]
            try:
                future.result()
            except Exception as e:
                msg = f"Failed to delete run {run_id}"
                raise Exception(msg) from e

    LOGGER.debug("Old runs removed: count=%d", len(old_runs))
