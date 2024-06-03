import logging
import os
import sys
from argparse import ArgumentParser, Namespace
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel

from sapporo.utils import inside_docker, str2bool

PKG_DIR = Path(__file__).resolve().parent


GA4GH_WES_SPEC_PATH = PKG_DIR.joinpath("ga4gh-wes-spec-1.1.0.yml")
GA4GH_WES_SPEC = yaml.safe_load(GA4GH_WES_SPEC_PATH.read_text(encoding="utf-8"))


# === Global configuration ===


class AppConfig(BaseModel):
    host: str = "0.0.0.0" if inside_docker() else "127.0.0.1"
    port: int = 1122
    debug: bool = False
    run_dir: Path = Path.cwd().joinpath("runs")
    get_runs: bool = True
    workflow_attachment: bool = True
    registered_only_mode: bool = False
    service_info: Path = PKG_DIR.joinpath("service_info.json")
    executable_workflows: Path = PKG_DIR.joinpath("executable_workflows.json")
    run_sh: Path = PKG_DIR.joinpath("run.sh")
    url_prefix: str = "/"
    allow_origin: str = "*"
    auth_config: Path = PKG_DIR.joinpath("auth_config.json")


default_config = AppConfig()


def parse_args(args: Optional[List[str]] = None) -> Namespace:
    parser = ArgumentParser(
        description="The sapporo-service is a standard implementation conforming to the Global Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API specification.",
    )

    parser.add_argument(
        "--host",
        type=str,
        metavar="",
        help="The host address for the service. (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        metavar="",
        help="The port number for the service. (default: 1122)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode."
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        metavar="",
        help="Directory where the runs are stored. (default: ./runs)"
    )
    parser.add_argument(
        "--disable-get-runs",
        action="store_true",
        help="Disable the GET /runs endpoint."
    )
    parser.add_argument(
        "--disable-workflow-attachment",
        action="store_true",
        help="Disable workflow attachment handling on the POST /runs endpoint."
    )
    parser.add_argument(
        "--run-only-registered-workflows",
        action="store_true",
        help="Allow only registered workflows to run."
    )
    parser.add_argument(
        "--service-info",
        type=Path,
        metavar="",
        help="Path to the service_info.json file."
    )
    parser.add_argument(
        "--executable-workflows",
        type=Path,
        metavar="",
        help="Path to the executable_workflows.json file."
    )
    parser.add_argument(
        "--run-sh",
        type=Path,
        metavar="",
        help="Path to the run.sh script."
    )
    parser.add_argument(
        "--url-prefix",
        type=str,
        metavar="",
        help="URL prefix for the service endpoints. (default: /)"
    )
    parser.add_argument(
        "--allow-origin",
        type=str,
        metavar="",
        help="Access-Control-Allow-Origin header value. (default: *)"
    )
    parser.add_argument(
        "--auth-config",
        type=Path,
        metavar="",
        help="Path to the auth_config.json file."
    )

    return parser.parse_args(args)


@lru_cache(maxsize=None)
def get_config() -> AppConfig:
    """
    Get the configuration for the application.

    This function initializes and returns the configuration used throughout the application.
    The initial state is cached using `lru_cache` to ensure that the configuration is only loaded once when the application starts.
    This state depends on `os.environ` and `sys.argv`, but passing them as arguments is not necessary as the primary goal is to cache the initial values.

    Parameter priority:

    1. Command line arguments
    2. Environment variables
    3. Default values
    """
    args = parse_args(sys.argv[1:])

    return AppConfig(
        host=args.host or os.environ.get("SAPPORO_HOST", default_config.host),
        port=args.port or int(os.environ.get("SAPPORO_PORT", default_config.port)),
        debug=args.debug or str2bool(os.environ.get("SAPPORO_DEBUG", default_config.debug)),
        run_dir=args.run_dir or Path(os.environ.get("SAPPORO_RUN_DIR", default_config.run_dir)),
        get_runs=False if args.disable_get_runs else str2bool(os.environ.get("SAPPORO_GET_RUNS", default_config.get_runs)),
        workflow_attachment=False if args.disable_workflow_attachment else str2bool(
            os.environ.get("SAPPORO_WORKFLOW_ATTACHMENT", default_config.workflow_attachment)),
        registered_only_mode=True if args.run_only_registered_workflows else str2bool(
            os.environ.get("SAPPORO_RUN_ONLY_REGISTERED_WORKFLOWS", default_config.registered_only_mode)),
        service_info=args.service_info or Path(os.environ.get("SAPPORO_SERVICE_INFO", default_config.service_info)),
        executable_workflows=args.executable_workflows or Path(os.environ.get("SAPPORO_EXECUTABLE_WORKFLOWS", default_config.executable_workflows)),
        run_sh=args.run_sh or Path(os.environ.get("SAPPORO_RUN_SH", default_config.run_sh)),
        url_prefix=args.url_prefix or os.environ.get("SAPPORO_URL_PREFIX", default_config.url_prefix),
        allow_origin=args.allow_origin or os.environ.get("SAPPORO_ALLOW_ORIGIN", default_config.allow_origin),
        auth_config=args.auth_config or Path(os.environ.get("SAPPORO_AUTH_CONFIG", default_config.auth_config)),
    )

# === Logging ===


# Ref.: https://github.com/encode/uvicorn/blob/master/uvicorn/config.py
def logging_config(debug: bool = False) -> Dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": True,
            }
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            }
        },
        "loggers": {
            "sapporo": {
                "handlers": ["default"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False
            }
        }
    }


LOGGER = logging.getLogger("sapporo")
