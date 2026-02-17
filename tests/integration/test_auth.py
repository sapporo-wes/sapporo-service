"""Integration tests for authentication and run isolation.

All tests use the ``sapporo_auth_env`` fixture which starts a dedicated
sapporo instance on port 1123 with auth enabled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.integration.conftest import (
    RESOURCES_DIR,
    auth_headers,
    get_auth_token,
    submit_workflow,
    wait_for_completion,
)

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.integration

CWL_DIR = RESOURCES_DIR / "cwl"


class TestTokenEndpoint:
    def test_valid_credentials_return_token(self, sapporo_auth_env: dict[str, Any]) -> None:
        """Correct username/password returns 200 with access_token."""
        client: httpx.Client = sapporo_auth_env["client"]
        user = sapporo_auth_env["user1"]
        res = client.post("/token", data={"username": user["username"], "password": user["password"]})
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_invalid_password_returns_401(self, sapporo_auth_env: dict[str, Any]) -> None:
        """Wrong password returns 401."""
        client: httpx.Client = sapporo_auth_env["client"]
        user = sapporo_auth_env["user1"]
        res = client.post("/token", data={"username": user["username"], "password": "wrongpassword"})
        assert res.status_code == 401

    def test_nonexistent_user_returns_401(self, sapporo_auth_env: dict[str, Any]) -> None:
        """Nonexistent username returns 401."""
        client: httpx.Client = sapporo_auth_env["client"]
        res = client.post("/token", data={"username": "nosuchuser", "password": "anything"})
        assert res.status_code == 401


class TestMeEndpoint:
    def test_valid_token_returns_username(self, sapporo_auth_env: dict[str, Any]) -> None:
        """GET /me with valid token returns the username."""
        client: httpx.Client = sapporo_auth_env["client"]
        user = sapporo_auth_env["user1"]
        token = get_auth_token(client, user["username"], user["password"])
        res = client.get("/me", headers=auth_headers(token))
        assert res.status_code == 200
        assert res.json()["username"] == user["username"]

    def test_no_token_returns_401(self, sapporo_auth_env: dict[str, Any]) -> None:
        """GET /me without token returns 401."""
        client: httpx.Client = sapporo_auth_env["client"]
        res = client.get("/me")
        assert res.status_code == 401

    def test_invalid_token_returns_401(self, sapporo_auth_env: dict[str, Any]) -> None:
        """GET /me with invalid token returns 401."""
        client: httpx.Client = sapporo_auth_env["client"]
        res = client.get("/me", headers=auth_headers("invalid.jwt.token"))
        assert res.status_code == 401


class TestProtectedEndpoints:
    def test_runs_without_token_returns_401(self, sapporo_auth_env: dict[str, Any]) -> None:
        """GET /runs without token returns 401."""
        client: httpx.Client = sapporo_auth_env["client"]
        res = client.get("/runs")
        assert res.status_code == 401

    def test_runs_with_token_returns_200(self, sapporo_auth_env: dict[str, Any]) -> None:
        """GET /runs with valid token returns 200."""
        client: httpx.Client = sapporo_auth_env["client"]
        user = sapporo_auth_env["user1"]
        token = get_auth_token(client, user["username"], user["password"])
        res = client.get("/runs", headers=auth_headers(token))
        assert res.status_code == 200

    def test_post_runs_without_token_returns_401(self, sapporo_auth_env: dict[str, Any]) -> None:
        """POST /runs without token returns 401."""
        client: httpx.Client = sapporo_auth_env["client"]
        res = client.post(
            "/runs",
            data={
                "workflow_type": "CWL",
                "workflow_type_version": "v1.2",
                "workflow_engine": "cwltool",
                "workflow_url": "hello.cwl",
                "workflow_params": "{}",
            },
        )
        assert res.status_code == 401


class TestRunIsolation:
    def test_user_cannot_access_other_users_run(self, sapporo_auth_env: dict[str, Any]) -> None:
        """user1 submits a run; user2 gets 403 on GET /runs/{run_id}."""
        client: httpx.Client = sapporo_auth_env["client"]
        user1 = sapporo_auth_env["user1"]
        user2 = sapporo_auth_env["user2"]

        token1 = get_auth_token(client, user1["username"], user1["password"])
        token2 = get_auth_token(client, user2["username"], user2["password"])

        run_id = submit_workflow(
            client,
            wf_type="CWL",
            wf_type_version="v1.2",
            wf_engine="cwltool",
            wf_url="hello.cwl",
            params_file=CWL_DIR / "hello_params.json",
            attachments=[
                CWL_DIR / "hello.cwl",
                CWL_DIR / "input.txt",
            ],
            headers=auth_headers(token1),
        )

        wait_for_completion(client, run_id, headers=auth_headers(token1))

        res = client.get(f"/runs/{run_id}", headers=auth_headers(token2))
        assert res.status_code == 403

    def test_user_only_sees_own_runs_in_list(self, sapporo_auth_env: dict[str, Any]) -> None:
        """user1 submits a run; user2's GET /runs does not include it."""
        client: httpx.Client = sapporo_auth_env["client"]
        user1 = sapporo_auth_env["user1"]
        user2 = sapporo_auth_env["user2"]

        token1 = get_auth_token(client, user1["username"], user1["password"])
        token2 = get_auth_token(client, user2["username"], user2["password"])

        run_id = submit_workflow(
            client,
            wf_type="CWL",
            wf_type_version="v1.2",
            wf_engine="cwltool",
            wf_url="hello.cwl",
            params_file=CWL_DIR / "hello_params.json",
            attachments=[
                CWL_DIR / "hello.cwl",
                CWL_DIR / "input.txt",
            ],
            headers=auth_headers(token1),
        )

        wait_for_completion(client, run_id, headers=auth_headers(token1))

        res = client.get("/runs", headers=auth_headers(token2))
        assert res.status_code == 200
        runs = res.json()["runs"]
        run_ids_in_list = [r["run_id"] for r in runs]
        assert run_id not in run_ids_in_list
