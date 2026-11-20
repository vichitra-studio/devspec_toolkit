from __future__ import annotations

import re
from typing import Any, Optional

from ...core.scope_helpers import as_list, dict_items
from ...core.errors import make_error, SpecError


# Valid section name patterns: numeric step prefix (00_*, 16a_*) OR any
# domain-style identifier (tables, indexes, my-section, etc.).  The original
# strict pattern r"^[0-9]{2}[a-z]?_" incorrectly rejected non-numeric section
# names used by domain-specific schemas.
_STEP_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def validate_step_13(instance: dict[str, Any], toolkit_root: str, spec_root: Optional[str] = None) -> list[SpecError]:
    errors: list[SpecError] = []
    extensions = as_list(instance.get("extensions"))
    for ext in dict_items(extensions):
        ext_id = ext.get("extension_id")

        # required_schema_sections must be present and non-empty
        sections = ext.get("required_schema_sections")
        if not sections:
            errors.append(make_error("E520", f"Extension '{ext_id}' missing required_schema_sections"))
        elif isinstance(sections, list):
            for j, section in enumerate(sections):
                if isinstance(section, str) and not _STEP_PATTERN.match(section):
                    errors.append(
                        make_error("E320", f"Extension '{ext_id}' required_schema_sections[{j}] "
                        f"'{section}' is not a valid identifier (must start with alphanumeric, only alphanumeric/underscore/hyphen allowed)")
                    )

        # Justification must be non-empty
        justification = ext.get("justification")
        if not justification or (isinstance(justification, str) and not justification.strip()):
            errors.append(
                make_error("E320", f"Extension '{ext_id}' missing or empty justification")
            )


    return errors
