"""Tests for the spec-graph kind adapter, model and builder (WI-M4-01)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.kinds import KindRegistryError, load_kind_registry
from specdev_tools.graph.model import Graph, Node, node_label

from ._synth import copy_build_spec, make_toolkit, write_json

_FR = "04_fr_list.json"


@pytest.fixture
def toolkit(tmp_path: Path) -> Path:
    return make_toolkit(tmp_path / "tk")


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    return copy_build_spec(tmp_path / "spec")


@pytest.fixture
def graph(spec: Path, toolkit: Path) -> Graph:
    return build_graph(str(spec), str(toolkit))


def _fr_document(spec: Path) -> dict[str, Any]:
    return json.loads((spec / _FR).read_text(encoding="utf-8"))


def test_expand_star_kinds(toolkit: Path) -> None:
    registry = load_kind_registry(str(toolkit))
    kinds = {decl.kind: decl for file in registry.files for decl in file.kinds}
    about = next(link for link in kinds["ambiguity-item"].links if link.field == "about")
    assert about.kinds == registry.kind_names
    assert "seed" in about.kinds and set(kinds) <= set(about.kinds)
    assert all(about.accepts(kind) for kind in registry.kind_names)
    depends_on = next(link for link in kinds["fr"].links if link.field == "depends_on")
    assert depends_on.kinds == ("fr",)
    assert depends_on.accepts("fr") and not depends_on.accepts("api") and not depends_on.accepts("seed")


def test_nodes_from_declarations_only(graph: Graph) -> None:
    assert {node.id for node in graph.nodes} == {
        "seed-accounts", "cap-login", "prod", "dev", "fr-login", "ac-login-1", "ac-login-2", "fr-logout",
        "amb-lockout", "api-login", "LOGIN_ITEM_01", "rec-note",
    }
    assert [n.jq_path for n in graph.by_kind["fr"]] == [".functional_requirements[0]", ".functional_requirements[1]"]


def test_map_keyed_collection_key_is_id(graph: Graph) -> None:
    prod = graph.by_id["prod"]
    assert (prod.kind, prod.step, prod.role, prod.parent) == ("environment", "02a", "obligation-delivery", None)
    assert prod.jq_path == '.environments["prod"]'
    assert [link.target for link in prod.links] == ["cap-login"]


def test_nested_children_and_parent(graph: Graph) -> None:
    assert graph.by_id["fr-login"].children == ("ac-login-1", "ac-login-2")
    assert graph.children == {"fr-login": ["ac-login-1", "ac-login-2"]}
    criterion = graph.by_id["ac-login-1"]
    assert (criterion.kind, criterion.parent, criterion.step) == ("criterion", "fr-login", "04")
    assert criterion.jq_path == ".functional_requirements[0].acceptance_criteria[0]"
    assert graph.by_id["fr-logout"].children == ()


def test_seed_kind_from_manifest(graph: Graph) -> None:
    seed = graph.by_id["seed-accounts"]
    assert (seed.kind, seed.step, seed.links, seed.role) == ("seed", "seed", (), None)
    assert seed.file == "docs/seed/accounts.md" and seed.jq_path == ".seeds[0]"
    assert graph.nodes[0] is seed


def test_plan_file_included_and_milestone_key_read(graph: Graph) -> None:
    item = graph.by_id["LOGIN_ITEM_01"]
    assert (item.file, item.step, item.milestone) == ("impl_context/ms_login_plan.json", "16a", "ms-login")
    assert [link.target for link in item.links] == ["fr-login"]
    assert {node.milestone for node in graph.nodes if node.id != "LOGIN_ITEM_01"} == {None}


def test_deterministic_order_two_runs_equal(spec: Path, toolkit: Path) -> None:
    first, second = build_graph(str(spec), str(toolkit)), build_graph(str(spec), str(toolkit))
    assert first == second
    assert [node.id for node in first.nodes] == [
        "seed-accounts", "cap-login", "prod", "dev", "fr-login", "ac-login-1", "ac-login-2", "fr-logout",
        "amb-lockout", "api-login", "LOGIN_ITEM_01", "rec-note",
    ]


@pytest.mark.parametrize("registry_text", [None, "{", "[]"], ids=["missing", "not-json", "not-an-object"])
def test_registry_missing_is_e520(toolkit: Path, spec: Path, registry_text: str | None) -> None:
    registry = toolkit / "tools" / "entry_key_registry.json"
    if registry_text is None:
        registry.unlink()
    else:
        registry.write_text(registry_text, encoding="utf-8")
    with pytest.raises(KindRegistryError) as raised:
        build_graph(str(spec), str(toolkit))
    assert raised.value.error.code == "E520"
    assert "entry_key_registry.json" in raised.value.error.message


@pytest.mark.parametrize("order_text", ["[1, 2]", "{", None], ids=["not-an-object", "not-json", "missing"])
def test_step_order_that_is_not_an_object_is_e520(toolkit: Path, spec: Path, order_text: str | None) -> None:
    path = toolkit / "tools" / "step_order.json"
    if order_text is None:
        path.unlink()
    else:
        path.write_text(order_text, encoding="utf-8")
    with pytest.raises(KindRegistryError) as raised:
        build_graph(str(spec), str(toolkit))
    assert raised.value.error.code == "E520"
    assert "step_order.json" in raised.value.error.message


def test_registry_regenerated_in_place_is_read_again(toolkit: Path) -> None:
    before = load_kind_registry(str(toolkit))
    document = json.loads((toolkit / "tools" / "entry_key_registry.json").read_text(encoding="utf-8"))
    document["registry"]["04_fr_list.json"]["arrays"][0]["kind"] = "requirement"
    write_json(toolkit, "tools/entry_key_registry.json", document)
    after = load_kind_registry(str(toolkit))
    assert "fr" in before.kind_names and "fr" not in after.kind_names and "requirement" in after.kind_names


@pytest.mark.parametrize("item", [{"statement": "no id"}, {"fr_id": 5}, {"fr_id": ""}, {"fr_id": ["fr-x"]}])
def test_missing_id_item_skipped(spec: Path, toolkit: Path, item: dict[str, Any]) -> None:
    document = _fr_document(spec)
    document["functional_requirements"].append(item)
    built = build_graph(str(spec), str(toolkit), overrides={_FR: document})
    assert [node.id for node in built.by_kind["fr"]] == ["fr-login", "fr-logout"]
    assert built.load_errors == []


def test_nested_node_of_an_item_without_id_has_no_parent(spec: Path, toolkit: Path) -> None:
    document = _fr_document(spec)
    document["functional_requirements"].append({"acceptance_criteria": [{"criterion_id": "ac-orphan"}]})
    built = build_graph(str(spec), str(toolkit), overrides={_FR: document})
    assert built.by_id["ac-orphan"].parent is None


def test_lifecycle_defaults_and_gated_nodes_exclude_not_applicable(graph: Graph) -> None:
    assert graph.by_id["dev"].lifecycle == "not_applicable"
    assert graph.by_id["fr-logout"].lifecycle == "deprecated"
    assert graph.by_id["fr-login"].lifecycle == "active"
    assert "dev" in {node.id for node in graph.live_nodes()}
    assert "dev" not in {node.id for node in graph.gated_nodes()}
    assert len(graph.gated_nodes()) == len(graph.nodes) - 1


@pytest.mark.parametrize("value", [5, ["active"], "retired", None])
def test_wrong_lifecycle_reads_as_active(spec: Path, toolkit: Path, value: Any) -> None:
    document = _fr_document(spec)
    document["functional_requirements"][0]["lifecycle"] = value
    built = build_graph(str(spec), str(toolkit), overrides={_FR: document})
    assert built.by_id["fr-login"].lifecycle == "active"


def test_scope_is_kept_when_it_is_a_string(graph: Graph) -> None:
    assert graph.by_id["fr-login"].scope == "in" and graph.by_id["fr-logout"].scope is None


def test_duplicate_ids_keep_every_definition(spec: Path, toolkit: Path) -> None:
    document = _fr_document(spec)
    document["functional_requirements"].append({"fr_id": "fr-login", "statement": "again"})
    built = build_graph(str(spec), str(toolkit), overrides={_FR: document})
    assert [node.jq_path for node in built.dups["fr-login"]] == [
        ".functional_requirements[0]", ".functional_requirements[2]"
    ]
    assert built.by_id["fr-login"] is built.dups["fr-login"][0]
    assert len(built.by_kind["fr"]) == 3


def test_links_index_both_directions(graph: Graph) -> None:
    assert [(link.field, link.target) for link in graph.outgoing["amb-lockout"]] == [
        ("about", "fr-login"), ("about", "seed-accounts"),
    ]
    assert sorted(link.source for link in graph.incoming["fr-login"]) == [
        "LOGIN_ITEM_01", "amb-lockout", "api-login", "fr-logout",
    ]


@pytest.mark.parametrize("raw", ["{", '["x"]', ""])
def test_unreadable_file_is_a_load_error_and_skipped(spec: Path, toolkit: Path, raw: str) -> None:
    (spec / _FR).write_text(raw, encoding="utf-8")
    built = build_graph(str(spec), str(toolkit))
    assert [(error.file, error.message) for error in built.load_errors] == [
        (_FR, "unreadable or not a JSON object")
    ]
    assert "fr-login" not in built.by_id and "cap-login" in built.by_id


def test_non_utf8_file_is_a_load_error(spec: Path, toolkit: Path) -> None:
    (spec / _FR).write_bytes(b'{"a": "\xff\xfe"}')
    assert [error.file for error in build_graph(str(spec), str(toolkit)).load_errors] == [_FR]


def test_override_replaces_disk_content_and_may_add_a_file(spec: Path, toolkit: Path) -> None:
    extra = {"records": [{"record_id": "rec-extra"}]}
    built = build_graph(
        str(spec), str(toolkit),
        overrides={_FR: {"functional_requirements": [{"fr_id": "fr-only"}]}, "extras/sample/new.json": extra},
    )
    assert [node.id for node in built.by_kind["fr"]] == ["fr-only"]
    assert [node.file for node in built.by_kind["sample-record"]] == ["extras/sample/new.json", "extras/sample/rec.json"]


def test_override_that_is_not_an_object_is_a_load_error(spec: Path, toolkit: Path) -> None:
    built = build_graph(str(spec), str(toolkit), overrides={_FR: ["x"]})
    assert [error.file for error in built.load_errors] == [_FR]


def test_files_and_steps_select_what_is_read(spec: Path, toolkit: Path) -> None:
    only_file = build_graph(str(spec), str(toolkit), files=[_FR])
    assert {node.file for node in only_file.nodes} == {_FR}
    only_steps = build_graph(str(spec), str(toolkit), steps=["seed", "16a"])
    assert [node.id for node in only_steps.nodes] == ["seed-accounts", "LOGIN_ITEM_01"]


def test_extras_record_has_no_step(graph: Graph) -> None:
    record = graph.by_id["rec-note"]
    assert (record.step, record.kind, record.role) == (None, "sample-record", "record")
    assert graph.nodes[-1] is record


def test_unregistered_files_contribute_no_node(spec: Path, toolkit: Path) -> None:
    write_json(spec, "99_unknown.json", {"things": [{"thing_id": "thing-1"}]})
    assert "thing-1" not in build_graph(str(spec), str(toolkit)).by_id


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ({"title": "  A \n b  ", "name": "x"}, "A b"),
        ({"title": "", "name": 5, "statement": "S"}, "S"),
        ({"text": "t" * 200}, "t" * 120),
        ({"title": ["x"], "description": {"a": 1}}, ""),
        ({}, ""),
    ],
)
def test_node_label(item: dict[str, Any], expected: str) -> None:
    assert node_label(item) == expected


def test_label_is_collapsed_text_of_the_first_field(graph: Graph) -> None:
    assert graph.by_id["fr-login"].label == "A user can sign in with a password."
    assert isinstance(graph.by_id["fr-login"], Node)
