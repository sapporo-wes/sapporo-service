"""File I/O operations for run directories.

Extracted from run.py to break circular imports between
run.py, factory.py, and database.py.
"""

import json
import logging
import shlex
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from sapporo.config import RUN_DIR_STRUCTURE, RunDirStructureKeys, get_config
from sapporo.schemas import RunRequest, State
from sapporo.utils import sapporo_version

LOGGER = logging.getLogger(__name__)


def resolve_run_dir(run_id: str) -> Path:
    run_dir_base = get_config().run_dir

    return run_dir_base.joinpath(run_id[:2]).joinpath(run_id).resolve()


def resolve_content_path(run_id: str, key: RunDirStructureKeys) -> Path:
    return resolve_run_dir(run_id).joinpath(RUN_DIR_STRUCTURE[key])


def write_file(run_id: str, key: RunDirStructureKeys, content: Any) -> None:
    file = resolve_content_path(run_id, key)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open(mode="w", encoding="utf-8") as f:
        if file.suffix == ".json":
            if key == "wf_params" and isinstance(content, str):
                pass
            else:
                content = json.dumps(content, indent=2)
        elif key == "state":
            content = content.value
        else:
            content = str(content)
        f.write(content)


def read_file(run_id: str, key: RunDirStructureKeys) -> Any:
    if key == "state":
        return read_state(run_id)

    if "dir" in key:
        return None
    file_path = resolve_content_path(run_id, key)
    if file_path.exists() is False:
        return None

    with file_path.open(mode="r", encoding="utf-8") as f:
        content = f.read().strip()
        # Special handling for specific keys
        if key == "run_request":
            try:
                return RunRequest.model_validate_json(content)
            except ValidationError as e:
                LOGGER.warning("Ignoring run_request.json that cannot be parsed: run_id=%s, error=%s", run_id, e)
                return None
        if key == "cmd":
            return shlex.split(content)
        if key in ["start_time", "end_time", "stdout", "stderr", "username"]:
            return content
        if key == "exit_code":
            return _parse_int(content)
        if key == "pid":
            pid = _parse_int(content)
            # 0 and negative values address process groups and 1 is init, so none of them is run.sh
            return pid if pid is not None and pid > 1 else None
        if key == "ro_crate":
            return json.loads(content)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content


def _parse_int(content: str) -> int | None:
    try:
        return int(content)
    except ValueError:
        return None


def read_state(run_id: str) -> State:
    """Read state.txt. A missing file or a value that is not a State is reported as UNKNOWN."""
    try:
        with resolve_content_path(run_id, "state").open(mode="r", encoding="utf-8") as f:
            return State(f.read().strip())
    except FileNotFoundError:
        return State.UNKNOWN
    except ValueError as e:
        LOGGER.warning("Treating state.txt that cannot be parsed as UNKNOWN: run_id=%s, error=%s", run_id, e)
        return State.UNKNOWN


def glob_all_run_ids() -> list[str]:
    """List every run directory, including deleted runs, which keep only state.txt and the timestamps."""
    return [run_dir.parent.name for run_dir in get_config().run_dir.glob(f"*/*/{RUN_DIR_STRUCTURE['state']}")]


def dump_runtime_info(run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "sapporo_version": sapporo_version(),
        "base_url": get_config().base_url,
    }
