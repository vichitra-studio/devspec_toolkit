"""Tests for ``specdev trace --up|--down`` (WI-M4-08): the closures, their options and the ``context scope`` alias."""
from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.context.scope_resolver import DEPRECATION_NOTE, resolve_scope
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import LIFECYCLES, NOT_APPLICABLE, Graph, Link, Node, SpecShape
from specdev_tools.graph.trace import (
    TraceOptions,
    UnknownTraceTargetError,
    render_text,
    result_to_dict,
    trace_node,
)

from ._synth import EXAMPLE_SPEC, ROOT, copy_example, load_doc, run_specdev, write_json

LIFECYCLE_SPEC = ROOT / "tests" / "fixtures" / "graph" / "synthetic" / "lifecycle"
LEGACY_CORPUS = ROOT / "tests" / "fixtures" / "spec_corpus"
_CRITERION = "ac-password-reset-3"
_RANKS = {"seed": -1, "s1": 0, "s2": 1, "s3": 2}


@pytest.fixture(scope="module")
def example() -> Graph:
    return build_graph(str(EXAMPLE_SPEC), str(ROOT))


def _ids(nodes: Iterable[Node]) -> set[str]:
    return {node.id for node in nodes}


def _up(graph: Graph, node_id: str, options: TraceOptions = TraceOptions()) -> set[str]:
    side = trace_node(graph, node_id, ("up",), options).up
    assert side is not None
    return _ids(side.nodes)


def _down(graph: Graph, node_id: str, options: TraceOptions = TraceOptions()) -> set[str]:
    side = trace_node(graph, node_id, ("down",), options).down
    assert side is not None
    return _ids(side.nodes)


# --- the worked example ---------------------------------------------------------------------------------------------

def test_up_lineage_matches_doc_fr_to_seed(example: Graph) -> None:
    up = _up(example, _CRITERION)
    assert {"fr-password-reset", "cap-account-recovery", "scope-password-reset", "seed-accounts"} <= up


def test_down_impact_from_criterion(example: Graph) -> None:
    assert _down(example, _CRITERION) == {
        "err-password-reset-confirm-token-expired",
        "fix-password-reset-expired-token",
        "ec-token-at-expiry-second",
        "tc-confirm-expired-token",
        "threat-reset-token-replay",
        "PWRESET_CONFIRM_EXPIRED_01",
    }


def test_siblings_not_returned(example: Graph) -> None:
    both = trace_node(example, _CRITERION).reached
    assert not _ids(both) & {"ac-password-reset-1", "ac-password-reset-2", "fr-password-reset-request"}
    request_up = _up(example, "fr-password-reset-request")
    assert "cap-account-recovery" in request_up and "fr-password-reset" not in request_up


def _fr_graph(per_capability: int) -> Graph:
    """Two capabilities under one scope item and one seed, each with *per_capability* FRs of two criteria."""
    decl = LinkDecl(field="derives_from", kinds=("*",), required=True, built=True, same_step_kinds=())

    def node(node_id: str, kind: str, step: str, target: str | None = None, parent: str | None = None, kids: tuple[str, ...] = ()) -> Node:
        links = (Link(node_id, "derives_from", target, decl),) if target else ()
        return Node(
            id=node_id, kind=kind, step=step, role="obligation-system", file=f"{step}.json", jq_path=f".{kind}[0]",
            parent=parent, children=kids, lifecycle="active", scope=None, links=links, label=node_id,
        )

    nodes = [node("seed-a", "seed", "seed"), node("scope-a", "scope-item", "s1", "seed-a")]
    for cap in ("cap-a", "cap-b"):
        nodes.append(node(cap, "capability", "s1", "scope-a"))
        for index in range(per_capability):
            fr = f"fr-{cap}-{index}"
            criteria = tuple(f"ac-{fr}-{n}" for n in (1, 2))
            nodes.append(node(fr, "fr", "s2", cap, kids=criteria))
            nodes.extend(node(criterion, "criterion", "s2", parent=fr) for criterion in criteria)
    return Graph.from_nodes(nodes, shape=SpecShape(step_ranks=_RANKS))


def test_no_717_id_blowup() -> None:
    graph = _fr_graph(per_capability=73)
    everything = set(graph.by_id)
    assert len(everything) == 2 * 73 * 3 + 4
    frs_of_a = {f"fr-cap-a-{index}" for index in range(73)}

    one_fr = _ids(trace_node(graph, "fr-cap-a-0").reached)
    assert one_fr < everything
    assert one_fr == {"fr-cap-a-0", "ac-fr-cap-a-0-1", "ac-fr-cap-a-0-2", "cap-a", "scope-a", "seed-a"}

    capability = _ids(trace_node(graph, "cap-a").reached)
    assert not capability & {f"fr-cap-b-{index}" for index in range(73)}
    assert frs_of_a <= capability and "cap-b" not in capability


def test_threat_returns_its_targets_and_mitigations(example: Graph) -> None:
    threat = "threat-reset-token-replay"
    up = _up(example, threat)
    assert {"api-password-reset-confirm", "inv-reset-token-single-use", "fix-password-reset-expired-token"} <= up
    assert {"risk-reset-link-takeover", "seed-accounts"} <= up
    assert len(_ids(trace_node(example, threat).reached)) > 1


def test_depth_and_kind_filters(example: Graph) -> None:
    assert _up(example, _CRITERION, TraceOptions(depth=1)) == {"fr-password-reset"}
    assert _up(example, _CRITERION, TraceOptions(depth=2)) == {"fr-password-reset", "cap-account-recovery"}
    assert _up(example, _CRITERION, TraceOptions(kinds=frozenset({"seed", "capability"}))) == {"seed-accounts", "cap-account-recovery"}
    assert _down(example, _CRITERION, TraceOptions(kinds=frozenset({"fixture"}))) == {"fix-password-reset-expired-token"}


def test_verb_filter_limits_the_links_followed(example: Graph) -> None:
    assert _up(example, "api-password-reset-confirm", TraceOptions(verbs=frozenset({"relies_on"}))) == {"tp-argon2"}
    only_derives = TraceOptions(containment=False, verbs=frozenset({"derives_from"}))
    assert _down(example, "fr-password-reset", only_derives) == {"api-password-reset-confirm"}


def test_no_containment_stops_at_the_child_and_the_parent(example: Graph) -> None:
    assert _up(example, _CRITERION, TraceOptions(containment=False)) == set()
    assert "ac-password-reset-1" in _down(example, "fr-password-reset")
    assert "ac-password-reset-1" not in _down(example, "fr-password-reset", TraceOptions(containment=False))


def test_records_are_shown_apart_in_down(example: Graph) -> None:
    side = trace_node(example, "ms-account-recovery", ("down",)).down
    assert side is not None
    assert _ids(side.records) == {"anchor-ms-account-recovery"}
    assert "anchor-ms-account-recovery" not in _ids(side.nodes)


def test_a_record_is_shown_but_never_walked_through() -> None:
    decl = LinkDecl(field="derives_from", kinds=("*",), required=True, built=True, same_step_kinds=())

    def node(node_id: str, kind: str, role: str, target: str | None = None) -> Node:
        links = (Link(node_id, "derives_from", target, decl),) if target else ()
        return Node(node_id, kind, "s1", role, "s1.json", f".{kind}[0]", None, (), "active", None, links, node_id)

    graph = Graph.from_nodes(
        [node("fr-a", "fr", "obligation-system", "amb-r"), node("amb-r", "ambiguity", "record", "fr-b"), node("fr-b", "fr", "obligation-system")],
        shape=SpecShape(step_ranks=_RANKS),
    )
    side = trace_node(graph, "fr-a", ("up",)).up
    assert side is not None
    assert _ids(side.records) == {"amb-r"} and _ids(side.nodes) == set()


def test_results_are_ordered_by_step_then_id(example: Graph) -> None:
    side = trace_node(example, "fr-password-reset", ("up",)).up
    assert side is not None
    ids = [node.id for node in side.nodes]
    assert ids != sorted(ids), "the entry must be one whose id order is not its step order, or this test checks nothing"
    keys = [(example.shape.step_ranks[node.step], node.id) for node in side.nodes if node.step]
    assert len(keys) == len(ids) and keys == sorted(keys)


def test_a_direction_not_asked_for_is_none(example: Graph) -> None:
    result = trace_node(example, _CRITERION, ("up",))
    assert result.down is None and result.up is not None
    assert "down" not in result_to_dict(result)


def test_unknown_id_raises_e706(example: Graph) -> None:
    with pytest.raises(UnknownTraceTargetError) as raised:
        trace_node(example, "fr-no-such")
    assert raised.value.error.code == "E706" and "fr-no-such" in raised.value.error.message


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (TraceOptions(kinds=frozenset({"nosuch"})), "no kind 'nosuch'"),
        (TraceOptions(verbs=frozenset({"derive_from"})), "no link field 'derive_from'; nearest: derives_from"),
        (TraceOptions(kinds=frozenset({"fr", "frr"}), verbs=frozenset({"zz"})), "no kind 'frr'"),
    ],
    ids=["kind", "verb", "both"],
)
def test_a_kind_or_verb_the_graph_does_not_have_is_e706(example: Graph, options: TraceOptions, message: str) -> None:
    with pytest.raises(UnknownTraceTargetError) as raised:
        trace_node(example, _CRITERION, options=options)
    assert raised.value.error.code == "E706" and message in raised.value.error.message


def test_every_kind_and_verb_the_registry_declares_is_accepted(example: Graph) -> None:
    kinds = frozenset(example.decls)
    verbs = frozenset(link.field for decl in example.decls.values() for link in decl.links)
    assert "derives_from" in verbs and "replaces" in verbs
    assert trace_node(example, _CRITERION, options=TraceOptions(kinds=kinds, verbs=verbs)).entry.id == _CRITERION


def test_text_groups_by_kind_and_prints_the_five_columns(example: Graph) -> None:
    text = render_text(trace_node(example, _CRITERION, ("up",)))
    assert "up (" in text and "  fr (1)" in text
    assert "    fr-password-reset  fr  04  active  The system shall" in text


def test_json_groups_by_kind(example: Graph) -> None:
    document = result_to_dict(trace_node(example, _CRITERION))
    assert document["entry"]["id"] == _CRITERION
    assert [node["id"] for node in document["up"]["groups"]["fr"]] == ["fr-password-reset"]
    assert document["up"]["count"] == sum(len(nodes) for nodes in document["up"]["groups"].values())


# --- lifecycle ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("lifecycle", LIFECYCLES)
def test_trace_honours_lifecycle(tmp_path: Path, lifecycle: str) -> None:
    spec = tmp_path / "spec"
    shutil.copytree(LIFECYCLE_SPEC, spec)
    document = load_doc(spec, "04_fr_list.json")
    next(item for item in document["functional_requirements"] if item["fr_id"] == "fr-probe")["lifecycle"] = lifecycle
    write_json(spec, "04_fr_list.json", document)
    reached = _ids(trace_node(build_graph(str(spec), str(ROOT)), "ac-probe-1", ("up",)).reached)
    assert ("fr-probe" in reached) is (lifecycle != NOT_APPLICABLE)


# --- context scope as an alias --------------------------------------------------------------------------------------

def test_context_scope_alias_directed_and_no_matrix_write(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = copy_example(tmp_path / "spec")
    before = {path: path.read_bytes() for path in spec.rglob("*") if path.is_file()}
    scope = resolve_scope("fr-password-reset-request", str(spec), str(ROOT))
    assert {path: path.read_bytes() for path in spec.rglob("*") if path.is_file()} == before
    assert not (spec / "extras" / "trace_matrix.json").exists()
    assert set(scope) == {"entry", "resolved_ids", "source_files"}
    assert scope["entry"] == "fr-password-reset-request"
    assert scope["resolved_ids"]["fr"] == ["fr-password-reset-request"]
    assert scope["resolved_ids"]["criterion"] == ["ac-password-reset-request-1", "ac-password-reset-request-2"]
    assert "fr-password-reset" not in scope["source_files"]
    assert scope["source_files"]["fr-password-reset-request"] == {
        "file": "spec/04_fr_list.json", "path": ".functional_requirements[1]",
    }
    assert capsys.readouterr().err.strip() == DEPRECATION_NOTE


def test_context_scope_entries_differ_and_threat_returns_more_than_itself(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")

    def scope_ids(entry: str) -> set[str]:
        process = run_specdev("context", "scope", str(spec), "--entry", entry, "--repo-root", str(ROOT))
        assert process.returncode == 0, process.stderr
        assert DEPRECATION_NOTE in process.stderr
        return {node_id for ids in json.loads(process.stdout)["resolved_ids"].values() for node_id in ids}

    first, second = scope_ids("fr-password-reset"), scope_ids("fr-password-reset-request")
    assert first != second and "fr-password-reset-request" not in first
    assert len(scope_ids("threat-reset-token-replay")) > 1


def test_context_scope_on_a_1_1_1_corpus_returns_the_entry_and_the_nodes_it_contains(tmp_path: Path) -> None:
    """A 1.1.1 spec declares no links, so the scope is the entry and its criterion; containment is not a link."""
    spec = tmp_path / "spec_corpus"
    shutil.copytree(LEGACY_CORPUS, spec)
    scope = resolve_scope("FR-CORPUS-001", str(spec), str(ROOT))
    assert scope["resolved_ids"] == {"fr": ["FR-CORPUS-001"], "criterion": ["AC-CORPUS-001"]}
    assert "scope_warning" not in scope


def test_context_scope_unknown_entry_warns(tmp_path: Path) -> None:
    scope = resolve_scope("fr-nope", str(tmp_path), str(ROOT))
    assert scope["resolved_ids"] == {} and "fr-nope" in scope["scope_warning"]


def test_context_scope_without_a_registry_warns_and_does_not_raise(tmp_path: Path) -> None:
    scope = resolve_scope("fr-password-reset", str(EXAMPLE_SPEC), str(tmp_path))
    assert scope["resolved_ids"] == {} and "could not be built" in scope["scope_warning"]


def test_context_scope_without_an_entry_is_all(tmp_path: Path) -> None:
    assert resolve_scope(None, str(tmp_path), str(ROOT)) == {
        "entry": None, "resolved_ids": {}, "source_files": {}, "scope": "all",
    }


# --- wrong-typed values ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value", [7, "cap-account-recovery", {"id": "x"}, [None, 7, ["x"]], None])
@pytest.mark.parametrize("field", ["derives_from", "criterion_id", "acceptance_criteria", "lifecycle", "statement"])
def test_trace_and_scope_do_not_raise_on_a_wrong_value(tmp_path: Path, field: str, value: Any) -> None:
    spec = copy_example(tmp_path / "spec")
    document = load_doc(spec, "04_fr_list.json")
    document["functional_requirements"][0][field] = value
    write_json(spec, "04_fr_list.json", document)
    graph = build_graph(str(spec), str(ROOT))
    for node_id in ("fr-password-reset", "cap-account-recovery", "ac-password-reset-3"):
        if node_id in graph.by_id:
            render_text(trace_node(graph, node_id))
            result_to_dict(trace_node(graph, node_id))
    scope = resolve_scope("fr-password-reset", str(spec), str(ROOT))
    assert isinstance(scope["resolved_ids"], dict)
