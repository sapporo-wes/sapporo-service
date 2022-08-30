#!/usr/bin/env python3
# coding: utf-8
import argparse
import json
import os
from argparse import ArgumentParser, Namespace
from pathlib import Path
from sys import version_info
from typing import List, Optional, Tuple, Union, cast

import pkg_resources
from jsonschema import validate

from sapporo.const import (DEFAULT_ACCESS_CONTROL_ALLOW_ORIGIN,
                           DEFAULT_EXECUTABLE_WORKFLOWS, DEFAULT_HOST,
                           DEFAULT_PORT, DEFAULT_RUN_DIR, DEFAULT_RUN_SH,
                           DEFAULT_SERVICE_INFO, DEFAULT_URL_PREFIX,
                           EXECUTABLE_WORKFLOWS_SCHEMA, SERVICE_INFO_SCHEMA)
from sapporo.model import Workflow

if version_info.minor < 8:
    from typing_extensions import TypedDict
else:
    from typing import TypedDict


def str2bool(val: Union[str, bool]) -> bool:
    if isinstance(val, bool):
        return val
    if val.lower() in ["true", "yes", "y"]:
        return True
    if val.lower() in ["false", "no", "n"]:
        return False

    return bool(val)


class TypedNamespace(Namespace):
    host: Optional[str]
    port: Optional[int]
    debug: bool
    run_dir: Optional[Path]
    disable_get_runs: bool
    disable_workflow_attachment: bool
    run_only_registered_workflows: bool
    service_info: Optional[Path]
    executable_workflows: Optional[Path]
    run_sh: Optional[Path]
    url_prefix: Optional[str]


def parse_args(args: Optional[List[str]] = None) -> TypedNamespace:
    parser: ArgumentParser = argparse.ArgumentParser(
        description="Implementation of a GA4GH workflow execution service that can easily support various workflow runners.")

    parser.add_argument(
        "--host",
        metavar="",
        help=f"Host address of Flask. (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        metavar="",
        help=f"Port of Flask. (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode of Flask."
    )
    parser.add_argument(
        "-r",
        "--run-dir",
        type=Path,
        metavar="",
        help="Specify the run dir. (default: ./run)"
    )
    parser.add_argument(
        "--disable-get-runs",
        action="store_true",
        help="Disable endpoint of `GET /runs`."
    )
    parser.add_argument(
        "--disable-workflow-attachment",
        action="store_true",
        help="Disable `workflow_attachment` on endpoint `Post /runs`."
    )
    parser.add_argument(
        "--run-only-registered-workflows",
        action="store_true",
        help="Run only registered workflows. Check the registered workflows using `GET /executable-workflows`, and specify `workflow_name` in the `POST /run`."
    )
    parser.add_argument(
        "--service-info",
        type=Path,
        metavar="",
        help="Specify `service-info.json`. The `supported_wes_versions` and `system_state_counts` are overwritten in the application."
    )
    parser.add_argument(
        "--executable-workflows",
        type=Path,
        metavar="",
        help="Specify `executable-workflows.json`."
    )
    parser.add_argument(
        "--run-sh",
        type=Path,
        metavar="",
        help="Specify `run.sh`."
    )
    parser.add_argument(
        "--url-prefix",
        metavar="",
        help="Specify the prefix of the url (e.g. --url-prefix /foo -> /foo/service-info)."
    )

    if args is None:
        return cast(TypedNamespace, parser.parse_args())

    return cast(TypedNamespace, parser.parse_args(args))


class Config(TypedDict):
    host: str
    port: int
    debug: bool
    run_dir: Path
    sapporo_version: str
    get_runs: bool
    workflow_attachment: bool
    registered_only_mode: bool
    service_info: Path
    executable_workflows: Path
    run_sh: Path
    url_prefix: str
    access_control_allow_origin: str


def resolve_path_from_cwd(path: Union[Path, Tuple[Path]]) -> Path:
    if isinstance(path, tuple):
        path = path[0]
    if path.is_absolute():
        return path
    return path.resolve(strict=True)


def get_config(args: Optional[TypedNamespace] = None) -> Config:
    if args is None:
        args = parse_args()

    run_dir = args.run_dir or Path(os.environ.get("SAPPORO_RUN_DIR", DEFAULT_RUN_DIR))
    service_info = args.service_info or Path(os.environ.get("SAPPORO_SERVICE_INFO", DEFAULT_SERVICE_INFO))
    executable_workflows = args.executable_workflows or Path(os.environ.get("SAPPORO_EXECUTABLE_WORKFLOWS", DEFAULT_EXECUTABLE_WORKFLOWS))
    run_sh = args.run_sh or Path(os.environ.get("SAPPORO_RUN_SH", DEFAULT_RUN_SH))

    return {
        "host": args.host or str(os.environ.get("SAPPORO_HOST", DEFAULT_HOST)),
        "port": args.port or int(os.environ.get("SAPPORO_PORT", DEFAULT_PORT)),
        "debug": args.debug or str2bool(os.environ.get("SAPPORO_DEBUG", False)),
        "run_dir": resolve_path_from_cwd(run_dir),
        "sapporo_version": pkg_resources.get_distribution("sapporo").version,
        "get_runs": False if args.disable_get_runs else str2bool(os.environ.get("SAPPORO_GET_RUNS", True)),
        "workflow_attachment": False if args.disable_workflow_attachment else str2bool(os.environ.get("SAPPORO_WORKFLOW_ATTACHMENT", True)),
        "registered_only_mode": args.run_only_registered_workflows or str2bool(os.environ.get("SAPPORO_RUN_ONLY_REGISTERED_WORKFLOWS", False)),
        "service_info": resolve_path_from_cwd(service_info),
        "executable_workflows": resolve_path_from_cwd(executable_workflows),
        "run_sh": resolve_path_from_cwd(run_sh),
        "url_prefix": args.url_prefix or str(os.environ.get("SAPPORO_URL_PREFIX", DEFAULT_URL_PREFIX)),
        "access_control_allow_origin": os.environ.get("SAPPORO_ACCESS_CONTROL_ALLOW_ORIGIN", DEFAULT_ACCESS_CONTROL_ALLOW_ORIGIN)
    }


def validate_config(config: Config) -> None:
    if not config["service_info"].exists():
        raise ValueError(f"{config['service_info']} does not exist.")
    with config["service_info"].open(mode="r", encoding="utf-8") as f_data, \
            SERVICE_INFO_SCHEMA.open(mode="r", encoding="utf-8") as f_schema:
        validate(json.load(f_data), json.load(f_schema))

    if not config["executable_workflows"].exists():
        raise ValueError(f"{config['executable_workflows']} does not exist.")
    with config["executable_workflows"].open(mode="r", encoding="utf-8") as f_data, \
            EXECUTABLE_WORKFLOWS_SCHEMA.open(mode="r", encoding="utf-8") as f_schema:
        validate(json.load(f_data), json.load(f_schema))

    # Check uniqueness of workflow_name
    with config["executable_workflows"].open(mode="r", encoding="utf-8") as f_data:
        executable_wfs: List[Workflow] = json.load(f_data)["workflow"]
    wf_names: List[str] = [wf["workflow_name"] for wf in executable_wfs]
    if len(wf_names) != len(set(wf_names)):
        raise Exception(
            "The workflow name included in `executable-workflows.json` must be unique.")

    if not config["run_sh"].exists():
        raise ValueError(f"{config['run_sh']} does not exist.")
