import json
import os
import shlex
import shutil
import signal
import time
import traceback
import urllib
import zipfile
from io import BytesIO
from pathlib import Path
from subprocess import Popen
from typing import Any, Dict, Iterable, List, Optional, Union

import httpx

from sapporo.config import RUN_DIR_STRUCTURE, RunDirStructureKeys, get_config
from sapporo.factory import create_service_info
from sapporo.schemas import RunRequest, RunRequestForm, State
from sapporo.utils import now_str, sapporo_version, secure_filepath


def prepare_run_dir(run_id: str, run_request: RunRequestForm) -> None:
    run_dir = resolve_run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    exe_dir = resolve_content_path(run_id, "exe_dir")
    exe_dir.mkdir(mode=0o777, parents=True, exist_ok=True)
    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    outputs_dir.mkdir(mode=0o777, parents=True, exist_ok=True)

    write_file(run_id, "state", State.INITIALIZING)
    write_file(run_id, "start_time", now_str())
    write_file(run_id, "runtime_info", dump_runtime_info())
    write_file(run_id, "run_request", run_request.model_dump())
    write_file(run_id, "wf_params", run_request.workflow_params)
    write_file(run_id, "wf_engine_params", wf_engine_params_to_str(run_request))
    write_file(run_id, "system_logs", [])

    write_wf_attachment(run_id, run_request)


def resolve_run_dir(run_id: str) -> Path:
    run_dir_base = get_config().run_dir

    return run_dir_base.joinpath(run_id[:2]).joinpath(run_id).resolve()


def resolve_content_path(run_id: str, key: RunDirStructureKeys) -> Path:
    return resolve_run_dir(run_id).joinpath(RUN_DIR_STRUCTURE[key])


def write_file(run_id: str, key: RunDirStructureKeys, content: Any) -> None:
    file = resolve_content_path(run_id, key)
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.suffix == ".json":
        content = json.dumps(content, indent=2)
    with file.open(mode="w", encoding="utf-8") as f:
        f.write(str(content))


def dump_runtime_info() -> Dict[str, Any]:
    return {
        "sapporo_version": sapporo_version(),
        "base_url": get_config().base_url,
    }


def wf_engine_params_to_str(run_request: RunRequestForm) -> str:
    params: List[str] = []
    wf_engine = run_request.workflow_engine
    wf_engine_params = run_request.workflow_engine_parameters
    if wf_engine_params is None:
        service_info = create_service_info()
        default_wf_engine_params = service_info.default_workflow_engine_parameters.get(wf_engine or "", [])  # pylint: disable=E1101
        for param in default_wf_engine_params:
            params.append(param.get("name", ""))
            params.append(param.get("default_value", ""))
    else:
        for key, value in wf_engine_params.items():
            params.append(str(key))
            params.append(str(value))

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
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme in ["http", "https"]:
            file_path = exe_dir.joinpath(secure_filepath(name)).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with httpx.Client() as client:
                res = client.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "sapporo"})
                if res.status_code == 200:
                    with file_path.open(mode="wb") as f:
                        f.write(res.content)
                else:
                    raise Exception(f"Failed to download workflow attachment {obj}: {res.status_code} {res.text}")  # pylint: disable=W0719


def fork_run(run_id: str) -> None:
    run_dir = resolve_run_dir(run_id)
    stdout = resolve_content_path(run_id, "stdout")
    stderr = resolve_content_path(run_id, "stderr")
    cmd = ["/bin/bash", str(get_config().run_sh), str(run_dir)]
    write_file(run_id, "state", State.QUEUED)
    with stdout.open(mode="w", encoding="utf-8") as f_stdout, stderr.open(mode="w", encoding="utf-8") as f_stderr:
        process = Popen(cmd,  # pylint: disable=R1732
                        cwd=str(run_dir),
                        env=os.environ.copy(),
                        encoding="utf-8",
                        stdout=f_stdout,
                        stderr=f_stderr)
    if process.pid is not None:
        write_file(run_id, "pid", process.pid)


def post_run_task(run_id: str, run_request: RunRequestForm) -> None:
    """\
    A function that runs in the background after issuing a run_id in POST /runs.
    """
    try:
        download_wf_attachment(run_id, run_request)
        fork_run(run_id)
    except Exception as e:  # pylint: disable=W0718
        write_file(run_id, "state", State.EXECUTOR_ERROR)
        write_file(run_id, "end_time", now_str())
        error_msg = "".join(traceback.TracebackException.from_exception(e).format())
        append_system_logs(run_id, error_msg)


def read_file(run_id: str, key: RunDirStructureKeys) -> Any:
    if key == "state":
        read_state(run_id)

    if "dir" in key:
        return None
    file_path = resolve_content_path(run_id, key)
    if file_path.exists() is False:
        return None

    with file_path.open(mode="r", encoding="utf-8") as f:
        content = f.read().strip()
        # Special handling for specific keys
        if key == "run_request":
            return RunRequest.model_validate_json(content)
        if key == "cmd":
            return shlex.split(content)
        if key in ["start_time", "end_time", "stdout", "stderr"]:
            return content
        if key in ["pid", "exit_code"]:
            return int(content)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content


def read_state(run_id: str) -> State:
    try:
        with resolve_content_path(run_id, "state").open(mode="r", encoding="utf-8") as f:
            return State(f.read().strip())
    except FileNotFoundError:
        return State("UNKNOWN")


def append_system_logs(run_id: str, log: str) -> None:
    system_logs = read_file(run_id, "system_logs") or []
    system_logs.append(log)
    write_file(run_id, "system_logs", system_logs)


# Called from run.sh
def dump_outputs_list(run_dir: Union[str, Path]) -> None:
    run_dir = Path(run_dir).resolve()
    run_id = run_dir.name
    with run_dir.joinpath(RUN_DIR_STRUCTURE["runtime_info"]).open(mode="r", encoding="utf-8") as f:
        runtime_info = json.load(f)
    base_url = runtime_info["base_url"]
    outputs_dir = run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"])
    output_files = sorted(list(list_files(outputs_dir)))
    outputs = []
    for file in output_files:
        file_name = str(file.relative_to(outputs_dir))
        outputs.append({
            "file_name": file_name,
            "file_url": f"{base_url}/runs/{run_id}/outputs/{file_name}"
        })
    with run_dir.joinpath(RUN_DIR_STRUCTURE["outputs"]).open(mode="w", encoding="utf-8") as f:
        json.dump(outputs, f, indent=2)


def list_files(dir_: Path) -> Iterable[Path]:
    for root, _, files in os.walk(dir_):
        for file in files:
            yield Path(root).joinpath(file)


def glob_all_run_ids() -> List[str]:
    return [run_dir.parent.name for run_dir in get_config().run_dir.glob(f"*/*/{RUN_DIR_STRUCTURE['run_request']}")]


def cancel_run_task(run_id: str) -> None:
    state = read_state(run_id)
    if state == State.INITIALIZING:
        # The process is doing in fastapi's background task. This task has no stop feature.
        # So, write CANCELING to the state.
        # Then, when run.sh is executed, check the state and do not run the job.
        write_file(run_id, "state", State.CANCELING)
    if state in [State.QUEUED, State.RUNNING]:
        # The process is doing in run.sh. Send SIGUSR1 to the process.
        write_file(run_id, "state", State.CANCELING)
        pid: Optional[int] = read_file(run_id, "pid")
        if pid is not None:
            os.kill(pid, signal.SIGUSR1)
        else:
            write_file(run_id, "state", State.UNKNOWN)


KEEP_FILES = [
    RUN_DIR_STRUCTURE["state"],
    RUN_DIR_STRUCTURE["start_time"],
    RUN_DIR_STRUCTURE["end_time"],
]


def delete_run_task(run_id: str) -> None:
    # 1. Cancel the run if it is running.
    cancel_run_task(run_id)

    # 2. Delete run-related files.
    # Pooling 10min for the cancellation process.
    # If it does not cancel after 10min, delete it as it is.
    for _ in range(10):
        state = read_state(run_id)
        if state == State.CANCELING:
            time.sleep(60)
        else:
            break
    write_file(run_id, "state", State.DELETING)
    run_dir = resolve_run_dir(run_id)
    for path in run_dir.glob("*"):
        if path.name in KEEP_FILES:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    # 3. Record the deletion.
    write_file(run_id, "state", State.DELETED)


def zip_stream(run_id: str) -> Iterable[bytes]:
    outputs_dir = resolve_content_path(run_id, "outputs_dir")
    base_dir_name = f"sapporo_{run_id}_outputs"

    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in outputs_dir.glob("**/*"):
                if path.is_dir():
                    # Check if directory is empty
                    if not any(path.iterdir()):
                        arc_path = f"{base_dir_name}/{path.relative_to(outputs_dir)}/"
                        zf.writestr(arc_path, "")
                if path.is_file():
                    arc_path = f"{base_dir_name}/{path.relative_to(outputs_dir)}"
                    zf.write(path, arc_path)
        buffer.seek(0)
        while chunk := buffer.read(8192):
            yield chunk
