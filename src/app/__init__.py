#!/usr/local/bin/python3
# coding: utf-8

from flask import Flask

from .config import d_config
from .controllers import bp_app
from .util import fix_errorhandler, set_logger


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(d_config)
    app.register_blueprint(bp_app, url_prefix="/")
    fix_errorhandler(app)
    set_logger()

    return app
