"""Module for creating an SQLite database, `{run_dir}/sapporo.db`, within the run directory.

All run-related information stored under the each run directory serves as the master data.
To avoid performance degradation when listing runs or aggregating state counts, etc., this database is used as an index.
This database can be safely deleted if necessary, without impacting the master data.

Init DB script:

    $ python ./sapporo/database.py
"""

import base64
import binascii
import hashlib
import hmac
import json
import logging
import re
import secrets
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import cache
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, text
from sqlalchemy.engine.base import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from sapporo.config import get_config
from sapporo.exceptions import raise_bad_request
from sapporo.factory import create_run_summary
from sapporo.run_io import glob_all_run_ids, read_file
from sapporo.schemas import RunSummary, State
from sapporo.utils import dt_to_time_str, time_str_to_dt

LOGGER = logging.getLogger(__name__)

DATABASE_NAME = "sapporo.db"


class PageTokenData(BaseModel):
    start_time: str
    run_id: str


@cache
def create_db_engine() -> Engine:
    engine = create_engine(
        f"sqlite:///{get_config().run_dir}/{DATABASE_NAME}",
        echo=get_config().debug,
        connect_args={"check_same_thread": False},
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))
    return engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session.

    With WAL mode enabled, SQLite handles read concurrency internally.
    Write serialization is managed by SQLite's internal locking and busy_timeout.
    """
    session = Session(create_db_engine())
    try:
        yield session
    finally:
        session.close()


# === Models ===


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    run_id: str = Field(primary_key=True)
    username: str | None = None
    state: State
    start_time: datetime
    end_time: datetime | None = None
    tags: str  # JSON string, Dict[str, str]


def db_runs_to_run_summaries(runs: list[Run]) -> list[RunSummary]:
    return [
        RunSummary(
            run_id=run.run_id,
            state=run.state,
            start_time=dt_to_time_str(run.start_time),
            end_time=dt_to_time_str(run.end_time) if run.end_time is not None else None,
            tags=json.loads(run.tags),
        )
        for run in runs
    ]


# === CRUD func ===


def _full_rebuild(session: Session, disk_run_ids: set[str]) -> None:
    """Full rebuild: index all runs from disk."""
    count = 0
    for run_id in disk_run_ids:
        run_summary = create_run_summary(run_id)
        username: str | None = read_file(run_id, "username")
        run = Run(
            run_id=run_summary.run_id,
            username=username,
            state=run_summary.state,
            start_time=run_summary.start_time and time_str_to_dt(run_summary.start_time),
            end_time=run_summary.end_time and time_str_to_dt(run_summary.end_time),
            tags=json.dumps(run_summary.tags),
        )
        session.add(run)
        count += 1
    session.commit()
    LOGGER.debug("DB initialized: %d runs indexed", count)


def _incremental_sync(session: Session, disk_run_ids: set[str]) -> None:
    """Incremental sync: add new, update non-terminal, remove deleted."""
    db_runs = session.exec(select(Run)).all()
    db_run_map = {r.run_id: r for r in db_runs}
    db_run_ids = set(db_run_map.keys())

    terminal_states = {State.COMPLETE, State.EXECUTOR_ERROR, State.SYSTEM_ERROR, State.CANCELED, State.DELETED}

    added = 0
    for run_id in disk_run_ids - db_run_ids:
        run_summary = create_run_summary(run_id)
        username: str | None = read_file(run_id, "username")
        run = Run(
            run_id=run_summary.run_id,
            username=username,
            state=run_summary.state,
            start_time=run_summary.start_time and time_str_to_dt(run_summary.start_time),
            end_time=run_summary.end_time and time_str_to_dt(run_summary.end_time),
            tags=json.dumps(run_summary.tags),
        )
        session.add(run)
        added += 1

    updated = 0
    for run_id, db_run in db_run_map.items():
        if run_id not in disk_run_ids:
            continue
        if db_run.state in terminal_states:
            continue
        run_summary = create_run_summary(run_id)
        db_run.state = run_summary.state or State.UNKNOWN
        db_run.end_time = time_str_to_dt(run_summary.end_time) if run_summary.end_time else None
        session.add(db_run)
        updated += 1

    removed = 0
    for run_id in db_run_ids - disk_run_ids:
        db_run = db_run_map[run_id]
        session.delete(db_run)
        removed += 1

    session.commit()
    LOGGER.debug("DB synced: added=%d, updated=%d, removed=%d", added, updated, removed)


def init_db() -> None:
    """Initialize or incrementally update the database.

    On first run (no DB file), creates the schema and indexes all runs.
    On subsequent runs, performs an incremental sync:
    - Adds new runs not yet in the DB.
    - Updates state/end_time for runs in non-terminal states.
    - Removes DB entries for runs whose directories have been deleted.
    """
    engine = create_db_engine()
    get_config().run_dir.mkdir(parents=True, exist_ok=True)

    db_exists = get_config().run_dir.joinpath(DATABASE_NAME).exists()
    SQLModel.metadata.create_all(engine)

    disk_run_ids = set(glob_all_run_ids())

    with get_session() as session:
        if not db_exists:
            _full_rebuild(session, disk_run_ids)
        else:
            _incremental_sync(session, disk_run_ids)


def add_run_db(
    run_summary: RunSummary,
    username: str | None = None,
) -> Run:
    """Add a run record to the database.

    Called at POST /runs. Since it is called after generating a uuid (run_id), id conflicts are unlikely to occur.
    """
    run = Run(
        run_id=run_summary.run_id,
        username=username,
        state=run_summary.state or State.UNKNOWN,
        start_time=run_summary.start_time and time_str_to_dt(run_summary.start_time),
        end_time=run_summary.end_time and time_str_to_dt(run_summary.end_time),
        tags=json.dumps(run_summary.tags),
    )
    with get_session() as session:
        session.add(run)
        session.commit()
        session.refresh(run)

    return run


def system_state_counts(username: str | None = None) -> dict[str, int]:
    """Get the count of runs in each state.

    Args:
        username: If provided, only count runs belonging to this user.
                  If None, count all runs (for backward compatibility).

    """
    query = select(Run.state, func.count(Run.run_id)).group_by(Run.state)  # type: ignore[arg-type]
    if username is not None:
        query = query.where(Run.username == username)

    with get_session() as session:
        results = session.exec(query).all()

    return {state.value: 0 for state in State} | dict(results)


_PAGE_TOKEN_SECRET: str = secrets.token_urlsafe(32)


def _get_page_token_secret() -> str:
    """Get the secret key for signing page tokens.

    Uses an independent random secret generated at process startup.
    Page tokens are session-scoped, so a reset on restart is acceptable.
    """
    return _PAGE_TOKEN_SECRET


def _sign_data(data: str) -> str:
    """Create HMAC-SHA256 signature for the given data."""
    secret = _get_page_token_secret().encode("utf-8")
    signature = hmac.new(secret, data.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature).decode("utf-8")


def _encode_page_token(last_run: Run) -> str:
    """Encode a page token with HMAC signature for tamper protection."""
    token_data = {
        "start_time": last_run.start_time.isoformat(),
        "run_id": last_run.run_id,
    }
    data = json.dumps(token_data)
    signature = _sign_data(data)
    encoded_data = base64.urlsafe_b64encode(data.encode("utf-8")).decode("utf-8")
    return f"{encoded_data}.{signature}"


def _decode_page_token(page_token: str) -> PageTokenData:
    """Decode and verify a page token's HMAC signature."""
    try:
        expected_parts = 2
        parts = page_token.split(".")
        if len(parts) != expected_parts:
            raise_bad_request("Invalid page token format")

        encoded_data, provided_signature = parts
        data = base64.urlsafe_b64decode(encoded_data).decode("utf-8")

        # Verify signature using constant-time comparison
        expected_signature = _sign_data(data)
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise_bad_request("Invalid page token signature")

        return PageTokenData.model_validate_json(data)
    except (ValueError, UnicodeDecodeError, binascii.Error, ValidationError):
        raise_bad_request("Invalid page token")


def _build_filter_query(
    query: Any,
    state: State | None = None,
    run_ids: list[str] | None = None,
    username: str | None = None,
    tags: list[str] | None = None,
) -> Any:
    if state is not None:
        query = query.where(Run.state == state)
    if username is not None:
        query = query.where(Run.username == username)
    if run_ids is not None:
        query = query.where(Run.run_id.in_(run_ids))  # type: ignore[attr-defined]
    if tags is not None:
        tag_key_pattern = re.compile(r"^[a-zA-Z0-9_.\-]+$")
        for tag in tags:
            key, _, value = tag.partition(":")
            if key and value:
                if not tag_key_pattern.match(key):
                    raise_bad_request(f"Invalid tag key: {key}")
                query = query.where(func.json_extract(Run.tags, f"$.{key}") == value)
    return query


def count_runs_db(
    state: State | None = None,
    run_ids: list[str] | None = None,
    username: str | None = None,
    tags: list[str] | None = None,
) -> int:
    query = select(func.count()).select_from(Run)
    query = _build_filter_query(query, state, run_ids, username, tags)
    with get_session() as session:
        result: int = session.exec(query).one()
        return result


def list_runs_db(
    page_size: int,
    page_token: str | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
    state: State | None = None,
    run_ids: list[str] | None = None,
    username: str | None = None,
    tags: list[str] | None = None,
) -> tuple[list[Run], str | None]:
    query = select(Run)
    query = _build_filter_query(query, state, run_ids, username, tags)

    if sort_order == "asc":
        query = query.order_by(Run.start_time.asc(), Run.run_id.asc())  # type: ignore[attr-defined]
    else:
        query = query.order_by(Run.start_time.desc(), Run.run_id.desc())  # type: ignore[attr-defined]

    if page_token is not None:
        token_data = _decode_page_token(page_token)
        start_time = datetime.fromisoformat(token_data.start_time)
        run_id = token_data.run_id
        if sort_order == "asc":
            query = query.where(
                (Run.start_time > start_time) | ((Run.start_time == start_time) & (Run.run_id > run_id))
            )
        else:
            query = query.where(
                (Run.start_time < start_time) | ((Run.start_time == start_time) & (Run.run_id < run_id))
            )

    query = query.limit(page_size + 1)

    with get_session() as session:
        results = session.exec(query).all()
    results = list(results)
    if len(results) > page_size:
        next_page_token = _encode_page_token(results[page_size - 1])
        results = results[:page_size]
    else:
        next_page_token = None

    return results, next_page_token


def list_old_runs_db(
    older_than_days: int,
) -> list[Run]:
    with get_session() as session:
        cutoff_date = datetime.now(tz=timezone.utc) - timedelta(days=older_than_days)
        query = select(Run).where(Run.start_time < cutoff_date)
        results = session.exec(query).all()

    return list(results)


if __name__ == "__main__":
    init_db()
