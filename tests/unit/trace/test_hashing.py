"""Tests for the content hash and chain stamp (WI-M5-02) over the worked example and synthetic graphs."""
from __future__ import annotations

import copy
import time
import unicodedata
from collections.abc import Callable, Collection, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.contract import item_at
from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import Graph, Link, Node, first_name_index
from specdev_tools.trace.hashing import (
    HASH_PREFIX,
    chain_stamp,
    compute_all,
    content_hash,
    own_hash,
    seed_hash,
)

ROOT = Path(__file__).parents[3]
EXAMPLE_SPEC = str(ROOT / "tests" / "fixtures" / "graph_example" / "spec")
SEED_TEXT = "Members reset their password through an emailed link.\nThe link works once."
SEEDS = {"seed-accounts": SEED_TEXT}
FR, CAP, SCOPE, SEED = "fr-password-reset", "cap-account-recovery", "scope-password-reset", "seed-accounts"
CRITERIA = ("ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-3")
TASK_CRITERION = "tc-confirm-expired-token"
FR_FILE, CAP_FILE, SCOPE_FILE = "04_fr_list.json", "01_capabilities.json", "00_charter.json"
_LINK = LinkDecl("derives_from", ("*",), False, True, ())

Edit = Callable[[dict[str, Any]], None]


def _base() -> Graph:
    return build_graph(EXAMPLE_SPEC, str(ROOT))


def _edited_graph(file: str, edit: Edit) -> Graph:
    """The worked example with *edit* applied to the parsed document *file*."""
    document = copy.deepcopy(dict(_base().documents[file]))
    edit(document)
    return build_graph(EXAMPLE_SPEC, str(ROOT), overrides={file: document})


def _edited(file: str, edit: Edit, seeds: Mapping[str, str] = SEEDS) -> Mapping[str, tuple[str, str]]:
    """The hashes of the worked example with *edit* applied to the parsed document *file*."""
    return compute_all(_edited_graph(file, edit), seeds)


def _original(seeds: Mapping[str, str] = SEEDS) -> Mapping[str, tuple[str, str]]:
    return compute_all(_base(), seeds)


def _fr(document: dict[str, Any]) -> dict[str, Any]:
    return document["functional_requirements"][0]


def _set_statement(text: str) -> Edit:
    return lambda document: _fr(document).__setitem__("statement", text)


def _set_criterion_text(index: int, text: str) -> Edit:
    return lambda document: _fr(document)["acceptance_criteria"][index].__setitem__("text", text)


def _node(node_id: str, *targets: str, parent: str | None = None, kind: str = "thing", children: tuple[str, ...] = ()) -> Node:
    links = tuple(Link(node_id, "derives_from", target, _LINK) for target in targets)
    return Node(node_id, kind, None, None, "f.json", f".{node_id}", parent, children, "active", None, links, node_id)


def test_normalisation_variants_hash_equal_and_changed_word_or_case_differs() -> None:
    plain = 'The "reset" link - works once, in a café.'
    variants = (
        "The “reset” link – works once, in a café.",
        "The \"reset\" link - works once, in a café.",
        unicodedata.normalize("NFD", plain),
    )
    expected = _edited(FR_FILE, _set_statement(plain))
    for variant in variants:
        assert _edited(FR_FILE, _set_statement(variant)) == expected
    for changed in (plain.replace("works", "worked"), plain.replace("The", "THE")):
        moved = _edited(FR_FILE, _set_statement(changed))
        assert moved[FR][0] != expected[FR][0]
        assert moved[FR][1] != expected[FR][1]


@pytest.mark.parametrize("field", ["status", "notes", "tags", "owner", "lifecycle"])
def test_excluded_fields_change_neither_content_nor_chain(field: str) -> None:
    value: Any = {
        "status": "done", "notes": "note", "tags": ["x"], "owner": "ops", "lifecycle": "deprecated",
    }[field]
    assert _edited(FR_FILE, lambda document: _fr(document).__setitem__(field, value)) == _original()


@pytest.mark.parametrize("field", ["scope", "scope_reason"])
def test_scope_edit_moves_own_content_and_chain(field: str) -> None:
    def edit(document: dict[str, Any]) -> None:
        document["scope_items"][0][field] = "out" if field == "scope" else "dropped"

    base = _base()
    document = copy.deepcopy(dict(base.documents[SCOPE_FILE]))
    edit(document)
    moved = build_graph(EXAMPLE_SPEC, str(ROOT), overrides={SCOPE_FILE: document})
    assert own_hash(SCOPE, moved) != own_hash(SCOPE, base)
    after, before = compute_all(moved, SEEDS), _original()
    assert after[SCOPE][0] != before[SCOPE][0]
    assert after[SCOPE][1] != before[SCOPE][1]
    assert after[CAP][1] != before[CAP][1]


def test_relinking_and_adding_a_link_change_own() -> None:
    base = _base()
    before = own_hash(CAP, base)

    def own_after(edit: Edit) -> str:
        document = copy.deepcopy(dict(base.documents[CAP_FILE]))
        edit(document)
        graph = build_graph(EXAMPLE_SPEC, str(ROOT), overrides={CAP_FILE: document})
        return own_hash(CAP, graph)

    relinked = own_after(lambda d: d["capabilities"][0]["derives_from"].__setitem__(0, "scope-sms-reset"))
    added = own_after(lambda d: d["capabilities"][0]["derives_from"].append("scope-sms-reset"))
    assert len({before, relinked, added}) == 3


def test_criterion_edit_moves_fr_and_own_chain_not_sibling_chain() -> None:
    before, after = _original(), _edited(FR_FILE, _set_criterion_text(2, "Given an old token, then it is rejected."))
    assert after[FR][0] != before[FR][0]
    assert after[FR][1] != before[FR][1]
    assert after[CRITERIA[2]][1] != before[CRITERIA[2]][1]
    for sibling in CRITERIA[:2]:
        assert after[sibling] == before[sibling]


def test_fr_contract_edit_moves_chain_of_every_criterion() -> None:
    before, after = _original(), _edited(FR_FILE, _set_statement("The system shall do something else."))
    for criterion in CRITERIA:
        assert after[criterion][1] != before[criterion][1]
        assert after[criterion][0] == before[criterion][0]


def test_seed_edit_moves_every_chain_below_and_no_content() -> None:
    before = _original()
    after = _original({SEED: SEED_TEXT + " It expires."})
    below = (SCOPE, CAP, FR, *CRITERIA, TASK_CRITERION)
    for node_id in below:
        assert after[node_id][1] != before[node_id][1], node_id
    assert after[SEED][0] != before[SEED][0]
    assert after[SEED][0] == after[SEED][1]
    assert {i: v[0] for i, v in after.items() if i != SEED} == {i: v[0] for i, v in before.items() if i != SEED}


def _with_value_renamed(value: Any, old: str, new: str) -> Any:
    """*value* with every string equal to *old* (a value or a list member, not a key) replaced by *new*."""
    if isinstance(value, str):
        return new if value == old else value
    if isinstance(value, list):
        return [_with_value_renamed(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _with_value_renamed(item, old, new) for key, item in value.items()}
    return value


def _renamed(documents: Mapping[str, Any], old: str, new: str, *, keep: Collection[str] = ()) -> dict[str, Any]:
    """The documents after ``node rename old new``: the id and the links in them become *new*, the files of *keep* (historical holders) are left as they are, and *old* is appended to the node's aliases."""
    node = build_graph(EXAMPLE_SPEC, str(ROOT), overrides=documents).by_id[old]
    result = {path: doc if path in keep else _with_value_renamed(doc, old, new) for path, doc in copy.deepcopy(dict(documents)).items()}
    item = item_at(result[node.file], node.jq_path)
    assert item is not None
    item["aliases"] = [*item.get("aliases", []), old]
    return result


def _hashes(documents: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    return compute_all(build_graph(EXAMPLE_SPEC, str(ROOT), overrides=documents), SEEDS)


def _through(before: Mapping[str, tuple[str, str]], renames: Mapping[str, str]) -> dict[str, tuple[str, str]]:
    """*before* keyed through the renames (old id to new id): what the hashes must equal after them."""
    return {renames.get(node_id, node_id): value for node_id, value in before.items()}


CRITERION_ID = CRITERIA[2]
_RENAMES = {
    "capability": (CAP, "cap-account-recovery-v2", ()),
    "fr": (FR, "fr-password-reset-v2", ()),
    "criterion": (CRITERION_ID, "ac-password-reset-3b", ()),
    "criterion with historical holders left as written": (CRITERION_ID, "ac-password-reset-3b", ("14_roadmap.json",)),
}


@pytest.mark.parametrize(("old", "new", "keep"), list(_RENAMES.values()), ids=list(_RENAMES))
def test_rename_changes_no_hash_before_and_after(old: str, new: str, keep: tuple[str, ...]) -> None:
    documents = _base().documents
    once = _renamed(documents, old, new, keep=keep)
    assert _hashes(once) == _through(_hashes(documents), {old: new})
    third = f"{new}-again"
    twice = _renamed(once, new, third, keep=keep)
    assert _hashes(twice) == _through(_hashes(documents), {old: third})


def test_an_alias_is_outside_the_contract_of_its_node_and_a_later_alias_changes_nothing() -> None:
    """``aliases`` is no contract field: the node's own hash stays.  Only the first alias renames the node for the hashes of its holders."""

    def with_aliases(*names: str) -> Graph:
        return _edited_graph(FR_FILE, lambda document: _fr(document).__setitem__("aliases", list(names)))

    first, second = with_aliases("fr-old-name"), with_aliases("fr-old-name", "fr-older-name")
    assert own_hash(FR, first) == own_hash(FR, _base())
    assert compute_all(first, SEEDS)[FR][0] == _original()[FR][0]
    assert compute_all(second, SEEDS) == compute_all(first, SEEDS)


def test_a_renamed_criterion_leaves_its_fr_hashes_alone() -> None:
    documents = _base().documents
    before = _hashes(documents)
    after = _hashes(_renamed(documents, CRITERION_ID, "ac-password-reset-3b"))
    assert after[FR] == before[FR] and after["ac-password-reset-3b"] == before[CRITERION_ID]


def test_alias_rename_changes_no_hash() -> None:
    """A holder that still writes the old id and one that writes the new id hash alike: both name the target by its first name."""
    new = "cap-account-recovery-v2"
    documents = _base().documents
    renamed = _renamed(documents, CAP, new)
    holder_keeps_old_name = {**renamed, FR_FILE: documents[FR_FILE]}
    current = build_graph(EXAMPLE_SPEC, str(ROOT), overrides=renamed)
    stale = build_graph(EXAMPLE_SPEC, str(ROOT), overrides=holder_keeps_old_name)
    assert stale.alias_index == {CAP: new}
    assert compute_all(stale, SEEDS) == compute_all(current, SEEDS)


def test_the_first_name_of_a_node_is_its_first_alias() -> None:
    plain = Graph.from_nodes([_node("a"), _node("b")])
    assert first_name_index(plain) == {}
    renamed = replace(_node("c"), aliases=("a", "b"))
    assert first_name_index(Graph.from_nodes([renamed, _node("d")])) == {"c": "a", "a": "a", "b": "a"}


def test_cycle_marker_and_evaluation_order_use_the_first_name() -> None:
    """Renaming ``a`` to ``z`` moves it behind ``b`` in id order; its first name keeps it in front, so the cycle breaks at the same node."""
    before = Graph.from_nodes([_node("a", "b"), _node("b", "a", "ghost")])
    after = Graph.from_nodes([replace(_node("z", "b"), aliases=("a",)), _node("b", "z", "ghost")])
    assert compute_all(after, {}) == _through(compute_all(before, {}), {"a": "z"})


def test_a_missing_target_marker_is_the_same_before_and_after_a_rename() -> None:
    before = Graph.from_nodes([_node("a", "ghost")])
    after = Graph.from_nodes([replace(_node("z", "ghost"), aliases=("a",))])
    assert compute_all(after, {})["z"] == compute_all(before, {})["a"]


def test_seed_whitespace_reflow_keeps_seed_hash() -> None:
    reflowed = "  Members reset\ttheir password   through an emailed link.\n\n\nThe link works once.  \n"
    assert seed_hash(reflowed) == seed_hash(SEED_TEXT.replace("\n", " "))
    assert seed_hash(SEED_TEXT) != seed_hash(SEED_TEXT.replace("once", "twice"))
    assert seed_hash(SEED_TEXT).startswith(HASH_PREFIX)


def test_a_seed_without_text_hashes_as_a_marker() -> None:
    absent = _original({})
    assert absent[SEED] != _original()[SEED]
    assert absent[CAP][1] != _original()[CAP][1]


def test_cycle_and_missing_target_use_sentinels() -> None:
    cyclic = Graph.from_nodes([_node("a", "b"), _node("b", "a", "ghost")])
    values = compute_all(cyclic, {})
    assert set(values) == {"a", "b"}
    assert all(h.startswith(HASH_PREFIX) for pair in values.values() for h in pair)
    other_ghost = Graph.from_nodes([_node("a", "b"), _node("b", "a", "phantom")])
    assert compute_all(other_ghost, {})["b"] != values["b"]
    acyclic = Graph.from_nodes([_node("a", "b"), _node("b", "ghost")])
    assert compute_all(acyclic, {})["a"] != values["a"]
    assert compute_all(Graph.from_nodes([_node("b", "ghost"), _node("a", "b")]), {})["b"] == compute_all(
        Graph.from_nodes([_node("a", "b"), _node("b", "ghost")]), {}
    )["b"]


def test_a_deep_link_chain_does_not_exhaust_the_stack() -> None:
    depth = 5000
    nodes = [_node(f"n{i}", f"n{i + 1}") for i in range(depth)] + [_node(f"n{depth}")]
    graph = Graph.from_nodes(nodes)
    assert chain_stamp("n0", graph, {}) != chain_stamp(f"n{depth}", graph, {})


def test_public_functions_agree_with_compute_all_and_reject_an_unknown_id() -> None:
    graph = _base()
    values = compute_all(graph, SEEDS)
    assert (content_hash(FR, graph, SEEDS), chain_stamp(FR, graph, SEEDS)) == values[FR]
    for function in (content_hash, chain_stamp):
        with pytest.raises(KeyError):
            function("no-such-node", graph, SEEDS)
    with pytest.raises(KeyError):
        own_hash("no-such-node", graph)


def test_hash_pass_scale() -> None:
    """2,222 nodes and 4,715 links (the size of the largest host spec) in a single pass under five seconds."""
    count, link_count = 2222, 4715
    targets: dict[int, list[str]] = {i: [] for i in range(count)}
    for number in range(link_count):
        source = 1 + number % (count - 1)
        targets[source].append(f"n{(source * 7 + number) % source}")
    nodes = [_node(f"n{i}", *sorted(set(targets[i]))) for i in range(count)]
    graph = Graph.from_nodes(nodes)
    started = time.perf_counter()
    values = compute_all(graph, {})
    assert len(values) == count
    assert time.perf_counter() - started < 5.0
