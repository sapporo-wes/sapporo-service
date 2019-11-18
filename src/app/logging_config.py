#!/usr/local/bin/python3
# coding: utf-8
from copy import deepcopy

from .lib.util import LOG_FILE_PATH

TEMPLATE = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "long": {
            "format": "[%(asctime)s] %(levelname)s - " +
            "%(filename)s#%(funcName)s:%(lineno)d: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stderr"
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "formatter": "default",
            "filename": str(LOG_FILE_PATH),
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}

wsgi_info = deepcopy(TEMPLATE)
wsgi_info["root"]["handlers"] = ["file"]
wsgi_debug = deepcopy(TEMPLATE)
wsgi_debug["handlers"]["file"]["level"] = "DEBUG"
wsgi_debug["handlers"]["file"]["formatter"] = "long"
wsgi_debug["root"]["handlers"] = ["file"]
wsgi_debug["root"]["level"] = "DEBUG"

local_info = deepcopy(TEMPLATE)
local_debug = deepcopy(TEMPLATE)
local_debug["handlers"]["console"]["level"] = "DEBUG"
local_debug["handlers"]["console"]["formatter"] = "long"
local_debug["handlers"]["file"]["level"] = "DEBUG"
local_debug["handlers"]["file"]["formatter"] = "long"
local_debug["root"]["level"] = "DEBUG"
