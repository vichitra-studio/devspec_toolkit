from __future__ import annotations

import os
import re
from typing import Any

from ...core.errors import make_error, SpecError
from ...core.loaders import load_upstream_ids
from ...validation.linter_utils import check_no_duplicates, load_canonical_stages

KNOWN_STAGES = {"dev", "ci", "staging", "prod"}
NFR_ID_PATTERN = re.compile(r"^nfr-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_07(instance: dict[str, Any], toolkit_root: str) -> list[SpecError]:
    errors: list[SpecError] = []

    check_no_duplicates(instance.get("nfrs", []), "nfr_id", "nfr_id", errors)

    # Load canonical stage values if available
    canon_stages = load_canonical_stages(os.path.join(toolkit_root, "canon"))

    for i, nfr in enumerate(instance.get("nfrs", [])):
        nfr_id = nfr.get("nfr_id")

        # NFR ID format check
        if isinstance(nfr_id, str) and not NFR_ID_PATTERN.match(nfr_id):
            errors.append(make_error("E530", f"NFR at index {i} has nfr_id '{nfr_id}' that does not follow 'nfr-<kebab>' convention"))

        # Target digit validation (schema requires pattern ^.*\d+.*$)
        target = nfr.get("target")
        if target is not None and isinstance(target, str):
            if not re.search(r"\d", target):
                errors.append(make_error("E520", f"NFR '{nfr_id}' target string contains no digit: '{target}'"))

        # Stage validation against canonical values
        stage = nfr.get("stage")
        valid_stages = canon_stages if canon_stages else KNOWN_STAGES
        if stage and stage not in valid_stages:
            errors.append(make_error("E530", f"NFR '{nfr_id}' has invalid stage '{stage}'"))

        # FR traceability: fr_refs should reference valid FR IDs if step 04 exists
        fr_refs = nfr.get("fr_refs", [])
        if isinstance(fr_refs, list):
            for ref in fr_refs:
                if isinstance(ref, str) and not ref.startswith("fr-"):
                    errors.append(
                        make_error("E590", f"NFR '{nfr_id}' has fr_ref '{ref}' that does not follow 'fr-*' convention")
                    )

    # Cross-step FR traceability validation
    fr_ids = load_upstream_ids(toolkit_root, "04", "functional_requirements", "fr_id")
    if fr_ids is not None:
        for nfr in instance.get("nfrs", []):
            nfr_id = nfr.get("nfr_id")
            for ref in nfr.get("fr_refs", []):
                if isinstance(ref, str) and ref not in fr_ids:
                    errors.append(
                        make_error("E590", f"NFR '{nfr_id}' references unknown FR '{ref}' (not in 04_fr_list.json)")
                    )

    return errors
