#!/usr/bin/env python3
# coding: utf-8
import argparse
import json
import os
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from traceback import format_exc
from typing import Dict, List, Optional, Union

from flask import Flask, Response, current_app, jsonify
from jsonschema import validate
from werkzeug.exceptions import HTTPException

from sapporo.const import (DEFAULT_ACCESS_CONTROL_ALLOW_ORIGIN,
                           DEFAULT_EXECUTABLE_WORKFLOWS, DEFAULT_HOST,
                           DEFAULT_PORT, DEFAULT_RUN_DIR, DEFAULT_RUN_SH,
                           DEFAULT_SERVICE_INFO, DEFAULT_URL_PREFIX,
                           EXECUTABLE_WORKFLOWS_SCHEMA, SERVICE_INFO_SCHEMA)
from sapporo.controller import app_bp
from sapporo.type import ErrorResponse, Workflow
from sapporo.util import str2bool


def parse_args(sys_args: List[str]) -> Namespace:
    parser: ArgumentParser = argparse.ArgumentParser(
        description="Implementation of a GA4GH workflow execution service "
                    "that can easily support various workflow runners.")

    parser.add_argument(
        "--host",
        nargs=1,
        metavar="",
        help=f"Host address of Flask. (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        nargs=1,
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
        nargs=1,
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
        help="Run only registered workflows. Check the registered "
             "workflows using `GET /service-info`, and specify "
             "`workflow_name` in the `POST /run`."
    )
    parser.add_argument(
        "--service-info",
        nargs=1,
        metavar="",
        help="Specify `service-info.json`. The supported_wes_versions, "
             "system_state_counts and workflows are overwritten in the "
             "application."
    )
    parser.add_argument(
        "--executable-workflows",
        nargs=1,
        metavar="",
        help="Specify `executable-workflows.json`."
    )
    parser.add_argument(
        "--run-sh",
        nargs=1,
        metavar="",
        help="Specify `run.sh`."
    )
    parser.add_argument(
        "--url-prefix",
        nargs=1,
        metavar="",
        help="Specify the prefix of the url (e.g. --url-prefix /foo -> "
        "/foo/service-info)."
    )

    args: Namespace = parser.parse_args(sys_args)

    return args


def handle_default_params(args: Namespace) -> Dict[str, Union[str, int, Path]]:
    params: Dict[str, Union[str, int, Path]] = {
        "host": handle_default_host(args.host),
        "port": handle_default_port(args.port),
        "debug": handle_default_debug(args.debug),
        "run_dir": handle_default_path(args.run_dir,
                                       "SAPPORO_RUN_DIR",
                                       DEFAULT_RUN_DIR),
        "get_runs": handle_default_get_runs(args.disable_get_runs),
        "workflow_attachment":
            handle_default_workflow_attachment(
                args.disable_workflow_attachment),
        "registered_only_mode":
            handle_default_registered_only_mode(
                args.run_only_registered_workflows),
        "service_info": handle_default_path(args.service_info,
                                            "SAPPORO_SERVICE_INFO",
                                            DEFAULT_SERVICE_INFO),
        "executable_workflows":
            handle_default_path(args.executable_workflows,
                                "SAPPORO_EXECUTABLE_WORKFLOWS",
                                DEFAULT_EXECUTABLE_WORKFLOWS),
        "run_sh": handle_default_path(args.run_sh,
                                      "SAPPORO_RUN_SH",
                                      DEFAULT_RUN_SH),
        "url_prefix": handle_default_url_prefix(args.url_prefix)
    }

    return params


def handle_default_host(host: Optional[List[str]]) -> str:
    if host is None:
        return os.environ.get("SAPPORO_HOST", DEFAULT_HOST)

    return host[0]


def handle_default_port(port: Optional[List[str]]) -> int:
    if port is None:
        return int(os.environ.get("SAPPORO_PORT", DEFAULT_PORT))

    return int(port[0])


def handle_default_debug(debug: bool) -> bool:
    if debug is False:
        return str2bool(os.environ.get("SAPPORO_DEBUG", False))

    return True


def handle_default_path(input_arg: Optional[List[str]], env_var: str,
                        default_val: Path) -> Path:
    handled_path: Path
    if input_arg is None:
        handled_path = Path(os.environ.get(env_var, default_val))
    else:
        handled_path = Path(input_arg[0])
    if not handled_path.is_absolute():
        handled_path = Path.cwd().joinpath(handled_path).resolve()

    return handled_path


def handle_default_get_runs(disable_get_runs: bool) -> bool:
    if disable_get_runs:
        return False
    else:
        return str2bool(os.environ.get("SAPPORO_GET_RUNS", True))


def handle_default_workflow_attachment(disable_workflow_attachment: bool) \
        -> bool:
    if disable_workflow_attachment:
        return False
    else:
        return str2bool(os.environ.get("SAPPORO_WORKFLOW_ATTACHMENT", True))


def handle_default_registered_only_mode(run_only_registered_workflows: bool) \
        -> bool:
    if run_only_registered_workflows is False:
        return str2bool(os.environ.get("SAPPORO_RUN_ONLY_REGISTERED_WORKFLOWS",
                                       False))

    return True


def handle_default_url_prefix(url_prefix: Optional[List[str]]) -> str:
    if url_prefix is None:
        return os.environ.get("SAPPORO_URL_PREFIX", DEFAULT_URL_PREFIX)

    return url_prefix[0]


def check_uniqueness_wf_name(executable_wf_path: Path) -> None:
    with executable_wf_path.open(mode="r") as f:
        executable_wfs: List[Workflow] = json.load(f)
    wf_names: List[str] = [wf["workflow_name"] for wf in executable_wfs]
    if len(wf_names) != len(set(wf_names)):
        raise Exception(
            "`workflow_name` is not unique in the "
            f"`executable_workflows.json`: {executable_wf_path} you inputted.")


def validate_json(service_info: Path, executable_wf: Path) -> None:
    pairs: List[List[Path]] = [
        [service_info, SERVICE_INFO_SCHEMA],
        [executable_wf, EXECUTABLE_WORKFLOWS_SCHEMA]
    ]
    for data, schema in pairs:
        with data.open(mode="r") as f_d, schema.open(mode="r") as f_s:
            validate(json.load(f_d), json.load(f_s))


def fix_errorhandler(app: Flask) -> Flask:
    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def error_handler(error: HTTPException) -> Response:
        res_body: ErrorResponse = {
            "msg": error.description,  # type: ignore
            "status_code": error.code,  # type: ignore
        }
        response: Response = jsonify(res_body)
        response.status_code = error.code  # type: ignore
        return response

    @app.errorhandler(Exception)
    def error_handler_exception(exception: Exception) -> Response:
        current_app.logger.error(exception.args[0])
        current_app.logger.debug(format_exc())
        res_body: ErrorResponse = {
            "msg": "The server encountered an internal error and was "
                   "unable to complete your request.",
            "status_code": 500,
        }
        if current_app.config["TESTING"]:
            res_body["msg"] = format_exc()
        response: Response = jsonify(res_body)
        response.status_code = 500
        return response

    return app


def add_after_request(app: Flask) -> Flask:
    @app.after_request
    def after_request_func(response: Response) -> Response:
        response.headers["Access-Control-Allow-Origin"] = \
            os.environ.get("SAPPORO_ACCESS_CONTROL_ALLOW_ORIGIN",
                           DEFAULT_ACCESS_CONTROL_ALLOW_ORIGIN)
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"

        return response

    return app


def create_app(params: Dict[str, Union[str, int, Path]]) -> Flask:
    app = Flask(__name__)
    app.register_blueprint(app_bp, url_prefix=params["url_prefix"])
    fix_errorhandler(app)
    add_after_request(app)
    app.config["RUN_DIR"] = params["run_dir"]
    app.config["GET_RUNS"] = params["get_runs"]
    app.config["WORKFLOW_ATTACHMENT"] = params["workflow_attachment"]
    app.config["REGISTERED_ONLY_MODE"] = params["registered_only_mode"]
    app.config["SERVICE_INFO"] = params["service_info"]
    app.config["EXECUTABLE_WORKFLOWS"] = params["executable_workflows"]
    app.config["RUN_SH"] = params["run_sh"]
    app.config["URL_PREFIX"] = params["url_prefix"]
    validate_json(app.config["SERVICE_INFO"],
                  app.config["EXECUTABLE_WORKFLOWS"])
    check_uniqueness_wf_name(app.config["EXECUTABLE_WORKFLOWS"])

    return app


def main() -> None:
    args: Namespace = parse_args(sys.argv[1:])
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)
    app.run(
        host=params["host"],  # type: ignore
        port=params["port"],  # type: ignore
        debug=params["debug"]  # type: ignore
    )


if __name__ == "__main__":
    main()
