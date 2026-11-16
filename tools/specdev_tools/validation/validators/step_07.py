from __future__ import annotations

import os
import re
from typing import Any

from ...core.scope_helpers import str_in
from ...core.errors import make_error, SpecError
from ...validation.linter_utils import load_canonical_stages

KNOWN_STAGES = {"dev", "ci", "staging", "prod"}
NFR_ID_PATTERN = re.compile(r"^nfr-[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_step_07(instance: dict[str, Any], toolkit_root: str, spec_root: str | None = None) -> list[SpecError]:
    errors: list[SpecError] = []

    nfrs = instance.get("nfrs", [])
    if not isinstance(nfrs, list):
        return errors

    # Load canonical stage values if available
    canon_stages = load_canonical_stages(os.path.join(toolkit_root, "canon"))

    for i, nfr in enumerate(nfrs):
        if not isinstance(nfr, dict):
            continue
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
        if stage and not str_in(stage, valid_stages):
            errors.append(make_error("E530", f"NFR '{nfr_id}' has invalid stage '{stage}'"))

    return errors
