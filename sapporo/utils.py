import errno
import importlib.metadata
import ipaddress
import json
import logging
import os
import re
import socket
import stat
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any
from unicodedata import normalize
from urllib.parse import urlparse

if TYPE_CHECKING:
    from sapporo.config import RunDirStructureKeys

LOGGER = logging.getLogger(__name__)


def inside_docker() -> bool:
    return Path("/.dockerenv").exists()


def now_str() -> str:
    """Return the current time in RFC 3339 format (e.g., "2022-01-01T00:00:00Z")."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def time_str_to_dt(time_str: str) -> datetime:
    return datetime.fromisoformat(time_str)


def dt_to_time_str(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def sapporo_version() -> str:
    return importlib.metadata.version("sapporo")


def user_agent() -> str:
    return f"sapporo/{sapporo_version()}"


def open_run_file(path: Path, *, binary: bool = False, errors: str | None = None) -> IO[Any] | None:
    """Open a file of a run directory for reading.

    Return None when the file does not exist or is not a regular file. The engine container can
    write anywhere in the run directory, so a control file may have been replaced by a symlink to a
    file that only the server can read, or by a FIFO that blocks the reader. O_NOFOLLOW refuses a
    symlink when the file is opened and fstat refuses everything else, so there is no window
    between a check and the open.
    """
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.ENXIO):
            LOGGER.warning("Ignoring %s: it is a symlink or a socket, not a regular file", path)
            return None
        raise
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            LOGGER.warning("Ignoring %s: it is not a regular file", path)
            os.close(fd)
            return None
    except OSError:
        os.close(fd)
        raise
    if binary:
        return os.fdopen(fd, "rb")
    return os.fdopen(fd, "r", encoding="utf-8", errors=errors)


def open_run_file_for_write(path: Path) -> IO[str]:
    """Open a file of a run directory for writing, replacing a symlink instead of following it.

    The engine container can replace a control file by a symlink to any file the server can write,
    and a plain open would then overwrite that file.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags, 0o666)
    except OSError as e:
        if e.errno != errno.ELOOP:
            raise
        LOGGER.warning("Replacing the symlink %s by a regular file", path)
        path.unlink()
        fd = os.open(path, flags, 0o666)
    return os.fdopen(fd, "w", encoding="utf-8")


def resolve_within_run(path: Path, run_dir: Path) -> Path | None:
    """Return the real path of path (symlinks followed) when it exists and lies inside the run directory, else None."""
    try:
        real_path = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return real_path if real_path.is_relative_to(run_dir) else None


def inside_run_dir(path: Path, run_dir: Path) -> bool:
    """Whether the file that path refers to (symlinks followed) lies inside the run directory."""
    return resolve_within_run(path, run_dir) is not None


def walk_within_run(root: Path, run_dir: Path) -> Iterator[tuple[Path, list[str], list[str]]]:
    """Walk a directory tree like os.walk, following only symlinks whose target lies inside the run directory.

    A directory is entered once, so a symlink loop ends the descent instead of repeating it. A file
    whose target lies outside the run directory is left out. Names are sorted, so the result does
    not depend on the order in which the filesystem lists them.
    """
    real_root = resolve_within_run(root, run_dir)
    if real_root is None:
        return
    visited = {real_root}
    for current, dirs, files in os.walk(root, followlinks=True):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for name in sorted(dirs):
            real_child = resolve_within_run(current_path / name, run_dir)
            if real_child is None:
                LOGGER.warning("Leaving %s out: it points outside the run directory", current_path / name)
                continue
            if real_child in visited:
                continue
            visited.add(real_child)
            kept_dirs.append(name)
        dirs[:] = kept_dirs
        kept_files: list[str] = []
        for name in sorted(files):
            if inside_run_dir(current_path / name, run_dir):
                kept_files.append(name)
            else:
                LOGGER.warning("Leaving %s out: it points outside the run directory", current_path / name)
        yield current_path, kept_dirs, kept_files


def read_run_dir_file(run_dir: Path, key: "RunDirStructureKeys", one_line: bool = False, raw: bool = False) -> Any:
    """Read a file from a run directory by its RUN_DIR_STRUCTURE key."""
    from sapporo.config import RUN_DIR_STRUCTURE

    if "dir" in key:
        return None
    f = open_run_file(run_dir / RUN_DIR_STRUCTURE[key])
    if f is None:
        return None

    with f:
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
    f = open_run_file(path, binary=True)
    if f is None:
        return ""
    try:
        with f:
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


def _is_link_local(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to the link-local range (cloud metadata services)."""
    return addr.is_link_local


def validate_url_not_metadata_service(url: str) -> None:
    """Validate that a URL does not point to a cloud metadata service.

    Blocks link-local addresses (169.254.0.0/16, fe80::/10) which are used by
    AWS, GCP, and Azure metadata services. Also checks DNS-resolved addresses
    to prevent DNS rebinding attacks.

    Private IPs (localhost, 10.x, 192.168.x) are intentionally allowed
    for development environments where local file servers are common.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        msg = f"URL scheme must be http or https, got: {parsed.scheme!r}"
        raise ValueError(msg)

    hostname = parsed.hostname
    if hostname is None:
        msg = f"URL has no hostname: {url!r}"
        raise ValueError(msg)

    # Check if hostname is an IP literal
    try:
        addr = ipaddress.ip_address(hostname)
        if _is_link_local(addr):
            msg = f"URL points to a link-local address (metadata service): {hostname}"
            raise ValueError(msg)
    except ValueError as e:
        if "link-local" in str(e) or "metadata" in str(e):
            raise
        # Not an IP literal, will resolve via DNS below

    # DNS resolution check (prevents DNS rebinding to metadata IPs)
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return  # DNS resolution failure is not a security concern here

    for _family, _type, _proto, _canonname, sockaddr in addrinfos:
        ip_str = sockaddr[0]
        addr = ipaddress.ip_address(ip_str)
        if _is_link_local(addr):
            msg = f"URL hostname {hostname!r} resolves to link-local address: {ip_str}"
            raise ValueError(msg)
