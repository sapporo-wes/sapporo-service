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

from sapporo.config import LOGGER, PKG_DIR, get_config, logging_config
from sapporo.database import SNAPSHOT_INTERVAL, init_db
from sapporo.factory import create_service_info
from sapporo.routers import router
from sapporo.schemas import ErrorResponse


def fix_error_handler(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        app_config = get_config()
        if app_config.debug and exc.status_code == 500:
            LOGGER.exception("Internal server error occurred.", exc_info=exc)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                msg=exc.detail,
                status_code=exc.status_code,
            ).model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                msg=str(exc.errors()),
                status_code=400,
            ).model_dump()
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        app_config = get_config()
        if app_config.debug:
            LOGGER.exception("Internal server error occurred.", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                msg="The server encountered an internal error and was unable to complete your request.",
                status_code=500,
            ).model_dump()
        )


def validate_initial_state() -> None:
    """\
    Validate the initial state of the app before starting the app.

    - Check if the service_info file exists.
    - Check if the service_info file is valid JSON.
    """
    service_info_path = get_config().service_info
    if not service_info_path.exists():
        raise FileNotFoundError(f"Service info file not found: {service_info_path}")
    try:
        create_service_info()
    except Exception as e:
        raise ValueError(f"Service info file is invalid: {service_info_path}") from e


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
    logging.config.dictConfig(logging_config(app_config.debug))

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
    LOGGER.debug("App config: %s", app_config)
    validate_initial_state()
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
