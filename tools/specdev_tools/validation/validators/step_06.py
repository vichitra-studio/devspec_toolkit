from __future__ import annotations

import re
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.scope_helpers import dict_items
from ...validation.linter_utils import check_no_duplicates

INV_ID_PATTERN = re.compile(r"^inv-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_06(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    """Validate Step 06 (invariants): duplicate ``inv_id`` values and the ``inv-<kebab>`` id convention.

    Links (``constrains``, ``assumes``) are checked by the schema; whether their targets exist is the
    resolver's job, so this validator reads no other field. Never raises on a wrong-typed value.
    """
    errors: list[SpecError] = []
    rules = dict_items(instance.get("rules"))
    check_no_duplicates(rules, "inv_id", "inv_id", errors)
    for i, rule in enumerate(rules):
        inv_id = rule.get("inv_id")
        if isinstance(inv_id, str) and not INV_ID_PATTERN.match(inv_id):
            errors.append(make_error("E530", f"Invariant at index {i} has inv_id '{inv_id}' that does not follow 'inv-<kebab>' convention"))
    return errors
