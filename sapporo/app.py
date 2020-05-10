#!/usr/bin/env python3
# coding: utf-8
import argparse
import os
from argparse import ArgumentParser, Namespace
from pathlib import Path
from traceback import format_exc
from typing import List, Optional

from flask import Flask, Response, current_app, jsonify
from werkzeug.exceptions import HTTPException

from sapporo.const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_RUN_DIR
from sapporo.controller import app_bp
from sapporo.type import ErrorResponse


def parse_args() -> Namespace:
    parser: ArgumentParser = argparse.ArgumentParser(
        description="Implementation of a GA4GH workflow execution " +
                    "service that can easily support various " +
                    "workflow runners.")

    parser.add_argument(
        "--host",
        nargs=1,
        type=str,
        metavar="",
        help=f"Host address of Flask. (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "-p",
        "--port",
        nargs=1,
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
        nargs=1,
        type=str,
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

    args: Namespace = parser.parse_args()

    return args


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

    return debug


def handle_default_run_dir(run_dir: Optional[List[str]]) -> Path:
    run_dir_path: Path
    if run_dir is None:
        run_dir_path = Path(os.environ.get("SAPPORO_RUN_DIR", DEFAULT_RUN_DIR))
    else:
        run_dir_path = Path(run_dir[0])
    if not run_dir_path.is_absolute():
        run_dir_path = Path.cwd().joinpath(run_dir_path).resolve()

    return run_dir_path


def handle_default_get_runs(disable_get_runs: bool) -> bool:
    if disable_get_runs:
        return False
    else:
        return bool(os.environ.get("SAPPORO_GET_RUNS", True))


def handle_default_registered_only_mode(run_only_registered_workflows: bool) \
        -> bool:
    if run_only_registered_workflows:
        return True
    else:
        return bool(os.environ.get("SAPPORO_RUN_ONLY_REGISTERED_WORKFLOWS",
                                   False))


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


def create_app(run_dir: Path, get_runs: bool, registered_only_mode: bool) \
        -> Flask:
    app = Flask(__name__)
    app.register_blueprint(app_bp)
    fix_errorhandler(app)
    app.config["RUN_DIR"] = run_dir
    app.config["GET_RUNS"] = get_runs
    app.config["REGISTERED_ONLY_MODE"] = registered_only_mode

    return app


def run(host: str, port: int, debug: bool, run_dir: Path,
        get_runs: bool, registered_only_mode: bool) -> None:
    app: Flask = create_app(run_dir, get_runs, registered_only_mode)
    app.run(host=host, port=port, debug=debug)


def main() -> None:
    args: Namespace = parse_args()
    host: str = handle_default_host(args.host)
    port: int = handle_default_port(args.port)
    debug: bool = handle_default_debug(args.debug)
    run_dir: Path = handle_default_run_dir(args.run_dir)
    get_runs: bool = handle_default_get_runs(args.disable_get_runs)
    registered_only_mode: bool = \
        handle_default_registered_only_mode(args.run_only_registered_workflows)

    run(host, port, debug, run_dir, get_runs, registered_only_mode)


if __name__ == "__main__":
    main()
