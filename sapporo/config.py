import logging
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import FastAPI
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, CliSettingsSource, PydanticBaseSettingsSource

from sapporo.utils import inside_docker

# Bare type annotations (PEP 526) — resolved lazily via __getattr__
GA4GH_WES_SPEC: dict[str, Any]
PKG_DIR: Path


@cache
def _load_pkg_dir() -> Path:
    return Path(str(files("sapporo")))


@cache
def _load_ga4gh_wes_spec() -> dict[str, Any]:
    pkg = _load_pkg_dir()
    spec: dict[str, Any] = yaml.safe_load(pkg.joinpath("ga4gh-wes-spec-1.1.0.yml").read_text(encoding="utf-8"))
    return spec


def __getattr__(name: str) -> Any:
    if name == "PKG_DIR":
        pkg_dir = _load_pkg_dir()
        globals()["PKG_DIR"] = pkg_dir
        return pkg_dir
    if name == "GA4GH_WES_SPEC":
        spec = _load_ga4gh_wes_spec()
        globals()["GA4GH_WES_SPEC"] = spec
        return spec
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


SAPPORO_WES_SPEC_VERSION = "2.1.0"


# === Global configuration ===


def _default_host() -> str:
    return "0.0.0.0" if inside_docker() else "127.0.0.1"


def _pkg_path(name: str) -> Path:
    return _load_pkg_dir().joinpath(name)


class AppConfig(BaseSettings):
    """Application configuration.

    Parameter priority: CLI > Environment variables > Init (keyword arguments) > Default values.
    """

    model_config = {
        "env_prefix": "SAPPORO_",
        "cli_prog_name": "sapporo",
        "cli_kebab_case": True,
        "cli_implicit_flags": True,
        "cli_exit_on_error": True,
    }

    host: str = Field(default_factory=_default_host)
    port: int = Field(default=1122)
    debug: bool = Field(default=False)
    run_dir: Path = Field(default_factory=lambda: Path.cwd().joinpath("runs"))
    service_info: Path = Field(default_factory=lambda: _pkg_path("service_info.json"))
    executable_workflows: Path = Field(default_factory=lambda: _pkg_path("executable_workflows.json"))
    run_sh: Path = Field(default_factory=lambda: _pkg_path("run.sh"))
    url_prefix: str = Field(default="")
    base_url: str = Field(default="")
    allow_origin: str = Field(default="*")
    auth_config: Path = Field(default_factory=lambda: _pkg_path("auth_config.json"))
    run_remove_older_than_days: int | None = Field(default=None)
    snapshot_interval: int = Field(default=30)

    @field_validator("snapshot_interval")
    @classmethod
    def _validate_snapshot_interval(cls, v: int) -> int:
        if v < 1:
            msg = "The value of --snapshot-interval (SAPPORO_SNAPSHOT_INTERVAL) must be greater than or equal to 1."
            raise ValueError(msg)
        return v

    @field_validator("run_remove_older_than_days")
    @classmethod
    def _validate_run_remove_older_than_days(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            msg = "The value of --run-remove-older-than-days (SAPPORO_RUN_REMOVE_OLDER_THAN_DAYS) must be greater than or equal to 1."
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _compute_base_url(self) -> "AppConfig":
        if not self.base_url:
            self.base_url = f"http://{self.host}:{self.port}{self.url_prefix}"
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            CliSettingsSource(settings_cls, cli_parse_args=True),
            env_settings,
            init_settings,
        )


@cache
def get_config() -> AppConfig:
    """Get the configuration for the application.

    This function initializes and returns the configuration used throughout the application.
    The initial state is cached using `cache` to ensure that the configuration is only loaded once when the application starts.

    Parameter priority: CLI > Environment variables > Init (keyword arguments) > Default values.
    """
    return AppConfig()


# === Logging ===


# Ref.: https://github.com/encode/uvicorn/blob/master/uvicorn/config.py
def logging_config(debug: bool = False) -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": True,
            },
            "sqlalchemy": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s DB - %(message)s",
                "use_colors": True,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "sqlalchemy": {
                "formatter": "sqlalchemy",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "sapporo": {"handlers": ["default"], "level": "DEBUG" if debug else "INFO", "propagate": False},
            "sqlalchemy.engine": {
                "handlers": ["sqlalchemy"],
                "level": "INFO" if debug else "WARNING",
                "propagate": False,
            },
        },
    }


LOGGER = logging.getLogger("sapporo")


# === Const ===


RUN_DIR_STRUCTURE: dict[str, str] = {
    "runtime_info": "runtime_info.json",
    "run_request": "run_request.json",
    "state": "state.txt",
    "exe_dir": "exe",
    "outputs_dir": "outputs",
    "outputs": "outputs.json",
    "wf_params": "exe/workflow_params.json",
    "start_time": "start_time.txt",
    "end_time": "end_time.txt",
    "exit_code": "exit_code.txt",
    "stdout": "stdout.log",
    "stderr": "stderr.log",
    "pid": "run.pid",
    "wf_engine_params": "workflow_engine_params.txt",
    "cmd": "cmd.txt",
    "system_logs": "system_logs.json",
    "username": "username.txt",
    "ro_crate": "ro-crate-metadata.json",
    "multiqc_stats": "multiqc_general_stats.json",
}


RunDirStructureKeys = Literal[
    "runtime_info",
    "run_request",
    "state",
    "exe_dir",
    "outputs_dir",
    "outputs",
    "wf_params",
    "start_time",
    "end_time",
    "exit_code",
    "stdout",
    "stderr",
    "pid",
    "wf_engine_params",
    "cmd",
    "system_logs",
    "username",
    "ro_crate",
]


# === API Spec ===


API_DESCRIPTION = f"""\
*Run standard workflows on workflow execution platforms in a platform-agnostic way.*

## Executive Summary

The Workflow Execution Service (WES) API provides a standard way for users to submit workflow requests to workflow execution systems and monitor their execution. This API lets users run a single workflow (currently [**CWL**](https://www.commonwl.org/) or [**WDL**](http://www.openwdl.org/) formatted workflows, with other types potentially supported in the future) on multiple different platforms, clouds, and environments.

Key features of the API:

- Request that a workflow be run.
- Pass parameters to that workflow (e.g., input files, command-line arguments).
- Get information about running workflows (e.g., status, errors, output file locations).
- Cancel a running workflow.

## Sapporo-WES Extensions

`sapporo-wes-{SAPPORO_WES_SPEC_VERSION}` extends the original WES API to provide enhanced functionality and support for additional features. This document describes the WES API and details the specific endpoints, request formats, and responses, aimed at developers of WES-compatible services and clients.
"""


def add_openapi_info(app: FastAPI) -> None:
    app.title = "GA4GH Workflow Execution Service API specification extended for the Sapporo"
    app.version = SAPPORO_WES_SPEC_VERSION
    app.description = API_DESCRIPTION
    app.servers = [{"url": get_config().base_url}]
    app.license_info = {
        "name": "Apache 2.0",
        "identifier": "Apache-2.0",
        "url": "https://github.com/sapporo-wes/sapporo-service/blob/main/LICENSE",
    }
    app.contact = {
        "name": "Sapporo-WES Project Team",
        "url": "https://github.com/sapporo-wes/sapporo-service/issues",
    }

    # Store original openapi function
    original_openapi = app.openapi

    # Add security schemes to OpenAPI
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        # Temporarily restore original to avoid recursion
        app.openapi = original_openapi  # type: ignore[method-assign]
        openapi_schema = app.openapi()
        app.openapi = custom_openapi  # type: ignore[method-assign]

        openapi_schema["components"] = openapi_schema.get("components", {})

        # Add RunRequestJson schema (referenced by openapi_extra in POST /runs)
        from sapporo.schemas import RunRequestJson

        run_request_json_schema = RunRequestJson.model_json_schema(ref_template="#/components/schemas/{model}")
        # Extract $defs (referenced models like FileObject) and merge into components/schemas
        defs = run_request_json_schema.pop("$defs", {})
        openapi_schema["components"]["schemas"] = openapi_schema.get("components", {}).get("schemas", {})
        openapi_schema["components"]["schemas"]["RunRequestJson"] = run_request_json_schema
        for def_name, def_schema in defs.items():
            if def_name not in openapi_schema["components"]["schemas"]:
                openapi_schema["components"]["schemas"][def_name] = def_schema

        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token obtained from POST /token endpoint",
            },
            "oauth2PasswordFlow": {
                "type": "oauth2",
                "flows": {"password": {"tokenUrl": "/token", "scopes": {}}},
                "description": "OAuth2 password flow for sapporo authentication",
            },
        }
        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


def dump_openapi_schema(app: FastAPI) -> str:
    return yaml.dump(app.openapi())


if __name__ == "__main__":
    from sapporo.app import create_app

    f_app = create_app()
    out = _load_pkg_dir().joinpath("../openapi/sapporo-wes-spec-2.1.0.yml")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write(dump_openapi_schema(f_app))
