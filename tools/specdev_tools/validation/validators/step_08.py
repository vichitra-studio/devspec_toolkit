from __future__ import annotations

import json
import os
import re
from typing import Any, Optional, Set

FIXTURE_ID_PATTERN = re.compile(r"^fix-[a-z0-9]+(?:-[a-z0-9]+)*$")
TARGET_ID_PATTERN = re.compile(r"^(fr|api|nfr|inv)-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_08(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, fixture in enumerate(instance.get("fixtures", [])):
        fixture_id = fixture.get("fixture_id")
        if isinstance(fixture_id, str) and not FIXTURE_ID_PATTERN.match(fixture_id):
            errors.append(f"Fixture at index {i} has fixture_id '{fixture_id}' that does not follow 'fix-<kebab>' convention")
        if fixture_id in seen_ids:
            errors.append(f"Duplicate fixture_id '{fixture_id}' at index {i}")
        seen_ids.add(fixture_id)
        targets = fixture.get("targets")
        if not targets:
            errors.append(f"Fixture '{fixture_id}' missing targets")
        elif isinstance(targets, list):
            for t in targets:
                if isinstance(t, dict):
                    tid = t.get("id", "")
                    if tid and not TARGET_ID_PATTERN.match(tid):
                        errors.append(f"Fixture '{fixture_id}' has target '{tid}' that does not match (fr|api|nfr|inv)-* pattern")
                elif isinstance(t, str) and not TARGET_ID_PATTERN.match(t):
                    errors.append(f"Fixture '{fixture_id}' has target '{t}' that does not match (fr|api|nfr|inv)-* pattern")

    # Cross-step target ID validation against upstream artifacts
    fr_ids = _load_fr_ids(toolkit_root)
    api_ids = _load_api_ids(toolkit_root)
    inv_ids = _load_inv_ids(toolkit_root)
    nfr_ids = _load_nfr_ids(toolkit_root)

    # Map: prefix -> (loaded set or None, upstream filename, type label)
    upstream_map: dict[str, tuple[Optional[Set[str]], str, str]] = {
        "fr-": (fr_ids, "04_fr_list.json", "FR"),
        "api-": (api_ids, "05_interface_contracts.json", "API"),
        "inv-": (inv_ids, "06_invariants.json", "INV"),
        "nfr-": (nfr_ids, "07_nfrs.json", "NFR"),
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

    # Validate each fixture target against the upstream ID set
    for fixture in instance.get("fixtures", []):
        fixture_id = fixture.get("fixture_id", "<unknown>")
        targets = fixture.get("targets")
        if not isinstance(targets, list):
            continue
        for t in targets:
            if isinstance(t, dict):
                target_id = t.get("id", "")
            elif isinstance(t, str):
                target_id = t
            else:
                continue
            if not target_id:
                continue
            for prefix, (id_set, filename, _type_label) in upstream_map.items():
                if target_id.startswith(prefix):
                    if id_set is not None and target_id not in id_set:
                        errors.append(
                            f"E590 CROSS_STEP_ID_NOT_FOUND fixture "
                            f"'{fixture_id}' target '{target_id}' not found "
                            f"in {filename}"
                        )
                    break

    return errors


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


def _load_inv_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load invariant IDs from step 06 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None

    for fn in os.listdir(spec_dir):
        if fn.startswith("06_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    rule.get("inv_id")
                    for rule in data.get("rules", [])
                    if isinstance(rule, dict) and rule.get("inv_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None


def _load_nfr_ids(toolkit_root: str) -> Optional[Set[str]]:
    """Load NFR IDs from step 07 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None

    for fn in os.listdir(spec_dir):
        if fn.startswith("07_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    nfr.get("nfr_id")
                    for nfr in data.get("nfrs", [])
                    if isinstance(nfr, dict) and nfr.get("nfr_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
