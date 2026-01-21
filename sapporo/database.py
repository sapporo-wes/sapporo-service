"""\
Module for creating an SQLite database, `{run_dir}/sapporo.db`, within the run directory.
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
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, Generator, List, Literal, Optional, Tuple

from pydantic import BaseModel, ValidationError
from sqlalchemy import func
from sqlalchemy.engine.base import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from sapporo.config import get_config
from sapporo.exceptions import raise_bad_request
from sapporo.factory import create_run_summary
from sapporo.run import glob_all_run_ids, read_file
from sapporo.schemas import RunSummary, State
from sapporo.utils import dt_to_time_str, time_str_to_dt

SNAPSHOT_INTERVAL = 30  # minutes
DATABASE_NAME = "sapporo.db"

# Thread lock for SQLite operations to ensure thread safety
_db_lock = threading.Lock()


class PageTokenData(BaseModel):
    start_time: str
    run_id: str


@lru_cache(maxsize=None)
def create_db_engine() -> Engine:
    return create_engine(
        f"sqlite:///{get_config().run_dir}/{DATABASE_NAME}",
        echo=get_config().debug,
        connect_args={"check_same_thread": False},
    )


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Get a database session with thread-safe access.

    Uses a threading lock to ensure only one thread can access
    the SQLite database at a time, preventing potential data corruption.
    """
    with _db_lock:
        session = Session(create_db_engine())
        try:
            yield session
        finally:
            session.close()


# === Models ===


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    run_id: str = Field(primary_key=True)
    username: Optional[str] = None
    state: State
    start_time: datetime
    end_time: Optional[datetime] = None
    tags: str  # JSON string, Dict[str, str]


def db_runs_to_run_summaries(runs: List[Run]) -> List[RunSummary]:
    return [RunSummary(
        run_id=run.run_id,
        state=run.state,
        start_time=dt_to_time_str(run.start_time),
        end_time=dt_to_time_str(run.end_time) if run.end_time is not None else None,
        tags=json.loads(run.tags),
    ) for run in runs]


# === CRUD func ===


def init_db() -> None:
    """\
    Master data is stored under the each run directory, so if an existing database is found,
    it will be deleted and regenerated from scratch.
    """
    engine = create_db_engine()
    get_config().run_dir.mkdir(parents=True, exist_ok=True)
    if get_config().run_dir.joinpath(DATABASE_NAME).exists():
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with get_session() as session:
        for run_id in glob_all_run_ids():
            run_summary = create_run_summary(run_id)
            username: Optional[str] = read_file(run_id, "username")
            run = Run(
                run_id=run_summary.run_id,
                username=username,
                state=run_summary.state,
                start_time=run_summary.start_time and time_str_to_dt(run_summary.start_time),
                end_time=run_summary.end_time and time_str_to_dt(run_summary.end_time),
                tags=json.dumps(run_summary.tags),
            )
            session.add(run)
        session.commit()


def add_run_db(
    run_summary: RunSummary,
    username: Optional[str] = None,
) -> Run:
    """\
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


def system_state_counts(username: Optional[str] = None) -> Dict[str, int]:
    """
    Get the count of runs in each state.

    Args:
        username: If provided, only count runs belonging to this user.
                  If None, count all runs (for backward compatibility).
    """
    query = select(Run.state, func.count(Run.run_id)).group_by(Run.state)  # type: ignore # pylint: disable=E1102
    if username is not None:
        query = query.where(Run.username == username)

    with get_session() as session:
        results = session.exec(query).all()

    state_counts = {state.value: 0 for state in State}
    for state, count in results:
        state_counts[state] = count

    return state_counts


def _get_page_token_secret() -> str:
    """Get the secret key for signing page tokens."""
    # Import here to avoid circular imports
    from sapporo.auth import \
        get_auth_config  # pylint: disable=import-outside-toplevel
    return get_auth_config().sapporo_auth_config.secret_key


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
    # Format: base64(data).signature
    encoded_data = base64.urlsafe_b64encode(data.encode("utf-8")).decode("utf-8")
    return f"{encoded_data}.{signature}"


def _decode_page_token(page_token: str) -> PageTokenData:
    """Decode and verify a page token's HMAC signature."""
    try:
        parts = page_token.split(".")
        if len(parts) != 2:
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


def list_runs_db(
    page_size: int,
    page_token: Optional[str] = None,
    sort_order: Literal["asc", "desc"] = "desc",
    state: Optional[State] = None,
    run_ids: Optional[List[str]] = None,
    username: Optional[str] = None,
) -> Tuple[List[Run], Optional[str]]:
    query = select(Run)

    if state is not None:
        query = query.where(Run.state == state)

    if username is not None:
        query = query.where(Run.username == username)

    if sort_order == "asc":
        query = query.order_by(Run.start_time.asc(), Run.run_id.asc())  # type: ignore[attr-defined] # pylint: disable=E1101
    else:
        query = query.order_by(Run.start_time.desc(), Run.run_id.desc())  # type: ignore[attr-defined] # pylint: disable=E1101

    if run_ids is not None:
        query = query.where(Run.run_id.in_(run_ids))  # type: ignore[attr-defined] # pylint: disable=E1101

    if page_token is not None:
        token_data = _decode_page_token(page_token)
        start_time = datetime.fromisoformat(token_data.start_time)
        run_id = token_data.run_id
        if sort_order == "asc":
            query = query.where(
                (Run.start_time > start_time) |
                ((Run.start_time == start_time) & (Run.run_id > run_id))
            )
        else:
            query = query.where(
                (Run.start_time < start_time) |
                ((Run.start_time == start_time) & (Run.run_id < run_id))
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
) -> List[Run]:
    with get_session() as session:
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        query = select(Run).where(Run.start_time < cutoff_date)
        results = session.exec(query).all()

    return list(results)


if __name__ == "__main__":
    init_db()
