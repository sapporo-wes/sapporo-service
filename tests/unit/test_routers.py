import importlib
import json
import logging
import os
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from tests.unit.conftest import (
    create_run_dir,
    create_test_client,
    default_auth_config_dict,
    write_auth_config,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


# === Helper ===


def _post_run_form(client: TestClient, **overrides: Any) -> Any:
    """Submit POST /runs with form data and return the response."""
    defaults = {
        "workflow_type": "CWL",
        "workflow_type_version": "v1.0",
        "workflow_engine": "cwltool",
        "workflow_url": "https://example.com/wf.cwl",
    }
    defaults.update(overrides)
    return client.post("/runs", data=defaults)


def _post_run_json(client: TestClient, **overrides: Any) -> Any:
    """Submit POST /runs with JSON body and return the response."""
    defaults: dict[str, Any] = {
        "workflow_type": "CWL",
        "workflow_type_version": "v1.0",
        "workflow_engine": "cwltool",
        "workflow_url": "https://example.com/wf.cwl",
    }
    defaults.update(overrides)
    return client.post("/runs", json=defaults)


def _client_with_mock_run_tasks(mocker: "MockerFixture", tmp_path: Path) -> TestClient:
    """Create a test client with run lifecycle tasks mocked out."""
    mocker.patch("sapporo.routers.post_run_task")
    mocker.patch("sapporo.routers.cancel_run_task")
    mocker.patch("sapporo.routers.delete_run_task")
    mocker.patch("sapporo.routers.bulk_delete_run_tasks")
    return create_test_client(mocker, tmp_path)


def _clear_module_caches() -> None:
    """Clear @cache-decorated functions via current module attributes.

    Unlike conftest._do_clear_caches which uses imported function references
    (which become stale after importlib.reload), this helper always accesses
    the current module attribute, so it works correctly across reloads.
    """
    import sapporo.auth
    import sapporo.config
    import sapporo.database
    import sapporo.factory

    sapporo.config.get_config.cache_clear()
    sapporo.config._load_pkg_dir.cache_clear()
    sapporo.config._load_ga4gh_wes_spec.cache_clear()
    sapporo.factory.create_service_info.cache_clear()
    sapporo.factory.create_executable_wfs.cache_clear()
    sapporo.auth.get_auth_config.cache_clear()
    sapporo.auth.fetch_endpoint_metadata.cache_clear()
    sapporo.auth.fetch_jwks.cache_clear()
    sapporo.database.create_db_engine.cache_clear()


# === Fixture: auth-enabled client via module reload ===


@pytest.fixture
def auth_env(tmp_path: Path) -> Generator[tuple[TestClient, Path], None, None]:
    """Create a TestClient with real auth enforcement enabled.

    auth_depends_factory() is evaluated once at module import time, baking
    ``Depends(lambda: None)`` (auth disabled) into every endpoint's default
    parameter.  To test endpoints with auth enforcement we must:

    1. Write an auth_config with ``auth_enabled=True`` and set env vars so
       ``get_config()`` picks up the right paths.
    2. Clear all @cache functions.
    3. ``importlib.reload`` the module chain (auth → routers → app) so that
       ``auth_depends_factory()`` re-evaluates and returns
       ``Depends(password_bearer)``.
    4. Initialize the DB and build the app from the reloaded modules.

    Yields ``(client, run_dir)`` so tests can create run directories.
    """
    import sapporo.app
    import sapporo.auth
    import sapporo.database
    import sapporo.routers

    auth_dict = default_auth_config_dict()
    auth_dict["auth_enabled"] = True
    ac_path = write_auth_config(tmp_path, auth_dict)

    os.environ["SAPPORO_AUTH_CONFIG"] = str(ac_path)
    os.environ["SAPPORO_RUN_DIR"] = str(tmp_path)

    _clear_module_caches()

    importlib.reload(sapporo.auth)
    importlib.reload(sapporo.routers)
    importlib.reload(sapporo.app)

    sapporo.database.create_db_engine.cache_clear()
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    sapporo.database.init_db()

    client = TestClient(sapporo.app.create_app())

    yield client, tmp_path

    # Cleanup: restore default (auth-disabled) module state.
    os.environ.pop("SAPPORO_AUTH_CONFIG", None)
    os.environ.pop("SAPPORO_RUN_DIR", None)
    _clear_module_caches()
    importlib.reload(sapporo.auth)
    importlib.reload(sapporo.routers)
    importlib.reload(sapporo.app)


def _get_auth_token(client: TestClient) -> str:
    """Obtain a JWT token from POST /token with the default test credentials."""
    res = client.post(
        "/token",
        data={"username": "test-user", "password": "sapporo-test-password"},
    )
    assert res.status_code == 200
    token: str = res.json()["access_token"]
    return token


# === GET /service-info ===


class TestGetServiceInfo:
    def test_returns_200_with_service_info(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = create_test_client(mocker, tmp_path)
        res = client.get("/service-info")
        assert res.status_code == 200
        body = res.json()
        assert "workflow_type_versions" in body
        assert "workflow_engine_versions" in body

    def test_contains_system_state_counts(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = create_test_client(mocker, tmp_path)
        res = client.get("/service-info")
        body = res.json()
        assert "system_state_counts" in body
        assert isinstance(body["system_state_counts"], dict)


# === GET /runs ===


class TestListRuns:
    def test_empty_returns_200_with_empty_list(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = create_test_client(mocker, tmp_path)
        res = client.get("/runs")
        assert res.status_code == 200
        body = res.json()
        assert body["runs"] == []
        assert body["total_runs"] == 0

    def test_with_runs_returns_run_summaries(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000000001"
        create_run_dir(tmp_path, run_id)

        from sapporo.database import add_run_db
        from sapporo.factory import create_run_summary

        add_run_db(create_run_summary(run_id))

        res = client.get("/runs")
        assert res.status_code == 200
        body = res.json()
        assert len(body["runs"]) == 1
        assert body["runs"][0]["run_id"] == run_id

    def test_page_size_limits_results(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)

        from sapporo.database import add_run_db
        from sapporo.factory import create_run_summary

        for i in range(3):
            rid = f"aabbccdd-0000-0000-0000-00000000010{i}"
            create_run_dir(tmp_path, rid)
            add_run_db(create_run_summary(rid))

        res = client.get("/runs", params={"page_size": 2})
        assert res.status_code == 200
        body = res.json()
        assert len(body["runs"]) == 2
        assert body["total_runs"] == 3

    def test_page_token_paginates_correctly(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)

        from sapporo.database import add_run_db
        from sapporo.factory import create_run_summary

        for i in range(3):
            rid = f"aabbccdd-0000-0000-0000-00000000020{i}"
            create_run_dir(tmp_path, rid)
            add_run_db(create_run_summary(rid))

        res1 = client.get("/runs", params={"page_size": 2})
        body1 = res1.json()
        assert body1["next_page_token"] is not None

        res2 = client.get("/runs", params={"page_size": 2, "page_token": body1["next_page_token"]})
        body2 = res2.json()
        assert len(body2["runs"]) == 1

        all_ids = {r["run_id"] for r in body1["runs"]} | {r["run_id"] for r in body2["runs"]}
        assert len(all_ids) == 3

    def test_sort_order_desc_returns_newest_first(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)

        from sapporo.database import add_run_db
        from sapporo.factory import create_run_summary

        create_run_dir(tmp_path, "aabbccdd-0000-0000-0000-000000000301", start_time="2024-01-01T00:00:00Z")
        add_run_db(create_run_summary("aabbccdd-0000-0000-0000-000000000301"))
        create_run_dir(tmp_path, "aabbccdd-0000-0000-0000-000000000302", start_time="2024-06-01T00:00:00Z")
        add_run_db(create_run_summary("aabbccdd-0000-0000-0000-000000000302"))

        res = client.get("/runs", params={"sort_order": "desc"})
        runs = res.json()["runs"]
        assert runs[0]["run_id"] == "aabbccdd-0000-0000-0000-000000000302"

    def test_filter_by_state_returns_matching_only(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)

        from sapporo.database import add_run_db
        from sapporo.factory import create_run_summary

        create_run_dir(tmp_path, "aabbccdd-0000-0000-0000-000000000401", state="COMPLETE")
        add_run_db(create_run_summary("aabbccdd-0000-0000-0000-000000000401"))
        create_run_dir(tmp_path, "aabbccdd-0000-0000-0000-000000000402", state="RUNNING")
        add_run_db(create_run_summary("aabbccdd-0000-0000-0000-000000000402"))

        res = client.get("/runs", params={"state": "COMPLETE"})
        runs = res.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["state"] == "COMPLETE"

    def test_filter_by_tag_returns_matching_only(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)

        from sapporo.database import add_run_db
        from sapporo.factory import create_run_summary

        create_run_dir(tmp_path, "aabbccdd-0000-0000-0000-000000000501", tags={"project": "genomics"})
        add_run_db(create_run_summary("aabbccdd-0000-0000-0000-000000000501"))
        create_run_dir(tmp_path, "aabbccdd-0000-0000-0000-000000000502", tags={"project": "other"})
        add_run_db(create_run_summary("aabbccdd-0000-0000-0000-000000000502"))

        res = client.get("/runs", params={"tags": "project:genomics"})
        runs = res.json()["runs"]
        assert len(runs) == 1

    def test_filter_by_run_ids_returns_matching_only(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)

        from sapporo.database import add_run_db
        from sapporo.factory import create_run_summary

        rid1 = "aabbccdd-0000-0000-0000-000000000601"
        rid2 = "aabbccdd-0000-0000-0000-000000000602"
        create_run_dir(tmp_path, rid1)
        add_run_db(create_run_summary(rid1))
        create_run_dir(tmp_path, rid2)
        add_run_db(create_run_summary(rid2))

        res = client.get("/runs", params={"run_ids": rid1})
        runs = res.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["run_id"] == rid1


# === POST /runs ===


class TestRunWorkflow:
    def test_form_data_returns_201_with_run_id(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = _post_run_form(client)
        assert res.status_code == 200
        body = res.json()
        assert "run_id" in body
        assert isinstance(body["run_id"], str)

    def test_json_body_returns_201_with_run_id(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = _post_run_json(client)
        assert res.status_code == 200
        body = res.json()
        assert "run_id" in body

    def test_missing_required_field_returns_400(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        # Form data without workflow_type → empty string → validator rejects
        res = client.post(
            "/runs",
            data={
                "workflow_type_version": "v1.0",
                "workflow_engine": "cwltool",
                "workflow_url": "https://example.com/wf.cwl",
            },
        )
        assert res.status_code == 400

    def test_invalid_workflow_type_returns_400(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = _post_run_form(client, workflow_type="INVALID_TYPE")
        assert res.status_code == 400

    def test_invalid_json_params_raises_json_decode_error(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        """Verify that invalid JSON in workflow_params raises JSONDecodeError.

        validate_run_request passes workflow_params through json.loads without
        catching JSONDecodeError.  Starlette 0.52+ always re-raises from
        ServerErrorMiddleware, so the exception propagates through TestClient.
        """
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        with pytest.raises(json.JSONDecodeError):
            _post_run_form(client, workflow_params="not-valid-json{{{")


# === GET /runs/{run_id} ===


class TestGetRunLog:
    def test_existing_run_returns_200(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000000701"
        create_run_dir(tmp_path, run_id)

        res = client.get(f"/runs/{run_id}")
        assert res.status_code == 200

    def test_nonexistent_run_returns_404(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = client.get("/runs/nonexistent-run-id-0000-000000000000")
        assert res.status_code == 404

    def test_contains_run_request_and_state(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000000702"
        create_run_dir(tmp_path, run_id, state="COMPLETE")

        res = client.get(f"/runs/{run_id}")
        body = res.json()
        assert body["state"] == "COMPLETE"
        assert body["request"] is not None
        assert body["request"]["workflow_type"] == "CWL"


# === GET /runs/{run_id}/status ===


class TestGetRunStatus:
    def test_returns_200_with_state(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000000801"
        create_run_dir(tmp_path, run_id, state="RUNNING")

        res = client.get(f"/runs/{run_id}/status")
        assert res.status_code == 200
        body = res.json()
        assert body["state"] == "RUNNING"
        assert body["run_id"] == run_id

    def test_nonexistent_run_returns_404(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = client.get("/runs/nonexistent-run-id-0000-000000000000/status")
        assert res.status_code == 404


# === GET /runs/{run_id}/tasks ===


class TestListTasks:
    def test_returns_400_not_implemented(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000000901"
        res = client.get(f"/runs/{run_id}/tasks")
        assert res.status_code == 400

    def test_get_task_returns_400_not_implemented(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = client.get("/runs/some-run-id/tasks/some-task-id")
        assert res.status_code == 400


# === POST /runs/{run_id}/cancel ===


class TestCancelRun:
    def test_returns_200_with_run_id(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000001001"
        create_run_dir(tmp_path, run_id, state="RUNNING")

        res = client.post(f"/runs/{run_id}/cancel")
        assert res.status_code == 200
        assert res.json()["run_id"] == run_id

    def test_nonexistent_run_returns_404(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = client.post("/runs/nonexistent-run-id-0000-000000000000/cancel")
        assert res.status_code == 404


# === DELETE /runs/{run_id} ===


class TestDeleteRun:
    def test_returns_200_with_run_id(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000001101"
        create_run_dir(tmp_path, run_id)

        res = client.delete(f"/runs/{run_id}")
        assert res.status_code == 200
        assert res.json()["run_id"] == run_id

    def test_nonexistent_run_returns_404(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = client.delete("/runs/nonexistent-run-id-0000-000000000000")
        assert res.status_code == 404


# === DELETE /runs (bulk) ===


class TestDeleteRuns:
    def test_returns_200_with_deleted_ids(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        rid1 = "aabbccdd-0000-0000-0000-000000001201"
        rid2 = "aabbccdd-0000-0000-0000-000000001202"
        create_run_dir(tmp_path, rid1)
        create_run_dir(tmp_path, rid2)

        res = client.delete("/runs", params={"run_ids": [rid1, rid2]})
        assert res.status_code == 200
        assert set(res.json()["run_ids"]) == {rid1, rid2}

    def test_nonexistent_ids_returns_404(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = client.delete("/runs", params={"run_ids": ["nonexistent-id-000000000000"]})
        assert res.status_code == 404

    def test_empty_ids_returns_422(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        # FastAPI requires the query parameter, sending none triggers 422
        res = client.delete("/runs")
        assert res.status_code in (400, 422)


# === GET /executable-workflows ===


class TestListExecutableWorkflows:
    def test_returns_200(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = create_test_client(mocker, tmp_path)
        res = client.get("/executable-workflows")
        assert res.status_code == 200
        body = res.json()
        assert "workflows" in body

    def test_with_custom_file_returns_custom_workflows(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        from sapporo.config import AppConfig

        ew_path = tmp_path / "custom_ew.json"
        ew_path.write_text(
            json.dumps({"workflows": ["https://example.com/custom.cwl"]}),
            encoding="utf-8",
        )
        config = AppConfig(run_dir=tmp_path, executable_workflows=ew_path)
        client = create_test_client(mocker, tmp_path, app_config=config)

        res = client.get("/executable-workflows")
        body = res.json()
        assert body["workflows"] == ["https://example.com/custom.cwl"]


# === GET /runs/{run_id}/outputs ===


class TestGetRunOutputs:
    def test_list_returns_200_with_outputs(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000001401"
        rd = create_run_dir(tmp_path, run_id)

        from sapporo.config import RUN_DIR_STRUCTURE

        outputs_file = [{"file_name": "out.txt", "file_url": "http://localhost/out.txt"}]
        rd.joinpath(RUN_DIR_STRUCTURE["outputs"]).write_text(json.dumps(outputs_file), encoding="utf-8")

        res = client.get(f"/runs/{run_id}/outputs")
        assert res.status_code == 200
        body = res.json()
        assert len(body["outputs"]) == 1

    def test_download_true_returns_zip_stream(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000001402"
        rd = create_run_dir(tmp_path, run_id)

        from sapporo.config import RUN_DIR_STRUCTURE

        outputs_dir = rd / RUN_DIR_STRUCTURE["outputs_dir"]
        (outputs_dir / "result.txt").write_text("hello", encoding="utf-8")

        res = client.get(f"/runs/{run_id}/outputs", params={"download": "true"})
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/zip"

    def test_file_returns_file_content(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000001403"
        rd = create_run_dir(tmp_path, run_id)

        from sapporo.config import RUN_DIR_STRUCTURE

        outputs_dir = rd / RUN_DIR_STRUCTURE["outputs_dir"]
        (outputs_dir / "result.txt").write_text("file-content-here", encoding="utf-8")

        res = client.get(f"/runs/{run_id}/outputs/result.txt")
        assert res.status_code == 200
        assert res.text == "file-content-here"

    def test_nonexistent_path_returns_404(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000001404"
        create_run_dir(tmp_path, run_id)

        res = client.get(f"/runs/{run_id}/outputs/nonexistent.txt")
        assert res.status_code == 404


# === GET /runs/{run_id}/ro-crate ===


class TestGetRunRoCrate:
    def test_returns_json_ld(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000001501"
        rd = create_run_dir(tmp_path, run_id)

        from sapporo.config import RUN_DIR_STRUCTURE

        ro_crate = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": []}
        rd.joinpath(RUN_DIR_STRUCTURE["ro_crate"]).write_text(json.dumps(ro_crate), encoding="utf-8")

        res = client.get(f"/runs/{run_id}/ro-crate")
        assert res.status_code == 200
        assert "application/ld+json" in res.headers["content-type"]
        assert res.json()["@context"] == "https://w3id.org/ro/crate/1.1/context"

    def test_missing_metadata_returns_null_content(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        """Verify that missing ro-crate metadata returns 200 with null.

        When ro-crate-metadata.json is absent, read_file returns None and
        the endpoint returns 200 with ``null`` as the JSON body.
        """
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        run_id = "aabbccdd-0000-0000-0000-000000001502"
        create_run_dir(tmp_path, run_id)

        res = client.get(f"/runs/{run_id}/ro-crate")
        assert res.status_code == 200
        assert res.json() is None


# === POST /token, GET /me ===


class TestAuthEndpoints:
    def _create_auth_client(self, mocker: "MockerFixture", tmp_path: Path) -> TestClient:
        """Create a test client with sapporo auth config on disk.

        Note: auth_depends_factory() was already evaluated at import time with
        auth_enabled=False, so endpoint dependencies remain Depends(lambda: None).
        This client is suitable for testing /token (which reads config at runtime)
        and /me with auth disabled (returns 400).
        """
        from sapporo.config import AppConfig

        auth_dict = default_auth_config_dict()
        auth_dict["auth_enabled"] = True
        ac_path = write_auth_config(tmp_path, auth_dict)
        config = AppConfig(run_dir=tmp_path, auth_config=ac_path)
        mocker.patch("sapporo.routers.post_run_task")
        mocker.patch("sapporo.routers.cancel_run_task")
        mocker.patch("sapporo.routers.delete_run_task")
        mocker.patch("sapporo.routers.bulk_delete_run_tasks")
        return create_test_client(mocker, tmp_path, app_config=config)

    def test_create_token_valid_credentials_returns_token(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = self._create_auth_client(mocker, tmp_path)
        res = client.post(
            "/token",
            data={"username": "test-user", "password": "sapporo-test-password"},
        )
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_create_token_invalid_credentials_returns_401(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = self._create_auth_client(mocker, tmp_path)
        res = client.post(
            "/token",
            data={"username": "test-user", "password": "wrong-password"},
        )
        assert res.status_code == 401

    def test_get_me_with_valid_token_returns_username(self, auth_env: tuple[TestClient, Path]) -> None:
        client, _ = auth_env
        token = _get_auth_token(client)
        res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["username"] == "test-user"

    def test_get_me_without_auth_returns_400(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        # Auth disabled client — token dependency always returns None
        client = _client_with_mock_run_tasks(mocker, tmp_path)
        res = client.get("/me")
        assert res.status_code == 400


# === Auth cross-cutting tests ===


class TestAuthCrossCutting:
    def test_endpoint_with_auth_enabled_no_token_returns_401(self, auth_env: tuple[TestClient, Path]) -> None:
        client, _ = auth_env
        res = client.get("/runs")
        assert res.status_code == 401

    def test_endpoint_with_auth_enabled_valid_token_returns_200(self, auth_env: tuple[TestClient, Path]) -> None:
        client, _ = auth_env
        token = _get_auth_token(client)
        res = client.get("/runs", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    def test_endpoint_with_auth_enabled_filters_runs_by_username(self, auth_env: tuple[TestClient, Path]) -> None:
        client, run_dir = auth_env
        token = _get_auth_token(client)

        from sapporo.database import add_run_db
        from sapporo.factory import create_run_summary

        rid_owned = "aabbccdd-0000-0000-0000-000000001801"
        create_run_dir(run_dir, rid_owned, username="test-user")
        add_run_db(create_run_summary(rid_owned), username="test-user")

        rid_other = "aabbccdd-0000-0000-0000-000000001802"
        create_run_dir(run_dir, rid_other, username="other-user")
        add_run_db(create_run_summary(rid_other), username="other-user")

        res = client.get("/runs", headers={"Authorization": f"Bearer {token}"})
        runs = res.json()["runs"]
        run_ids = {r["run_id"] for r in runs}
        assert rid_owned in run_ids
        assert rid_other not in run_ids

    def test_endpoint_without_auth_returns_all_runs(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        client = _client_with_mock_run_tasks(mocker, tmp_path)

        from sapporo.database import add_run_db
        from sapporo.factory import create_run_summary

        rid1 = "aabbccdd-0000-0000-0000-000000001901"
        rid2 = "aabbccdd-0000-0000-0000-000000001902"
        create_run_dir(tmp_path, rid1, username="alice")
        add_run_db(create_run_summary(rid1), username="alice")
        create_run_dir(tmp_path, rid2, username="bob")
        add_run_db(create_run_summary(rid2), username="bob")

        res = client.get("/runs")
        runs = res.json()["runs"]
        run_ids = {r["run_id"] for r in runs}
        assert rid1 in run_ids
        assert rid2 in run_ids
