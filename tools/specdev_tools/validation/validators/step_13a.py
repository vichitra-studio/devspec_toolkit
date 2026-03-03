from __future__ import annotations

import json
import os
import re
from typing import Any, Optional, Set

ELEMENT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_13a(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    for item in instance.get("missing_elements", []):
        element_id = item.get("element_id")
        if isinstance(element_id, str) and not ELEMENT_ID_PATTERN.match(element_id):
            errors.append(f"Element has element_id '{element_id}' that does not follow kebab-case convention")
        score = item.get("impact_score")
        if isinstance(score, (int, float)) and not (0 <= score <= 100):
            errors.append(f"Invalid impact_score for '{element_id}': {score}")
    summary = instance.get("summary", {})
    if isinstance(summary, dict):
        completeness = summary.get("completeness")
        if isinstance(completeness, (int, float)) and not (0 <= completeness <= 100):
            errors.append(f"Invalid summary.completeness: {completeness}")
        if isinstance(completeness, (int, float)) and completeness < 100:
            missing = instance.get("missing_elements", [])
            if not missing:
                errors.append(f"summary.completeness is {completeness} (< 100) but missing_elements is empty")

    # Cross-step ID validation against upstream FR and API artifacts
    fr_ids = _load_fr_ids(toolkit_root)
    api_ids = _load_api_ids(toolkit_root)

    # Map: prefix -> (loaded set or None, upstream filename, type label)
    upstream_map: dict[str, tuple[Optional[Set[str]], str, str]] = {
        "fr-": (fr_ids, "04_fr_list.json", "FR"),
        "api-": (api_ids, "05_interface_contracts.json", "API"),
    }

    # Emit W590 once per missing upstream file
    warned_missing: set[str] = set()
    for prefix, (id_set, filename, type_label) in upstream_map.items():
        if id_set is None and filename not in warned_missing:
            errors.append(
                f"W590 CROSS_STEP_UPSTREAM_MISSING {filename} not found; "
                f"skipping {type_label} reference validation"
            )
            warned_missing.add(filename)

    # Validate each missing_element for spec-ref IDs
    for item in instance.get("missing_elements", []):
        element_id = item.get("element_id", "<unknown>")
        refs = _collect_spec_refs(item)
        for ref in refs:
            if not isinstance(ref, str):
                continue
            for prefix, (id_set, filename, type_label) in upstream_map.items():
                if ref.startswith(prefix):
                    if id_set is not None and ref not in id_set:
                        errors.append(
                            f"E590 CROSS_STEP_ID_NOT_FOUND element "
                            f"'{element_id}' references unknown {type_label} "
                            f"'{ref}' (not in {filename})"
                        )
                    break

    return errors


def _collect_spec_refs(item: dict[str, Any]) -> list[str]:
    """Extract all potential FR/API ID references from a missing_element."""
    refs: list[str] = []

    # Check element_id itself if it looks like a spec ref
    element_id = item.get("element_id")
    if isinstance(element_id, str) and (
        element_id.startswith("fr-") or element_id.startswith("api-")
    ):
        refs.append(element_id)

    # Scan all string values for IDs starting with fr- or api-
    for key, val in item.items():
        if key == "element_id":
            continue  # already handled above
        if isinstance(val, str) and (
            val.startswith("fr-") or val.startswith("api-")
        ):
            if val not in refs:
                refs.append(val)
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, str) and (
                    v.startswith("fr-") or v.startswith("api-")
                ):
                    if v not in refs:
                        refs.append(v)

    return refs


def _load_fr_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load FR IDs from step 04 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None

    for fn in os.listdir(spec_dir):
        if fn.startswith("04_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    req.get("fr_id")
                    for req in data.get("functional_requirements", [])
                    if isinstance(req, dict) and req.get("fr_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None


def _load_api_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load API IDs from step 05 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None

    for fn in os.listdir(spec_dir):
        if fn.startswith("05_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    api.get("api_id")
                    for api in data.get("apis", [])
                    if isinstance(api, dict) and api.get("api_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
