"""Unit tests for the entry_key_registry module.

All tests use the minimal fixture registry at
``tests/fixtures/entry_key_registry/entry_key_registry.json``.  No real
project data is used.  Every public API call passes ``repo_root`` explicitly
pointing at that fixture directory.

Covers:
- Registry loads without I/O errors.
- list_entries: known files return correct tuples; unknown files return None;
  steps with no entry arrays return []; nested arrays are included with their
  full dot-notation path.
- is_corpus_excluded: canonical_refs_used/canonical_proposals excluded;
  per-array corpus_excluded flag; normal array keys not excluded.
- find_entry: single-array files return the triple; multi-array files select
  by id prefix heuristic; unknown files return None.
- all_registered_basenames / get_step_for_file: utilities work from fixture.
- _collect_ids_from_file: registry path collects top-level and nested ids;
  unknown files return empty results (no broad scan — registry is the sole source).
- FileNotFoundError raised when repo_root has no tools/entry_key_registry.json.

Parametrized step_order.json coverage test
-------------------------------------------
The parametrized test that checks every step in step_order.json is covered
by the registry has been moved OUT of this test file.  It is
project-coupled (it validates a specific project's registry against the
toolkit's step_order.json) and does not belong in toolkit CI.

New home: ``tests/host_repo/test_entry_key_registry_coverage.py`` in the
host repo (e.g. ``vc_website/tests/host_repo/``).  That file runs against
the real ``spec/entry_key_registry.json`` and the real step_order.json.

Phantom-filename guard (TestRegistryBasenamesMatchExtractionPaths)
------------------------------------------------------------------
Also moved out to the host-repo test file above — it validates
project-registry basenames against toolkit's extraction_paths.json, which
is a cross-layer check that belongs in host CI.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict

import pytest

from specdev_tools.core.entry_key_registry import (
    all_registered_basenames,
    find_entry,
    get_step_for_file,
    is_corpus_excluded,
    list_entries,
)
from specdev_tools.core.json_utils import _collect_ids_from_file


# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------

_FIXTURE_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    "..", "..", "fixtures", "entry_key_registry",
))
"""Path to the fixture repo_root for tests.

The fixture registry lives at ``<_FIXTURE_DIR>/tools/entry_key_registry.json``.
All public API calls in this module pass ``repo_root=_FIXTURE_DIR``.
"""


def _load_fixture_registry_raw() -> Dict[str, Any]:
    """Load the raw fixture registry JSON (for structural assertions)."""
    path = os.path.join(_FIXTURE_DIR, "tools", "entry_key_registry.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Basic load / registry integrity
# ---------------------------------------------------------------------------


class TestRegistryLoads:
    def test_registry_json_is_valid(self) -> None:
        """Fixture JSON is present and valid."""
        raw = _load_fixture_registry_raw()
        assert isinstance(raw, dict)
        assert "registry" in raw
        assert "_format_version" in raw

    def test_all_registered_basenames_is_nonempty(self) -> None:
        basenames = all_registered_basenames(_FIXTURE_DIR)
        assert len(basenames) > 0

    def test_registry_entries_have_required_fields(self) -> None:
        """Each non-sentinel registry entry has 'step' and 'arrays' keys."""
        raw = _load_fixture_registry_raw()
        for basename, entry in raw["registry"].items():
            if entry.get("_special"):
                continue
            assert "step" in entry, f"{basename}: missing 'step'"
            assert "arrays" in entry, f"{basename}: missing 'arrays'"
            for arr in entry["arrays"]:
                assert "array_path" in arr, f"{basename}: array missing 'array_path'"
                assert "id_field" in arr, f"{basename}: array missing 'id_field'"
                assert "kind" in arr, f"{basename}: array missing 'kind'"
                assert arr["array_path"].startswith("."), (
                    f"{basename}: array_path '{arr['array_path']}' must start with '.'"
                )

    def test_missing_registry_raises_file_not_found(self) -> None:
        """FileNotFoundError raised when repo_root has no tools/entry_key_registry.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError, match="entry_key_registry.json"):
                list_entries("04_fr_list.json", tmpdir)


# ---------------------------------------------------------------------------
# list_entries: known files
# ---------------------------------------------------------------------------


class TestListEntriesKnownFiles:
    def test_04_fr_list_returns_functional_requirements(self) -> None:
        entries = list_entries("04_fr_list.json", _FIXTURE_DIR)
        assert entries is not None
        assert len(entries) == 1
        e = entries[0]
        assert e.array_path == ".functional_requirements"
        assert e.id_field == "fr_id"
        assert e.kind == "functional_requirement"

    def test_01_capabilities_returns_capability(self) -> None:
        entries = list_entries("01_capabilities.json", _FIXTURE_DIR)
        assert entries is not None
        assert any(e.id_field == "capability_id" for e in entries)
        assert any(e.kind == "capability" for e in entries)

    def test_03_glossary_returns_terms(self) -> None:
        entries = list_entries("03_glossary.json", _FIXTURE_DIR)
        assert entries is not None
        assert len(entries) == 1
        e = entries[0]
        assert e.id_field == "term_id"
        assert e.kind == "term"

    def test_06_invariants_returns_rules(self) -> None:
        entries = list_entries("06_invariants.json", _FIXTURE_DIR)
        assert entries is not None
        assert any(e.id_field == "inv_id" for e in entries)
        assert any(e.kind == "rule" for e in entries)

    def test_relative_path_is_stripped_to_basename(self) -> None:
        """spec/04_fr_list.json should match 04_fr_list.json."""
        entries_rel = list_entries("spec/04_fr_list.json", _FIXTURE_DIR)
        entries_base = list_entries("04_fr_list.json", _FIXTURE_DIR)
        assert entries_rel == entries_base

    def test_14_roadmap_includes_nested_task_entries(self) -> None:
        """14_roadmap.json nested tasks[] are included in the flat list."""
        entries = list_entries("14_roadmap.json", _FIXTURE_DIR)
        assert entries is not None
        array_paths = {e.array_path for e in entries}
        # Top-level milestones
        assert ".milestones" in array_paths
        # Nested tasks under milestones
        assert ".milestones[].tasks" in array_paths
        # Nested deliverables under milestones
        assert ".milestones[].deliverables" in array_paths

    def test_14_roadmap_nested_task_entry_fields(self) -> None:
        """14_roadmap.json tasks nested entry has correct id_field and kind."""
        entries = list_entries("14_roadmap.json", _FIXTURE_DIR)
        assert entries is not None
        task_entry = next(e for e in entries if e.array_path == ".milestones[].tasks")
        assert task_entry.id_field == "task_id"
        assert task_entry.kind == "task"

    def test_14_roadmap_nested_deliverable_entry_fields(self) -> None:
        """14_roadmap.json deliverables nested entry has correct id_field and kind."""
        entries = list_entries("14_roadmap.json", _FIXTURE_DIR)
        assert entries is not None
        del_entry = next(e for e in entries if e.array_path == ".milestones[].deliverables")
        assert del_entry.id_field == "id"
        assert del_entry.kind == "deliverable"

    def test_14_roadmap_includes_deep_nested_criterion(self) -> None:
        """Three-deep milestones[].tasks[].acceptance_criteria is flattened (DEVSPEC-125).

        The registry schema defines ``arrayEntry.nested`` recursively, so an
        acceptance-criterion nested two levels under a milestone must appear in
        the flat list with its full ``[].``-joined path.  Regression guard for
        the single-level nesting cap that previously dropped it.
        """
        entries = list_entries("14_roadmap.json", _FIXTURE_DIR)
        assert entries is not None
        crit = next(
            (e for e in entries
             if e.array_path == ".milestones[].tasks[].acceptance_criteria"),
            None,
        )
        assert crit is not None, (
            "deep-nested acceptance_criteria not flattened; got paths "
            f"{[e.array_path for e in entries]}"
        )
        assert crit.id_field == "criterion_id"
        assert crit.kind == "criterion"

    def test_13_extension_manifest_has_extensions_array(self) -> None:
        """13_extension_manifest.json registers extensions[] with extension_id."""
        entries = list_entries("13_extension_manifest.json", _FIXTURE_DIR)
        assert entries is not None
        assert len(entries) == 1
        e = entries[0]
        assert e.array_path == ".extensions"
        assert e.id_field == "extension_id"
        assert e.kind == "extension"

    def test_11_redteam_returns_multiple_arrays(self) -> None:
        entries = list_entries("11_redteam.json", _FIXTURE_DIR)
        assert entries is not None
        assert len(entries) >= 2
        id_fields = {e.id_field for e in entries}
        assert "threat_id" in id_fields
        assert "id" in id_fields  # edge_cases and trace


# ---------------------------------------------------------------------------
# list_entries: no-entry-array steps return empty list (not None)
# ---------------------------------------------------------------------------


class TestListEntriesNoArraySteps:
    """Steps registered with empty arrays return [] (known file) not None (unknown)."""

    def test_13a_returns_empty_list(self) -> None:
        """13a_completeness_assessment.json is registered with arrays:[] — returns []."""
        entries = list_entries("13a_completeness_assessment.json", _FIXTURE_DIR)
        assert entries == []

    def test_16_impl_context_returns_empty_list(self) -> None:
        """16_impl_context.json is registered with arrays:[] — returns []."""
        entries = list_entries("16_impl_context.json", _FIXTURE_DIR)
        assert entries == []

    def test_sentinel_canonical_refs_used_returns_empty(self) -> None:
        """canonical_refs_used is a sentinel — list_entries returns []."""
        entries = list_entries("canonical_refs_used", _FIXTURE_DIR)
        assert entries == []


# ---------------------------------------------------------------------------
# list_entries: unknown files return None
# ---------------------------------------------------------------------------


class TestListEntriesUnknownFile:
    def test_unknown_basename_returns_none(self) -> None:
        assert list_entries("totally_unknown_file.json", _FIXTURE_DIR) is None

    def test_spec_dot_json_returns_none(self) -> None:
        """Test fixture filenames like 'spec.json' fall back to None."""
        assert list_entries("spec.json", _FIXTURE_DIR) is None

    def test_none_file_returns_none(self) -> None:
        """None spec_file falls back gracefully."""
        assert list_entries(None, _FIXTURE_DIR) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# is_corpus_excluded
# ---------------------------------------------------------------------------


class TestIsCorpusExcluded:
    def test_canonical_refs_used_is_excluded(self) -> None:
        assert is_corpus_excluded("canonical_refs_used", _FIXTURE_DIR) is True

    def test_canonical_proposals_is_excluded(self) -> None:
        assert is_corpus_excluded("canonical_proposals", _FIXTURE_DIR) is True

    def test_per_array_corpus_excluded_flag(self) -> None:
        """corpus_excluded:true on an array in the fixture registry marks that key."""
        assert is_corpus_excluded("excluded_items", _FIXTURE_DIR) is True

    def test_functional_requirements_is_not_excluded(self) -> None:
        assert is_corpus_excluded("functional_requirements", _FIXTURE_DIR) is False

    def test_capabilities_is_not_excluded(self) -> None:
        assert is_corpus_excluded("capabilities", _FIXTURE_DIR) is False

    def test_unknown_key_is_not_excluded(self) -> None:
        assert is_corpus_excluded("some_random_array", _FIXTURE_DIR) is False


# ---------------------------------------------------------------------------
# find_entry
# ---------------------------------------------------------------------------


class TestFindEntry:
    def test_single_array_file_returns_triple(self) -> None:
        result = find_entry("04_fr_list.json", "fr-newsletter-subscribe", _FIXTURE_DIR)
        assert result is not None
        array_path, id_field, kind = result
        assert array_path == ".functional_requirements"
        assert id_field == "fr_id"
        assert kind == "functional_requirement"

    def test_unknown_file_returns_none(self) -> None:
        result = find_entry("spec.json", "fr-anything", _FIXTURE_DIR)
        assert result is None

    def test_multi_array_file_selects_by_id_prefix(self) -> None:
        """11_redteam has threats (threat_id) and edge_cases/trace (id).
        A threat-* id should select the threats array.
        """
        result = find_entry("11_redteam.json", "threat-xss-injection", _FIXTURE_DIR)
        assert result is not None
        array_path, id_field, kind = result
        assert id_field == "threat_id"
        assert kind == "threat"

    def test_relative_path_works(self) -> None:
        result = find_entry("spec/03_glossary.json", "term-ghost-cms", _FIXTURE_DIR)
        assert result is not None
        _, id_field, kind = result
        assert id_field == "term_id"
        assert kind == "term"

    def test_bare_id_ambiguity_returns_none(self) -> None:
        """11_redteam has edge_cases (id) and trace (id).
        A bare-id value like 'ec-rate-limit' has no prefix that uniquely
        matches a non-empty stem, so find_entry returns None rather than
        silently returning the wrong array.
        """
        result = find_entry("11_redteam.json", "ec-rate-limit", _FIXTURE_DIR)
        assert result is None

    def test_bare_id_trace_value_returns_none(self) -> None:
        """trace-001 has no matching non-empty stem → None (not edge_cases)."""
        result = find_entry("11_redteam.json", "trace-001", _FIXTURE_DIR)
        assert result is None


# ---------------------------------------------------------------------------
# get_step_for_file
# ---------------------------------------------------------------------------


class TestGetStepForFile:
    def test_04_fr_list_returns_step_04(self) -> None:
        assert get_step_for_file("04_fr_list.json", _FIXTURE_DIR) == "04"

    def test_01_capabilities_returns_step_01(self) -> None:
        assert get_step_for_file("01_capabilities.json", _FIXTURE_DIR) == "01"

    def test_unknown_file_returns_none(self) -> None:
        assert get_step_for_file("spec.json", _FIXTURE_DIR) is None


# ---------------------------------------------------------------------------
# Backward compat: _collect_ids_from_file with registry
# ---------------------------------------------------------------------------


SAMPLE_FR_SPEC = {
    "$schema": "vc:04-fr-list",
    "id": "test-catalog",
    "functional_requirements": [
        {"fr_id": "fr-newsletter-subscribe", "name": "Newsletter Subscribe", "owner": "product"},
        {"fr_id": "fr-newsletter-confirm", "name": "Newsletter Confirm", "owner": "product"},
    ],
    "canonical_refs_used": [
        {"id": "cn:project:cap-newsletter", "label": "Newsletter capability"},
    ],
}

SAMPLE_CAPABILITIES_SPEC = {
    "$schema": "vc:01-capabilities",
    "capabilities": [
        {"capability_id": "cap-search", "name": "Search", "owner": "api"},
        {"capability_id": "cap-auth", "name": "Auth", "owner": "api"},
    ],
}

SAMPLE_INVARIANTS_SPEC = {
    "$schema": "vc:06-invariants",
    "rules": [
        {"inv_id": "inv-data-immutability", "name": "Data Immutability", "owner": "system"},
        {"inv_id": "inv-auth-required", "name": "Auth Required", "owner": "api"},
    ],
}

SAMPLE_MULTI_ARRAY_SPEC = {
    "threats": [{"threat_id": "threat-xss", "description": "XSS", "severity": "high"}],
    "edge_cases": [{"id": "ec-rate-limit", "description": "Rate limit boundary"}],
    "trace": [{"id": "trace-001", "type": "nfr", "note": "derived from NFR-01"}],
}


class TestCollectIdsWithRegistry:
    def test_known_file_uses_registry_id_field(self) -> None:
        """Known file 04_fr_list.json uses fr_id, not bare id fallback."""
        all_ids, id_map = _collect_ids_from_file(
            SAMPLE_FR_SPEC, spec_file="04_fr_list.json", repo_root=_FIXTURE_DIR
        )
        assert "fr-newsletter-subscribe" in all_ids
        assert "fr-newsletter-confirm" in all_ids
        # canonical_refs_used must NOT be in corpus (C2)
        assert "cn:project:cap-newsletter" not in all_ids

    def test_known_file_kind_is_correct(self) -> None:
        all_ids, id_map = _collect_ids_from_file(
            SAMPLE_FR_SPEC, spec_file="04_fr_list.json", repo_root=_FIXTURE_DIR
        )
        kind, jq_path, _ = id_map["fr-newsletter-subscribe"]
        assert kind == "functional_requirement"
        assert jq_path == ".functional_requirements[0]"

    def test_known_file_capabilities_kind(self) -> None:
        all_ids, id_map = _collect_ids_from_file(
            SAMPLE_CAPABILITIES_SPEC, spec_file="01_capabilities.json", repo_root=_FIXTURE_DIR
        )
        assert "cap-search" in all_ids
        kind, _, _ = id_map["cap-search"]
        assert kind == "capability"

    def test_known_file_inv_id_resolves(self) -> None:
        all_ids, id_map = _collect_ids_from_file(
            SAMPLE_INVARIANTS_SPEC, spec_file="06_invariants.json", repo_root=_FIXTURE_DIR
        )
        assert "inv-data-immutability" in all_ids
        kind, jq_path, _ = id_map["inv-data-immutability"]
        assert kind == "rule"
        assert jq_path == ".rules[0]"

    def test_unknown_file_returns_empty(self) -> None:
        """Files not in registry (e.g. spec.json) return empty results — no broad scan."""
        all_ids, id_map = _collect_ids_from_file(
            SAMPLE_FR_SPEC, spec_file="spec.json", repo_root=_FIXTURE_DIR
        )
        # Unknown file → no broad scan → empty results
        assert all_ids == []
        assert id_map == {}

    def test_corpus_exclusion_without_spec_file(self) -> None:
        """Even with an unknown file, the call completes and returns empty."""
        all_ids, id_map = _collect_ids_from_file(
            SAMPLE_FR_SPEC, spec_file="unknown_file.json", repo_root=_FIXTURE_DIR
        )
        assert all_ids == []
        assert id_map == {}

    def test_multi_array_known_file_collects_all(self) -> None:
        """11_redteam.json: threats (threat_id) + edge_cases (id) + trace (id)."""
        all_ids, id_map = _collect_ids_from_file(
            SAMPLE_MULTI_ARRAY_SPEC, spec_file="11_redteam.json", repo_root=_FIXTURE_DIR
        )
        assert "threat-xss" in all_ids
        assert "ec-rate-limit" in all_ids
        assert "trace-001" in all_ids

    def test_id_collision_keeps_first_occurrence(self) -> None:
        """When two entries share an id, the first is kept (deterministic)."""
        # craft a spec with duplicate fr_id
        spec = {
            "functional_requirements": [
                {"fr_id": "fr-dup", "name": "First", "owner": "product"},
                {"fr_id": "fr-dup", "name": "Second", "owner": "api"},
            ]
        }
        all_ids, id_map = _collect_ids_from_file(
            spec, spec_file="04_fr_list.json", repo_root=_FIXTURE_DIR
        )
        # Both are in all_ids (corpus for nearest-search)
        assert all_ids.count("fr-dup") == 2
        # But id_map keeps first occurrence
        kind, jq_path, entry = id_map["fr-dup"]
        assert jq_path == ".functional_requirements[0]"
        assert entry["name"] == "First"

    def test_relative_path_spec_file_works(self) -> None:
        """spec/04_fr_list.json → registry lookup by basename."""
        all_ids, id_map = _collect_ids_from_file(
            SAMPLE_FR_SPEC, spec_file="spec/04_fr_list.json", repo_root=_FIXTURE_DIR
        )
        assert "fr-newsletter-subscribe" in all_ids

    def test_nested_arrays_collected_from_14_roadmap(self) -> None:
        """14_roadmap.json: tasks and deliverables nested inside milestones are indexed."""
        spec = {
            "milestones": [
                {
                    "milestone_id": "ms-1",
                    "name": "Milestone 1",
                    "tasks": [
                        {"task_id": "task-install-ghost-local", "description": "Install"},
                        {"task_id": "task-build-theme-zip", "description": "Build"},
                    ],
                    "deliverables": [
                        {"id": "fr-post-publish", "type": "fr", "note": "publish FR"},
                    ],
                }
            ],
            "dependencies": [],
            "trace": [],
        }
        all_ids, id_map = _collect_ids_from_file(
            spec, spec_file="14_roadmap.json", repo_root=_FIXTURE_DIR
        )
        # Milestone id present
        assert "ms-1" in all_ids
        # Task ids present
        assert "task-install-ghost-local" in all_ids
        assert "task-build-theme-zip" in all_ids
        # Deliverable id present
        assert "fr-post-publish" in all_ids
        # Kind and jq_path are correct for nested task
        kind, jq_path, _ = id_map["task-install-ghost-local"]
        assert kind == "task"
        assert jq_path == ".milestones[0].tasks[0]"
        # Kind and jq_path are correct for nested deliverable
        kind_d, jq_path_d, _ = id_map["fr-post-publish"]
        assert kind_d == "deliverable"
        assert jq_path_d == ".milestones[0].deliverables[0]"

    def test_deep_nested_criteria_collected_from_14_roadmap(self) -> None:
        """14_roadmap.json: criteria 3-deep (milestones[].tasks[].acceptance_criteria)
        are indexed with the correct kind and concrete jq index path (DEVSPEC-125)."""
        spec = {
            "milestones": [
                {
                    "milestone_id": "ms-1",
                    "tasks": [
                        {
                            "task_id": "task-verify-e2e",
                            "acceptance_criteria": [
                                {"criterion_id": "ac-e2e-1", "text": "first"},
                                {"criterion_id": "ac-e2e-2", "text": "second"},
                            ],
                        },
                    ],
                }
            ],
            "dependencies": [],
        }
        all_ids, id_map = _collect_ids_from_file(
            spec, spec_file="14_roadmap.json", repo_root=_FIXTURE_DIR
        )
        assert "ac-e2e-1" in all_ids
        assert "ac-e2e-2" in all_ids
        kind, jq_path, _ = id_map["ac-e2e-2"]
        assert kind == "criterion"
        assert jq_path == ".milestones[0].tasks[0].acceptance_criteria[1]"

    def test_registered_empty_file_returns_no_ids(self) -> None:
        """Files registered with arrays:[] (e.g. 13a) return empty ids and map."""
        all_ids, id_map = _collect_ids_from_file(
            {"dimensions": {"completeness": {"score": 1.0}}},
            spec_file="13a_completeness_assessment.json",
            repo_root=_FIXTURE_DIR,
        )
        assert all_ids == []
        assert id_map == {}

    def test_unknown_file_always_returns_empty_regardless_of_corpus_exclusion(self) -> None:
        """Unknown files return empty — registry is the only source of truth."""
        spec = {
            "canonical_refs_used": [{"id": "cn:project:cap-foo"}],
            "custom_array": [{"fr_id": "fr-example"}],
        }
        all_ids, _ = _collect_ids_from_file(spec, spec_file="unknown.json", repo_root=_FIXTURE_DIR)
        # Unknown file → empty results
        assert all_ids == []
