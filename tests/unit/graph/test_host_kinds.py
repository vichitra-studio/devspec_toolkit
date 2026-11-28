"""The kinds a host declares in its extension schemas, laid over the toolkit's at run time (DEVSPEC-245, piece B).

Decisions 2, 3 and 5 of the pack: the overlay gives the entries the generator would write for the same schema; a spec
folder with no extension gets the toolkit's registry object itself; a host kind is a ``context`` or an
``obligation-system`` kind and sets neither ``step`` nor ``files``; a schema that fails the annotation lint stops the
graph with one E520 of step 13 that lists the lines; a link that declares ``roles`` accepts the host kinds of those
roles and never a kind of the toolkit by its role.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.registry import clear_shared_caches
from specdev_tools.graph import kinds as toolkit_kinds
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.host_kinds import HOST_ROLES, host_entries, host_kinds, load_kind_registry, overlay
from specdev_tools.graph.kinds import KindDecl, KindRegistry, KindRegistryError, parse_registry
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.registry.generate import generate_registry

from ._extension import (
    CRITERION, DATA_PLACE, DATASTORE, DRAFT_2020_12, MANIFEST, PARKED_TABLE, ROADMAP, SCHEMA_PLACE, SECOND_DATA_PLACE, SECOND_SCHEMA_PLACE, STEP_13,
    TABLE, add_second, criterion, datastores, edit, extension_host, graph_of, lines, read, refusal, second_schema, spec_of, table, table_fields, tables,
)
from ._synth import BUILD_SPEC, EXAMPLE_SPEC, ROOT, copy_build_spec, make_toolkit, write_json

GENERATED = ("tools/entry_key_registry.json", "tools/extraction_paths.json", "tools/step_order.json", "tools/cli_commands.json")


def _refines_of_the_roadmap_schema(node: Any) -> list[str] | None:
    """The ``kinds`` of the one ``x-link`` on a property called ``refines`` in the roadmap schema."""
    if isinstance(node, dict):
        declared = node.get("refines")
        if isinstance(declared, dict) and "x-link" in declared:
            return declared["x-link"]["kinds"]
        node = list(node.values())
    if isinstance(node, list):
        return next((found for found in map(_refines_of_the_roadmap_schema, node) if found is not None), None)
    return None


REFINES_KINDS = tuple(_refines_of_the_roadmap_schema(json.loads((ROOT / "schema" / "14_roadmap.schema.json").read_text(encoding="utf-8"))) or ())
"""The kinds the toolkit lists for ``refines`` of a task criterion, read from its schema."""


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return extension_host(tmp_path / "host")


def _all_decls(registry: KindRegistry) -> dict[str, KindDecl]:
    found: dict[str, KindDecl] = {}

    def add(decls: tuple[KindDecl, ...]) -> None:
        for decl in decls:
            found.setdefault(decl.kind, decl)
            add(decl.nested)

    for file in registry.files:
        add(file.kinds)
    return found


def _link_kinds(registry: KindRegistry, kind: str, field: str) -> tuple[str, ...]:
    return next(link.kinds for link in _all_decls(registry)[kind].links if link.field == field)


def _file_patterns(registry: KindRegistry) -> list[str]:
    return [file.pattern for file in registry.files]


# --- zero change: no extension, no overlay ------------------------------------------------------------------------------


def test_a_spec_folder_with_no_extensions_folder_gets_the_toolkits_registry_object_itself() -> None:
    toolkit = toolkit_kinds.load_kind_registry(str(ROOT))
    assert not (EXAMPLE_SPEC / "extensions").exists()
    assert load_kind_registry(str(ROOT), str(EXAMPLE_SPEC)) is toolkit
    assert load_kind_registry(str(ROOT)) is toolkit
    assert load_kind_registry(str(ROOT), None) is toolkit
    assert load_kind_registry(str(ROOT), str(ROOT / "no-such-spec-folder")) is toolkit


@pytest.mark.parametrize("content", ["an empty folder", "a readme only", "a data file with no schema", "a schema that is refused", "a schema that declares no kind"])
def test_an_extensions_folder_that_declares_no_kind_gets_the_toolkits_registry_object_itself(tmp_path: Path, content: str) -> None:
    spec = tmp_path / "spec"
    shutil.copytree(EXAMPLE_SPEC, spec)
    folder = spec / "extensions"
    folder.mkdir()
    if content == "a readme only":
        (folder / "README.md").write_text("notes\n", encoding="utf-8")
    elif content == "a data file with no schema":
        write_json(spec, "extensions/ext_01_database.json", {"$schema": "vc:ext-01-database"})
    elif content == "a schema that is refused":  # its $id is not the one its file name gives, so it is not loaded as a schema at all
        schema = json.loads((ROOT / "tests" / "fixtures" / "extension_example" / "spec" / SCHEMA_PLACE).read_text(encoding="utf-8"))
        write_json(spec, SCHEMA_PLACE, {**schema, "$id": "vc:ext-01-db"})
    elif content == "a schema that declares no kind":
        write_json(spec, SCHEMA_PLACE, {"$schema": DRAFT_2020_12, "$id": "vc:ext-01-database", "type": "object"})
    assert load_kind_registry(str(ROOT), str(spec)) is toolkit_kinds.load_kind_registry(str(ROOT))


def test_the_toolkits_registry_holds_no_host_kind_after_an_extension_spec_was_read(host: Path) -> None:
    before = load_kind_registry(str(ROOT))
    names_before, patterns_before = before.kind_names, _file_patterns(before)
    overlaid = load_kind_registry(str(ROOT), str(spec_of(host)))
    assert overlaid is not before and {"table", "datastore"} <= set(overlaid.kind_names)
    after = load_kind_registry(str(ROOT))
    assert after is before
    assert (after.kind_names, _file_patterns(after)) == (names_before, patterns_before)
    assert not {"table", "datastore"} & set(after.kind_names)
    assert host_kinds(after) == () and not [pattern for pattern in _file_patterns(after) if pattern.startswith("extensions/")]
    assert _link_kinds(after, "task-criterion", "refines") == REFINES_KINDS
    assert not {"table", "datastore"} & set(_link_kinds(after, "ambiguity-item", "about"))
    assert toolkit_kinds.load_kind_registry(str(ROOT)) is before


def test_reading_an_extension_spec_changes_no_generated_file(host: Path) -> None:
    def digests() -> list[str]:
        return [hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in GENERATED]

    before = digests()
    load_kind_registry(str(ROOT), str(spec_of(host)))
    graph_of(host)
    assert digests() == before
    assert "table" not in (ROOT / GENERATED[0]).read_text(encoding="utf-8").split('"kind": ')[-1]  # no entry of a host kind was appended
    assert '"datastore"' not in (ROOT / GENERATED[0]).read_text(encoding="utf-8")


# --- the overlay --------------------------------------------------------------------------------------------------------


def test_the_overlay_adds_one_file_of_step_13_per_extension_with_its_kinds(host: Path) -> None:
    toolkit = load_kind_registry(str(ROOT))
    overlaid = load_kind_registry(str(ROOT), str(spec_of(host)))
    assert _file_patterns(overlaid) == [*_file_patterns(toolkit), DATA_PLACE]  # the toolkit's files first, in their order
    file = overlaid.files[-1]
    assert (file.step, file.is_glob, [decl.kind for decl in file.kinds]) == ("13", False, ["datastore", "table"])
    assert [(decl.kind, decl.role, decl.host) for decl in host_kinds(overlaid)] == [("datastore", "context", True), ("table", "obligation-system", True)]
    assert set(overlaid.kind_names) == set(toolkit.kind_names) | {"datastore", "table"}
    assert overlaid.kind_names == tuple(sorted(overlaid.kind_names))
    decls = _all_decls(overlaid)
    assert (decls["table"].array_path, decls["table"].id_field, decls["table"].map_keyed) == (".tables", "table_id", False)
    assert decls["table"].contract == ("name", "description", "columns", "scope", "scope_reason")
    assert {link.field: (link.kinds, link.required, link.built, link.same_step_kinds) for link in decls["table"].links} == {
        "derives_from": (("fr",), True, True, ()),
        "part_of": (("datastore",), True, False, ("datastore",)),
        "verified_by": (("fixture", "job"), False, False, ()),
    }
    assert [decl.kind for decl in _all_decls(overlaid).values() if decl.host] == ["datastore", "table"]  # no toolkit kind is marked


def test_the_items_of_the_data_file_are_nodes_of_step_13(host: Path) -> None:
    graph = graph_of(host)
    found = {node.id: (node.kind, node.step, node.role, node.file, node.jq_path, node.parent) for node in graph.nodes if node.file == DATA_PLACE}
    assert found == {
        DATASTORE: ("datastore", "13", "context", DATA_PLACE, ".datastores[0]", None),
        TABLE: ("table", "13", "obligation-system", DATA_PLACE, ".tables[0]", None),
        PARKED_TABLE: ("table", "13", "obligation-system", DATA_PLACE, ".tables[1]", None),
    }
    assert [(link.field, link.target) for link in graph.by_id[TABLE].links] == [
        ("derives_from", "fr-password-reset"), ("part_of", DATASTORE), ("verified_by", "fix-password-reset-reused-token"),
    ]
    assert (graph.by_id[TABLE].scope, graph.by_id[PARKED_TABLE].scope, graph.by_id[DATASTORE].scope) == ("in", "later", None)
    assert graph.shape.kind_steps["table"] == ("13",) and graph.shape.kind_steps["datastore"] == ("13",)
    assert graph.shape.files_by_step["13"] == (MANIFEST, DATA_PLACE)
    assert graph.decls["table"].host and not graph.decls["fr"].host
    assert [link.source for link in graph.incoming[TABLE]] == [CRITERION]
    assert [error.render() for error in resolve_graph(graph)] == []


def test_the_same_registry_object_serves_a_spec_folder_until_a_schema_changes(host: Path) -> None:
    first = load_kind_registry(str(ROOT), str(spec_of(host)))
    assert load_kind_registry(str(ROOT), str(spec_of(host))) is first
    assert load_kind_registry(str(ROOT), str(spec_of(host)) + os.sep) is first  # the folder, however it is typed
    edit(host, SCHEMA_PLACE, lambda schema: tables(schema)["x-node"].update(contract=["name"]))
    second = load_kind_registry(str(ROOT), str(spec_of(host)))
    assert second is not first
    assert _all_decls(second)["table"].contract == ("name",) and _all_decls(first)["table"].contract != ("name",)


def test_two_spec_folders_in_one_process_each_keep_their_own_kinds(tmp_path: Path, host: Path) -> None:
    """The step gate reads a head tree and a baseline tree: one with the extension, one without, one with another."""
    other = extension_host(tmp_path / "other")
    edit(other, SCHEMA_PLACE, lambda schema: tables(schema)["x-node"].update(kind="relation"))
    edit(other, ROADMAP, lambda roadmap: criterion(roadmap).update(refines=["ac-password-reset-3"]))
    plain = str(EXAMPLE_SPEC)
    for _round in range(2):
        with_table = load_kind_registry(str(ROOT), str(spec_of(host)))
        with_relation = load_kind_registry(str(ROOT), str(spec_of(other)))
        assert "table" in with_table.kind_names and "relation" not in with_table.kind_names
        assert "relation" in with_relation.kind_names and "table" not in with_relation.kind_names
        assert load_kind_registry(str(ROOT), plain) is load_kind_registry(str(ROOT))
    assert load_kind_registry(str(ROOT), str(spec_of(host))) is with_table and load_kind_registry(str(ROOT), str(spec_of(other))) is with_relation
    assert graph_of(host).by_id[TABLE].kind == "table" and graph_of(other).by_id[TABLE].kind == "relation"
    assert TABLE not in build_graph(plain, str(ROOT)).by_id


def test_two_extensions_give_two_files_in_name_order_and_a_link_may_name_a_kind_of_the_other(host: Path) -> None:
    uses = {"type": "array", "items": {"$ref": "vc:core:atoms#kebabId"}, "x-link": {"kinds": ["datastore"], "required": False, "same_step_kinds": ["datastore"]}}
    add_second(host, second_schema(part_of=uses), {"cache_id": "cache-reset-attempts", "name": "Reset attempts", "derives_from": ["identity-service"], "part_of": [DATASTORE]})
    overlaid = load_kind_registry(str(ROOT), str(spec_of(host)))
    assert _file_patterns(overlaid)[-2:] == [DATA_PLACE, SECOND_DATA_PLACE]
    assert [decl.kind for decl in host_kinds(overlaid)] == ["datastore", "table", "cache"]
    graph = graph_of(host)
    assert (graph.by_id["cache-reset-attempts"].file, graph.by_id["cache-reset-attempts"].step) == (SECOND_DATA_PLACE, "13")
    assert graph.shape.files_by_step["13"] == (MANIFEST, DATA_PLACE, SECOND_DATA_PLACE)
    assert [error.render() for error in resolve_graph(graph)] == []  # a kind of another extension is a declared kind, in the same step


def test_an_extension_with_no_node_and_a_kind_with_no_link_are_legal(host: Path) -> None:
    schema = second_schema()
    del schema["properties"]["caches"]["items"]["properties"]["derives_from"]
    add_second(host, schema, {"cache_id": "cache-alone", "name": "Alone"})
    graph = graph_of(host)
    assert graph.by_id["cache-alone"].links == () and graph.decls["cache"].links == ()
    del schema["properties"]["caches"]["x-node"]  # now the second extension declares no node at all
    add_second(host, schema, {"cache_id": "cache-alone", "name": "Alone"})
    overlaid = load_kind_registry(str(ROOT), str(spec_of(host)))
    assert SECOND_DATA_PLACE not in _file_patterns(overlaid) and "cache" not in overlaid.kind_names
    assert "cache-alone" not in graph_of(host).by_id and TABLE in graph_of(host).by_id


# --- the overlay is the generator's output ------------------------------------------------------------------------------

_ID = {"$ref": "vc:core:atoms#kebabId"}
_IDS = {"type": "array", "items": _ID}


def _stock_schema(uri: str) -> dict[str, Any]:
    """A schema in the vocabulary of the mini toolkit: an array kind, a nested kind, a map-keyed kind, a shared kind by ``$ref``, every link key."""
    return {
        "$schema": DRAFT_2020_12,
        "$id": uri,
        "type": "object",
        "properties": {
            "warehouses": {
                "type": "array",
                "x-node": {"kind": "warehouse", "role": "context", "contract": ["name"], "id": "warehouse_id"},
                "items": {
                    "type": "object",
                    "required": ["warehouse_id"],
                    "properties": {
                        "warehouse_id": _ID, "name": {"type": "string"}, "lifecycle": {"$ref": "vc:core:graph#lifecycle"},
                        "derives_from": {**_IDS, "x-link": {"kinds": ["capability"], "required": True, "built": True}},
                        "relies_on": {**_IDS, "x-link": {"kinds": ["capability"], "required": False, "roles": ["obligation-system"], "same_step_kinds": []}},
                    },
                },
            },
            "shelves": {"type": "array", "x-node": {"kind": "shelf", "role": "obligation-system", "contract": ["name", "scope"], "id": "shelf_id", "coarse": True}, "items": {"$ref": "#/$defs/shelf"}},
            "zones": {
                "type": "object",
                "x-node": {"kind": "zone", "role": "context", "contract": ["name"], "map_keyed": True},
                "additionalProperties": {"type": "object", "properties": {"name": {"type": "string"}, "lifecycle": {"$ref": "vc:core:graph#lifecycle"}}},
            },
            "ambiguities": {"$ref": "vc:core:ambiguity-fixture#/$defs/ambiguityList"},
        },
        "$defs": {
            "shelf": {
                "type": "object",
                "required": ["shelf_id"],
                "allOf": [{"$ref": "vc:core:graph#scopeReasonRule"}],
                "properties": {
                    "shelf_id": _ID, "name": {"type": "string"}, "lifecycle": {"$ref": "vc:core:graph#lifecycle"},
                    "scope": {"$ref": "vc:core:graph#scope"}, "scope_reason": {"$ref": "vc:core:graph#scopeReason"},
                    "derives_from": {**_IDS, "x-link": {"kinds": ["fr", "seed"], "required": True, "built": True, "additional_kinds": ["seed"]}},
                    "part_of": {**_IDS, "x-link": {"kinds": ["warehouse"], "required": True, "same_step_kinds": ["warehouse"]}},
                    "about": {"type": "array", "items": {"$ref": "vc:core:graph#nodeId"}, "x-link": {"kinds": "*", "required": False}},
                    "bins": {
                        "type": "array",
                        "x-node": {"kind": "bin", "role": "context", "contract": ["label"], "id": "bin_id"},
                        "items": {"type": "object", "required": ["bin_id"], "properties": {"bin_id": _ID, "label": {"type": "string"}, "lifecycle": {"$ref": "vc:core:graph#lifecycle"}}},
                    },
                },
            },
        },
    }


_STOCK_DATA = {
    "$schema": "vc:ext-01-stock",
    "warehouses": [{"warehouse_id": "wh-north", "name": "North", "derives_from": ["cap-login"], "relies_on": ["shelf-a"]}],
    "shelves": [{"shelf_id": "shelf-a", "name": "A", "derives_from": ["fr-login"], "part_of": ["wh-north"], "bins": [{"bin_id": "bin-a-1", "label": "A1"}]}],
    "zones": {"zone-cold": {"name": "Cold"}},
    "ambiguities": [{"ambiguity_id": "amb-shelf", "text": "How deep is a shelf?", "about": ["fr-login"]}],
}
"""The open item is about an upstream node: one about a node of its own step is E702, as in every step file."""


def _of_step_13(generated: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The file key and the entry the generator registered for step 13 (it names the file of step 13 by its own table, not by the schema's stem)."""
    found = [(key, value) for key, value in generated["registry"].items() if value["step"] == "13"]
    assert len(found) == 1
    return found[0]


def _without_host_mark(decl: KindDecl, dropped_link: str) -> KindDecl:
    return dataclasses.replace(
        decl, host=False, links=tuple(link for link in decl.links if link.field != dropped_link),
        nested=tuple(_without_host_mark(child, dropped_link) for child in decl.nested),
    )


@pytest.fixture
def stock(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    """A synthetic toolkit, a spec folder whose extension ``ext-01-stock`` has the schema, and the registry a second toolkit generates with the same schema as its step 13."""
    as_step = make_toolkit(tmp_path / "toolkit_with_step_13")
    write_json(as_step, "schema/13_stock.schema.json", _stock_schema("vc:13-stock"))
    mapping = json.loads((as_step / "tools" / "schema_registry.json").read_text(encoding="utf-8"))
    write_json(as_step, "tools/schema_registry.json", {**mapping, "vc:13-stock": "schema/13_stock.schema.json"})
    clear_shared_caches()
    generated, _extraction = generate_registry(str(as_step))
    toolkit = make_toolkit(tmp_path / "toolkit")
    spec = copy_build_spec(tmp_path / "spec")
    write_json(spec, "extensions/ext_01_stock.schema.json", _stock_schema("vc:ext-01-stock"))
    write_json(spec, "extensions/ext_01_stock.json", _STOCK_DATA)
    return toolkit, spec, generated


def test_the_entries_of_the_overlay_are_those_the_generator_writes_for_the_same_schema(stock: tuple[Path, Path, dict[str, Any]]) -> None:
    toolkit, spec, generated = stock
    _key, written = _of_step_13(generated)
    assert [entry["kind"] for entry in written["arrays"]] == ["warehouse", "shelf", "zone", "ambiguity-item"]  # the fixture is not empty
    found = host_entries(str(toolkit), str(spec))
    assert dict(found.files) == {"extensions/ext_01_stock.json": written["arrays"]}
    assert dict(found.roles) == {"warehouse": "context", "shelf": "obligation-system", "zone": "context", "bin": "context"}  # not the shared ambiguity-item
    document = json.loads((toolkit / "tools" / "entry_key_registry.json").read_text(encoding="utf-8"))
    laid = overlay(document, found)
    assert laid["registry"]["extensions/ext_01_stock.json"]["step"] == "13"
    assert {key: value for key, value in laid.items() if key != "registry"} == {key: value for key, value in document.items() if key != "registry"}
    assert {key: value for key, value in laid["registry"].items() if key != "extensions/ext_01_stock.json"} == document["registry"]
    assert "extensions/ext_01_stock.json" not in document["registry"]  # the document read from disk was not changed


def test_the_parsed_host_kinds_are_the_generated_ones_but_for_the_host_mark_and_the_kinds_added_by_role(stock: tuple[Path, Path, dict[str, Any]]) -> None:
    toolkit, spec, generated = stock
    overlaid = load_kind_registry(str(toolkit), str(spec))
    as_step = parse_registry(generated)
    host_file = next(file for file in overlaid.files if file.pattern == "extensions/ext_01_stock.json")
    step_file = next(file for file in as_step.files if file.pattern == _of_step_13(generated)[0])
    assert host_file.step == step_file.step == "13"
    assert overlaid.kind_names == as_step.kind_names
    assert [_without_host_mark(decl, "relies_on") for decl in host_file.kinds] == [_without_host_mark(decl, "relies_on") for decl in step_file.kinds]
    assert [decl.kind for decl in host_kinds(overlaid)] == ["warehouse", "shelf", "bin", "zone"] and host_kinds(as_step) == ()
    assert not _all_decls(overlaid)["ambiguity-item"].host  # reached by $ref: the toolkit's kind, registered once more
    # the link that declares roles: the host kind of the role is added, the toolkit's kinds of that role (fr, criterion) are not
    assert _link_kinds(as_step, "warehouse", "relies_on") == ("capability",)
    assert _link_kinds(overlaid, "warehouse", "relies_on") == ("capability", "shelf")
    assert {decl.kind for decl in _all_decls(overlaid).values() if decl.role == "obligation-system"} >= {"fr", "criterion", "shelf"}


def test_the_nodes_of_a_synthetic_extension_are_built_nested_and_map_keyed(stock: tuple[Path, Path, dict[str, Any]]) -> None:
    toolkit, spec, _generated = stock
    graph = build_graph(str(spec), str(toolkit))
    found = {node.id: (node.kind, node.step, node.parent) for node in graph.nodes if node.file == "extensions/ext_01_stock.json"}
    assert found == {
        "wh-north": ("warehouse", "13", None), "shelf-a": ("shelf", "13", None), "bin-a-1": ("bin", "13", "shelf-a"),
        "zone-cold": ("zone", "13", None), "amb-shelf": ("ambiguity-item", "13", None),
    }
    assert graph.by_id["shelf-a"].children == ("bin-a-1",) and graph.by_id["bin-a-1"].jq_path == ".shelves[0].bins[0]"
    added = [error for error in resolve_graph(graph) if error.render() not in {found.render() for found in resolve_graph(build_graph(str(BUILD_SPEC), str(toolkit)))}]
    # relies_on accepts the shelf (no E701) only because the overlay added it by role; nothing declares it a same-step target, so the direction rule speaks
    assert [(error.code, error.node_id, error.owner, error.target) for error in added] == [("E702", "wh-north", "step:13", "relies_on->shelf-a")]
    assert "the target is in the same step and a shelf is not declared as a same-step target of the field" in added[0].message


# --- decision 3: what a host kind may not declare -----------------------------------------------------------------------


@pytest.mark.parametrize("role", ["verifier", "record", "plan", "obligation-delivery"])
def test_a_host_kind_may_not_take_a_role_other_than_context_and_obligation_system(host: Path, role: str) -> None:
    edit(host, SCHEMA_PLACE, lambda schema: tables(schema)["x-node"].update(role=role))
    error = refusal(host)
    assert (error.code, error.owner, error.node_id) == ("E520", STEP_13, None)
    assert [line for line in lines(error) if f"an extension kind may not take the role '{role}'" in line and line.startswith(f"{SCHEMA_PLACE} /properties/tables")] != []
    assert "context and obligation-system" in error.message


def test_the_two_roles_a_host_kind_may_take_are_accepted(host: Path) -> None:
    assert HOST_ROLES == ("context", "obligation-system")
    edit(host, SCHEMA_PLACE, lambda schema: datastores(schema)["x-node"].update(role="obligation-system"))
    error = refusal(host)  # an obligation kind needs scope, scope_reason and the scope rule: the lint's lines, and no line about the role
    assert [line for line in lines(error) if "may not take the role" in line] == []
    assert len([line for line in lines(error) if line.startswith("ANNOT-08") and "'datastore'" in line]) == 3
    edit(host, SCHEMA_PLACE, lambda schema: datastores(schema)["x-node"].update(role="context"))
    assert [(decl.kind, decl.role) for decl in host_kinds(load_kind_registry(str(ROOT), str(spec_of(host))))] == [("datastore", "context"), ("table", "obligation-system")]


@pytest.mark.parametrize(("key", "value"), [("step", "13"), ("step", "04"), ("files", ["extensions/ext_01_database.json"]), ("files", ["impl_context/ms_*_plan.json"])])
def test_a_host_kind_may_not_set_its_step_or_its_files(host: Path, key: str, value: Any) -> None:
    edit(host, SCHEMA_PLACE, lambda schema: tables(schema)["x-node"].update({key: value}))
    error = refusal(host)
    assert (error.code, error.owner) == ("E520", STEP_13)
    assert [line for line in lines(error) if f"an extension kind may not set '{key}'" in line and line.startswith(f"{SCHEMA_PLACE} /properties/tables")] != []
    assert len(lines(error)) == 1


def test_a_key_a_host_kind_may_set_is_not_refused(host: Path) -> None:
    edit(host, SCHEMA_PLACE, lambda schema: tables(schema)["x-node"].update(coarse=True))
    assert "table" in load_kind_registry(str(ROOT), str(spec_of(host))).kind_names


def test_a_host_kind_may_not_be_the_top_of_the_graph(host: Path) -> None:
    def change(schema: dict[str, Any]) -> None:
        node = datastores(schema)["x-node"]
        del node["role"], node["contract"]
        node["top_of_graph"] = True

    edit(host, SCHEMA_PLACE, change)
    error = refusal(host)
    assert [line for line in lines(error) if "an extension kind may not set 'top_of_graph'" in line and line.startswith(f"{SCHEMA_PLACE} /properties/datastores")] != []


def test_one_e520_lists_every_line_and_no_kind_of_any_extension_is_loaded(host: Path) -> None:
    add_second(host, second_schema(role="verifier"), {"cache_id": "cache-reset-attempts", "name": "Reset attempts", "derives_from": ["identity-service"]})
    edit(host, SCHEMA_PLACE, lambda schema: tables(schema)["x-node"].update(step="13"))
    with pytest.raises(KindRegistryError) as raised:
        load_kind_registry(str(ROOT), str(spec_of(host)))
    error = raised.value.error
    assert (error.code, error.owner) == ("E520", STEP_13)
    assert len(lines(error)) == 2
    assert [line.split(":")[0] for line in lines(error)] == [f"{SCHEMA_PLACE} /properties/tables", f"{SECOND_SCHEMA_PLACE} /properties/caches"]
    assert str(host) not in error.message  # the schema is named by its place in the spec folder
    with pytest.raises(KindRegistryError):
        graph_of(host)  # the first extension's schema is correct but for the one line: none of its kinds is loaded either
    assert "table" not in load_kind_registry(str(ROOT)).kind_names  # and the toolkit's own registry is still read
    edit(host, SCHEMA_PLACE, lambda schema: tables(schema)["x-node"].pop("step"))
    assert lines(refusal(host)) == [line for line in lines(error) if line.startswith(SECOND_SCHEMA_PLACE)]  # one line corrected, one left
    edit(host, SECOND_SCHEMA_PLACE, lambda schema: schema["properties"]["caches"]["x-node"].update(role="context"))
    assert {"table", "cache"} <= set(graph_of(host).decls)  # both corrected: read again with no cache cleared


# --- the lines of the annotation lint, on a host schema -----------------------------------------------------------------


def _rename_field(schema: dict[str, Any], old: str, new: str) -> None:
    fields = table_fields(schema)
    fields[new] = fields.pop(old)
    required = tables(schema)["items"]["required"]
    required[required.index(old)] = new


LINT_CASES: dict[str, tuple[Any, list[str]]] = {
    # name: (an edit of the schema, the words one line of the E520 holds)
    "a kind name the toolkit has": (
        lambda schema: tables(schema)["x-node"].update(kind="fr"),
        ["ANNOT-02 kind 'fr' is declared at more than one site", "schema/04_fr_list.schema.json", f"{SCHEMA_PLACE} /properties/tables"],
    ),
    "a role outside the closed list": (
        lambda schema: tables(schema)["x-node"].update(role="storage"), ["ANNOT-01", SCHEMA_PLACE, "invalid x-node", "'storage'"],
    ),
    "an annotation key outside the closed list": (
        lambda schema: tables(schema)["x-node"].update(colour="blue"), ["ANNOT-01", SCHEMA_PLACE, "invalid x-node", "colour"],
    ),
    "a link field that is not a verb": (
        lambda schema: _rename_field(schema, "part_of", "stores"),
        ["ANNOT-05", SCHEMA_PLACE, "x-link field 'stores' is not a verb of linkVerb"],
    ),
    "a link to a kind nobody declares": (
        lambda schema: table_fields(schema)["derives_from"]["x-link"].update(kinds=["tablespace"]),
        ["ANNOT-07", SCHEMA_PLACE, "x-link kind 'tablespace' is not a declared kind"],
    ),
    "a kind with no lifecycle": (
        lambda schema: datastores(schema)["items"]["properties"].pop("lifecycle"),
        ["ANNOT-08", SCHEMA_PLACE, "'datastore' must declare lifecycle"],
    ),
    "an obligation kind with no scope": (
        lambda schema: table_fields(schema).pop("scope"), ["ANNOT-08", SCHEMA_PLACE, "obligation item of 'table' must declare scope"],
    ),
    "an obligation kind with no scope_reason": (
        lambda schema: table_fields(schema).pop("scope_reason"), ["ANNOT-08", SCHEMA_PLACE, "obligation item of 'table' must declare scope_reason"],
    ),
    "an obligation kind with no scope rule": (
        lambda schema: tables(schema)["items"].pop("allOf"), ["ANNOT-08", SCHEMA_PLACE, "'table' must carry", "vc:core:graph#scopeReasonRule in allOf"],
    ),
    "a roles entry that is not a role": (
        lambda schema: table_fields(schema)["derives_from"]["x-link"].update(roles=["storage"]), ["ANNOT-01", SCHEMA_PLACE, "invalid x-link", "'storage'"],
    ),
    "an empty roles list": (
        lambda schema: table_fields(schema)["derives_from"]["x-link"].update(roles=[]), ["ANNOT-01", SCHEMA_PLACE, "invalid x-link"],
    ),
}


@pytest.mark.parametrize("case", sorted(LINT_CASES))
def test_a_host_schema_that_fails_the_annotation_lint_stops_the_graph_with_one_e520_of_step_13(host: Path, case: str) -> None:
    change, words = LINT_CASES[case]
    edit(host, SCHEMA_PLACE, change)
    error = refusal(host)
    assert (error.code, error.owner) == ("E520", STEP_13)
    assert [line for line in lines(error) if all(word in line for word in words)] != [], lines(error)
    assert "extensions/*.schema.json" in error.message.splitlines()[0] and "no kind of an extension is loaded" in error.message.splitlines()[0]


def test_a_kind_name_that_two_extensions_declare_is_refused_naming_both_schema_files(host: Path) -> None:
    add_second(host, second_schema(kind="table", role="context"), {"cache_id": "cache-reset-attempts", "name": "Reset attempts", "derives_from": ["identity-service"]})
    matching = [line for line in lines(refusal(host)) if line.startswith("ANNOT-02 kind 'table' is declared at more than one site")]
    assert len(matching) == 1 and f"{SCHEMA_PLACE} /properties/tables" in matching[0] and f"{SECOND_SCHEMA_PLACE} /properties/caches" in matching[0]


def test_the_example_schema_as_it_is_passes_the_lint(host: Path) -> None:
    assert sorted(decl.kind for decl in host_kinds(load_kind_registry(str(ROOT), str(spec_of(host))))) == ["datastore", "table"]


# --- decision 5: refines opens to host obligation kinds, by role --------------------------------------------------------


def test_refines_accepts_the_host_obligation_kinds_after_the_toolkits_and_no_host_context_kind(host: Path) -> None:
    assert len(REFINES_KINDS) == 16
    toolkit, overlaid = load_kind_registry(str(ROOT)), load_kind_registry(str(ROOT), str(spec_of(host)))
    assert _link_kinds(toolkit, "task-criterion", "refines") == REFINES_KINDS
    assert _link_kinds(overlaid, "task-criterion", "refines") == (*REFINES_KINDS, "table")
    add_second(host, second_schema(kind="cache", role="obligation-system"), {"cache_id": "cache-reset-attempts", "name": "Reset attempts", "derives_from": ["identity-service"]})
    assert _link_kinds(load_kind_registry(str(ROOT), str(spec_of(host))), "task-criterion", "refines") == (*REFINES_KINDS, "cache", "table")


def test_no_other_link_of_the_toolkit_gains_a_host_kind_but_those_that_accept_any_kind(host: Path) -> None:
    toolkit, overlaid = _all_decls(load_kind_registry(str(ROOT))), _all_decls(load_kind_registry(str(ROOT), str(spec_of(host))))
    all_toolkit = load_kind_registry(str(ROOT)).kind_names
    gained = {
        (kind, link.field) for kind, decl in overlaid.items() if not decl.host for link in decl.links
        if {"table", "datastore"} & set(link.kinds)
    }
    any_kind = {(kind, link.field) for kind, decl in toolkit.items() for link in decl.links if link.kinds == all_toolkit}
    assert {field for _kind, field in any_kind} == {"about", "removes", "replaces"}  # the three verbs the design gives every kind
    assert gained == any_kind | {("task-criterion", "refines")}
    for kind, decl in toolkit.items():
        for link in decl.links:
            if (kind, link.field) not in gained:
                assert _link_kinds(load_kind_registry(str(ROOT), str(spec_of(host))), kind, link.field) == link.kinds


def test_a_criterion_refines_a_host_obligation_and_a_host_context_kind_is_e701(host: Path) -> None:
    graph = graph_of(host)
    assert [link.target for link in graph.by_id[CRITERION].links if link.field == "refines"] == [TABLE]
    assert [error.render() for error in resolve_graph(graph)] == []
    edit(host, ROADMAP, lambda roadmap: criterion(roadmap).update(refines=[DATASTORE]))
    errors = resolve_graph(graph_of(host))
    assert [(error.code, error.node_id, error.owner, error.target) for error in errors] == [("E701", CRITERION, "step:14", f"refines->{DATASTORE}")]
    assert f"target '{DATASTORE}' is a datastore; the field accepts: " in errors[0].message
    accepted = errors[0].message.split("the field accepts: ")[1].split(", ")
    assert accepted == [*REFINES_KINDS, "table"]


def test_without_the_extension_the_criterion_that_names_the_table_dangles(host: Path) -> None:
    (spec_of(host) / SCHEMA_PLACE).unlink()
    errors = resolve_graph(graph_of(host))
    assert [(error.code, error.node_id, error.target) for error in errors] == [("E700", CRITERION, f"refines->{TABLE}")]
    assert "no node has that id" in errors[0].message


# --- odd but legal data -------------------------------------------------------------------------------------------------


def test_an_empty_link_list_a_link_listed_twice_and_an_id_with_a_brace(host: Path) -> None:
    def change(document: dict[str, Any]) -> None:
        table(document)["derives_from"] = ["fr-password-reset", "fr-password-reset"]
        table(document, PARKED_TABLE)["derives_from"] = []
        document["tables"].append({"table_id": "tbl-{audit}", "name": "audit", "description": "x", "columns": [], "derives_from": ["fr-password-reset"], "part_of": [DATASTORE]})

    edit(host, DATA_PLACE, change)
    graph = graph_of(host)
    assert [link.target for link in graph.by_id[TABLE].links if link.field == "derives_from"] == ["fr-password-reset", "fr-password-reset"]
    assert [link.field for link in graph.by_id[PARKED_TABLE].links] == ["part_of"]
    assert (graph.by_id["tbl-{audit}"].kind, graph.by_id["tbl-{audit}"].jq_path) == ("table", ".tables[2]")
    assert [error.render() for error in resolve_graph(graph)] == []


def test_a_link_of_a_host_node_to_a_later_step_is_e702_and_to_its_own_step_needs_the_kind_declared(host: Path) -> None:
    edit(host, SCHEMA_PLACE, lambda schema: table_fields(schema)["derives_from"]["x-link"].update(kinds=["fr", "task", "datastore"]))
    edit(host, DATA_PLACE, lambda document: table(document).update(derives_from=["fr-password-reset", "task-implement-password-reset-confirm", DATASTORE]))
    errors = resolve_graph(graph_of(host))
    assert [(error.code, error.node_id, error.owner, error.target) for error in errors] == [
        ("E702", TABLE, STEP_13, "derives_from->task-implement-password-reset-confirm"), ("E702", TABLE, STEP_13, f"derives_from->{DATASTORE}"),
    ]
    assert "the target is in a later step; a link points to an earlier step" in errors[0].message
    assert "the target is in the same step and a datastore is not declared as a same-step target of the field" in errors[1].message


# --- fix round 1, F1: a schema that refers to itself ----------------------------------------------------------------------

_GROUP_ITEMS = {"type": "array", "items": {"$ref": "#/$defs/group"}}
_KEBAB = {"$ref": "vc:core:atoms#kebabId"}
THIRD_SCHEMA_PLACE = "extensions/ext_03_members.schema.json"


def _plain_groups(shape: str) -> dict[str, dict[str, Any]]:
    """Extension schemas with no annotation in which a definition reaches itself; keyed by the place of each schema file."""
    group: dict[str, Any] = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}
    defs: dict[str, Any] = {"group": group}
    others: dict[str, dict[str, Any]] = {}
    if shape == "itself":
        group["properties"]["groups"] = _GROUP_ITEMS
    elif shape == "two definitions":
        group["properties"]["members"] = {"type": "array", "items": {"$ref": "#/$defs/member"}}
        defs["member"] = {"type": "object", "properties": {"name": {"type": "string"}, "groups": _GROUP_ITEMS}}
    elif shape == "another host schema":
        group["properties"]["members"] = {"type": "array", "items": {"$ref": "vc:ext-03-members#/$defs/member"}}
        member = {"type": "object", "properties": {"name": {"type": "string"}, "groups": {"type": "array", "items": {"$ref": "vc:ext-02-cache#/$defs/group"}}}}
        others[THIRD_SCHEMA_PLACE] = {"$schema": DRAFT_2020_12, "$id": "vc:ext-03-members", "type": "object", "$defs": {"member": member}}
    elif shape == "through allOf and a condition":
        group["allOf"] = [{"$ref": "#/$defs/group"}]
        group["if"] = {"$ref": "#/$defs/group"}
    else:
        raise AssertionError(shape)
    schema = {
        "$schema": DRAFT_2020_12, "$id": "vc:ext-02-cache", "type": "object", "allOf": [{"$ref": "vc:core:step-base"}],
        "$defs": defs, "properties": {"groups": _GROUP_ITEMS}, "required": ["groups"],
    }
    return {SECOND_SCHEMA_PLACE: schema, **others}


def _write_schemas(host: Path, schemas: dict[str, dict[str, Any]]) -> None:
    for place, schema in schemas.items():
        write_json(spec_of(host), place, schema)


@pytest.mark.parametrize("shape", ["itself", "two definitions", "another host schema", "through allOf and a condition"])
def test_a_schema_with_no_annotation_whose_definition_reaches_itself_declares_no_kind(tmp_path: Path, host: Path, shape: str) -> None:
    """On its own it leaves the toolkit's registry as it is; beside the example's extension it adds no file and takes none away."""
    alone = tmp_path / "alone"
    shutil.copytree(EXAMPLE_SPEC, alone / "spec")
    (alone / "spec" / "extensions").mkdir()
    _write_schemas(alone, _plain_groups(shape))
    assert load_kind_registry(str(ROOT), str(alone / "spec")) is toolkit_kinds.load_kind_registry(str(ROOT))
    assert len(graph_of(alone).nodes) == len(build_graph(str(EXAMPLE_SPEC), str(ROOT)).nodes)
    before = load_kind_registry(str(ROOT), str(spec_of(host)))
    _write_schemas(host, _plain_groups(shape))
    after = load_kind_registry(str(ROOT), str(spec_of(host)))
    assert _file_patterns(after) == _file_patterns(before) and [decl.kind for decl in host_kinds(after)] == ["datastore", "table"]
    assert TABLE in graph_of(host).by_id


def _group_kind(**more: Any) -> dict[str, Any]:
    """An array of groups that carries the ``x-node`` of the kind ``group``; *more* is merged into the properties of a group."""
    properties = {"group_id": _KEBAB, "name": {"type": "string"}, "lifecycle": {"$ref": "vc:core:graph#lifecycle"}, **more}
    return {
        "type": "array",
        "x-node": {"kind": "group", "role": "context", "contract": ["name"], "id": "group_id"},
        "items": {"type": "object", "required": ["group_id", "name"], "properties": properties},
    }


def _groups_schema(defs: dict[str, Any], top: dict[str, Any]) -> dict[str, Any]:
    return {"$schema": DRAFT_2020_12, "$id": "vc:ext-02-cache", "type": "object", "allOf": [{"$ref": "vc:core:step-base"}], "$defs": defs, "properties": top}


def _groups_data(groups: list[dict[str, Any]], **more: Any) -> dict[str, Any]:
    return {"$schema": "vc:ext-02-cache", "id": "ext-groups", "owner": "data", "created_at": "2026-11-15T00:00:00Z", "canonical_refs_used": [], "groups": groups, **more}


def _nested_in_itself(error: Any) -> list[str]:
    return [line for line in lines(error) if "nested in itself" in line]


def test_a_kind_whose_items_hold_the_kind_itself_is_one_line_of_the_e520_that_names_the_place(host: Path) -> None:
    """A group that holds groups: the registry is a tree of kinds and cannot say "a kind nested in itself"; the schema is refused in words, and no command recurses."""
    schema = _groups_schema({"groups": _group_kind(groups={"$ref": "#/$defs/groups"})}, {"groups": {"$ref": "#/$defs/groups"}})
    write_json(spec_of(host), SECOND_SCHEMA_PLACE, schema)
    write_json(spec_of(host), SECOND_DATA_PLACE, _groups_data([{"group_id": "grp-a", "name": "A", "groups": [{"group_id": "grp-b", "name": "B"}]}]))
    error = refusal(host)
    assert (error.code, error.owner) == ("E520", STEP_13)
    [line] = _nested_in_itself(error)
    assert line.startswith(f"{SECOND_SCHEMA_PLACE} /$defs/groups") and "'group'" in line
    assert len(lines(error)) == 1  # the one line: the example's own schema is right
    with pytest.raises(KindRegistryError):
        load_kind_registry(str(ROOT), str(spec_of(host)))


def test_a_kind_that_reaches_itself_through_another_kind_is_refused_the_same_way(host: Path) -> None:
    member = {
        "type": "array",
        "x-node": {"kind": "member", "role": "context", "contract": ["name"], "id": "member_id"},
        "items": {"type": "object", "required": ["member_id", "name"], "properties": {
            "member_id": _KEBAB, "name": {"type": "string"}, "lifecycle": {"$ref": "vc:core:graph#lifecycle"}, "groups": {"$ref": "#/$defs/groups"},
        }},
    }
    schema = _groups_schema({"groups": _group_kind(members={"$ref": "#/$defs/members"}), "members": member}, {"groups": {"$ref": "#/$defs/groups"}})
    write_json(spec_of(host), SECOND_SCHEMA_PLACE, schema)
    [line] = _nested_in_itself(refusal(host))
    assert line.startswith(f"{SECOND_SCHEMA_PLACE} /$defs/groups") and "'group'" in line


def test_one_definition_of_a_kind_used_by_two_arrays_side_by_side_is_no_cycle(host: Path) -> None:
    """Next to the refusal: the same annotated definition reached twice, neither inside the other."""
    schema = _groups_schema({"groups": _group_kind()}, {"groups": {"$ref": "#/$defs/groups"}, "archived": {"$ref": "#/$defs/groups"}})
    write_json(spec_of(host), SECOND_SCHEMA_PLACE, schema)
    write_json(spec_of(host), SECOND_DATA_PLACE, _groups_data([{"group_id": "grp-a", "name": "A"}], archived=[{"group_id": "grp-old", "name": "Old"}]))
    graph = graph_of(host)
    assert (graph.by_id["grp-a"].kind, graph.by_id["grp-old"].kind) == ("group", "group")
    [entries] = [file.kinds for file in load_kind_registry(str(ROOT), str(spec_of(host))).files if file.pattern == SECOND_DATA_PLACE]
    assert sorted(decl.array_path for decl in entries) == [".archived", ".groups"]


def test_a_kind_whose_items_hold_a_plain_tree_is_loaded_once_and_the_tree_is_data(host: Path) -> None:
    """Next to the refusal: the cycle is below the kind and carries no ``x-node``, so nothing of it is a node."""
    tree = {"type": "object", "properties": {"label": {"type": "string"}, "children": {"type": "array", "items": {"$ref": "#/$defs/tree"}}}}
    schema = _groups_schema({"tree": tree}, {"groups": _group_kind(layout={"$ref": "#/$defs/tree"})})
    write_json(spec_of(host), SECOND_SCHEMA_PLACE, schema)
    layout = {"label": "root", "children": [{"label": "leaf", "children": []}]}
    write_json(spec_of(host), SECOND_DATA_PLACE, _groups_data([{"group_id": "grp-a", "name": "A", "layout": layout}]))
    graph = graph_of(host)
    assert graph.by_id["grp-a"].kind == "group" and graph.decls["group"].nested == ()
    assert [node.id for node in graph.nodes if node.file == SECOND_DATA_PLACE] == ["grp-a"]


# --- fix round 1, F7: the contract and the id of a host kind, checked as the toolkit's own are -----------------------------

ITEM_CASES: dict[str, tuple[Any, list[str]]] = {
    # name: (an edit of the example schema, the words the one line of the E520 holds: the place, the kind and the entry)
    "a contract entry that is no property of the item": (
        lambda schema: tables(schema)["x-node"].update(contract=["title"]), [f"{SCHEMA_PLACE} /properties/tables", "contract", "'table'", "'title'"],
    ),
    "one of several contract entries is no property": (
        lambda schema: datastores(schema)["x-node"]["contract"].append("region"), [f"{SCHEMA_PLACE} /properties/datastores", "contract", "'datastore'", "'region'"],
    ),
    "the id property in the contract": (
        lambda schema: tables(schema)["x-node"]["contract"].append("table_id"), [f"{SCHEMA_PLACE} /properties/tables", "contract", "'table'", "'table_id'", "id"],
    ),
    "a link field in the contract": (
        lambda schema: tables(schema)["x-node"]["contract"].append("part_of"), [f"{SCHEMA_PLACE} /properties/tables", "contract", "'table'", "'part_of'", "link"],
    ),
    "the id property is not required of an item": (
        lambda schema: tables(schema)["items"]["required"].remove("table_id"), [f"{SCHEMA_PLACE} /properties/tables", "'table'", "'table_id'", "required"],
    ),
    "the item requires nothing": (
        lambda schema: datastores(schema)["items"].pop("required"), [f"{SCHEMA_PLACE} /properties/datastores", "'datastore'", "'datastore_id'", "required"],
    ),
}


@pytest.mark.parametrize("case", sorted(ITEM_CASES))
def test_a_host_kind_whose_contract_or_id_the_item_does_not_bear_out_is_one_line_of_the_e520(host: Path, case: str) -> None:
    change, words = ITEM_CASES[case]
    edit(host, SCHEMA_PLACE, change)
    error = refusal(host)
    assert (error.code, error.owner) == ("E520", STEP_13)
    [line] = lines(error)
    assert all(word in line for word in words), line


def test_the_contract_and_the_id_of_the_example_as_it_is_are_accepted(host: Path) -> None:
    schema = read(host, SCHEMA_PLACE)
    assert set(tables(schema)["x-node"]["contract"]) <= set(table_fields(schema)) and "table_id" in tables(schema)["items"]["required"]
    graph = graph_of(host)
    assert {TABLE, DATASTORE} <= set(graph.by_id)


def test_required_and_properties_reached_through_ref_and_allof_bear_a_host_kind_out(host: Path) -> None:
    """Next to the refusals: the item says the same through a definition and an ``allOf`` branch, as a toolkit schema may."""

    def move(schema: dict[str, Any]) -> None:
        item = tables(schema)["items"]
        required = item.pop("required")
        name = item["properties"].pop("name")
        schema.setdefault("$defs", {})["named"] = {"type": "object", "required": required, "properties": {"name": name}}
        item["allOf"].append({"$ref": "#/$defs/named"})
        item.pop("additionalProperties")

    edit(host, SCHEMA_PLACE, move)
    assert "name" in tables(read(host, SCHEMA_PLACE))["x-node"]["contract"]
    assert TABLE in graph_of(host).by_id


def test_a_map_keyed_host_kind_needs_no_id_in_required(host: Path) -> None:
    """Next to the id rule: the id of a map-keyed item is its key, so there is no id property to require."""
    caches = {
        "type": "object",
        "x-node": {"kind": "cache", "role": "context", "contract": ["name"], "map_keyed": True},
        "additionalProperties": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "lifecycle": {"$ref": "vc:core:graph#lifecycle"}}},
    }
    schema = {"$schema": DRAFT_2020_12, "$id": "vc:ext-02-cache", "type": "object", "allOf": [{"$ref": "vc:core:step-base"}], "properties": {"caches": caches}}
    write_json(spec_of(host), SECOND_SCHEMA_PLACE, schema)
    data = {"$schema": "vc:ext-02-cache", "id": "ext-cache", "owner": "data", "created_at": "2026-11-15T00:00:00Z", "canonical_refs_used": [], "caches": {"cache-reset-attempts": {"name": "Reset attempts"}}}
    write_json(spec_of(host), SECOND_DATA_PLACE, data)
    assert graph_of(host).by_id["cache-reset-attempts"].kind == "cache"


# --- fix round 1, F8: a toolkit kind reached by $ref ---------------------------------------------------------------------------

BORROWED = {"$ref": "vc:08-fixtures#/properties/fixtures"}
"""The annotated array of the toolkit's step 08: its items are nodes of kind ``fixture``, role verifier."""
LIVES_IN_STEP_08 = "the nodes of kind fixture live in the file of step 08"


def test_a_host_schema_that_reaches_a_kind_of_a_toolkit_step_schema_by_ref_is_one_line_of_the_e520(host: Path) -> None:
    schema = second_schema()
    schema["properties"]["fixtures"] = BORROWED
    add_second(host, schema, {"cache_id": "cache-reset-attempts", "name": "Reset attempts", "derives_from": ["identity-service"]})
    error = refusal(host)
    assert (error.code, error.owner) == ("E520", STEP_13)
    [line] = lines(error)
    assert line.startswith(SECOND_SCHEMA_PLACE) and "'fixture'" in line and LIVES_IN_STEP_08 in line
    with pytest.raises(KindRegistryError):
        graph_of(host)


def test_a_toolkit_kind_reached_inside_the_item_of_a_host_kind_is_refused_too(host: Path) -> None:
    add_second(host, second_schema(fixtures=BORROWED), {"cache_id": "cache-reset-attempts", "name": "Reset attempts", "derives_from": ["identity-service"]})
    [line] = lines(refusal(host))
    assert line.startswith(SECOND_SCHEMA_PLACE) and "'fixture'" in line and LIVES_IN_STEP_08 in line


def test_a_ref_into_the_core_schemas_stays_accepted_with_and_without_an_x_node(host: Path) -> None:
    """Next to the refusal: the shared list of open items (the one ``x-node`` of the core schemas) and a plain atom."""
    schema = second_schema(note={"$ref": "vc:core:atoms#kebabId"})
    schema["properties"]["ambiguities"] = {"$ref": "vc:core:collections#ambiguityList"}
    add_second(host, schema, {"cache_id": "cache-reset-attempts", "name": "Reset attempts", "derives_from": ["identity-service"], "note": "a-note"})
    graph = graph_of(host)
    assert graph.by_id["cache-reset-attempts"].kind == "cache"
    [entries] = [file.kinds for file in load_kind_registry(str(ROOT), str(spec_of(host))).files if file.pattern == SECOND_DATA_PLACE]
    assert sorted(decl.kind for decl in entries) == ["ambiguity-item", "cache"]


def test_a_ref_into_another_host_schema_stays_accepted(host: Path) -> None:
    """Next to the refusal: the second extension keeps datastores of its own in the shape the first one declares."""
    schema = second_schema()
    schema["properties"]["stores"] = {"$ref": "vc:ext-01-database#/properties/datastores"}
    (spec_of(host) / SECOND_SCHEMA_PLACE).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    store = {**read(host, DATA_PLACE)["datastores"][0], "datastore_id": "ds-cache"}
    data = {"$schema": "vc:ext-02-cache", "id": "ext-cache", "owner": "data", "created_at": "2026-11-15T00:00:00Z", "canonical_refs_used": [], "caches": [], "stores": [store]}
    write_json(spec_of(host), SECOND_DATA_PLACE, data)
    graph = graph_of(host)
    assert (graph.by_id["ds-cache"].kind, graph.by_id["ds-cache"].file) == ("datastore", SECOND_DATA_PLACE)
    assert graph.by_id[DATASTORE].file == DATA_PLACE


# --- fix round 1, F10: tests the mutation run of review G asked for -------------------------------------------------------------


def test_the_overlay_is_built_again_when_the_registry_of_the_toolkit_changes(stock: tuple[Path, Path, dict[str, Any]]) -> None:
    """One registry per (toolkit, spec folder) is kept; a toolkit registry written again is a new base, and the host kinds go over the new one."""
    toolkit, spec, _generated = stock
    path = toolkit / "tools" / "entry_key_registry.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    [capability] = document["registry"]["01_capabilities.json"]["arrays"]
    assert capability["contract"] == ["statement"]
    first = load_kind_registry(str(toolkit), str(spec))
    assert _all_decls(first)["capability"].contract == ("statement",) and "warehouse" in first.kind_names
    assert load_kind_registry(str(toolkit), str(spec)) is first  # nothing changed: the same object

    capability["contract"] = ["statement", "rationale"]  # the toolkit's own kind, declared anew (the file grows: its stamp changes)
    write_json(toolkit, "tools/entry_key_registry.json", document)
    second = load_kind_registry(str(toolkit), str(spec))
    assert _all_decls(load_kind_registry(str(toolkit)))["capability"].contract == ("statement", "rationale")  # the base is read again ...
    assert _all_decls(second)["capability"].contract == ("statement", "rationale")  # ... and so is what lies over it
    assert [decl.kind for decl in host_kinds(second)] == [decl.kind for decl in host_kinds(first)] != []


def test_overlay_changes_neither_the_document_nor_the_entries_it_is_given(host: Path) -> None:
    """A link of the toolkit that names ``roles`` gains the host kinds in the result; the document handed in keeps its own list."""
    document = toolkit_kinds.read_registry_document(toolkit_kinds.registry_path(str(ROOT)))
    found = host_entries(str(ROOT), str(spec_of(host)))
    document_before, files_before = json.dumps(document, sort_keys=True), json.dumps(dict(found.files), sort_keys=True)

    def refines(registry_document: Any) -> list[str]:
        return list(_link_kinds(parse_registry(registry_document), "task-criterion", "refines"))

    assert refines(document) == list(REFINES_KINDS)
    laid = overlay(document, found)
    assert refines(laid) == [*REFINES_KINDS, "table"]  # the result did change, in a list the document holds too
    assert json.dumps(document, sort_keys=True) == document_before and refines(document) == list(REFINES_KINDS)
    assert json.dumps(dict(found.files), sort_keys=True) == files_before
    assert overlay(document, found) == laid  # and a second overlay of the same document gives the same


def _a_kind_no_property_reaches(schema: dict[str, Any]) -> None:
    """An obligation kind ``ledger``, well-formed, under ``$defs``: declared, and no property of the schema refers to it."""
    item = json.loads(json.dumps(tables(schema)["items"]))
    fields = item["properties"]
    fields["ledger_id"] = fields.pop("table_id")
    item["required"] = ["ledger_id" if name == "table_id" else name for name in item["required"]]
    node = {**tables(schema)["x-node"], "kind": "ledger", "id": "ledger_id"}
    schema.setdefault("$defs", {})["ledgers"] = {"type": "array", "x-node": node, "items": item}


def test_an_obligation_kind_declared_where_no_property_reaches_it_does_not_join_refines(host: Path) -> None:
    edit(host, SCHEMA_PLACE, _a_kind_no_property_reaches)
    registry = load_kind_registry(str(ROOT), str(spec_of(host)))
    assert "ledger" not in registry.kind_names  # no file of the spec can hold one
    assert _link_kinds(registry, "task-criterion", "refines") == (*REFINES_KINDS, "table")
    # the boundary: a property that refers to the definition makes it a kind of the file, and then it joins
    edit(host, SCHEMA_PLACE, lambda schema: schema["properties"].update(ledgers={"$ref": "#/$defs/ledgers"}))
    registry = load_kind_registry(str(ROOT), str(spec_of(host)))
    assert "ledger" in registry.kind_names
    assert _link_kinds(registry, "task-criterion", "refines") == (*REFINES_KINDS, "ledger", "table")


# --- fix round 1: the cases a mutation pass over the lines of F1 and F7 asked for ---------------------------------------------------


def _map_keyed_caches(node: dict[str, Any], **item_more: Any) -> dict[str, Any]:
    """The schema of a second extension whose ``caches`` is a map of caches by id, with the ``x-node`` *node*."""
    item = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "lifecycle": {"$ref": "vc:core:graph#lifecycle"}, **item_more}}
    caches = {"type": "object", "x-node": {"kind": "cache", "role": "context", "map_keyed": True, **node}, "additionalProperties": item}
    return {"$schema": DRAFT_2020_12, "$id": "vc:ext-02-cache", "type": "object", "allOf": [{"$ref": "vc:core:step-base"}], "properties": {"caches": caches}}


_CACHES = {"$schema": "vc:ext-02-cache", "id": "ext-cache", "owner": "data", "created_at": "2026-11-15T00:00:00Z", "canonical_refs_used": [], "caches": {"cache-reset-attempts": {"name": "Reset attempts"}}}


def test_the_contract_of_a_map_keyed_host_kind_is_checked_against_the_item_of_the_map(host: Path) -> None:
    write_json(spec_of(host), SECOND_SCHEMA_PLACE, _map_keyed_caches({"contract": ["title"]}))
    write_json(spec_of(host), SECOND_DATA_PLACE, _CACHES)
    [line] = lines(refusal(host))
    assert all(word in line for word in (f"{SECOND_SCHEMA_PLACE} /properties/caches", "contract", "'cache'", "'title'")), line
    write_json(spec_of(host), SECOND_SCHEMA_PLACE, _map_keyed_caches({"contract": ["name"]}))  # the boundary: a property of the item of the map
    assert graph_of(host).by_id["cache-reset-attempts"].kind == "cache"


def test_a_map_keyed_host_kind_that_also_names_an_id_property_gets_the_line_of_the_lint_and_no_line_about_required(host: Path) -> None:
    """The annotation schema allows a key or an id property, not both (ANNOT-01).  The id rule is about an item that would be no node; an item of a map is one by its key.

    First written as "accepted": the lint refuses the pair, so what is left to hold is that the rule on ``required`` adds no second line.
    """
    write_json(spec_of(host), SECOND_SCHEMA_PLACE, _map_keyed_caches({"contract": ["name"], "id": "label"}, label=_KEBAB))
    write_json(spec_of(host), SECOND_DATA_PLACE, _CACHES)
    [line] = lines(refusal(host))
    assert line.startswith(f"ANNOT-01 {SECOND_SCHEMA_PLACE} /properties/caches") and "required" not in line


def test_a_kind_that_holds_itself_under_two_properties_is_still_one_line(host: Path) -> None:
    again = {"$ref": "#/$defs/groups"}
    write_json(spec_of(host), SECOND_SCHEMA_PLACE, _groups_schema({"groups": _group_kind(groups=again, archived=again)}, {"groups": again}))
    write_json(spec_of(host), SECOND_DATA_PLACE, _groups_data([{"group_id": "grp-a", "name": "A"}]))
    error = refusal(host)
    [line] = lines(error)
    assert line.startswith(f"{SECOND_SCHEMA_PLACE} /$defs/groups") and "nested in itself" in line


# --- the lead's tests after the mutation run of the fix round (expectations written before the probes ran) -----------------------


def test_a_boolean_branch_in_the_allof_of_an_item_neither_breaks_the_reader_nor_hides_what_a_later_branch_requires(host: Path) -> None:
    """``true`` is a JSON Schema.  A branch that says nothing is read as one that requires nothing, and the walk goes on to the next branch."""

    def change(schema: dict[str, Any]) -> None:
        item = tables(schema)["items"]
        item["required"].remove("table_id")
        item["allOf"] += [True, {"required": ["table_id"]}]

    edit(host, SCHEMA_PLACE, change)
    assert TABLE in graph_of(host).by_id


@pytest.mark.parametrize("items", ["no items", "items: true"])
def test_a_host_kind_with_no_item_schema_gets_the_line_of_the_lint_and_no_line_about_its_contract(host: Path, items: str) -> None:
    """The contract and id rules are about an item schema; where there is none the lint has said so, and one line is the whole refusal."""

    def change(schema: dict[str, Any]) -> None:
        if items == "no items":
            tables(schema).pop("items")
        else:
            tables(schema)["items"] = True

    edit(host, SCHEMA_PLACE, change)
    error = refusal(host)
    assert (error.code, error.owner) == ("E520", STEP_13)
    [line] = lines(error)
    assert f"{SCHEMA_PLACE} /properties/tables" in line and "'table'" in line and "items" in line
