"""Unit tests for specdev_tools.canonical.accept (canon-accept command)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from specdev_tools.canonical.accept import run_canon_accept


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_manifest(entries: list | None = None) -> dict:
    return {
        "$schema": "vc:core:canon",
        "registry_version": "1.0.0",
        "entries": entries or [],
        "aliases": [],
    }


def _make_spec(proposals: list | None = None) -> dict:
    spec: dict = {
        "$schema": "vc:03-glossary",
        "id": "glossary-v1",
        "owner": "product",
        "created_at": "2026-03-23T00:00:00Z",
    }
    if proposals is not None:
        spec["canonical_proposals"] = proposals
    return spec


def _proposal(
    temp_id: str = "my-term",
    kind: str = "entity",
    proposed_label: str = "My Term",
    definition: str = "A well-defined term.",
    source_field: str = "terms[0].definition",
    suggested_namespace: str | None = None,
) -> dict:
    p: dict = {
        "temp_id": temp_id,
        "kind": kind,
        "proposed_label": proposed_label,
        "definition": definition,
        "source_field": source_field,
    }
    if suggested_namespace is not None:
        p["suggested_namespace"] = suggested_namespace
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal repo layout: tmp_path/canon/manifest.json."""
    (tmp_path / "canon").mkdir()
    return tmp_path


@pytest.fixture()
def manifest_path(tmp_repo: Path) -> Path:
    manifest = _make_manifest()
    path = tmp_repo / "canon" / "manifest.json"
    _write_json(path, manifest)
    return path


@pytest.fixture()
def spec_path(tmp_path: Path) -> Path:
    return tmp_path / "spec" / "03_glossary.json"


# ---------------------------------------------------------------------------
# Test 1 — Basic accept flow: proposals are added to manifest
# ---------------------------------------------------------------------------

class TestBasicAccept:
    def test_single_proposal_added(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        _ = manifest_path
        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["added"] == ["cn:project:entity:my-term"]
        assert result["skipped"] == []

    def test_manifest_updated_on_disk(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = [e["id"] for e in updated["entries"]]
        assert "cn:project:entity:my-term" in ids

    def test_entry_fields_are_correct(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec([_proposal(
            temp_id="auth-token",
            kind="entity",
            proposed_label="Auth Token",
            definition="A token used for authentication.",
            source_field="terms[3].name",
        )]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(e for e in updated["entries"] if e["id"] == "cn:project:entity:auth-token")
        assert entry["kind"] == "entity"
        assert entry["preferred_label"] == "Auth Token"
        assert entry["definition"] == "A token used for authentication."
        assert entry["version"] == "1.0.0"
        assert entry["status"] == "active"
        assert "introduced_at" in entry["lifecycle"]
        assert entry["lifecycle"]["source_field"] == "terms[3].name"
        # accepted_from may be relative (when spec is inside repo_root) or absolute;
        # either way the spec filename must appear in it.
        assert "03_glossary.json" in entry["lifecycle"]["accepted_from"]

    def test_multiple_proposals_added(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        _ = manifest_path
        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec([
            _proposal(temp_id="term-a", kind="entity", proposed_label="Term A", definition="Def A."),
            _proposal(temp_id="term-b", kind="entity", proposed_label="Term B", definition="Def B."),
        ]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert sorted(result["added"]) == ["cn:project:entity:term-a", "cn:project:entity:term-b"]
        assert result["skipped"] == []


# ---------------------------------------------------------------------------
# Test 2 — Dry run: nothing written
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_returns_would_add(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        _ = manifest_path
        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
            dry_run=True,
        )

        assert result["error"] is None
        assert result["added"] == ["cn:project:entity:my-term"]

    def test_dry_run_does_not_write(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        original_content = manifest_path.read_text(encoding="utf-8")
        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
            dry_run=True,
        )

        assert manifest_path.read_text(encoding="utf-8") == original_content


# ---------------------------------------------------------------------------
# Test 3 — Duplicate handling: existing IDs skipped, new IDs added
# ---------------------------------------------------------------------------

class TestDuplicateHandling:
    def test_existing_id_skipped(self, tmp_repo: Path, tmp_path: Path) -> None:
        existing_entry = {
            "id": "cn:project:entity:my-term",
            "kind": "entity",
            "preferred_label": "My Term",
            "definition": "Already here.",
            "version": "1.0.0",
            "status": "active",
            "owners": ["spec-platform"],
            "aliases": [],
            "lifecycle": {"introduced_at": "2026-03-01T00:00:00Z"},
        }
        manifest_path = tmp_repo / "canon" / "manifest.json"
        _write_json(manifest_path, _make_manifest([existing_entry]))

        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["added"] == []
        assert result["skipped"] == ["cn:project:entity:my-term"]

    def test_mixed_new_and_duplicate(self, tmp_repo: Path, tmp_path: Path) -> None:
        existing_entry = {
            "id": "cn:project:entity:term-a",
            "kind": "entity",
            "preferred_label": "Term A",
            "definition": "Already here.",
            "version": "1.0.0",
            "status": "active",
            "owners": ["spec-platform"],
            "aliases": [],
            "lifecycle": {"introduced_at": "2026-03-01T00:00:00Z"},
        }
        manifest_path = tmp_repo / "canon" / "manifest.json"
        _write_json(manifest_path, _make_manifest([existing_entry]))

        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec([
            _proposal(temp_id="term-a", kind="entity", proposed_label="Term A", definition="Old."),
            _proposal(temp_id="term-b", kind="entity", proposed_label="Term B", definition="New one."),
        ]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["added"] == ["cn:project:entity:term-b"]
        assert result["skipped"] == ["cn:project:entity:term-a"]

        # Verify only one new entry added (not duplicated)
        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = [e["id"] for e in updated["entries"]]
        assert ids.count("cn:project:entity:term-a") == 1
        assert "cn:project:entity:term-b" in ids

    def test_intra_batch_duplicate_proposals(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Two proposals with same temp_id+kind in one call: first accepted, second skipped."""
        manifest_path = tmp_repo / "canon" / "manifest.json"
        _write_json(manifest_path, _make_manifest())

        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec([
            _proposal(temp_id="my-term", kind="entity", proposed_label="My Term", definition="First."),
            _proposal(temp_id="my-term", kind="entity", proposed_label="My Term", definition="Duplicate."),
        ]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert len(result["added"]) == 1
        assert len(result["skipped"]) == 1
        assert result["skipped"][0] == result["added"][0]  # same ID skipped

        # Verify only one entry written to manifest
        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = [e["id"] for e in updated["entries"]]
        assert ids.count("cn:project:entity:my-term") == 1


# ---------------------------------------------------------------------------
# Test 4 — Empty proposals: gracefully handles spec with no canonical_proposals
# ---------------------------------------------------------------------------

class TestEmptyProposals:
    def test_no_proposals_key(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        """Spec file with no canonical_proposals key at all."""
        _ = manifest_path
        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec(proposals=None))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["added"] == []
        assert result["skipped"] == []

    def test_empty_proposals_array(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        _ = manifest_path
        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec(proposals=[]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["added"] == []
        assert result["skipped"] == []

    def test_manifest_unchanged_when_no_proposals(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        original = manifest_path.read_text(encoding="utf-8")
        spec_file = tmp_path / "03_glossary.json"
        _write_json(spec_file, _make_spec(proposals=[]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert manifest_path.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# Test 5 — Missing spec file: raises appropriate error
# ---------------------------------------------------------------------------

class TestMissingSpecFile:
    def test_missing_spec_returns_error(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        _ = manifest_path
        missing = str(tmp_path / "does_not_exist.json")

        result = run_canon_accept(
            spec_file=missing,
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "not found" in result["error"]
        assert result["added"] == []
        assert result["skipped"] == []

    def test_missing_manifest_returns_error(self, tmp_path: Path) -> None:
        # repo without canon/manifest.json
        (tmp_path / "canon").mkdir()
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_path),
        )

        assert result["error"] is not None
        assert "manifest" in result["error"]
        assert result["added"] == []


# ---------------------------------------------------------------------------
# Test 6 — Namespace prefix applied correctly
# ---------------------------------------------------------------------------

class TestNamespacePrefix:
    def test_default_project_namespace(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal(temp_id="widget", kind="entity")]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["added"] == ["cn:project:entity:widget"]

    def test_custom_namespace(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal(temp_id="widget", kind="unit")]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:starter:",
            repo_root=str(tmp_repo),
        )

        assert result["added"] == ["cn:starter:unit:widget"]

    def test_namespace_without_trailing_colon_is_normalised(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal(temp_id="gadget", kind="role")]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project",  # no trailing colon
            repo_root=str(tmp_repo),
        )

        # Should still produce a valid ID
        assert result["added"] == ["cn:project:role:gadget"]

    def test_suggested_namespace_not_stored_in_entry(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """suggested_namespace must NOT be copied to the manifest entry (finding 3-004).

        The namespace is already captured in the ID prefix; storing it again as a
        top-level field is not part of the canon entry schema.
        """
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([
            _proposal(
                temp_id="my-widget",
                kind="entity",
                suggested_namespace="project.widgets",
            )
        ]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(e for e in updated["entries"] if e["id"] == "cn:project:entity:my-widget")
        assert "suggested_namespace" not in entry


# ---------------------------------------------------------------------------
# Test 7 — accepted_from stores a path relative to repo_root (finding 3-001)
# ---------------------------------------------------------------------------

class TestAcceptedFromRelativePath:
    def test_accepted_from_is_relative_when_spec_inside_repo_root(self, tmp_path: Path) -> None:
        """When spec file is inside repo_root, accepted_from must be a relative path."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "canon").mkdir()
        manifest_path = repo / "canon" / "manifest.json"
        _write_json(manifest_path, _make_manifest())

        spec_dir = repo / "spec"
        spec_dir.mkdir()
        spec_file = spec_dir / "03_glossary.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(repo),
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(e for e in updated["entries"] if e["id"] == "cn:project:entity:my-term")
        accepted_from = entry["lifecycle"]["accepted_from"]

        # Must be a relative path — must not start with /
        assert not accepted_from.startswith("/"), f"Expected relative path, got: {accepted_from}"
        # Must contain the filename
        assert "03_glossary.json" in accepted_from

    def test_accepted_from_falls_back_to_absolute_when_outside_repo_root(
        self, tmp_path: Path
    ) -> None:
        """When spec file is outside repo_root, accepted_from falls back to absolute path."""
        # Create two sibling dirs so spec_file is genuinely outside repo_root
        repo = tmp_path / "the_repo"
        repo.mkdir()
        (repo / "canon").mkdir()
        manifest_path = repo / "canon" / "manifest.json"
        _write_json(manifest_path, _make_manifest())

        external_dir = tmp_path / "external"
        external_dir.mkdir()
        spec_file = external_dir / "external_spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(repo),
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(e for e in updated["entries"] if e["id"] == "cn:project:entity:my-term")
        accepted_from = entry["lifecycle"]["accepted_from"]

        # The absolute path of the spec file must appear in accepted_from
        assert str(spec_file) in accepted_from


# ---------------------------------------------------------------------------
# Test 8 — Malformed proposals: warned and counted (finding 3-002)
# ---------------------------------------------------------------------------

class TestMalformedProposals:
    def test_malformed_proposal_is_counted(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        """Proposals missing required fields are counted in the malformed key."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        # One valid + one missing 'definition'
        bad = {"temp_id": "bad-term", "kind": "entity", "proposed_label": "Bad"}
        _write_json(spec_file, _make_spec([_proposal(), bad]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["malformed"] == 1
        assert result["added"] == ["cn:project:entity:my-term"]

    def test_non_dict_proposal_is_counted(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        """Non-object items in canonical_proposals are counted as malformed."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec(["not-a-dict", _proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["malformed"] == 1
        assert result["added"] == ["cn:project:entity:my-term"]

    def test_malformed_key_present_on_success(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        """The malformed key is always present in the result dict, even when zero."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert "malformed" in result
        assert result["malformed"] == 0

    def test_malformed_warned_via_logger(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A warning is emitted for each skipped malformed proposal."""
        _ = manifest_path
        import logging

        spec_file = tmp_path / "spec.json"
        bad = {"temp_id": "x", "kind": "entity"}  # missing proposed_label + definition
        _write_json(spec_file, _make_spec([bad]))

        with caplog.at_level(logging.WARNING, logger="specdev_tools.canonical.accept"):
            run_canon_accept(
                spec_file=str(spec_file),
                namespace="cn:project:",
                repo_root=str(tmp_repo),
            )

        assert any("malformed" in r.message.lower() or "missing" in r.message.lower() for r in caplog.records)

    def test_proposal_missing_temp_id_skipped(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """Proposal with missing temp_id is skipped (can't build a canon ID)."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        no_id = {
            "kind": "entity",
            "proposed_label": "Nameless",
            "definition": "Has no temp_id field.",
        }
        _write_json(spec_file, _make_spec([no_id]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["added"] == []

    def test_canonical_proposals_wrong_type_returns_error(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """canonical_proposals set to a string (not a list) must return an error, not crash."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        bad_spec = _make_spec(proposals=None)
        bad_spec["canonical_proposals"] = "not-a-list"
        _write_json(spec_file, bad_spec)

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "canonical_proposals" in result["error"]
        assert result["added"] == []

    def test_canonical_proposals_int_type_returns_error(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """canonical_proposals set to an int must return an error, not raise AttributeError."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        bad_spec = _make_spec(proposals=None)
        bad_spec["canonical_proposals"] = 99
        _write_json(spec_file, bad_spec)

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert result["added"] == []


# ---------------------------------------------------------------------------
# Test 9 — owners field (finding 3-003)
# ---------------------------------------------------------------------------

class TestOwnersField:
    def test_default_owners_is_empty_list(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        """Without --owner, new entries get an empty owners list."""
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(e for e in updated["entries"] if e["id"] == "cn:project:entity:my-term")
        assert entry["owners"] == []

    def test_owner_argument_sets_owners(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        """Passing owner='spec-platform' sets owners to ['spec-platform']."""
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
            owner="spec-platform",
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(e for e in updated["entries"] if e["id"] == "cn:project:entity:my-term")
        assert entry["owners"] == ["spec-platform"]


# ---------------------------------------------------------------------------
# Test 10 — Malformed input files: structural errors in spec/manifest files
# ---------------------------------------------------------------------------

class TestMalformedInputFiles:
    def test_non_dict_spec_root_returns_error(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        """Spec file whose root is a JSON array (not object) must return an error."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, [1, 2, 3])

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "must be an object" in result["error"]
        assert result["added"] == []
        assert result["skipped"] == []

    def test_non_dict_manifest_root_returns_error(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Manifest whose root is a JSON array (not object) must return an error."""
        manifest_path = tmp_repo / "canon" / "manifest.json"
        _write_json(manifest_path, [])

        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "manifest root must be an object" in result["error"]
        assert result["added"] == []

    def test_non_list_manifest_entries_returns_error(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Manifest with entries set to a non-list value must return an error."""
        manifest_path = tmp_repo / "canon" / "manifest.json"
        _write_json(manifest_path, {"entries": "not-a-list"})

        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "manifest.entries must be an array" in result["error"]
        assert result["added"] == []

    def test_invalid_json_in_spec_file_returns_error(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        """Spec file containing unparseable JSON must return a read error."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        spec_file.write_text("{broken", encoding="utf-8")

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "failed to read spec file" in result["error"]
        assert result["added"] == []
        assert result["skipped"] == []

    def test_invalid_json_in_manifest_returns_error(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Manifest file containing unparseable JSON must return a read error."""
        manifest_path = tmp_repo / "canon" / "manifest.json"
        manifest_path.write_text("not json", encoding="utf-8")

        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "failed to read manifest" in result["error"]
        assert result["added"] == []


class TestOwnersListIndependence:
    def test_owners_list_is_independent_per_entry(self, tmp_repo: Path, manifest_path: Path, tmp_path: Path) -> None:
        """Each entry gets its own owners list — mutation of one must not affect others."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([
            _proposal(temp_id="alpha", kind="entity", proposed_label="Alpha", definition="First entry for mutation test.", source_field="terms[0]"),
            _proposal(temp_id="beta", kind="entity", proposed_label="Beta", definition="Second entry for mutation test.", source_field="terms[1]"),
        ]))
        result = run_canon_accept(str(spec_file), "cn:project:", str(tmp_repo), owner="team-a")
        assert result["error"] is None
        assert len(result["added"]) == 2

        manifest = json.loads((tmp_repo / "canon" / "manifest.json").read_text(encoding="utf-8"))
        entries = [e for e in manifest["entries"] if e["id"] in result["added"]]
        assert len(entries) == 2

        # Mutate one entry's owners list and verify the other is unaffected
        entries[0]["owners"].append("intruder")
        assert "intruder" not in entries[1]["owners"], "owners lists must be independent copies, not shared references"


class TestInvalidNamespace:
    """TEST-007: Namespace validation edge cases.

    The current implementation normalises any namespace by appending ':' if
    missing and does not validate the structure further.  A completely invalid
    namespace (empty string, no colon) will produce structurally odd IDs but
    should not crash.  These tests document the current behaviour and serve as
    a regression baseline — if a future change adds proper namespace
    validation, these tests will need to be updated to assert the ValueError
    or error-result path.
    """

    def test_empty_namespace_produces_error_or_odd_id(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """Empty string namespace should not crash the function.

        Current behaviour: normalises to ':' and produces ':entity:my-term'.
        Acceptable future behaviour: returns error with 'namespace' in message.
        """
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="",
            repo_root=str(tmp_repo),
        )

        # Must not raise — either an error result or an odd-but-valid ID.
        assert isinstance(result, dict)
        assert "error" in result
        assert "added" in result

    def test_namespace_without_colon_is_normalised(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """Namespace without any colon gets a trailing colon appended.

        This is a regression test for the existing normalisation logic.
        The resulting ID will be 'badnamespace:entity:my-term'.
        """
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal(temp_id="my-term", kind="entity")]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="badnamespace",
            repo_root=str(tmp_repo),
        )

        # Function must not crash; the namespace 'badnamespace' does not start with 'cn:'
        # so it is rejected early with a descriptive error before any proposals are processed.
        assert isinstance(result, dict)
        assert result["error"] is not None
        assert "invalid namespace" in result["error"]
        assert result["added"] == []
        assert result["malformed"] == 0

    def test_namespace_with_colon_but_wrong_prefix_is_rejected(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """A namespace like 'badprefix:' that has a colon but does not start
        with 'cn:' must be rejected with a descriptive error (L15)."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal(temp_id="my-term", kind="entity")]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="badprefix:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "invalid namespace" in result["error"]
        assert result["added"] == []
        assert result["skipped"] == []

    def test_empty_segment_namespace_rejected(self, tmp_repo: Path, tmp_path: Path) -> None:
        """'cn:' alone (empty second segment) should be rejected as invalid namespace."""
        (tmp_repo / "canon" / "manifest.json").write_text(
            json.dumps(_make_manifest()), encoding="utf-8"
        )
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps({
            "canonical_proposals": [{
                "temp_id": "my-term", "kind": "term",
                "proposed_label": "My Term",
                "definition": "A test definition.",
                "source_field": "terms[0].term",
            }]
        }), encoding="utf-8")
        result = run_canon_accept(str(spec_file), "cn:", str(tmp_repo))
        assert result["error"] is not None
        assert "non-empty" in result["error"] or "invalid" in result["error"].lower()


class TestIdempotentWrite:
    """TEST-007: Running accept twice with identical proposals must not duplicate entries."""

    def test_second_run_skips_all_already_added(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """All proposals from the first run appear in skipped on the second run."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([
            _proposal(temp_id="term-x", kind="entity", proposed_label="Term X", definition="X."),
            _proposal(temp_id="term-y", kind="entity", proposed_label="Term Y", definition="Y."),
        ]))

        first = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )
        assert first["error"] is None
        assert sorted(first["added"]) == ["cn:project:entity:term-x", "cn:project:entity:term-y"]

        second = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )
        assert second["error"] is None
        assert second["added"] == []
        assert sorted(second["skipped"]) == [
            "cn:project:entity:term-x",
            "cn:project:entity:term-y",
        ]

    def test_no_duplicate_entries_in_manifest_after_two_runs(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """Manifest must contain exactly one entry per proposal even after two runs."""
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([
            _proposal(temp_id="dedup-term", kind="entity", proposed_label="Dedup", definition="D."),
        ]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )
        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = [e["id"] for e in updated["entries"]]
        assert ids.count("cn:project:entity:dedup-term") == 1


class TestCLISubcommandWiring:
    """TEST-007: Verify that the canon-accept subcommand is registered in the CLI."""

    def test_canon_accept_help_exits_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invoking the CLI with ``canon-accept --help`` must exit 0, not raise an unknown command error.

        argparse raises SystemExit(0) on --help, which we catch here.
        An unknown subcommand would either raise SystemExit(2) or an
        AttributeError / KeyError before reaching --help handling.
        """
        import specdev_tools.cli as cli_module

        monkeypatch.setattr(sys, "argv", ["specdev-tools", "canon-accept", "--help"])

        with pytest.raises(SystemExit) as exc_info:
            cli_module.main()

        # argparse exits with code 0 for --help
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# TEST-008 — Kind field validation: unknown kind
# ---------------------------------------------------------------------------

class TestUnknownKind:
    """TEST-008: Behaviour when a proposal uses a kind not in the known kinds registry.

    Expected behaviour: the toolkit treats kinds as extensible, so an unknown
    kind is ACCEPTED (not rejected) provided it matches the canonicalRef pattern
    (kind segment must use underscores, not hyphens: [a-z_]+).  The entry should
    land in the manifest with the supplied kind value verbatim.  Schema validation
    (a separate tool) is responsible for enforcing kind constraints — accept.py is
    intentionally permissive to avoid blocking novel kind introductions.

    Kinds using hyphens (e.g. 'invented-kind') are rejected at ID-generation time
    because they produce IDs that violate the canonicalRef regex pattern.
    """

    def test_unknown_kind_is_accepted(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """A proposal with an invented underscore kind should be accepted and written to the manifest."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([
            _proposal(
                temp_id="new-concept",
                kind="invented_kind",
                proposed_label="New Concept",
                definition="A concept from a future extension.",
            )
        ]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["added"] == ["cn:project:invented_kind:new-concept"]
        assert result["skipped"] == []

    def test_unknown_kind_entry_written_verbatim(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """The manifest entry must store the unknown kind value without modification."""
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([
            _proposal(
                temp_id="widget-v2",
                kind="invented_kind",
                proposed_label="Widget V2",
                definition="An extended widget type.",
            )
        ]))

        run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(e for e in updated["entries"] if e["id"] == "cn:project:invented_kind:widget-v2")
        assert entry["kind"] == "invented_kind"

    def test_hyphenated_kind_is_rejected(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """A proposal whose kind contains a hyphen generates an invalid canonicalRef ID and is rejected."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([
            _proposal(
                temp_id="new-concept",
                kind="invented-kind",
                proposed_label="New Concept",
                definition="A concept from a future extension.",
            )
        ]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["added"] == []
        assert result["malformed"] == 1


# ---------------------------------------------------------------------------
# TEST-NEW-003 — CLI end-to-end: plain-text malformed count + JSON output
# ---------------------------------------------------------------------------

class TestCLIEndToEnd:
    """NEW-003: Verify the CLI end-to-end output for canon-accept.

    These tests invoke ``main()`` directly (injecting args via monkeypatch) and
    capture stdout/stderr to assert the plain-text and JSON output paths both
    produce the correct content, including the malformed count.
    """

    # ------------------------------------------------------------------
    # Helpers shared by all three tests
    # ------------------------------------------------------------------

    @staticmethod
    def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
        """Return (repo_root, manifest_path) with an empty manifest on disk."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "canon").mkdir()
        manifest_path = repo / "canon" / "manifest.json"
        _write_json(manifest_path, _make_manifest())
        return repo, manifest_path

    # ------------------------------------------------------------------
    # Test 1: plain-text output shows the malformed count
    # ------------------------------------------------------------------

    def test_cli_plain_text_malformed_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Plain-text mode must print the malformed count when proposals are skipped.

        Finding NEW-003: lines ~1241-1242 in cli.py print the malformed count
        but were never exercised end-to-end.
        """
        import specdev_tools.cli as cli_module

        repo, _ = self._make_repo(tmp_path)
        spec_file = tmp_path / "spec.json"
        bad = {"temp_id": "bad-term", "kind": "entity", "proposed_label": "Bad"}  # missing definition
        _write_json(spec_file, _make_spec([bad]))

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "specdev",
                "canon-accept",
                "--from", str(spec_file),
                "--namespace", "cn:project:",
                "--repo-root", str(repo),
            ],
        )

        # plain-text success path does not call sys.exit — just returns
        cli_module.main()

        captured = capsys.readouterr()
        assert "malformed" in captured.out
        assert "1" in captured.out

    # ------------------------------------------------------------------
    # Test 2: --json output contains the malformed key
    # ------------------------------------------------------------------

    def test_cli_json_output_contains_malformed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """JSON output must include a ``malformed`` key with the correct count."""
        import specdev_tools.cli as cli_module

        repo, _ = self._make_repo(tmp_path)
        spec_file = tmp_path / "spec.json"
        bad1 = {"temp_id": "bad-a", "kind": "entity", "proposed_label": "Bad A"}  # missing definition
        bad2 = {"kind": "entity", "proposed_label": "Bad B", "definition": "No temp_id."}  # missing temp_id
        _write_json(spec_file, _make_spec([bad1, bad2]))

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "specdev",
                "canon-accept",
                "--from", str(spec_file),
                "--namespace", "cn:project:",
                "--repo-root", str(repo),
                "--json",
            ],
        )

        # JSON path always calls sys.exit(0) on success
        with pytest.raises(SystemExit) as exc_info:
            cli_module.main()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "malformed" in data
        # bad1 missing definition → malformed; bad2 missing temp_id may be
        # counted as malformed or treated as a separate skip — either way the
        # key must be present and >= 1 (at least bad1 is definitely malformed).
        assert data["malformed"] >= 1

    # ------------------------------------------------------------------
    # Test 3: plain-text success summary shows "added" count
    # ------------------------------------------------------------------

    def test_cli_plain_text_success_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Plain-text mode must print the summary line showing the number added."""
        import specdev_tools.cli as cli_module

        repo, _ = self._make_repo(tmp_path)
        spec_file = tmp_path / "spec.json"
        _write_json(
            spec_file,
            _make_spec([
                _proposal(temp_id="alpha", kind="entity", proposed_label="Alpha", definition="First term."),
                _proposal(temp_id="beta", kind="entity", proposed_label="Beta", definition="Second term."),
            ]),
        )

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "specdev",
                "canon-accept",
                "--from", str(spec_file),
                "--namespace", "cn:project:",
                "--repo-root", str(repo),
            ],
        )

        # plain-text success path does not call sys.exit — just returns
        cli_module.main()

        captured = capsys.readouterr()
        # The summary line must contain "added" and show count >= 1
        assert "added" in captured.out
        # Each accepted entry is also prefixed with "  + added: ..."
        assert "alpha" in captured.out or "2 added" in captured.out

# ---------------------------------------------------------------------------
# TEST NEW-002 — Write-failure path exposes attempted `added` list
# ---------------------------------------------------------------------------

class TestWriteFailureAdded:
    """NEW-002: When the manifest write fails, the error result must include the
    in-memory `added` list (with `write_failed: True`) so callers can distinguish
    'nothing attempted' from 'attempted but not persisted'.
    """

    def test_write_failure_returns_attempted_added_and_write_failed_flag(
        self, tmp_repo: Path, tmp_path: Path
    ) -> None:
        """Simulate an OSError on manifest write and assert `added` is non-empty
        and `write_failed` is True in the returned dict.

        accept.py uses Path.open(), so we patch pathlib.Path.open to intercept
        the write call while allowing all read calls to pass through.
        """
        import unittest.mock as mock
        from pathlib import Path as _Path

        manifest_path = tmp_repo / "canon" / "manifest.json"
        _write_json(manifest_path, _make_manifest())

        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        real_path_open = _Path.open

        def patched_path_open(self_path, mode="r", **kwargs):
            if "w" in mode and "manifest.json" in str(self_path):
                raise OSError("simulated write failure")
            return real_path_open(self_path, mode, **kwargs)

        with mock.patch.object(_Path, "open", patched_path_open):
            result = run_canon_accept(
                spec_file=str(spec_file),
                namespace="cn:project:",
                repo_root=str(tmp_repo),
            )

        assert result["error"] is not None
        assert "write" in result["error"].lower() or "manifest" in result["error"].lower()
        # The attempted IDs must be surfaced, not hidden behind an empty list.
        assert result["added"] == ["cn:project:entity:my-term"], (
            "added should contain the IDs that were queued but not persisted"
        )
        assert result.get("write_failed") is True

    def test_write_failure_result_still_contains_skipped_and_malformed(
        self, tmp_repo: Path, tmp_path: Path
    ) -> None:
        """skipped and malformed counts must be present even when a write failure occurs."""
        import unittest.mock as mock
        from pathlib import Path as _Path

        existing_entry = {
            "id": "cn:project:entity:existing",
            "kind": "entity",
            "preferred_label": "Existing",
            "definition": "Already here.",
            "version": "1.0.0",
            "status": "active",
            "owners": [],
            "aliases": [],
            "lifecycle": {"introduced_at": "2026-03-01T00:00:00Z"},
        }
        manifest_path = tmp_repo / "canon" / "manifest.json"
        _write_json(manifest_path, _make_manifest([existing_entry]))

        spec_file = tmp_path / "spec.json"
        bad = {"temp_id": "bad", "kind": "entity", "proposed_label": "Bad"}  # missing definition + source_field
        _write_json(spec_file, _make_spec([
            _proposal(),  # new — will be in `added`
            {"temp_id": "existing", "kind": "entity", "proposed_label": "E",
             "definition": "D.", "source_field": "f"},  # dup — skipped
            bad,  # malformed
        ]))

        real_path_open = _Path.open

        def patched_path_open(self_path, mode="r", **kwargs):
            if "w" in mode and "manifest.json" in str(self_path):
                raise OSError("simulated write failure")
            return real_path_open(self_path, mode, **kwargs)

        with mock.patch.object(_Path, "open", patched_path_open):
            result = run_canon_accept(
                spec_file=str(spec_file),
                namespace="cn:project:",
                repo_root=str(tmp_repo),
            )

        assert result["error"] is not None
        assert result["added"] == ["cn:project:entity:my-term"]
        assert result["skipped"] == ["cn:project:entity:existing"]
        assert result["malformed"] == 1
        assert result.get("write_failed") is True


# ---------------------------------------------------------------------------
# TEST NEW-004 — source_field is a required field for proposals
# ---------------------------------------------------------------------------

class TestSourceFieldRequired:
    """NEW-004: A proposal without `source_field` must be counted as malformed,
    not silently accepted.  The canonicalProposal schema requires source_field.
    """

    def test_proposal_missing_source_field_counted_as_malformed(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """A proposal with all other required fields but no source_field is malformed."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        no_source = {
            "temp_id": "no-source",
            "kind": "entity",
            "proposed_label": "No Source",
            "definition": "A term with no source_field.",
        }
        _write_json(spec_file, _make_spec([no_source]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["malformed"] == 1, "proposal missing source_field must be counted as malformed"
        assert result["added"] == []

    def test_proposal_with_empty_source_field_counted_as_malformed(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """A proposal with source_field='' (empty string) is also malformed."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        empty_source = {
            "temp_id": "empty-source",
            "kind": "entity",
            "proposed_label": "Empty Source",
            "definition": "A term with empty source_field.",
            "source_field": "",
        }
        _write_json(spec_file, _make_spec([empty_source]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["malformed"] == 1, "proposal with empty source_field must be counted as malformed"
        assert result["added"] == []

    def test_proposal_with_valid_source_field_is_accepted(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """A proposal that includes source_field is accepted normally (regression guard)."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal(source_field="terms[0].definition")]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["malformed"] == 0
        assert result["added"] == ["cn:project:entity:my-term"]

    def test_missing_source_field_warning_logged(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A warning must be emitted when source_field is absent."""
        _ = manifest_path
        import logging

        spec_file = tmp_path / "spec.json"
        no_source = {
            "temp_id": "warn-source",
            "kind": "entity",
            "proposed_label": "Warn Source",
            "definition": "Missing source_field.",
        }
        _write_json(spec_file, _make_spec([no_source]))

        with caplog.at_level(logging.WARNING, logger="specdev_tools.canonical.accept"):
            run_canon_accept(
                spec_file=str(spec_file),
                namespace="cn:project:",
                repo_root=str(tmp_repo),
            )

        assert any(
            "source_field" in r.message or "missing" in r.message.lower()
            for r in caplog.records
        ), "Expected a warning mentioning source_field or missing fields"


# ---------------------------------------------------------------------------
# Test — Invalid namespace rejection (non-cn: prefix)
# ---------------------------------------------------------------------------

class TestInvalidNamespaceRejection:
    """Namespace that does not start with 'cn:' must be rejected with an error."""

    def test_namespace_not_starting_with_cn_returns_error(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """A namespace like 'not-cn:project:' must be rejected because it
        does not start with the required 'cn:' prefix."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="not-cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "invalid namespace" in result["error"]
        assert result["added"] == []
        assert result["skipped"] == []
        assert result["malformed"] == 0


# ---------------------------------------------------------------------------
# Test — CANON_ID_RE rejects malformed kind with hyphens
# ---------------------------------------------------------------------------

class TestCanonIdReKindRejection:
    """A proposal whose kind contains hyphens produces an ID that fails CANON_ID_RE."""

    def test_hyphenated_kind_counted_as_malformed(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """kind='risk-category' generates 'cn:project:risk-category:my-term'
        which violates the CANON_ID_RE pattern (kind segment must use
        underscores, not hyphens). The proposal must be counted as malformed."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([
            _proposal(temp_id="my-term", kind="risk-category"),
        ]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is None
        assert result["malformed"] == 1
        assert result["added"] == []


# ---------------------------------------------------------------------------
# M9 — Invalid namespace missing cn: prefix
# ---------------------------------------------------------------------------

class TestNamespaceMissingCnPrefix:
    """M9: Namespace 'project:' (missing 'cn:' prefix) must be rejected."""

    def test_namespace_project_colon_without_cn_prefix_returns_error(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """namespace='project:' is missing the required 'cn:' prefix and must
        produce an error result with 'invalid namespace' in the message."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([_proposal()]))

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="project:",
            repo_root=str(tmp_repo),
        )

        assert result["error"] is not None
        assert "invalid namespace" in result["error"]
        assert result["added"] == []
        assert result["skipped"] == []
        assert result["malformed"] == 0


# ---------------------------------------------------------------------------
# M9 — Idempotent re-run with manifest content identity
# ---------------------------------------------------------------------------

class TestIdempotentRerunManifestIdentity:
    """M9: Running canon-accept twice with the same spec and proposals must
    produce an identical manifest file after the second run (byte-identical)."""

    def test_idempotent_rerun_manifest_unchanged(
        self, tmp_repo: Path, manifest_path: Path, tmp_path: Path
    ) -> None:
        """First call adds entries, second call skips all. Manifest content
        must be identical after both calls."""
        _ = manifest_path
        spec_file = tmp_path / "spec.json"
        _write_json(spec_file, _make_spec([
            _proposal(temp_id="idem-a", kind="entity", proposed_label="Idem A", definition="First."),
            _proposal(temp_id="idem-b", kind="entity", proposed_label="Idem B", definition="Second."),
        ]))

        first = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )
        assert first["error"] is None
        assert sorted(first["added"]) == [
            "cn:project:entity:idem-a",
            "cn:project:entity:idem-b",
        ]

        manifest_after_first = (tmp_repo / "canon" / "manifest.json").read_text(encoding="utf-8")

        second = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_repo),
        )
        assert second["error"] is None
        assert second["added"] == []
        assert sorted(second["skipped"]) == [
            "cn:project:entity:idem-a",
            "cn:project:entity:idem-b",
        ]

        manifest_after_second = (tmp_repo / "canon" / "manifest.json").read_text(encoding="utf-8")
        assert manifest_after_first == manifest_after_second, (
            "Manifest must be byte-identical after an idempotent re-run that adds nothing"
        )
