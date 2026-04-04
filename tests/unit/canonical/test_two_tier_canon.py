"""Tests for two-tier canonical registry support (core + project canon)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from specdev_tools.canonical.registry import CanonicalRegistry
from specdev_tools.canonical.lint import lint_canon_dir, lint_canon_dirs
from specdev_tools.canonical.accept import run_canon_accept
from specdev_tools.canonical.integrity import validate_canonical_integrity
from specdev_tools.canonical.autofix import canonical_autofix
from specdev_tools.validation.hallucination_lint import lint_hallucinations
from specdev_tools.validation.canon_schema_alignment import lint_canon_schema_alignment
from specdev_tools.core.errors import SpecError


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _make_kind_file(canon_dir: Path, kind: str, entries: list[dict]) -> None:
    kinds_dir = canon_dir / "kinds"
    kinds_dir.mkdir(parents=True, exist_ok=True)
    _write_json(kinds_dir / f"{kind}.json", {
        "$schema": "vc:canon:kind",
        "registry_version": "1.0.0",
        "kind": kind,
        "entries": entries,
    })


def _make_manifest(canon_dir: Path, entries: list[dict], aliases: list[dict] | None = None) -> None:
    _write_json(canon_dir / "manifest.json", {
        "$schema": "vc:core:canon",
        "registry_version": "1.0.0",
        "entries": entries,
        "aliases": aliases or [],
    })


def _core_entry(kind: str, slug: str) -> dict:
    return {
        "id": f"cn:core:{kind}:{slug}",
        "kind": kind,
        "preferred_label": slug.replace("-", " "),
        "definition": f"Core {kind} {slug}",
        "version": "1.0.0",
        "status": "active",
        "owners": [],
        "aliases": [],
        "lifecycle": {"introduced_at": "2024-01-01T00:00:00Z"},
    }


def _project_entry(kind: str, slug: str) -> dict:
    return {
        "id": f"cn:project:{kind}:{slug}",
        "kind": kind,
        "preferred_label": slug.replace("-", " "),
        "definition": f"Project {kind} {slug}",
        "version": "1.0.0",
        "status": "active",
        "owners": [],
        "aliases": [],
        "lifecycle": {"introduced_at": "2024-01-01T00:00:00Z"},
    }


# ---------- Registry loading tests ----------

class TestTwoTierRegistryLoad:
    def test_load_core_only(self, tmp_path: Path) -> None:
        """Single-tier backward compat — project_canon_dir=None works as before."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])
        _make_kind_file(core, "stage", [_core_entry("stage", "dev")])

        registry = CanonicalRegistry.load(str(tmp_path), project_canon_dir=None)
        assert registry.get("cn:core:stage:dev") is not None
        assert not any(e.code == "W421" for e in registry.load_errors)

    def test_load_project_only(self, tmp_path: Path) -> None:
        """Project canon loads when core canon is minimal/empty."""
        core = tmp_path / "canon"
        _make_manifest(core, [])

        project = tmp_path / "spec" / "canon"
        _make_manifest(project, [_project_entry("entity", "post")])
        _make_kind_file(project, "entity", [_project_entry("entity", "post")])

        registry = CanonicalRegistry.load(str(tmp_path), project_canon_dir=str(project))
        assert registry.get("cn:project:entity:post") is not None

    def test_load_merged_both_tiers(self, tmp_path: Path) -> None:
        """Core + project entries both appear in merged registry."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])
        _make_kind_file(core, "stage", [_core_entry("stage", "dev")])

        project = tmp_path / "spec" / "canon"
        _make_manifest(project, [_project_entry("entity", "post")])
        _make_kind_file(project, "entity", [_project_entry("entity", "post")])

        registry = CanonicalRegistry.load(str(tmp_path), project_canon_dir=str(project))
        assert registry.get("cn:core:stage:dev") is not None
        assert registry.get("cn:project:entity:post") is not None

    def test_project_takes_precedence_on_id_collision(self, tmp_path: Path) -> None:
        """Same ID in both tiers → project entry wins, W421 warning emitted."""
        shared_entry = _core_entry("stage", "dev")
        project_version = dict(shared_entry)
        project_version["definition"] = "Project override"

        core = tmp_path / "canon"
        _make_manifest(core, [shared_entry])

        project = tmp_path / "spec" / "canon"
        _make_manifest(project, [project_version])

        registry = CanonicalRegistry.load(str(tmp_path), project_canon_dir=str(project))
        entry = registry.get("cn:core:stage:dev")
        assert entry is not None
        assert entry.payload["definition"] == "Project override"
        assert any(e.code == "W421" for e in registry.load_errors)

    def test_project_canon_not_found_silently_skipped(self, tmp_path: Path) -> None:
        """Non-existent project dir → no error, core-only behavior."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])

        registry = CanonicalRegistry.load(
            str(tmp_path),
            project_canon_dir=str(tmp_path / "nonexistent" / "canon"),
        )
        assert registry.get("cn:core:stage:dev") is not None
        assert not any(e.code.startswith("E") for e in registry.load_errors)

    def test_modular_kinds_in_project_canon(self, tmp_path: Path) -> None:
        """Project canon with kinds/*.json loads correctly."""
        core = tmp_path / "canon"
        _make_manifest(core, [])

        project = tmp_path / "spec" / "canon"
        # Only modular kinds, no manifest entries
        _make_kind_file(project, "capability", [_project_entry("capability", "search")])
        # Need at least a manifest for modular to attach to
        _make_manifest(project, [])

        registry = CanonicalRegistry.load(str(tmp_path), project_canon_dir=str(project))
        assert registry.get("cn:project:capability:search") is not None


# ---------- Lint tests ----------

class TestTwoTierLint:
    def test_lint_canon_dirs_both_tiers(self, tmp_path: Path) -> None:
        """lint_canon_dirs validates both core and project canon."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])
        _make_kind_file(core, "stage", [_core_entry("stage", "dev")])

        project = tmp_path / "spec" / "canon"
        _make_manifest(project, [_project_entry("entity", "post")])
        _make_kind_file(project, "entity", [_project_entry("entity", "post")])

        errs = lint_canon_dirs(
            str(tmp_path),
            project_canon_dir=str(project),
            require_manifest_schema_registration=False,
        )
        # Should pass with no errors (both tiers are valid)
        assert not any(e.code.startswith("E") for e in errs)

    def test_lint_project_canon_with_schema_registry_root(self, tmp_path: Path) -> None:
        """lint_canon_dir for project canon uses schema_registry_root."""
        project = tmp_path / "host" / "spec" / "canon"
        _make_manifest(project, [_project_entry("entity", "post")])
        _make_kind_file(project, "entity", [_project_entry("entity", "post")])

        # Should not fail looking for schema_registry in project canon parent
        errs = lint_canon_dir(
            str(project.parent),
            canon_dir="canon",
            require_manifest_schema_registration=False,
        )
        assert not any("schema_registry" in e.message for e in errs)

    def test_lint_canon_dirs_no_project(self, tmp_path: Path) -> None:
        """lint_canon_dirs with no project canon = single-tier behavior."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])
        _make_kind_file(core, "stage", [_core_entry("stage", "dev")])

        errs = lint_canon_dirs(
            str(tmp_path),
            project_canon_dir=None,
            require_manifest_schema_registration=False,
        )
        assert not any(e.code.startswith("E") for e in errs)


# ---------- Accept tests ----------

class TestTwoTierAccept:
    def test_accept_writes_to_project_canon(self, tmp_path: Path) -> None:
        """canon-accept writes to project canon dir, not toolkit canon."""
        project_canon = tmp_path / "spec" / "canon"
        _make_manifest(project_canon, [])

        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, {
            "$schema": "vc:03-glossary",
            "canonical_proposals": [{
                "temp_id": "my-term",
                "kind": "entity",
                "proposed_label": "My Term",
                "definition": "A test entity",
                "source_field": "terms",
            }],
        })

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_path),
            canon_dir=str(project_canon),
            project_canon=True,
        )
        assert result["error"] is None
        assert "cn:project:entity:my-term" in result["added"]

        # Verify written to project canon
        with open(project_canon / "manifest.json") as f:
            m = json.load(f)
        ids = [e["id"] for e in m["entries"]]
        assert "cn:project:entity:my-term" in ids

    def test_accept_rejects_core_namespace_in_project(self, tmp_path: Path) -> None:
        """canon-accept raises E422 when project_canon=True and cn:core:* namespace."""
        project_canon = tmp_path / "spec" / "canon"
        _make_manifest(project_canon, [])

        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, {
            "$schema": "vc:03-glossary",
            "canonical_proposals": [{
                "temp_id": "my-stage",
                "kind": "stage",
                "proposed_label": "My Stage",
                "definition": "A test stage",
                "source_field": "terms",
            }],
        })

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:core:",
            repo_root=str(tmp_path),
            canon_dir=str(project_canon),
            project_canon=True,
        )
        assert result["error"] is not None
        assert "E422" in result["error"]

    def test_accept_does_not_write_to_core(self, tmp_path: Path) -> None:
        """canon-accept with project_canon writes to project dir, not core."""
        core_canon = tmp_path / "canon"
        _make_manifest(core_canon, [_core_entry("stage", "dev")])

        project_canon = tmp_path / "spec" / "canon"
        _make_manifest(project_canon, [])

        spec_file = tmp_path / "spec" / "03_glossary.json"
        _write_json(spec_file, {
            "$schema": "vc:03-glossary",
            "canonical_proposals": [{
                "temp_id": "my-entity",
                "kind": "entity",
                "proposed_label": "My Entity",
                "definition": "A test entity",
                "source_field": "terms",
            }],
        })

        result = run_canon_accept(
            spec_file=str(spec_file),
            namespace="cn:project:",
            repo_root=str(tmp_path),
            canon_dir=str(project_canon),
            project_canon=True,
        )
        assert result["error"] is None

        # Core manifest should be unchanged
        with open(core_canon / "manifest.json") as f:
            m = json.load(f)
        ids = [e["id"] for e in m["entries"]]
        assert "cn:project:entity:my-entity" not in ids


# ---------- Discovery tests ----------

class TestDiscoverProjectCanonDir:
    def test_discover_git_root_path(self, tmp_path: Path) -> None:
        from specdev_tools.cli import _discover_project_canon_dir
        canon_dir = tmp_path / "spec" / "canon"
        canon_dir.mkdir(parents=True)
        result = _discover_project_canon_dir(git_root=str(tmp_path))
        assert result == str(canon_dir)

    def test_discover_spec_root_fallback(self, tmp_path: Path) -> None:
        from specdev_tools.cli import _discover_project_canon_dir
        spec_root = tmp_path / "spec"
        canon_dir = spec_root / "canon"
        canon_dir.mkdir(parents=True)
        result = _discover_project_canon_dir(spec_root=str(spec_root))
        assert result == str(canon_dir)

    def test_discover_spec_dir_fallback(self, tmp_path: Path) -> None:
        from specdev_tools.cli import _discover_project_canon_dir
        spec_dir = tmp_path / "spec"
        canon_dir = spec_dir / "canon"
        canon_dir.mkdir(parents=True)
        result = _discover_project_canon_dir(spec_dir=str(spec_dir))
        assert result == str(canon_dir)

    def test_discover_nonexistent_returns_none(self, tmp_path: Path) -> None:
        from specdev_tools.cli import _discover_project_canon_dir
        result = _discover_project_canon_dir(git_root=str(tmp_path))
        assert result is None

    def test_discover_priority_order(self, tmp_path: Path) -> None:
        """git_root takes priority over spec_root."""
        from specdev_tools.cli import _discover_project_canon_dir
        git_canon = tmp_path / "git" / "spec" / "canon"
        git_canon.mkdir(parents=True)
        spec_canon = tmp_path / "specroot" / "canon"
        spec_canon.mkdir(parents=True)
        result = _discover_project_canon_dir(
            git_root=str(tmp_path / "git"),
            spec_root=str(tmp_path / "specroot"),
        )
        assert result == str(git_canon)


# ---------- Namespace isolation ----------

class TestNamespaceIsolation:
    def test_core_and_project_entries_separate(self, tmp_path: Path) -> None:
        """cn:core:* from core, cn:project:* from project — no cross-contamination."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])

        project = tmp_path / "spec" / "canon"
        _make_manifest(project, [_project_entry("entity", "post")])

        registry = CanonicalRegistry.load(str(tmp_path), project_canon_dir=str(project))

        core_ids = [eid for eid in registry.entries if eid.startswith("cn:core:")]
        project_ids = [eid for eid in registry.entries if eid.startswith("cn:project:")]

        assert "cn:core:stage:dev" in core_ids
        assert "cn:project:entity:post" in project_ids
        assert len(core_ids) == 1
        assert len(project_ids) == 1


# ---------- Integrity merged registry tests ----------

class TestIntegrityMergedRegistry:
    def test_integrity_merged_registry(self, tmp_path: Path) -> None:
        """validate_canonical_integrity resolves cn:project:* refs from project canon."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])

        project = tmp_path / "spec" / "canon"
        _make_manifest(project, [_project_entry("entity", "post")])

        # Create a spec file that references the project canon entry
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir(exist_ok=True)
        _write_json(spec_dir / "03_glossary.json", {
            "$schema": "vc:03-glossary",
            "canonical_refs_used": ["cn:project:entity:post", "cn:core:stage:dev"],
            "terms": [{
                "term": "post",
                "definition": "A blog post entity for publishing content",
                "domain": "content",
                "canonical_refs": [
                    {"id": "cn:project:entity:post", "kind": "entity", "version": "^1.0.0"},
                    {"id": "cn:core:stage:dev", "kind": "stage", "version": "^1.0.0"},
                ],
            }],
        })

        errs = validate_canonical_integrity(
            str(tmp_path),
            str(spec_dir),
            require_manifest_schema_registration=False,
            project_canon_dir=str(project),
        )
        # No E150 (UNRESOLVED_CANONICAL_REF) for either tier
        unresolved = [e for e in errs if e.code == "E150"]
        assert not unresolved, f"Unexpected unresolved refs: {unresolved}"


# ---------- Hallucination lint merged registry tests ----------

class TestHallucinationLintMergedRegistry:
    def test_hallucination_lint_merged_registry(self, tmp_path: Path) -> None:
        """lint_hallucinations recognizes project canon IDs as valid."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])

        project = tmp_path / "spec" / "canon"
        _make_manifest(project, [_project_entry("entity", "post")])

        spec_dir = tmp_path / "spec"
        spec_dir.mkdir(exist_ok=True)
        _write_json(spec_dir / "03_glossary.json", {
            "$schema": "vc:03-glossary",
            "canonical_refs_used": ["cn:project:entity:post"],
            "terms": [{
                "term": "post",
                "definition": "A blog post entity for publishing content",
                "domain": "content",
                "canonical_refs": [
                    {"id": "cn:project:entity:post", "kind": "entity", "version": "^1.0.0"},
                ],
            }],
        })

        errs = lint_hallucinations(
            str(spec_dir),
            repo_root=str(tmp_path),
            require_manifest_schema_registration=False,
            project_canon_dir=str(project),
        )
        # No hallucination errors for valid project canon IDs
        hallucination_errs = [e for e in errs if "hallucin" in e.message.lower() or e.code in ("E301", "E302")]
        assert not hallucination_errs, f"Unexpected hallucination errors: {hallucination_errs}"


# ---------- Autofix merged registry tests ----------

class TestAutofixMergedRegistry:
    def test_autofix_merged_registry(self, tmp_path: Path) -> None:
        """canonical_autofix uses both tiers for correction lookups."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])

        project = tmp_path / "spec" / "canon"
        _make_manifest(project, [_project_entry("entity", "post")])

        spec_dir = tmp_path / "spec"
        spec_dir.mkdir(exist_ok=True)
        _write_json(spec_dir / "03_glossary.json", {
            "$schema": "vc:03-glossary",
            "canonical_refs_used": ["cn:project:entity:post"],
            "terms": [{
                "term": "post",
                "definition": "A blog post entity for publishing content",
                "domain": "content",
                "canonical_refs": [
                    {"id": "cn:project:entity:post", "kind": "entity", "version": "^1.0.0"},
                ],
            }],
        })

        result = canonical_autofix(
            str(tmp_path),
            str(spec_dir),
            write=False,
            require_manifest_schema_registration=False,
            project_canon_dir=str(project),
        )
        # Should not crash; no errors about missing project canon entries
        for file_path, items in result.items():
            for item in items:
                if isinstance(item, SpecError):
                    assert "cn:project:entity:post" not in item.message


# ---------- Canon schema alignment merged tests ----------

class TestCanonSchemaAlignmentMerged:
    def test_canon_schema_alignment_merged(self, tmp_path: Path) -> None:
        """lint_canon_schema_alignment includes project entries in merged registry."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])

        project = tmp_path / "spec" / "canon"
        _make_manifest(project, [_project_entry("entity", "post")])

        # This function checks alignment between canon kinds and schema enums.
        # With no schema dir, it should still load the merged registry without crashing.
        errs = lint_canon_schema_alignment(
            str(tmp_path),
            project_canon_dir=str(project),
        )
        # Should not error about missing project entries in registry
        assert not any("cn:project:entity:post" in e.message and e.code.startswith("E") for e in errs)


# ---------- Aliases in project canon tests ----------

class TestAliasesInProjectCanon:
    def test_aliases_in_project_canon(self, tmp_path: Path) -> None:
        """Project-level aliases resolve against project entries."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])

        project = tmp_path / "spec" / "canon"
        project_entry = _project_entry("entity", "post")
        _write_json(project / "manifest.json", {
            "$schema": "vc:core:canon",
            "registry_version": "1.0.0",
            "entries": [project_entry],
            "aliases": [{
                "kind": "entity",
                "normalized": "blog-post",
                "target_id": "cn:project:entity:post",
                "status": "active",
            }],
        })

        registry = CanonicalRegistry.load(str(tmp_path), project_canon_dir=str(project))
        resolved = registry.resolve_alias("entity", "blog-post")
        assert resolved == "cn:project:entity:post"


# ---------- Error gating tests ----------

class TestErrorGatingMixedTiers:
    def test_error_gating_with_mixed_tier_errors(self, tmp_path: Path) -> None:
        """Project canon lint errors cause lint_canon_dirs to return errors, gating downstream."""
        core = tmp_path / "canon"
        _make_manifest(core, [_core_entry("stage", "dev")])

        # Create invalid project canon (malformed manifest)
        project = tmp_path / "spec" / "canon"
        project.mkdir(parents=True)
        with open(project / "manifest.json", "w") as f:
            f.write("not valid json {{{")

        errs = lint_canon_dirs(
            str(tmp_path),
            project_canon_dir=str(project),
            require_manifest_schema_registration=False,
        )
        # Should contain errors from the project tier
        assert any(e.code.startswith("E") for e in errs), \
            "Expected errors from malformed project canon"
