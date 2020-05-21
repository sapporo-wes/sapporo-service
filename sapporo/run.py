#!/usr/bin/env python3
# coding: utf-8
import json
import os
import shlex
import signal
from pathlib import Path
from subprocess import Popen
from typing import Dict, List, Optional, Union

import requests
from flask import abort, current_app
from requests import Response
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from sapporo.type import Log, RunLog, RunRequest, ServiceInfo, State, Workflow
from sapporo.util import (generate_service_info, get_all_run_ids, get_path,
                          get_run_dir, get_state, get_workflow, read_file,
                          write_file)


def validate_run_request(run_request: RunRequest) -> None:
    required_fields: List[str] = ["workflow_params",
                                  "workflow_type",
                                  "workflow_type_version",
                                  "workflow_url",
                                  "workflow_engine_name"]
    for field in required_fields:
        if field not in run_request:
            abort(400,
                  f"{field} not included in the form data of the request.")


def update_and_validate_registered_only_mode(run_request: RunRequest) \
        -> RunRequest:
    if "workflow_name" not in run_request:
        abort(400,
              "Currently, Sapporo is running with " +
              "registered_only_mode. Therefore, you need to run " +
              "the workflow with the workflow_name.")
    wf: Workflow = get_workflow(run_request["workflow_name"])
    run_request["workflow_url"] = wf["workflow_url"]
    run_request["workflow_type"] = wf["workflow_type"]
    run_request["workflow_type_version"] = \
        wf["workflow_type_version"]
    run_request["workflow_attachment"] = \
        wf["workflow_attachment"]

    return run_request


def validate_wf_type(wf_type: str, wf_type_version: str) -> None:
    service_info: ServiceInfo = generate_service_info()
    wf_type_versions = service_info["workflow_type_versions"]

    available_wf_types: List[str] = \
        list(map(str, wf_type_versions.keys()))
    if wf_type not in available_wf_types:
        abort(400,
              f"{wf_type}, the workflow_type specified in the " +
              f"request, is not included in {available_wf_types}, " +
              "the available workflow_types.")

    available_wf_versions: List[str] = \
        list(map(str, wf_type_versions[wf_type]["workflow_type_version"]))
    if wf_type_version not in available_wf_versions:
        abort(400,
              f"{wf_type_version}, the workflow_type_version specified in " +
              f"the request, is not included in {available_wf_versions}, " +
              "the available workflow_type_versions.")


def prepare_exe_dir(run_id: str,
                    request_files: Dict[str, FileStorage]) -> None:
    exe_dir: Path = get_path(run_id, "exe_dir")
    exe_dir.mkdir(parents=True, exist_ok=True)
    run_request: RunRequest = read_file(run_id, "run_request")
    if current_app.config["REGISTERED_ONLY_MODE"]:
        for attached_file in run_request["workflow_attachment"]:
            file_name: str = secure_filename(attached_file["file_name"])
            file_path: Path = exe_dir.joinpath(file_name).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            response: Response = requests.get(attached_file["file_url"])
            with file_path.open(mode="wb") as f:
                f.write(response.content)
    if "workflow_attachment" not in run_request:
        run_request["workflow_attachment"] = []
    if current_app.config["WORKFLOW_ATTACHMENT"]:
        for file in request_files.values():
            if file.filename != "":
                file_name = secure_filename(file.filename)
                run_request["workflow_attachment"].append({
                    "file_name": file_name,
                    "file_url": ""
                })
                file_path = exe_dir.joinpath(file_name).resolve()
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file.save(file_path)  # type: ignore

    write_file(run_id, "run_request", json.dumps(run_request, indent=2))


def fork_run(run_id: str) -> None:
    run_dir: Path = get_run_dir(run_id)
    stdout: Path = get_path(run_id, "stdout")
    stderr: Path = get_path(run_id, "stderr")
    cmd: str = f"/bin/bash {current_app.config['RUN_SH']} {run_dir}"
    with stdout.open(mode="w") as f_stdout, stderr.open(mode="w") as f_stderr:
        process = Popen(shlex.split(cmd), stdout=f_stdout, stderr=f_stderr)
    pid: Optional[int] = process.pid
    if pid is not None:
        write_file(run_id, "pid", str(pid))


def validate_run_id(run_id: str) -> None:
    all_run_ids: List[str] = get_all_run_ids()
    if run_id not in all_run_ids:
        abort(404,
              f"The run_id {run_id} you requested does not exist, " +
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
        "name": None,  # type: ignore
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
