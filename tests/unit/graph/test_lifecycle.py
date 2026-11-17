"""Tests for node lifecycle (WI-M4-06): the gate every graph consumer reads, and ``set_lifecycle`` with its refusals."""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import check_alias_space
from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.lifecycle import LifecycleRefusedError, plan_lifecycle_change, set_lifecycle
from specdev_tools.graph.model import LIFECYCLES, NOT_APPLICABLE, Graph, Link, Node
from specdev_tools.graph.queries import candidates
from specdev_tools.graph.recipes import build_pack, parse_recipes
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.graph.trace import trace_node
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.id_writes import broken_holders
from specdev_tools.trace.lockfile import Lock, LockEntry
from specdev_tools.trace.rename import live_holders
from specdev_tools.trace.suspects import find_suspects, lock_links, missing_entries, orphan_entries

from ._synth import EXAMPLE_SPEC, ROOT, load_doc, make_toolkit, write_json

LIFECYCLE_SPEC = Path(__file__).parents[2] / "fixtures" / "graph" / "synthetic" / "lifecycle"
_FR = "04_fr_list.json"
_PROBE = "fr-probe"

# The plan item of the fixture realises the probe, so a one-section recipe over the fixture's own kinds reaches it.
_PROBE_RECIPES = parse_recipes(
    {
        "start_kinds": {"16b": "plan-item"},
        "sections": [
            {
                "name": "probe", "roles": ["16b"], "start_set": ["start"], "kinds": ["fr"],
                "hops": [{"verb": "realises", "direction": "out", "kinds": ["fr"]}],
            }
        ],
    }
)

_ZERO_HASH = "sha256:" + "0" * 64


def _stale_lock(graph: Graph) -> Lock:
    """A lock that holds an entry with a wrong chain stamp for every link of the graph that carries one."""
    return Lock(tuple(
        LockEntry(item.holder.id, item.link.field, item.link.target, _ZERO_HASH, _ZERO_HASH) for item in lock_links(graph)
    ))


def _with_probe_in_closed_milestone(graph: Graph) -> Graph:
    """*graph* plus a milestone whose anchor row is ``done`` and a plan file of that milestone holding the probe."""
    about = LinkDecl(field="about", kinds=("roadmap-milestone",), required=False, built=True, same_step_kinds=())
    milestone = replace(graph.by_id["fr-twin"], id="ms-closed", kind="roadmap-milestone", children=(), links=(), milestone=None)
    anchor = replace(
        milestone, id="anchor-closed", kind="anchor-row", file="anchor.json", jq_path=".row",
        links=(Link("anchor-closed", "about", "ms-closed", about),),
    )
    nodes = [replace(node, milestone="ms-closed") if node.id == _PROBE else node for node in graph.nodes]
    closed = Graph.from_nodes([*nodes, milestone, anchor], shape=graph.shape)
    closed.documents["anchor.json"] = {"row": {"status": "done"}}
    return closed


def _holders_a_rename_rewrites(graph: Graph) -> set[str]:
    """The holders of a rename of ``cap-missing`` (the target the probe links to, added as a node): the probe, unless it is out of play."""
    target = replace(graph.by_id["fr-twin"], id="cap-missing", kind="capability", children=(), links=())
    renamed = Graph.from_nodes([*graph.nodes, target], shape=graph.shape)
    return set(live_holders(renamed, target))


# Each consumer of the graph, as the ids of the nodes it reads or reports on; later work items add their rows.
CONSUMERS: dict[str, Callable[[Graph], set[str]]] = {
    "resolver": lambda graph: {error.node_id for error in resolve_graph(graph) if error.node_id},
    "trace": lambda graph: {node.id for node in trace_node(graph, "ac-probe-1", ("up",)).reached},
    "candidates": lambda graph: {item.id for item in candidates(graph, "derives_from", kind="api").candidates},
    "recipes": lambda graph: set(build_pack(graph, _PROBE_RECIPES, "16b", "LOGIN_ITEM_01").node_ids),
    "suspects": lambda graph: {
        end for suspect in find_suspects(graph, _stale_lock(graph), {}) for end in (suspect.holder, suspect.target)
    },
    "missing_entries": lambda graph: {end for item in missing_entries(graph, Lock()) for end in (item.holder.id, item.target.id)},
    "orphan_entries": lambda graph: {
        entry.source for entry in orphan_entries(graph, Lock((LockEntry(_PROBE, "derives_from", "cap-gone", _ZERO_HASH, _ZERO_HASH),)))
    },
    "historical": lambda graph: historical_node_ids(_with_probe_in_closed_milestone(graph)),
    # An id write reports the live nodes whose links point at a deleted id; the probe links to a target that is gone.
    "broken_holders": lambda graph: {link.holder for link in broken_holders(graph, ["cap-missing"])},
    "rename": _holders_a_rename_rewrites,
}


@pytest.fixture
def toolkit(tmp_path: Path) -> Path:
    return make_toolkit(tmp_path / "tk")


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    dest = tmp_path / "spec"
    shutil.copytree(LIFECYCLE_SPEC, dest)
    return dest


def _graph(spec: Path, toolkit: Path) -> Graph:
    return build_graph(str(spec), str(toolkit))


def _with_probe_lifecycle(spec: Path, lifecycle: str) -> None:
    document = load_doc(spec, _FR)
    probe = next(item for item in document["functional_requirements"] if item["fr_id"] == _PROBE)
    probe["lifecycle"] = lifecycle
    write_json(spec, _FR, document)


def _probe_item(spec: Path) -> dict[str, Any]:
    return next(item for item in load_doc(spec, _FR)["functional_requirements"] if item["fr_id"] == _PROBE)


def test_record_lifecycle_constant_active(spec: Path, toolkit: Path) -> None:
    graph = _graph(EXAMPLE_SPEC, ROOT)
    records = [node for node in graph.nodes if node.role == "record"]
    assert records
    assert {node.lifecycle for node in records} == {"active"}

    stray = {"lifecycle": "not_applicable"}
    document = load_doc(spec, _FR)
    document["ambiguities"][0].update(stray)
    manifest = load_doc(spec, "common/seed_manifest.json")
    manifest["seeds"][0].update(stray)
    overrides = {_FR: document, "common/seed_manifest.json": manifest}
    graph = build_graph(str(spec), str(toolkit), overrides=overrides)
    gated = {node.id for node in graph.gated_nodes()}
    for node_id in ("amb-open", "seed-accounts"):
        assert graph.by_id[node_id].lifecycle == "active"
        assert node_id in gated


@pytest.mark.parametrize("lifecycle", LIFECYCLES)
def test_gated_nodes_skips_only_not_applicable(spec: Path, toolkit: Path, lifecycle: str) -> None:
    _with_probe_lifecycle(spec, lifecycle)
    graph = _graph(spec, toolkit)
    assert (_PROBE in {node.id for node in graph.gated_nodes()}) is (lifecycle != NOT_APPLICABLE)
    assert _PROBE in {node.id for node in graph.live_nodes()}


@pytest.mark.parametrize("consumer", CONSUMERS)
@pytest.mark.parametrize("lifecycle", LIFECYCLES)
def test_every_consumer_honours_lifecycle(spec: Path, toolkit: Path, consumer: str, lifecycle: str) -> None:
    _with_probe_lifecycle(spec, lifecycle)
    seen = CONSUMERS[consumer](_graph(spec, toolkit))
    assert (_PROBE in seen) is (lifecycle != NOT_APPLICABLE)


@pytest.mark.parametrize("lifecycle", LIFECYCLES)
def test_alias_space_reads_every_node_whatever_its_lifecycle(spec: Path, toolkit: Path, lifecycle: str) -> None:
    """Aliases share the id space of the nodes, which is unique among every node present in a file: ``not_applicable`` does not free an alias."""
    document = load_doc(spec, _FR)
    probe = next(item for item in document["functional_requirements"] if item["fr_id"] == _PROBE)
    probe.update(lifecycle=lifecycle, aliases=["fr-twin"])
    write_json(spec, _FR, document)
    assert [error.node_id for error in check_alias_space(_graph(spec, toolkit))] == [_PROBE]


@pytest.mark.parametrize("node_id", ["amb-open", "rec-note", "seed-accounts"], ids=["ambiguity", "record", "seed"])
def test_node_status_refused_on_record_and_seed_e705(spec: Path, toolkit: Path, node_id: str) -> None:
    graph = _graph(spec, toolkit)
    before = {path: path.read_bytes() for path in spec.rglob("*.json")}
    with pytest.raises(LifecycleRefusedError) as raised:
        set_lifecycle(graph, str(spec), str(toolkit), node_id, "deprecated")
    assert raised.value.error.code == "E705"
    assert {path: path.read_bytes() for path in spec.rglob("*.json")} == before


@pytest.mark.parametrize(
    ("node_id", "message"),
    [
        ("seed-accounts", "'seed-accounts' is a seed, and a seed has no lifecycle"),
        ("amb-open", "'amb-open' is an ambiguity-item, which is a record, and a record has no lifecycle"),
        ("rec-note", "'rec-note' is a sample-record, which is a record, and a record has no lifecycle"),
    ],
    ids=["seed", "record-an", "record-a"],
)
def test_the_e705_message_names_the_case(spec: Path, toolkit: Path, node_id: str, message: str) -> None:
    graph = _graph(spec, toolkit)
    with pytest.raises(LifecycleRefusedError) as raised:
        plan_lifecycle_change(graph, node_id, "deprecated")
    assert message in raised.value.error.message
    assert "a record or seed node" not in raised.value.error.message


@pytest.mark.parametrize(
    ("node_id", "value"), [("fr-no-such", "deprecated"), (_PROBE, "retired")], ids=["unknown-id", "value-outside-enum"]
)
def test_status_refused_for_unknown_id_and_bad_value(spec: Path, toolkit: Path, node_id: str, value: str) -> None:
    with pytest.raises(LifecycleRefusedError) as raised:
        plan_lifecycle_change(_graph(spec, toolkit), node_id, value)
    assert raised.value.error.code == "E705"


def test_status_refused_on_duplicate_id(spec: Path, toolkit: Path) -> None:
    graph = _graph(spec, toolkit)
    with pytest.raises(LifecycleRefusedError) as raised:
        plan_lifecycle_change(graph, "fr-twin", "deprecated")
    assert raised.value.error.code == "E705"
    assert "E704" in raised.value.error.message


def test_node_status_roundtrip(spec: Path, toolkit: Path) -> None:
    original = load_doc(spec, _FR)
    deprecated = set_lifecycle(_graph(spec, toolkit), str(spec), str(toolkit), _PROBE, "deprecated")
    assert (deprecated.old, deprecated.new, deprecated.file) == ("active", "deprecated", _FR)
    assert _probe_item(spec)["lifecycle"] == "deprecated"
    assert _graph(spec, toolkit).by_id[_PROBE].lifecycle == "deprecated"

    active = set_lifecycle(_graph(spec, toolkit), str(spec), str(toolkit), _PROBE, "active")
    assert (active.old, active.new) == ("deprecated", "active")
    assert "lifecycle" not in _probe_item(spec)
    assert load_doc(spec, _FR) == original


@pytest.mark.parametrize(
    ("node_id", "file"),
    [(_PROBE, _FR), ("ac-probe-1", _FR), ("LOGIN_ITEM_01", "impl_context/ms_login_plan.json")],
    ids=["top-level", "nested", "plan-item"],
)
def test_not_applicable_accepted_for_any_node(spec: Path, toolkit: Path, node_id: str, file: str) -> None:
    change = set_lifecycle(_graph(spec, toolkit), str(spec), str(toolkit), node_id, "not_applicable")
    assert (change.new, change.file) == ("not_applicable", file)
    document = json.dumps(load_doc(spec, file))
    assert '"lifecycle": "not_applicable"' in document
    assert _graph(spec, toolkit).by_id[node_id].lifecycle == "not_applicable"
