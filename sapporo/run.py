import json
import os
import shutil
import traceback
import urllib
from pathlib import Path
from subprocess import Popen
from typing import Any, List

import httpx

from sapporo.config import (RUN_DIR_STRUCTURE, RUN_DIR_STRUCTURE_KEYS,
                            get_config)
from sapporo.factory import create_service_info
from sapporo.schemas import RunRequestForm
from sapporo.utils import secure_filepath


def prepare_run_dir(run_id: str, run_request: RunRequestForm) -> None:
    run_dir = resolve_run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    exe_dir = resolve_content_path(run_id, "exe_dir")
    exe_dir.mkdir(mode=0o777, parents=True, exist_ok=True)
    output_dir = resolve_content_path(run_id, "output_dir")
    output_dir.mkdir(mode=0o777, parents=True, exist_ok=True)

    print(run_request)

    write_file(run_id, "run_request", run_request.model_dump())
    write_file(run_id, "wf_params", run_request.workflow_params)
    write_file(run_id, "wf_engine_params", wf_engine_params_to_str(run_request))

    write_wf_attachment(run_id, run_request)


def resolve_run_dir(run_id: str) -> Path:
    run_dir_base = get_config().run_dir

    return run_dir_base.joinpath(run_id[:2]).joinpath(run_id).resolve()


def resolve_content_path(run_id: str, key: RUN_DIR_STRUCTURE_KEYS) -> Path:
    return resolve_run_dir(run_id).joinpath(RUN_DIR_STRUCTURE[key])


def write_file(run_id: str, key: RUN_DIR_STRUCTURE_KEYS, content: Any) -> None:
    file = resolve_content_path(run_id, key)
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.suffix == ".json":
        content = json.dumps(content, indent=2)
    with file.open(mode="w", encoding="utf-8") as f:
        f.write(str(content))


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
    write_file(run_id, "state", "QUEUED")
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
    write_file(run_id, "state", "INITIALIZING")
    try:
        download_wf_attachment(run_id, run_request)
        fork_run(run_id)
    except Exception as e:  # pylint: disable=W0718
        write_file(run_id, "state", "EXECUTOR_ERROR")
        error_msg = "".join(traceback.TracebackException.from_exception(e).format())
        write_file(run_id, "stderr", error_msg)
