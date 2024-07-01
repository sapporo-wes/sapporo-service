import importlib.metadata
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Union
from unicodedata import normalize


def str2bool(val: Union[str, bool]) -> bool:
    if isinstance(val, bool):
        return val
    if val.lower() in ["true", "yes", "y"]:
        return True
    if val.lower() in ["false", "no", "n"]:
        return False

    return bool(val)


def inside_docker() -> bool:
    return Path("/.dockerenv").exists()


def now_str() -> str:
    """
    Return the current time in RFC 3339 format. (e.g., "2022-01-01T00:00:00Z")
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def time_str_to_dt(time_str: str) -> datetime:
    return datetime.fromisoformat(time_str.replace("Z", "+00:00"))


def dt_to_time_str(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def sapporo_version() -> str:
    return importlib.metadata.version("sapporo")


def user_agent() -> str:
    return f"sapporo/{sapporo_version()}"


_filename_char_whitelist_re = re.compile(r"[^A-Za-z0-9_.-]+")


def secure_filepath(filepath: str) -> Path:
    """
    Creates a safe file path that preserves directory structures while filtering out potentially harmful or unsupported characters.
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
    ascii_filepath = normalize("NFKD", filepath).encode("ascii", "ignore").decode("ascii")
    pure_path = Path(ascii_filepath)
    sanitized_parts = []
    for part in pure_path.parts:
        part = part.replace(" ", "_")
        part = re.sub(r"\.{3,}", "", part)
        part = _filename_char_whitelist_re.sub("", part)
        if part not in ("", ".", ".."):
            sanitized_parts.append(part)
    safe_path = Path(*sanitized_parts)

    return safe_path
