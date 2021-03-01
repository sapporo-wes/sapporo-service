#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from shutil import make_archive
from tempfile import NamedTemporaryFile

from flask import (Blueprint, Response, abort, current_app, g, request,
                   send_file)
from flask.json import jsonify

from sapporo.const import GET_STATUS_CODE, POST_STATUS_CODE
from sapporo.run import (cancel_run, fork_run, get_run_log, prepare_run_dir,
                         validate_and_update_run_request, validate_run_id)
from sapporo.type import RunId, RunListResponse, RunLog, RunStatus, ServiceInfo
from sapporo.util import (generate_run_id, generate_service_info,
                          get_all_run_ids, get_run_dir, get_state,
                          path_hierarchy, secure_filepath, str2bool)

app_bp = Blueprint("sapporo", __name__)


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
    if current_app.config["GET_RUNS"] is False:
        abort(403, "This endpoint `GET /runs` is unavailable because the "
              "service provider didn't allow the request to this endpoint "
              "when sapporo was started.")

    res_body: RunListResponse = {
        "runs": [],
        "next_page_token": ""
    }
    for run_id in get_all_run_ids():
        res_body["runs"].append({
            "run_id": run_id,
            "state": get_state(run_id).name  # type: ignore
        })
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/runs", methods=["POST"])
def post_runs() -> Response:
    """
    This endpoint creates a new workflow run and returns a `RunId` to monitor
    its progress.
    """
    run_id: str = generate_run_id()
    run_request = validate_and_update_run_request(
        run_id,
        dict(request.form),  # type: ignore
        request.files
    )
    prepare_run_dir(run_id, run_request, request.files)
    fork_run(run_id)
    response: Response = jsonify({
        "run_id": run_id
    })
    response.status_code = POST_STATUS_CODE

    return response


@app_bp.route("/runs/<string:run_id>", methods=["GET"])
def get_runs_id(run_id: str) -> Response:
    """
    This endpoint provides detailed information about a given workflow run.
    The returned result has information about the outputs produced by this
    workflow (if available), a log object which allows the stderr and stdout
    to be retrieved, a log array so stderr/stdout for individual tasks can be
    retrieved, and the overall state of the workflow run (e.g. RUNNING, see
    the State section).
    """
    validate_run_id(run_id)
    res_body: RunLog = get_run_log(run_id)
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/runs/<string:run_id>/cancel", methods=["POST"])
def post_runs_id_cancel(run_id: str) -> Response:
    """
    Cancel a running workflow.
    """
    validate_run_id(run_id)
    cancel_run(run_id)
    res_body: RunId = {"run_id": run_id}
    response: Response = jsonify(res_body)
    response.status_code = POST_STATUS_CODE

    return response


@app_bp.route("/runs/<string:run_id>/status", methods=["GET"])
def get_runs_id_status(run_id: str) -> Response:
    """
    This provides an abbreviated (and likely fast depending on implementation)
    status of the running workflow, returning a simple result with the overall
    state of the workflow run (e.g. RUNNING, see the State section).
    """
    validate_run_id(run_id)
    res_body: RunStatus = {
        "run_id": run_id,
        "state": get_state(run_id).name  # type: ignore
    }
    response: Response = jsonify(res_body)
    response.status_code = GET_STATUS_CODE

    return response


@app_bp.route("/runs/<string:run_id>/data/", methods=["GET"])
@app_bp.route("/runs/<string:run_id>/data/<path:subpath>", methods=["GET"])
def get_runs_id_data(run_id: str, subpath: str = "") -> Response:
    """
    This provides a remote url to download a file or directory under the
    `run_dir` of the Sapporo-service.

    - In the case of `path/to/file`, this returns the file.
    - In the case of `path/to/dir`, this returns the list of files under
      directory in JSON format.
    - In the case of `path/to/dir?download=true`, this returns the directory
      in zip format.

    The path is relative to the base directory of each run.
    See `README.md` in sapporo-service for the structure of `run_dir`.
    For example, if you want to download the output `foo.txt`, specify
    something like `outputs/foo.txt`.

    `..` will be ignored.
    """
    validate_run_id(run_id)
    requested_path = secure_filepath(subpath)
    path = get_run_dir(run_id).joinpath(secure_filepath(subpath))
    if not path.exists():
        parent = Path(f"runs/{run_id}/data").joinpath(requested_path.parent)
        abort(404,
              f"The specified path: {requested_path} does not exist. "
              f"Please make another request to `<endpoint>/{parent}/` again "
              "and check the dir structure.")
    if path.is_file():
        return send_file(path, as_attachment=True)
    else:
        if str2bool(request.args.get("download", False)):
            with NamedTemporaryFile() as f:
                res = make_archive(f.name, "zip",
                                   root_dir=path.parent, base_dir=path.name)
                if "temp_files" not in g:
                    g.temp_files = [Path(f"{f.name}.zip")]
                else:
                    g.temp_files.append(Path(f"{f.name}.zip"))
                return send_file(res, as_attachment=True,
                                 attachment_filename=f"{path.name}.zip")
        else:
            response: Response = jsonify(path_hierarchy(path, path))
            response.status_code = GET_STATUS_CODE
            return response


@app_bp.after_request
def delete_temp_files(response: Response) -> Response:
    if "temp_files" in g:
        for temp_file in g.temp_files:
            temp_file.unlink(missing_ok=False)

    return response
