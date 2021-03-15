#!/usr/bin/env python3
# coding: utf-8
import os
import shlex
import shutil
import signal
import subprocess as sp
import tempfile
from os import environ
from pathlib import Path
from time import sleep
from typing import Generator

import pytest
from _pytest.monkeypatch import MonkeyPatch

UNIT_TEST_DIR = Path(__file__).parent.resolve()
ROOT_DIR = UNIT_TEST_DIR.parent.parent.resolve()

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
    if environ.get("TEST_SERVER_MODE", "uwsgi") == "uwsgi":
        pre_proc = sp.run("which uwsgi", shell=True,
                          encoding="utf-8", stdout=sp.PIPE, stderr=sp.PIPE)
        uwsgi_path = pre_proc.stdout.strip()
        proc = sp.Popen(shlex.split(f"{uwsgi_path} "
                                    f"--http {TEST_HOST}:{TEST_PORT} "
                                    f"--chdir {str(ROOT_DIR)} "
                                    "--module sapporo.uwsgi "
                                    "--callable app "
                                    "--master --need-app --single-interpreter "
                                    "--enable-threads --die-on-term --vacuum"),
                        env={"SAPPORO_DEBUG": str(True),
                             "SAPPORO_RUN_DIR": str(tempdir)},
                        encoding="utf-8",
                        stdout=sp.PIPE, stderr=sp.PIPE)
    else:
        pre_proc = sp.run("which sapporo", shell=True,
                          encoding="utf-8", stdout=sp.PIPE, stderr=sp.PIPE)
        sapporo_path = pre_proc.stdout.strip()
        proc = sp.Popen(shlex.split(f"{sapporo_path} "
                                    f"--host {TEST_HOST} --port {TEST_PORT} "
                                    f"--run-dir {tempdir} "),
                        env={"SAPPORO_HOST": str(TEST_HOST),
                             "SAPPORO_PORT": str(TEST_PORT),
                             "SAPPORO_DEBUG": str(True),
                             "SAPPORO_RUN_DIR": str(tempdir)},
                        encoding="utf-8",
                        stdout=sp.PIPE, stderr=sp.PIPE)
    sleep(3)
    if proc.poll() is not None:
        stderr = proc.communicate()[1]
        raise Exception(
            f"Failed to start the test server.\n{str(stderr)}")
    yield
    os.kill(proc.pid, signal.SIGTERM)
    sleep(3)
    try:
        shutil.rmtree(tempdir)
    except Exception:
        pass
