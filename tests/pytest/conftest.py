#!/usr/bin/env python3
# coding: utf-8
import os

from _pytest.monkeypatch import MonkeyPatch

import pytest


@pytest.fixture
def delete_env_vars(monkeypatch: MonkeyPatch) -> None:
    for key in os.environ.keys():
        if key.startswith("SAPPORO"):
            monkeypatch.delenv(key)
