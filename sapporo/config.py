import logging
import os
import sys
from argparse import ArgumentParser, Namespace
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from fastapi import FastAPI
from pydantic import BaseModel

from sapporo.utils import inside_docker, str2bool

PKG_DIR = Path(__file__).resolve().parent


GA4GH_WES_SPEC_PATH = PKG_DIR.joinpath("ga4gh-wes-spec-1.1.0.yml")
GA4GH_WES_SPEC: Dict[str, Any] = yaml.safe_load(GA4GH_WES_SPEC_PATH.read_text(encoding="utf-8"))


# === Global configuration ===


class AppConfig(BaseModel):
    host: str = "0.0.0.0" if inside_docker() else "127.0.0.1"
    port: int = 1122
    debug: bool = False
    run_dir: Path = Path.cwd().joinpath("runs")
    service_info: Path = PKG_DIR.joinpath("service_info.json")
    executable_workflows: Path = PKG_DIR.joinpath("executable_workflows.json")
    run_sh: Path = PKG_DIR.joinpath("run.sh")
    url_prefix: str = ""
    base_url: str = f"http://{'0.0.0.0' if inside_docker() else '127.0.0.1'}:1122"
    allow_origin: str = "*"
    auth_config: Path = PKG_DIR.joinpath("auth_config.json")
    run_remove_older_than_days: Optional[int] = None


default_config = AppConfig()


def parse_args(args: Optional[List[str]] = None) -> Namespace:
    parser = ArgumentParser(
        description="The sapporo-service is a standard implementation conforming to the Global Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API specification.",
    )

    parser.add_argument(
        "--host",
        type=str,
        metavar="",
        help="Host address for the service. (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        metavar="",
        help="Port number for the service. (default: 1122)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode."
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        metavar="",
        help="Directory where the runs are stored. (default: ./runs)"
    )
    parser.add_argument(
        "--service-info",
        type=Path,
        metavar="",
        help="Path to the service_info.json file."
    )
    parser.add_argument(
        "--executable-workflows",
        type=Path,
        metavar="",
        help="Path to the executable_workflows.json file."
    )
    parser.add_argument(
        "--run-sh",
        type=Path,
        metavar="",
        help="Path to the run.sh script."
    )
    parser.add_argument(
        "--url-prefix",
        type=str,
        metavar="",
        help="URL prefix for the service endpoints. (default: '', e.g., /sapporo/api)"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        metavar="",
        help="Base URL for downloading the output files of the executed runs. The files can be downloaded using the format: {base_url}/runs/{run_id}/outputs/{path}. (default: http://{host}:{port}{url_prefix})"
    )
    parser.add_argument(
        "--allow-origin",
        type=str,
        metavar="",
        help="Access-Control-Allow-Origin header value. (default: *)"
    )
    parser.add_argument(
        "--auth-config",
        type=Path,
        metavar="",
        help="Path to the auth_config.json file."
    )
    parser.add_argument(
        "--run-remove-older-than-days",
        type=int,
        metavar="",
        help="Clean up run directories with a start time older than the specified number of days."
    )

    return parser.parse_args(args)


@lru_cache(maxsize=None)
def get_config() -> AppConfig:
    """
    Get the configuration for the application.

    This function initializes and returns the configuration used throughout the application.
    The initial state is cached using `lru_cache` to ensure that the configuration is only loaded once when the application starts.
    This state depends on `os.environ` and `sys.argv`, but passing them as arguments is not necessary as the primary goal is to cache the initial values.

    Parameter priority:

    1. Command line arguments
    2. Environment variables
    3. Default values
    """
    args = parse_args(sys.argv[1:])

    host = args.host or os.environ.get("SAPPORO_HOST", default_config.host)
    port = args.port or int(os.environ.get("SAPPORO_PORT", default_config.port))
    url_prefix = args.url_prefix or os.environ.get("SAPPORO_URL_PREFIX", default_config.url_prefix)
    base_url = args.base_url or os.environ.get("SAPPORO_BASE_URL", f"http://{host}:{port}{url_prefix}")

    run_remove_older_than_days = args.run_remove_older_than_days or os.environ.get(
        "SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS", default_config.run_remove_older_than_days)
    if run_remove_older_than_days is not None:
        run_remove_older_than_days = int(run_remove_older_than_days)
        if run_remove_older_than_days < 1:
            raise ValueError("The value of --run-remove-older-than-days (SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS) must be greater than or equal to 1.")

    return AppConfig(
        host=host,
        port=port,
        debug=args.debug or str2bool(os.environ.get("SAPPORO_DEBUG", default_config.debug)),
        run_dir=args.run_dir or Path(os.environ.get("SAPPORO_RUN_DIR", default_config.run_dir)),
        service_info=args.service_info or Path(os.environ.get("SAPPORO_SERVICE_INFO", default_config.service_info)),
        executable_workflows=args.executable_workflows or Path(os.environ.get("SAPPORO_EXECUTABLE_WORKFLOWS", default_config.executable_workflows)),
        run_sh=args.run_sh or Path(os.environ.get("SAPPORO_RUN_SH", default_config.run_sh)),
        url_prefix=url_prefix,
        base_url=base_url,
        allow_origin=args.allow_origin or os.environ.get("SAPPORO_ALLOW_ORIGIN", default_config.allow_origin),
        auth_config=args.auth_config or Path(os.environ.get("SAPPORO_AUTH_CONFIG", default_config.auth_config)),
        run_remove_older_than_days=run_remove_older_than_days,
    )


# === Logging ===


# Ref.: https://github.com/encode/uvicorn/blob/master/uvicorn/config.py
def logging_config(debug: bool = False) -> Dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": True,
            },
            "sqlalchemy": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s DB - %(message)s",
                "use_colors": True,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "sqlalchemy": {
                "formatter": "sqlalchemy",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "sapporo": {
                "handlers": ["default"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False
            },
            "sqlalchemy.engine": {
                "handlers": ["sqlalchemy"],
                "level": "INFO" if debug else "WARNING",
                "propagate": False
            },
        }
    }


LOGGER = logging.getLogger("sapporo")


# === Const ===


RUN_DIR_STRUCTURE: Dict[str, str] = {
    "runtime_info": "runtime_info.json",
    "run_request": "run_request.json",
    "state": "state.txt",
    "exe_dir": "exe",
    "outputs_dir": "outputs",
    "outputs": "outputs.json",
    "wf_params": "exe/workflow_params.json",
    "start_time": "start_time.txt",
    "end_time": "end_time.txt",
    "exit_code": "exit_code.txt",
    "stdout": "stdout.log",
    "stderr": "stderr.log",
    "pid": "run.pid",
    "wf_engine_params": "workflow_engine_params.txt",
    "cmd": "cmd.txt",
    "system_logs": "system_logs.json",
    "username": "username.txt",
    "ro_crate": "ro-crate-metadata.json",
}


RunDirStructureKeys = Literal[
    "runtime_info",
    "run_request",
    "state",
    "exe_dir",
    "outputs_dir",
    "outputs",
    "wf_params",
    "start_time",
    "end_time",
    "exit_code",
    "stdout",
    "stderr",
    "pid",
    "wf_engine_params",
    "cmd",
    "system_logs",
    "username",
    "ro_crate",
]


# === API Spec ===


API_DESCRIPTION = """\
*Run standard workflows on workflow execution platforms in a platform-agnostic way.*

## Executive Summary

The Workflow Execution Service (WES) API provides a standard way for users to submit workflow requests to workflow execution systems and monitor their execution. This API lets users run a single workflow (currently [**CWL**](https://www.commonwl.org/) or [**WDL**](http://www.openwdl.org/) formatted workflows, with other types potentially supported in the future) on multiple different platforms, clouds, and environments.

Key features of the API:

- Request that a workflow be run.
- Pass parameters to that workflow (e.g., input files, command-line arguments).
- Get information about running workflows (e.g., status, errors, output file locations).
- Cancel a running workflow.

## Sapporo-WES Extensions

`sapporo-wes-2.0.0` extends the original WES API to provide enhanced functionality and support for additional features. This document describes the WES API and details the specific endpoints, request formats, and responses, aimed at developers of WES-compatible services and clients.
"""


def add_openapi_info(app: FastAPI) -> None:
    app.title = "GA4GH Workflow Execution Service API specification extended for the Sapporo"
    app.version = "2.0.0"
    app.description = API_DESCRIPTION
    app.servers = [{"url": get_config().base_url}]
    app.license_info = {
        "name": "Apache 2.0",
        "identifier": "Apache-2.0",
        "url": "https://github.com/sapporo-wes/sapporo-service/blob/main/LICENSE",
    }
    app.contact = {
        "name": "Sapporo-WES Project Team",
        "url": "https://github.com/sapporo-wes/sapporo-service/issues",
    }


def dump_openapi_schema(app: FastAPI) -> str:
    return yaml.dump(app.openapi())


if __name__ == "__main__":
    from sapporo.app import create_app
    f_app = create_app()
    with PKG_DIR.joinpath("../sapporo-wes-spec-2.0.0.yml").open("w", encoding="utf-8") as f:
        f.write(dump_openapi_schema(f_app))
