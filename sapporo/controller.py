#!/usr/bin/env python3
# coding: utf-8
from shutil import make_archive
from tempfile import NamedTemporaryFile
from typing import List
from uuid import uuid4

from flask import Blueprint, Response, abort, current_app, request, send_file
from flask.json import jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity

from sapporo.auth import conditional_jwt_required
from sapporo.config import str2bool
from sapporo.const import GET_STATUS_CODE, POST_STATUS_CODE
from sapporo.model import (ParseRequest, RunId, RunListResponse, RunLog,
                           RunRequest, RunStatus, ServiceInfo, Workflow)
from sapporo.model.factory import (generate_executable_workflows,
                                   generate_run_id, generate_run_list,
                                   generate_run_log, generate_run_status,
                                   generate_service_info)
from sapporo.parser import parse_workflows
from sapporo.run import (cancel_run, fork_run, path_hierarchy, prepare_run_dir,
                         read_username, resolve_requested_file_path)
from sapporo.validator import (validate_get_runs,
                               validate_post_parse_workflows, validate_run_id,
                               validate_run_request)

app_bp = Blueprint("sapporo", __name__)


@app_bp.route("/auth", methods=["POST"])
def post_auth() -> Response:
    username = request.json.get("username", None)
    password = request.json.get("password", None)
    if username is None or password is None:
        abort(401, "username and password are required.")

    auth = False
    print(current_app.config["AUTH_USERS"])
    for user in current_app.config["AUTH_USERS"]:
        if user["username"] == username and user["password"] == password:
            auth = True
            break
    if not auth:
        abort(401, "username or password is invalid.")

    access_token = create_access_token(identity=username)
    res_body = {"access_token": access_token}
    response: Response = jsonify(res_body)
    response.status_code = POST_STATUS_CODE

    return response


@app_bp.route("/service-info", methods=["GET"])
def get_service_info() -> Response:
    res_body: ServiceInfo = generate_service_info()
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/executable-workflows", methods=["GET"])
def get_executable_workflows() -> Response:
    res_body: List[Workflow] = generate_executable_workflows()
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/parse-workflow", methods=["POST"])
def post_parse_workflows() -> Response:
    parse_request: ParseRequest = validate_post_parse_workflows()
    res_body = parse_workflows(parse_request)
    response: Response = jsonify(res_body)
    response.status_code = POST_STATUS_CODE

    return response


@app_bp.route("/runs", methods=["GET"])
@conditional_jwt_required
def get_runs() -> Response:
    validate_get_runs()
    username = None
    if current_app.config["AUTH_ENABLED"]:
        username = get_jwt_identity()
    res_body: RunListResponse = generate_run_list(username)
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/runs", methods=["POST"])
@conditional_jwt_required
def post_runs() -> Response:
    run_id = str(uuid4())
    run_request: RunRequest = validate_run_request(run_id)
    prepare_run_dir(run_id, run_request)
    username = None
    if current_app.config["AUTH_ENABLED"]:
        username = get_jwt_identity()
    fork_run(run_id, username)
    response: Response = jsonify(generate_run_id(run_id))
    response.status_code = POST_STATUS_CODE

    return response


@app_bp.route("/runs/<string:run_id>", methods=["GET"])
@conditional_jwt_required
def get_runs_id(run_id: str) -> Response:
    if current_app.config["AUTH_ENABLED"]:
        username = get_jwt_identity()
        if read_username(run_id) != username:
            abort(403, "You don't have permission to access this run.")

    validate_run_id(run_id)
    res_body: RunLog = generate_run_log(run_id)
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/runs/<string:run_id>/cancel", methods=["POST"])
@conditional_jwt_required
def post_runs_id_cancel(run_id: str) -> Response:
    if current_app.config["AUTH_ENABLED"]:
        username = get_jwt_identity()
        if read_username(run_id) != username:
            abort(403, "You don't have permission to access this run.")

    validate_run_id(run_id)
    cancel_run(run_id)
    res_body: RunId = generate_run_id(run_id)
    response: Response = jsonify(res_body)
    response.status_code = POST_STATUS_CODE

    return response


@app_bp.route("/runs/<string:run_id>/status", methods=["GET"])
@conditional_jwt_required
def get_runs_id_status(run_id: str) -> Response:
    if current_app.config["AUTH_ENABLED"]:
        username = get_jwt_identity()
        if read_username(run_id) != username:
            abort(403, "You don't have permission to access this run.")

    validate_run_id(run_id)
    res_body: RunStatus = generate_run_status(run_id)
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/runs/<string:run_id>/data/", methods=["GET"])
@app_bp.route("/runs/<string:run_id>/data/<path:subpath>", methods=["GET"])
@conditional_jwt_required
def get_runs_id_data(run_id: str, subpath: str = "") -> Response:
    if current_app.config["AUTH_ENABLED"]:
        username = get_jwt_identity()
        if read_username(run_id) != username:
            abort(403, "You don't have permission to access this run.")

    validate_run_id(run_id)
    requested_path = resolve_requested_file_path(run_id, subpath)
    if not requested_path.exists():
        abort(404, f"`{subpath}` is not found.")
    if requested_path.is_file():
        return send_file(requested_path, as_attachment=True)
    if str2bool(request.args.get("download", False)):
        with NamedTemporaryFile() as f:
            archive = make_archive(f.name, "zip", root_dir=requested_path.parent, base_dir=requested_path.name)
            return send_file(archive, as_attachment=True, download_name=f"{requested_path.name}.zip")  # type: ignore
    else:
        response: Response = jsonify(path_hierarchy(requested_path, requested_path))
        response.status_code = GET_STATUS_CODE
        return response
