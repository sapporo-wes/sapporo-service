#!/usr/bin/env python3
# coding: utf-8
import collections
import json
import os
import shlex
import shutil
import signal
from pathlib import Path, PurePath
from subprocess import Popen
from typing import Any, Dict, Iterable, List, Optional
from unicodedata import normalize
from urllib import parse

import requests
from flask import current_app, request
from werkzeug.utils import _filename_ascii_strip_re

from sapporo.const import RUN_DIR_STRUCTURE, RUN_DIR_STRUCTURE_KEYS
from sapporo.model import RunRequest, State
from sapporo.model.factory import (generate_executable_workflows,
                                   generate_service_info)
from sapporo.model.sapporo_wes_1_0_1 import AttachedFile


def resolve_run_dir_path(run_id: str) -> Path:
    run_base_dir: Path = current_app.config["RUN_DIR"]

    return run_base_dir.joinpath(run_id[:2]).joinpath(run_id).resolve()


def resolve_content_path(run_id: str, key: RUN_DIR_STRUCTURE_KEYS) -> Path:
    run_dir: Path = resolve_run_dir_path(run_id)

    return run_dir.joinpath(RUN_DIR_STRUCTURE[key])


def read_state(run_id: str) -> State:
    try:
        with resolve_content_path(run_id, "state").open(mode="r") as f:
            state: State = f.readline().strip()  # type: ignore
            return state
    except Exception:
        return "UNKNOWN"


def count_system_state() -> Dict[State, int]:
    run_ids: List[str] = glob_all_run_ids()
    count: Dict[State, int] = dict(collections.Counter(
        [read_state(run_id) for run_id in run_ids]))

    return count


def glob_all_run_ids() -> List[str]:
    run_base_dir: Path = current_app.config["RUN_DIR"]
    run_requests: List[Path] = \
        list(run_base_dir.glob(f"**/{RUN_DIR_STRUCTURE['run_request']}"))
    run_ids: List[str] = \
        [run_request.parent.name for run_request in run_requests]

    return run_ids


def read_file(run_id: str, file_type: RUN_DIR_STRUCTURE_KEYS) -> Any:
    if "dir" in file_type:
        return None
    file_path = resolve_content_path(run_id, file_type)
    if file_path.exists() is False:
        return None
    with file_path.open(mode="r", encoding="utf-8") as f:
        content = f.read().strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content


def secure_filepath(filepath: str) -> Path:
    """
    We know `werkzeug.secure_filename()`.
    However, this function cannot represent the dir structure,

    >>> secure_filename("../../../etc/passwd")
    'etc_passwd'

    Thus, it is incompatible with workflow engines such as snakemake.
    Therefore, We implemented this by referring to `werkzeug.secure_filename()`

    Please check `tests/unit_test/test_secure_filepath.py`

    Reference of `PurePath.parts`:
    >> > PurePath("/").parts
    ('/',)
    >> > PurePath("//").parts
    ('//',)
    >> > PurePath("/foo/bar").parts
    ('/', 'foo', 'bar')
    >> > PurePath("foo/bar").parts
    ('foo', 'bar')
    >> > PurePath("/foo/bar/").parts
    ('/', 'foo', 'bar')
    >> > PurePath("./foo/bar/").parts
    ('foo', 'bar')
    >> > PurePath("/../../foo/bar//").parts
    ('/', '..', '..', 'foo', 'bar')
    >> > PurePath("/../.../foo/bar//").parts
    ('/', '..', '...', 'foo', 'bar')
    """
    ascii_filepath = normalize("NFKD", filepath).encode(
        "ascii", "ignore").decode("ascii")
    pure_path = PurePath(ascii_filepath)
    nodes = []
    for node in pure_path.parts:
        # Change space to underscore
        node = "_".join(node.split())
        # Change [^A-Za-z0-9_.-] to empty.
        node = str(_filename_ascii_strip_re.sub("", node))
        node = node.strip("._")
        if node not in ["", ".", ".."]:
            nodes.append(node)

    path = Path("/".join([str(node) for node in nodes]))

    return path


def write_file(run_id: str, key: RUN_DIR_STRUCTURE_KEYS, content: Any) -> None:
    file = resolve_content_path(run_id, key)
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.suffix == ".json" and isinstance(content, (dict, list)):
        content = json.dumps(content, indent=2)
    with file.open(mode="w", encoding="utf-8") as f:
        f.write(str(content))


def sapporo_endpoint() -> str:
    host = request.host_url.strip("/")
    url_prefix = current_app.config['URL_PREFIX'].strip("/")
    endpoint = f"{host}/{url_prefix}".strip("/")

    return endpoint


def prepare_run_dir(run_id: str, run_request: RunRequest) -> None:
    run_dir = resolve_run_dir_path(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    exe_dir = resolve_content_path(run_id, "exe_dir")
    exe_dir.mkdir(parents=True, exist_ok=True)
    exe_dir.chmod(0o777)
    outputs_dir: Path = resolve_content_path(run_id, "outputs_dir")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.chmod(0o777)

    write_file(run_id, "sapporo_config", dump_sapporo_config())
    write_file(run_id, "run_request", run_request)
    write_file(run_id, "wf_params", run_request["workflow_params"])
    write_file(run_id, "wf_engine_params",
               convert_wf_engine_params_str(run_request))

    write_file(run_id, "service_info", generate_service_info())
    write_file(run_id, "executable_workflows", generate_executable_workflows())
    with current_app.config["RUN_SH"].open(mode="r", encoding="utf-8") as f:
        run_sh_content = f.read()
    write_file(run_id, "run_sh", run_sh_content)

    yevis_metadata = request.form.get("yevis_metadata", None)
    if yevis_metadata is not None:
        write_file(run_id, "yevis_metadata", yevis_metadata)

    write_workflow_attachment(run_id, run_request)


def dump_sapporo_config() -> Dict[str, Any]:
    return {
        "sapporo_version": current_app.config["SAPPORO_VERSION"],
        "get_runs": current_app.config["GET_RUNS"],
        "workflow_attachment": current_app.config["WORKFLOW_ATTACHMENT"],
        "registered_only_mode": current_app.config["REGISTERED_ONLY_MODE"],
        "service_info": str(current_app.config["SERVICE_INFO"]),
        "executable_workflows": str(current_app.config["EXECUTABLE_WORKFLOWS"]),
        "run_sh": str(current_app.config["RUN_SH"]),
        "url_prefix": current_app.config["URL_PREFIX"],
        "sapporo_endpoint": sapporo_endpoint(),
    }


def convert_wf_engine_params_str(run_request: RunRequest) -> str:
    wf_engine_params: Optional[str] = run_request["workflow_engine_parameters"]
    params: List[str] = []
    if wf_engine_params is None:
        service_info = generate_service_info()
        default_wf_engine_dict = service_info["default_workflow_engine_parameters"]
        default_wf_engine_params = default_wf_engine_dict.get(
            run_request["workflow_engine_name"], [])
        for default_wf_engine_param in default_wf_engine_params:
            params.append(default_wf_engine_param.get("name", ""))
            params.append(default_wf_engine_param.get("default_value", ""))
    else:
        wf_engine_params_obj = json.loads(wf_engine_params)
        if isinstance(wf_engine_params_obj, list):
            params.extend(map(str, wf_engine_params_obj))
        elif isinstance(wf_engine_params_obj, dict):
            for key, value in wf_engine_params_obj.items():
                params.append(str(key))
                params.append(str(value))

    return " ".join(params)


def write_workflow_attachment(run_id: str, run_request: RunRequest) -> None:
    exe_dir = resolve_content_path(run_id, "exe_dir")
    if current_app.config["WORKFLOW_ATTACHMENT"]:
        workflow_attachment = request.files.getlist("workflow_attachment")
        for file_storage in workflow_attachment:
            if file_storage.filename:
                file_name = secure_filepath(file_storage.filename)
                file_path = exe_dir.joinpath(file_name).resolve()
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_storage.save(file_path)


# Called in run.sh
def download_workflow_attachment(inputted_run_dir: str) -> None:
    run_dir: Path = Path(inputted_run_dir).resolve()
    config_path = run_dir.joinpath(RUN_DIR_STRUCTURE["sapporo_config"])
    with config_path.open(mode="r", encoding="utf-8") as f:
        sapporo_config = json.load(f)
    endpoint = sapporo_config["sapporo_endpoint"]
    exe_dir = run_dir.joinpath(RUN_DIR_STRUCTURE["exe_dir"])
    run_request_path = run_dir.joinpath(RUN_DIR_STRUCTURE["run_request"])
    with run_request_path.open(mode="r", encoding="utf-8") as f:
        run_request = json.load(f)
    wf_attachment_obj: List[AttachedFile] = json.loads(run_request["workflow_attachment"] or "[]")
    for file in wf_attachment_obj:
        name = file["file_name"]
        url = file["file_url"]
        parsed_url = parse.urlparse(url)
        if parsed_url.scheme in ["http", "https"] and not url.startswith(endpoint):
            file_path = exe_dir.joinpath(secure_filepath(name)).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with requests.get(url, stream=True) as res:
                if res.status_code == 200:
                    with file_path.open(mode="wb") as f:
                        res.raw.decode_content = True
                        shutil.copyfileobj(res.raw, f, 1024 * 1024)


def fork_run(run_id: str) -> None:
    run_dir: Path = resolve_run_dir_path(run_id)
    stdout: Path = resolve_content_path(run_id, "stdout")
    stderr: Path = resolve_content_path(run_id, "stderr")
    cmd: str = f"/bin/bash {current_app.config['RUN_SH']} {run_dir}"
    write_file(run_id, "state", "QUEUED")
    with stdout.open(mode="w", encoding="utf-8") as f_stdout, \
            stderr.open(mode="w", encoding="utf-8") as f_stderr:
        process = Popen(shlex.split(cmd),  # pylint: disable=consider-using-with
                        cwd=str(run_dir),
                        env=os.environ.copy(),
                        encoding="utf-8",
                        stdout=f_stdout, stderr=f_stderr)
    pid: Optional[int] = process.pid
    if pid is not None:
        write_file(run_id, "pid", str(pid))


def cancel_run(run_id: str) -> None:
    state: State = read_state(run_id)
    if state == "RUNNING":
        write_file(run_id, "state", "CANCELING")
        pid: int = int(read_file(run_id, "pid"))
        os.kill(pid, signal.SIGUSR1)


def resolve_requested_file_path(run_id: str, subpath: str) -> Path:
    if Path(subpath).name[0] == ".":
        requested_path = secure_filepath(
            str(Path(subpath).parent)).joinpath(Path(subpath).name)
    else:
        requested_path = secure_filepath(subpath)
    run_dir_path = resolve_run_dir_path(run_id)

    return run_dir_path.joinpath(requested_path)


def path_hierarchy(original_path: Path, dir_path: Path) -> Any:
    hierarchy: Dict[str, Any] = {
        "type": "directory",
        "name": dir_path.name,
        "path": str(dir_path.relative_to(original_path)),
    }

    try:
        hierarchy["children"] = [
            path_hierarchy(original_path, dir_path.joinpath(child))
            for child in dir_path.iterdir()
        ]
    except Exception:
        hierarchy["type"] = "file"

    return hierarchy


# Called in run.sh
def dump_outputs_list(inputted_run_dir: str) -> None:
    run_dir: Path = Path(inputted_run_dir).resolve()
    run_id = run_dir.name
    config_path = run_dir.joinpath(RUN_DIR_STRUCTURE["sapporo_config"])
    with config_path.open(mode="r", encoding="utf-8") as f:
        sapporo_config = json.load(f)
    base_remote_url = \
        f"{sapporo_config['sapporo_endpoint']}/runs/{run_id}/data/"
    outdir_path: Path = run_dir.joinpath(RUN_DIR_STRUCTURE["outputs_dir"])
    output_files: List[Path] = sorted(list(walk_all_files(outdir_path)))
    outputs = []
    for output_file in output_files:
        outputs.append({
            "file_name": str(output_file.relative_to(outdir_path)),
            "file_url":
                f"{base_remote_url}{str(output_file.relative_to(run_dir))}"
        })
    output_path = run_dir.joinpath(RUN_DIR_STRUCTURE["outputs"])
    with output_path.open(mode="w", encoding="utf-8") as f:
        f.write(json.dumps(outputs, indent=2))


def walk_all_files(dir_path: Path) -> Iterable[Path]:
    for root, _, files in os.walk(dir_path):
        for file in files:
            yield Path(root).joinpath(file)
