from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..core.errors import SpecError, make_error
from ..core.registry import derive_allowed_upstream
from ._extraction_intent_parser import parse_extraction_intent


# Pattern to match step number from prompt filenames: prompt_05_interface_contracts.md -> "05"
_PROMPT_STEP_RE = re.compile(r"prompt_(\d{2}[a-z]?)_")

# Vague-intent trigger words — aligned with dag_lint._VAGUE_MARKERS
_VAGUE_WORDS_RE = re.compile(
    r"\b(?:relevant|as needed|as appropriate|etc\.?|various|TBD|TODO)\b",
    re.IGNORECASE,
)


def check_extraction_intent(
    repo_root: str,
    prompts_dir: str | None = None,
) -> list[SpecError]:
    """Validate extraction intent sections against step_order.json.

    For each prompt file that contains a ``### Extraction Intent`` section:
    1. Parse declared upstream artifact references from the section.
    2. Cross-reference against the derived allowed upstream steps (computed at runtime via derive_allowed_upstream).
    3. Report missing intent entries, invalid references, and vague descriptions.

    Error codes:
        E591 — required extraction intent field missing or empty
        E597 — an allowed_upstream_dep has no corresponding extraction intent entry
        W597 — intent text is vague (<10 words or contains "relevant"/"as needed")
        E598 — intent references an artifact not in step_order.json steps list

    Prompts without a ``### Extraction Intent`` section are skipped gracefully.
    """
    errors: list[SpecError] = []
    prompts_path = prompts_dir or os.path.join(repo_root, "prompts")
    step_order_path = os.path.join(repo_root, "tools", "step_order.json")

    if not os.path.isfile(step_order_path):
        return errors

    # Load step_order.json
    try:
        with open(step_order_path, "r", encoding="utf-8") as f:
            step_order = json.load(f)
    except (OSError, json.JSONDecodeError):
        return errors

    steps_list: list[str] = step_order.get("steps", [])
    valid_steps: set[str] = set(steps_list)
    allowed_deps: dict[str, list[str]] = {
        s: derive_allowed_upstream(s, steps_list) for s in steps_list
    }

    # Scan prompt files
    if not os.path.isdir(prompts_path):
        return errors

    for fn in sorted(os.listdir(prompts_path)):
        if not fn.startswith("prompt_") or not fn.endswith(".md"):
            continue

        step_match = _PROMPT_STEP_RE.match(fn)
        if not step_match:
            continue
        step_id = step_match.group(1)

        prompt_path = os.path.join(prompts_path, fn)
        parsed = parse_extraction_intent(Path(prompt_path))
        if parsed is None:
            continue  # Graceful skip — no section or unreadable

        intent_entries = parsed.step_entries
        has_seed_entries = parsed.has_seed_entries

        # E591: section header found but no entries parsed
        # Suppress when the section contains only seed doc entries — the
        # section IS populated, just not with spec step dependencies.
        if not intent_entries and not has_seed_entries:
            errors.append(make_error(
                "E591",
                f"EXTRACTION_INTENT_EMPTY prompt_{step_id} "
                f"has ### Extraction Intent section but no entries were parsed",
            ))
            continue

        # E597: each allowed_upstream_dep should have an intent entry
        step_deps = allowed_deps.get(step_id, [])
        for dep in step_deps:
            if dep not in intent_entries:
                errors.append(make_error(
                    "E597",
                    f"EXTRACTION_INTENT_UPSTREAM_GAP prompt_{step_id} "
                    f"has no extraction intent for allowed upstream "
                    f"dependency '{dep}'",
                ))

        # Validate each intent entry
        for ref_step, intent_text in intent_entries.items():
            # E598: intent references a step not in the steps list
            if ref_step not in valid_steps:
                errors.append(make_error(
                    "E598",
                    f"EXTRACTION_INTENT_INVALID_REF prompt_{step_id} "
                    f"extraction intent references unknown step '{ref_step}'",
                ))

            # W597: vague intent — too short or contains weasel words
            word_count = len(intent_text.split())
            if word_count < 10 or _VAGUE_WORDS_RE.search(intent_text):
                errors.append(make_error(
                    "W597",
                    f"EXTRACTION_INTENT_VAGUE prompt_{step_id} "
                    f"intent for '{ref_step}' is vague ({word_count} words)",
                ))

    return errors
