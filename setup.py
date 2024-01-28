#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path

from setuptools import setup

from sapporo import __version__

BASE_DIR: Path = Path(__file__).parent.resolve()
LONG_DESCRIPTION: Path = BASE_DIR.joinpath("README.md")

setup(
    name="sapporo",
    version=__version__,
    description="The sapporo-service is a standard implementation conforming to the Global Alliance for Genomics and Health (GA4GH) Workflow Execution Service (WES) API specification.",
    long_description=LONG_DESCRIPTION.open(mode="r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="DDBJ(Bioinformatics and DDBJ Center)",
    author_email="tazro.ohta@chiba-u.jp",
    url="https://github.com/sapporo-wes/sapporo-service",
    license="Apache2.0",
    python_requires=">=3.8",
    platforms="any",
    packages=["sapporo", "sapporo.model"],
    package_data={
        "sapporo": [
            "sapporo/auth_config.json",
            "sapporo/auth_config.schema.json",
            "sapporo/executable_workflows.json",
            "sapporo/executable_workflows.schema.json",
            "sapporo/run.sh",
            "sapporo/service-info.json",
            "sapporo/service-info.schema.json",
        ]
    },
    include_package_data=True,
    install_requires=[
        "cwl-inputs-parser>=1.0.2",
        "flask_jwt_extended",
        "flask-cors",
        "flask",
        "jsonschema",
        "multiqc",
        "psutil",
        "python-magic",
        "pyyaml",
        "requests",
        "rocrate",
    ],
    extras_require={
        "tests": [
            "flake8",
            "isort",
            "mypy",
            "pytest",
            "types-jsonschema",
            "types-Flask-Cors",
            "types-Flask",
            "types-PyYAML",
            "types-requests",
            "types-setuptools",
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
)
