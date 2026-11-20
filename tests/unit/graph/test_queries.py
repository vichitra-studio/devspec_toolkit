"""Tests for the graph read queries (WI-M4-07): the view of a node and the valid targets of a link field."""
from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import make_error
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.contract import item_at
from specdev_tools.graph.model import NOT_APPLICABLE, Graph
from specdev_tools.graph.resolve import HISTORY_FIELDS, resolve_graph
from specdev_tools.graph.queries import (
    NodeReport,
    QueryTargetError,
    candidates,
    candidates_json,
    candidates_text,
    milestone_of,
    node_json,
    node_text,
    node_view,
    relied_on_third_parties,
)

from ._synth import EXAMPLE_SPEC, ROOT, copy_example, docs_graph, load_doc, write_json

_CAPS = "01_capabilities.json"
_FRS = "04_fr_list.json"
_APIS = "05_interface_contracts.json"


def _docs(frs: list[dict[str, Any]], caps: list[dict[str, Any]] | None = None, apis: list[dict[str, Any]] | None = None,
          ambiguities: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    docs: dict[str, Any] = {
        _CAPS: {"capabilities": caps if caps is not None else [{"capability_id": "cap-a", "description": "Alpha"}]},
        _FRS: {"functional_requirements": frs},
    }
    if apis is not None:
        docs[_APIS] = {"apis": apis}
    if ambiguities is not None:
        docs[_FRS]["ambiguities"] = ambiguities
    return docs


def _fr(fr_id: str, **fields: Any) -> dict[str, Any]:
    return {"fr_id": fr_id, "statement": f"Statement of {fr_id}", **fields}


def _ids(result: Any) -> list[str]:
    return [item.id for item in result.candidates]


@pytest.fixture(scope="module")
def example() -> Graph:
    return build_graph(str(EXAMPLE_SPEC), str(ROOT))


def test_node_shows_content_file_path_lifecycle(example: Graph) -> None:
    [view] = node_view(example, ["fr-password-reset"]).views
    assert (view.kind, view.step, view.role, view.lifecycle, view.scope) == ("fr", "04", "obligation-system", "active", "in")
    assert (view.file, view.jq_path) == ("04_fr_list.json", ".functional_requirements[0]")
    assert view.content is not None
    assert view.content["statement"].startswith("The system shall let a registered member")
    assert view.content["acceptance_criteria"] == ["ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-3"]
    assert [(link.field, link.target, link.kind, link.step) for link in view.outgoing] == [
        ("derives_from", "cap-account-recovery", "capability", "01")
    ]
    assert view.outgoing[0].label.startswith("A registered member can regain access")
    incoming = {(entry.verb, entry.kind): entry.count for entry in view.incoming}
    assert incoming[("derives_from", "api")] == 1
    assert incoming[("schedules", "design-milestone")] == 1


def test_node_full_includes_child_content(example: Graph) -> None:
    [view] = node_view(example, ["fr-password-reset"], full=True).views
    assert view.content is not None
    assert [child["criterion_id"] for child in view.content["acceptance_criteria"]] == list(view.children)


def test_node_text_and_json_renderings(example: Graph) -> None:
    report = node_view(example, ["fr-password-reset"])
    text = node_text(report)
    assert text.splitlines()[0].startswith("fr-password-reset  fr  step 04")
    assert "derives_from -> cap-account-recovery  [capability, step 01, active]" in text
    assert "derives_from <- 1 api" in text
    assert json.loads(json.dumps(node_json(report)))["nodes"][0]["id"] == "fr-password-reset"


def test_node_unknown_id_nearest(example: Graph) -> None:
    with pytest.raises(QueryTargetError) as raised:
        node_view(example, ["fr-password-rest"])
    assert raised.value.error.code == "E706"
    assert "nearest: fr-password-reset" in raised.value.error.message
    assert (raised.value.error.owner, raised.value.error.node_id) == (None, None)


def test_node_unknown_id_among_known_names_each_unknown(example: Graph) -> None:
    with pytest.raises(QueryTargetError) as raised:
        node_view(example, ["fr-password-reset", "no-such-a", "no-such-b"])
    assert "'no-such-a'" in raised.value.error.message and "'no-such-b'" in raised.value.error.message


def test_node_batch_ids(example: Graph) -> None:
    report = node_view(example, ["cap-account-recovery", "fr-password-reset"])
    assert [view.id for view in report.views] == ["cap-account-recovery", "fr-password-reset"]
    assert report.errors == ()


def test_node_duplicate_id_lists_all() -> None:
    graph = docs_graph(_docs([_fr("fr-twin"), _fr("fr-twin", priority="must-have"), _fr("fr-one")]))
    report = node_view(graph, ["fr-twin"])
    assert [view.jq_path for view in report.views] == [".functional_requirements[0]", ".functional_requirements[1]"]
    assert [error.code for error in report.errors] == ["E704"]
    assert node_view(graph, ["fr-one"]).errors == ()
    assert "E704" in node_text(report)


def test_node_link_to_unknown_target_is_shown_not_found() -> None:
    graph = docs_graph(_docs([_fr("fr-a", derives_from=["cap-missing"])]))
    [view] = node_view(graph, ["fr-a"]).views
    assert (view.outgoing[0].target, view.outgoing[0].kind) == ("cap-missing", None)
    assert "cap-missing  (not found)" in node_text(node_view(graph, ["fr-a"]))


def test_node_incoming_ignores_not_applicable_sources() -> None:
    frs = [_fr("fr-a"), _fr("fr-b", depends_on=["fr-a"]), _fr("fr-c", depends_on=["fr-a"], lifecycle=NOT_APPLICABLE)]
    [view] = node_view(docs_graph(_docs(frs)), ["fr-a"]).views
    assert [(entry.verb, entry.kind, entry.count) for entry in view.incoming] == [("depends_on", "fr", 1)]


def test_candidates_kind_and_direction() -> None:
    docs = _docs(
        [_fr("fr-a")],
        caps=[{"capability_id": "cap-a"}, {"capability_id": "cap-b"}],
        apis=[{"api_id": "api-a"}],
        ambiguities=[{"id": "amb-a", "about": []}],
    )
    graph = docs_graph(docs)
    assert _ids(candidates(graph, "derives_from", kind="fr")) == ["cap-a", "cap-b"]
    assert _ids(candidates(graph, "derives_from", for_id="fr-a")) == ["cap-a", "cap-b"]
    about = candidates(graph, "about", for_id="amb-a")
    assert [item.step for item in about.candidates] == ["01", "01"]
    assert _ids(about) == ["cap-a", "cap-b"]
    assert "api-a" not in _ids(candidates(graph, "about", for_id="amb-a"))


def test_candidates_are_sorted_by_step_then_id() -> None:
    docs = _docs([_fr("fr-b"), _fr("fr-a")], caps=[{"capability_id": "cap-z"}, {"capability_id": "cap-m"}],
                 ambiguities=[{"id": "amb-a", "about": []}])
    result = candidates(docs_graph(docs), "about", for_id="amb-a")
    assert [(item.step, item.id) for item in result.candidates][:2] == [("01", "cap-m"), ("01", "cap-z")]


def test_candidates_same_step_field_excludes_cycles() -> None:
    frs = [_fr("fr-a"), _fr("fr-b", depends_on=["fr-a"]), _fr("fr-c"), _fr("fr-d", depends_on=["fr-b"])]
    graph = docs_graph(_docs(frs))
    assert _ids(candidates(graph, "depends_on", for_id="fr-a")) == ["fr-c"]
    assert _ids(candidates(graph, "depends_on", for_id="fr-c")) == ["fr-a", "fr-b", "fr-d"]
    assert _ids(candidates(graph, "depends_on", kind="fr")) == ["fr-a", "fr-b", "fr-c", "fr-d"]


def test_candidates_exclude_already_linked() -> None:
    frs = [_fr("fr-a"), _fr("fr-b"), _fr("fr-c", depends_on=["fr-a"])]
    graph = docs_graph(_docs(frs))
    assert _ids(candidates(graph, "depends_on", for_id="fr-c")) == ["fr-b"]
    assert _ids(candidates(graph, "depends_on", kind="fr")) == ["fr-a", "fr-b", "fr-c"]


def test_candidates_flag_deprecated_exclude_not_applicable() -> None:
    caps = [{"capability_id": "cap-live"}, {"capability_id": "cap-old", "lifecycle": "deprecated"},
            {"capability_id": "cap-gone", "lifecycle": NOT_APPLICABLE}]
    result = candidates(docs_graph(_docs([_fr("fr-a")], caps=caps)), "derives_from", for_id="fr-a")
    assert _ids(result) == ["cap-live", "cap-old"]
    assert [item.deprecated for item in result.candidates] == [False, True]
    assert "DEPRECATED" in candidates_text(result).splitlines()[2]
    assert candidates_json(result)["candidates"][1]["deprecated"] is True


@pytest.mark.parametrize("lifecycle", ["active", "deprecated", NOT_APPLICABLE])
def test_candidates_honours_lifecycle(lifecycle: str) -> None:
    caps = [{"capability_id": "cap-probe", "lifecycle": lifecycle}]
    result = candidates(docs_graph(_docs([_fr("fr-a")], caps=caps)), "derives_from", kind="fr")
    assert ("cap-probe" in _ids(result)) is (lifecycle != NOT_APPLICABLE)


@pytest.mark.parametrize("history_field", ["replaces", "removes"])
def test_candidates_replaces_field_errors(history_field: str) -> None:
    graph = docs_graph(_docs([_fr("fr-a")]))
    with pytest.raises(QueryTargetError) as raised:
        candidates(graph, history_field, kind="fr")
    assert raised.value.error.code == "E706"
    assert "targets deleted ids; there are no candidates" in raised.value.error.message


@pytest.mark.parametrize(
    "call",
    [
        lambda g: candidates(g, "derives_from", kind="no-such-kind"),
        lambda g: candidates(g, "no_such_field", kind="fr"),
        lambda g: candidates(g, "derives_from", for_id="fr-nope"),
    ],
    ids=["kind", "field", "node"],
)
def test_candidates_unknown_target_is_e706(call: Callable[[Graph], Any]) -> None:
    with pytest.raises(QueryTargetError) as raised:
        call(docs_graph(_docs([_fr("fr-a")])))
    assert raised.value.error.code == "E706"


@pytest.mark.parametrize("arguments", [{}, {"kind": "fr", "for_id": "fr-a"}], ids=["neither", "both"])
def test_candidates_needs_exactly_one_holder(arguments: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        candidates(docs_graph(_docs([_fr("fr-a")])), "derives_from", **arguments)


def test_candidates_query_and_limit() -> None:
    caps = [{"capability_id": f"cap-{name}", "description": text} for name, text in
            [("a", "Reset passwords"), ("b", "Export data"), ("c", "RESET sessions")]]
    graph = docs_graph(_docs([_fr("fr-a")], caps=caps))
    assert _ids(candidates(graph, "derives_from", kind="fr", query="reset")) == ["cap-a", "cap-c"]
    limited = candidates(graph, "derives_from", kind="fr", limit=1)
    assert (_ids(limited), limited.total) == (["cap-a"], 3)
    assert candidates(graph, "derives_from", kind="fr", limit=0).candidates == ()
    assert candidates_text(limited).splitlines()[0] == "3 candidates for fr.derives_from (showing 1)"


_WRONG_VALUES: list[Any] = [None, 7, True, [], {}, "text", [1, None], {"k": 1}]


def _mutations(base: dict[str, Any], wrong: Any) -> list[dict[str, Any]]:
    """Copies of *base*, each with one field of one item set to *wrong*."""
    copies = []
    for rel, document in base.items():
        for array, items in document.items():
            for index, item in enumerate(items):
                for key in item:
                    copy = deepcopy(base)
                    copy[rel][array][index][key] = wrong
                    copies.append(copy)
    return copies


def _read_everything(graph: Graph) -> None:
    ids = [node.id for node in graph.nodes]
    if ids:
        node_text(node_view(graph, ids, full=True))
        node_json(node_view(graph, ids))
    for node_id in (found for found in ("fr-a", "amb-a") if found in graph.by_id):
        for verb in ("derives_from", "about", "depends_on"):
            try:
                candidates_text(candidates(graph, verb, for_id=node_id))
            except QueryTargetError:
                pass


@pytest.mark.parametrize("wrong", _WRONG_VALUES, ids=repr)
def test_queries_do_not_raise_on_a_wrong_value(wrong: Any) -> None:
    base = _docs(
        [_fr("fr-a", derives_from=["cap-a"], acceptance_criteria=[{"criterion_id": "ac-a", "text": "T"}]), _fr("fr-b")],
        ambiguities=[{"id": "amb-a", "about": ["fr-a"]}],
    )
    for mutated in _mutations(base, wrong):
        _read_everything(docs_graph(mutated))


_CANDIDATES_PER_FIELD = 3
_LINK_CODES = {"E700", "E701", "E702"}


def _holders_by_field(graph: Graph) -> list[tuple[str, str, str]]:
    """``(holder id, kind, field)`` for the first node of each kind and each of its link fields except history ones."""
    pairs = []
    for kind, nodes in graph.by_kind.items():
        decl = graph.decls.get(kind)
        for link in decl.links if decl is not None else ():
            if link.field not in HISTORY_FIELDS:
                pairs.append((nodes[0].id, kind, link.field))
    return pairs


def test_every_candidate_is_accepted_by_the_resolver(example: Graph) -> None:
    """Writes the first candidates of each (kind, field) of the worked example into a holder and resolves the result.

    One holder per (kind, field), not every holder.  E703 (a same-step cycle) is not checked: only E700, E701 and E702.
    """
    checked = 0
    for holder_id, kind, link_field in _holders_by_field(example):
        found = candidates(example, link_field, for_id=holder_id, limit=_CANDIDATES_PER_FIELD).candidates
        if not found:
            continue
        documents = deepcopy(dict(example.documents))
        holder = example.by_id[holder_id]
        item = item_at(documents[holder.file], holder.jq_path)
        assert item is not None
        existing = item.get(link_field)
        item[link_field] = [*(existing if isinstance(existing, list) else []), *(c.id for c in found)]
        rejected = [
            (holder_id, link_field, error.message)
            for error in resolve_graph(docs_graph(documents))
            if error.code in _LINK_CODES and error.node_id == holder_id
            and any(f"'{c.id}'" in error.message for c in found)
        ]
        assert not rejected, f"{kind}.{link_field}: {rejected}"
        checked += len(found)
    assert checked > 20


def test_node_show_of_a_seed_names_the_manifest_pointer_and_the_document_separately() -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    report = node_view(graph, ["seed-accounts", "fr-password-reset"])
    seed, fr = report.views
    assert (seed.file, seed.jq_path, seed.document) == ("common/seed_manifest.json", ".seeds[0]", "docs/seed/seed_accounts.md")
    assert fr.document is None
    text = node_text(report).splitlines()
    assert "  file common/seed_manifest.json  path .seeds[0]" in text and "  seed document docs/seed/seed_accounts.md" in text
    assert text.count("  seed document docs/seed/seed_accounts.md") == 1
    assert node_json(report)["nodes"][0]["document"] == "docs/seed/seed_accounts.md"


def test_a_message_that_names_a_kind_after_an_article_says_an_before_a_vowel() -> None:
    """H1-8: the recipe start check, run on every kind of the worked example that starts with a vowel ("is a api" before the fix)."""
    from unit.graph._synth import run_cli

    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    vowel_nodes = {node.kind: node.id for node in graph.nodes if node.kind[:1] in "aeiou"}
    assert {"api", "assumption", "invariant"} <= set(vowel_nodes)
    for kind, node_id in sorted(vowel_nodes.items()):
        code, out = run_cli("trace", node_id, "--recipe", "16b", "--repo-root", str(ROOT), "--spec-root", str(EXAMPLE_SPEC))
        assert code == 1 and "E707" in out, (kind, out)
        assert f"is an {kind}" in out and f"is a {kind}" not in out, (kind, out)


def test_error_json_omits_target() -> None:
    error = make_error("E700", "m", node_id="api-y", target="derives_from->fr-x")
    (document,) = node_json(NodeReport(views=(), errors=(error,)))["errors"]
    assert document == {"code": "E700", "message": "m", "node_id": "api-y"}


def test_milestone_of_reads_a_plan_files_milestone_then_the_containing_roadmap_milestone(example: Graph) -> None:
    plan_node = next(node for node in example.nodes if node.milestone is not None)
    assert milestone_of(example, plan_node) == example.canonical_id(plan_node.milestone)
    criterion = example.by_id["tc-confirm-expired-token"]
    assert milestone_of(example, criterion) == "ms-account-recovery" == milestone_of(example, example.by_id["ms-account-recovery"])
    assert milestone_of(example, example.by_id["fr-password-reset"]) is None


def test_milestone_of_resolves_a_plan_files_milestone_written_with_a_retired_name() -> None:
    from dataclasses import replace

    from unit.validation.graph_checks._built_support import graph_of, node

    renamed = replace(node("ms-new", "roadmap-milestone", "plan", step="14"), aliases=("ms-old",))
    task = replace(node("task-t", "task", "plan", step="14"), milestone="ms-old")
    assert milestone_of(graph_of([renamed, task]), task) == "ms-new"


_SKETCH = "02_system_sketch.json"
_API = "api-password-reset-confirm"


def _reliance(spec: Any, *ids: str) -> list[str]:
    graph = build_graph(str(spec), str(ROOT))
    return relied_on_third_parties(graph, [graph.by_id[node_id] for node_id in ids])


def test_reliance_of_an_api_is_its_direct_relies_on_then_the_third_parties_its_components_connections_connect_to() -> None:
    """The worked example: the API relies on tp-argon2 itself, and identity-service (its component) connects to tp-mailrelay."""
    assert _reliance(EXAMPLE_SPEC, _API) == ["tp-argon2", "tp-mailrelay"]


def test_a_node_with_no_relies_on_and_no_providing_component_has_no_reliance() -> None:
    assert _reliance(EXAMPLE_SPEC, "fr-password-reset", "cap-account-recovery") == []


def test_a_third_party_reached_directly_and_through_a_connection_is_listed_once(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")
    document = load_doc(spec, _SKETCH)
    document["connections"][0]["connects_to"].append("tp-argon2")
    write_json(spec, _SKETCH, document)
    assert _reliance(spec, _API) == ["tp-argon2", "tp-mailrelay"]


def test_the_computed_reliance_alone_names_the_third_party_a_connection_reaches(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")
    document = load_doc(spec, _APIS)
    del document["apis"][0]["relies_on"]
    write_json(spec, _APIS, document)
    assert _reliance(spec, _API) == ["tp-mailrelay"]


def test_a_connection_to_a_component_is_not_a_third_party(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")
    document = load_doc(spec, _SKETCH)
    document["connections"][0]["connects_to"] = ["identity-service"]
    write_json(spec, _SKETCH, document)
    assert _reliance(spec, _API) == ["tp-argon2"]
