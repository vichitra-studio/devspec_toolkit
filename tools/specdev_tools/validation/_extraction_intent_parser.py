"""Shared extraction intent parser for prompt files.

Consolidates the extraction intent parsing logic previously duplicated
in ``dag_lint.py`` and ``extraction_intent_check.py`` into a single
module consumed by both validators.

Exports:
    INTENT_ENTRY_RE — regex matching extraction intent bullet entries
    ARTIFACT_STEP_RE — regex extracting step numbers from artifact filenames
    SEED_ENTRY_RE — regex matching seed document references
    ParsedIntent — dataclass holding parsed extraction intent data
    parse_extraction_intent — function to parse a prompt file's intent section
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# Matches extraction intent bullet entries like:
#   - **00_charter.json**: Project scope boundaries ...
#   - **spec/00_charter.json**: Project scope boundaries ... (spec-prefixed form)
#   - **docs/seed/seed_overview.md**: Scope boundaries ...
#   - **03_glossary.json** (optional): Domain terms ...
#   - **spec/16_impl_context.json**: Trinity Anchor scope ...
# The optional prefix group tolerates `docs/seed/` and `spec/` — the two
# in-prompt conventions used across the toolkit. A bare filename is also
# accepted.
INTENT_ENTRY_RE = re.compile(
    r"^\s*-\s+\*\*(?:docs/seed/|spec/)?(\d{2}[a-z]?_[a-z0-9_]+\.\w+|seed_\w+\.md)\*\*"
    r"(?:\s*\([^)]*\))?\s*:\s*(.+)",
    re.IGNORECASE,
)

# Matches bullet entries that reference per-milestone 16a plan files living in
# spec/impl_context/. The filename varies per milestone (and is often a
# template placeholder like `{step_id}.json` in the prompt source), so we do
# not extract a step number from it — these entries map to step 16a directly.
# Example:
#   - **spec/impl_context/{step_id}.json**: milestone context 16a authored ...
#   - **spec/impl_context/ms_auth_plan.json**: ...
IMPL_CONTEXT_ENTRY_RE = re.compile(
    r"^\s*-\s+\*\*spec/impl_context/[^*]+\.json\*\*"
    r"(?:\s*\([^)]*\))?\s*:\s*(.+)",
    re.IGNORECASE,
)

# Extracts the step number from an artifact filename like "04_fr_list.json" -> "04"
ARTIFACT_STEP_RE = re.compile(r"^(\d{2}[a-z]?)_")

# Matches seed document references (not step dependencies):
#   - **docs/seed/seed_overview.md**: ...
#   - **seed_tech_stack.md**: ...
SEED_ENTRY_RE = re.compile(
    r"^\s*-\s+\*\*(?:docs/(?:seed/)?)?seed_\w+\.md\*\*",
    re.IGNORECASE,
)


@dataclass
class ParsedIntent:
    """Parsed extraction intent section from a prompt file."""

    prompt_path: Path
    step_entries: dict[str, str] = field(default_factory=dict)
    referenced_steps: set[str] = field(default_factory=set)
    has_seed_entries: bool = False


def parse_extraction_intent(prompt_path: Path) -> ParsedIntent | None:
    """Parse the ``### Extraction Intent`` section from a prompt file.

    Uses dag_lint's section boundary logic: stops at ``## `` or a subsequent
    ``### `` header (more correct than stopping at any ``#``).

    Returns ``None`` if the file cannot be read or the section is not found.
    """
    try:
        text = prompt_path.read_text(encoding="utf-8")
    except OSError:
        return None

    # Find the ### Extraction Intent header
    lines = text.splitlines()
    intent_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("### Extraction Intent"):
            intent_start = i + 1
            break

    if intent_start is None:
        return None

    # Collect lines until the next ## or ### header or end of file
    intent_lines: list[str] = []
    for i in range(intent_start, len(lines)):
        line = lines[i]
        stripped = line.strip()
        # Stop at the next section header (## or ###)
        if stripped.startswith("## ") or (
            stripped.startswith("### ") and i > intent_start
        ):
            break
        intent_lines.append(line)

    # Parse individual intent entries
    step_entries: dict[str, str] = {}
    referenced_steps: set[str] = set()
    has_seed_entries: bool = False

    for line in intent_lines:
        # Check for seed document references first
        if SEED_ENTRY_RE.match(line):
            has_seed_entries = True
            continue

        # Per-milestone plan files in spec/impl_context/ are the shared Trinity
        # artifact — 16a authors it, 16b writes execution evidence into it,
        # 16c writes review findings into it. A single reference therefore
        # covers both upstream contributions (16a and 16b); 16c is not
        # registered from this path because 16c is only a writer, never
        # consumed by downstream Trinity steps.
        impl_match = IMPL_CONTEXT_ENTRY_RE.match(line)
        if impl_match:
            description = impl_match.group(1).strip()
            for covered_step in ("16a", "16b"):
                step_entries[covered_step] = description
                referenced_steps.add(covered_step)
            continue

        match = INTENT_ENTRY_RE.match(line)
        if not match:
            continue
        artifact_name = match.group(1)
        description = match.group(2).strip()

        # Check if this is a seed doc (matched by INTENT_ENTRY_RE but not SEED_ENTRY_RE)
        if artifact_name.startswith("seed_"):
            has_seed_entries = True
            continue

        # Extract step number from artifact filename (e.g., "04_fr_list.json" -> "04")
        step_match = ARTIFACT_STEP_RE.match(artifact_name)
        if step_match:
            step_number = step_match.group(1)
            step_entries[step_number] = description
            referenced_steps.add(step_number)

    return ParsedIntent(
        prompt_path=prompt_path,
        step_entries=step_entries,
        referenced_steps=referenced_steps,
        has_seed_entries=has_seed_entries,
    )
