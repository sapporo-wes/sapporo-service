#!/usr/local/bin/python3
# coding: utf-8
import os
import secrets
from distutils.util import strtobool

from .lib.util import SECRET_KEY_FILE_PATH


def str2bool(arg):
    if isinstance(arg, str):
        try:
            if strtobool(arg):
                return True
            else:
                return False
        except ValueError:
            raise Exception(
                "Please check your docker-compose.yml:environment, "
                "The bool value should be 'true value are y, yes, t, "
                "true, on and 1; false values are n, no, f, false, off and 0'")
    else:
        if arg:
            return True
        else:
            return False


def generate_secret_key():
    if SECRET_KEY_FILE_PATH.exists():
        with SECRET_KEY_FILE_PATH.open(mode="r") as f:
            for line in f.readlines():
                if line != "":
                    secret_key = line
    else:
        with SECRET_KEY_FILE_PATH.open(mode="w") as f:
            secret_key = secrets.token_urlsafe(32)
            f.write(secret_key)

    return secret_key


def generate_d_config():
    d_config = dict()
    d_config["DEBUG"] = str2bool(os.environ.get("DEBUG", True))
    if d_config["DEBUG"]:
        d_config["ENV"] = "development"
        d_config["TESTING"] = True
    else:
        d_config["ENV"] = "production"
        d_config["TESTING"] = False
    d_config["APPLICATION_ROOT"] = "/"
    d_config["JSON_AS_ASCII"] = False
    d_config["JSON_SORT_KEYS"] = True
    d_config["JSONIFY_PRETTYPRINT_REGULAR"] = True
    d_config["SECRET_KEY"] = generate_secret_key()

    return d_config


d_config = generate_d_config()
GET_RUNS = str2bool(os.environ.get("GET_RUNS", True))
TOKEN_AUTH = str2bool(os.environ.get("TOKEN_AUTH", False))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
