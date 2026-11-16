from __future__ import annotations

from typing import Any

from ...core.errors import make_error, SpecError
from ...validation.linter_utils import check_no_duplicates

_REQUIRED_FIELDS = ("id", "owner", "created_at", "project_skeleton", "validators", "build_status")
_BUILD_STATUSES = ("pending", "green", "red")


def validate_step_15(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    """Deep checks of a step 15 artifact: required fields, field types, ``build_status`` and unique ``row_id``.

    ``row_id`` is the only uniqueness rule: an API may be realised by several rows, so ``realises`` is not checked
    for overlap here, and whether a ``realises`` id names a real API is the resolver's job. Never raises on
    wrong-typed input; the schema reports the type errors.
    """
    errors: list[SpecError] = []
    errors.extend(_structure_errors(instance))
    errors.extend(_build_status_errors(instance))
    rows = instance.get("interface_map")
    if isinstance(rows, list):
        check_no_duplicates(rows, "row_id", "row_id", errors)
    return errors


def _structure_errors(instance: dict[str, Any]) -> list[SpecError]:
    """E520 for each missing required field and each of the three structured fields that has the wrong type."""
    errors = [make_error("E520", f"Missing required field: {field}") for field in _REQUIRED_FIELDS if field not in instance]
    expected = (("project_skeleton", dict, "an object"), ("interface_map", list, "an array"), ("validators", list, "an array"))
    for field, kind, label in expected:
        if field in instance and not isinstance(instance[field], kind):
            errors.append(make_error("E520", f"{field} must be {label}"))
    return errors


def _build_status_errors(instance: dict[str, Any]) -> list[SpecError]:
    """E530 for an unknown ``build_status``; E520 for ``green`` with no validator."""
    status = instance.get("build_status")
    if not isinstance(status, str):
        return []
    if status not in _BUILD_STATUSES:
        return [make_error("E530", f"Invalid build_status '{status}'. Must be one of {sorted(_BUILD_STATUSES)}")]
    validators = instance.get("validators")
    if status == "green" and isinstance(validators, list) and not validators:
        return [make_error("E520", "Build status is 'green' but 'validators' list is empty. Green status requires at least one validator.")]
    return []
