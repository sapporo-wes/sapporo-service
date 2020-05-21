#!/usr/bin/env python3
# coding: utf-8
import collections
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, cast
from uuid import uuid4

from flask import abort, current_app

from sapporo.const import RUN_DIR_STRUCTURE
from sapporo.type import (DefaultWorkflowEngineParameter, RunRequest,
                          ServiceInfo, State, Workflow)


def generate_service_info() -> ServiceInfo:
    with current_app.config["SERVICE_INFO"].open(mode="r") as f:
        service_info: ServiceInfo = json.load(f)

    if current_app.config["REGISTERED_ONLY_MODE"]:
        service_info["supported_wes_versions"] = ["sapporo-wes-1.1"]
    else:
        service_info["supported_wes_versions"] = ["1.0.0"]
    service_info["system_state_counts"] = count_system_state()  # type: ignore
    service_info["tags"]["debug"] = current_app.config["DEBUG"]
    service_info["tags"]["run_dir"] = str(current_app.config["RUN_DIR"])
    service_info["tags"]["get_runs"] = current_app.config["GET_RUNS"]
    service_info["tags"]["workflow_attachment"] = \
        current_app.config["WORKFLOW_ATTACHMENT"]
    service_info["tags"]["registered_only_mode"] = \
        current_app.config["REGISTERED_ONLY_MODE"]

    if current_app.config["REGISTERED_ONLY_MODE"]:
        with current_app.config["EXECUTABLE_WORKFLOWS"].open(mode="r") as f:
            executable_workflows: List[Workflow] = json.load(f)
        service_info["executable_workflows"] = executable_workflows

    return service_info


def generate_run_id() -> str:
    return str(uuid4())


def get_run_dir(run_id: str) -> Path:
    run_base_dir: Path = current_app.config["RUN_DIR"]

    return run_base_dir.joinpath(run_id[:2]).joinpath(run_id).resolve()


def get_path(run_id: str, key: str) -> Path:
    run_dir: Path = get_run_dir(run_id)

    return run_dir.joinpath(RUN_DIR_STRUCTURE[key])


def get_all_run_ids() -> List[str]:
    run_base_dir: Path = current_app.config["RUN_DIR"]
    run_requests: List[Path] = \
        list(run_base_dir.glob(f"**/{RUN_DIR_STRUCTURE['run_request']}"))
    run_ids: List[str] = \
        [run_request.parent.name for run_request in run_requests]

    return run_ids


def get_state(run_id: str) -> State:
    try:
        with get_path(run_id, "state").open(mode="r") as f:
            str_state: str = \
                [line for line in f.read().splitlines() if line != ""][0]
        return State[str_state]
    except Exception:
        return State.UNKNOWN


def count_system_state() -> Dict[str, int]:
    run_ids: List[str] = get_all_run_ids()
    count: Dict[str, int] = \
        dict(collections.Counter(
            [get_state(run_id).name for run_id in run_ids]))

    return count


def write_file(run_id: str, file_type: str, content: str) -> None:
    file: Path = get_path(run_id, file_type)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open(mode="w") as f:
        f.write(content)


def read_file(run_id: str, file_type: str) -> Any:
    file: Path = get_path(run_id, file_type)
    if file.exists() is False:
        return None
    with file.open(mode="r") as f:
        if file_type in ["cmd", "start_time", "end_time", "exit_code"]:
            return f.read().splitlines()[0]
        elif file_type in ["stdout", "stderr"]:
            return f.read()
        elif file_type in ["run_request", "outputs", "task_logs"]:
            return json.load(f)
        else:
            return f.read()


def dump_wf_engine_params(run_id: str) -> None:
    run_request: RunRequest = \
        cast(RunRequest, read_file(run_id, "run_request"))
    wf_engine_params_obj = \
        json.loads(run_request["workflow_engine_parameters"])
    params: List[str] = []
    for key, val in wf_engine_params_obj.items():
        params.append(key)
        if isinstance(val, list):
            params.append(",".join(val))
        else:
            params.append(str(val))
    joined_params: str = " ".join(params)
    write_file(run_id, "wf_engine_params", joined_params)


def dump_outputs_list(inputted_run_dir: str) -> None:
    run_dir: Path = Path(inputted_run_dir).resolve()
    outdir_path: Path = run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"])
    output_files: List[Path] = sorted(list(walk_all_files(outdir_path)))
    outputs: Dict[str, str] = {}
    for output_file in output_files:
        outputs[str(output_file.relative_to(outdir_path))] = str(output_file)
    with run_dir.joinpath(RUN_DIR_STRUCTURE["outputs"]).open(mode="w") as f:
        f.write(json.dumps(outputs, indent=2))


def walk_all_files(dir: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(dir):
        for file in files:
            yield Path(root).joinpath(file)


def generate_default_wf_engine_params(run_id: str) -> List[str]:
    default_wf_engine_params: List[DefaultWorkflowEngineParameter] = \
        generate_service_info()["default_workflow_engine_parameters"]
    params: List[str] = []
    for param in default_wf_engine_params:
        params.append(str(param.get("name", "")))
        params.append(str(param.get("default_value", "")))

    return params


def get_workflow(workflow_name: str) -> Workflow:
    with current_app.config["EXECUTABLE_WORKFLOWS"].open(mode="r") as f:
        executable_workflows: List[Workflow] = json.load(f)
    for wf in executable_workflows:
        if wf["workflow_name"] == workflow_name:
            return wf

    abort(404,
          f"The workflow_name: {workflow_name} you requested doesn't " +
          "exist. Please request `GET /service-info` again and check " +
          "the registered executable workflows.")
