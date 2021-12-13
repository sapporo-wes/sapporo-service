#!/usr/bin/env python3
# coding: utf-8
import json
from typing import List

from flask import current_app

from sapporo.model import (Log, RunId, RunListResponse, RunLog, RunStatus,
                           ServiceInfo, Workflow)
from sapporo.run import (count_system_state, glob_all_run_ids, read_file,
                         read_state)


def generate_service_info() -> ServiceInfo:
    with current_app.config["SERVICE_INFO"].open(mode="r", encoding="utf-8") as f:
        service_info: ServiceInfo = json.load(f)

    service_info["supported_wes_versions"] = ["sapporo-wes-1.0.1"]
    service_info["system_state_count"] = count_system_state()
    service_info["tags"]["get_runs"] = current_app.config["GET_RUNS"]
    service_info["tags"]["workflow_attachment"] = current_app.config["WORKFLOW_ATTACHMENT"]
    service_info["tags"]["registered_only_mode"] = current_app.config["REGISTERED_ONLY_MODE"]

    return service_info


def generate_executable_workflows() -> List[Workflow]:
    with current_app.config["EXECUTABLE_WORKFLOWS"].open(mode="r", encoding="utf-8") as f:
        executable_workflows: List[Workflow] = json.load(f)

    return executable_workflows


def generate_run_status(run_id: str) -> RunStatus:
    return {
        "run_id": run_id,
        "state": read_state(run_id)
    }


def generate_run_list() -> RunListResponse:
    all_run_ids = glob_all_run_ids()
    runs: List[RunStatus] = [generate_run_status(
        run_id) for run_id in all_run_ids]

    return {
        "runs": runs,
        "next_page_token": ""
    }


def generate_run_log(run_id: str) -> RunLog:
    run_log: RunLog = {
        "run_id": run_id,
        "request": read_file(run_id, "run_request"),
        "state": read_state(run_id),
        "run_log": generate_log(run_id),
        "task_logs": read_file(run_id, "task_logs"),
        "outputs": read_file(run_id, "outputs")
    }

    return run_log


def generate_log(run_id: str) -> Log:
    log: Log = {
        "name": read_file(run_id, "run_request")["workflow_name"],
        "cmd": read_file(run_id, "cmd"),
        "start_time": read_file(run_id, "start_time"),
        "end_time": read_file(run_id, "end_time"),
        "stdout": read_file(run_id, "stdout"),
        "stderr": read_file(run_id, "stderr"),
        "exit_code": read_file(run_id, "exit_code")
    }

    return log


def generate_run_id(run_id: str) -> RunId:
    return {
        "run_id": run_id
    }
