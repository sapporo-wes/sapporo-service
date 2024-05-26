import uvicorn
from fastapi import FastAPI

from sapporo.config import APP_CONFIG, PKG_DIR, AppConfig
from sapporo.routers import router


def create_app(app_config: AppConfig = APP_CONFIG) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    return app


def main(app_config: AppConfig = APP_CONFIG) -> None:
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
