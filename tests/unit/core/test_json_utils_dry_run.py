"""Tests for json_utils dry-run mechanics and WS1 differential schema validation.

Rewritten in Chunk E of DEVSPEC-37:
- All ``validate_against_schema_field`` tests removed (function deleted).
- Existing dry-run MECHANICS tests kept; schemaless fixtures call with validate=False.
- New WS1 unit tests added (see §5 of DEVSPEC-37_schema_validation_and_merge_consolidation.md).
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

from specdev_tools.core.json_utils import (
    json_delete,
    json_insert,
    json_patch,
)

# ---------------------------------------------------------------------------
# Shared fixture paths and helpers
# ---------------------------------------------------------------------------

# The toolkit root (this worktree) — guaranteed to have tools/schema_registry.json.
_TOOLKIT_ROOT = str(pathlib.Path(__file__).resolve().parents[3])

# Step-16 impl-context fixture directory.
_STEP16_DIR = pathlib.Path(_TOOLKIT_ROOT) / "tests" / "fixtures" / "step_16" / "impl_context"


def _make_spec_file(tmp_path: pathlib.Path, content: dict | None = None) -> pathlib.Path:
    """Create a minimal schemaless spec file used by the dry-run MECHANICS tests."""
    f = tmp_path / "04_fr_list.json"
    f.write_text(json.dumps(content or {"owner": "api", "items": [1, 2]}), encoding="utf-8")
    return f


def _copy_fixture(tmp_path: pathlib.Path, name: str) -> pathlib.Path:
    """Copy a step-16 fixture into tmp_path (so tests can write without modifying originals)."""
    src = _STEP16_DIR / name
    dst = tmp_path / name
    shutil.copy2(str(src), str(dst))
    return dst


# ---------------------------------------------------------------------------
# dry_run MECHANICS tests  (validate=False — fixtures lack $schema)
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_patch_dry_run_does_not_write(self, tmp_path: pathlib.Path) -> None:
        f = _make_spec_file(tmp_path)
        original = f.read_text(encoding="utf-8")

        result = json_patch(str(f), ".owner", '"product"', dry_run=True, validate=False)

        assert f.read_text(encoding="utf-8") == original, "File must not be modified in dry-run"
        assert "[dry-run]" in result
        assert "product" in result

    def test_patch_dry_run_false_writes(self, tmp_path: pathlib.Path) -> None:
        f = _make_spec_file(tmp_path)

        result = json_patch(str(f), ".owner", '"product"', dry_run=False, validate=False)

        content = json.loads(f.read_text(encoding="utf-8"))
        assert content["owner"] == "product"
        assert "[dry-run]" not in result

    def test_insert_dry_run_does_not_write(self, tmp_path: pathlib.Path) -> None:
        f = _make_spec_file(tmp_path)
        original = f.read_text(encoding="utf-8")

        result = json_insert(str(f), ".items", "99", dry_run=True, validate=False)

        assert f.read_text(encoding="utf-8") == original
        assert "[dry-run]" in result
        assert "99" in result

    def test_delete_dry_run_does_not_write(self, tmp_path: pathlib.Path) -> None:
        f = _make_spec_file(tmp_path)
        original = f.read_text(encoding="utf-8")

        result = json_delete(str(f), ".items[0]", dry_run=True)

        assert f.read_text(encoding="utf-8") == original
        assert "[dry-run]" in result


# ---------------------------------------------------------------------------
# WS1 differential validation tests  (§5 of the DEVSPEC-37 contract)
# ---------------------------------------------------------------------------


class TestWS1DifferentialValidation:
    """DEVSPEC-37 WS1 — implicit, differential, always-on schema validation."""

    # ------------------------------------------------------------------
    # §5: DEVSPEC-37 leaf write — step-16 plan fixture nested status
    # ------------------------------------------------------------------

    def test_devspec37_leaf_invalid_enum_is_refused(self, tmp_path: pathlib.Path) -> None:
        """Patching a nested status to an invalid enum is refused with the enum message.

        This is the canonical DEVSPEC-37 repro: step 16 has TWO schemas;
        ``vc:16-impl-context`` is selected by the document's own ``$schema``,
        so the wrong-schema bug (P1.1 — ``_find_schema_file`` always picking
        ``16_anchor.schema.json``) does not fire.
        """
        f = _copy_fixture(tmp_path, "valid_full.json")

        # checklist[1] has implementation.status = "verified"
        with pytest.raises(Exception, match="'verifyed' is not one of"):
            json_patch(
                str(f),
                ".plan.spec_alignment.checklist[1].implementation.status",
                '"verifyed"',
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    def test_devspec37_leaf_valid_enum_succeeds(self, tmp_path: pathlib.Path) -> None:
        """Patching a nested status to a valid enum writes successfully.

        Uses checklist[1] (which already has ``implementation.status = "verified"``)
        and patches to ``"in_progress"`` — a valid enum value that introduces
        no new schema violations (empirically verified).
        """
        f = _copy_fixture(tmp_path, "valid_full.json")

        result = json_patch(
            str(f),
            ".plan.spec_alignment.checklist[1].implementation.status",
            '"in_progress"',
            validate=True,
            repo_root=_TOOLKIT_ROOT,
        )

        assert "[dry-run]" not in result
        content = json.loads(f.read_text(encoding="utf-8"))
        assert content["plan"]["spec_alignment"]["checklist"][1]["implementation"]["status"] == "in_progress"

    # ------------------------------------------------------------------
    # §5: Incremental fix (no deadlock)
    # ------------------------------------------------------------------

    def test_incremental_fix_no_deadlock(self, tmp_path: pathlib.Path) -> None:
        """A valid patch on a doc with pre-existing errors SUCCEEDS.

        ``invalid_bad_enum.json`` has 5 pre-existing schema errors.  Patching the
        ``plan.summary.functional_summary`` field (a valid string) introduces no
        new errors → the write must succeed, proving the differential check does not
        deadlock incremental repair.
        """
        f = _copy_fixture(tmp_path, "invalid_bad_enum.json")

        result = json_patch(
            str(f),
            ".plan.summary.functional_summary",
            '"Updated valid summary text"',
            validate=True,
            repo_root=_TOOLKIT_ROOT,
        )

        assert "[dry-run]" not in result
        content = json.loads(f.read_text(encoding="utf-8"))
        assert content["plan"]["summary"]["functional_summary"] == "Updated valid summary text"

    # ------------------------------------------------------------------
    # §5: Array-reindex false-positive (fail-CLOSED behavior documented)
    # ------------------------------------------------------------------

    def test_array_reindex_false_positive_fails_closed(self, tmp_path: pathlib.Path) -> None:
        """Replacing an array with a version that reindexes an already-erroring element IS refused.

        KNOWN LIMITATION (§4 of the contract): the error identity is
        ``(instance_path, message)``.  When an array already contains errors and a
        write shifts their indices, the before-set errors appear at the old paths and
        the after-set errors appear at new paths — the set subtraction treats the
        shifted errors as "new", producing a false refusal.

        Mechanism: ``invalid_bad_enum.json`` has four checklist[0] errors
        (``'super_layer'`` invalid enum + three missing required fields).  We call
        ``json_patch`` to REPLACE ``.plan.spec_alignment.checklist`` with a new array
        that prepends one fully-valid item, pushing the existing bad element from
        index 0 to index 1.  The differential ``(path, message)`` check sees the
        checklist[0] errors as "disappeared" and the checklist[1] errors as "new",
        so the write is refused even though no net violation was introduced.

        The refusal is fail-CLOSED (safe, never silently writes a violation).
        This is not a bug — it is the accepted trade-off per §4.
        """
        f = _copy_fixture(tmp_path, "invalid_bad_enum.json")

        # Load the existing erroring item so the new array contains ONLY the
        # pre-existing bad item shifted to index 1 — no freshly-introduced violation.
        with open(str(f), encoding="utf-8") as fh:
            original = json.load(fh)
        bad_item = original["plan"]["spec_alignment"]["checklist"][0]

        # Fully-valid item to prepend (all required fields present, valid enum values).
        valid_prepend = {
            "id": "REQ_VALID_PREPEND",
            "spec_ref": {
                "type": "code",
                "id": "schema-user-table",
                "line_range": "L1-L100",
                "commit_hash": "2222222222222222222222222222222222222222",
            },
            "description": "Valid prepended item",
            "type": "metadata",
            "layer": "db",
            "linked_test_expectation": "migration applies successfully",
            "nfr_refs": ["nfr-availability-uptime"],
            "fixture_ref": "fixture-database-migration",
            "checklist_status": "deferred",
        }
        new_checklist = [valid_prepend, bad_item]

        # The patch replaces the whole checklist array.  The pre-existing checklist[0]
        # errors (at path-index 0) appear to "disappear"; the same errors now at
        # path-index 1 are counted as "new" → refused (§4 path-shift false-positive).
        with pytest.raises(Exception) as exc_info:
            json_patch(
                str(f),
                ".plan.spec_alignment.checklist",
                json.dumps(new_checklist),
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )
        msg = str(exc_info.value)
        assert "introduces schema violation" in msg
        # The shifted pre-existing error appears at checklist[1] (not a new violation).
        assert "checklist[1]" in msg
        # The discriminating enum value proves this is the pre-existing §4 path-shift,
        # not a freshly-introduced violation.
        assert "super_layer" in msg

    # ------------------------------------------------------------------
    # §5: $schema-target patch is refused
    # ------------------------------------------------------------------

    def test_schema_target_patch_refused(self, tmp_path: pathlib.Path) -> None:
        """Patching the $schema field itself is refused with a descriptive message."""
        f = _copy_fixture(tmp_path, "valid_full.json")

        with pytest.raises(Exception, match="Refusing to patch \\$schema"):
            json_patch(
                str(f),
                '.["$schema"]',
                '"vc:16-anchor"',
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    # ------------------------------------------------------------------
    # §5: No-$schema file — refused; same call with validate=False → writes
    # ------------------------------------------------------------------

    def test_no_schema_file_refused(self, tmp_path: pathlib.Path) -> None:
        """Patching a schemaless file is refused with the no-$schema didactic."""
        f = tmp_path / "schemaless.json"
        f.write_text(json.dumps({"owner": "api", "value": "foo"}), encoding="utf-8")

        with pytest.raises(Exception, match="declares no \\$schema"):
            json_patch(
                str(f),
                ".value",
                '"bar"',
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    def test_no_schema_file_validate_false_writes(self, tmp_path: pathlib.Path) -> None:
        """Same patch with validate=False succeeds on a schemaless file."""
        f = tmp_path / "schemaless.json"
        f.write_text(json.dumps({"owner": "api", "value": "foo"}), encoding="utf-8")

        result = json_patch(
            str(f),
            ".value",
            '"bar"',
            validate=False,
        )

        assert "[dry-run]" not in result
        content = json.loads(f.read_text(encoding="utf-8"))
        assert content["value"] == "bar"

    # ------------------------------------------------------------------
    # §5: Field-type coverage (string, number, pattern, enum)
    # ------------------------------------------------------------------

    def test_string_type_enforced(self, tmp_path: pathlib.Path) -> None:
        """Patching a string field with a number is refused: type violation."""
        f = _copy_fixture(tmp_path, "ms_auth_plan.json")

        with pytest.raises(Exception, match="is not of type 'string'"):
            json_patch(
                str(f),
                ".plan.spec_alignment.checklist[0].id",
                "42",  # integer, not string
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    def test_number_type_enforced(self, tmp_path: pathlib.Path) -> None:
        """Patching an integer exit_code field with a string is refused: type violation.

        ``valid_with_semantic_review.json`` contains
        ``.execution.execution_results[0].evidence_binding.exit_code`` whose schema
        declares ``type: integer``.  Patching it to a string value exercises genuine
        number-type enforcement, producing the ``is not of type 'integer'`` message.
        """
        f = _copy_fixture(tmp_path, "valid_with_semantic_review.json")

        with pytest.raises(Exception, match="is not of type 'integer'"):
            json_patch(
                str(f),
                ".execution.execution_results[0].evidence_binding.exit_code",
                '"not-an-integer"',  # string, not integer
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    def test_pattern_enforced(self, tmp_path: pathlib.Path) -> None:
        """Patching commit_hash with a non-hex-40 string is refused: pattern violation."""
        f = _copy_fixture(tmp_path, "ms_auth_plan.json")

        with pytest.raises(Exception, match="does not match"):
            json_patch(
                str(f),
                ".plan.spec_alignment.checklist[0].spec_ref.commit_hash",
                '"INVALID_HASH_NOT_HEX40"',
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    def test_enum_enforced(self, tmp_path: pathlib.Path) -> None:
        """Patching a status field with a non-enum value is refused: enum violation."""
        f = _copy_fixture(tmp_path, "valid_full.json")

        with pytest.raises(Exception, match="is not one of"):
            json_patch(
                str(f),
                ".plan.spec_alignment.checklist[1].implementation.status",
                '"bad_status_value"',
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    # ------------------------------------------------------------------
    # §5: HOST-CWD RESOLUTION REGRESSION (BLOCKING)
    # ------------------------------------------------------------------

    def test_host_cwd_resolution_regression_direct(self, tmp_path: pathlib.Path) -> None:
        """Toolkit-root fallback resolves correctly when repo_root lacks schema_registry.

        The CLI always passes ``repo_root=os.path.abspath(args.repo_root)`` with
        default ``args.repo_root='.'``.  In a submodule deployment, ``cwd=host-root``
        means ``./tools/schema_registry.json`` is the HOST wrapper dir — not the
        toolkit.  The fallback must resolve the schema via the package-relative path.

        This test mirrors the real CLI path:
        - ``repo_root`` is an abspath of a directory that does NOT contain
          ``tools/schema_registry.json`` (simulating a host root cwd).
        - ``validate=True`` — the CLI always sets this.
        - Asserts the refusal carries the ENUM message (proving validation ran
          against the correct ``vc:16-impl-context`` schema via the fallback).
          A bootstrap-error refusal would carry a schema-location message instead.
        """
        # tmp_path has no tools/schema_registry.json — simulates host root.
        assert not os.path.isfile(os.path.join(str(tmp_path), "tools", "schema_registry.json"))

        f = _copy_fixture(tmp_path, "valid_full.json")

        with pytest.raises(Exception, match="is not one of"):
            json_patch(
                str(f),
                ".plan.spec_alignment.checklist[1].implementation.status",
                '"bad_status_for_regression_test"',
                validate=True,
                repo_root=str(tmp_path),  # abspath of dir WITHOUT tools/schema_registry.json
            )

    def test_host_cwd_resolution_regression_subprocess(self, tmp_path: pathlib.Path) -> None:
        """Strongest form: subprocess CLI with no --repo-root from a host-like cwd.

        Runs ``specdev json patch`` from a temp directory (no schema_registry.json
        there) patching an invalid enum.  Asserts the exit code is 1 (refused) and
        the stderr contains the enum message — proving the package-relative fallback
        resolved the schema correctly without crashing on bootstrap failure.
        """
        # Set up the fixture in tmp_path.
        plan_file = _copy_fixture(tmp_path, "valid_full.json")

        result = subprocess.run(
            [
                sys.executable, "-m", "specdev_tools.core.json_utils",
                "patch",
                str(plan_file),
                ".plan.spec_alignment.checklist[1].implementation.status",
                '"subprocess_bad_status"',
                # No --repo-root → defaults to "." → tmp_path has no schema_registry.json
                # → package-relative fallback must kick in.
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),  # host-like cwd with no toolkit
        )

        assert result.returncode == 1, (
            f"Expected exit 1 (refused), got {result.returncode}. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # The enum message proves validation ran against the correct schema.
        assert "is not one of" in result.stderr or "not one of" in result.stderr, (
            f"Expected enum error message in stderr; got: {result.stderr!r}"
        )

    # ------------------------------------------------------------------
    # §5.5b/c/d: WS4 insert tests (command_prefixes.json)
    # ------------------------------------------------------------------

    def test_ws4_steady_state_valid_insert_succeeds(self, tmp_path: pathlib.Path) -> None:
        """(5b) Steady-state: inserting a valid string prefix into a schema'd file succeeds."""
        # Create a command_prefixes.json with $schema already present.
        cp_file = tmp_path / "command_prefixes.json"
        cp_file.write_text(
            json.dumps({
                "$schema": "vc:canon:command-prefixes",
                "allowed_prefixes": ["pytest"],
            }),
            encoding="utf-8",
        )

        result = json_insert(
            str(cp_file),
            ".allowed_prefixes",
            '"deno"',
            validate=True,
            repo_root=_TOOLKIT_ROOT,
        )

        assert "[dry-run]" not in result
        content = json.loads(cp_file.read_text(encoding="utf-8"))
        assert "deno" in content["allowed_prefixes"]

    def test_ws4_steady_state_non_string_insert_refused(self, tmp_path: pathlib.Path) -> None:
        """(5b) Steady-state: inserting a non-string (integer) prefix is refused."""
        cp_file = tmp_path / "command_prefixes.json"
        cp_file.write_text(
            json.dumps({
                "$schema": "vc:canon:command-prefixes",
                "allowed_prefixes": ["pytest"],
            }),
            encoding="utf-8",
        )

        with pytest.raises(Exception, match="is not of type"):
            json_insert(
                str(cp_file),
                ".allowed_prefixes",
                "42",  # integer, not a string
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    def test_ws4_negative_control_no_schema_refused(self, tmp_path: pathlib.Path) -> None:
        """(5c) Negative control: inserting into a command_prefixes.json LACKING $schema is refused."""
        cp_file = tmp_path / "command_prefixes.json"
        cp_file.write_text(
            json.dumps({"allowed_prefixes": ["pytest"]}),
            encoding="utf-8",
        )

        with pytest.raises(Exception, match="declares no \\$schema"):
            json_insert(
                str(cp_file),
                ".allowed_prefixes",
                '"deno"',
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    def test_ws4_bootstrap_creates_file_with_schema(self, tmp_path: pathlib.Path) -> None:
        """(5d) BOOTSTRAP: --create-schema seeds missing file and inserts value.

        When the target file does not exist and ``create_schema`` is set, the
        file is created as ``{"$schema":"vc:canon:command-prefixes","allowed_prefixes":["deno"]}``
        and the write succeeds.  The created file is validated against the schema.
        """
        cp_file = tmp_path / "command_prefixes.json"
        assert not cp_file.exists()

        result = json_insert(
            str(cp_file),
            ".allowed_prefixes",
            '"deno"',
            create_schema="vc:canon:command-prefixes",
            validate=True,
            repo_root=_TOOLKIT_ROOT,
        )

        assert cp_file.exists()
        content = json.loads(cp_file.read_text(encoding="utf-8"))
        assert content["$schema"] == "vc:canon:command-prefixes"
        assert content["allowed_prefixes"] == ["deno"]
        assert "[dry-run]" not in result

        # Assert the created file is byte-valid against the schema.
        from specdev_tools.core.schema_validate import validate_data_against_schema
        errors = validate_data_against_schema(_TOOLKIT_ROOT, content)
        assert errors == [], f"Created file failed schema validation: {errors}"

    def test_ws4_bootstrap_control_without_create_schema_errors(self, tmp_path: pathlib.Path) -> None:
        """(5d control) Without --create-schema, inserting into a missing file errors File not found."""
        cp_file = tmp_path / "command_prefixes.json"
        assert not cp_file.exists()

        with pytest.raises(Exception, match="File not found"):
            json_insert(
                str(cp_file),
                ".allowed_prefixes",
                '"deno"',
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )

    def test_ws4_create_schema_existing_file_noops(self, tmp_path: pathlib.Path) -> None:
        """(5d edge) --create-schema is a no-op when the file already exists."""
        cp_file = tmp_path / "command_prefixes.json"
        existing_content = {
            "$schema": "vc:canon:command-prefixes",
            "allowed_prefixes": ["existing"],
        }
        cp_file.write_text(json.dumps(existing_content), encoding="utf-8")

        # With create_schema set but file exists — normal path, no seeding.
        result = json_insert(
            str(cp_file),
            ".allowed_prefixes",
            '"deno"',
            create_schema="vc:canon:command-prefixes",
            validate=True,
            repo_root=_TOOLKIT_ROOT,
        )

        assert "Inserted into" in result, f"Expected success message; got: {result!r}"
        content = json.loads(cp_file.read_text(encoding="utf-8"))
        # $schema must not be changed (no re-seeding).
        assert content["$schema"] == "vc:canon:command-prefixes"
        assert "deno" in content["allowed_prefixes"]
        assert "existing" in content["allowed_prefixes"]

    def test_ws4_create_schema_existing_schemaless_file_refused(self, tmp_path: pathlib.Path) -> None:
        """(5d edge) --create-schema on an existing schemaless file fires the no-$schema refuse.

        --create-schema never back-doors a $schema into an existing file.
        """
        cp_file = tmp_path / "command_prefixes.json"
        cp_file.write_text(
            json.dumps({"allowed_prefixes": ["existing"]}),
            encoding="utf-8",
        )

        with pytest.raises(Exception, match="declares no \\$schema"):
            json_insert(
                str(cp_file),
                ".allowed_prefixes",
                '"deno"',
                create_schema="vc:canon:command-prefixes",
                validate=True,
                repo_root=_TOOLKIT_ROOT,
            )


# ---------------------------------------------------------------------------
# §5 Removal hygiene: --against-schema-field must be an unrecognized argument
# ---------------------------------------------------------------------------


class TestRemovalHygiene:
    def test_against_schema_field_patch_unrecognized(self, tmp_path: pathlib.Path) -> None:
        """A ``json patch`` invocation with ``--against-schema-field`` must fail with argparse error."""
        f = tmp_path / "dummy.json"
        f.write_text("{}", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable, "-m", "specdev_tools.core.json_utils",
                "patch",
                str(f),
                ".key",
                '"val"',
                "--against-schema-field", "04.owner",
            ],
            capture_output=True,
            text=True,
        )

        # argparse exits with code 2 on unrecognized arguments.
        assert result.returncode == 2, (
            f"Expected argparse exit 2; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )
        assert "unrecognized" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_against_schema_field_insert_unrecognized(self, tmp_path: pathlib.Path) -> None:
        """A ``json insert`` invocation with ``--against-schema-field`` must fail with argparse error."""
        f = tmp_path / "dummy.json"
        f.write_text("{}", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable, "-m", "specdev_tools.core.json_utils",
                "insert",
                str(f),
                ".items",
                '"val"',
                "--against-schema-field", "04.items",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2, (
            f"Expected argparse exit 2; got {result.returncode}. "
            f"stderr={result.stderr!r}"
        )
        assert "unrecognized" in result.stderr.lower() or "error" in result.stderr.lower()
