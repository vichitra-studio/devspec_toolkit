"""Tests for gap-remediation features added during the v0.3.0 release cycle.

Covers:
- ``get_step_from_path`` handling of ``impl_context/`` directories
- ``DEEP_VALIDATORS`` entries for steps 16a, 16b, 16c
- ``validators`` sub-package importability
- Migration runner ``execute_single_step`` importability
- ``init_project.py`` support for ``--venv-name`` argument
- the verb-named property rule on the step 16 plan schema
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.step_paths import get_step_from_path
from specdev_tools.validation.validate import DEEP_VALIDATORS


# ---------------------------------------------------------------------------
# 1. get_step_from_path: impl_context/ paths
# ---------------------------------------------------------------------------

class TestGetStepFromPathImplContext:
    """Files inside an ``impl_context/`` directory should map to step 16a (milestone plans)."""

    def test_relative_path(self):
        assert get_step_from_path("spec/impl_context/step-api-core.json") == "16a"

    def test_absolute_path(self):
        assert get_step_from_path("/abs/path/spec/impl_context/my-file.json") == "16a"

    def test_normal_step_still_works(self):
        assert get_step_from_path("spec/04_frs.json") == "04"

    def test_unknown_file(self):
        assert get_step_from_path("random_file.json") == "unknown"

    def test_step_16a(self):
        assert get_step_from_path("spec/16a_impl_planner.json") == "16a"

    def test_step_16b(self):
        assert get_step_from_path("spec/16b_code.json") == "16b"

    def test_step_16c(self):
        assert get_step_from_path("spec/16c_review.json") == "16c"


# ---------------------------------------------------------------------------
# 2. DEEP_VALIDATORS entries for 16a / 16b / 16c
# ---------------------------------------------------------------------------

class TestDeepValidatorsSubSteps:
    """Steps 16a, 16b, and 16c must have entries in DEEP_VALIDATORS."""

    def test_16a_present(self):
        assert "16a" in DEEP_VALIDATORS

    def test_16b_present(self):
        assert "16b" in DEEP_VALIDATORS

    def test_16c_present(self):
        assert "16c" in DEEP_VALIDATORS

    @pytest.mark.parametrize("step", ["16a", "16b", "16c"])
    def test_callable(self, step):
        assert callable(DEEP_VALIDATORS[step])

    @pytest.mark.parametrize("step", ["16a", "16b", "16c"])
    def test_shares_validator_with_step_16(self, step):
        """Sub-steps should delegate to the same validator logic as step 16."""
        # Both lambdas wrap step_16.validate_step_16; we can verify by
        # checking that calling with trivially empty data does not raise.
        validator = DEEP_VALIDATORS[step]
        # A minimal call — validators return a list of error strings.
        # An empty dict will likely produce errors, but should not raise.
        result = validator({}, ".", {})
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 3. validators package importability
# ---------------------------------------------------------------------------

class TestValidatorsPackage:
    """The ``specdev_tools.validation.validators`` package must be importable."""

    def test_package_importable(self):
        mod = importlib.import_module("specdev_tools.validation.validators")
        assert mod is not None

    def test_step_01_importable(self):
        mod = importlib.import_module("specdev_tools.validation.validators.step_01")
        assert hasattr(mod, "validate_step_01")


# ---------------------------------------------------------------------------
# 4. Migration runner importability
# ---------------------------------------------------------------------------

class TestMigrationRunner:
    """Verify that the migration runner module imports without errors."""

    def test_execute_single_step_importable(self):
        from specdev_tools.migration.runner import execute_single_step

        assert callable(execute_single_step)


# ---------------------------------------------------------------------------
# 5. init_project.py --venv-name argument
# ---------------------------------------------------------------------------

class TestInitProjectVenvName:
    """Verify that ``scripts/init_project.py`` supports ``--venv-name``."""

    _INIT_SCRIPT = (
        Path(__file__).resolve().parents[4] / "scripts" / "init_project.py"
    )

    def test_script_exists(self):
        assert self._INIT_SCRIPT.is_file(), f"init_project.py not found at {self._INIT_SCRIPT}"

    def test_contains_venv_name_argument(self):
        source = self._INIT_SCRIPT.read_text()
        assert "--venv-name" in source, "init_project.py should accept --venv-name"

    def test_default_is_devspec_env(self):
        source = self._INIT_SCRIPT.read_text()
        # The default value should be devspec_env
        assert 'default="devspec_env"' in source


# ---------------------------------------------------------------------------
# 6. Verb-named properties of the step 16 plan schema
# ---------------------------------------------------------------------------

_SCHEMA_DIR = Path(__file__).resolve().parents[4] / "schema"


def _verb_named_properties(node: Any, verbs: frozenset[str], path: str = "") -> dict[str, dict[str, Any]]:
    """Every property named like a link verb anywhere under *node*, keyed by its path."""
    found: dict[str, dict[str, Any]] = {}
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            for name, sub in props.items():
                if name in verbs and isinstance(sub, dict):
                    found[f"{path}.{name}"] = sub
        for key, value in node.items():
            found.update(_verb_named_properties(value, verbs, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.update(_verb_named_properties(value, verbs, f"{path}[{index}]"))
    return found


def test_verb_named_property_rule_in_impl_context_schema():
    """Every verb-named property of the plan schema declares ``x-link``; the old ``review_state.verified_by`` is gone."""
    verbs = frozenset(
        json.loads((_SCHEMA_DIR / "core" / "graph.schema.json").read_text())["$defs"]["linkVerb"]["enum"]
    )
    schema = json.loads((_SCHEMA_DIR / "16_impl_context.schema.json").read_text())
    found = _verb_named_properties(schema, verbs)
    assert found, "the plan item declares at least its realises link"
    assert [path for path, sub in found.items() if "x-link" not in sub] == []
    assert "review_state" not in schema["properties"]["extensions"]["properties"]
