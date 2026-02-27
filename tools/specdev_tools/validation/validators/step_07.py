from __future__ import annotations

import json
import os
from typing import Any


KNOWN_STAGES = {"dev", "ci", "staging", "prod"}


def validate_step_07(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    # Load canonical stage values if available
    canon_stages = _load_canonical_stages(toolkit_root)

    for i, nfr in enumerate(instance.get("nfrs", [])):
        nfr_id = nfr.get("nfr_id")

        # Duplicate ID check
        if nfr_id in seen_ids:
            errors.append(f"Duplicate nfr_id '{nfr_id}' at index {i}")
        seen_ids.add(nfr_id)

        # Stage validation against canonical values
        stage = nfr.get("stage")
        valid_stages = canon_stages if canon_stages else KNOWN_STAGES
        if stage and stage not in valid_stages:
            errors.append(f"NFR '{nfr_id}' has invalid stage '{stage}'")

        # FR traceability: fr_refs should reference valid FR IDs if step 04 exists
        fr_refs = nfr.get("fr_refs", [])
        if isinstance(fr_refs, list):
            for ref in fr_refs:
                if isinstance(ref, str) and not ref.startswith("fr-"):
                    errors.append(
                        f"NFR '{nfr_id}' has fr_ref '{ref}' that does not follow 'fr-*' convention"
                    )

    # Cross-step FR traceability validation
    fr_ids = _load_fr_ids(toolkit_root)
    if fr_ids is not None:
        for nfr in instance.get("nfrs", []):
            nfr_id = nfr.get("nfr_id")
            for ref in nfr.get("fr_refs", []):
                if isinstance(ref, str) and ref not in fr_ids:
                    errors.append(
                        f"NFR '{nfr_id}' references unknown FR '{ref}' (not in 04_fr_list.json)"
                    )

    return errors


def _load_canonical_stages(toolkit_root: str) -> set[str] | None:
    """Load canonical stage values from the canon directory."""
    manifest_path = os.path.join(toolkit_root, "canon", "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        stages = manifest.get("stages", {})
        if isinstance(stages, dict):
            values = stages.get("values", [])
            if isinstance(values, list) and values:
                return {v.get("id") for v in values if isinstance(v, dict) and v.get("id")}
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        pass
    return None


def _load_fr_ids(toolkit_root: str) -> set[str] | None:
    """Load FR IDs from step 04 if available."""
    spec_dir = os.path.join(toolkit_root, "spec")
    for fn in os.listdir(spec_dir) if os.path.isdir(spec_dir) else []:
        if fn.startswith("04_") and fn.endswith(".json"):
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    fr.get("fr_id")
                    for fr in data.get("functional_requirements", [])
                    if isinstance(fr, dict) and fr.get("fr_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
