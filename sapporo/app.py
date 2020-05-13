#!/usr/bin/env python3
# coding: utf-8
import argparse
import os
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from traceback import format_exc
from typing import Dict, List, Optional, Union

from flask import Flask, Response, current_app, jsonify
from werkzeug.exceptions import HTTPException

from sapporo.const import (DEFAULT_HOST, DEFAULT_PORT, DEFAULT_RUN_DIR,
                           DEFAULT_RUN_SH, DEFAULT_SERVICE_INFO,
                           DEFAULT_WORKFLOWS_FETCH_CONFIG)
from sapporo.controller import app_bp
from sapporo.type import ErrorResponse


def parse_args(sys_args: List[str]) -> Namespace:
    parser: ArgumentParser = argparse.ArgumentParser(
        description="Implementation of a GA4GH workflow execution " +
                    "service that can easily support various " +
                    "workflow runners.")

    parser.add_argument(
        "--host",
        type=str,
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
        type=str,
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
        "--run-only-registered-workflows",
        action="store_true",
        help="Run only registered workflows. Check the registered " +
             "workflows using `GET /service-info`, and specify " +
             "`workflow_name` in the `POST /run`."
    )
    parser.add_argument(
        "--service-info",
        type=str,
        nargs=1,
        metavar="",
        help="Specify `service-info.json`. The supported_wes_versions, " +
             "system_state_counts and workflows are overwritten in the " +
             "application."
    )
    parser.add_argument(
        "--workflows-fetch-config",
        type=str,
        nargs=1,
        metavar="",
        help="Specify `workflows-fetch-config.json`."
    )
    parser.add_argument(
        "--run-sh",
        type=str,
        nargs=1,
        metavar="",
        help="Specify `run.sh`."
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
        "registered_only_mode":
            handle_default_registered_only_mode(
                args.run_only_registered_workflows),
        "service_info": handle_default_path(args.service_info,
                                            "SAPPORO_SERVICE_INFO",
                                            DEFAULT_SERVICE_INFO),
        "workflows_fetch_config":
            handle_default_path(args.workflows_fetch_config,
                                "SAPPORO_WORKFLOWS_FETCH_CONFIG",
                                DEFAULT_WORKFLOWS_FETCH_CONFIG),
        "run_sh": handle_default_path(args.run_sh,
                                      "SAPPORO_RUN_SH",
                                      DEFAULT_RUN_SH),
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
        return bool(os.environ.get("SAPPORO_DEBUG", False))

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
        return bool(os.environ.get("SAPPORO_GET_RUNS", True))


def handle_default_registered_only_mode(run_only_registered_workflows: bool) \
        -> bool:
    if run_only_registered_workflows is False:
        return bool(os.environ.get("SAPPORO_RUN_ONLY_REGISTERED_WORKFLOWS",
                                   False))

    return True


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
            "msg": "The server encountered an internal error and was " +
                   "unable to complete your request.",
            "status_code": 500,
        }
        response: Response = jsonify(res_body)
        response.status_code = 500
        return response

    return app


def create_app(params: Dict[str, Union[str, int, Path]]) -> Flask:
    app = Flask(__name__)
    app.register_blueprint(app_bp)
    fix_errorhandler(app)
    app.config["RUN_DIR"] = params.run_dir
    app.config["GET_RUNS"] = params.get_runs
    app.config["REGISTERED_ONLY_MODE"] = params.registered_only_mode
    app.config["SERVICE_INFO"] = params.service_info
    app.config["WORKFLOWS_FETCH_CONFIG"] = params.workflows_fetch_config
    app.config["RUN_SH"] = params.run_sh

    return app


def main(sys_args: List[str]) -> None:
    args: Namespace = parse_args(sys_args)
    params: Dict[str, Union[str, int, Path]] = handle_default_params(args)
    app: Flask = create_app(params)
    app.run(host=params.host, port=params.port, debug=params.debug)


if __name__ == "__main__":
    main(sys.argv[1:])
