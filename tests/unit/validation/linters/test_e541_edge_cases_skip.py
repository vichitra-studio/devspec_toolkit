"""Bug 3 regression: Step 11 edge_cases[].description must be exempt from
E541 UNBOUND_CANONICAL_TERM scanning.

The edge_cases item schema sets additionalProperties: false and defines no
*_ref fields, so the linter cannot demand a canonical binding that is
structurally impossible to express.
"""
from specdev_tools.validation.hallucination_lint import _check_free_text_terms


def _codes(errs):
    return [e.code for e in errs]


def test_edge_case_description_exempt_from_e541():
    canonical_terms = {
        "post": {"cn:project:term:post"},
        "theme": {"cn:project:term:theme"},
    }
    obj = {
        "edge_cases": [
            {
                "id": "ec-01",
                "description": "Publishing a post without a theme causes a 500",
            },
            {
                "id": "ec-02",
                "description": "Theme upload with malformed archive",
            },
        ]
    }
    errs = _check_free_text_terms("11_redteam.json", obj, canonical_terms)
    assert "E541" not in _codes(errs), f"edge_cases must skip E541 scan: {[e.render() for e in errs]}"


def test_non_edge_case_field_still_flagged():
    """Sanity: exemption is scoped to edge_cases, not a global disable."""
    canonical_terms = {"post": {"cn:project:term:post"}}
    obj = {
        "threats": [
            {"threat_id": "t-01", "description": "An attacker modifies a post record"}
        ]
    }
    errs = _check_free_text_terms("11_redteam.json", obj, canonical_terms)
    assert "E541" in _codes(errs)


def test_edge_case_skip_with_subdirectory_rel_path():
    """Regression: _is_e541_skipped must use basename, not raw rel string,
    so that a nested rel like ``sub/11_redteam.json`` still hits the skip."""
    from specdev_tools.validation.hallucination_lint import _is_e541_skipped
    assert _is_e541_skipped("sub/11_redteam.json", "edge_cases") is True
    assert _is_e541_skipped("11_redteam.json", "edge_cases") is True
    assert _is_e541_skipped("other.json", "edge_cases") is False


def test_other_file_edge_cases_still_flagged():
    """Bug 3 follow-up: the ``edge_cases`` skip is scoped to 11_redteam.json.
    A hypothetical future step that introduces a literal ``edge_cases`` key
    must NOT inherit the exemption silently.
    """
    canonical_terms = {"post": {"cn:project:term:post"}}
    obj = {"edge_cases": [{"description": "Editing a post at the rate limit"}]}
    errs = _check_free_text_terms("99_future_step.json", obj, canonical_terms)
    assert "E541" in _codes(errs), "edge_cases skip must be scoped to 11_redteam.json"


# ---------------------------------------------------------------------------
# Step 16a/16b: actions[] and coding_examples[] E541 skip (Bug 3 — global)
# ---------------------------------------------------------------------------

def test_actions_description_exempt_from_e541():
    """Bug 3 regression: actions[].description must not fire E541.
    Step 16a schema defines no *_ref field on action items; the linter
    cannot demand a canonical binding that the schema cannot express."""
    canonical_terms = {
        "post": {"cn:project:term:post"},
        "ghost": {"cn:project:term:ghost"},
    }
    obj = {
        "actions": [
            {
                "type": "file_edit",
                "description": "Add Ghost post import handler to bootstrap.sh",
            },
            {
                "type": "manual_verification",
                "description": "Verify post count matches demo-content.json seed",
            },
        ]
    }
    errs = _check_free_text_terms("impl_context/ms_bootstrap_local_ghost_plan.json", obj, canonical_terms)
    assert "E541" not in _codes(errs), f"actions subtree must skip E541: {[e.render() for e in errs]}"


def test_actions_skip_applies_globally():
    """The actions skip is global (not scoped to a specific filename) because
    Step 16a artifacts have variable names in impl_context/."""
    canonical_terms = {"post": {"cn:project:term:post"}}
    obj = {"actions": [{"type": "file_edit", "description": "Edit post template"}]}
    for rel in ("impl_context/any_plan.json", "16_impl_context.json", "16a_plan.json"):
        errs = _check_free_text_terms(rel, obj, canonical_terms)
        assert "E541" not in _codes(errs), (
            f"actions skip must be global (failed for rel={rel!r}): {[e.render() for e in errs]}"
        )


def test_coding_examples_description_exempt_from_e541():
    """coding_examples[].description must not fire E541 — code examples
    demonstrate patterns and have no *_ref field in the schema."""
    canonical_terms = {"theme": {"cn:project:term:theme"}}
    obj = {
        "coding_examples": [
            {
                "title": "Theme upload",
                "description": "Shows how to upload a theme via the Ghost Admin API",
                "code": "curl -X POST ...",
            }
        ]
    }
    errs = _check_free_text_terms("impl_context/ms_bootstrap_local_ghost_plan.json", obj, canonical_terms)
    assert "E541" not in _codes(errs), (
        f"coding_examples subtree must skip E541: {[e.render() for e in errs]}"
    )


def test_non_actions_field_still_flagged_in_16a():
    """Sanity: exemption is scoped to actions/coding_examples subtrees.
    A top-level description in a Step 16a artifact must still fire E541."""
    canonical_terms = {"post": {"cn:project:term:post"}}
    obj = {"description": "Implements the post bootstrap flow"}
    errs = _check_free_text_terms("impl_context/ms_plan.json", obj, canonical_terms)
    assert "E541" in _codes(errs), (
        "top-level description in Step 16a must still fire E541"
    )


# ---------------------------------------------------------------------------
# End-to-end test via the public ``lint_hallucinations`` entrypoint.
#
# The unit tests above exercise ``_check_free_text_terms`` directly.  This
# test builds a minimal tmp-dir spec tree and invokes the public entrypoint
# so the full orchestration path (canon load → term index build → per-file
# scan) is covered.  A regression where the orchestration pre-processes
# or bypasses the edge_cases subtree would surface here.
# ---------------------------------------------------------------------------
import json
import tempfile
from pathlib import Path

from specdev_tools.validation.hallucination_lint import lint_hallucinations


def _render(errs):
    return [e.render() for e in errs]


def _write_minimal_canon_with_post_term(root: Path) -> None:
    canon = root / "canon"
    canon.mkdir()
    canon_entry = {
        "id": "cn:project:term:post",
        "kind": "term",
        "preferred_label": "post",
        "version": "1.0.0",
        "status": "active",
        "aliases": [],
        "lifecycle": {"introduced_at": "2026-02-21T00:00:00Z"},
    }
    (canon / "manifest.json").write_text(
        json.dumps({
            "registry_version": "1.0.0",
            "entries": [canon_entry],
            "aliases": [],
        }),
        encoding="utf-8",
    )


def test_lint_hallucinations_skips_edge_cases_in_11_redteam_end_to_end():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_minimal_canon_with_post_term(root)
        spec = root / "spec"
        spec.mkdir()
        (spec / "11_redteam.json").write_text(
            json.dumps({
                "threats": [],
                "edge_cases": [
                    {
                        "id": "ec-01",
                        "description": "Editing a post at the rate limit boundary",
                    }
                ],
            }),
            encoding="utf-8",
        )
        errs = lint_hallucinations(
            str(spec),
            repo_root=str(root),
            require_manifest_schema_registration=False,
        )
        rendered = _render(errs)
        assert not any("E541" in r and "edge_cases" in r for r in rendered), (
            f"edge_cases in 11_redteam.json must be exempt end-to-end: {rendered}"
        )


def test_lint_hallucinations_still_flags_non_exempt_fields_end_to_end():
    """Sanity check for the e2e fixture: a non-exempt field in the same file
    must still fire E541, proving the canon term index is actually loaded."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_minimal_canon_with_post_term(root)
        spec = root / "spec"
        spec.mkdir()
        (spec / "11_redteam.json").write_text(
            json.dumps({
                "threats": [
                    {
                        "threat_id": "t-01",
                        "description": "An attacker modifies a post record via IDOR",
                    }
                ],
                "edge_cases": [],
            }),
            encoding="utf-8",
        )
        errs = lint_hallucinations(
            str(spec),
            repo_root=str(root),
            require_manifest_schema_registration=False,
        )
        rendered = _render(errs)
        assert any("E541" in r and "post" in r for r in rendered), (
            f"non-exempt field with canonical term must still fire E541: {rendered}"
        )


# ---------------------------------------------------------------------------
# End-to-end tests for actions / coding_examples E541 skip via the public
# lint_hallucinations entrypoint (Bug 3 — Step 16a/16b global skip).
#
# The unit tests above exercise _check_free_text_terms directly.  These tests
# drive the full orchestration path: canon load → term index build → per-file
# scan → E541 skip, so a regression where the skip is bypassed at any layer
# will be caught here.
# ---------------------------------------------------------------------------

def test_lint_hallucinations_skips_actions_e541_end_to_end():
    """actions[].description must not fire E541 via the public entrypoint.
    Full orchestration: canon load → term index → per-file scan → skip."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_minimal_canon_with_post_term(root)
        spec = root / "spec"
        spec.mkdir()
        (spec / "16a_plan.json").write_text(
            json.dumps({
                "actions": [
                    {
                        "type": "file_edit",
                        "description": "Add Ghost post import handler to bootstrap.sh",
                    },
                    {
                        "type": "manual_verification",
                        "description": "Verify post count matches demo-content.json",
                    },
                ]
            }),
            encoding="utf-8",
        )
        errs = lint_hallucinations(
            str(spec),
            repo_root=str(root),
            require_manifest_schema_registration=False,
        )
        rendered = _render(errs)
        assert not any("E541" in r for r in rendered), (
            f"actions subtree must be exempt from E541 end-to-end: {rendered}"
        )


def test_lint_hallucinations_skips_coding_examples_e541_end_to_end():
    """coding_examples[].description must not fire E541 via the public entrypoint."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_minimal_canon_with_post_term(root)
        spec = root / "spec"
        spec.mkdir()
        (spec / "16a_plan.json").write_text(
            json.dumps({
                "coding_examples": [
                    {
                        "title": "Post import",
                        "description": "Shows how to import a post via Ghost Admin API",
                        "code": "curl -X POST ...",
                    }
                ]
            }),
            encoding="utf-8",
        )
        errs = lint_hallucinations(
            str(spec),
            repo_root=str(root),
            require_manifest_schema_registration=False,
        )
        rendered = _render(errs)
        assert not any("E541" in r for r in rendered), (
            f"coding_examples subtree must be exempt from E541 end-to-end: {rendered}"
        )


def test_lint_hallucinations_top_level_description_still_flags_e541_end_to_end():
    """Sanity: the actions/coding_examples exemption is scoped to those subtrees.
    A top-level description in the same artifact must still fire E541."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_minimal_canon_with_post_term(root)
        spec = root / "spec"
        spec.mkdir()
        (spec / "16a_plan.json").write_text(
            json.dumps({
                "description": "Implements the post bootstrap flow",
                "actions": [],
            }),
            encoding="utf-8",
        )
        errs = lint_hallucinations(
            str(spec),
            repo_root=str(root),
            require_manifest_schema_registration=False,
        )
        rendered = _render(errs)
        assert any("E541" in r and "post" in r for r in rendered), (
            f"top-level description in Step 16a artifact must still fire E541: {rendered}"
        )
