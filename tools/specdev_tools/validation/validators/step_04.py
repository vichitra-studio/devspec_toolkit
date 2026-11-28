from __future__ import annotations

from typing import Any

from ...core.errors import make_error, SpecError
from ...core.loaders import kebab_id_re
from ...core.scope_helpers import dict_items

FR_ID_PATTERN = kebab_id_re("fr")


def validate_step_04(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    """
    Validate Step 04 (Functional Requirements) logic.
    Checks the fr_id format convention.
    """
    errors: list[SpecError] = []

    requirements = dict_items(instance.get("functional_requirements"))

    for i, req in enumerate(requirements):
        fr_id = req.get("fr_id")

        # Check FR ID format convention
        if isinstance(fr_id, str) and fr_id:
            if not FR_ID_PATTERN.match(fr_id):
                errors.append(make_error("E530", f"FR at index {i} has fr_id '{fr_id}' that does not follow 'fr-<kebab>' convention"))

    return errors
