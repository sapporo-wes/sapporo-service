#!/usr/local/bin/python3
# coding: utf-8
import unittest
from pathlib import Path
from sys import path

base_dir = Path(__file__).resolve().parent.parent
path.append(str(base_dir))


class TestControllers(unittest.TestCase):
    def test_create_app(self):
        from app import create_app
        mock_app = create_app()  # NOQA

    def test_get_service_info(self):
        from app import create_app
        mock_app = create_app().test_client()
        response = mock_app.get("/service-info")  # NOQA

    def test_get_workflows_list(self):
        from app import create_app
        mock_app = create_app().test_client()
        response = mock_app.get("/workflows")  # NOQA

    def test_get_runs_false(self):
        from app import create_app
        mock_app = create_app().test_client()
        import app
        app.controllers.GET_RUNS = False
        response = mock_app.get("/runs")  # NOQA

    def test_get_runs_true(self):
        from app import create_app
        mock_app = create_app().test_client()
        import app
        app.controllers.GET_RUNS = True
        response = mock_app.get("/runs")  # NOQA

    def test_get_nothing_entrypoint(self):
        from app import create_app
        mock_app = create_app().test_client()
        response = mock_app.get("/nothing")  # NOQA
