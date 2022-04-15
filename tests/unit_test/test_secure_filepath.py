#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=redundant-u-string-prefix
from pathlib import Path

from sapporo.run import secure_filepath


def test_contain_space() -> None:
    assert secure_filepath("My cool movie.mov") == Path("My_cool_movie.mov")


def test_prev_dir() -> None:
    assert secure_filepath("../../../etc/passwd") == Path("etc/passwd")


def test_root_dir() -> None:
    assert secure_filepath("/foo/bar") == Path("foo/bar")


def test_contain_umlauts() -> None:
    assert secure_filepath(
        u"i contain cool \xfcml\xe4uts.txt") == \
        Path("i_contain_cool_umlauts.txt")


def test_japanese_filename() -> None:
    assert secure_filepath("/フーfoo/バーbar") == Path("foo/bar")


def test_contain_pipe() -> None:
    assert secure_filepath("/||/|foo/bar") == Path("foo/bar")


def test_contain_ampersand() -> None:
    assert secure_filepath("/&&/&foo/bar") == Path("foo/bar")


def test_contain_fullsize_ampersand() -> None:
    assert secure_filepath("/＆foo/bar") == Path("foo/bar")


def test_only_dot() -> None:
    assert secure_filepath(".") == Path("")


def test_only_double_dot() -> None:
    assert secure_filepath("..") == Path("")


def test_only_root() -> None:
    assert secure_filepath("/") == Path("")


def test_hidden_file() -> None:
    assert secure_filepath(".foo") == Path("foo")


def test_ds_store() -> None:
    assert secure_filepath("._.DS_STORE") == Path("DS_STORE")
