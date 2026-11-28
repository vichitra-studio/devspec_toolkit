"""The output guard: a regular expression searched in the output of all the commands."""
from __future__ import annotations

import pytest

from specdev_tools.verify.guard import GuardError, compile_guard, guard_matches


def test_guard_is_searched_multiline_over_the_concatenated_output() -> None:
    output = b"first command\n  ok\nsecond command\nexpired token rejected passed\n"
    assert guard_matches("^expired token .*passed$", output)
    assert guard_matches("^second command$", output)
    assert not guard_matches("^ok$", output)
    assert not guard_matches("rejected passed\\nnothing", output)


@pytest.mark.parametrize("guard", [None, "", "("])
def test_a_missing_or_invalid_guard_raises(guard: str | None) -> None:
    with pytest.raises(GuardError):
        compile_guard(guard)


def test_undecodable_bytes_do_not_break_the_search() -> None:
    assert guard_matches("passed", b"\xff\xfe passed")
