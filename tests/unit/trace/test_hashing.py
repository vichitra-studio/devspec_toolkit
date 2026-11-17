"""Tests for the content hash and chain stamp (WI-M5-02) over the worked example and synthetic graphs."""
from __future__ import annotations

import copy
import json
import time
import unicodedata
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import Graph, Link, Node
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


def _edited(file: str, edit: Edit, seeds: Mapping[str, str] = SEEDS) -> Mapping[str, tuple[str, str]]:
    """The hashes of the worked example with *edit* applied to the parsed document *file*."""
    base = _base()
    document = copy.deepcopy(dict(base.documents[file]))
    edit(document)
    graph = build_graph(EXAMPLE_SPEC, str(ROOT), overrides={file: document})
    return compute_all(graph, seeds)


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
    value: Any = {"status": "done", "notes": "note", "tags": ["x"], "owner": "ops", "lifecycle": "deprecated"}[field]
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


def test_alias_rename_changes_no_hash() -> None:
    new = "cap-account-recovery-v2"
    base = _base()

    def renamed(documents: Mapping[str, Any]) -> dict[str, Any]:
        return {path: json.loads(json.dumps(doc).replace(f'"{CAP}"', f'"{new}"')) for path, doc in documents.items()}

    full = renamed(base.documents)
    holder_keeps_old_name = {**full, FR_FILE: base.documents[FR_FILE]}
    current = build_graph(EXAMPLE_SPEC, str(ROOT), overrides=full)
    stale = build_graph(EXAMPLE_SPEC, str(ROOT), overrides=holder_keeps_old_name)
    stale.alias_index = {CAP: new}
    assert compute_all(stale, SEEDS) == compute_all(current, SEEDS)


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
