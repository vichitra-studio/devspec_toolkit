"""Smoke tests for context-extraction CLI commands.

Covers the five previously untested modules:
  - context/structure.py      → `specdev context structure`
  - context/canon_extractor.py → `specdev context canon`
  - context/freshness.py      → `specdev context freshness`
  - context/scope_resolver.py → `specdev context scope`
  - context/seed_indexer.py   → `specdev seed-index`

Each test exercises the real code path via subprocess (matching the
test_extractor.py convention) and asserts a non-trivial postcondition on
the JSON output — not merely "didn't crash".
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / "tools"
SPEC_CORPUS = REPO_ROOT / "tests" / "fixtures" / "spec_corpus"


@pytest.fixture
def spec_corpus_copy(tmp_path):
    """Return a temporary copy of SPEC_CORPUS so writes (e.g. trace_matrix.json)
    land in tmp_path rather than the tracked fixture directory."""
    dest = tmp_path / "spec_corpus"
    shutil.copytree(str(SPEC_CORPUS), str(dest))
    return dest


def _run(*args: str) -> subprocess.CompletedProcess:
    """Run a specdev_tools.cli command, returning the CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli"] + list(args),
        capture_output=True,
        text=True,
        cwd=str(TOOLS_DIR),
    )


def _parse_json(proc: subprocess.CompletedProcess) -> dict:
    """Assert success and parse stdout as JSON."""
    assert proc.returncode == 0, (
        f"Command exited {proc.returncode}\n"
        f"stdout: {proc.stdout!r}\n"
        f"stderr: {proc.stderr!r}"
    )
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# context structure
# ---------------------------------------------------------------------------

class TestContextStructure:
    """Smoke tests for `specdev context structure`."""

    def test_returns_expected_keys(self):
        """Output JSON must contain the seven documented top-level keys."""
        proc = _run(
            "context", "structure", str(SPEC_CORPUS),
            "--step", "05",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        expected_keys = {
            "step", "required_inputs", "canon_kinds_needed",
            "canon_kinds_required", "canon_kinds_optional",
            "seeds_required", "output_schema_keys",
        }
        assert expected_keys == set(data.keys()), f"Unexpected key set: {set(data.keys())}"

    def test_step_echoed_correctly(self):
        """The 'step' field must echo the --step argument."""
        proc = _run(
            "context", "structure", str(SPEC_CORPUS),
            "--step", "05",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert data["step"] == "05"

    def test_output_schema_keys_contains_apis(self):
        """Step 05 schema defines 'apis' as a step-specific property."""
        proc = _run(
            "context", "structure", str(SPEC_CORPUS),
            "--step", "05",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert "apis" in data["output_schema_keys"], (
            f"Expected 'apis' in output_schema_keys, got: {data['output_schema_keys']}"
        )

    def test_required_input_step04_has_real_file_data(self):
        """The spec_corpus has 04_fr_list.json — structure must reflect its actual content.

        This proves the file loader walked the real JSON file on disk rather
        than returning empty metadata.
        """
        proc = _run(
            "context", "structure", str(SPEC_CORPUS),
            "--step", "05",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        required_inputs = data["required_inputs"]
        assert required_inputs, "required_inputs must not be empty for step 05"

        step04_entry = next(
            (ri for ri in required_inputs if ri["step"] == "04"), None
        )
        assert step04_entry is not None, "Step 04 must appear as a required input for step 05"
        assert step04_entry["file"] == "04_fr_list.json", (
            f"Expected file '04_fr_list.json', got {step04_entry['file']!r}"
        )
        assert step04_entry["array_counts"].get("functional_requirements") == 1, (
            "spec_corpus/04_fr_list.json has exactly one FR; "
            f"got array_counts={step04_entry['array_counts']}"
        )


# ---------------------------------------------------------------------------
# context canon
# ---------------------------------------------------------------------------

class TestContextCanon:
    """Smoke tests for `specdev context canon`."""

    def test_returns_expected_top_level_keys(self):
        """Output must include all documented top-level keys."""
        proc = _run(
            "context", "canon",
            "--step", "04",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        expected_keys = {"step", "canon_kinds", "canon_kinds_required",
                         "canon_kinds_optional", "total_entries", "token_estimate"}
        assert expected_keys == set(data.keys()), f"Unexpected key set: {set(data.keys())}"

    def test_step04_capability_is_required(self):
        """Step 04 schema has a required capability_ref field → 'capability' must be required."""
        proc = _run(
            "context", "canon",
            "--step", "04",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert data["canon_kinds_required"] == ["capability"], (
            f"Expected ['capability'], got {data['canon_kinds_required']}"
        )

    def test_status_kind_has_canonical_entries(self):
        """The 'status' kind must be present with at least one cn:core:status: entry."""
        proc = _run(
            "context", "canon",
            "--step", "04",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert "status" in data["canon_kinds"], (
            f"'status' not found in canon_kinds. Keys: {list(data['canon_kinds'].keys())}"
        )
        status_entries = data["canon_kinds"]["status"]
        assert any(
            e.get("id", "").startswith("cn:core:status:")
            for e in status_entries
        ), f"No cn:core:status: entry found. entries={status_entries[:3]}"

    def test_total_entries_nonzero(self):
        """At least some canon entries must be loaded for step 04."""
        proc = _run(
            "context", "canon",
            "--step", "04",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert data["total_entries"] >= 1, (
            f"Expected at least 1 total_entries, got {data['total_entries']}"
        )


# ---------------------------------------------------------------------------
# context freshness
# ---------------------------------------------------------------------------

class TestContextFreshness:
    """Smoke tests for `specdev context freshness`.

    Fixture layout (standard flat layout):
        tmp_path/           ← host root; dirname(spec_dir) == host root
          spec/             ← spec_dir passed to commands
            common/
              seed_manifest.json
          docs/seed/        ← seeds[].path = "docs/seed/..." (relative to host root)
            seed_overview.md

    The git_root-implicit path (git_root=None → dirname(spec_dir)) is tested by
    all tests that omit --git-root.  The explicit nested-layout tests at the
    bottom of this class pass --git-root explicitly and prove correctness when
    host_root != dirname(spec_dir).
    """

    def test_no_index_when_no_seed_requirements(self, tmp_path):
        """freshness returns {'status': 'no_index'} when no seed_requirements.json exists."""
        spec_dir = tmp_path / "spec"
        (spec_dir / "common").mkdir(parents=True)
        proc = _run(
            "context", "freshness", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert data == {"status": "no_index"}, (
            f"Expected no_index result, got {data}"
        )

    def test_fresh_seed_reports_not_stale(self, tmp_path):
        """A seed document that has not changed since indexing must report stale=False.

        Setup: write a seed file, build seed_requirements.json via seed-index,
        then call freshness and assert on the populated result.

        Uses the standard flat layout: spec_dir = tmp_path/spec, seeds at
        tmp_path/docs/seed/ (seeds[].path relative to tmp_path == host root).
        No --git-root flag → dirname(spec_dir) == tmp_path is used as host root.
        """
        # 1. Build the host + spec dir structure
        spec_dir = tmp_path / "spec"
        common_dir = spec_dir / "common"
        seed_file_dir = tmp_path / "docs" / "seed"
        common_dir.mkdir(parents=True)
        seed_file_dir.mkdir(parents=True)
        seed_file = seed_file_dir / "seed_overview.md"
        seed_file.write_text("Smoke test seed content.\n", encoding="utf-8")

        manifest = {
            "$schema": "vc:seed-manifest",
            "seed_manifest_id": "seed-manifest-smoke",
            "version": "0.1.0",
            "created_at": "2026-01-01T00:00:00Z",
            "last_updated": "2026-01-01T00:00:00Z",
            "global_seed_order": ["seed-overview"],
            "seeds": [
                {
                    "seed_id": "seed-overview",
                    "path": "docs/seed/seed_overview.md",
                    "description": "Smoke test seed",
                    "required": True,
                    "source_type": "doc",
                }
            ],
            "step_requirements": {"00": ["seed-overview"]},
        }
        (common_dir / "seed_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # 2. Run seed-index to produce seed_requirements.json
        idx_proc = _run(
            "seed-index", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
            "--json",
        )
        assert idx_proc.returncode == 0, (
            f"seed-index failed: {idx_proc.stderr}"
        )

        # 3. Run freshness and verify the seed reports not stale
        proc = _run(
            "context", "freshness", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)

        assert "seed-overview" in data, (
            f"'seed-overview' not present in freshness output: {data}"
        )
        entry = data["seed-overview"]
        assert entry["stale"] is False, (
            "Seed was indexed and not modified; must not be stale"
        )
        assert entry["indexed_hash"].startswith("sha256:"), (
            f"indexed_hash must be a sha256: digest, got {entry['indexed_hash']!r}"
        )
        assert entry["current_hash"] == entry["indexed_hash"], (
            "indexed_hash and current_hash must match for an unmodified seed"
        )

    def test_stale_seed_detected(self, tmp_path):
        """Modifying a seed file after indexing must cause stale=True.

        Uses the standard flat layout (no --git-root).
        """
        spec_dir = tmp_path / "spec"
        common_dir = spec_dir / "common"
        seed_file_dir = tmp_path / "docs" / "seed"
        common_dir.mkdir(parents=True)
        seed_file_dir.mkdir(parents=True)
        seed_file = seed_file_dir / "seed_overview.md"
        seed_file.write_text("Original content.\n", encoding="utf-8")

        manifest = {
            "$schema": "vc:seed-manifest",
            "seed_manifest_id": "seed-manifest-stale-smoke",
            "version": "0.1.0",
            "created_at": "2026-01-01T00:00:00Z",
            "last_updated": "2026-01-01T00:00:00Z",
            "global_seed_order": ["seed-overview"],
            "seeds": [
                {
                    "seed_id": "seed-overview",
                    "path": "docs/seed/seed_overview.md",
                    "description": "Stale test seed",
                    "required": True,
                    "source_type": "doc",
                }
            ],
            "step_requirements": {"00": ["seed-overview"]},
        }
        (common_dir / "seed_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # Index the seed
        idx_proc = _run(
            "seed-index", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
            "--json",
        )
        assert idx_proc.returncode == 0, f"seed-index failed: {idx_proc.stderr}"

        # Modify the seed file so it's stale
        seed_file.write_text("Modified content — now stale!\n", encoding="utf-8")

        # Check freshness — expect stale=True
        proc = _run(
            "context", "freshness", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert "seed-overview" in data
        assert data["seed-overview"]["stale"] is True, (
            "Seed content changed after indexing; must report stale=True"
        )

    def test_nested_layout_freshness_resolves_via_git_root(self, tmp_path):
        """Nested layout: spec_dir is NOT a direct child of the host root.

        host_root = tmp_path
        spec_dir  = tmp_path/src/project/spec   (deeply nested)
        seeds     = tmp_path/docs/seed/seed_overview.md
        seeds[].path = "docs/seed/seed_overview.md"  (relative to host root)

        Without --git-root the dirname heuristic gives tmp_path/src/project —
        wrong.  With --git-root tmp_path the path resolves correctly.
        This test proves the nested-layout bug is fixed.
        """
        host_root = tmp_path
        spec_dir = tmp_path / "src" / "project" / "spec"
        common_dir = spec_dir / "common"
        seed_file_dir = host_root / "docs" / "seed"
        common_dir.mkdir(parents=True)
        seed_file_dir.mkdir(parents=True)
        seed_file = seed_file_dir / "seed_overview.md"
        seed_file.write_text("Nested layout seed content.\n", encoding="utf-8")

        manifest = {
            "$schema": "vc:seed-manifest",
            "seed_manifest_id": "seed-manifest-nested",
            "version": "0.1.0",
            "created_at": "2026-01-01T00:00:00Z",
            "last_updated": "2026-01-01T00:00:00Z",
            "global_seed_order": ["seed-overview"],
            "seeds": [
                {
                    "seed_id": "seed-overview",
                    "path": "docs/seed/seed_overview.md",
                    "description": "Nested layout seed",
                    "required": True,
                    "source_type": "doc",
                }
            ],
            "step_requirements": {"00": ["seed-overview"]},
        }
        (common_dir / "seed_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # seed-index must also use --git-root to resolve correctly
        idx_proc = _run(
            "seed-index", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
            "--git-root", str(host_root),
            "--json",
        )
        assert idx_proc.returncode == 0, (
            f"seed-index with --git-root failed: {idx_proc.stderr}"
        )

        # freshness with --git-root must find the seed and report it not stale
        proc = _run(
            "context", "freshness", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
            "--git-root", str(host_root),
        )
        data = _parse_json(proc)
        assert "seed-overview" in data, (
            f"'seed-overview' missing from freshness output for nested layout: {data}"
        )
        assert data["seed-overview"]["stale"] is False, (
            "Seed was just indexed and not modified; must not be stale (nested layout)"
        )
        assert data["seed-overview"]["current_hash"] != "", (
            "current_hash must be non-empty — seed found+hashed via --git-root"
        )
        assert data["seed-overview"]["current_hash"] == data["seed-overview"]["indexed_hash"], (
            "hashes must match for unmodified seed (nested layout)"
        )


# ---------------------------------------------------------------------------
# context scope
# ---------------------------------------------------------------------------

class TestContextScope:
    """Smoke tests for `specdev context scope`."""

    def test_entry_id_present_in_source_files(self, spec_corpus_copy):
        """The queried entry ID must appear in source_files with its origin file."""
        proc = _run(
            "context", "scope", str(spec_corpus_copy),
            "--entry", "FR-CORPUS-001",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert "FR-CORPUS-001" in data["source_files"], (
            f"FR-CORPUS-001 not found in source_files: {data.get('source_files')}"
        )
        assert data["source_files"]["FR-CORPUS-001"]["file"].endswith("04_fr_list.json"), (
            f"Unexpected source file: {data['source_files']['FR-CORPUS-001']['file']}"
        )

    def test_connected_entities_are_reachable(self, spec_corpus_copy):
        """BFS must discover cross-file linked entities (milestone, API, NFR, etc.)."""
        proc = _run(
            "context", "scope", str(spec_corpus_copy),
            "--entry", "FR-CORPUS-001",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        # All IDs across all buckets (spec_corpus uses uppercase so they land in "other")
        all_ids: set[str] = set()
        resolved = data.get("resolved_ids", {})
        for bucket_ids in resolved.values():
            all_ids.update(bucket_ids)

        expected_connected = {"MS-CORPUS-001", "API-CORPUS-001", "NFR-CORPUS-001"}
        missing = expected_connected - all_ids
        assert not missing, (
            f"Expected cross-file entities {expected_connected} to be reachable. "
            f"Missing: {missing}. All found: {all_ids}"
        )

    def test_entry_field_echoed(self, spec_corpus_copy):
        """The 'entry' field must echo the --entry argument."""
        proc = _run(
            "context", "scope", str(spec_corpus_copy),
            "--entry", "FR-CORPUS-001",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert data["entry"] == "FR-CORPUS-001"

    def test_found_entry_has_no_scope_warning(self, spec_corpus_copy):
        """An entry that exists in spec files must not produce a scope_warning."""
        proc = _run(
            "context", "scope", str(spec_corpus_copy),
            "--entry", "FR-CORPUS-001",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert "scope_warning" not in data, (
            f"Unexpected scope_warning: {data.get('scope_warning')}"
        )

    def test_missing_entry_produces_scope_warning(self, tmp_path):
        """An entry ID not present in any spec file must produce a scope_warning."""
        # Empty spec dir — no JSON files
        proc = _run(
            "context", "scope", str(tmp_path),
            "--entry", "fr-does-not-exist",
            "--repo-root", str(REPO_ROOT),
        )
        data = _parse_json(proc)
        assert "scope_warning" in data, (
            "Expected scope_warning for an unknown entry ID"
        )
        assert "fr-does-not-exist" in data["scope_warning"]


# ---------------------------------------------------------------------------
# seed-index
# ---------------------------------------------------------------------------

class TestSeedIndex:
    """Smoke tests for `specdev seed-index`.

    Fixture layout (standard flat layout):
        tmp_path/           ← host root; dirname(spec_dir) == host root
          spec/             ← spec_dir passed to commands
            common/
              seed_manifest.json
          docs/seed/        ← seeds[].path = "docs/seed/..." (relative to host root)
            seed_overview.md

    The git_root-implicit path (git_root=None → dirname(spec_dir)) is tested by
    all tests that omit --git-root.  The explicit nested-layout test at the
    bottom of this class passes --git-root explicitly and proves correctness when
    host_root != dirname(spec_dir).
    """

    def test_pass_status_on_valid_manifest(self, tmp_path):
        """seed-index must exit 0 and report PASS for a well-formed manifest."""
        spec_dir = tmp_path / "spec"
        common_dir = spec_dir / "common"
        seed_dir = tmp_path / "docs" / "seed"
        common_dir.mkdir(parents=True)
        seed_dir.mkdir(parents=True)
        seed_file = seed_dir / "seed_overview.md"
        seed_file.write_text("Seed content for indexing.\n", encoding="utf-8")

        manifest = {
            "$schema": "vc:seed-manifest",
            "seed_manifest_id": "seed-manifest-idx-smoke",
            "version": "0.1.0",
            "created_at": "2026-01-01T00:00:00Z",
            "last_updated": "2026-01-01T00:00:00Z",
            "global_seed_order": ["seed-overview"],
            "seeds": [
                {
                    "seed_id": "seed-overview",
                    "path": "docs/seed/seed_overview.md",
                    "description": "Index smoke test seed",
                    "required": True,
                    "source_type": "doc",
                }
            ],
            "step_requirements": {"00": ["seed-overview"]},
        }
        (common_dir / "seed_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        proc = _run(
            "seed-index", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
            "--json",
        )
        data = _parse_json(proc)
        assert data["status"] == "PASS", f"Expected PASS, got {data['status']!r}"

    def test_writes_seed_requirements_json(self, tmp_path):
        """seed-index must write seed_requirements.json into common/."""
        spec_dir = tmp_path / "spec"
        common_dir = spec_dir / "common"
        seed_dir = tmp_path / "docs" / "seed"
        common_dir.mkdir(parents=True)
        seed_dir.mkdir(parents=True)
        (seed_dir / "seed_overview.md").write_text("Content.", encoding="utf-8")

        manifest = {
            "$schema": "vc:seed-manifest",
            "seed_manifest_id": "seed-manifest-write-smoke",
            "version": "0.1.0",
            "created_at": "2026-01-01T00:00:00Z",
            "last_updated": "2026-01-01T00:00:00Z",
            "global_seed_order": ["seed-overview"],
            "seeds": [
                {
                    "seed_id": "seed-overview",
                    "path": "docs/seed/seed_overview.md",
                    "description": "Write test seed",
                    "required": True,
                    "source_type": "doc",
                }
            ],
            "step_requirements": {"00": ["seed-overview"]},
        }
        (common_dir / "seed_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        _run("seed-index", str(spec_dir), "--repo-root", str(REPO_ROOT), "--json")

        out_file = common_dir / "seed_requirements.json"
        assert out_file.exists(), "seed_requirements.json was not written into common/"

    def test_seed_hash_is_sha256_digest(self, tmp_path):
        """The source_hash for each indexed seed must start with 'sha256:'."""
        spec_dir = tmp_path / "spec"
        common_dir = spec_dir / "common"
        seed_dir = tmp_path / "docs" / "seed"
        common_dir.mkdir(parents=True)
        seed_dir.mkdir(parents=True)
        (seed_dir / "seed_overview.md").write_text("Hash test content.\n", encoding="utf-8")

        manifest = {
            "$schema": "vc:seed-manifest",
            "seed_manifest_id": "seed-manifest-hash-smoke",
            "version": "0.1.0",
            "created_at": "2026-01-01T00:00:00Z",
            "last_updated": "2026-01-01T00:00:00Z",
            "global_seed_order": ["seed-overview"],
            "seeds": [
                {
                    "seed_id": "seed-overview",
                    "path": "docs/seed/seed_overview.md",
                    "description": "Hash smoke test seed",
                    "required": True,
                    "source_type": "doc",
                }
            ],
            "step_requirements": {"00": ["seed-overview"]},
        }
        (common_dir / "seed_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        proc = _run(
            "seed-index", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
            "--json",
        )
        data = _parse_json(proc)
        seeds = data["result"]["seeds"]
        assert "seed-overview" in seeds, f"seed-overview not in result.seeds: {seeds}"
        source_hash = seeds["seed-overview"]["source_hash"]
        assert source_hash.startswith("sha256:"), (
            f"source_hash must be a sha256: digest, got {source_hash!r}"
        )
        # sha256 hex is 64 chars; 'sha256:' prefix makes total 71
        assert len(source_hash) == 71, (
            f"Expected sha256 hash of length 71, got {len(source_hash)}"
        )

    def test_fail_status_when_manifest_missing(self, tmp_path):
        """seed-index must report FAIL (exit 1) when seed_manifest.json is absent."""
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir(parents=True)
        proc = _run(
            "seed-index", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
            "--json",
        )
        # The CLI exits 1 on hard errors (E520), but still writes JSON to stdout.
        assert proc.returncode == 1, (
            f"Expected exit 1 when manifest is missing, got {proc.returncode}"
        )
        data = json.loads(proc.stdout)
        assert data["status"] == "FAIL", (
            f"Expected FAIL when manifest is missing, got {data['status']!r}"
        )
        assert data["error_count"] >= 1

    def test_nested_layout_seed_index_resolves_via_git_root(self, tmp_path):
        """Nested layout: spec_dir is NOT a direct child of the host root.

        host_root = tmp_path
        spec_dir  = tmp_path/src/project/spec   (deeply nested)
        seeds     = tmp_path/docs/seed/seed_overview.md
        seeds[].path = "docs/seed/seed_overview.md"  (relative to host root)

        Without --git-root the dirname heuristic gives tmp_path/src/project —
        wrong.  With --git-root tmp_path the path resolves correctly.
        This test proves the nested-layout bug is fixed.
        """
        host_root = tmp_path
        spec_dir = tmp_path / "src" / "project" / "spec"
        common_dir = spec_dir / "common"
        seed_file_dir = host_root / "docs" / "seed"
        common_dir.mkdir(parents=True)
        seed_file_dir.mkdir(parents=True)
        (seed_file_dir / "seed_overview.md").write_text(
            "Nested layout seed content.\n", encoding="utf-8"
        )

        manifest = {
            "$schema": "vc:seed-manifest",
            "seed_manifest_id": "seed-manifest-nested-idx",
            "version": "0.1.0",
            "created_at": "2026-01-01T00:00:00Z",
            "last_updated": "2026-01-01T00:00:00Z",
            "global_seed_order": ["seed-overview"],
            "seeds": [
                {
                    "seed_id": "seed-overview",
                    "path": "docs/seed/seed_overview.md",
                    "description": "Nested layout seed",
                    "required": True,
                    "source_type": "doc",
                }
            ],
            "step_requirements": {"00": ["seed-overview"]},
        }
        (common_dir / "seed_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        proc = _run(
            "seed-index", str(spec_dir),
            "--repo-root", str(REPO_ROOT),
            "--git-root", str(host_root),
            "--json",
        )
        data = _parse_json(proc)
        assert data["status"] == "PASS", (
            f"seed-index with --git-root should succeed for nested layout, got {data}"
        )
        seeds = data["result"]["seeds"]
        assert "seed-overview" in seeds, (
            f"seed-overview must be indexed in nested layout: {seeds}"
        )
        assert seeds["seed-overview"]["source_hash"].startswith("sha256:"), (
            "source_hash must be a sha256 digest for the nested-layout seed"
        )
