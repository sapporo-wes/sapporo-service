import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sapporo.config import AppConfig, get_config
from sapporo.database import (
    DATABASE_NAME,
    Run,
    _decode_page_token,
    _encode_page_token,
    _sign_data,
    add_run_db,
    count_runs_db,
    db_runs_to_run_summaries,
    get_session,
    init_db,
    list_old_runs_db,
    list_runs_db,
    system_state_counts,
)
from sapporo.schemas import RunSummary, State
from tests.unit.conftest import create_run_dir, mock_get_config

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def _seed_runs(tmp_path: object) -> None:
    """Seed the database with test runs.

    Sets --run-dir to tmp_path, clears config cache, and initializes the DB.
    """
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()
    runs = [
        Run(
            run_id="run-1",
            username="alice",
            state=State.COMPLETE,
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 0, 10, tzinfo=timezone.utc),
            tags=json.dumps({"project": "genomics", "env": "production"}),
        ),
        Run(
            run_id="run-2",
            username="alice",
            state=State.RUNNING,
            start_time=datetime(2024, 1, 2, tzinfo=timezone.utc),
            tags=json.dumps({"project": "genomics", "env": "staging"}),
        ),
        Run(
            run_id="run-3",
            username="bob",
            state=State.COMPLETE,
            start_time=datetime(2024, 1, 3, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 3, 0, 5, tzinfo=timezone.utc),
            tags=json.dumps({"project": "proteomics"}),
        ),
        Run(
            run_id="run-4",
            username="bob",
            state=State.QUEUED,
            start_time=datetime(2024, 1, 4, tzinfo=timezone.utc),
            tags=json.dumps({}),
        ),
    ]
    with get_session() as session:
        for run in runs:
            session.add(run)
        session.commit()


# === tags filtering in list_runs_db ===


@pytest.mark.usefixtures("_seed_runs")
class TestListRunsDbTagsFiltering:
    def test_single_tag_filters_matching_runs(self) -> None:
        runs, _ = list_runs_db(page_size=10, tags=["project:genomics"])
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"run-1", "run-2"}

    def test_multiple_tags_use_and_logic(self) -> None:
        runs, _ = list_runs_db(page_size=10, tags=["project:genomics", "env:production"])
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"run-1"}

    def test_no_matching_tags_returns_empty(self) -> None:
        runs, _ = list_runs_db(page_size=10, tags=["project:nonexistent"])
        assert runs == []

    def test_malformed_tag_without_colon_is_ignored(self) -> None:
        runs, _ = list_runs_db(page_size=10, tags=["malformed"])
        assert len(runs) == 4

    def test_tag_with_empty_key_is_ignored(self) -> None:
        runs, _ = list_runs_db(page_size=10, tags=[":value"])
        assert len(runs) == 4

    def test_tags_combined_with_state_filter(self) -> None:
        runs, _ = list_runs_db(page_size=10, state=State.COMPLETE, tags=["project:genomics"])
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"run-1"}

    def test_tags_combined_with_username_filter(self) -> None:
        runs, _ = list_runs_db(page_size=10, username="alice", tags=["project:genomics"])
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"run-1", "run-2"}

    def test_empty_tags_dict_not_matched_by_tag_filter(self) -> None:
        runs, _ = list_runs_db(page_size=10, tags=["project:genomics"])
        run_ids = {r.run_id for r in runs}
        assert "run-4" not in run_ids


# === count_runs_db ===


@pytest.mark.usefixtures("_seed_runs")
class TestCountRunsDb:
    def test_count_all_runs(self) -> None:
        assert count_runs_db() == 4

    def test_count_with_state_filter(self) -> None:
        assert count_runs_db(state=State.COMPLETE) == 2

    def test_count_with_username_filter(self) -> None:
        assert count_runs_db(username="alice") == 2

    def test_count_with_run_ids_filter(self) -> None:
        assert count_runs_db(run_ids=["run-1", "run-3"]) == 2

    def test_count_with_tags_filter(self) -> None:
        assert count_runs_db(tags=["project:genomics"]) == 2

    def test_count_with_multiple_filters(self) -> None:
        assert count_runs_db(state=State.COMPLETE, tags=["project:genomics"]) == 1

    def test_count_with_no_matches_returns_zero(self) -> None:
        assert count_runs_db(tags=["project:nonexistent"]) == 0


# === init_db ===


def test_init_db_creates_database_file(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()
    assert tmp_path.joinpath(DATABASE_NAME).exists()


def test_init_db_rebuilds_from_run_dirs(mocker: "MockerFixture", tmp_path: Path) -> None:
    config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, config)

    run_id = "aabbccdd-0000-0000-0000-000000000100"
    create_run_dir(tmp_path, run_id)

    init_db()

    with get_session() as session:
        from sqlmodel import select

        runs = session.exec(select(Run)).all()
        run_ids = {r.run_id for r in runs}
        assert run_id in run_ids


def test_init_db_drops_existing_tables_first(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    # Add a record
    with get_session() as session:
        session.add(
            Run(
                run_id="temp-run",
                state=State.COMPLETE,
                start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tags="{}",
            )
        )
        session.commit()

    # Re-init should drop and recreate
    get_config.cache_clear()
    init_db()

    with get_session() as session:
        from sqlmodel import select

        runs = session.exec(select(Run)).all()
        # temp-run should be gone since no run directory exists for it
        assert all(r.run_id != "temp-run" for r in runs)


# === add_run_db ===


def test_add_run_db_inserts_run_record(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    summary = RunSummary(
        run_id="add-test-1",
        state=State.RUNNING,
        start_time="2024-06-01T00:00:00Z",
        tags={"key": "val"},
    )
    result = add_run_db(summary)

    assert result.run_id == "add-test-1"
    assert result.state == State.RUNNING


def test_add_run_db_stores_username(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    summary = RunSummary(
        run_id="add-test-2",
        state=State.QUEUED,
        start_time="2024-06-01T00:00:00Z",
        tags={},
    )
    result = add_run_db(summary, username="alice")
    assert result.username == "alice"


def test_add_run_db_stores_none_username(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    summary = RunSummary(
        run_id="add-test-3",
        state=State.QUEUED,
        start_time="2024-06-01T00:00:00Z",
        tags={},
    )
    result = add_run_db(summary, username=None)
    assert result.username is None


def test_add_run_db_stores_tags_as_json_string(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    tags = {"project": "genomics", "env": "prod"}
    summary = RunSummary(
        run_id="add-test-4",
        state=State.COMPLETE,
        start_time="2024-06-01T00:00:00Z",
        tags=tags,
    )
    result = add_run_db(summary)
    assert json.loads(result.tags) == tags


# === system_state_counts ===


@pytest.mark.usefixtures("_seed_runs")
class TestSystemStateCounts:
    def test_system_state_counts_all_users(self) -> None:
        counts = system_state_counts()
        assert counts["COMPLETE"] == 2
        assert counts["RUNNING"] == 1
        assert counts["QUEUED"] == 1

    def test_system_state_counts_specific_user(self) -> None:
        counts = system_state_counts(username="alice")
        assert counts["COMPLETE"] == 1
        assert counts["RUNNING"] == 1
        assert counts.get("QUEUED", 0) == 0

    def test_system_state_counts_empty_db_returns_all_zero(self, tmp_path: Path) -> None:
        sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
        get_config.cache_clear()
        init_db()

        counts = system_state_counts()
        for state in State:
            assert counts[state.value] == 0

    def test_system_state_counts_includes_all_state_values(self) -> None:
        counts = system_state_counts()
        for state in State:
            assert state.value in counts


# === list_old_runs_db ===


@pytest.mark.usefixtures("_seed_runs")
class TestListOldRunsDb:
    def test_list_old_runs_db_returns_runs_older_than_days(self) -> None:
        # All seed runs are from January 2024, definitely > 1 day old
        old_runs = list_old_runs_db(older_than_days=1)
        assert len(old_runs) == 4

    def test_list_old_runs_db_excludes_recent_runs(self) -> None:
        # Seed runs are from 2024-01-01..04. Set cutoff to 1 day before the earliest run.
        # Using older_than_days large enough to predate 2024 runs would overflow.
        # Instead, add a recent run and verify it's excluded.
        with get_session() as session:
            session.add(
                Run(
                    run_id="recent-run",
                    state=State.COMPLETE,
                    start_time=datetime.now(tz=timezone.utc),
                    tags="{}",
                )
            )
            session.commit()
        old_runs = list_old_runs_db(older_than_days=1)
        old_ids = {r.run_id for r in old_runs}
        assert "recent-run" not in old_ids

    def test_list_old_runs_db_empty_result(self, tmp_path: Path) -> None:
        sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
        get_config.cache_clear()
        init_db()

        old_runs = list_old_runs_db(older_than_days=1)
        assert old_runs == []

    def test_list_old_runs_db_zero_days_returns_all_past_runs(self) -> None:
        old_runs = list_old_runs_db(older_than_days=0)
        assert len(old_runs) == 4

    def test_list_old_runs_db_boundary_cutoff(self) -> None:
        """Run exactly at the cutoff boundary is included."""
        from datetime import timedelta

        cutoff_days = 5
        cutoff_time = datetime.now(tz=timezone.utc) - timedelta(days=cutoff_days)
        with get_session() as session:
            session.add(
                Run(
                    run_id="boundary-exact",
                    state=State.COMPLETE,
                    start_time=cutoff_time - timedelta(seconds=1),
                    tags="{}",
                )
            )
            session.add(
                Run(
                    run_id="boundary-just-after",
                    state=State.COMPLETE,
                    start_time=cutoff_time + timedelta(seconds=1),
                    tags="{}",
                )
            )
            session.commit()

        old_runs = list_old_runs_db(older_than_days=cutoff_days)
        old_ids = {r.run_id for r in old_runs}
        assert "boundary-exact" in old_ids
        assert "boundary-just-after" not in old_ids


# === db_runs_to_run_summaries ===


class TestDbRunsToRunSummaries:
    def test_db_runs_to_run_summaries_converts_correctly(self) -> None:
        runs = [
            Run(
                run_id="conv-1",
                state=State.COMPLETE,
                start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_time=datetime(2024, 1, 1, 0, 10, tzinfo=timezone.utc),
                tags=json.dumps({"k": "v"}),
            )
        ]
        summaries = db_runs_to_run_summaries(runs)
        assert len(summaries) == 1
        assert summaries[0].run_id == "conv-1"
        assert summaries[0].state == State.COMPLETE
        assert summaries[0].tags == {"k": "v"}

    def test_db_runs_to_run_summaries_handles_none_end_time(self) -> None:
        runs = [
            Run(
                run_id="conv-2",
                state=State.RUNNING,
                start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end_time=None,
                tags=json.dumps({}),
            )
        ]
        summaries = db_runs_to_run_summaries(runs)
        assert summaries[0].end_time is None

    def test_db_runs_to_run_summaries_parses_tags_json(self) -> None:
        tags = {"project": "genomics", "env": "production"}
        runs = [
            Run(
                run_id="conv-3",
                state=State.COMPLETE,
                start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tags=json.dumps(tags),
            )
        ]
        summaries = db_runs_to_run_summaries(runs)
        assert summaries[0].tags == tags

    def test_db_runs_to_run_summaries_empty_list(self) -> None:
        assert db_runs_to_run_summaries([]) == []


# === page token (HMAC) ===


@pytest.mark.usefixtures("_seed_runs")
class TestPageToken:
    def test_encode_decode_page_token_roundtrip(self) -> None:
        run = Run(
            run_id="token-1",
            state=State.COMPLETE,
            start_time=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            tags="{}",
        )
        token = _encode_page_token(run)
        decoded = _decode_page_token(token)
        assert decoded.run_id == "token-1"
        assert "2024-06-15" in decoded.start_time

    @settings(max_examples=20)
    @given(
        run_id=st.text(min_size=1, max_size=36, alphabet="abcdef0123456789-"),
    )
    def test_encode_decode_page_token_roundtrip_arbitrary_data(self, run_id: str) -> None:
        run = Run(
            run_id=run_id,
            state=State.COMPLETE,
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tags="{}",
        )
        token = _encode_page_token(run)
        decoded = _decode_page_token(token)
        assert decoded.run_id == run_id

    def test_decode_page_token_invalid_format_raises_400(self) -> None:
        from starlette.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_page_token("no-dot-separator")
        assert exc_info.value.status_code == 400

    def test_decode_page_token_tampered_signature_raises_400(self) -> None:
        from starlette.exceptions import HTTPException

        run = Run(
            run_id="tamper-test",
            state=State.COMPLETE,
            start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tags="{}",
        )
        token = _encode_page_token(run)
        parts = token.split(".")
        parts[1] = parts[1][:-4] + "XXXX"  # Tamper with signature
        tampered_token = ".".join(parts)

        with pytest.raises(HTTPException) as exc_info:
            _decode_page_token(tampered_token)
        assert exc_info.value.status_code == 400

    def test_decode_page_token_invalid_base64_raises_400(self) -> None:
        from starlette.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_page_token("!!!invalid-base64!!!.fakesig")
        assert exc_info.value.status_code == 400

    def test_sign_data_produces_consistent_result(self) -> None:
        sig1 = _sign_data("test-data")
        sig2 = _sign_data("test-data")
        assert sig1 == sig2

    @settings(max_examples=20)
    @given(
        data1=st.text(min_size=1, max_size=50),
        data2=st.text(min_size=1, max_size=50),
    )
    def test_sign_data_different_input_different_signature(self, data1: str, data2: str) -> None:
        if data1 != data2:
            sig1 = _sign_data(data1)
            sig2 = _sign_data(data2)
            assert sig1 != sig2


# === list_runs_db additional tests (pagination, sort) ===


@pytest.mark.usefixtures("_seed_runs")
class TestListRunsDbPaginationSort:
    def test_list_runs_db_pagination_with_page_token(self) -> None:
        runs1, next_token = list_runs_db(page_size=2)
        assert len(runs1) == 2
        assert next_token is not None

        runs2, _ = list_runs_db(page_size=2, page_token=next_token)
        assert len(runs2) == 2

        all_ids = {r.run_id for r in runs1} | {r.run_id for r in runs2}
        assert len(all_ids) == 4

    def test_list_runs_db_asc_sort_order(self) -> None:
        runs, _ = list_runs_db(page_size=10, sort_order="asc")
        start_times = [r.start_time for r in runs]
        assert start_times == sorted(start_times)

    def test_list_runs_db_desc_sort_order(self) -> None:
        runs, _ = list_runs_db(page_size=10, sort_order="desc")
        start_times = [r.start_time for r in runs]
        assert start_times == sorted(start_times, reverse=True)

    def test_list_runs_db_next_page_token_when_more_results(self) -> None:
        _, next_token = list_runs_db(page_size=2)
        assert next_token is not None

    def test_list_runs_db_no_next_page_token_when_all_fit(self) -> None:
        _, next_token = list_runs_db(page_size=100)
        assert next_token is None


# === list_runs_db: cursor accuracy tests ===


@pytest.mark.usefixtures("_seed_runs")
class TestListRunsDbCursorAccuracy:
    def test_page_size_1_desc_yields_correct_order(self) -> None:
        collected_ids: list[str] = []
        token: str | None = None
        for _ in range(4):
            runs, token = list_runs_db(page_size=1, page_token=token)
            assert len(runs) == 1
            collected_ids.append(runs[0].run_id)
        assert collected_ids == ["run-4", "run-3", "run-2", "run-1"]
        # After all pages, token should be None (no more pages)
        assert token is None

    def test_page_size_1_asc_yields_correct_order(self) -> None:
        collected_ids: list[str] = []
        token: str | None = None
        for _ in range(4):
            runs, token = list_runs_db(page_size=1, page_token=token, sort_order="asc")
            assert len(runs) == 1
            collected_ids.append(runs[0].run_id)
        assert collected_ids == ["run-1", "run-2", "run-3", "run-4"]

    def test_no_overlap_between_pages(self) -> None:
        runs1, token = list_runs_db(page_size=2)
        assert token is not None
        runs2, _ = list_runs_db(page_size=2, page_token=token)

        ids1 = {r.run_id for r in runs1}
        ids2 = {r.run_id for r in runs2}
        assert ids1.isdisjoint(ids2)

    def test_page_size_exact_count_no_next_token(self) -> None:
        _, token = list_runs_db(page_size=4)
        assert token is None

    def test_page_size_plus_one_has_next_token(self) -> None:
        # 4 runs exist, page_size=3 means 4 > 3, so next_page_token should exist
        runs, token = list_runs_db(page_size=3)
        assert len(runs) == 3
        assert token is not None

    def test_state_filter_with_page_size_1_full_scan(self) -> None:
        collected_ids: list[str] = []
        token: str | None = None
        while True:
            runs, token = list_runs_db(page_size=1, page_token=token, state=State.COMPLETE)
            if not runs:
                break
            collected_ids.append(runs[0].run_id)
            if token is None:
                break
        assert set(collected_ids) == {"run-1", "run-3"}


# === list_runs_db: same start_time sorting ===


def test_list_runs_db_same_start_time_sorted_by_run_id(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    same_time = datetime(2024, 6, 1, tzinfo=timezone.utc)
    runs_data = [
        Run(run_id="ccc-run", state=State.COMPLETE, start_time=same_time, tags="{}"),
        Run(run_id="aaa-run", state=State.COMPLETE, start_time=same_time, tags="{}"),
        Run(run_id="bbb-run", state=State.COMPLETE, start_time=same_time, tags="{}"),
    ]
    with get_session() as session:
        for r in runs_data:
            session.add(r)
        session.commit()

    # desc order: by run_id desc when start_time is equal
    runs, _ = list_runs_db(page_size=10, sort_order="desc")
    ids = [r.run_id for r in runs]
    assert ids == ["ccc-run", "bbb-run", "aaa-run"]

    # asc order: by run_id asc
    runs, _ = list_runs_db(page_size=10, sort_order="asc")
    ids = [r.run_id for r in runs]
    assert ids == ["aaa-run", "bbb-run", "ccc-run"]


def test_list_runs_db_same_start_time_pagination_no_overlap(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    same_time = datetime(2024, 6, 1, tzinfo=timezone.utc)
    for i in range(3):
        with get_session() as session:
            session.add(Run(run_id=f"same-{i:02d}", state=State.COMPLETE, start_time=same_time, tags="{}"))
            session.commit()

    all_ids: list[str] = []
    token: str | None = None
    for _ in range(3):
        runs, token = list_runs_db(page_size=1, page_token=token)
        assert len(runs) == 1
        all_ids.append(runs[0].run_id)
    # No duplicates
    assert len(set(all_ids)) == 3


# === _decode_page_token: detailed value tests ===


@pytest.mark.usefixtures("_seed_runs")
class TestDecodePageTokenDetailed:
    def test_roundtrip_preserves_exact_values(self) -> None:
        start_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        run = Run(run_id="exact-val-test", state=State.COMPLETE, start_time=start_time, tags="{}")
        token = _encode_page_token(run)
        decoded = _decode_page_token(token)

        assert decoded.run_id == "exact-val-test"
        assert decoded.start_time == start_time.isoformat()

    def test_token_with_three_dots_raises_400(self) -> None:
        from starlette.exceptions import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            _decode_page_token("part1.part2.part3")
        assert exc_info.value.status_code == 400

    def test_token_with_valid_base64_but_invalid_json_raises_400(self) -> None:
        from starlette.exceptions import HTTPException

        invalid_json = base64.urlsafe_b64encode(b"not-json").decode("utf-8")
        sig = _sign_data("not-json")
        token = f"{invalid_json}.{sig}"

        with pytest.raises(HTTPException) as exc_info:
            _decode_page_token(token)
        assert exc_info.value.status_code == 400

    @settings(max_examples=20)
    @given(
        run_id=st.text(min_size=1, max_size=36, alphabet="abcdef0123456789-"),
        year=st.integers(min_value=2000, max_value=2030),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
    )
    def test_roundtrip_arbitrary_start_time_and_run_id(self, run_id: str, year: int, month: int, day: int) -> None:
        start_time = datetime(year, month, day, tzinfo=timezone.utc)
        run = Run(run_id=run_id, state=State.COMPLETE, start_time=start_time, tags="{}")
        token = _encode_page_token(run)
        decoded = _decode_page_token(token)
        assert decoded.run_id == run_id
        assert decoded.start_time == start_time.isoformat()


# === init_db: additional tests ===


def test_init_db_rebuilds_run_fields_correctly(mocker: "MockerFixture", tmp_path: Path) -> None:
    config = AppConfig(run_dir=tmp_path)
    mock_get_config(mocker, config)

    run_id = "aabbccdd-0000-0000-0000-000000000200"
    create_run_dir(
        tmp_path,
        run_id,
        state="RUNNING",
        start_time="2024-06-15T10:00:00Z",
        tags={"env": "test"},
        username="alice",
    )

    init_db()

    with get_session() as session:
        from sqlmodel import select

        run = session.exec(select(Run).where(Run.run_id == run_id)).one()
        assert run.state == State.RUNNING
        assert run.username == "alice"
        assert json.loads(run.tags) == {"env": "test"}
        assert run.start_time is not None


def test_init_db_empty_run_dir_creates_empty_table(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    with get_session() as session:
        from sqlmodel import select

        runs = session.exec(select(Run)).all()
        assert runs == []


def test_init_db_no_existing_db_file_creates_new(tmp_path: Path) -> None:
    db_path = tmp_path / DATABASE_NAME
    assert not db_path.exists()

    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    assert db_path.exists()
    with get_session() as session:
        from sqlmodel import select

        runs = session.exec(select(Run)).all()
        assert runs == []


# === db_runs_to_run_summaries: additional tests ===


class TestDbRunsToRunSummariesAdditional:
    def test_start_time_format_ends_with_z(self) -> None:
        runs = [
            Run(
                run_id="fmt-1",
                state=State.COMPLETE,
                start_time=datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
                tags="{}",
            )
        ]
        summaries = db_runs_to_run_summaries(runs)
        assert summaries[0].start_time is not None
        assert summaries[0].start_time.endswith("Z")

    def test_tags_multiple_keys_parsed_correctly(self) -> None:
        tags = {"project": "genomics", "env": "production", "team": "bio"}
        runs = [
            Run(
                run_id="multi-tag",
                state=State.COMPLETE,
                start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tags=json.dumps(tags),
            )
        ]
        summaries = db_runs_to_run_summaries(runs)
        assert summaries[0].tags == tags
        assert len(summaries[0].tags) == 3

    @settings(max_examples=20)
    @given(
        tags=st.dictionaries(
            keys=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
            values=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"),
            max_size=5,
        ),
    )
    def test_tags_roundtrip_arbitrary_dict(self, tags: dict[str, str]) -> None:
        runs = [
            Run(
                run_id="pbt-tags",
                state=State.COMPLETE,
                start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
                tags=json.dumps(tags),
            )
        ]
        summaries = db_runs_to_run_summaries(runs)
        assert summaries[0].tags == tags


# === add_run_db: start_time/end_time short-circuit tests ===


def test_add_run_db_with_start_and_end_time(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    summary = RunSummary(
        run_id="add-times",
        state=State.COMPLETE,
        start_time="2024-06-01T00:00:00Z",
        end_time="2024-06-01T01:00:00Z",
        tags={},
    )
    result = add_run_db(summary)
    # SQLite may not store timezone info; normalize both sides
    assert result.start_time.replace(tzinfo=timezone.utc) == datetime(2024, 6, 1, tzinfo=timezone.utc)
    assert result.end_time is not None
    assert result.end_time.replace(tzinfo=timezone.utc) == datetime(2024, 6, 1, 1, 0, 0, tzinfo=timezone.utc)


def test_add_run_db_with_none_end_time(tmp_path: Path) -> None:
    sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
    get_config.cache_clear()
    init_db()

    summary = RunSummary(
        run_id="add-no-end",
        state=State.RUNNING,
        start_time="2024-06-01T00:00:00Z",
        end_time=None,
        tags={},
    )
    result = add_run_db(summary)
    assert result.end_time is None


# === _sign_data: URL-safe base64 ===


@pytest.mark.usefixtures("_seed_runs")
class TestSignData:
    def test_sign_data_is_urlsafe_base64(self) -> None:
        sig = _sign_data("test-payload")
        # URL-safe base64 should not contain + or /
        assert "+" not in sig
        assert "/" not in sig
        # Should be decodable as URL-safe base64
        base64.urlsafe_b64decode(sig + "==")  # Padding may be needed


# === _build_filter_query: tag edge cases ===


@pytest.mark.usefixtures("_seed_runs")
class TestBuildFilterQueryTags:
    def test_tag_with_empty_value_is_ignored(self) -> None:
        runs, _ = list_runs_db(page_size=10, tags=["project:"])
        assert len(runs) == 4

    def test_tag_filter_with_both_key_and_value(self) -> None:
        runs, _ = list_runs_db(page_size=10, tags=["env:production"])
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"run-1"}


# === list_old_runs_db: boundary value test ===


@pytest.mark.usefixtures("_seed_runs")
class TestListOldRunsDbBoundary:
    def test_boundary_days_value_excludes_recent_runs(self) -> None:
        from datetime import timedelta

        cutoff_time = datetime.now(tz=timezone.utc) - timedelta(days=10)
        with get_session() as session:
            session.add(
                Run(
                    run_id="boundary-run",
                    state=State.COMPLETE,
                    start_time=cutoff_time - timedelta(hours=1),
                    tags="{}",
                )
            )
            session.commit()

        old_runs = list_old_runs_db(older_than_days=10)
        old_ids = {r.run_id for r in old_runs}
        assert "boundary-run" in old_ids

    def test_list_old_runs_large_days_returns_nothing_recent(self) -> None:
        with get_session() as session:
            session.add(
                Run(
                    run_id="very-recent",
                    state=State.COMPLETE,
                    start_time=datetime.now(tz=timezone.utc),
                    tags="{}",
                )
            )
            session.commit()

        old_runs = list_old_runs_db(older_than_days=365)
        old_ids = {r.run_id for r in old_runs}
        assert "very-recent" not in old_ids


# === system_state_counts: filtered username ===


@pytest.mark.usefixtures("_seed_runs")
class TestSystemStateCountsFiltered:
    def test_username_filter_excludes_other_users(self) -> None:
        counts = system_state_counts(username="bob")
        assert counts["COMPLETE"] == 1
        assert counts["QUEUED"] == 1
        assert counts.get("RUNNING", 0) == 0

    def test_nonexistent_username_returns_all_zero(self) -> None:
        counts = system_state_counts(username="nonexistent-user")
        for state in State:
            assert counts[state.value] == 0

    def test_single_state_only(self, tmp_path: Path) -> None:
        sys.argv = ["sapporo", "--run-dir", str(tmp_path)]
        get_config.cache_clear()
        init_db()

        with get_session() as session:
            session.add(
                Run(
                    run_id="only-running",
                    state=State.RUNNING,
                    start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    tags="{}",
                )
            )
            session.commit()

        counts = system_state_counts()
        assert counts["RUNNING"] == 1
        assert counts["COMPLETE"] == 0
        assert counts["QUEUED"] == 0
