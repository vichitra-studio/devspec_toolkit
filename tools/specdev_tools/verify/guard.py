"""The output guard of a binding: a regular expression the output of the commands must match.

The guard is the only protection against a command that exits 0 and ran nothing.  It is applied to the captured output
and nothing else; no test runner's report is read.
"""
from __future__ import annotations

import re


class GuardError(ValueError):
    """A guard that is missing or is not a regular expression; the message says which."""


def compile_guard(guard: str | None) -> re.Pattern[str]:
    """The compiled *guard* (multi-line mode, so ``^`` and ``$`` match at each line of the output).

    Raises:
        GuardError: *guard* is missing or empty, or is not a valid regular expression.
    """
    if not guard:
        raise GuardError("the guard is required: give a regular expression the output must match, such as the name of the test")
    try:
        return re.compile(guard, re.MULTILINE)
    except re.error as exc:
        raise GuardError(f"the guard '{guard}' is not a valid regular expression ({exc})") from exc


def guard_matches(guard: str, output: bytes) -> bool:
    """Whether *guard* is found anywhere in *output* (the output of every command in order; undecodable bytes are replaced).

    Raises:
        GuardError: *guard* is not a valid regular expression.
    """
    return compile_guard(guard).search(output.decode("utf-8", errors="replace")) is not None
