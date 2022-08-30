#!/usr/bin/env python3
# coding: utf-8
import sys
from traceback import format_exc

from flask import Flask, Response, current_app, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from sapporo.config import (Config, TypedNamespace, get_config, parse_args,
                            validate_config)
from sapporo.controller import app_bp
from sapporo.model import ErrorResponse


def fix_errorhandler(app: Flask) -> Flask:
    @app.errorhandler(HTTPException)
    def error_handler(error: HTTPException) -> Response:
        res_body: ErrorResponse = {
            "msg": error.description or "",
            "status_code": error.code or 500,
        }
        response: Response = jsonify(res_body)
        response.status_code = error.code or 500
        return response

    @app.errorhandler(Exception)
    def error_handler_exception(exception: Exception) -> Response:
        current_app.logger.error(exception.args[0])
        current_app.logger.debug(format_exc())
        res_body: ErrorResponse = {
            "msg": "The server encountered an internal error and was unable to complete your request.",
            "status_code": 500,
        }
        if current_app.config["TESTING"]:
            res_body["msg"] = format_exc()
        response: Response = jsonify(res_body)
        response.status_code = 500
        return response

    return app


def create_app(config: Config) -> Flask:
    validate_config(config)
    app: Flask = Flask(__name__)
    app.register_blueprint(app_bp, url_prefix=config["url_prefix"])
    fix_errorhandler(app)
    CORS(app, resources={
         r"/*": {"origins": config["access_control_allow_origin"]}})
    app.config["RUN_DIR"] = config["run_dir"]
    app.config["SAPPORO_VERSION"] = config["sapporo_version"]
    app.config["GET_RUNS"] = config["get_runs"]
    app.config["WORKFLOW_ATTACHMENT"] = config["workflow_attachment"]
    app.config["REGISTERED_ONLY_MODE"] = config["registered_only_mode"]
    app.config["SERVICE_INFO"] = config["service_info"]
    app.config["EXECUTABLE_WORKFLOWS"] = config["executable_workflows"]
    app.config["RUN_SH"] = config["run_sh"]
    app.config["URL_PREFIX"] = config["url_prefix"]
    if config["debug"]:
        app.config["FLASK_ENV"] = "development"
        app.config["DEBUG"] = True
        app.config["TESTING"] = True
        app.logger.debug(f"config: {config}")

    return app


def main() -> None:
    args: TypedNamespace = parse_args(sys.argv[1:])
    config: Config = get_config(args)
    app: Flask = create_app(config)
    app.run(
        host=config["host"],
        port=config["port"],
    )


if __name__ == "__main__":
    main()
