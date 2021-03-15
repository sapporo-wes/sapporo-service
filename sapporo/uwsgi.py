#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from typing import Dict, Union

from flask import Flask

from sapporo.app import create_app, handle_default_params, parse_args

params: Dict[str, Union[str, int, Path]] = \
    handle_default_params(parse_args([]))
app: Flask = create_app(params)
