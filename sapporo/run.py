import asyncio
import contextlib
import json
import logging
import os
import shutil
import signal
import time
import traceback
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath
from subprocess import Popen
from threading import Thread
from typing import Any
from urllib import parse

import httpx
from zipstream import ZipStream

from sapporo.config import RUN_DIR_STRUCTURE, get_config
from sapporo.exceptions import raise_bad_request, raise_not_found
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
from sapporo.utils import (
    inside_run_dir,
    now_str,
    open_run_file,
    open_run_file_for_write,
    read_run_dir_file,
    resolve_within_run,
    secure_filepath,
    user_agent,
    validate_url_not_metadata_service,
    walk_within_run,
)
from sapporo.validator import validate_wf_engine_param_token

LOGGER = logging.getLogger(__name__)


def _process_alive(pid: int) -> bool:
    """Check whether a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists but we cannot signal it

    return True


def _run_sh_alive(run_id: str, pid: int) -> bool:
    """Whether pid is the run.sh process of this run.

    The command line in /proc is checked, so that a PID that the system reused for another process
    (for example after a container restart) is not mistaken for the run. Without /proc, any live
    process counts.
    """
    proc_dir = Path("/proc")
    if not proc_dir.is_dir():
        return _process_alive(pid)
    cmdline = b""
    for _ in range(5):
        try:
            cmdline = proc_dir.joinpath(str(pid), "cmdline").read_bytes()
        except OSError:
            return False
        if cmdline:
            break
        # Empty for a zombie, and for a moment while the process is still being exec'd
        time.sleep(0.01)

    return str(resolve_run_dir(run_id)).encode() in cmdline.split(b"\0")


# Same value that run.sh writes for a canceled run
CANCELED_EXIT_CODE = 138

# Runs that this process is preparing: their attachments are downloading, or run.sh was started but
# has not written run.pid yet. reconcile_runs must not treat them as vanished.
_PREPARING_RUNS: set[str] = set()

# How long post_run_task waits for run.sh to write run.pid before it stops guarding the run
RUN_PID_WAIT_SECONDS = 5.0

_PREPARATION_ABORT_STATES = frozenset({State.CANCELING, State.DELETING, State.DELETED})


class RunPreparationAbortedError(Exception):
    """The run was canceled or deleted while its attachments were being downloaded."""


def _abort_preparation_if_requested(run_id: str) -> None:
    if read_state(run_id) in _PREPARATION_ABORT_STATES:
        raise RunPreparationAbortedError(run_id)


_RECONCILE_SKIP_STATES = frozenset(
    {
        State.COMPLETE,
        State.EXECUTOR_ERROR,
        State.SYSTEM_ERROR,
        State.CANCELED,
        State.DELETED,
        State.UNKNOWN,
    }
)


def reconcile_runs() -> None:
    """Reconcile runs whose declared state does not match reality.

    For each run in a non-terminal state, reads the PID file and checks
    whether the process is still alive:

    - PID present + process alive -> skip (running normally)
    - PID present + process dead  -> SYSTEM_ERROR (reason: "process vanished")
    - PID absent                  -> SYSTEM_ERROR (reason: "no pid file")

    A run whose directory cannot be processed is logged and skipped, so that one broken run does not
    stop the reconciliation of the others.
    """
    reconciled = 0
    for run_id in glob_all_run_ids():
        try:
            if _reconcile_run(run_id):
                reconciled += 1
        except Exception as e:
            LOGGER.warning("Skipping run that cannot be reconciled: run_id=%s, error=%s", run_id, e)

    if reconciled > 0:
        LOGGER.info("Reconciled %d run(s)", reconciled)


def _reconcile_run(run_id: str) -> bool:
    """Reconcile one run. Returns True when the run was marked as SYSTEM_ERROR."""
    state = read_state(run_id)
    if state in _RECONCILE_SKIP_STATES:
        return False
    if run_id in _PREPARING_RUNS:
        return False

    pid: int | None = read_file(run_id, "pid")
    if pid is not None and _run_sh_alive(run_id, pid):
        return False

    reason = "process vanished" if pid is not None else "no pid file"
    LOGGER.warning(
        "Reconciling run: run_id=%s, previous_state=%s, reason=%s",
        run_id,
        state.value,
        reason,
    )
    write_file(run_id, "state", State.SYSTEM_ERROR)
    write_file(run_id, "end_time", now_str())
    append_system_logs(
        run_id,
        f"Reconciled run (previous state: {state.value}, reason: {reason}). The process was no longer running.",
    )

    return True


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
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with file_path.open(mode="wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            except OSError as e:
                # For example a file and a directory with the same name in one request
                raise_bad_request(f"Cannot write workflow attachment {file.filename!r}: {e.strerror}")


# A single deadline cannot serve both purposes: an unreachable host has to fail fast, while a large
# attachment legitimately takes a while to arrive. Attachments come from arbitrary URLs, so the
# transient failures below (connection resets, a proxy restarting, a gateway returning 502) are
# expected rather than exceptional, and one attempt is not enough to distinguish them from a real
# outage.
ATTACHMENT_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=60.0, pool=10.0)
ATTACHMENT_MAX_ATTEMPTS = 3
ATTACHMENT_RETRY_BACKOFF_SECONDS = 1.0
ATTACHMENT_RETRY_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
ATTACHMENT_MAX_REDIRECTS = 5
ATTACHMENT_CHUNK_SIZE = 1024 * 1024


async def _stream_to_file(
    client: httpx.AsyncClient, url: str, file_path: Path, check_abort: Callable[[], None]
) -> None:
    """GET url into file_path in chunks, following redirects one hop at a time.

    Every hop is checked against the metadata service addresses before it is requested, so a
    redirect cannot lead to an address that the first URL was not allowed to point to. check_abort
    is called before every chunk is written.
    """
    for _ in range(ATTACHMENT_MAX_REDIRECTS + 1):
        # The check resolves the hostname, which blocks, so it runs off the event loop
        await asyncio.to_thread(validate_url_not_metadata_service, url)
        async with client.stream(
            "GET", url, timeout=ATTACHMENT_TIMEOUT, follow_redirects=False, headers={"User-Agent": user_agent()}
        ) as res:
            if res.is_redirect:
                url = str(res.url.join(res.headers["location"]))
                continue
            if res.is_error:
                await res.aread()
            res.raise_for_status()
            with file_path.open(mode="wb") as f:
                async for chunk in res.aiter_bytes(ATTACHMENT_CHUNK_SIZE):
                    check_abort()
                    f.write(chunk)
            return
    msg = f"More than {ATTACHMENT_MAX_REDIRECTS} redirects while downloading {url}"
    raise httpx.TooManyRedirects(msg)


async def download_url(url: str, file_path: Path, check_abort: Callable[[], None] = lambda: None) -> None:
    """Download url into file_path, retrying transient failures with exponential backoff.

    The body is written in chunks, so a large file does not stay in memory and the download can be
    abandoned between chunks. A retry starts the file again.
    """
    last_error: Exception
    async with httpx.AsyncClient() as client:
        for attempt in range(1, ATTACHMENT_MAX_ATTEMPTS + 1):
            try:
                await _stream_to_file(client, url, file_path, check_abort)
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in ATTACHMENT_RETRY_STATUS_CODES:
                    raise
                last_error = e
            except httpx.TransportError as e:
                last_error = e
            else:
                return

            if attempt < ATTACHMENT_MAX_ATTEMPTS:
                backoff = ATTACHMENT_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                LOGGER.warning(
                    "Retrying download: url=%s, attempt=%d/%d, backoff=%.1fs, error=%s",
                    url,
                    attempt,
                    ATTACHMENT_MAX_ATTEMPTS,
                    backoff,
                    last_error,
                )
                await asyncio.sleep(backoff)

    raise last_error


async def download_wf_attachment(run_id: str, run_request: RunRequestForm) -> None:
    exe_dir = resolve_content_path(run_id, "exe_dir")
    for obj in run_request.workflow_attachment_obj:
        _abort_preparation_if_requested(run_id)
        url = obj.file_url
        file_path = exe_dir.joinpath(secure_filepath(obj.file_name)).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Because it is a background task, raise Exception instead of HTTPException
        try:
            await download_url(url, file_path, lambda: _abort_preparation_if_requested(run_id))
        except RunPreparationAbortedError:
            raise
        except ValueError as e:
            msg = f"Blocked download of workflow attachment {obj}: {e}"
            raise Exception(msg) from e
        except httpx.HTTPStatusError as e:
            msg = f"Failed to download workflow attachment {obj}: {e.response.status_code} {e.response.text}"
            raise Exception(msg) from e
        except Exception as e:
            msg = f"Failed to download workflow attachment {obj}: {e}"
            raise Exception(msg) from e


def fork_run(run_id: str) -> "Popen[str]":
    """Start run.sh for the run. run.sh writes run.pid itself, after it has set its signal traps."""
    _abort_preparation_if_requested(run_id)
    run_dir = resolve_run_dir(run_id)
    stdout = resolve_content_path(run_id, "stdout")
    stderr = resolve_content_path(run_id, "stderr")
    cmd = ["/bin/bash", str(get_config().run_sh), str(run_dir)]
    env = os.environ.copy()
    env["SAPPORO_CANCEL_GRACE_SECONDS"] = str(get_config().cancel_grace_seconds)
    write_file(run_id, "state", State.QUEUED)
    with stdout.open(mode="w", encoding="utf-8") as f_stdout, stderr.open(mode="w", encoding="utf-8") as f_stderr:
        process = Popen(cmd, cwd=str(run_dir), env=env, encoding="utf-8", stdout=f_stdout, stderr=f_stderr)
    # Reap the child process in a background thread to prevent zombie processes
    reaper = Thread(target=process.wait, daemon=True)
    reaper.start()
    LOGGER.debug("Run forked: run_id=%s, pid=%d", run_id, process.pid or -1)
    return process


async def _wait_for_run_pid(run_id: str, process: "Popen[str]") -> None:
    """Wait until run.sh has written run.pid or has exited, so that reconcile_runs can judge the run."""
    pid_path = resolve_content_path(run_id, "pid")
    deadline = time.monotonic() + RUN_PID_WAIT_SECONDS
    while time.monotonic() < deadline:
        if pid_path.exists() or process.poll() is not None:
            return
        await asyncio.sleep(0.05)
    LOGGER.warning("run.sh of run %s has not written run.pid within %.0f seconds", run_id, RUN_PID_WAIT_SECONDS)


# Reported as the exit code when the run fails before run.sh is ever started, so that the run log
# carries a failure exit code instead of null.
POST_RUN_TASK_FAILURE_EXIT_CODE = 1


async def post_run_task(run_id: str, run_request: RunRequestForm) -> None:
    """Run in the background after issuing a run_id in POST /runs."""
    _PREPARING_RUNS.add(run_id)
    try:
        await download_wf_attachment(run_id, run_request)
        process = fork_run(run_id)
        await _wait_for_run_pid(run_id, process)
    except RunPreparationAbortedError:
        _settle_aborted_preparation(run_id)
    except Exception as e:
        if read_state(run_id) in _PREPARATION_ABORT_STATES:
            _settle_aborted_preparation(run_id)
            return
        LOGGER.exception("Background task failed for run %s", run_id)
        write_file(run_id, "exit_code", POST_RUN_TASK_FAILURE_EXIT_CODE)
        write_file(run_id, "state", State.SYSTEM_ERROR)
        write_file(run_id, "end_time", now_str())
        error_msg = "".join(traceback.TracebackException.from_exception(e).format())
        append_system_logs(run_id, error_msg)
    finally:
        _PREPARING_RUNS.discard(run_id)


def _settle_aborted_preparation(run_id: str) -> None:
    """Finish a run that was canceled or deleted before run.sh started."""
    if read_state(run_id) == State.CANCELING:
        write_file(run_id, "exit_code", CANCELED_EXIT_CODE)
        write_file(run_id, "end_time", now_str())
        write_file(run_id, "state", State.CANCELED)
        LOGGER.info("Run %s was canceled before run.sh started", run_id)
        return
    # Deleted while attachments were downloading: remove what the download wrote after the deletion
    shutil.rmtree(resolve_content_path(run_id, "exe_dir"), ignore_errors=True)
    LOGGER.info("Run %s was deleted before run.sh started", run_id)


def append_system_logs(run_id: str, log: str) -> None:
    content = read_file(run_id, "system_logs")
    if content is None:
        system_logs: list[Any] = []
    elif isinstance(content, list):
        system_logs = content
    else:
        # system_logs.json is expected to hold a list; keep foreign content as the first entry.
        system_logs = [str(content)]
    system_logs.append(log)
    write_file(run_id, "system_logs", system_logs)


# Called from run.sh
def dump_outputs_list(run_dir: str | Path) -> None:
    run_dir = Path(run_dir).resolve()
    runtime_info = read_run_dir_file(run_dir, "runtime_info")
    if not isinstance(runtime_info, dict):
        msg = f"runtime_info.json is missing or is not a JSON object in {run_dir}"
        raise TypeError(msg)
    run_id = runtime_info.get("run_id", run_dir.name)
    base_url = runtime_info["base_url"]
    outputs_dir = run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"])
    output_files = sorted(list_files(outputs_dir, run_dir))
    outputs = []
    for file in output_files:
        file_name = str(file.relative_to(outputs_dir))
        # The URL must round-trip names with spaces, "+" and other reserved characters
        file_url = f"{base_url}/runs/{run_id}/outputs/{parse.quote(file_name)}"
        outputs.append({"file_name": file_name, "file_url": file_url})
    with open_run_file_for_write(run_dir.joinpath(RUN_DIR_STRUCTURE["outputs"])) as f:
        json.dump(outputs, f, indent=2)


def list_files(dir_: Path, run_dir: Path) -> Iterable[Path]:
    """Files under dir_, following symlinks only inside the run directory."""
    for current, _, files in walk_within_run(dir_, run_dir):
        for name in files:
            yield current / name


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
        if pid is None:
            # run.sh has not set its traps and written run.pid yet; it reads CANCELING before it starts the workflow
            LOGGER.info("Run %s has no run.pid yet; run.sh ends it as CANCELED on start", run_id)
        elif not _run_sh_alive(run_id, pid):
            # run.sh is gone without a terminal state; reconcile_runs settles the run later
            LOGGER.warning("run.sh (pid=%d) of run %s is not running, nothing to cancel", pid, run_id)
        else:
            try:
                os.kill(pid, signal.SIGUSR1)
            except ProcessLookupError:
                LOGGER.warning("Process %d not found when canceling run %s", pid, run_id)
            except PermissionError:
                LOGGER.warning("Permission denied when canceling run %s (pid=%d)", run_id, pid)


# Kept when a run is deleted, so that the run stays listed as DELETED and stays attributable to
# its owner
KEEP_FILES = [
    RUN_DIR_STRUCTURE["state"],
    RUN_DIR_STRUCTURE["start_time"],
    RUN_DIR_STRUCTURE["end_time"],
    RUN_DIR_STRUCTURE["username"],
]


def _wait_for_run_sh_exit(run_id: str, pid: int, timeout: float) -> bool:
    """Wait for the run.sh process of this run to exit, sending SIGKILL on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _run_sh_alive(run_id, pid):
            return True
        time.sleep(0.5)
    if _run_sh_alive(run_id, pid):
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
    return False


def delete_run_task(run_id: str) -> None:
    LOGGER.debug("Run deleted: run_id=%s", run_id)
    # 1. Cancel the run if it is running.
    cancel_run_task(run_id)

    # 1.5 Wait for run.sh to exit before deleting files. run.sh needs the cancel grace period to
    # stop the engine, so allow a little more than that.
    pid: int | None = read_file(run_id, "pid")
    if pid is not None and _run_sh_alive(run_id, pid):
        timeout = get_config().cancel_grace_seconds + 10
        if not _wait_for_run_sh_exit(run_id, pid, timeout):
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
    _sync_run_db(run_id)


def _sync_run_db(run_id: str) -> None:
    # Avoid circular import
    from sapporo.database import sync_run_db

    try:
        sync_run_db(run_id)
    except Exception as e:
        LOGGER.warning("Could not update the run index after deleting run %s: %s", run_id, e)


def resolve_output_file(run_id: str, path: str) -> Path:
    """Map a requested output path to the file to serve.

    The path is used as given, not sanitized, so that every file the engine wrote can be addressed.
    A path that climbs out of outputs/ is rejected, and a symlink is followed only when its target
    lies inside the run directory.
    """
    parts = PurePosixPath(path).parts
    if not parts or path.startswith("/") or any(part in ("", "..") or "\0" in part for part in parts):
        raise_bad_request(f"Invalid file path: {path!r}")
    file_path = resolve_content_path(run_id, "outputs_dir").joinpath(*parts)
    if not file_path.exists() and not file_path.is_symlink():
        raise_not_found("File", path)
    if not inside_run_dir(file_path, resolve_run_dir(run_id)):
        raise_bad_request(f"Invalid file path: {path!r}")
    if not file_path.is_file():
        raise_not_found("File", path)

    return file_path


def _add_tree_within_run(zs: ZipStream, root: Path, arcname: PurePosixPath, run_dir: Path) -> None:
    """Add a directory tree to zs, leaving out files whose target lies outside the run directory."""
    for current_path, dirs, files in walk_within_run(root, run_dir):
        current_arcname = arcname / current_path.relative_to(root).as_posix()
        if not dirs and not files:
            zs.add_path(current_path, arcname=str(current_arcname), recurse=False)
        for name in files:
            zs.add_path(current_path / name, arcname=str(current_arcname / name))


def outputs_zip_stream(run_id: str, name: str | None = None) -> tuple[Iterable[bytes], int]:
    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    base_dir_name = name or f"sapporo_{run_id}_outputs"
    zs = ZipStream(sized=True)
    _add_tree_within_run(zs, outputs_dir, PurePosixPath(base_dir_name), resolve_run_dir(run_id))
    return iter(zs), len(zs)


_DATA_ENTITY_TYPES = frozenset({"File", "Dataset"})


def _data_entity_path(entity_id: str) -> PurePosixPath | None:
    """Return the path in the run directory that the @id of a data entity names.

    None for an id that is not a path in the run directory: a URL, a fragment, the root dataset, an
    absolute path, or a path that climbs out with "..". The ids of ro-crate-py are percent-encoded.
    """
    if entity_id.startswith("#") or parse.urlsplit(entity_id).scheme:
        return None
    path = PurePosixPath(parse.unquote(entity_id))
    if path.is_absolute() or not path.parts or any(part == ".." or "\0" in part for part in path.parts):
        return None
    return path


def _ro_crate_data_entity_paths(run_dir: Path) -> list[PurePosixPath]:
    """Return the paths of the files and directories that ro-crate-metadata.json lists as data entities."""
    f = open_run_file(run_dir.joinpath(RUN_DIR_STRUCTURE["ro_crate"]))
    if f is None:
        return []
    with f:
        try:
            crate = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []
    graph = crate.get("@graph") if isinstance(crate, dict) else None
    if not isinstance(graph, list):
        return []

    paths: list[PurePosixPath] = []
    for entity in graph:
        if not isinstance(entity, dict):
            continue
        types = entity.get("@type")
        type_names = {types} if isinstance(types, str) else set(types) if isinstance(types, list) else set()
        entity_id = entity.get("@id")
        if not (_DATA_ENTITY_TYPES & type_names) or not isinstance(entity_id, str):
            continue
        path = _data_entity_path(entity_id)
        if path is not None:
            paths.append(path)
    return paths


def ro_crate_zip_stream(run_id: str) -> tuple[Iterable[bytes], int]:
    """Zip the crate: ro-crate-metadata.json, README.md and the data entities that the crate lists.

    Control files that the crate does not list, such as run.pid and username.txt, stay out. A file
    directly under the run directory is a control file and is added only as a regular file, while a
    path below it follows the rule of outputs/: a symlink is followed when its target lies inside
    the run directory.
    """
    run_dir = resolve_run_dir(run_id)
    base_dir = PurePosixPath(f"sapporo_{run_id}_ro_crate")
    zs = ZipStream(sized=True)
    added: set[PurePosixPath] = set()
    candidates = [PurePosixPath(RUN_DIR_STRUCTURE["ro_crate"]), PurePosixPath("README.md")]
    for rel_path in [*candidates, *_ro_crate_data_entity_paths(run_dir)]:
        if rel_path in added:
            continue
        added.add(rel_path)
        path = run_dir.joinpath(*rel_path.parts)
        if len(rel_path.parts) == 1 and path.is_symlink():
            continue
        real_path = resolve_within_run(path, run_dir)
        if real_path is None:
            continue
        if real_path.is_dir():
            _add_tree_within_run(zs, path, base_dir / rel_path, run_dir)
        elif real_path.is_file():
            zs.add_path(path, arcname=str(base_dir / rel_path))

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

    failed = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_run_id = {executor.submit(delete_run_task, run.run_id): run.run_id for run in old_runs}
        for future in as_completed(future_to_run_id):
            run_id = future_to_run_id[future]
            try:
                future.result()
            except Exception:
                LOGGER.exception("Failed to delete old run: run_id=%s", run_id)
                failed += 1

    LOGGER.debug("Old runs removed: count=%d, failed=%d", len(old_runs) - failed, failed)
