from __future__ import annotations

from typing import Any

from ...core.errors import SpecError
from ...validation.linter_utils import check_no_duplicates


def validate_step_02a(instance: dict[str, Any], toolkit_root: str) -> list[SpecError]:
    errors: list[SpecError] = []
    for collection, id_field in (("ci_gates", "gate_id"), ("secrets", "secret_id")):
        items = instance.get(collection, [])
        if isinstance(items, list):
            check_no_duplicates(items, id_field, id_field, errors)
    return errors
