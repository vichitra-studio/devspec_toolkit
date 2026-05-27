"""Unit tests for derive_allowed_upstream in core.registry."""
from __future__ import annotations

from specdev_tools.core.registry import derive_allowed_upstream

STEPS = ["00", "01", "02", "02a", "03", "04", "05"]


def test_normal_case_middle_step():
    result = derive_allowed_upstream("03", STEPS)
    assert result == ["00", "01", "02", "02a"]


def test_first_step_returns_empty():
    result = derive_allowed_upstream("00", STEPS)
    assert result == []


def test_last_step_returns_all_preceding():
    result = derive_allowed_upstream("05", STEPS)
    assert result == ["00", "01", "02", "02a", "03", "04"]


def test_step_not_in_list_returns_empty():
    result = derive_allowed_upstream("99", STEPS)
    assert result == []


def test_empty_steps_list():
    result = derive_allowed_upstream("03", [])
    assert result == []


def test_single_element_list_match():
    result = derive_allowed_upstream("00", ["00"])
    assert result == []


def test_single_element_list_no_match():
    result = derive_allowed_upstream("01", ["00"])
    assert result == []


WATERFALL = [
    "00", "01", "02", "02a", "03", "04", "05", "06", "07", "08",
    "09", "10", "11", "12", "13", "13a", "14", "15", "16", "16a", "16b", "16c",
]


def test_letter_suffix_step_02a():
    """02a has a letter suffix and should return the three steps that precede it."""
    result = derive_allowed_upstream("02a", WATERFALL)
    assert result == ["00", "01", "02"]


def test_letter_suffix_step_16c_last():
    """16c is the last step in the waterfall; all other steps are valid upstreams."""
    result = derive_allowed_upstream("16c", WATERFALL)
    assert result == ["00", "01", "02", "02a", "03", "04", "05", "06", "07", "08",
                      "09", "10", "11", "12", "13", "13a", "14", "15", "16", "16a", "16b"]
