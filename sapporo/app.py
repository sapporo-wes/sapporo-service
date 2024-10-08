import logging.config
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Message, Receive, Scope, Send

from sapporo.auth import get_auth_config
from sapporo.config import (LOGGER, PKG_DIR, add_openapi_info, get_config,
                            logging_config)
from sapporo.database import SNAPSHOT_INTERVAL, init_db
from sapporo.factory import create_executable_wfs, create_service_info
from sapporo.routers import router
from sapporo.run import remove_old_runs
from sapporo.schemas import ErrorResponse


def fix_error_handler(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        app_config = get_config()
        if app_config.debug:
            LOGGER.exception("Something http exception occurred.", exc_info=exc)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                msg=exc.detail,
                status_code=exc.status_code,
            ).model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        app_config = get_config()
        if app_config.debug:
            LOGGER.exception("Request validation error occurred.", exc_info=exc)
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                msg=str(exc.errors()),
                status_code=400,
            ).model_dump()
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
        # If a general Exception occurs, a traceback will be output without using LOGGER.
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                msg="The server encountered an internal error and was unable to complete your request.",
                status_code=500,
            ).model_dump()
        )


class CustomCORSMiddleware(CORSMiddleware):
    """\
    CORSMiddleware that returns CORS headers even if the Origin header is not present
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        headers = Headers(scope=scope)

        if method == "OPTIONS" and "access-control-request-method" in headers:
            response = self.preflight_response(request_headers=headers)
            await response(scope, receive, send)
            return

        await self.simple_response(scope, receive, send, request_headers=headers)

    async def send(
        self, message: Message, send: Send, request_headers: Headers
    ) -> None:
        if message["type"] != "http.response.start":
            await send(message)
            return

        message.setdefault("headers", [])
        headers = MutableHeaders(scope=message)
        headers.update(self.simple_headers)
        origin = request_headers.get("Origin", "*")
        has_cookie = "cookie" in request_headers

        # If request includes any cookie headers, then we must respond
        # with the specific origin instead of '*'.
        if self.allow_all_origins and has_cookie:
            self.allow_explicit_origin(headers, origin)

        # If we only allow specific origins, then we have to mirror back
        # the Origin header in the response.
        elif not self.allow_all_origins and self.is_allowed_origin(origin=origin):
            self.allow_explicit_origin(headers, origin)

        await send(message)


def init_app_state() -> None:
    """
    Perform validation, initialize the cache, and log the configuration contents.
    Specifically, validate the configuration files such as service_info.json, auth_config.json,
    executable_workflows.json, etc., and the initial state of the application.
    """
    LOGGER.info("=== Initializing app state... ====")

    service_info_path = get_config().service_info
    if not service_info_path.exists():
        raise FileNotFoundError(f"Service info file not found: {service_info_path}")
    try:
        service_info = create_service_info()  # Cache and validate
    except Exception as e:
        raise ValueError(f"Service info file is invalid: {service_info_path}") from e
    LOGGER.info("Service info: %s", service_info)

    executable_wfs_path = get_config().executable_workflows
    try:
        executable_wfs = create_executable_wfs()  # Cache and validate
        if len(executable_wfs.workflows) != 0:
            # Check wf_url is http or https
            for wf_url in executable_wfs.workflows:
                if not wf_url.startswith("http://") and not wf_url.startswith("https://"):
                    raise ValueError(f"Invalid workflow_url: {wf_url} in executable_workflows.json. The workflow_url must start with 'http://' or 'https://'.")
    except Exception as e:
        raise ValueError(f"Executable workflows file is invalid: {executable_wfs_path}") from e
    LOGGER.info("Executable workflows: %s", executable_wfs)

    auth_config_path = get_config().auth_config
    if not auth_config_path.exists():
        raise FileNotFoundError(f"Auth config file not found: {auth_config_path}")
    try:
        auth_config = get_auth_config()  # Cache and validate
        # Extra validation
        if auth_config.auth_enabled:
            if auth_config.idp_provider == "external" and auth_config.external_config.client_mode == "confidential":
                if auth_config.external_config.client_id is None or auth_config.external_config.client_secret is None:
                    raise ValueError("Client ID and Client Secret must be specified in confidential mode in the auth_config.json file.")
    except Exception as e:
        raise ValueError(f"Auth config file is invalid: {auth_config_path}") from e
    LOGGER.info("Auth config: %s", auth_config)

    LOGGER.info("=== App state initialized. ===")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()

    scheduler = BackgroundScheduler()
    scheduler.add_job(init_db, "interval", minutes=SNAPSHOT_INTERVAL)
    scheduler.add_job(remove_old_runs, "interval", minutes=SNAPSHOT_INTERVAL)
    scheduler.start()
    LOGGER.info("DB snapshot scheduler started.")

    try:
        yield
    except Exception as e:  # pylint: disable=W0718
        LOGGER.exception("An unexpected error occurred.", exc_info=e)
        # do not raise
    finally:
        scheduler.shutdown()
        LOGGER.info("DB snapshot scheduler stopped.")


def create_app() -> FastAPI:
    app_config = get_config()
    logging.config.dictConfig(logging_config(app_config.debug))  # Reconfigure logging

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

    app.add_middleware(
        CustomCORSMiddleware,
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
