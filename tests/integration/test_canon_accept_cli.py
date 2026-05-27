"""Integration tests for the canon-accept CLI subcommand (FINDING-TEST-003/M7).

Invokes the ``specdev`` entry point via subprocess and verifies end-to-end
behaviour: manifest written on success, untouched on --dry-run.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_manifest(entries: list | None = None) -> dict:
    return {
        "$schema": "vc:core:canon",
        "registry_version": "1.0.0",
        "entries": entries or [],
        "aliases": [],
    }


def _make_spec_with_proposals(proposals: list) -> dict:
    return {
        "$schema": "vc:03-glossary",
        "id": "glossary-v1",
        "owner": "product",
        "created_at": "2026-03-23T00:00:00Z",
        "canonical_proposals": proposals,
    }


def _proposal(
    temp_id: str = "my-term",
    kind: str = "entity",
    proposed_label: str = "My Term",
    definition: str = "A well-defined term used in the system.",
    source_field: str = "terms[0].definition",
) -> dict:
    return {
        "temp_id": temp_id,
        "kind": kind,
        "proposed_label": proposed_label,
        "definition": definition,
        "source_field": source_field,
    }


def _run_canon_accept(
    spec_file: Path,
    repo_root: Path,
    namespace: str = "cn:project:",
    dry_run: bool = False,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke ``specdev canon-accept`` via subprocess."""
    cmd = [
        sys.executable, "-m", "specdev_tools.cli",
        "canon-accept",
        "--from", str(spec_file),
        "--repo-root", str(repo_root),
        "--namespace", namespace,
    ]
    if dry_run:
        cmd.append("--dry-run")
    if extra_args:
        cmd.extend(extra_args)

    toolkit_root = Path(__file__).resolve().parents[2]
    tools_dir = toolkit_root / "tools"

    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tools_dir) + os.pathsep + env.get("PYTHONPATH", "")

    return subprocess.run(cmd, capture_output=True, text=True, env=env)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_repo(tmp_path: Path):
    """Minimal repo layout: tmp_path/canon/manifest.json."""
    canon_dir = tmp_path / "canon"
    canon_dir.mkdir()
    manifest_path = canon_dir / "manifest.json"
    _write_json(manifest_path, _make_manifest())
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCanonAcceptCLIBasic:
    """CLI invocation succeeds and manifest is updated."""

    def test_exit_code_zero_on_valid_proposals(self, tmp_repo: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal()]))

        result = _run_canon_accept(spec_file, tmp_repo)

        assert result.returncode == 0, (
            f"Expected exit 0.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_manifest_updated_with_new_entry(self, tmp_repo: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal(
            temp_id="session-token",
            kind="entity",
            proposed_label="Session Token",
            definition="A short-lived token identifying an authenticated session.",
            source_field="terms[0].name",
        )]))

        result = _run_canon_accept(spec_file, tmp_repo)

        assert result.returncode == 0, result.stderr
        manifest = json.loads((tmp_repo / "canon" / "manifest.json").read_text(encoding="utf-8"))
        ids = [e["id"] for e in manifest["entries"]]
        assert "cn:project:entity:session-token" in ids, f"Got: {ids}"

    def test_output_reports_added_id(self, tmp_repo: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal(
            temp_id="user-role",
            kind="entity",
            proposed_label="User Role",
            definition="A named set of permissions assigned to a user account.",
        )]))

        result = _run_canon_accept(spec_file, tmp_repo)

        assert result.returncode == 0, result.stderr
        assert "cn:project:entity:user-role" in result.stdout, (
            f"Expected ID in output.\nstdout: {result.stdout}"
        )

    def test_multiple_proposals_all_added(self, tmp_repo: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([
            _proposal(temp_id="alpha", proposed_label="Alpha", definition="First entry."),
            _proposal(temp_id="beta",  proposed_label="Beta",  definition="Second entry."),
        ]))

        result = _run_canon_accept(spec_file, tmp_repo)

        assert result.returncode == 0, result.stderr
        manifest = json.loads((tmp_repo / "canon" / "manifest.json").read_text(encoding="utf-8"))
        ids = [e["id"] for e in manifest["entries"]]
        assert "cn:project:entity:alpha" in ids
        assert "cn:project:entity:beta" in ids

    def test_no_proposals_exits_zero(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Spec without canonical_proposals should exit 0 with 'no proposals' message."""
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, {
            "$schema": "vc:03-glossary",
            "id": "glossary-empty",
            "owner": "product",
            "created_at": "2026-03-23T00:00:00Z",
        })

        result = _run_canon_accept(spec_file, tmp_repo)

        assert result.returncode == 0, result.stderr
        assert "no proposals" in result.stdout.lower(), (
            f"Expected 'no proposals' in output.\nstdout: {result.stdout}"
        )


    def test_owner_flag_sets_entry_owner(self, tmp_repo: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal(
            temp_id="owned-term",
            kind="entity",
            proposed_label="Owned Term",
            definition="A term with an explicit owner assignment via CLI flag.",
        )]))

        result = _run_canon_accept(spec_file, tmp_repo, extra_args=["--owner", "product"])

        assert result.returncode == 0, result.stderr
        manifest = json.loads((tmp_repo / "canon" / "manifest.json").read_text(encoding="utf-8"))
        entry = next(e for e in manifest["entries"] if e["id"] == "cn:project:entity:owned-term")
        assert entry["owners"] == ["product"], f"Expected ['product'], got {entry['owners']}"


class TestCanonAcceptCLIDryRun:
    """--dry-run: output produced, manifest NOT modified."""

    def test_dry_run_exit_code_zero(self, tmp_repo: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal()]))

        result = _run_canon_accept(spec_file, tmp_repo, dry_run=True)

        assert result.returncode == 0, (
            f"Expected exit 0 for dry-run.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dry_run_manifest_not_modified(self, tmp_repo: Path, tmp_path: Path) -> None:
        manifest_path = tmp_repo / "canon" / "manifest.json"
        original_bytes = manifest_path.read_bytes()

        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal()]))

        result = _run_canon_accept(spec_file, tmp_repo, dry_run=True)

        assert result.returncode == 0, result.stderr
        assert manifest_path.read_bytes() == original_bytes, (
            "Manifest must not be modified during --dry-run"
        )

    def test_dry_run_output_mentions_would_add(self, tmp_repo: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal(
            temp_id="audit-log",
            kind="entity",
            proposed_label="Audit Log",
            definition="An immutable record of system events for compliance purposes.",
        )]))

        result = _run_canon_accept(spec_file, tmp_repo, dry_run=True)

        assert result.returncode == 0, result.stderr
        combined = result.stdout + result.stderr
        # CLI prints either "would add" or "dry-run" in its summary line
        assert "dry-run" in combined.lower() or "would add" in combined.lower(), (
            f"Expected dry-run indication in output.\nstdout: {result.stdout}"
        )

    def test_dry_run_id_appears_in_output(self, tmp_repo: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal(
            temp_id="payment-gateway",
            kind="entity",
            proposed_label="Payment Gateway",
            definition="An external service that processes payment transactions.",
        )]))

        result = _run_canon_accept(spec_file, tmp_repo, dry_run=True)

        assert result.returncode == 0, result.stderr
        assert "cn:project:entity:payment-gateway" in result.stdout, (
            f"Expected entry ID in dry-run output.\nstdout: {result.stdout}"
        )


class TestCanonAcceptCLIJsonOutput:
    """--json flag produces structured JSON output."""

    def test_json_flag_produces_valid_json(self, tmp_repo: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal()]))

        result = _run_canon_accept(spec_file, tmp_repo, extra_args=["--json"])

        assert result.returncode == 0, (
            f"Expected exit 0.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        payload = json.loads(result.stdout)
        assert "status" in payload or "command" in payload, (
            f"Expected JSON with status or command field.\nGot: {payload}"
        )

    def test_json_flag_dry_run_no_manifest_write(self, tmp_repo: Path, tmp_path: Path) -> None:
        manifest_path = tmp_repo / "canon" / "manifest.json"
        original_bytes = manifest_path.read_bytes()

        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal()]))

        result = _run_canon_accept(spec_file, tmp_repo, dry_run=True, extra_args=["--json"])

        assert result.returncode == 0, result.stderr
        assert manifest_path.read_bytes() == original_bytes


class TestCanonAcceptCLIErrorCases:
    """CLI exits non-zero for invalid inputs."""

    def test_missing_spec_file_exits_nonzero(self, tmp_repo: Path, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.json"

        result = _run_canon_accept(missing, tmp_repo)

        assert result.returncode != 0, (
            f"Expected non-zero exit for missing spec file.\nstdout: {result.stdout}"
        )

    def test_missing_manifest_exits_nonzero(self, tmp_path: Path) -> None:
        """Repo root without canon/manifest.json should produce an error."""
        empty_repo = tmp_path / "empty_repo"
        empty_repo.mkdir()

        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, _make_spec_with_proposals([_proposal()]))

        result = _run_canon_accept(spec_file, empty_repo)

        assert result.returncode != 0, (
            f"Expected non-zero exit for missing manifest.\nstdout: {result.stdout}"
        )
