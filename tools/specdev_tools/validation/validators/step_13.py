from __future__ import annotations

import json
import os
import re
from typing import Any, Optional, Set

from ...core.errors import make_error, SpecError
from ...validation.linter_utils import check_no_duplicates


# Valid section name patterns: numeric step prefix (00_*, 13a_*) OR any
# domain-style identifier (tables, indexes, my-section, etc.).  The original
# strict pattern r"^[0-9]{2}[a-z]?_" incorrectly rejected non-numeric section
# names used by domain-specific schemas.
_STEP_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def validate_step_13(instance: dict[str, Any], toolkit_root: str, spec_root: Optional[str] = None) -> list[SpecError]:
    errors: list[SpecError] = []
    check_no_duplicates(instance.get("extensions", []), "extension_id", "extension_id", errors)
    for ext in instance.get("extensions", []):
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


    # --- Cross-step validation: governance_label_ref against 10_governance.json ---
    if instance.get("extensions"):
        governance_labels = _load_governance_labels(toolkit_root, spec_root=spec_root)
        if governance_labels is None:
            errors.append(
                make_error("W590", "CROSS_STEP_UPSTREAM_MISSING 10_governance.json not found; "
                "skipping governance reference validation")
            )
        else:
            for ext in instance.get("extensions", []):
                ext_id = ext.get("extension_id", "<unknown>")
                label_ref = ext.get("governance_label_ref")
                if isinstance(label_ref, dict):
                    label_id = label_ref.get("id")
                    if label_id and label_id not in governance_labels:
                        errors.append(
                            make_error("E590", f"CROSS_STEP_ID_NOT_FOUND extension '{ext_id}' "
                            f"references unknown governance label '{label_id}' "
                            f"(not in 10_governance.json)")
                        )

    return errors


def _load_governance_labels(toolkit_root: str, spec_root: Optional[str] = None) -> Optional[Set[str]]:
    """Load governance label IDs from step 10 if available.

    Scans the spec directory for a file starting with ``10_`` and ending
    with ``.json``.  Extracts canonical-ref IDs from the governance
    artifact's ``canonical_refs_used`` array (filtering for entries whose
    ``kind`` is ``governance_label``).

    Returns ``None`` when the upstream file cannot be found or parsed,
    signalling the caller to emit a W590 warning.
    """
    spec_dir = spec_root if spec_root is not None else os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None

    for fn in os.listdir(spec_dir):
        if fn.startswith("10_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                labels: Set[str] = set()

                # Extract governance_label canonical refs
                for ref in data.get("canonical_refs_used", []):
                    if isinstance(ref, dict) and ref.get("kind") == "governance_label":
                        ref_id = ref.get("id")
                        if ref_id:
                            labels.add(ref_id)

                return labels
            except (OSError, json.JSONDecodeError):
                pass
    return None
