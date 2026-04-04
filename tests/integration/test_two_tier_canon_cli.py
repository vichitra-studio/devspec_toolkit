"""Integration tests for two-tier canonical registry CLI commands.

Invokes ``specdev`` entry point via subprocess and verifies end-to-end
behaviour: project canon discovery, merged registry, namespace guard,
and backward compatibility when no project canon exists.

Uses the real toolkit as ``--repo-root`` so the schema registry and core
canon resolve correctly.  Only the host repo (project canon + spec files)
is synthesised in tmp_path.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOLKIT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = TOOLKIT_ROOT / "tools"


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _project_entry(kind: str, slug: str) -> dict:
    return {
        "id": f"cn:project:{kind}:{slug}",
        "kind": kind,
        "preferred_label": slug.replace("-", " "),
        "definition": f"Project {kind} {slug}",
        "version": "1.0.0",
        "status": "active",
        "owners": ["product"],
        "aliases": [],
        "lifecycle": {"introduced_at": "2024-01-01T00:00:00Z"},
    }


def _make_project_canon(host: Path, entries: list | None = None) -> Path:
    """Create a project canon dir at <host>/spec/canon/ with entries."""
    project_canon = host / "spec" / "canon"
    _write_json(project_canon / "manifest.json", {
        "$schema": "vc:core:canon",
        "registry_version": "1.0.0",
        "entries": entries if entries is not None else [_project_entry("entity", "post")],
        "aliases": [],
    })
    return project_canon


def _make_spec_with_canon_refs(spec_dir: Path, refs: list[str] | None = None) -> None:
    """Create a minimal glossary spec that references canonical IDs.

    This is intentionally minimal — it will fail full schema validation
    (missing id, owner, created_at) but passes enough for canonical-integrity
    and hallucination-lint to detect the canon refs.
    """
    if refs is None:
        refs = ["cn:project:entity:post"]
    canonical_refs = [
        {"id": r, "kind": r.split(":")[2], "version": "^1.0.0"} for r in refs
    ]
    _write_json(spec_dir / "03_glossary.json", {
        "$schema": "vc:03-glossary",
        "canonical_refs_used": refs,
        "terms": [{
            "term": "post",
            "definition": "A blog post entity for publishing content",
            "domain": "content",
            "canonical_refs": canonical_refs,
        }],
    })


def _run_specdev(*args: str) -> subprocess.CompletedProcess:
    """Invoke ``specdev_tools.cli`` via subprocess.  Does NOT assert exit code."""
    cmd = [sys.executable, "-m", "specdev_tools.cli", *args]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(TOOLS_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _run_specdev_ok(*args: str) -> subprocess.CompletedProcess:
    """Invoke ``specdev_tools.cli`` and assert exit 0."""
    result = _run_specdev(*args)
    assert result.returncode == 0, (
        f"Expected exit 0 for: {' '.join(args)}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSpecCheckDiscovery:
    """spec-check discovers and uses project canon when --git-root is provided."""

    def test_spec_check_discovers_project_canon(self, tmp_path: Path) -> None:
        host = tmp_path / "host"
        spec_dir = host / "spec"
        _make_project_canon(host)
        _make_spec_with_canon_refs(spec_dir)

        # spec-check may fail on schema validation (minimal spec), but
        # canonical checks should NOT flag project refs as unresolved
        result = _run_specdev(
            "spec-check", str(spec_dir),
            "--repo-root", str(TOOLKIT_ROOT),
            "--git-root", str(host),
            "--json",
        )
        payload = json.loads(result.stdout)
        checks = payload.get("checks", {})

        # canonical-lint should pass (project canon is valid)
        canon_lint = checks.get("canonical-lint", {})
        assert canon_lint.get("status") != "FAIL", (
            f"canonical-lint should not fail: {canon_lint}"
        )

        # If canonical-integrity ran, no E150 for project refs
        canon_int = checks.get("canonical-integrity", {})
        if canon_int.get("status") not in ("SKIP",):
            errors = payload.get("errors", [])
            e150_project = [
                e for e in errors
                if "E150" in str(e) and "cn:project:" in str(e)
            ]
            assert not e150_project, f"Unexpected E150 for project refs: {e150_project}"

    def test_spec_check_without_project_canon(self, tmp_path: Path) -> None:
        """spec-check without project canon works as before (single-tier)."""
        spec_dir = tmp_path / "spec"
        _make_spec_with_canon_refs(spec_dir, refs=["cn:core:stage:dev"])

        # No --git-root → single-tier
        result = _run_specdev(
            "spec-check", str(spec_dir),
            "--repo-root", str(TOOLKIT_ROOT),
            "--json",
        )
        payload = json.loads(result.stdout)
        # Command produced structured output (not a crash)
        assert "checks" in payload, f"Expected checks in output: {payload}"


class TestCanonAcceptCLITwoTier:
    """canon-accept CLI writes to project canon via --git-root."""

    def test_canon_accept_cli_writes_to_project(self, tmp_path: Path) -> None:
        host = tmp_path / "host"
        project_canon = _make_project_canon(host, entries=[])

        _write_json(host / "spec" / "03_glossary.json", {
            "$schema": "vc:03-glossary",
            "canonical_proposals": [{
                "temp_id": "newsletter",
                "kind": "capability",
                "proposed_label": "Newsletter",
                "definition": "Email newsletter subscription and delivery capability",
                "source_field": "terms",
            }],
        })

        _run_specdev_ok(
            "canon-accept",
            "--from", str(host / "spec" / "03_glossary.json"),
            "--repo-root", str(TOOLKIT_ROOT),
            "--git-root", str(host),
            "--namespace", "cn:project:",
        )

        # Verify written to project canon
        manifest = json.loads((project_canon / "manifest.json").read_text())
        ids = [e["id"] for e in manifest["entries"]]
        assert "cn:project:capability:newsletter" in ids

        # Core canon unchanged
        core_manifest = json.loads((TOOLKIT_ROOT / "canon" / "manifest.json").read_text())
        core_ids = [e["id"] for e in core_manifest["entries"]]
        assert "cn:project:capability:newsletter" not in core_ids


class TestCanonicalLintTwoTier:
    """canonical-lint validates both tiers when --git-root is provided."""

    def test_canonical_lint_both_tiers(self, tmp_path: Path) -> None:
        host = tmp_path / "host"
        _make_project_canon(host)

        result = _run_specdev_ok(
            "canonical-lint", "canon",
            "--repo-root", str(TOOLKIT_ROOT),
            "--git-root", str(host),
            "--json",
        )
        payload = json.loads(result.stdout)
        assert payload.get("error_count", 0) == 0, (
            f"Unexpected errors: {payload.get('errors', [])}"
        )

    def test_canonical_lint_single_tier_no_git_root(self, tmp_path: Path) -> None:
        """canonical-lint without --git-root keeps single-dir behavior."""
        result = _run_specdev_ok(
            "canonical-lint", "canon",
            "--repo-root", str(TOOLKIT_ROOT),
            "--json",
        )
        payload = json.loads(result.stdout)
        assert payload.get("error_count", 0) == 0


class TestCanonicalIntegrityTwoTier:
    """canonical-integrity resolves refs from both tiers."""

    def test_canonical_integrity_both_tiers(self, tmp_path: Path) -> None:
        host = tmp_path / "host"
        spec_dir = host / "spec"
        _make_project_canon(host)
        _make_spec_with_canon_refs(spec_dir)

        result = _run_specdev(
            "canonical-integrity", str(spec_dir),
            "--repo-root", str(TOOLKIT_ROOT),
            "--git-root", str(host),
            "--json",
        )
        payload = json.loads(result.stdout)
        # No E150 (unresolved canonical ref) for project entries
        e150 = [
            e for e in payload.get("errors", [])
            if "E150" in str(e) and "cn:project:" in str(e)
        ]
        assert not e150, f"Unexpected E150: {e150}"


class TestValidateSingleFileTwoTier:
    """validate (single-file) discovers project canon via --git-root / --spec-root."""

    def test_validate_single_file_discovers_project_canon_via_git_root(self, tmp_path: Path) -> None:
        host = tmp_path / "host"
        spec_dir = host / "spec"
        _make_project_canon(host)
        _make_spec_with_canon_refs(spec_dir)

        result = _run_specdev(
            "validate", str(spec_dir / "03_glossary.json"),
            "--repo-root", str(TOOLKIT_ROOT),
            "--git-root", str(host),
            "--json",
        )
        payload = json.loads(result.stdout)
        e110_project = [
            e for e in payload.get("errors", [])
            if "E110" in str(e) and "cn:project:" in str(e)
        ]
        assert not e110_project, f"E110 for project refs with --git-root: {e110_project}"

    def test_validate_single_file_discovers_project_canon_via_spec_root(self, tmp_path: Path) -> None:
        host = tmp_path / "host"
        spec_dir = host / "spec"
        _make_project_canon(host)
        _make_spec_with_canon_refs(spec_dir)

        result = _run_specdev(
            "validate", str(spec_dir / "03_glossary.json"),
            "--repo-root", str(TOOLKIT_ROOT),
            "--spec-root", str(spec_dir),
            "--json",
        )
        payload = json.loads(result.stdout)
        e110_project = [
            e for e in payload.get("errors", [])
            if "E110" in str(e) and "cn:project:" in str(e)
        ]
        assert not e110_project, f"E110 for project refs with --spec-root: {e110_project}"

    def test_validate_single_file_without_project_canon_is_unchanged(self, tmp_path: Path) -> None:
        """No --git-root, no --spec-root → single-tier; project refs produce E110."""
        spec_dir = tmp_path / "spec"
        _make_spec_with_canon_refs(spec_dir, refs=["cn:project:entity:post"])

        result = _run_specdev(
            "validate", str(spec_dir / "03_glossary.json"),
            "--repo-root", str(TOOLKIT_ROOT),
            "--json",
        )
        payload = json.loads(result.stdout)
        e110_project = [
            e for e in payload.get("errors", [])
            if "E110" in str(e) and "cn:project:" in str(e)
        ]
        assert e110_project, "Expected E110 for project refs when no canon is discoverable"


class TestValidateAllTwoTier:
    """validate-all discovers project canon via --git-root."""

    def test_validate_all_discovers_project_canon(self, tmp_path: Path) -> None:
        host = tmp_path / "host"
        spec_dir = host / "spec"
        _make_project_canon(host)
        _make_spec_with_canon_refs(spec_dir)

        # validate-all will report schema validation errors for the minimal
        # spec, but should NOT have E150 for project canon refs
        result = _run_specdev(
            "validate-all", str(spec_dir),
            "--repo-root", str(TOOLKIT_ROOT),
            "--git-root", str(host),
            "--json",
        )
        payload = json.loads(result.stdout)
        e150 = [
            e for e in payload.get("errors", [])
            if "E150" in str(e) and "cn:project:" in str(e)
        ]
        assert not e150, f"Unexpected E150 for project refs: {e150}"


class TestHallucinationLintTwoTier:
    """hallucination-lint with merged registry."""

    def test_hallucination_lint_both_tiers(self, tmp_path: Path) -> None:
        host = tmp_path / "host"
        spec_dir = host / "spec"
        _make_project_canon(host)
        _make_spec_with_canon_refs(spec_dir)

        result = _run_specdev(
            "hallucination-lint", str(spec_dir),
            "--repo-root", str(TOOLKIT_ROOT),
            "--git-root", str(host),
            "--json",
        )
        payload = json.loads(result.stdout)
        # No hallucination errors for valid project canon IDs
        hallucination_errors = [
            e for e in payload.get("errors", [])
            if any(code in str(e) for code in ("E301", "E302", "E303"))
        ]
        assert not hallucination_errors, (
            f"Unexpected hallucination errors: {hallucination_errors}"
        )
