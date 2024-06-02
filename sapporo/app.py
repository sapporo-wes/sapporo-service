import uvicorn
from fastapi import FastAPI

from sapporo.config import PKG_DIR, AppConfig, get_config
from sapporo.factory import create_service_info
from sapporo.routers import router


def validate_initial_state(app_config: AppConfig) -> None:
    """\
    Validate the initial state of the app before starting the app.

    - Check if the service_info file exists.
    - Check if the service_info file is valid JSON.
    """
    service_info_path = app_config.service_info
    if not service_info_path.exists():
        raise FileNotFoundError(f"Service info file not found: {service_info_path}")
    try:
        create_service_info(service_info_path)
    except Exception as e:
        raise ValueError(f"Service info file is invalid: {service_info_path}") from e


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    _app_config = get_config()

    return app


def main() -> None:
    app_config = get_config()  # Cache the config
    # TODO logging app_config
    validate_initial_state(app_config)
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
