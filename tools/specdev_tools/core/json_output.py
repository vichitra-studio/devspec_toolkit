"""Shared JSON output formatter for CLI commands.

Converts ``list[SpecError]`` into a deterministic JSON envelope with
``status``, ``error_count``, ``warning_count``, and ``errors`` fields.

Usage::

    from .core.json_output import format_errors_json
    print(format_errors_json(spec_errors, context={"command": "validate"}))
"""
from __future__ import annotations

import json
from typing import Any

from .errors import SpecError


def format_errors_json(
    errors: list[SpecError],
    context: dict[str, Any] | None = None,
) -> str:
    """Serialize a list of ``SpecError`` objects to a JSON string.

    Parameters
    ----------
    errors:
        Validated/linted errors to serialize.
    context:
        Optional extra keys merged into the top-level JSON object
        (e.g. ``{"command": "validate-all"}``).

    Returns
    -------
    str
        Pretty-printed JSON string.
    """
    output: list[dict[str, Any]] = []
    for err in errors:
        entry: dict[str, Any] = {
            "code": err.code,
            "message": err.message,
            "severity": "warning" if err.code.startswith("W") else "error",
        }
        if err.path:
            entry["path"] = err.path
        output.append(entry)

    error_count = sum(1 for e in errors if e.code.startswith("E"))
    warning_count = sum(1 for e in errors if e.code.startswith("W"))

    if not errors:
        status = "PASS"
    elif error_count == 0:
        status = "WARN"
    else:
        status = "FAIL"

    status_value = status  # preserve computed value
    result: dict[str, Any] = {}
    if context:
        result.update(context)
    # Set core fields AFTER context update so they always win
    result["status"] = status_value
    result["error_count"] = error_count
    result["warning_count"] = warning_count
    result["errors"] = output
    return json.dumps(result, indent=2)
