"""Тесты для задачи t03_backoff."""
import pytest

from backoff_delays import backoff_delays


def test_default():
    assert backoff_delays(3) == [1.0, 2.0, 4.0]


def test_custom_base():
    assert backoff_delays(3, base=0.5) == [0.5, 1.0, 2.0]


def test_cap_is_respected():
    assert backoff_delays(5, cap=5.0) == [1.0, 2.0, 4.0, 5.0, 5.0]


def test_zero_and_negative():
    assert backoff_delays(0) == []
    assert backoff_delays(-2) == []


def test_types_are_float():
    for v in backoff_delays(3):
        assert isinstance(v, float)


def test_custom_factor():
    assert backoff_delays(4, base=1.0, factor=3.0) == [1.0, 3.0, 9.0, 27.0]
