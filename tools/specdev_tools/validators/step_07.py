from __future__ import annotations

from typing import Any


KNOWN_STAGES = {"dev", "ci", "staging", "prod"}


def validate_step_07(instance: dict[str, Any], toolkit_root: str) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, nfr in enumerate(instance.get("nfrs", [])):
        nfr_id = nfr.get("nfr_id")
        if nfr_id in seen_ids:
            errors.append(f"Duplicate nfr_id '{nfr_id}' at index {i}")
        seen_ids.add(nfr_id)
        stage = nfr.get("stage")
        if stage and stage not in KNOWN_STAGES:
            errors.append(f"NFR '{nfr_id}' has invalid stage '{stage}'")
    return errors
