"""Тесты для задачи t02_duration."""
import pytest

from parse_duration import parse_duration


@pytest.mark.parametrize("text,expected", [
    ("1h30m", 5400),
    ("90s", 90),
    ("2h", 7200),
    ("45m", 2700),
    ("1h2m3s", 3723),
    ("30m2h", 9000),
    ("1h1h", 7200),
    ("0s", 0),
])
def test_parses(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("bad", ["", "abc", "10", "h", "1x"])
def test_rejects_invalid(bad):
    with pytest.raises(ValueError):
        parse_duration(bad)
