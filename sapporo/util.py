#!/usr/bin/env python3
# coding: utf-8
import collections
import json
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from flask import current_app

from sapporo.const import RUN_DIR_STRUCTURE
from sapporo.type import ServiceInfo, State, Workflow


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
    service_info["tags"]["registered_only_mode"] = \
        current_app.config["REGISTERED_ONLY_MODE"]
    if current_app.config["REGISTERED_ONLY_MODE"]:
        service_info["workflows"] = get_workflows()

    return service_info


def generate_run_id() -> str:
    return str(uuid4())


def get_run_dir(run_id: str, run_base_dir: Optional[Path] = None) -> Path:
    if run_base_dir is None:
        run_base_dir = current_app.config["RUN_DIR"]

    return run_base_dir.joinpath(run_id[:2]).joinpath(run_id).resolve()


def get_path(run_id: str, key: str,
             run_base_dir: Optional[Path] = None) -> Path:
    run_dir: Path = get_run_dir(run_id, run_base_dir)

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


def get_workflows() -> List[Workflow]:
    workflows: List[Workflow]
    # with WORKFLOWS.open(mode="r") as f:
    #     workflows = json.load(f)

    workflows = []  # TODO fix

    return workflows
