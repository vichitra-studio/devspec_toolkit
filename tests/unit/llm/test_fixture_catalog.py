"""Unit tests asserting that each spec-fixture directory fires the documented error code.

These tests exist to verify that the fixture dirs are correctly constructed —
if spec-check behaviour changes and a fixture no longer fires the expected code,
these tests will catch the regression.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLKIT_ROOT = Path(__file__).parents[3]  # devspec_toolkit/
FIXTURES_SPECS = TOOLKIT_ROOT / "tools" / "specdev_tools" / "llm" / "test_fixtures" / "specs"


def _run_spec_check(fixture_dir: Path) -> tuple[int, str]:
    """Run spec-check on a fixture directory; return (returncode, combined stdout+stderr)."""
    result = subprocess.run(
        [
            sys.executable, "-m", "specdev_tools.cli",
            "spec-check", str(fixture_dir),
            "--repo-root", str(TOOLKIT_ROOT),
            # Intentionally NO --spec-root so project-canon IDs (cn:project:*) aren't loaded
        ],
        capture_output=True,
        text=True,
        cwd=TOOLKIT_ROOT,
    )
    return result.returncode, result.stdout + result.stderr


class TestFixtureCatalog:
    def test_e110_missing_canon_fires(self) -> None:
        """e110_missing_canon/ must exit non-zero with at least one E110 UNKNOWN_CANONICAL_ID."""
        rc, output = _run_spec_check(FIXTURES_SPECS / "e110_missing_canon")
        assert rc != 0, (
            "Expected spec-check to exit non-zero for e110_missing_canon but got rc=0:\n" + output
        )
        assert "E110" in output, (
            "Expected E110 UNKNOWN_CANONICAL_ID from e110_missing_canon fixture but got:\n" + output
        )

    def test_e530_invented_verb_fires(self) -> None:
        """e530_invented_verb/ must exit non-zero with E530 INVENTED_ENUM_OR_ID."""
        rc, output = _run_spec_check(FIXTURES_SPECS / "e530_invented_verb")
        assert rc != 0, (
            "Expected spec-check to exit non-zero for e530_invented_verb but got rc=0:\n" + output
        )
        assert "E530" in output, (
            "Expected E530 from e530_invented_verb fixture but got:\n" + output
        )
        assert "INVENTED_ENUM_OR_ID" in output, (
            "Expected subcode INVENTED_ENUM_OR_ID in E530 output but got:\n" + output
        )

    def test_e530_missing_test_file_fires(self) -> None:
        """e530_missing_test_file/ must exit non-zero with E530 LINKED_TEST_FILE_NOT_FOUND."""
        rc, output = _run_spec_check(FIXTURES_SPECS / "e530_missing_test_file")
        assert rc != 0, (
            "Expected spec-check to exit non-zero for e530_missing_test_file but got rc=0:\n" + output
        )
        assert "E530" in output, (
            "Expected E530 from e530_missing_test_file fixture but got:\n" + output
        )
        assert "LINKED_TEST_FILE_NOT_FOUND" in output, (
            "Expected subcode LINKED_TEST_FILE_NOT_FOUND in output but got:\n" + output
        )
