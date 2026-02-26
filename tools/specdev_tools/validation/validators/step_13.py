from __future__ import annotations

import re
from typing import Any


# Valid step schema patterns: 00-16 + optional letter suffix
_STEP_PATTERN = re.compile(r"^[0-9]{2}[a-z]?_")


def validate_step_13(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, ext in enumerate(instance.get("extensions", [])):
        ext_id = ext.get("extension_id")

        # Duplicate ID check
        if ext_id in seen_ids:
            errors.append(f"Duplicate extension_id '{ext_id}' at index {i}")
        seen_ids.add(ext_id)

        # required_schema_sections must be present and non-empty
        sections = ext.get("required_schema_sections")
        if not sections:
            errors.append(f"Extension '{ext_id}' missing required_schema_sections")
        elif isinstance(sections, list):
            for j, section in enumerate(sections):
                if isinstance(section, str) and not _STEP_PATTERN.match(section):
                    errors.append(
                        f"E320 Extension '{ext_id}' required_schema_sections[{j}] "
                        f"'{section}' does not match a valid step schema pattern (NN_*)"
                    )

        # Justification must be non-empty
        justification = ext.get("justification")
        if not justification or (isinstance(justification, str) and not justification.strip()):
            errors.append(
                f"E320 Extension '{ext_id}' missing or empty justification"
            )

        # Warn if no verification rules or test commands hint
        schema_guidelines = ext.get("schema_design_guidelines", "")
        has_verification_hint = any(
            kw in (schema_guidelines or "").lower()
            for kw in ("verif", "test", "check", "validat", "assert")
        )
        if not has_verification_hint and not ext.get("verification_rules"):
            errors.append(
                f"E320 Extension '{ext_id}' has no verification_rules and "
                f"schema_design_guidelines lacks verification keywords"
            )

    return errors
