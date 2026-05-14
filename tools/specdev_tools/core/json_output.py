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


def _make_remediation(err: SpecError) -> dict[str, Any] | None:
    """Generate a unified remediation block for actionable E110/E530 errors.

    Shape: {guide_code, parameters: {fix_kind, candidates[], references[]}, owner_story}
    §17.4 outer envelope + §7.1 candidates inside parameters.
    """
    if err.subcode == "UNKNOWN_CANONICAL_ID":
        cid = err.value or "<canonical-id>"
        file_ref = f'"{err.file}"' if err.file else "<spec-file>"
        return {
            "guide_code": "E110-UNKNOWN_CANONICAL_ID",
            "parameters": {
                "fix_kind": "REGISTER_CANON_ENTRY",
                "candidates": [
                    {
                        "kind": "canon_accept",
                        "command": (
                            f"specdev canon-accept --from {file_ref}"
                            " --repo-root ./devspec_toolkit --git-root ."
                            " --namespace cn:project: --owner product"
                        ),
                        "rationale": (
                            f"Add '{cid}' to canonical_proposals in the artifact,"
                            " then run canon-accept to promote it into spec/canon/"
                        ),
                    }
                ],
                "references": [],
            },
            "owner_story": (
                f"Canonical ID '{cid}' is not registered — declare it in"
                " canonical_proposals then run specdev canon-accept"
            ),
        }

    # Guard: only emit command-prefix remediation when the field IS a `command`
    # field. All command-prefix E530s from _scan_node set jq_path ending in
    # ".command" (e.g. ".jobs[0].steps[0].command"). Non-command INVENTED_ENUM_OR_ID
    # errors (stage, unit, pr_rules) return None and get no remediation block.
    if err.subcode == "INVENTED_ENUM_OR_ID" and err.jq_path and err.jq_path.endswith(".command"):
        prefix = err.value or "<prefix>"
        return {
            "guide_code": "E530-INVENTED_ENUM_OR_ID",
            "parameters": {
                "fix_kind": "ALLOWLIST_OR_REF",
                "candidates": [
                    {
                        "kind": "extend_prefixes",
                        "command": (
                            f"specdev json insert spec/canon/command_prefixes.json"
                            f" '.allowed_prefixes' '\"{prefix}\"'"
                        ),
                        "rationale": f"Add '{prefix}' to the project command-prefix allowlist",
                    },
                    {
                        "kind": "attach_command_ref",
                        "command": (
                            f"specdev json insert spec/canon/kinds/command.json '.entries'"
                            f' \'{{"id":"cn:project:command:{prefix}","kind":"command",'
                            f'"preferred_label":"{prefix}","owner":"engineering"}}\''
                        ),
                        "rationale": (
                            f"Register '{prefix}' as a canonical command entry,"
                            " then add a sibling command_ref in the artifact"
                        ),
                    },
                ],
                "references": [],
            },
            "owner_story": (
                f"Command prefix '{prefix}' is not in the allowlist —"
                " extend spec/canon/command_prefixes.json or register"
                " in spec/canon/kinds/command.json"
            ),
        }

    if err.subcode == "LINKED_TEST_FILE_NOT_FOUND":
        path = err.value or "<test-path>"
        file_arg = f'"{err.file}"' if err.file else "<spec-file>"
        jq_arg = err.jq_path or ".linked_test_expectation"
        return {
            "guide_code": "E530-LINKED_TEST_FILE_NOT_FOUND",
            "parameters": {
                "fix_kind": "CREATE_OR_FIX_TEST_PATH",
                "candidates": [
                    {
                        "kind": "correct_path",
                        "command": (
                            f"specdev json patch {file_arg}"
                            f" '{jq_arg}' '\"<correct-path>\"'"
                        ),
                        "rationale": (
                            "Update linked_test_expectation to point to an"
                            " existing test file"
                        ),
                    },
                ],
                "references": [],
            },
            "owner_story": (
                f"Test file '{path}' referenced in linked_test_expectation"
                " does not exist on disk"
            ),
        }

    return None


def error_to_dict(err: SpecError) -> dict[str, Any]:
    """Serialize a single ``SpecError`` to a JSON-ready dict."""
    entry: dict[str, Any] = {
        "code": err.code,
        "message": err.message,
        "severity": "warning" if err.code.startswith("W") else "error",
    }
    if err.path is not None:
        entry["path"] = err.path
    if err.subcode is not None:
        entry["subcode"] = err.subcode
    if err.file is not None:
        entry["file"] = err.file
    if err.jq_path is not None:
        entry["jq_path"] = err.jq_path
    if err.value is not None:
        entry["value"] = err.value
    remediation = _make_remediation(err)
    if remediation is not None:
        entry["remediation"] = remediation
    return entry


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
    output = [error_to_dict(err) for err in errors]

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
