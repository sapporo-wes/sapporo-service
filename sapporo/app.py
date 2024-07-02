import logging.config
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sapporo.auth import get_auth_config
from sapporo.config import LOGGER, PKG_DIR, get_config, logging_config
from sapporo.database import SNAPSHOT_INTERVAL, init_db
from sapporo.factory import create_service_info
from sapporo.routers import router
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
    scheduler.start()
    LOGGER.info("DB snapshot scheduler started.")

    yield

    scheduler.shutdown()
    LOGGER.info("DB snapshot scheduler stopped.")


def create_app() -> FastAPI:
    app_config = get_config()
    logging.config.dictConfig(logging_config(app_config.debug))  # Reconfigure logging

    app = FastAPI(root_path=app_config.url_prefix, lifespan=lifespan)
    app.include_router(router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_config.allow_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fix_error_handler(app)

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
