"""Tests for the contract view and the node-level diff (WI-M4-10): the diff over parsed documents, no git."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

import pytest

from specdev_tools.graph.contract import contract_view, item_at, normalise_text
from specdev_tools.graph.diff import (
    ADDED,
    CHANGED,
    KIND,
    LIFECYCLE,
    MAJOR,
    MINOR,
    NO_BUMP,
    PATCH,
    REMOVED,
    GraphDiff,
    NodeChange,
    diff_snapshots,
    diff_to_dict,
    render_text,
    suggest_bump,
)
from specdev_tools.graph.gitview import Snapshot
from specdev_tools.graph.model import Graph, Node

from ._synth import docs_graph

_FR_FILE = "04_fr_list.json"
_TASK_FILE = "14_roadmap.json"


def _criterion(criterion_id: str, text: str) -> dict[str, Any]:
    return {"criterion_id": criterion_id, "text": text}


def _fr(fr_id: str, statement: str, **extra: Any) -> dict[str, Any]:
    return {"fr_id": fr_id, "statement": statement, **extra}


def _docs(*requirements: dict[str, Any]) -> dict[str, Any]:
    return {_FR_FILE: {"functional_requirements": list(requirements)}}


def _snapshot(docs: Mapping[str, Any]) -> Snapshot:
    return Snapshot(docs_graph(docs), {})


def _diff(old: Mapping[str, Any], new: Mapping[str, Any]) -> GraphDiff:
    return diff_snapshots(_snapshot(old), _snapshot(new))


def _changes_by_id(diff: GraphDiff) -> dict[str, tuple[str, ...]]:
    return {change.id: change.changes for change in diff.changes}


def test_diff_added_removed_changed() -> None:
    old = _docs(_fr("fr-kept", "The system shall keep."), _fr("fr-gone", "The system shall go."))
    new = _docs(_fr("fr-kept", "The system shall keep for ninety days."), _fr("fr-new", "The system shall add."))
    diff = _diff(old, new)
    assert _changes_by_id(diff) == {"fr-gone": (REMOVED,), "fr-kept": (CHANGED,), "fr-new": (ADDED,)}


def test_diff_relink_is_a_change() -> None:
    old = _docs(_fr("fr-a", "The system shall do a.", derives_from=["cap-one"]))
    new = _docs(_fr("fr-a", "The system shall do a.", derives_from=["cap-two"]))
    assert _changes_by_id(_diff(old, new)) == {"fr-a": (CHANGED,)}


def test_diff_lifecycle_only_is_patch() -> None:
    old = _docs(_fr("fr-a", "The system shall do a."))
    new = _docs(_fr("fr-a", "The system shall do a.", lifecycle="deprecated"))
    diff = _diff(old, new)
    assert diff.changes == (NodeChange("fr-a", "fr", "obligation-system", (LIFECYCLE,), lifecycle=("active", "deprecated")),)
    assert diff.bump == PATCH


def test_bump_major_on_removed_obligation() -> None:
    old = _docs(_fr("fr-a", "The system shall do a."), _fr("fr-b", "The system shall do b."))
    diff = _diff(old, _docs(_fr("fr-a", "The system shall do a.")))
    assert (diff.bump, _changes_by_id(diff)) == (MAJOR, {"fr-b": (REMOVED,)})


def test_bump_major_on_a_new_removes_link() -> None:
    def roadmap(removes: list[str]) -> dict[str, Any]:
        criterion = {**_criterion("tc-a", "Done."), "removes": removes}
        task = {"task_id": "task-a", "description": "Do it.", "acceptance_criteria": [criterion]}
        return {_TASK_FILE: {"milestones": [{"milestone_id": "ms-a", "tasks": [task]}]}}

    diff = _diff(roadmap([]), roadmap(["ac-old"]))
    assert diff.new_removes == (("tc-a", "ac-old"),)
    assert diff.bump == MAJOR


def test_bump_minor_on_added_criterion() -> None:
    old = _docs(_fr("fr-a", "The system shall do a.", acceptance_criteria=[_criterion("ac-1", "It works.")]))
    new = _docs(_fr("fr-a", "The system shall do a.", acceptance_criteria=[_criterion("ac-1", "It works."), _criterion("ac-2", "It is fast.")]))
    diff = _diff(old, new)
    assert _changes_by_id(diff) == {"ac-2": (ADDED,), "fr-a": (CHANGED,)}
    assert diff.bump == MINOR


def test_text_normalisation_ignores_whitespace_quotes() -> None:
    old = _docs(_fr("fr-a", 'The system shall reject "bad"  input - always.'))
    new = _docs(_fr("fr-a", "The system shall reject “bad”\n input – always. "))
    diff = _diff(old, new)
    assert (diff.changes, diff.bump) == ((), NO_BUMP)


_NA = "not_applicable"


def _fr_with(lifecycle: str | None, statement: str = "Stays.") -> dict[str, Any]:
    return _fr("fr-x", statement, **({"lifecycle": lifecycle} if lifecycle else {}))


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ((None, "Stays."), ("deprecated", "Stays."), {"fr-x": (LIFECYCLE,)}),
        ((None, "Stays."), (_NA, "Stays."), {"fr-x": (LIFECYCLE,)}),
        ((_NA, "Stays."), (None, "Stays."), {"fr-x": (LIFECYCLE,)}),
        ((_NA, "Old."), (_NA, "New."), {}),
        ((None, "Old."), ("deprecated", "New."), {"fr-x": (LIFECYCLE, CHANGED)}),
    ],
)
def test_diff_honours_lifecycle(old: tuple[str | None, str], new: tuple[str | None, str], expected: dict[str, tuple[str, ...]]) -> None:
    assert _changes_by_id(_diff(_docs(_fr_with(*old)), _docs(_fr_with(*new)))) == expected


@pytest.mark.parametrize("lifecycle", [_NA, "active"])
def test_diff_added_or_removed_not_applicable_node_is_left_out(lifecycle: str) -> None:
    gone, here = _docs(_fr_with(lifecycle)), _docs()
    expected = {} if lifecycle == _NA else {"fr-x": (REMOVED,)}
    assert _changes_by_id(_diff(gone, here)) == expected
    assert _changes_by_id(_diff(here, gone)) == ({} if lifecycle == _NA else {"fr-x": (ADDED,)})


def test_diff_lifecycle_to_not_applicable_is_patch_for_an_obligation() -> None:
    assert _diff(_docs(_fr_with(None)), _docs(_fr_with(_NA))).bump == PATCH


def test_diff_reports_a_kind_change() -> None:
    old = _snapshot(_docs(_fr("shared-id", "The system shall do it.")))
    new = _snapshot({"01_capabilities.json": {"capabilities": [{"capability_id": "shared-id", "description": "A thing."}]}})
    (change,) = diff_snapshots(old, new).changes
    assert (change.id, change.kind, change.old_kind) == ("shared-id", "capability", "fr")
    assert KIND in change.changes


@pytest.mark.parametrize(
    ("old", "new", "bump"),
    [
        ({_FR_FILE: {"functional_requirements": [{"fr_id": "same-id"}]}}, {"00_charter.json": {"assumptions": [{"assumption_id": "same-id"}]}}, MAJOR),
        ({"00_charter.json": {"assumptions": [{"assumption_id": "same-id"}]}}, {"03_glossary.json": {"terms": [{"term_id": "same-id"}]}}, PATCH),
        ({"00_charter.json": {"assumptions": [{"assumption_id": "same-id"}]}}, {_FR_FILE: {"functional_requirements": [{"fr_id": "same-id"}]}}, MINOR),
    ],
)
def test_kind_change_bump_follows_the_obligation_role(old: dict[str, Any], new: dict[str, Any], bump: str) -> None:
    diff = _diff(old, new)
    assert KIND in diff.changes[0].changes
    assert diff.bump == bump


def test_a_node_that_stops_being_obligation_follows_the_removed_rule() -> None:
    stops = NodeChange("x", "k", "context", (KIND,), old_kind="fr", old_role="obligation-system")
    starts = NodeChange("x", "fr", "obligation-system", (KIND,), old_kind="k", old_role="context")
    plain = NodeChange("x", "k", "context", (KIND,), old_kind="j", old_role="context")
    assert [suggest_bump((c,), ()) for c in (stops, starts, plain)] == [MAJOR, MINOR, PATCH]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a \t b\n\nc ", "a b c"),
        ("‘x’ “y” „z‟", "'x' \"y\" \"z\""),
        ("a‐b‑c‒d–e—f―g−h", "a-b-c-d-e-f-g-h"),
        ("café", "café"),
        ("The system MUST", "The system MUST"),
    ],
)
def test_normalise_text(raw: str, expected: str) -> None:
    assert normalise_text(raw) == expected


def test_normalise_text_keeps_case_as_a_difference() -> None:
    assert normalise_text("MUST") != normalise_text("must")


def test_contract_view_maps_aliases_so_a_rename_changes_no_view() -> None:
    before = _snapshot(_docs(_fr("fr-a", "Do a.", derives_from=["cap-old"])))
    after = _snapshot(_docs(_fr("fr-a", "Do a.", derives_from=["cap-new"])))
    old_node, new_node = before.graph.by_id["fr-a"], after.graph.by_id["fr-a"]
    assert contract_view(old_node, before.graph) != contract_view(new_node, after.graph)
    renamed = contract_view(old_node, before.graph, {"cap-old": "cap-new"})
    assert renamed == contract_view(new_node, after.graph)


@pytest.mark.parametrize("field", ["status", "notes", "tags", "owner"])
def test_contract_view_ignores_status_notes_tags_and_owner(field: str) -> None:
    old = _docs(_fr("fr-a", "Do a."))
    new = _docs(_fr("fr-a", "Do a.", **{field: "something"}))
    assert _diff(old, new).changes == ()


def test_contract_view_of_an_fr_folds_its_criteria() -> None:
    snapshot = _snapshot(_docs(_fr("fr-a", "Do a.", acceptance_criteria=[_criterion("ac-1", "It  works.")])))
    view = contract_view(snapshot.graph.by_id["fr-a"], snapshot.graph)
    assert view["criteria"] == {"ac-1": {"fields": {"text": "It works."}, "links": {}}}
    criterion_view = contract_view(snapshot.graph.by_id["ac-1"], snapshot.graph)
    assert "criteria" not in criterion_view


@pytest.mark.parametrize(
    ("jq_path", "found"),
    [
        (".a[1].b", {"c": 1}),
        ('.m["k.x"]', {"d": 2}),
        (".a[5]", None),
        (".a[0]", None),
        (".missing", None),
        ("a", None),
    ],
)
def test_item_at(jq_path: str, found: dict[str, int] | None) -> None:
    document = {"a": [1, {"b": {"c": 1}}], "m": {"k.x": {"d": 2}}}
    assert item_at(document, jq_path) == found


@pytest.mark.parametrize("statement", [None, 5, ["x"], {"k": "v"}])
def test_contract_view_does_not_raise_on_a_wrong_value(statement: Any) -> None:
    docs = _docs(_fr("fr-a", "Do a.", acceptance_criteria=[_criterion("ac-1", "ok")]))
    broken = copy.deepcopy(docs)
    broken[_FR_FILE]["functional_requirements"][0]["statement"] = statement
    broken[_FR_FILE]["functional_requirements"][0]["acceptance_criteria"] = [statement, _criterion("ac-1", statement)]
    assert isinstance(_diff(docs, broken), GraphDiff)


def test_suggest_bump_for_each_class() -> None:
    def change(role: str | None, *names: str) -> NodeChange:
        return NodeChange("x", "k", role, names)

    assert suggest_bump((), ()) == NO_BUMP
    assert suggest_bump((change("context", REMOVED),), ()) == PATCH
    assert suggest_bump((change("obligation-delivery", ADDED),), ()) == PATCH
    assert suggest_bump((change("obligation-system", LIFECYCLE),), ()) == PATCH
    assert suggest_bump((change("obligation-system", CHANGED),), ()) == MINOR
    assert suggest_bump((change("obligation-system", REMOVED), change("obligation-system", ADDED)), ()) == MAJOR
    assert suggest_bump((), (("a", "b"),)) == MAJOR


def test_render_text_and_json_group_by_role_and_kind() -> None:
    old = _docs(_fr("fr-a", "Do a."), _fr("fr-gone", "Gone."))
    new = _docs(_fr("fr-a", "Do a.", lifecycle="deprecated"), _fr("fr-b", "Do b."))
    diff = diff_snapshots(_snapshot(old), _snapshot(new))
    text = render_text(diff)
    assert "obligation-system / fr" in text
    assert "fr-a: lifecycle active -> deprecated" in text
    assert "fr-gone: removed" in text and "suggested bump: major" in text
    payload = diff_to_dict(diff)
    assert payload["bump"] == MAJOR
    assert [(g["role"], g["kind"], [n["id"] for n in g["nodes"]]) for g in payload["groups"]] == [
        ("obligation-system", "fr", ["fr-a", "fr-b", "fr-gone"])
    ]


def test_contract_view_of_a_hand_made_graph_has_no_fields() -> None:
    node = Node("n", "fr", "04", "obligation-system", "x.json", ".a[0]", None, (), "active", None, (), "")
    assert contract_view(node, Graph.from_nodes([node])) == {"fields": {}, "links": {}, "criteria": {}}


def test_build_graph_keeps_its_documents_and_declarations() -> None:
    graph = docs_graph(_docs(_fr("fr-a", "Do a.")))
    assert graph.documents[_FR_FILE]["functional_requirements"][0]["fr_id"] == "fr-a"
    assert graph.decls["fr"].kind == "fr" and graph.decls["criterion"].kind == "criterion"
