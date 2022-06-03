#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path

from setuptools import setup

BASE_DIR: Path = Path(__file__).parent.resolve()
LONG_DESCRIPTION: Path = BASE_DIR.joinpath("README.md")

setup(
    name="sapporo",
    version="1.2.4",
    description="The sapporo-service is a standard implementation conforming to "
    "the Global Alliance for Genomics and Health (GA4GH) Workflow Execution "
    "Service (WES) API specification.",
    long_description=LONG_DESCRIPTION.open(mode="r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="DDBJ(DNA Data Bank of Japan)",
    author_email="t.ohta@nig.ac.jp",
    url="https://github.com/sapporo-wes/sapporo-service",
    license="Apache2.0",
    python_requires=">=3.6",
    platforms="any",
    packages=["sapporo", "sapporo.model"],
    package_data={
        "sapporo": [
            "executable_workflows.json",
            "executable_workflows.schema.json",
            "run.sh",
            "service-info.json",
            "service-info.schema.json",
        ]
    },
    include_package_data=True,
    install_requires=[
        "cwl-inputs-parser>=1.0.1",
        "flask-cors",
        "flask",
        "jsonschema",
        "requests",
        "uwsgi",
    ],
    tests_require=[
        "flake8",
        "isort",
        "mypy",
        "pytest",
        "types-requests",
        "typing-extensions",
    ],
    extras_require={
        "tests": [
            "flake8",
            "isort",
            "mypy",
            "pytest",
            "types-requests",
            "typing-extensions",
        ],
    },
    entry_points={
        "console_scripts": [
            "sapporo=sapporo.app:main",
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: Flask",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
)
