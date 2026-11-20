"""``specdev coverage``: the reverse index, the three link counts, the FR matrix and the role findings (WI-M5-14)."""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.trace.coverage import (
    REFINED_CURRENT,
    REFINED_NONE,
    REFINED_STALE,
    CriterionRow,
    FrRow,
    LinkRow,
    build_fr_matrix,
    build_report,
    exemption,
    link_counts,
)
from specdev_tools.trace.gaps import CoverageGap
from specdev_tools.trace.lockfile import Lock
from specdev_tools.validation.traceability_closure import check_traceability_closure, uncomputed_dimensions

from ..graph._synth import ROOT, docs_graph, run_cli
from ._lock_support import EXAMPLE_HOST, gap_providers  # noqa: F401  (a fixture)
from .test_suspects import Example

FR, FR_REQUEST = "fr-password-reset", "fr-password-reset-request"
FR_FILE = "04_fr_list.json"
FIXTURE_FILE = "08_fixtures.json"
CRITERION = "ac-password-reset-3"
CLOSED_REFINEMENT = "tc-confirm-expired-token"
EXPIRED_FIXTURE = "fix-password-reset-expired-token"


@pytest.fixture
def example(tmp_path: Path, gap_providers: Any) -> Example:
    """The worked example in a copy.  No coverage-gap provider is registered (the ``gap_providers`` fixture clears them): the
    role gaps the real graph checks report on this partial example are not the subject of these tests."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    return Example(host)


def _matrix(example: Example) -> dict[str, FrRow]:
    graph = example.graph()
    return {row.id: row for row in build_fr_matrix(graph, example.lock(), example.seed_texts(graph))}


def _criterion(row: FrRow, criterion_id: str) -> CriterionRow:
    return next(criterion for criterion in row.criteria if criterion.id == criterion_id)


def _links(groups: tuple[tuple[str, tuple[LinkRow, ...]], ...], kind: str) -> dict[str, LinkRow]:
    return {link.node: link for group_kind, links in groups if group_kind == kind for link in links}


def _edit_file(example: Example, rel: str, change: Callable[[dict[str, Any]], None]) -> None:
    path = example.spec / rel
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _fr_item(document: dict[str, Any], fr_id: str) -> dict[str, Any]:
    return next(item for item in document["functional_requirements"] if item["fr_id"] == fr_id)


def _run_coverage(example: Example, *flags: str) -> tuple[int, str]:
    return run_cli("coverage", "--repo-root", str(ROOT), "--spec-root", str(example.spec), "--git-root", str(example.host), *flags)


# --- the matrix and the reverse index -------------------------------------------------------------------------------

def test_by_fr_counts_direct_links_only(example: Example) -> None:
    """DEVSPEC-255: a fixture that verifies the API of an FR, and no criterion of it, is not listed under the FR."""
    row = _matrix(example)[FR]
    assert EXPIRED_FIXTURE in _links(row.groups, "fixture") or EXPIRED_FIXTURE in _links(_criterion(row, CRITERION).groups, "fixture")
    _edit_file(example, FIXTURE_FILE, lambda doc: doc["fixtures"][0].update(verifies=["api-password-reset-confirm"]))
    row = _matrix(example)[FR]
    listed = {link.node for groups in (row.groups, *(criterion.groups for criterion in row.criteria)) for _kind, links in groups for link in links}
    assert EXPIRED_FIXTURE not in listed
    assert "api-password-reset-confirm" in _links(row.groups, "api")
    counts = dict(link_counts(example.graph()))
    assert counts["fr_fixture_coverage"].unlinked == (FR, FR_REQUEST)


def test_a_link_is_current_while_its_lock_entry_holds_the_content_hash_of_the_target(example: Example) -> None:
    example.close_milestone()
    row = _matrix(example)[FR]
    assert all(link.current and not link.suspect for _kind, links in row.groups for link in links)
    refinement = _links(_criterion(row, CRITERION).groups, "task-criterion")[CLOSED_REFINEMENT]
    assert refinement.current and refinement.historical and refinement.field == "refines"
    assert _criterion(row, CRITERION).refined == REFINED_CURRENT
    assert _criterion(row, "ac-password-reset-1").refined == REFINED_NONE


def test_changed_obligation_is_uncovered_until_refined_again(example: Example) -> None:
    example.close_milestone()
    example.edit_criterion()
    row = _matrix(example)[FR]
    criterion = _criterion(row, CRITERION)
    refinement = _links(criterion.groups, "task-criterion")[CLOSED_REFINEMENT]
    assert not refinement.current and refinement.historical and not refinement.suspect
    assert criterion.refined == REFINED_STALE
    graph = example.graph()
    report = build_report(graph, example.lock(), example.seed_texts(graph))
    assert CRITERION in report.criteria_refined.unlinked and report.criteria_refined.linked == 0
    code, out = _run_coverage(example)
    assert code == 0 and "E7" not in out


def test_a_live_suspect_link_is_listed_and_marked(example: Example) -> None:
    example.edit_criterion()
    row = _matrix(example)[FR]
    fixture_link = _links(_criterion(row, CRITERION).groups, "fixture")[EXPIRED_FIXTURE]
    assert fixture_link.suspect and not fixture_link.historical and not fixture_link.current


def test_deleted_then_readded_closed_refinement_is_not_current(example: Example) -> None:
    """The ``coverage`` half of WI-09's re-added-id test: the criterion is deleted and inserted again with new text."""
    example.close_milestone()

    def readd(document: dict[str, Any]) -> None:
        criteria = _fr_item(document, FR)["acceptance_criteria"]
        old = next(item for item in criteria if item["criterion_id"] == CRITERION)
        criteria.remove(old)
        criteria.append({**old, "text": "Given any reset token, when it is used twice, then the second use is refused."})

    _edit_file(example, FR_FILE, readd)
    criterion = _criterion(_matrix(example)[FR], CRITERION)
    assert not _links(criterion.groups, "task-criterion")[CLOSED_REFINEMENT].current
    assert criterion.refined == REFINED_STALE


# --- the three link counts ------------------------------------------------------------------------------------------

def _capability(cap_id: str, scope: str = "in") -> dict[str, Any]:
    return {"capability_id": cap_id, "scope": scope, "verb": "do", "description": cap_id, "derives_from": []}


def _fr(fr_id: str, cap_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "fr_id": fr_id, "priority": "must-have", "scope": "in", "statement": fr_id, "derives_from": [cap_id],
        "acceptance_criteria": [{"criterion_id": f"ac-{fr_id}", "scope": "in", "text": f"{fr_id} works."}], **extra,
    }


GRAPH_CAPABILITIES = [_capability("cap-a"), _capability("cap-b"), _capability("cap-parked", "later")]
GRAPH_FRS = [_fr("fr-a", "cap-a"), _fr("fr-b", "cap-a"), _fr("fr-c", "cap-a")]
GRAPH_DOCS = {
    "01_capabilities.json": {"capabilities": GRAPH_CAPABILITIES},
    FR_FILE: {"functional_requirements": GRAPH_FRS},
    "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "derives_from": ["fr-a", "fr-b"], "scope": "in"}]},
    FIXTURE_FILE: {"fixtures": [{"fixture_id": "fix-a", "verifies": ["ac-fr-a"]}]},
}
LEGACY_DOCS = {
    "01_capabilities.json": {"capabilities": [
        {"capability_id": "cap-a", "scope": "in", "trace": []}, {"capability_id": "cap-b", "scope": "in", "trace": []},
        {"capability_id": "cap-parked", "scope": "later", "trace": []}]},
    FR_FILE: {"$schema": "vc:04_fr_list", "functional_requirements": [
        {"fr_id": fr_id, "priority": "must-have", "trace": [{"type": "capability", "id": "cap-a"}]} for fr_id in ("fr-a", "fr-b", "fr-c")]},
    "05_interface_contracts.json": {"apis": [{"api_id": "api-a", "trace": [{"type": "fr", "id": "fr-a"}, {"type": "fr", "id": "fr-b"}]}]},
    FIXTURE_FILE: {"fixtures": [{"fixture_id": "fix-a", "targets": [{"type": "fr", "id": "fr-a"}]}]},
}
LEGACY_LABELS = {"fr_api_coverage": "UNCOVERED_FR_API", "fr_fixture_coverage": "UNCOVERED_FR_FIXTURE", "capability_fr_coverage": "UNCOVERED_CAPABILITY"}


def _legacy_unlinked(spec_dir: Path) -> dict[str, set[str]]:
    """The ids ``completeness-check`` finds uncovered on a 1.1.1-shaped spec folder, by dimension."""
    findings = [error.message for error in check_traceability_closure(str(spec_dir)) if isinstance(error, SpecError)]
    return {name: {message.split()[1] for message in findings if message.startswith(label)} for name, label in LEGACY_LABELS.items()}


def test_three_dimensions_match_the_legacy_completeness_check_on_the_equivalent_fixture(tmp_path: Path) -> None:
    """The legacy side is 1.1.1-shaped (``trace``, ``targets``): on a graph-shaped spec the dimension is listed as not computed."""
    spec_dir = tmp_path / "legacy"
    spec_dir.mkdir()
    for name, document in LEGACY_DOCS.items():
        (spec_dir / name).write_text(json.dumps(document), encoding="utf-8")
    assert uncomputed_dimensions(str(spec_dir)) == []
    legacy = _legacy_unlinked(spec_dir)
    assert legacy == {"fr_api_coverage": {"fr-c"}, "fr_fixture_coverage": {"fr-b", "fr-c"}, "capability_fr_coverage": {"cap-b"}}
    counts = dict(link_counts(docs_graph(GRAPH_DOCS)))
    assert {name: set(dimension.unlinked) for name, dimension in counts.items()} == legacy
    assert {name: dimension.total for name, dimension in counts.items()} == {"fr_api_coverage": 3, "fr_fixture_coverage": 3, "capability_fr_coverage": 2}


def test_scope_later_out_and_not_applicable_excluded_and_listed() -> None:
    """Hand-off case 10 of M4: ``fr-login`` states ``scope: out`` (no fixture): it leaves the denominator and is listed under ``exempt``."""
    frs = [_fr("fr-a", "cap-a"), _fr("fr-login", "cap-a", scope="out", scope_reason="handled by the identity provider"),
           _fr("fr-later", "cap-a", scope="later"), _fr("fr-gone", "cap-a", lifecycle="not_applicable")]
    docs = {**GRAPH_DOCS, FR_FILE: {"functional_requirements": frs}}
    graph = docs_graph(docs)
    report = build_report(graph, Lock(), {})
    counts = dict(report.dimensions)
    assert counts["fr_fixture_coverage"].total == 1 and counts["fr_fixture_coverage"].unlinked == ()
    assert counts["capability_fr_coverage"].total == 2 and counts["capability_fr_coverage"].unlinked == ("cap-b",)
    reasons = {item.id: item.reason for item in report.exempt}
    assert reasons == {
        "fr-login": "scope_out", "ac-fr-login": "scope_out", "fr-later": "scope_later", "ac-fr-later": "scope_later",
        "fr-gone": "not_applicable", "ac-fr-gone": "not_applicable", "cap-parked": "scope_later",
    }
    assert [row.id for row in build_fr_matrix(graph, Lock(), {})] == ["fr-a"]
    assert exemption(graph.by_id["fr-a"]) is None


# --- role findings --------------------------------------------------------------------------------------------------

def test_role_findings_section_empty_without_provider_and_grouped_with_stub(example: Example, gap_providers: Any) -> None:
    graph = example.graph()
    empty = build_report(graph, example.lock(), example.seed_texts(graph))
    assert empty.gaps_by_step == () and empty.gap_counts == ()
    gap_providers(lambda _graph, _lock: [CoverageGap("E743", "fix-b", "08"), CoverageGap("E740", "fr-z", "04"), CoverageGap("E740", "fr-a", "04")])
    report = build_report(graph, example.lock(), example.seed_texts(graph))
    assert report.gaps_by_step == (("04", (("E740", "fr-a"), ("E740", "fr-z"))), ("08", (("E743", "fix-b"),)))
    assert report.gap_counts == (("E740", 2), ("E743", 1))
    code, out = _run_coverage(example, "--json")
    assert code == 0
    assert json.loads(out)["role_findings"]["counts"] == {"E740": 2, "E743": 1}


def test_coverage_command_emits_no_error_for_fr_without_api(example: Example) -> None:
    """An in-scope FR with no API shows as unlinked; the exit code is 0 and no finding is printed (the role rules are M6b's)."""
    code, out = _run_coverage(example)
    assert code == 0 and "E7" not in out
    assert f"unlinked: {FR_REQUEST}" in out
    code, out = _run_coverage(example, "--json")
    assert code == 0
    assert json.loads(out)["counts"]["fr_api_coverage"] == {"linked": 1, "total": 2, "ratio": 0.5, "unlinked": [FR_REQUEST]}
