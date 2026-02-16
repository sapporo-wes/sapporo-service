import json
import sys
from datetime import datetime, timezone

import pytest

from sapporo.config import get_config
from sapporo.database import (
    Run,
    count_runs_db,
    get_session,
    init_db,
    list_runs_db,
)
from sapporo.schemas import State


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
