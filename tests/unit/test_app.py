from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.websockets import WebSocket

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from sapporo.auth import AuthConfig
    from sapporo.config import AppConfig
    from sapporo.schemas import ExecutableWorkflows


# === Helper ===


def _create_error_test_app(mocker: "MockerFixture", debug: bool = False) -> TestClient:
    """Create a minimal app with fix_error_handler for testing error responses."""
    from sapporo.app import fix_error_handler
    from sapporo.config import AppConfig

    config = AppConfig(debug=debug)
    mocker.patch("sapporo.app.get_config", return_value=config)

    app = FastAPI()

    @app.get("/raise-http-404")
    async def _raise_http_404() -> None:
        raise StarletteHTTPException(status_code=404, detail="Not found")

    @app.get("/raise-runtime-error")
    async def _raise_runtime_error() -> None:
        msg = "Something went wrong internally"
        raise RuntimeError(msg)

    @app.get("/validate/{item_id}")
    async def _validate_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    fix_error_handler(app)
    return TestClient(app, raise_server_exceptions=False)


def _create_cors_test_app(allow_origins: list[str] | None = None) -> TestClient:
    """Create a minimal app with CustomCORSMiddleware for testing CORS behavior."""
    from sapporo.app import CustomCORSMiddleware

    app = FastAPI()

    @app.get("/hello")
    async def _hello() -> dict[str, str]:
        return {"msg": "hello"}

    @app.websocket("/ws")
    async def _websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("hello")
        await websocket.close()

    app.add_middleware(
        CustomCORSMiddleware,
        allow_origins=allow_origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return TestClient(app)


def _make_auth_config(
    auth_enabled: bool = False,
    idp_provider: str = "sapporo",
    secret_key: str = "sapporo_test_secret_key_for_unit_tests",  # noqa: S107
    client_mode: str = "public",
    client_id: str | None = "test-client",
    client_secret: str | None = "test-secret",  # noqa: S107
) -> "AuthConfig":
    from sapporo.auth import AuthConfig, AuthUser, ExternalAuthConfig, SapporoAuthConfig

    return AuthConfig(
        auth_enabled=auth_enabled,
        idp_provider=idp_provider,
        sapporo_auth_config=SapporoAuthConfig(
            secret_key=secret_key,
            expires_delta_hours=24,
            users=[AuthUser(username="test", password_hash="$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy")],
        ),
        external_config=ExternalAuthConfig(
            idp_url="https://example.com/realms/test",
            jwt_audience="account",
            client_mode=client_mode,
            client_id=client_id,
            client_secret=client_secret,
        ),
    )


def _setup_init_mocks_through_service_info(
    mocker: "MockerFixture",
    tmp_path: Path,
    *,
    debug: bool = False,
) -> "AppConfig":
    """Set up mocks so init_app_state passes service_info validation."""
    from sapporo.config import AppConfig

    si_path = tmp_path / "service_info.json"
    si_path.write_text("{}", encoding="utf-8")
    ac_path = tmp_path / "auth_config.json"
    ac_path.write_text("{}", encoding="utf-8")

    config = AppConfig(run_dir=tmp_path, service_info=si_path, auth_config=ac_path, debug=debug)
    mocker.patch("sapporo.app.get_config", return_value=config)
    mocker.patch("sapporo.app.create_service_info", return_value=MagicMock())
    return config


def _setup_init_mocks_through_executable_wfs(
    mocker: "MockerFixture",
    tmp_path: Path,
    *,
    debug: bool = False,
    executable_wfs: "ExecutableWorkflows | None" = None,
) -> "AppConfig":
    """Set up mocks so init_app_state passes service_info + executable_wfs validation."""
    from sapporo.schemas import ExecutableWorkflows

    config = _setup_init_mocks_through_service_info(mocker, tmp_path, debug=debug)
    mocker.patch(
        "sapporo.app.create_executable_wfs",
        return_value=executable_wfs or ExecutableWorkflows(workflows=[]),
    )
    return config


# === fix_error_handler ===


class TestFixErrorHandler:
    def test_http_exception_returns_json_error_response(self, mocker: "MockerFixture") -> None:
        client = _create_error_test_app(mocker)
        res = client.get("/raise-http-404")
        assert res.status_code == 404
        body = res.json()
        assert body["msg"] == "Not found"
        assert body["status_code"] == 404

    def test_validation_error_returns_400(self, mocker: "MockerFixture") -> None:
        client = _create_error_test_app(mocker)
        res = client.get("/validate/not-an-int")
        assert res.status_code == 400
        body = res.json()
        assert body["status_code"] == 400
        assert "msg" in body

    def test_generic_exception_returns_500(self, mocker: "MockerFixture") -> None:
        client = _create_error_test_app(mocker)
        res = client.get("/raise-runtime-error")
        assert res.status_code == 500
        body = res.json()
        assert body["status_code"] == 500

    def test_generic_exception_does_not_leak_details(self, mocker: "MockerFixture") -> None:
        client = _create_error_test_app(mocker)
        res = client.get("/raise-runtime-error")
        body = res.json()
        assert "Something went wrong internally" not in body["msg"]

    def test_debug_mode_logs_http_exception(self, mocker: "MockerFixture") -> None:
        client = _create_error_test_app(mocker, debug=True)
        mock_logger = mocker.patch("sapporo.app.LOGGER")
        client.get("/raise-http-404")
        mock_logger.exception.assert_called_once()


# === CustomCORSMiddleware ===


class TestCustomCORSMiddleware:
    def test_without_origin_header_still_returns_cors_headers(self) -> None:
        client = _create_cors_test_app()
        res = client.get("/hello")
        assert res.status_code == 200
        assert "access-control-allow-origin" in res.headers

    def test_with_origin_header_returns_that_origin(self) -> None:
        client = _create_cors_test_app(allow_origins=["http://example.com"])
        res = client.get("/hello", headers={"Origin": "http://example.com"})
        assert res.status_code == 200
        assert res.headers["access-control-allow-origin"] == "http://example.com"

    def test_preflight_options_returns_200(self) -> None:
        client = _create_cors_test_app()
        res = client.options(
            "/hello",
            headers={
                "Origin": "http://example.com",
                "access-control-request-method": "GET",
            },
        )
        assert res.status_code == 200

    def test_with_cookie_uses_explicit_origin(self) -> None:
        client = _create_cors_test_app()
        res = client.get(
            "/hello",
            headers={
                "Origin": "http://example.com",
                "Cookie": "session=abc123",
            },
        )
        assert res.headers["access-control-allow-origin"] == "http://example.com"

    def test_non_http_scope_passes_through(self) -> None:
        client = _create_cors_test_app()
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_text()
            assert data == "hello"


# === init_app_state ===


class TestInitAppState:
    def test_missing_service_info_raises_file_not_found_error(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        from sapporo.app import init_app_state
        from sapporo.config import AppConfig

        config = AppConfig(
            run_dir=tmp_path,
            service_info=tmp_path / "nonexistent.json",
        )
        mocker.patch("sapporo.app.get_config", return_value=config)

        with pytest.raises(FileNotFoundError, match="Service info file not found"):
            init_app_state()

    def test_invalid_service_info_raises_value_error(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        from sapporo.app import init_app_state
        from sapporo.config import AppConfig

        si_path = tmp_path / "service_info.json"
        si_path.write_text("{}", encoding="utf-8")
        config = AppConfig(run_dir=tmp_path, service_info=si_path)
        mocker.patch("sapporo.app.get_config", return_value=config)
        mocker.patch("sapporo.app.create_service_info", side_effect=ValueError("bad"))

        with pytest.raises(ValueError, match="Service info file is invalid"):
            init_app_state()

    def test_missing_auth_config_raises_file_not_found_error(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        from sapporo.app import init_app_state

        config = _setup_init_mocks_through_executable_wfs(mocker, tmp_path)
        config.auth_config = tmp_path / "nonexistent_auth.json"

        with pytest.raises(FileNotFoundError, match="Auth config file not found"):
            init_app_state()

    def test_auth_enabled_weak_secret_non_debug_raises_value_error(
        self, mocker: "MockerFixture", tmp_path: Path
    ) -> None:
        from sapporo.app import init_app_state

        _setup_init_mocks_through_executable_wfs(mocker, tmp_path, debug=False)
        mocker.patch(
            "sapporo.app.get_auth_config",
            return_value=_make_auth_config(auth_enabled=True, secret_key="secret"),
        )

        with pytest.raises(ValueError, match="Auth config file is invalid"):
            init_app_state()

    def test_auth_enabled_weak_secret_debug_logs_warning(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        from sapporo.app import init_app_state

        _setup_init_mocks_through_executable_wfs(mocker, tmp_path, debug=True)
        mocker.patch(
            "sapporo.app.get_auth_config",
            return_value=_make_auth_config(auth_enabled=True, secret_key="secret"),
        )
        mock_logger = mocker.patch("sapporo.app.LOGGER")

        init_app_state()

        assert any("Weak secret_key" in str(call) for call in mock_logger.warning.call_args_list)

    def test_external_confidential_missing_secret_raises_value_error(
        self, mocker: "MockerFixture", tmp_path: Path
    ) -> None:
        from sapporo.app import init_app_state

        _setup_init_mocks_through_executable_wfs(mocker, tmp_path)
        mocker.patch(
            "sapporo.app.get_auth_config",
            return_value=_make_auth_config(
                auth_enabled=True,
                idp_provider="external",
                client_mode="confidential",
                client_id=None,
                client_secret=None,
            ),
        )

        with pytest.raises(ValueError, match="Auth config file is invalid"):
            init_app_state()

    def test_invalid_workflow_url_raises_value_error(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        from sapporo.app import init_app_state
        from sapporo.schemas import ExecutableWorkflows

        _setup_init_mocks_through_service_info(mocker, tmp_path)
        mocker.patch(
            "sapporo.app.create_executable_wfs",
            return_value=ExecutableWorkflows(workflows=["ftp://bad.example.com/wf.cwl"]),
        )

        with pytest.raises(ValueError, match="Executable workflows file is invalid"):
            init_app_state()

    def test_valid_config_succeeds(self, mocker: "MockerFixture", tmp_path: Path) -> None:
        from sapporo.app import init_app_state

        _setup_init_mocks_through_executable_wfs(mocker, tmp_path)
        mocker.patch("sapporo.app.get_auth_config", return_value=_make_auth_config())

        init_app_state()  # Should not raise


# === main ===


class TestMain:
    def test_main_calls_uvicorn_run_with_factory(self, mocker: "MockerFixture") -> None:
        from sapporo.app import main
        from sapporo.config import AppConfig

        config = AppConfig()
        mocker.patch("sapporo.app.get_config", return_value=config)
        mocker.patch("sapporo.app.init_app_state")
        mock_uvicorn = mocker.patch("sapporo.app.uvicorn.run")

        main()

        mock_uvicorn.assert_called_once()
        _, kwargs = mock_uvicorn.call_args
        assert mock_uvicorn.call_args[0][0] == "sapporo.app:create_app"
        assert kwargs["factory"] is True

    def test_main_debug_mode_enables_reload(self, mocker: "MockerFixture") -> None:
        from sapporo.app import main
        from sapporo.config import AppConfig

        config = AppConfig(debug=True)
        mocker.patch("sapporo.app.get_config", return_value=config)
        mocker.patch("sapporo.app.init_app_state")
        mock_uvicorn = mocker.patch("sapporo.app.uvicorn.run")

        main()

        _, kwargs = mock_uvicorn.call_args
        assert kwargs["reload"] is True
