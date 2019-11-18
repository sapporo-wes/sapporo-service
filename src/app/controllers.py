#!/usr/local/bin/python3
# coding: utf-8
from flask import Blueprint, abort, jsonify, request

from .config import GET_RUNS
from .lib.runs import (cancel_run, execute, generate_run_order, get_run_info,
                       get_run_status_list, validate_post_runs_request)
from .lib.util import read_service_info
from .lib.workflows import generate_workflow_list
from .util import token_auth

bp_app = Blueprint("app", __name__)


@bp_app.route("/service-info", methods=["GET"])
@token_auth
def get_service_info():
    data = read_service_info()
    response = jsonify(data)
    response.status_code = 200
    return response


@bp_app.route("/workflows", methods=["GET"])
@token_auth
def get_workflows_list():
    data = generate_workflow_list()
    response = jsonify(data)
    response.status_code = 200
    return response


@bp_app.route("/runs", methods=["GET"])
@token_auth
def get_runs():
    if GET_RUNS:
        data = get_run_status_list()
        response = jsonify(data)
        response.status_code = 200
        return response
    else:
        abort(403, "Forbidden")


@bp_app.route("/runs", methods=["POST"])
@token_auth
def post_runs():
    validate_post_runs_request(request)
    run_order = generate_run_order(request)
    data = execute(run_order)
    response = jsonify(data)
    response.status_code = 201
    return response


@bp_app.route("/runs/<uuid:run_id>", methods=["GET"])
@token_auth
def get_runs_uuid(run_id):
    data = get_run_info(run_id)
    response = jsonify(data)
    response.status_code = 200
    return response


@bp_app.route("/runs/<uuid:run_id>/cancel", methods=["POST"])
@token_auth
def post_runs_cancel(run_id):
    data = cancel_run(run_id)
    response = jsonify(data)
    response.status_code = 201
    return response
