import os
from pathlib import Path

import yaml
from pydantic import BaseModel

from sapporo.utils import inside_docker, str2bool

PKG_DIR = Path(__file__).resolve().parent


GA4GH_WES_SPEC_PATH = PKG_DIR.joinpath("ga4gh-wes-spec-1.1.0.yml")
GA4GH_WES_SPEC = yaml.safe_load(GA4GH_WES_SPEC_PATH.read_text(encoding="utf-8"))


# === Global configuration ===


class AppConfig(BaseModel):
    host: str
    port: int
    debug: bool

    @classmethod
    def from_env_or_default(cls) -> "AppConfig":
        return cls(
            host=os.environ.get("SAPPORO_HOST", "0.0.0.0" if inside_docker() else "localhost"),
            port=int(os.environ.get("SAPPORO_PORT", 1122)),
            debug=str2bool(os.environ.get("SAPPORO_DEBUG", False)),
        )


APP_CONFIG = AppConfig.from_env_or_default()


# === Logging ===
