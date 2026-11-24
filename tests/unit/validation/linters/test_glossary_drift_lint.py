"""Unit tests for lint_glossary_drift (E606, E607, W606)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from specdev_tools.validation.glossary_drift_lint import lint_glossary_drift


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _glossary(terms=None, proposals=None, refs_used=None) -> dict:
    return {
        "id": "03_glossary",
        "terms": terms or [],
        "canonical_proposals": proposals or [],
        "canonical_refs_used": refs_used or [],
    }


def _term(term_id: str, definition: str, canon_id: str | None = None) -> dict:
    t: dict = {"term_id": term_id, "term": term_id.removeprefix("term-"), "definition": definition}
    if canon_id:
        t["term_ref"] = {"id": canon_id, "kind": "term", "label": term_id, "version": "1.0.0"}
    return t


def _proposal(temp_id: str, definition: str, kind: str = "term") -> dict:
    return {
        "temp_id": temp_id,
        "kind": kind,
        "proposed_label": temp_id,
        "definition": definition,
        "source_field": "terms[*].term",
        "suggested_namespace": "project",
    }


def _kinds_term_file(entries: list[dict]) -> dict:
    return {"kind": "term", "entries": entries}


def _canon_entry(eid: str, definition: str, accepted_from: str = "03_glossary.json") -> dict:
    return {
        "id": eid,
        "kind": eid.split(":")[2],
        "preferred_label": eid.rsplit(":", 1)[1],
        "definition": definition,
        "version": "1.0.0",
        "status": "active",
        "owners": ["product"],
        "aliases": [],
        "lifecycle": {
            "introduced_at": "2026-01-01T00:00:00Z",
            "source_field": "terms[*].term",
            "accepted_from": accepted_from,
        },
    }


def _manifest(entries: list[dict]) -> dict:
    return {"registry_version": "1.0.0", "entries": entries}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_glossary_is_noop(tmp_path):
    """No 03_glossary.json → returns []."""
    spec = tmp_path / "spec"
    spec.mkdir()
    result = lint_glossary_drift(str(spec))
    assert result == []


def test_clean_glossary_passes(tmp_path):
    """All three copies in sync → no errors."""
    root = tmp_path
    spec = root / "spec"
    spec.mkdir()
    canon = spec / "canon"

    definition = "A clean definition."
    _write(
        spec / "03_glossary.json",
        _glossary(
            terms=[_term("term-foo", definition, "cn:project:term:foo")],
            proposals=[_proposal("foo", definition)],
            refs_used=[{"id": "cn:project:term:foo", "kind": "term", "version": "1.0.0"}],
        ),
    )
    _write(canon / "kinds" / "term.json", _kinds_term_file([
        _canon_entry("cn:project:term:foo", definition),
    ]))
    _write(canon / "manifest.json", _manifest([
        _canon_entry("cn:project:term:foo", definition),
    ]))

    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    assert result == []


def test_proposal_drift_fires_e606(tmp_path):
    """Term def differs from proposal def → E606."""
    root = tmp_path
    spec = root / "spec"
    spec.mkdir()

    _write(
        spec / "03_glossary.json",
        _glossary(
            terms=[_term("term-foo", "The correct definition.")],
            proposals=[_proposal("foo", "A different definition in the proposal.")],
        ),
    )

    result = lint_glossary_drift(str(spec))
    codes = [e.code for e in result]
    assert "E606" in codes
    assert any("term-foo" in e.message for e in result if e.code == "E606")


def test_canon_drift_fires_e607(tmp_path):
    """Term def differs from canon kinds entry → E607."""
    spec = tmp_path / "spec"
    spec.mkdir()
    canon = spec / "canon"

    _write(
        spec / "03_glossary.json",
        _glossary(
            terms=[_term("term-bar", "Term definition.", "cn:project:term:bar")],
            proposals=[_proposal("bar", "Term definition.")],
        ),
    )
    _write(canon / "kinds" / "term.json", _kinds_term_file([
        _canon_entry("cn:project:term:bar", "Canon has a different definition."),
    ]))
    _write(canon / "manifest.json", _manifest([]))

    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    codes = [e.code for e in result]
    assert "E607" in codes
    assert any("term-bar" in e.message for e in result if e.code == "E607")


def test_orphan_fires_w606(tmp_path):
    """Canon entry from glossary not in refs_used or proposals → W606."""
    spec = tmp_path / "spec"
    spec.mkdir()
    canon = spec / "canon"

    _write(
        spec / "03_glossary.json",
        _glossary(
            terms=[],
            proposals=[],
            refs_used=[],
        ),
    )
    _write(canon / "manifest.json", _manifest([
        _canon_entry("cn:project:term:orphan", "Some definition.", accepted_from="03_glossary.json"),
    ]))

    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    codes = [e.code for e in result]
    assert "W606" in codes
    assert any("cn:project:term:orphan" in e.message for e in result if e.code == "W606")


def test_scss_term_proposal_parity(tmp_path):
    """term-scss and canonical_proposals[scss, kind=term] differ → E606."""
    spec = tmp_path / "spec"
    spec.mkdir()

    _write(
        spec / "03_glossary.json",
        _glossary(
            terms=[_term("term-scss", "Full SCSS term definition with details.")],
            proposals=[
                _proposal("scss", "A shorter proposal definition.", kind="term"),
                _proposal("scss", "Abbreviation for Sassy CSS.", kind="acronym"),
            ],
        ),
    )

    result = lint_glossary_drift(str(spec))
    e606 = [e for e in result if e.code == "E606"]
    assert len(e606) == 1, "exactly one E606 expected (term proposal only, not acronym)"
    assert "term-scss" in e606[0].message


def test_core_canon_ids_not_orphaned(tmp_path):
    """cn:core:* entries in manifest are never flagged as orphans."""
    spec = tmp_path / "spec"
    spec.mkdir()
    canon = spec / "canon"

    _write(
        spec / "03_glossary.json",
        _glossary(terms=[], proposals=[], refs_used=[]),
    )
    core_entry = _canon_entry("cn:core:unit:count", "Count definition.")
    core_entry["lifecycle"]["accepted_from"] = "03_glossary.json"
    _write(canon / "manifest.json", _manifest([core_entry]))

    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    assert result == []


def test_invalid_glossary_json_returns_e521(tmp_path):
    """Malformed JSON in 03_glossary.json → [E521]."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "03_glossary.json").write_text("{invalid json", encoding="utf-8")

    result = lint_glossary_drift(str(spec))
    assert len(result) == 1
    assert result[0].code == "E521"


def test_missing_kinds_dir_skips_pass2(tmp_path):
    """project_canon_dir given but kinds/ subdir absent → no E607."""
    spec = tmp_path / "spec"
    spec.mkdir()
    canon = tmp_path / "mycanon"
    canon.mkdir()  # no kinds/ subdir

    _write(
        spec / "03_glossary.json",
        _glossary(
            terms=[_term("term-x", "Some definition.", "cn:project:term:x")],
            proposals=[_proposal("x", "Some definition.")],
        ),
    )

    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    assert not any(e.code == "E607" for e in result)


def test_no_canon_dir_skips_pass2_and_pass3(tmp_path):
    """No project_canon_dir, no spec/canon/ → no E607, no W606."""
    spec = tmp_path / "spec"
    spec.mkdir()

    _write(
        spec / "03_glossary.json",
        _glossary(
            terms=[_term("term-z", "Definition A.", "cn:project:term:z")],
            proposals=[_proposal("z", "Definition A.")],
        ),
    )

    result = lint_glossary_drift(str(spec))
    assert not any(e.code in ("E607", "W606") for e in result)


def test_multiple_drifts_all_reported(tmp_path):
    """Two proposal drifts + one canon drift → 2x E606 + 1x E607."""
    spec = tmp_path / "spec"
    spec.mkdir()
    canon = spec / "canon"

    _write(
        spec / "03_glossary.json",
        _glossary(
            terms=[
                _term("term-a", "Term A definition.", "cn:project:term:a"),
                _term("term-b", "Term B definition.", "cn:project:term:b"),
                _term("term-c", "Term C definition.", "cn:project:term:c"),
            ],
            proposals=[
                _proposal("a", "Proposal A — different from term."),
                _proposal("b", "Proposal B — also different."),
                _proposal("c", "Term C definition."),  # same → no E606
            ],
        ),
    )
    _write(canon / "kinds" / "term.json", _kinds_term_file([
        _canon_entry("cn:project:term:a", "Term A definition."),
        _canon_entry("cn:project:term:b", "Term B definition."),
        _canon_entry("cn:project:term:c", "Canon C is different from term."),
    ]))
    _write(canon / "manifest.json", _manifest([]))

    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    e606 = [e for e in result if e.code == "E606"]
    e607 = [e for e in result if e.code == "E607"]
    assert len(e606) == 2
    assert len(e607) == 1
    assert any("term-c" in e.message for e in e607)


def test_single_term_both_e606_and_e607(tmp_path):
    """One term where all three copies differ → both E606 and E607 for same term_id."""
    spec = tmp_path / "spec"
    spec.mkdir()
    canon = spec / "canon"

    _write(
        spec / "03_glossary.json",
        _glossary(
            terms=[_term("term-d", "Term D version.", "cn:project:term:d")],
            proposals=[_proposal("d", "Proposal D version.")],
        ),
    )
    _write(canon / "kinds" / "term.json", _kinds_term_file([
        _canon_entry("cn:project:term:d", "Canon D version."),
    ]))
    _write(canon / "manifest.json", _manifest([]))

    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    codes = [e.code for e in result]
    assert "E606" in codes
    assert "E607" in codes
    e606_paths = [e.path for e in result if e.code == "E606"]
    e607_paths = [e.path for e in result if e.code == "E607"]
    assert any("term-d" in (p or "") for p in e606_paths)
    assert any("term-d" in (p or "") for p in e607_paths)


def test_accepted_from_basename_only(tmp_path):
    """Only basename of accepted_from compared — absolute path and non-matching filename."""
    spec = tmp_path / "spec"
    spec.mkdir()
    canon = spec / "canon"

    _write(
        spec / "03_glossary.json",
        _glossary(terms=[], proposals=[], refs_used=[]),
    )
    glossary_entry = _canon_entry(
        "cn:project:term:glossary-sourced",
        "Some definition.",
        accepted_from="/some/other/path/03_glossary.json",
    )
    non_glossary_entry = _canon_entry(
        "cn:project:term:other-sourced",
        "Another definition.",
        accepted_from="04_fr_list.json",
    )
    _write(canon / "manifest.json", _manifest([glossary_entry, non_glossary_entry]))

    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    orphan_ids = [e.path for e in result if e.code == "W606"]
    assert any("cn:project:term:glossary-sourced" in (p or "") for p in orphan_ids)
    assert not any("cn:project:term:other-sourced" in (p or "") for p in orphan_ids)


def test_term_missing_term_id_does_not_crash(tmp_path):
    """Terms without term_id are skipped gracefully — no KeyError."""
    spec = tmp_path / "spec"
    # One valid term and one term with term_id absent
    terms = [
        _term("term-valid", "A valid term definition."),
        {"term": "no-id-term", "definition": "A term that omits term_id."},
    ]
    _write(spec / "03_glossary.json", _glossary(terms=terms))
    result = lint_glossary_drift(str(spec))
    # Must not raise; no drift errors expected
    assert isinstance(result, list)
    assert not any(e.code in ("E606", "E607") for e in result)


def test_term_with_term_ref_but_no_term_id_skipped_in_pass2(tmp_path):
    """Term has term_ref pointing to cn:project: but no term_id → skipped, no malformed E607."""
    spec = tmp_path / "spec"
    spec.mkdir()
    canon = tmp_path / "canon"
    canon_id = "cn:project:term:noname"
    terms = [
        # term_ref present, definition drifts from canon, but term_id absent
        {"term": "no-id", "definition": "Definition differs.", "term_ref": {"id": canon_id}},
    ]
    _write(spec / "03_glossary.json", _glossary(terms=terms))
    kinds_entry = {"id": canon_id, "kind": "term", "preferred_label": "noname",
                   "definition": "Canon definition."}
    _write(canon / "kinds" / "term.json", _kinds_term_file([kinds_entry]))
    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    # No E607 because term_id is absent — cannot produce a meaningful error path
    assert not any(e.code == "E607" for e in result)


def test_term_missing_term_id_does_not_suppress_e607(tmp_path):
    """A term with term_id but a drifted definition still fires E607 when term_id is present."""
    spec = tmp_path / "spec"
    canon = tmp_path / "canon"
    canon_id = "cn:project:term:drifted"
    terms = [
        # term with term_id — definition drifts from canon
        _term("term-drifted", "Drifted definition.", canon_id=canon_id),
        # term without term_id — should be silently skipped
        {"term": "no-id", "definition": "No term_id here."},
    ]
    _write(spec / "03_glossary.json", _glossary(terms=terms))
    kinds_entry = {"id": canon_id, "kind": "term", "preferred_label": "drifted",
                   "definition": "Canon definition differs."}
    _write(canon / "kinds" / "term.json", _kinds_term_file([kinds_entry]))
    result = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    e607 = [e for e in result if e.code == "E607"]
    assert len(e607) == 1, f"Expected exactly 1 E607, got {e607}"
    assert "term-drifted" in e607[0].message


# ---------------------------------------------------------------------------
# H-152-2: normalised comparison, first difference, label, proposals of any step
# ---------------------------------------------------------------------------

_FOO = "cn:project:term:foo"


def _term_canon(tmp_path: Path, term: dict, entry: dict, proposals=None) -> tuple[Path, Path]:
    spec = tmp_path / "spec"
    canon = spec / "canon"
    _write(spec / "03_glossary.json", _glossary(terms=[term], proposals=proposals))
    _write(canon / "manifest.json", _manifest([entry]))
    return spec, canon


def _e607(spec: Path, canon: Path) -> list:
    return [e for e in lint_glossary_drift(str(spec), project_canon_dir=str(canon)) if e.code == "E607"]


def _step_artifact_with_proposal(spec: Path, file_name: str, proposal: dict) -> None:
    _write(spec / file_name, {"id": file_name, "canonical_proposals": [proposal]})


def test_whitespace_and_unicode_form_do_not_count_as_drift(tmp_path):
    decomposed = "Café owner  grants\naccess."
    composed = "Café owner grants access."
    spec, canon = _term_canon(
        tmp_path,
        _term("term-foo", decomposed, _FOO),
        _canon_entry(_FOO, composed),
        proposals=[_proposal("foo", composed)],
    )
    assert lint_glossary_drift(str(spec), project_canon_dir=str(canon)) == []


def test_the_drift_message_names_the_first_difference(tmp_path):
    spec, canon = _term_canon(
        tmp_path,
        _term("term-foo", "A shared start, then spec text.", _FOO),
        _canon_entry(_FOO, "A shared start, then canon text."),
    )
    (e607,) = _e607(spec, canon)
    assert "first_difference_at=21" in e607.message
    assert "spec='spec text.'" in e607.message
    assert "canon='canon text.'" in e607.message


def test_a_proposal_drift_message_names_the_first_difference(tmp_path):
    spec = tmp_path / "spec"
    _write(spec / "03_glossary.json", _glossary(
        terms=[_term("term-foo", "Same start, term end.")],
        proposals=[_proposal("foo", "Same start, proposal end.")],
    ))
    (e606,) = lint_glossary_drift(str(spec))
    assert e606.code == "E606"
    assert "first_difference_at=12 spec='term end.' proposal='proposal end.'" in e606.message


def test_a_changed_term_label_is_e607_unless_the_old_label_is_an_alias(tmp_path):
    renamed = _canon_entry(_FOO, "Same.")
    renamed["preferred_label"] = "new label"
    term = _term("term-foo", "Same.", _FOO)
    spec, canon = _term_canon(tmp_path, term, renamed)
    (e607,) = _e607(spec, canon)
    assert "field=preferred_label" in e607.message

    renamed["aliases"] = ["FOO"]
    _write(canon / "manifest.json", _manifest([renamed]))
    assert _e607(spec, canon) == []


def test_a_capability_proposal_that_differs_from_its_canon_entry_is_e607(tmp_path):
    spec = tmp_path / "spec"
    canon = spec / "canon"
    cap_id = "cn:project:capability:login"
    _write(spec / "03_glossary.json", _glossary())
    _step_artifact_with_proposal(spec, "01_capabilities.json", {
        **_proposal("login", "Members sign in.", kind="capability"),
    })
    entry = _canon_entry(cap_id, "Members sign in with a password.", accepted_from="01_capabilities.json")
    _write(canon / "kinds" / "capability.json", {"kind": "capability", "entries": [entry]})

    (e607,) = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    assert e607.code == "E607"
    assert e607.message.startswith(
        f"CANON_PROPOSAL_DRIFT kind=capability canon={cap_id} file=01_capabilities.json field=definition"
    )
    assert e607.path == f"01_capabilities.json:{cap_id}"


def test_a_metric_proposal_that_matches_its_canon_entry_is_clean(tmp_path):
    spec = tmp_path / "spec"
    canon = spec / "canon"
    metric_id = "cn:project:metric:p95"
    _write(spec / "03_glossary.json", _glossary())
    _step_artifact_with_proposal(spec, "07_nfr.json", _proposal("p95", "95th percentile latency.", kind="metric"))
    entry = _canon_entry(metric_id, "95th percentile  latency.", accepted_from="07_nfr.json")
    _write(canon / "manifest.json", _manifest([entry]))

    assert lint_glossary_drift(str(spec), project_canon_dir=str(canon)) == []


def test_the_glossary_file_is_not_scanned_twice(tmp_path):
    spec, canon = _term_canon(
        tmp_path,
        _term("term-foo", "Term text.", _FOO),
        _canon_entry(_FOO, "Canon text."),
        proposals=[_proposal("foo", "Term text.")],
    )
    codes = [e.code for e in lint_glossary_drift(str(spec), project_canon_dir=str(canon))]
    assert codes == ["E607"]


# ---------------------------------------------------------------------------
# H-256-1: the lint reads the project tier through the registry loader
# ---------------------------------------------------------------------------

def test_manifest_only_project_canon_is_checked(tmp_path):
    spec, canon = _term_canon(
        tmp_path,
        _term("term-foo", "Edited definition.", _FOO),
        _canon_entry(_FOO, "Accepted definition."),
    )
    assert not (canon / "kinds").exists()
    (e607,) = _e607(spec, canon)
    assert "term-foo" in e607.message


def test_orphans_come_from_the_same_loaded_entries(tmp_path):
    spec = tmp_path / "spec"
    canon = spec / "canon"
    _write(spec / "03_glossary.json", _glossary())
    _write(canon / "kinds" / "term.json", _kinds_term_file([_canon_entry(_FOO, "Orphan.")]))
    (w606,) = lint_glossary_drift(str(spec), project_canon_dir=str(canon))
    assert w606.code == "W606"
