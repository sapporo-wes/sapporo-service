import uvicorn
from fastapi import FastAPI

from sapporo.config import PKG_DIR, get_config
from sapporo.routers import router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    return app


def main() -> None:
    app_config = get_config()
    # TODO logging app_config
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
