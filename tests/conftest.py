#!/usr/bin/env python3
# coding: utf-8
import os

import pytest
from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def delete_env_vars(monkeypatch: MonkeyPatch) -> None:
    for key in os.environ.keys():
        if key.startswith("SAPPORO"):
            monkeypatch.delenv(key)
