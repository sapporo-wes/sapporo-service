import importlib.metadata
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unicodedata import normalize

if TYPE_CHECKING:
    from sapporo.config import RunDirStructureKeys


def inside_docker() -> bool:
    return Path("/.dockerenv").exists()


def now_str() -> str:
    """Return the current time in RFC 3339 format (e.g., "2022-01-01T00:00:00Z")."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def time_str_to_dt(time_str: str) -> datetime:
    return datetime.fromisoformat(time_str.replace("Z", "+00:00"))


def dt_to_time_str(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def sapporo_version() -> str:
    return importlib.metadata.version("sapporo")


def user_agent() -> str:
    return f"sapporo/{sapporo_version()}"


def read_run_dir_file(run_dir: Path, key: "RunDirStructureKeys", one_line: bool = False, raw: bool = False) -> Any:
    """Read a file from a run directory by its RUN_DIR_STRUCTURE key."""
    from sapporo.config import RUN_DIR_STRUCTURE

    if "dir" in key:
        return None
    file_path = run_dir / RUN_DIR_STRUCTURE[key]
    if not file_path.is_file():
        return None

    with file_path.open(mode="r", encoding="utf-8") as f:
        if one_line:
            return f.readline().strip()
        if raw:
            return f.read()
        content = f.read()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content


def tail_file(path: Path, n_lines: int = 20) -> str:
    """Read the last n_lines from a file efficiently.

    Uses a seek-from-end strategy to avoid reading the entire file into memory.
    """
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            if file_size == 0:
                return ""
            chunk_size = min(file_size, n_lines * 512)
            f.seek(max(0, file_size - chunk_size))
            data = f.read().decode("utf-8", errors="replace")
            lines = data.splitlines()
            return "\n".join(lines[-n_lines:])
    except OSError:
        return ""


def mask_sensitive(obj: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    """Return a shallow copy of obj with values of specified keys replaced by '***'."""
    result: dict[str, Any] = {}
    for k, v in obj.items():
        if k in keys:
            result[k] = "***"
        elif isinstance(v, dict):
            result[k] = mask_sensitive(v, keys)
        else:
            result[k] = v
    return result


_filename_char_whitelist_re = re.compile(r"[^A-Za-z0-9_.-]+")


def secure_filepath(filepath: str) -> Path:
    """Create a safe file path that preserves directory structures.

    Filter out potentially harmful or unsupported characters.
    This function is designed to be more suitable for workflows that need to preserve directory hierarchies unlike
    werkzeug.secure_filename(), which does not preserve directory structures, as shown below:

    >>> secure_filename("../../../etc/passwd")
    'etc_passwd'

    Reference usage of `Path.parts` for understanding how parts are handled:

    >>> Path("/").parts
    ('/',)
    >>> Path("//").parts
    ('//',)
    >>> Path("/foo/bar").parts
    ('/', 'foo', 'bar')
    >>> Path("foo/bar").parts
    ('foo', 'bar')
    >>> Path("/foo/bar/").parts
    ('/', 'foo', 'bar')
    >>> Path("./foo/bar/").parts
    ('foo', 'bar')
    >>> Path("/../../foo/bar//").parts
    ('/', '..', '..', 'foo', 'bar')
    >>> Path("/../.../foo/bar//").parts
    ('/', '..', '...', 'foo', 'bar')
    """
    from sapporo.exceptions import raise_bad_request

    ascii_filepath = normalize("NFKD", filepath).encode("ascii", "ignore").decode("ascii")
    pure_path = Path(ascii_filepath)
    sanitized_parts = []
    for part in pure_path.parts:
        cleaned_part = part.replace(" ", "_")
        cleaned_part = re.sub(r"\.{3,}", "", cleaned_part)
        cleaned_part = _filename_char_whitelist_re.sub("", cleaned_part)
        if cleaned_part not in ("", ".", ".."):
            sanitized_parts.append(cleaned_part)
    if not sanitized_parts:
        raise_bad_request(f"Invalid file path: {filepath!r}")
    return Path(*sanitized_parts)
