"""Тесты для задачи t01_slugify. Исполняемые — генерированный код проверяется по-настоящему."""
import pytest

from slugify import slugify


def test_basic():
    assert slugify("Hello World") == "hello-world"


def test_multiple_spaces():
    assert slugify("  Много   пробелов  ") == "много-пробелов"


def test_underscores_and_dots():
    assert slugify("foo_bar.baz") == "foo-bar-baz"


def test_leading_trailing_hyphens():
    assert slugify("--a--b--") == "a-b"


def test_empty():
    assert slugify("") == ""


def test_only_symbols():
    assert slugify("!!!") == ""


def test_mixed_case_and_punctuation():
    assert slugify("Python 3.12: What's New?") == "python-3-12-what-s-new"


def test_already_slug():
    assert slugify("already-a-slug") == "already-a-slug"
