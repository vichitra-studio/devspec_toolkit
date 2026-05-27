"""T-step-registry-coverage — every step in step_order.json is accounted for in the registry.

Covers W6-T3 invariant (ported from R001 / E620 which ran host-side).

After W3, the registry generator enforces coverage as an internal contract.
This test moves the check to the toolkit test suite where it belongs:
toolkit-generated artifacts must satisfy toolkit-defined invariants.

A step is "accounted for" if it appears in any of:
  1. ``registry`` — as a basename whose step field matches, OR
  2. ``steps_without_entry_arrays`` — explicit opt-out (no id-bearing arrays), OR
  3. ``steps_with_deferred_registration`` — deferred (e.g. per-milestone files).

Reads directly from ``devspec_toolkit/tools/entry_key_registry.json``.

Toolkit root from this file: Path(__file__).parents[4]
  → devspec_toolkit/tests/unit/toolkit_invariants/test_step_registry_coverage.py
  → parents[0] = devspec_toolkit/tests/unit/toolkit_invariants/
  → parents[1] = devspec_toolkit/tests/unit/
  → parents[2] = devspec_toolkit/tests/
  → parents[3] = devspec_toolkit/
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Toolkit root resolution
# ---------------------------------------------------------------------------

_TOOLKIT_ROOT = Path(__file__).parents[3]
_STEP_ORDER_PATH = _TOOLKIT_ROOT / "tools" / "step_order.json"
_REGISTRY_PATH = _TOOLKIT_ROOT / "tools" / "entry_key_registry.json"


def _load_steps() -> list[str]:
    data = json.loads(_STEP_ORDER_PATH.read_text(encoding="utf-8"))
    return data.get("steps", [])


def _load_registry_doc() -> dict:
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))


def _opted_out_steps(doc: dict) -> set[str]:
    """Return steps in steps_without_entry_arrays (supports dict and list formats)."""
    opted: set[str] = set()
    for key in ("steps_without_entry_arrays", "steps_with_deferred_registration"):
        entry = doc.get(key, [])
        if isinstance(entry, dict):
            opted.update(entry.keys())
        elif isinstance(entry, list):
            for item in entry:
                if isinstance(item, dict) and "step" in item:
                    opted.add(item["step"])
    return opted


def _registered_steps(doc: dict) -> set[str]:
    """Return step values from registry entries (non-special)."""
    registered: set[str] = set()
    for _bn, entry in doc.get("registry", {}).items():
        if not entry.get("_special", False):
            step = entry.get("step")
            if step:
                registered.add(step)
    return registered


# ---------------------------------------------------------------------------
# Precondition
# ---------------------------------------------------------------------------


def test_registry_file_exists() -> None:
    """entry_key_registry.json must exist at tools/entry_key_registry.json."""
    assert _REGISTRY_PATH.is_file(), (
        f"entry_key_registry.json not found at {_REGISTRY_PATH}. "
        "Run: specdev registry-generate --repo-root <toolkit-path>"
    )


# ---------------------------------------------------------------------------
# T-step-registry-coverage
# ---------------------------------------------------------------------------


class TestStepRegistryCoverage:
    """Every step in step_order.json is registered, opted-out, or deferred."""

    @pytest.fixture(scope="class")
    def registry_doc(self) -> dict:
        return _load_registry_doc()

    @pytest.fixture(scope="class")
    def accounted_steps(self, registry_doc: dict) -> set[str]:
        return _registered_steps(registry_doc) | _opted_out_steps(registry_doc)

    @pytest.mark.parametrize("step", _load_steps(), ids=lambda s: f"step_{s}")
    def test_step_is_accounted_for(self, step: str, accounted_steps: set[str]) -> None:
        """Step must be registered, in steps_without_entry_arrays, or in steps_with_deferred_registration."""
        assert step in accounted_steps, (
            f"Step '{step}' is not accounted for in entry_key_registry.json. "
            "It must appear in one of: "
            "(1) registry (as a basename starting with '{step}_'), "
            "(2) steps_without_entry_arrays, or "
            "(3) steps_with_deferred_registration. "
            "Re-run: specdev registry-generate --repo-root <toolkit-path>"
        )

    def test_no_registered_step_missing_from_step_order(self, registry_doc: dict) -> None:
        """Every step referenced in the registry must exist in step_order.json."""
        step_order = set(_load_steps())
        all_step_refs = _registered_steps(registry_doc) | _opted_out_steps(registry_doc)
        phantom = all_step_refs - step_order
        assert not phantom, (
            f"Registry references step(s) not in step_order.json: {sorted(phantom)}. "
            "Remove stale entries or add the step to step_order.json."
        )

    def test_registry_format_version_present(self, registry_doc: dict) -> None:
        """Registry document must have _format_version field."""
        assert "_format_version" in registry_doc, (
            "entry_key_registry.json is missing '_format_version'. "
            "The file may be corrupted or hand-edited."
        )

    def test_registry_sentinels_present(self, registry_doc: dict) -> None:
        """Registry document must declare _sentinels."""
        assert "_sentinels" in registry_doc, (
            "entry_key_registry.json is missing '_sentinels'. "
            "Re-generate the registry with specdev registry-generate."
        )
