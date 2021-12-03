#!/usr/bin/env python3
# coding: utf-8
from flask import Flask

from sapporo.app import create_app, get_config
from sapporo.config import Config

config: Config = get_config()
app: Flask = create_app(config)
