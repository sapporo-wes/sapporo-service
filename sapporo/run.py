#!/usr/bin/env python3
# coding: utf-8
import json
import os
import shlex
import signal
from pathlib import Path
from subprocess import Popen
from typing import Dict, List, Optional, Union
from urllib import parse

import requests
from flask import abort, current_app
from requests import Response
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from sapporo.type import (DefaultWorkflowEngineParameter, Log, RunLog,
                          RunRequest, State, Workflow)
from sapporo.util import (generate_service_info, get_all_run_ids, get_path,
                          get_run_dir, get_state, get_workflow, read_file,
                          validate_wf_type, write_file)


def validate_and_update_run_request(run_id: str,
                                    run_request: RunRequest,
                                    files: Dict[str, FileStorage]) \
        -> RunRequest:
    if current_app.config["REGISTERED_ONLY_MODE"]:
        for field in ["workflow_params", "workflow_engine_name"]:
            if field not in run_request:
                abort(400,
                      f"{field} not included in the form data of the request.")
        if "workflow_name" not in run_request:
            abort(400,
                  "Currently, Sapporo is running with registered_only_mode. "
                  "Therefore, you need to run the workflow with the "
                  "workflow_name.")
        wf: Workflow = get_workflow(run_request["workflow_name"])
        run_request["workflow_url"] = wf["workflow_url"]
        run_request["workflow_type"] = wf["workflow_type"]
        run_request["workflow_type_version"] = wf["workflow_type_version"]
        run_request["workflow_attachment"] = wf["workflow_attachment"]
    else:
        for field in ["workflow_params", "workflow_type",
                      "workflow_type_version", "workflow_url",
                      "workflow_engine_name"]:
            if field not in run_request:
                abort(400,
                      f"{field} not included in the form data of the request.")
        run_request["workflow_name"] = \
            parse.urlparse(run_request["workflow_url"]).path.split("/")[-1]

    if "workflow_attachment" not in run_request:
        run_request["workflow_attachment"] = []
    if "workflow_engine_parameters" not in run_request:
        run_request["workflow_engine_parameters"] = "{}"
    if "tags" not in run_request:
        run_request["tags"] = "{}"

    tags = json.loads(run_request["tags"])
    if "workflow_name" in tags:
        run_request["workflow_name"] = tags["workflow_name"]

    if current_app.config["WORKFLOW_ATTACHMENT"]:
        workflow_attachment = \
            files.getlist("workflow_attachment[]")  # type: ignore
        exe_dir: Path = get_path(run_id, "exe_dir")
        for f in workflow_attachment:
            file_name: str = secure_filename(f.filename)
            file_url: Path = exe_dir.joinpath(file_name).resolve()
            run_request["workflow_attachment"].append({
                "file_name": file_name,
                "file_url": str(file_url)
            })

    validate_wf_type(run_request["workflow_type"],
                     run_request["workflow_type_version"])

    return run_request


def prepare_run_dir(run_id: str, run_request: RunRequest,  # type: ignore
                    files: Dict[str, FileStorage]) -> RunRequest:
    run_dir: Path = get_run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    exe_dir: Path = get_path(run_id, "exe_dir")
    exe_dir.mkdir(parents=True, exist_ok=True)
    exe_dir.chmod(0o777)
    outputs_dir: Path = get_path(run_id, "outputs_dir")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.chmod(0o777)

    write_file(run_id, "run_request", json.dumps(run_request, indent=2))
    write_file(run_id, "wf_params", run_request["workflow_params"])
    write_file(run_id, "wf_engine_params",
               generate_wf_engine_params_str(run_request))

    write_workflow_attachment(run_id, run_request, files)


def generate_wf_engine_params_str(run_request: RunRequest) -> str:
    params: List[str] = []
    default_wf_engine_params: List[DefaultWorkflowEngineParameter] = \
        generate_service_info()["default_workflow_engine_parameters"]
    for param in default_wf_engine_params:
        params.append(str(param.get("name", "")))
        params.append(str(param.get("default_value", "")))
    wf_engine_params = json.loads(run_request["workflow_engine_parameters"])
    for key, val in wf_engine_params.items():
        params.append(str(key))
        params.append(str(val))
    joined_params: str = " ".join(params)

    return joined_params


def write_workflow_attachment(run_id: str, run_request: RunRequest,
                              files: Dict[str, FileStorage]) -> None:
    exe_dir: Path = get_path(run_id, "exe_dir")

    file_path: Path
    if current_app.config["REGISTERED_ONLY_MODE"]:
        wf: Workflow = get_workflow(run_request["workflow_name"])
        for file in wf["workflow_attachment"]:
            file_path = \
                exe_dir.joinpath(secure_filename(file["file_name"])).resolve()
            response: Response = requests.get(file["file_url"])
            with file_path.open(mode="wb") as f:
                f.write(response.content)

    if current_app.config["WORKFLOW_ATTACHMENT"]:
        workflow_attachment = \
            files.getlist("workflow_attachment[]")  # type: ignore
        for file in workflow_attachment:
            file_name = secure_filename(file.filename)   # type: ignore
            file_path = exe_dir.joinpath(file_name).resolve()
            file.save(file_path)  # type: ignore


def fork_run(run_id: str) -> None:
    run_dir: Path = get_run_dir(run_id)
    stdout: Path = get_path(run_id, "stdout")
    stderr: Path = get_path(run_id, "stderr")
    cmd: str = f"/bin/bash {current_app.config['RUN_SH']} {run_dir}"
    write_file(run_id, "state", State.QUEUED.name)
    with stdout.open(mode="w") as f_stdout, stderr.open(mode="w") as f_stderr:
        process = Popen(shlex.split(cmd), stdout=f_stdout, stderr=f_stderr)
    pid: Optional[int] = process.pid
    if pid is not None:
        write_file(run_id, "pid", str(pid))


def validate_run_id(run_id: str) -> None:
    all_run_ids: List[str] = get_all_run_ids()
    if run_id not in all_run_ids:
        abort(404,
              f"The run_id {run_id} you requested does not exist, "
              "please check with GET /runs.")


def get_run_log(run_id: str) -> RunLog:
    run_log: RunLog = {
        "run_id": run_id,
        "request": read_file(run_id, "run_request"),
        "state": get_state(run_id).name,  # type: ignore
        "run_log": get_log(run_id),
        "task_logs": read_file(run_id, "task_logs"),
        "outputs": read_file(run_id, "outputs")
    }

    return run_log


def get_log(run_id: str) -> Log:
    exit_code: Optional[Union[str, int]] = read_file(run_id, "exit_code")
    if exit_code is not None:
        try:
            exit_code = int(exit_code)
        except Exception:
            pass
    log: Log = {
        "name": read_file(run_id, "run_request")["workflow_name"],
        "cmd": read_file(run_id, "cmd"),
        "start_time": read_file(run_id, "start_time"),
        "end_time": read_file(run_id, "end_time"),
        "stdout": read_file(run_id, "stdout"),
        "stderr": read_file(run_id, "stderr"),
        "exit_code": exit_code  # type: ignore
    }

    return log


def cancel_run(run_id: str) -> None:
    state: State = get_state(run_id)
    if state == State.RUNNING:
        write_file(run_id, "state", State.CANCELING.name)
        pid: int = int(read_file(run_id, "pid"))
        os.kill(pid, signal.SIGUSR1)
