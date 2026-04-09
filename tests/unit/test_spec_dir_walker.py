"""Unit tests for iter_spec_artifacts — the canonical spec-dir file-discovery helper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from specdev_tools.canonical.integrity import validate_canonical_integrity
from specdev_tools.core.loaders import iter_spec_artifacts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: dict | None = None) -> None:
    path.write_text(json.dumps(content or {}), encoding="utf-8")


# ---------------------------------------------------------------------------
# TestIterSpecArtifacts — unit tests for iter_spec_artifacts
# ---------------------------------------------------------------------------

class TestIterSpecArtifacts:

    # ---- basic discovery ----

    def test_yields_json_files_at_root(self, tmp_path):
        _write(tmp_path / "00_charter.json", {"$schema": "vc:00-charter"})
        names = {Path(p).name for p in iter_spec_artifacts(str(tmp_path))}
        assert "00_charter.json" in names

    def test_yields_json_files_in_subdirectories(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        _write(sub / "nested.json", {"$schema": "vc:nested"})
        names = {Path(p).name for p in iter_spec_artifacts(str(tmp_path))}
        assert "nested.json" in names

    def test_skips_non_json_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# readme", encoding="utf-8")
        _write(tmp_path / "00_charter.json")
        result = list(iter_spec_artifacts(str(tmp_path)))
        assert all(p.endswith(".json") for p in result)
        assert len(result) == 1

    def test_empty_dir_returns_empty(self, tmp_path):
        assert list(iter_spec_artifacts(str(tmp_path))) == []

    def test_nonexistent_dir_returns_empty(self, tmp_path):
        assert list(iter_spec_artifacts(str(tmp_path / "does_not_exist"))) == []

    # ---- spec/samples/ exclusion ----

    def test_excludes_samples_dir_at_top_level(self, tmp_path):
        """spec/samples/ must be silently skipped — runtime context, not spec artifact."""
        _write(tmp_path / "00_charter.json", {"$schema": "vc:00-charter"})
        samples = tmp_path / "samples"
        samples.mkdir()
        _write(samples / "invariants_sample.json", {"post": {"status": "published"}})
        _write(samples / "junk.json")

        result = [Path(p).name for p in iter_spec_artifacts(str(tmp_path))]
        assert "00_charter.json" in result
        assert "invariants_sample.json" not in result
        assert "junk.json" not in result

    def test_samples_nested_under_other_dirs_are_included(self, tmp_path):
        """spec/03_glossary/samples/ is a spec artifact — must NOT be excluded."""
        sub = tmp_path / "03_glossary"
        sub.mkdir()
        nested_samples = sub / "samples"
        nested_samples.mkdir()
        _write(nested_samples / "artifact.json", {"$schema": "vc:something"})

        result = [Path(p).name for p in iter_spec_artifacts(str(tmp_path))]
        assert "artifact.json" in result

    # ---- migration_backups exclusion ----

    def test_excludes_migration_backups_at_top_level(self, tmp_path):
        _write(tmp_path / "00_charter.json")
        backup = tmp_path / "migration_backups"
        backup.mkdir()
        _write(backup / "old.json")

        result = list(iter_spec_artifacts(str(tmp_path)))
        assert not any("migration_backups" in p for p in result)
        assert len(result) == 1

    def test_excludes_migration_backups_in_subdirectory(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        backup = sub / "migration_backups"
        backup.mkdir()
        _write(backup / "archived.json")
        _write(sub / "real.json")

        result = [Path(p).name for p in iter_spec_artifacts(str(tmp_path))]
        assert "archived.json" not in result
        assert "real.json" in result

    # ---- combined exclusions ----

    def test_complete_fixture_tree(self, tmp_path):
        """Mirrors the spec structure from the task description exactly."""
        _write(tmp_path / "00_charter.json", {"$schema": "vc:00-charter"})
        samples = tmp_path / "samples"
        samples.mkdir()
        _write(samples / "invariants_sample.json")
        _write(samples / "junk.json")

        result = list(iter_spec_artifacts(str(tmp_path)))
        names = [Path(p).name for p in result]
        assert names == ["00_charter.json"]


# ---------------------------------------------------------------------------
# Integration: spec-check skips samples/, invariants-check still reads it
# ---------------------------------------------------------------------------

class TestSpecCheckExcludesSamples:
    """subprocess-level integration tests."""

    def _cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", *args],
            capture_output=True, text=True,
        )

    def test_spec_check_ignores_sample_file(self, tmp_path):
        """spec-check must exit 0 when spec/samples/invariants_sample.json is present
        with non-canonical values — the file must be silently skipped, not flagged."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        # A minimal valid charter so spec-check has something real to validate
        _write(spec_dir / "00_charter.json", {
            "$schema": "https://raw.githubusercontent.com/vichitracollective/"
                       "devspec_toolkit/main/schema/00_charter.schema.json",
        })
        # Runtime evaluation context — deliberately schema-free
        samples = spec_dir / "samples"
        samples.mkdir()
        _write(samples / "invariants_sample.json", {
            "post": {"status": "published"},
            "request": {"user": {"role": "owner"}},
        })

        r = self._cli(
            "validate-all", str(spec_dir),
            "--repo-root", str(Path(__file__).resolve().parents[3]),
            "--json",
        )
        # Fail loudly if the CLI produced no JSON — previously this silently
        # passed the assertion because an empty errors list trivially does not
        # contain the sample filename.
        assert r.stdout.strip(), (
            f"empty stdout from validate-all (returncode={r.returncode}): "
            f"stderr={r.stderr}"
        )
        env = json.loads(r.stdout)
        assert "errors" in env, f"missing 'errors' key in envelope: {env}"
        # E520 (missing $schema) must NOT appear for the sample file
        errors_text = json.dumps(env["errors"])
        assert "invariants_sample" not in errors_text, (
            f"sample file leaked into validate-all errors: {errors_text}"
        )

    def test_canonical_integrity_skips_sample_file(self, tmp_path):
        """Direct call to validate_canonical_integrity — the original bug path.

        Reproduces the E210 CROSS_ARTIFACT_DRIFT failure mode: a sample file
        with canonical-looking values (post.status, user.role) must NOT be
        flagged because it lives under spec/samples/.
        """
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        samples = spec_dir / "samples"
        samples.mkdir()
        _write(samples / "invariants_sample.json", {
            "post": {"status": "published"},
            "request": {"user": {"role": "owner"}},
        })

        toolkit_root = str(Path(__file__).resolve().parents[3])
        errors = validate_canonical_integrity(
            repo_root=toolkit_root,
            spec_dir=str(spec_dir),
            project_canon_dir=None,
        )
        # The sample file must not appear in any error path/message. Any other
        # errors (e.g. missing upstream specs) are acceptable — we only care
        # that the sample file itself was never opened by the walker.
        offending = [
            e for e in errors
            if "invariants_sample" in (getattr(e, "message", "") or "")
            or "samples" in (getattr(e, "path", "") or "")
        ]
        assert offending == [], (
            f"canonical-integrity leaked into samples/: {offending}"
        )

    def test_invariants_check_still_reads_sample_explicitly(self, tmp_path):
        """invariants-check --sample spec/samples/invariants_sample.json must still
        evaluate rules — the samples/ exclusion applies to discovery only."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        # A step-06 invariants file with one always-true JSONLogic rule
        _write(spec_dir / "06_invariants.json", {
            "$schema": "vc:06-invariants",
            "id": "invariants-integration-test",
            "owner": "api",
            "created_at": "2025-01-01T00:00:00Z",
            "rules": [{
                "inv_id": "inv-always-true",
                "description": "always true",
                "language": "jsonlogic",
                "expression": {"==": [1, 1]},
                "scope": {"components": ["test"], "apis": []},
                "severity": "error",
                "trace": [],
            }],
            "canonical_refs_used": [],
            "canonical_proposals": [],
            "canonical_conflicts": [],
        })
        # Sample file in spec/samples/ — must be read by invariants-check
        samples = spec_dir / "samples"
        samples.mkdir()
        sample_path = samples / "invariants_sample.json"
        _write(sample_path, {"post": {"status": "published"}})

        r = self._cli(
            "invariants-check", str(spec_dir),
            "--sample", str(sample_path),
            "--json",
        )
        assert r.returncode == 0, r.stderr
        env = json.loads(r.stdout)
        assert env["status"] == "PASS"
        assert env["error_count"] == 0
        results = env["result"]
        assert len(results) == 1
        assert results[0]["inv_id"] == "inv-always-true"
        assert results[0]["evaluable"] is True
        assert results[0]["result"] is True
