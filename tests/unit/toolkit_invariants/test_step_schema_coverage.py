"""T-step-schema-coverage — every step in step_order.json has exactly one schema file.

Covers W6-T3 invariant: no step is schema-orphaned.

Steps that don't have dedicated schemas are explicitly modelled in the test
via the STEPS_WITHOUT_SCHEMAS allowlist below. Currently that set is empty —
all active steps (00 through 16, 16a/16b/16c) have schemas. If a new step
is added without a schema, add it to the allowlist with a rationale comment.

Toolkit root from this file: Path(__file__).parents[4]
  → devspec_toolkit/tests/unit/toolkit_invariants/test_step_schema_coverage.py
  → parents[0] = devspec_toolkit/tests/unit/toolkit_invariants/
  → parents[1] = devspec_toolkit/tests/unit/
  → parents[2] = devspec_toolkit/tests/
  → parents[3] = devspec_toolkit/
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Toolkit root resolution
# ---------------------------------------------------------------------------

_TOOLKIT_ROOT = Path(__file__).parents[3]
_SCHEMA_DIR = _TOOLKIT_ROOT / "schema"
_STEP_ORDER_PATH = _TOOLKIT_ROOT / "tools" / "step_order.json"

# Steps known to have no dedicated schema file (documented exceptions only).
# 16a/16b/16c are per-milestone artifacts covered by 16_anchor.schema.json
# and 16_impl_context.schema.json rather than separate per-substep files.
STEPS_WITHOUT_SCHEMAS: dict[str, str] = {
    "16a": "Per-milestone anchor; covered by 16_anchor.schema.json",
    "16b": "Per-milestone implementation; covered by 16_impl_context.schema.json",
    "16c": "Per-milestone review; no dedicated schema (review is narrative output)",
}

# Steps that intentionally have MORE than one schema file (documented exceptions only).
# Step 16 covers both the Trinity anchor format (16_anchor.schema.json) and the
# implementation context format (16_impl_context.schema.json) — two artifact types
# are produced within the single step 16 Trinity loop.
STEPS_WITH_MULTIPLE_SCHEMAS: dict[str, str] = {
    "16": "Two artifact types: 16_anchor.schema.json and 16_impl_context.schema.json",
}


def _load_steps() -> list[str]:
    data = json.loads(_STEP_ORDER_PATH.read_text(encoding="utf-8"))
    return data.get("steps", [])


def _schema_files_for_step(step: str) -> list[Path]:
    """Return schema files whose name starts with the step prefix (e.g. '04_')."""
    prefix = f"{step}_"
    return sorted(
        p for p in _SCHEMA_DIR.glob("*.schema.json")
        if p.name.startswith(prefix)
    )


# ---------------------------------------------------------------------------
# T-step-schema-coverage
# ---------------------------------------------------------------------------


class TestStepSchemaCoverage:
    """For every step in step_order.json, there is exactly one matching schema file."""

    @pytest.mark.parametrize(
        "step",
        [
            s for s in _load_steps()
            if s not in STEPS_WITHOUT_SCHEMAS and s not in STEPS_WITH_MULTIPLE_SCHEMAS
        ],
        ids=lambda s: f"step_{s}",
    )
    def test_step_has_exactly_one_schema(self, step: str) -> None:
        """Step has exactly one schema file matching schema/<step>_*.schema.json."""
        matches = _schema_files_for_step(step)
        assert len(matches) == 1, (
            f"Step '{step}': expected exactly 1 schema file matching "
            f"schema/{step}_*.schema.json, found {len(matches)}: "
            f"{[p.name for p in matches]}. "
            "If this step intentionally has multiple schemas, add it to STEPS_WITH_MULTIPLE_SCHEMAS. "
            "If this step intentionally lacks a schema, add it to STEPS_WITHOUT_SCHEMAS."
        )

    @pytest.mark.parametrize(
        "step",
        [s for s in _load_steps() if s in STEPS_WITH_MULTIPLE_SCHEMAS],
        ids=lambda s: f"step_{s}_multi",
    )
    def test_multi_schema_step_has_at_least_two_schemas(self, step: str) -> None:
        """Steps in STEPS_WITH_MULTIPLE_SCHEMAS must have >= 2 schema files."""
        matches = _schema_files_for_step(step)
        assert len(matches) >= 2, (
            f"Step '{step}' is in STEPS_WITH_MULTIPLE_SCHEMAS but only has "
            f"{len(matches)} schema(s): {[p.name for p in matches]}. "
            f"Remove '{step}' from STEPS_WITH_MULTIPLE_SCHEMAS."
        )

    @pytest.mark.parametrize(
        "step",
        [s for s in _load_steps() if s in STEPS_WITHOUT_SCHEMAS],
        ids=lambda s: f"step_{s}_exempt",
    )
    def test_exempt_step_has_no_dedicated_schema(self, step: str) -> None:
        """Steps in STEPS_WITHOUT_SCHEMAS have no dedicated schema (documents the exception)."""
        dedicated = _schema_files_for_step(step)
        # This test documents the known exception. If the step later gains a
        # dedicated schema, the test will fail — prompting removal from the
        # allowlist and a move to the main parametrize above.
        assert len(dedicated) == 0, (
            f"Exempt step '{step}' now has a schema file(s): "
            f"{[p.name for p in dedicated]}. "
            f"Remove '{step}' from STEPS_WITHOUT_SCHEMAS and let it be "
            "covered by the main test."
        )

    def test_step_order_file_exists(self) -> None:
        """step_order.json must exist at tools/step_order.json."""
        assert _STEP_ORDER_PATH.is_file(), (
            f"step_order.json not found at {_STEP_ORDER_PATH}. "
            "The toolkit root may be incorrectly resolved."
        )

    def test_step_order_has_steps(self) -> None:
        """step_order.json must declare at least one step."""
        steps = _load_steps()
        assert steps, "step_order.json has an empty 'steps' array."
