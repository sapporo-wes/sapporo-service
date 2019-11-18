#!/usr/local/bin/python3
# coding: utf-8
import os
import shlex
import signal
from copy import deepcopy
from datetime import datetime
from subprocess import PIPE, Popen
from uuid import uuid4

import yaml
from flask import abort

from .util import (PID_INFO_FILE_NAME, RUN_BASE_DIR, RUN_EXECUTION_SCRIPT_PATH,
                   RUN_ORDER_FILE_NAME, STATUS_FILE_NAME, STDERR_FILE_NAME,
                   STDOUT_FILE_NAME, UPLOAD_URL_FILE_NAME, WORKFLOW_FILE_NAME,
                   WORKFLOW_PARAMETERS_FILE_NAME, read_service_info,
                   read_workflow_info)
from .workflows import fetch_file


# GET /runs
def get_run_status_list():
    run_status_list = []
    for status_file in RUN_BASE_DIR.glob("**/{}".format(STATUS_FILE_NAME)):
        run_status = dict()
        run_status["run_id"] = status_file.parent.name
        _update_end_time(run_status["run_id"])
        with status_file.open(mode="r") as f:
            run_status["status"] = f.read().strip()
        run_status_list.append(run_status)

    return run_status_list


# POST /runs
def validate_post_runs_request(request):
    run_order = dict(request.form)
    if "workflow_parameters" not in request.files:
        abort(400, "Workflow parameter file not attached.")
    for param in ["workflow_name", "execution_engine_name"]:
        if param not in run_order:
            abort(400, "Param: {} is not included.".format(param))


# POST /runs
def generate_run_order(request):
    """
    run_order = {
        "workflow_name": str,
        "workflow_location": str,
        "workflow_version": str,
        "workflow_content": str,
        "workflow_parameters": str,
        "language_type": str,
        "language_version": str,
        "execution_engine_name": str,
        "execution_engine_version": str,
        "start_time": str (datetime -> str),
        "end_time": str (datetime -> str),
    }
    """
    run_order = deepcopy(dict(request.form))
    run_order["workflow_parameters"] = request.files["workflow_parameters"].stream.read(  # NOQA
    ).decode("utf-8")
    run_order["workflow_location"], run_order["workflow_version"], run_order["workflow_content"], run_order[  # NOQA
        "language_type"], run_order["language_version"] = _fetch_workflow_file(run_order["workflow_name"])  # NOQA
    run_order["execution_engine_version"] = _validate_engine(
        run_order["execution_engine_name"], run_order["language_type"], run_order["language_version"])  # NOQA
    run_order["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_order["end_time"] = ""

    return run_order


def _fetch_workflow_file(workflow_name):
    workflow_info = read_workflow_info()
    for workflow in workflow_info["workflows"]:
        if workflow["workflow_name"] == workflow_name:
            workflow_content = fetch_file(workflow["workflow_location"])
            return workflow["workflow_location"], workflow["workflow_version"], workflow_content, workflow["language_type"], workflow["language_version"]  # NOQA
    abort(400, "Workflow does not exist: {}".format(workflow_name))


def _validate_engine(engine, language_type, language_version):
    service_info = read_service_info()
    for workflow_engine in service_info["workflow_engines"]:
        if workflow_engine["engine_name"] == engine:
            for type_version in workflow_engine["workflow_types"]:
                if type_version["language_type"] == language_type and type_version["language_version"] == language_version:  # NOQA
                    return workflow_engine["engine_version"]
    abort(400, "Workflow engine parameter is incorrect.")


# POST /runs
def execute(run_order):
    uuid = str(uuid4())
    _prepare_run_dir(uuid, run_order)
    _fork_run(uuid)

    return {"run_id": uuid, "status": "PENDING"}


def _prepare_run_dir(uuid, run_order):
    run_dir = RUN_BASE_DIR.joinpath(uuid[:2]).joinpath(uuid)
    run_dir.mkdir(parents=True)
    with run_dir.joinpath(STATUS_FILE_NAME).open(mode="w") as f:
        f.write("QUEUED")
    with run_dir.joinpath(RUN_ORDER_FILE_NAME).open(mode="w") as f:
        f.write(yaml.dump(run_order, default_flow_style=False))
    with run_dir.joinpath(WORKFLOW_FILE_NAME).open(mode="w") as f:
        f.write(run_order["workflow_content"])
    with run_dir.joinpath(WORKFLOW_PARAMETERS_FILE_NAME).open(mode="w") as f:
        f.write(run_order["workflow_parameters"])
    run_dir.joinpath(PID_INFO_FILE_NAME).touch()
    run_dir.joinpath(UPLOAD_URL_FILE_NAME).touch()
    run_dir.joinpath(STDOUT_FILE_NAME).touch()
    run_dir.joinpath(STDERR_FILE_NAME).touch()

    return True


def _fork_run(uuid):
    cmd = "/bin/bash {} {}".format(RUN_EXECUTION_SCRIPT_PATH, uuid)
    l_cmd = shlex.split(cmd)
    proc = Popen(l_cmd)
    run_dir = RUN_BASE_DIR.joinpath(uuid[:2]).joinpath(uuid)
    with run_dir.joinpath(PID_INFO_FILE_NAME).open(mode="w") as f:
        f.write(str(proc.pid))


# GET /runs/<uuid:run_id>
def get_run_info(run_id):
    _update_end_time(run_id)
    run_info = dict()
    run_info["run_id"] = run_id
    run_dir = list(RUN_BASE_DIR.glob("**/{}".format(run_id)))[0]
    with run_dir.joinpath(STATUS_FILE_NAME).open(mode="r") as f:
        run_info["status"] = f.read().strip()
    with run_dir.joinpath(RUN_ORDER_FILE_NAME).open(mode="r") as f:
        run_order = yaml.load(f, Loader=yaml.SafeLoader)
        run_info.update(run_order)
    with run_dir.joinpath(UPLOAD_URL_FILE_NAME).open(mode="r") as f:
        run_info["upload_url"] = f.read().strip()
    with run_dir.joinpath(STDOUT_FILE_NAME).open(mode="r") as f:
        run_info["stdout"] = f.read()
    with run_dir.joinpath(STDERR_FILE_NAME).open(mode="r") as f:
        run_info["stderr"] = f.read()

    return run_info


def _update_end_time(run_id):
    run_dir = list(RUN_BASE_DIR.glob("**/{}".format(run_id)))[0]
    status_file = run_dir.joinpath(STATUS_FILE_NAME)
    with status_file.open(mode="r") as f:
        run_status = f.read().strip()
    if run_status not in ["QUEUED", "RUNNING"]:
        with run_dir.joinpath(RUN_ORDER_FILE_NAME).open(mode="r") as f:
            run_order = yaml.load(f, Loader=yaml.SafeLoader)
            run_order["end_time"] = datetime.fromtimestamp(
                status_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        with run_dir.joinpath(RUN_ORDER_FILE_NAME).open(mode="w") as f:
            f.write(yaml.dump(run_order, default_flow_style=False))


# POST /runs/<uuid:run_id>/cancel
def cancel_run(run_id):
    run_dir = list(RUN_BASE_DIR.glob("**/{}".format(run_id)))[0]
    status_file = run_dir.joinpath(STATUS_FILE_NAME)
    with status_file.open(mode="r") as f:
        run_status = f.read().strip()
        if run_status not in ["QUEUED", "RUNNING"]:
            abort(400, "The run can not be canceled.")
    with run_dir.joinpath(PID_INFO_FILE_NAME).open(mode="r") as f:
        pid = int(f.read().strip())
    ps = Popen(["ps", "aux"], stdout=PIPE).communicate()[0]
    processes = ps.decode("utf-8").split("\n")
    for process in processes:
        try:
            ps_pid = int(process.split()[0])
            l_command = process.split()[3:]
        except Exception:
            continue
        if ps_pid == pid:
            if "sh" in l_command and str(run_id) in l_command:
                os.kill(pid, signal.SIGUSR1)
                with status_file.open(mode="w") as f:
                    f.write("CANCELED")
                return {"run_id": run_id, "status": "CANCELED"}
    abort(400, "There is no run to cancel.")
