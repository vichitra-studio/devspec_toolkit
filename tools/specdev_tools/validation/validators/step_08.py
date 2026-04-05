from __future__ import annotations

import re
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids
from ...validation.linter_utils import check_no_duplicates

FIXTURE_ID_PATTERN = re.compile(r"^fix-[a-z0-9]+(?:-[a-z0-9]+)*$")
TARGET_ID_PATTERN = re.compile(r"^(fr|api|nfr|inv)-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_08(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    errors: list[SpecError] = []
    check_no_duplicates(instance.get("fixtures", []), "fixture_id", "fixture_id", errors)
    for i, fixture in enumerate(instance.get("fixtures", [])):
        fixture_id = fixture.get("fixture_id")
        if isinstance(fixture_id, str) and not FIXTURE_ID_PATTERN.match(fixture_id):
            errors.append(make_error("E530", f"Fixture at index {i} has fixture_id '{fixture_id}' that does not follow 'fix-<kebab>' convention"))
        targets = fixture.get("targets")
        if not targets:
            errors.append(make_error("E520", f"Fixture '{fixture_id}' missing targets"))
        elif isinstance(targets, list):
            for t in targets:
                if isinstance(t, dict):
                    tid = t.get("id", "")
                    if tid and not TARGET_ID_PATTERN.match(tid):
                        errors.append(make_error("E530", f"Fixture '{fixture_id}' has target '{tid}' that does not match (fr|api|nfr|inv)-* pattern"))
                elif isinstance(t, str) and not TARGET_ID_PATTERN.match(t):
                    errors.append(make_error("E530", f"Fixture '{fixture_id}' has target '{t}' that does not match (fr|api|nfr|inv)-* pattern"))

    # Cross-step target ID validation against upstream artifacts
    fr_ids = load_upstream_ids(toolkit_root, "04", "functional_requirements", "fr_id", spec_root=spec_root)
    api_ids = load_upstream_ids(toolkit_root, "05", "apis", "api_id", spec_root=spec_root)
    inv_ids = load_upstream_ids(toolkit_root, "06", "rules", "inv_id", spec_root=spec_root)
    nfr_ids = load_upstream_ids(toolkit_root, "07", "nfrs", "nfr_id", spec_root=spec_root)

    upstream_map: dict[str, tuple[set[str] | None, str, str]] = {
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
                make_error("W590", f"CROSS_STEP_UPSTREAM_MISSING {filename} not found; "
                f"skipping {type_label} reference validation")
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
            for prefix, (id_set, filename, _) in upstream_map.items():
                if target_id.startswith(prefix):
                    if id_set is not None and target_id not in id_set:
                        errors.append(
                            make_error("E590", f"CROSS_STEP_ID_NOT_FOUND fixture "
                            f"'{fixture_id}' target '{target_id}' not found "
                            f"in {filename}")
                        )
                    break

    return errors
