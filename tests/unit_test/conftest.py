#!/usr/bin/env python3
# coding: utf-8
import os
import shlex
import shutil
import signal
import subprocess as sp
import tempfile
from time import sleep
from typing import Generator

import pytest
from _pytest.monkeypatch import MonkeyPatch

TEST_HOST = "127.0.0.1"
TEST_PORT = "8888"


@pytest.fixture()
def delete_env_vars(monkeypatch: MonkeyPatch) -> None:
    for key in os.environ.keys():
        if key.startswith("SAPPORO"):
            monkeypatch.delenv(key)


@pytest.fixture()
def setup_test_server() -> Generator[None, None, None]:
    tempdir = tempfile.mkdtemp()
    proc = sp.Popen(shlex.split(f"sapporo --run-dir {tempdir} "
                                f"--host {TEST_HOST} --port {TEST_PORT}"),
                    stdout=sp.PIPE,
                    stderr=sp.PIPE)
    sleep(3)
    if proc.poll() is not None:
        stderr = proc.communicate()[1]
        raise Exception(
            f"Failed to start the test server.\n{str(stderr)}")
    yield
    os.kill(proc.pid, signal.SIGTERM)
    try:
        shutil.rmtree(tempdir)
    except Exception:
        pass


@pytest.fixture()
def setup_test_server_registered_only_mode() -> Generator[None, None, None]:
    tempdir = tempfile.mkdtemp()
    proc = sp.Popen(shlex.split(f"sapporo --run-dir {tempdir} "
                                f"--host {TEST_HOST} --port {TEST_PORT} "
                                "--run-only-registered-workflows"),
                    stdout=sp.PIPE,
                    stderr=sp.PIPE)
    sleep(3)
    if proc.poll() is not None:
        stderr = proc.communicate()[1]
        raise Exception(
            f"Failed to start the test server.\n{str(stderr)}")
    yield
    os.kill(proc.pid, signal.SIGTERM)
    try:
        shutil.rmtree(tempdir)
    except Exception:
        pass
