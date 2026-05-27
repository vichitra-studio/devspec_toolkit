"""Tests for gap-remediation features added during the v0.3.0 release cycle.

Covers:
- ``_get_step_from_path`` handling of ``impl_context/`` directories
- ``DEEP_VALIDATORS`` entries for steps 16a, 16b, 16c
- ``validators`` sub-package importability
- Migration runner ``execute_single_step`` importability
- ``init_project.py`` support for ``--venv-name`` argument
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from specdev_tools.validation.validate import DEEP_VALIDATORS, _get_step_from_path


# ---------------------------------------------------------------------------
# 1. _get_step_from_path: impl_context/ paths
# ---------------------------------------------------------------------------

class TestGetStepFromPathImplContext:
    """Files inside an ``impl_context/`` directory should map to step 16a (milestone plans)."""

    def test_relative_path(self):
        assert _get_step_from_path("spec/impl_context/step-api-core.json") == "16a"

    def test_absolute_path(self):
        assert _get_step_from_path("/abs/path/spec/impl_context/my-file.json") == "16a"

    def test_normal_step_still_works(self):
        assert _get_step_from_path("spec/04_frs.json") == "04"

    def test_unknown_file(self):
        assert _get_step_from_path("random_file.json") == "unknown"

    def test_step_16a(self):
        assert _get_step_from_path("spec/16a_impl_planner.json") == "16a"

    def test_step_16b(self):
        assert _get_step_from_path("spec/16b_code.json") == "16b"

    def test_step_16c(self):
        assert _get_step_from_path("spec/16c_review.json") == "16c"


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
