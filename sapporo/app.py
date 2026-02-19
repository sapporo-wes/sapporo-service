import logging
import logging.config
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from sapporo.auth import get_auth_config
from sapporo.config import PKG_DIR, add_openapi_info, get_config, logging_config
from sapporo.database import init_db
from sapporo.factory import create_executable_wfs, create_service_info
from sapporo.routers import router
from sapporo.run import remove_old_runs
from sapporo.schemas import ErrorResponse
from sapporo.utils import mask_sensitive

LOGGER = logging.getLogger(__name__)


def fix_error_handler(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        app_config = get_config()
        if app_config.debug:
            LOGGER.exception("HTTP exception occurred", exc_info=exc)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                msg=exc.detail,
                status_code=exc.status_code,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        app_config = get_config()
        if app_config.debug:
            LOGGER.exception("Request validation error occurred", exc_info=exc)
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                msg=str(exc.errors()),
                status_code=400,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        LOGGER.exception("Unhandled exception occurred", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                msg="The server encountered an internal error and was unable to complete your request.",
                status_code=500,
            ).model_dump(),
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def init_app_state() -> None:
    """Perform validation, initialize the cache, and log the configuration contents.

    Specifically, validate the configuration files such as service_info.json, auth_config.json,
    executable_workflows.json, etc., and the initial state of the application.
    """
    LOGGER.info("Initializing app state")

    service_info_path = get_config().service_info
    if not service_info_path.exists():
        msg = f"Service info file not found: {service_info_path}"
        raise FileNotFoundError(msg)
    try:
        service_info = create_service_info()  # Cache and validate
    except Exception as e:
        msg = f"Service info file is invalid: {service_info_path}"
        raise ValueError(msg) from e
    LOGGER.info("Service info: %s", service_info)

    executable_wfs_path = get_config().executable_workflows
    try:
        executable_wfs = create_executable_wfs()  # Cache and validate
        if len(executable_wfs.workflows) != 0:
            # Check wf_url is http or https
            for wf_url in executable_wfs.workflows:
                if not wf_url.startswith("http://") and not wf_url.startswith("https://"):
                    msg = f"Invalid workflow_url: {wf_url} in executable_workflows.json. The workflow_url must start with 'http://' or 'https://'."
                    raise ValueError(msg)
    except Exception as e:
        msg = f"Executable workflows file is invalid: {executable_wfs_path}"
        raise ValueError(msg) from e
    LOGGER.info("Executable workflows: %s", executable_wfs)

    auth_config_path = get_config().auth_config
    if not auth_config_path.exists():
        msg = f"Auth config file not found: {auth_config_path}"
        raise FileNotFoundError(msg)
    try:
        auth_config = get_auth_config()  # Cache and validate
        # Extra validation
        if auth_config.auth_enabled:
            if (
                auth_config.idp_provider == "external"
                and auth_config.external_config.client_mode == "confidential"
                and (auth_config.external_config.client_id is None or auth_config.external_config.client_secret is None)
            ):
                msg = "Client ID and Client Secret must be specified in confidential mode in the auth_config.json file."
                raise ValueError(msg)

            # Validate secret_key strength for sapporo mode
            if auth_config.idp_provider == "sapporo":
                secret_key = auth_config.sapporo_auth_config.secret_key
                weak_keys = [
                    "sapporo_secret_key_please_change_this",
                    "secret",
                    "changeme",
                    "password",
                ]
                min_secret_key_length = 32
                is_weak = secret_key in weak_keys or len(secret_key) < min_secret_key_length
                if is_weak:
                    warning_msg = (
                        "Weak secret_key detected in auth_config.json, "
                        "generate a strong key using: sapporo-cli generate-secret"
                    )
                    LOGGER.warning(warning_msg)
                    if not get_config().debug:
                        msg = (
                            "Weak secret_key is not allowed in production mode. "
                            "Generate a strong secret key using: sapporo-cli generate-secret"
                        )
                        raise ValueError(msg)
    except Exception as e:
        msg = f"Auth config file is invalid: {auth_config_path}"
        raise ValueError(msg) from e
    masked = mask_sensitive(auth_config.model_dump(), {"secret_key", "password_hash", "client_secret"})
    LOGGER.info("Auth config: %s", masked)

    LOGGER.info("App state initialized")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()

    snapshot_interval = get_config().snapshot_interval
    scheduler = BackgroundScheduler()
    scheduler.add_job(init_db, "interval", minutes=snapshot_interval)
    scheduler.add_job(remove_old_runs, "interval", minutes=snapshot_interval)
    scheduler.start()
    LOGGER.info("DB snapshot scheduler started")

    try:
        yield
    finally:
        scheduler.shutdown()
        LOGGER.info("DB snapshot scheduler stopped")


def create_app() -> FastAPI:
    app_config = get_config()

    app = FastAPI(
        root_path=app_config.url_prefix,
        debug=app_config.debug,
        lifespan=lifespan,
    )
    app.include_router(
        router,
        responses={
            400: {"model": ErrorResponse, "description": "The request is malformed."},
            401: {"model": ErrorResponse, "description": "The request is unauthorized."},
            403: {"model": ErrorResponse, "description": "The requester is not authorized to perform this action."},
            404: {"model": ErrorResponse, "description": "The requested workflow run not found."},
            500: {"model": ErrorResponse, "description": "An unexpected error occurred."},
        },
    )

    auth_config = get_auth_config()
    if auth_config.auth_enabled and app_config.allow_origin == "*":
        LOGGER.warning(
            "Authentication is enabled but CORS allows all origins (allow_origin='*'). "
            "Consider restricting allow_origin to trusted domains in production."
        )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_config.allow_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fix_error_handler(app)

    add_openapi_info(app)

    return app


def main() -> None:
    app_config = get_config()  # Cache the config
    logging.config.dictConfig(logging_config(app_config.debug))
    init_app_state()
    uvicorn.run(
        "sapporo.app:create_app",
        host=app_config.host,
        port=app_config.port,
        reload=app_config.debug,
        reload_dirs=[str(PKG_DIR)] if app_config.debug else None,
        factory=True,
    )


if __name__ == "__main__":
    main()
