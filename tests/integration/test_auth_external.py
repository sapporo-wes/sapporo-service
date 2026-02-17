"""Integration tests for external (Keycloak) authentication.

Requires:
- Keycloak running at localhost:8080 with sapporo-dev realm
  (docker compose -f compose.keycloak.dev.yml up -d)
- SAPPORO_ALLOW_INSECURE_IDP=true

Run with:
  pytest tests/integration/test_auth_external.py -v
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.integration.conftest import (
    auth_headers,
    get_keycloak_token,
)

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.integration


# === Public mode ===


class TestExternalPublicMode:
    def test_public_valid_keycloak_token_accepted(self, sapporo_ext_public_env: dict[str, Any]) -> None:
        """A valid Keycloak token is accepted by sapporo in public mode."""
        client: httpx.Client = sapporo_ext_public_env["client"]
        user = sapporo_ext_public_env["user1"]
        token = get_keycloak_token(user["username"], user["password"])
        res = client.get("/service-info", headers=auth_headers(token))
        assert res.status_code == 200

    def test_public_invalid_token_rejected(self, sapporo_ext_public_env: dict[str, Any]) -> None:
        """A fake token is rejected with 401."""
        client: httpx.Client = sapporo_ext_public_env["client"]
        res = client.get("/runs", headers=auth_headers("fake.invalid.token"))
        assert res.status_code == 401

    def test_public_runs_endpoint_with_token(self, sapporo_ext_public_env: dict[str, Any]) -> None:
        """GET /runs with a valid Keycloak token returns 200."""
        client: httpx.Client = sapporo_ext_public_env["client"]
        user = sapporo_ext_public_env["user1"]
        token = get_keycloak_token(user["username"], user["password"])
        res = client.get("/runs", headers=auth_headers(token))
        assert res.status_code == 200

    def test_public_runs_endpoint_without_token(self, sapporo_ext_public_env: dict[str, Any]) -> None:
        """GET /runs without token returns 401."""
        client: httpx.Client = sapporo_ext_public_env["client"]
        res = client.get("/runs")
        assert res.status_code == 401

    def test_public_me_endpoint_returns_username(self, sapporo_ext_public_env: dict[str, Any]) -> None:
        """GET /me returns the Keycloak username."""
        client: httpx.Client = sapporo_ext_public_env["client"]
        user = sapporo_ext_public_env["user1"]
        token = get_keycloak_token(user["username"], user["password"])
        res = client.get("/me", headers=auth_headers(token))
        assert res.status_code == 200
        assert res.json()["username"] == user["username"]

    def test_public_run_isolation(self, sapporo_ext_public_env: dict[str, Any]) -> None:
        """user1's runs are not visible to user2."""
        client: httpx.Client = sapporo_ext_public_env["client"]
        user1 = sapporo_ext_public_env["user1"]
        user2 = sapporo_ext_public_env["user2"]

        token1 = get_keycloak_token(user1["username"], user1["password"])
        token2 = get_keycloak_token(user2["username"], user2["password"])

        # Both users should see only their own runs
        res1 = client.get("/runs", headers=auth_headers(token1))
        res2 = client.get("/runs", headers=auth_headers(token2))
        assert res1.status_code == 200
        assert res2.status_code == 200

        runs1 = {r["run_id"] for r in res1.json()["runs"]}
        runs2 = {r["run_id"] for r in res2.json()["runs"]}
        # No overlap between user1 and user2 runs
        assert not runs1.intersection(runs2)

    def test_public_token_endpoint_disabled(self, sapporo_ext_public_env: dict[str, Any]) -> None:
        """POST /token should return 400 in public mode."""
        client: httpx.Client = sapporo_ext_public_env["client"]
        user = sapporo_ext_public_env["user1"]
        res = client.post("/token", data={"username": user["username"], "password": user["password"]})
        assert res.status_code == 400


# === Confidential mode ===


class TestExternalConfidentialMode:
    def test_confidential_token_creation(self, sapporo_ext_confidential_env: dict[str, Any]) -> None:
        """POST /token returns a valid access token in confidential mode."""
        client: httpx.Client = sapporo_ext_confidential_env["client"]
        user = sapporo_ext_confidential_env["user1"]
        res = client.post("/token", data={"username": user["username"], "password": user["password"]})
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_confidential_valid_token_accepted(self, sapporo_ext_confidential_env: dict[str, Any]) -> None:
        """A token obtained via POST /token is accepted."""
        client: httpx.Client = sapporo_ext_confidential_env["client"]
        user = sapporo_ext_confidential_env["user1"]
        res = client.post("/token", data={"username": user["username"], "password": user["password"]})
        token = res.json()["access_token"]
        res = client.get("/me", headers=auth_headers(token))
        assert res.status_code == 200
        assert res.json()["username"] == user["username"]

    def test_confidential_wrong_credentials_rejected(self, sapporo_ext_confidential_env: dict[str, Any]) -> None:
        """POST /token with wrong credentials returns 401."""
        client: httpx.Client = sapporo_ext_confidential_env["client"]
        res = client.post("/token", data={"username": "nobody", "password": "wrongpass"})
        assert res.status_code == 401

    def test_confidential_runs_endpoint_with_token(self, sapporo_ext_confidential_env: dict[str, Any]) -> None:
        """GET /runs with a valid token returns 200 in confidential mode."""
        client: httpx.Client = sapporo_ext_confidential_env["client"]
        user = sapporo_ext_confidential_env["user1"]
        res = client.post("/token", data={"username": user["username"], "password": user["password"]})
        token = res.json()["access_token"]
        res = client.get("/runs", headers=auth_headers(token))
        assert res.status_code == 200
