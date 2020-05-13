#!/usr/bin/env python3
# coding: utf-8
from flask import Blueprint, Response
from flask.json import jsonify

from sapporo.const import GET_STATUS_CODE, POST_STATUS_CODE
from sapporo.type import RunId, RunListResponse, RunLog, RunStatus, ServiceInfo
from sapporo.util import generate_service_info

app_bp = Blueprint("genpei", __name__)


@app_bp.route("/service-info", methods=["GET"])
def get_service_info() -> Response:
    """
    May include information related (but not limited to) the workflow
    descriptor formats, versions supported, the WES API versions supported,
    and information about general service availability.
    """
    res_body: ServiceInfo = generate_service_info()
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/runs", methods=["GET"])
def get_runs() -> Response:
    """
    This list should be provided in a stable ordering. (The actual ordering is
    implementation dependent.) When paging through the list, the client should
    not make assumptions about live updates, but should assume the contents of
    the list reflect the workflow list at the moment that the first page is
    requested. To monitor a specific workflow run, use GetRunStatus or
    GetRunLog.
    """
    res_body: RunListResponse = {
        "runs": [],
        "next_page_token": ""
    }
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/runs", methods=["POST"])
def post_runs() -> Response:
    """
    This endpoint creates a new workflow run and returns a `RunId` to monitor
    its progress.
    """
    response: Response = jsonify({
        "run_id": ""
    })
    response.status_code = POST_STATUS_CODE

    return response


@app_bp.route("/runs/<run_id>", methods=["GET"])
def get_runs_id(run_id: str) -> Response:
    """
    This endpoint provides detailed information about a given workflow run.
    The returned result has information about the outputs produced by this
    workflow (if available), a log object which allows the stderr and stdout
    to be retrieved, a log array so stderr/stdout for individual tasks can be
    retrieved, and the overall state of the workflow run (e.g. RUNNING, see
    the State section).
    """
    res_body: RunLog = {"endpoint": "run/run_id"}  # type: ignore
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/runs/<run_id>/cancel", methods=["POST"])
def post_runs_id_cancel(run_id: str) -> Response:
    """
    Cancel a running workflow.
    """
    res_body: RunId = {"run_id": ""}
    response: Response = jsonify(res_body)
    response.status_code = POST_STATUS_CODE

    return response


@app_bp.route("/runs/<run_id>/status", methods=["GET"])
def get_runs_id_status(run_id: str) -> Response:
    """
    This provides an abbreviated (and likely fast depending on implementation)
    status of the running workflow, returning a simple result with the overall
    state of the workflow run (e.g. RUNNING, see the State section).
    """
    res_body: RunStatus = {
        "run_id": "",
        "state": "UNKNOWN"  # type: ignore
    }
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response
