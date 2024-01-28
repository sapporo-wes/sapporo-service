#!/usr/bin/env python3
# coding: utf-8
import json
import sys
from traceback import format_exc

from flask import Flask, Response, current_app, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from sapporo.auth import apply_jwt_manager
from sapporo.config import Config, get_config, parse_args, validate_config
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
    app = Flask(__name__)
    app.register_blueprint(app_bp, url_prefix=config["url_prefix"])
    fix_errorhandler(app)
    CORS(app, resources={r"/*": {"origins": config["access_control_allow_origin"]}})
    with config["auth_config"].open(mode="r", encoding="utf-8") as f:
        auth_config = json.load(f)
        auth_enabled = auth_config["auth_enabled"]
        jwt_secret_key = auth_config["jwt_secret_key"]
        auth_users = auth_config["users"]
    if auth_enabled:
        apply_jwt_manager(app)

    app.config.update({
        "RUN_DIR": config["run_dir"],
        "SAPPORO_VERSION": config["sapporo_version"],
        "GET_RUNS": config["get_runs"],
        "WORKFLOW_ATTACHMENT": config["workflow_attachment"],
        "REGISTERED_ONLY_MODE": config["registered_only_mode"],
        "SERVICE_INFO": config["service_info"],
        "EXECUTABLE_WORKFLOWS": config["executable_workflows"],
        "RUN_SH": config["run_sh"],
        "URL_PREFIX": config["url_prefix"],
        "AUTH_ENABLED": auth_enabled,
        "JWT_SECRET_KEY": jwt_secret_key,
        "AUTH_USERS": auth_users,
        "FLASK_ENV": "development" if config["debug"] else "production",
        "DEBUG": config["debug"],
        "TESTING": config["debug"],
    })
    if config["debug"]:
        app.logger.debug("config: %s", config)

    return app


def main() -> None:
    args = parse_args(sys.argv[1:])
    config = get_config(args)
    app = create_app(config)
    app.run(
        host=config["host"],
        port=config["port"],
    )


if __name__ == "__main__":
    main()
