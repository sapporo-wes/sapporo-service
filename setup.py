#!/usr/bin/env python3
# coding: utf-8
from pathlib import Path
from typing import List

from setuptools import setup

BASE_DIR: Path = Path(__file__).parent.resolve()
REQUIREMENTS_TEXT: Path = BASE_DIR.joinpath("requirements.txt")
LONG_DESCRIPTION: Path = BASE_DIR.joinpath("README.md")


def read_requirements_txt() -> List[str]:
    with REQUIREMENTS_TEXT.open(mode="r") as f:
        packages: List[str] = \
            [str(line) for line in f.read().splitlines() if line != ""]

    return packages


def main() -> None:
    setup(name="sapporo",
          version="1.0.9",
          description="Implementation of a GA4GH workflow execution " +
                      "service that can easily support various " +
                      "workflow runners.",
          long_description=LONG_DESCRIPTION.open(mode="r").read(),
          long_description_content_type="text/markdown",
          author="DDBJ(DNA Data Bank of Japan)",
          author_email="t.ohta@nig.ac.jp",
          url="https://github.com/ddbj/SAPPORO-service",
          license="Apache2.0",
          python_requires=">=3.6",
          platforms="any",
          include_package_data=True,
          zip_safe=False,
          classifiers=["Programming Language :: Python"],
          packages=["sapporo"],
          install_requires=read_requirements_txt(),
          entry_points={
              "console_scripts": [
                  "sapporo=sapporo.app:main",
              ]
          }
          )


if __name__ == "__main__":
    main()
