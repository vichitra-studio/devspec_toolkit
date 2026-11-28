"""The context packs of a host with extension kinds (DEVSPEC-245, piece B, decision 7).

The obligation kinds of an extension join the ``obligations`` section of the packs; the context kinds they link to go
in one more section, which exists only when the host has such kinds.  The pack named 16a and 16c; the lead then ruled
that 16b is meant too (the coding agent builds the table and must see it).  The 16b pack of the plain example and its
twelve section names do not change, and a host with no extension kind is handed the recipe table itself.
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph import recipes
from specdev_tools.graph.model import Graph
from specdev_tools.graph.recipes import PARENT_VIA, RecipeError, RecipeTable, Section, build_pack, load_recipes, pack_to_dict, parse_recipes, render_text

from ..trace._lock_support import ROOT
from ._extension import (
    CRITERION, DATA_PLACE, DATASTORE, ENTRY, FIXTURE, PARKED_TABLE, SCHEMA_PLACE, TABLE, datastores, edit, extension_host, graph_of, table, table_fields,
)

TABLE_DATA = json.loads((ROOT / "tools" / "graph_recipes.json").read_text(encoding="utf-8"))
GOLDEN_16B = json.loads((ROOT / "tests" / "fixtures" / "graph" / "pack_16b_expected.json").read_text(encoding="utf-8"))
OBLIGATIONS = "obligations"
WITH_HOST_KINDS = ("16a", "16c")  # the planner and the reviewer: their packs are compared with the plain example's
ROLES = ("16a", "16b", "16c")  # the lead's ruling after the pack: the implementer's pack shows the kinds of a host too
PLAN = "impl_context/ms_account_recovery_plan.json"
TABLE_ITEM = "RESET_TOKEN_TABLE_01"  # a plan item this file adds: it realises the criterion that refines the table
COMPONENT = "identity-service"  # what ds-identity derives from in the example
SECOND_FIELD = "depends_on"  # a link verb of the graph that a table of the example does not use


@pytest.fixture(scope="module")
def recipe_table() -> RecipeTable:
    return load_recipes(str(ROOT))


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return extension_host(tmp_path / "host")


@pytest.fixture
def plain(tmp_path: Path) -> Path:
    """The worked example with no extensions folder: the criterion that refines the table is not there either."""
    folder = extension_host(tmp_path / "plain", declared=False, refined=False)
    shutil.rmtree(folder / "spec" / "extensions")
    return folder


def _start(graph: Graph, role: str) -> str:
    """The node a pack of *role* that concerns the table is for: the task of the refining criterion (16a), its milestone (16c)."""
    task = graph.by_id[CRITERION].parent
    return task if role == "16a" else graph.by_id[task].parent


def _plain_start(role: str, host: Path) -> str:
    return _start(graph_of(host), role)  # the task and the milestone exist in the plain example too


def _sections(folder: Path, recipe_table: RecipeTable, role: str, start: str) -> dict[str, list[str]]:
    pack = build_pack(graph_of(folder), recipe_table, role, start)
    return {name: [entry.id for entry in rows] for name, rows in pack.sections.items()}


def _both(host: Path, plain: Path, recipe_table: RecipeTable, role: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    start = _plain_start(role, host)
    return _sections(host, recipe_table, role, start), _sections(plain, recipe_table, role, start)


def _everything(sections: dict[str, list[str]]) -> set[str]:
    return {node_id for ids in sections.values() for node_id in ids}


# --- 16a and 16c ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_the_pack_shows_the_table_among_the_obligations_and_the_datastore_in_one_more_section(host: Path, plain: Path, recipe_table: RecipeTable, role: str) -> None:
    sections, before = _both(host, plain, recipe_table, role)
    assert TABLE in sections[OBLIGATIONS] and TABLE not in _everything(before)
    assert [name for name in sections[OBLIGATIONS] if name not in before[OBLIGATIONS]] == [TABLE]
    [added] = [name for name in sections if name not in before]
    assert sections[added] == [DATASTORE]
    assert list(sections).index(added) == list(sections).index(OBLIGATIONS) + 1  # beside what it explains
    assert not {PARKED_TABLE, ENTRY} & _everything(sections)  # nothing refines the parked table; the entry is a plan node
    assert [name for name in sections if name != added] == list(before)  # the sections of the role, in their order
    for name in before:  # every other section holds at least what it held
        assert set(before[name]) <= set(sections[name]), name


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_the_text_and_the_json_of_the_pack_name_the_section_and_say_how_the_datastore_was_reached(host: Path, plain: Path, recipe_table: RecipeTable, role: str) -> None:
    sections, before = _both(host, plain, recipe_table, role)
    [added] = [name for name in sections if name not in before]
    start = _plain_start(role, host)
    pack = build_pack(graph_of(host), recipe_table, role, start)
    text = render_text(pack)
    assert [line for line in text.splitlines() if line.startswith(added)] != [] and DATASTORE in text and TABLE in text
    assert added not in render_text(build_pack(graph_of(plain), recipe_table, role, start))
    [row] = pack_to_dict(pack)["sections"][added]
    assert row["id"] == DATASTORE and row["kind"] == "datastore"
    assert "part_of" in row["via"] and TABLE in row["via"] and not row["via"].startswith(PARENT_VIA)


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_with_expand_the_pack_holds_the_content_of_the_table_and_of_the_datastore(host: Path, recipe_table: RecipeTable, role: str) -> None:
    graph = graph_of(host)
    pack = build_pack(graph, recipe_table, role, _start(graph, role), expand=True)
    content = {entry.id: entry.content for rows in pack.sections.values() for entry in rows}
    document = json.loads((host / "spec" / DATA_PLACE).read_text(encoding="utf-8"))
    assert content[TABLE] == table(document) and content[DATASTORE] == document["datastores"][0]


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_a_table_no_criterion_refines_is_in_no_pack_and_the_section_is_empty(tmp_path: Path, host: Path, plain: Path, recipe_table: RecipeTable, role: str) -> None:
    unrefined = extension_host(tmp_path / "unrefined", refined=False)
    start = _plain_start(role, host)
    sections, before = _sections(unrefined, recipe_table, role, start), _sections(plain, recipe_table, role, start)
    [added] = [name for name in sections if name not in before]
    assert sections[added] == [] and {name: ids for name, ids in sections.items() if name != added} == before
    assert f"{added}" in render_text(build_pack(graph_of(unrefined), recipe_table, role, start))  # the section is there, and says it holds nothing


def _declare_clusters(schema: dict[str, Any]) -> None:
    """A second context kind, which the datastore links to and no table does."""
    item = copy.deepcopy(datastores(schema)["items"])
    properties = {"cluster_id": item["properties"]["datastore_id"], "name": item["properties"]["name"], "lifecycle": item["properties"]["lifecycle"]}
    schema["properties"]["clusters"] = {
        "type": "array",
        "x-node": {"kind": "cluster", "role": "context", "contract": ["name"], "id": "cluster_id"},
        "items": {"type": "object", "additionalProperties": False, "required": ["cluster_id", "name"], "properties": properties},
    }
    datastores(schema)["items"]["properties"]["part_of"] = {
        "type": "array", "items": {"$ref": "vc:core:atoms#kebabId"},
        "x-link": {"kinds": ["cluster"], "required": False, "same_step_kinds": ["cluster"]},
    }


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_a_context_node_only_a_context_node_links_to_is_not_shown(host: Path, plain: Path, recipe_table: RecipeTable, role: str) -> None:
    """The pack's words: "the host context kinds they link to", they being the obligation kinds.  The table is part of the datastore; the datastore is part of a cluster."""

    def write(document: dict[str, Any]) -> None:
        document["clusters"] = [{"cluster_id": "cl-primary", "name": "Primary cluster"}]
        document["datastores"][0]["part_of"] = ["cl-primary"]

    edit(host, SCHEMA_PLACE, _declare_clusters)
    edit(host, DATA_PLACE, write)
    assert graph_of(host).by_id["cl-primary"].kind == "cluster"  # the kind is loaded and the link resolves
    sections, before = _both(host, plain, recipe_table, role)
    [added] = [name for name in sections if name not in before]
    assert sections[added] == [DATASTORE] and "cl-primary" not in _everything(sections)


def _declare_indexes(schema: dict[str, Any]) -> None:
    """A second context kind the table links to by a second field (one that sorts before ``part_of``); an index is itself part of a datastore."""
    item = copy.deepcopy(datastores(schema)["items"])
    link = {"type": "array", "items": {"$ref": "vc:core:atoms#kebabId"}}
    properties = {
        "index_id": item["properties"]["datastore_id"], "name": item["properties"]["name"], "lifecycle": item["properties"]["lifecycle"],
        "part_of": {**link, "x-link": {"kinds": ["datastore"], "required": False, "same_step_kinds": ["datastore"]}},
    }
    schema["properties"]["indexes"] = {
        "type": "array",
        "x-node": {"kind": "index", "role": "context", "contract": ["name"], "id": "index_id"},
        "items": {"type": "object", "additionalProperties": False, "required": ["index_id", "name"], "properties": properties},
    }
    table_fields(schema)[SECOND_FIELD] = {**link, "x-link": {"kinds": ["index"], "required": False, "same_step_kinds": ["index"]}}


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_a_table_that_links_by_two_fields_shows_the_context_of_both_and_nothing_further(host: Path, plain: Path, recipe_table: RecipeTable, role: str) -> None:
    def write(document: dict[str, Any]) -> None:
        archive = {**document["datastores"][0], "datastore_id": "ds-archive", "name": "Archive store"}
        document["datastores"].append(archive)
        document["indexes"] = [
            {"index_id": "idx-token-hash", "name": "reset_token by token_hash", "part_of": ["ds-archive"]},
            {"index_id": "idx-unused", "name": "No table names this index"},
        ]
        table(document)[SECOND_FIELD] = ["idx-token-hash"]

    edit(host, SCHEMA_PLACE, _declare_indexes)
    edit(host, DATA_PLACE, write)
    graph = graph_of(host)
    assert graph.by_id["idx-token-hash"].kind == "index" and graph.by_id["ds-archive"].kind == "datastore"
    start = _start(graph, role)
    pack = pack_to_dict(build_pack(graph, recipe_table, role, start))
    [added] = [name for name in pack["sections"] if name not in _sections(plain, recipe_table, role, start)]
    via = {row["id"]: row["via"] for row in pack["sections"][added]}
    assert sorted(via) == sorted([DATASTORE, "idx-token-hash"])  # not idx-unused, and not ds-archive: only the index links to it
    assert "part_of" in via[DATASTORE] and SECOND_FIELD in via["idx-token-hash"] and all(TABLE in way for way in via.values())
    assert SECOND_FIELD not in via[DATASTORE] and "part_of" not in via["idx-token-hash"]  # each row names the field its own link is in


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_a_table_another_table_links_to_is_not_context(host: Path, plain: Path, recipe_table: RecipeTable, role: str) -> None:
    """An obligation kind may link to an obligation kind of its extension (a foreign key); the section is for the context kinds."""
    link = {"type": "array", "items": {"$ref": "vc:core:atoms#kebabId"}, "x-link": {"kinds": ["table"], "required": False, "same_step_kinds": ["table"]}}
    edit(host, SCHEMA_PLACE, lambda schema: table_fields(schema).update({SECOND_FIELD: link}))
    edit(host, DATA_PLACE, lambda document: table(document).update({SECOND_FIELD: [PARKED_TABLE]}))
    graph = graph_of(host)
    assert [found.target for found in graph.outgoing[TABLE] if found.field == SECOND_FIELD] == [PARKED_TABLE]
    sections, before = _both(host, plain, recipe_table, role)
    [added] = [name for name in sections if name not in before]
    assert sections[added] == [DATASTORE] and PARKED_TABLE not in _everything(sections)  # no criterion refines the parked table


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_when_no_obligation_kind_links_to_a_context_kind_of_the_host_there_is_no_section(host: Path, plain: Path, recipe_table: RecipeTable, role: str) -> None:
    edit(host, SCHEMA_PLACE, lambda schema: table_fields(schema)["part_of"].update({"x-link": {"kinds": ["component"], "required": True}}))
    edit(host, DATA_PLACE, lambda document: [item.update(part_of=[COMPONENT]) for item in document["tables"]])
    assert graph_of(host).decls["datastore"].host  # the host still has a context kind: no table links to it
    sections, before = _both(host, plain, recipe_table, role)
    assert list(sections) == list(before) and TABLE in sections[OBLIGATIONS]
    assert DATASTORE not in _everything(sections)


# --- 16b -----------------------------------------------------------------------------------------------------------------


def _plan_the_table(host: Path) -> None:
    """Add to the plan of the milestone an item that realises the criterion which refines the table."""

    def add(plan: dict[str, Any]) -> None:
        checklist = plan["plan"]["spec_alignment"]["checklist"]
        checklist.append({**copy.deepcopy(checklist[0]), "id": TABLE_ITEM, "realises": [CRITERION], "description": "A migration creates the table reset_token."})

    edit(host, PLAN, add)


def _golden_shape(pack: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    """The sections of a 16b pack in the form of ``pack_16b_expected.json``."""
    return {
        name: {
            "members": sorted(row["id"] for row in rows if not row["via"].startswith(PARENT_VIA)),
            "containers": sorted(row["id"] for row in rows if row["via"].startswith(PARENT_VIA)),
        }
        for name, rows in pack["sections"].items()
    }


GOLDEN_SECTIONS = {name: {part: sorted(ids) for part, ids in parts.items()} for name, parts in GOLDEN_16B["sections"].items()}


def test_the_16b_pack_of_the_item_that_builds_the_table_shows_the_table_the_datastore_and_its_fixture(host: Path, recipe_table: RecipeTable) -> None:
    _plan_the_table(host)
    graph = graph_of(host)
    assert [found.target for found in graph.outgoing[TABLE_ITEM] if found.field == "realises"] == [CRITERION]
    pack = build_pack(graph, recipe_table, "16b", TABLE_ITEM)
    sections = {name: [entry.id for entry in rows] for name, rows in pack.sections.items()}
    assert CRITERION in sections["core criteria"]
    assert TABLE in sections[OBLIGATIONS]
    assert sections[recipe_table.host_kinds.context] == [DATASTORE]
    assert FIXTURE in sections["verifiers"]
    assert not {PARKED_TABLE, ENTRY} & _everything(sections)
    names = list(sections)
    assert names.index(recipe_table.host_kinds.context) == names.index(OBLIGATIONS) + 1
    assert [name for name in names if name != recipe_table.host_kinds.context] == list(GOLDEN_16B["sections"])


def test_the_16b_pack_of_an_item_that_realises_another_criterion_holds_no_host_node(host: Path, plain: Path, recipe_table: RecipeTable) -> None:
    _plan_the_table(host)  # the item is in the plan; the pack is that of another item
    with_extension, without = (pack_to_dict(build_pack(graph_of(folder), recipe_table, "16b", GOLDEN_16B["start"])) for folder in (host, plain))
    added = recipe_table.host_kinds.context
    assert with_extension["sections"][added] == []
    assert {name: rows for name, rows in with_extension["sections"].items() if name != added} == without["sections"]
    assert not {TABLE, DATASTORE, PARKED_TABLE, ENTRY, TABLE_ITEM, CRITERION} & {row["id"] for rows in with_extension["sections"].values() for row in rows}


def test_the_16b_pack_of_the_plain_example_is_the_golden_with_its_twelve_sections(plain: Path, recipe_table: RecipeTable) -> None:
    pack = pack_to_dict(build_pack(graph_of(plain), recipe_table, "16b", GOLDEN_16B["start"]))
    assert list(pack["sections"]) == list(GOLDEN_16B["sections"]) and len(pack["sections"]) == 12
    assert _golden_shape(pack) == GOLDEN_SECTIONS


# --- the table ---------------------------------------------------------------------------------------------------------------


def test_the_table_names_the_roles_and_the_two_sections_for_the_kinds_of_a_host(recipe_table: RecipeTable) -> None:
    places = recipe_table.host_kinds
    assert places is not None and sorted(places.roles) == sorted(ROLES) == sorted(recipe_table.roles)
    assert places.obligations == OBLIGATIONS
    for role in ROLES:
        assert places.context not in [section.name for section in recipe_table.sections_for(role)]


def test_a_host_with_no_extension_kind_is_handed_the_table_itself(plain: Path, host: Path, recipe_table: RecipeTable) -> None:
    assert recipes.with_host_kinds(recipe_table, graph_of(plain)) is recipe_table
    for role in WITH_HOST_KINDS:
        assert list(_sections(plain, recipe_table, role, _plain_start(role, host))) == [section.name for section in recipe_table.sections_for(role)]


def test_the_table_of_the_toolkit_is_not_changed_by_a_pack_of_a_host_with_kinds(host: Path, recipe_table: RecipeTable) -> None:
    before = (recipe_table.sections, recipe_table.placed_kinds())
    widened = recipes.with_host_kinds(recipe_table, graph_of(host))
    assert widened is not recipe_table and (recipe_table.sections, recipe_table.placed_kinds()) == before
    assert {"table", "datastore"} <= widened.placed_kinds() and not {"table", "datastore"} & recipe_table.placed_kinds()
    assert (widened.start_kinds, widened.reports, widened.exempt, widened.suffix_fields) == (
        recipe_table.start_kinds, recipe_table.reports, recipe_table.exempt, recipe_table.suffix_fields,
    )


def test_a_table_that_places_no_host_kind_gives_the_packs_of_the_plain_example(host: Path, plain: Path) -> None:
    bare = parse_recipes({key: value for key, value in TABLE_DATA.items() if key != "host_kinds"})
    assert bare.host_kinds is None and recipes.with_host_kinds(bare, graph_of(host)) is bare
    for role in WITH_HOST_KINDS:
        start = _plain_start(role, host)
        sections = _sections(host, bare, role, start)
        assert list(sections) == list(_sections(plain, bare, role, start)) and not {TABLE, DATASTORE} & _everything(sections)


def _with_obligation_hops(*hops: dict[str, Any]) -> RecipeTable:
    """The toolkit's table with *hops* added to its ``obligations`` section."""
    data = copy.deepcopy(TABLE_DATA)
    [section] = [section for section in data["sections"] if section["name"] == OBLIGATIONS]
    section["hops"].extend(hops)
    return parse_recipes(data)


def test_only_a_hop_that_follows_a_link_which_may_name_the_kind_admits_it(host: Path) -> None:
    """``refines`` of a task criterion may name a table (decision 5); ``depends_on`` may not, and a hop that walks a link backwards or admits any kind is left as it is."""
    added = (
        {"verb": "depends_on", "direction": "out", "kinds": ["fr"]},
        {"verb": "refines", "direction": "in", "kinds": ["task-criterion"]},
        {"verb": "refines", "direction": "out", "kinds": []},
    )
    changed = _with_obligation_hops(*added)
    widened = recipes.with_host_kinds(changed, graph_of(host))
    for role in ROLES:
        [before] = [section for section in changed.sections_for(role) if section.name == OBLIGATIONS]
        [after] = [section for section in widened.sections_for(role) if section.name == OBLIGATIONS]
        assert after.kinds == before.kinds | {"table"}
        assert len(after.hops) == len(before.hops)
        gained = [new.kinds - old.kinds for old, new in zip(before.hops, after.hops)]
        follows_refines_out = [old.verb == "refines" and old.direction == "out" and bool(old.kinds) for old in before.hops]
        assert gained == [frozenset({"table"}) if follows else frozenset() for follows in follows_refines_out]
        assert follows_refines_out.count(True) == 1 and len(before.hops) >= 1 + len(added)
        assert [(new.verb, new.direction, new.repeat) for new in after.hops] == [(old.verb, old.direction, old.repeat) for old in before.hops]


def test_a_table_that_keeps_the_obligations_of_each_role_apart_gets_one_new_section_for_each_role_named(host: Path) -> None:
    """Odd but legal: the table may give 16b an ``obligations`` section of its own, as it gives each role its ``core criteria``."""
    data = copy.deepcopy(TABLE_DATA)
    index, section = next((index, section) for index, section in enumerate(data["sections"]) if section["name"] == OBLIGATIONS)
    data["sections"][index:index + 1] = [{**section, "roles": ["16b"]}, {**section, "roles": ["16a"]}, {**section, "roles": ["16c"]}]
    data["host_kinds"] = {**data["host_kinds"], "roles": list(WITH_HOST_KINDS)}  # an entry that leaves 16b out
    apart = parse_recipes(data)
    widened = recipes.with_host_kinds(apart, graph_of(host))
    assert all(section.roles for section in widened.sections)
    context = apart.host_kinds.context
    assert sorted(sorted(section.roles) for section in widened.sections if section.name == context) == [["16a"], ["16c"]]
    [of_16b] = [section for section in widened.sections if section.name == OBLIGATIONS and "16b" in section.roles]
    assert of_16b in apart.sections and "table" not in of_16b.kinds
    assert len(widened.sections) == len(apart.sections) + 2
    for role in WITH_HOST_KINDS:
        names = [section.name for section in widened.sections_for(role)]
        assert names.index(context) == names.index(OBLIGATIONS) + 1 and names.count(context) == 1


@pytest.mark.parametrize(
    "rule, said",
    [
        pytest.param({"roles": ["16a", "16d"], "obligations": OBLIGATIONS, "context": "extension context"}, "host_kinds.roles", id="a-role-the-table-does-not-have"),
        pytest.param({"roles": [], "obligations": OBLIGATIONS, "context": "extension context"}, "host_kinds.roles", id="no-role"),
        pytest.param({"roles": ["16a"], "obligations": "duties", "context": "extension context"}, "host_kinds.obligations", id="no-such-section"),
        pytest.param({"roles": ["16a"], "obligations": "universal", "context": "extension context"}, "host_kinds.obligations", id="a-section-that-is-no-traversal"),
        pytest.param({"roles": ["16a"], "obligations": OBLIGATIONS, "context": "threats"}, "host_kinds.context", id="the-name-of-a-section-of-the-role"),
        pytest.param({"roles": ["16a"], "obligations": OBLIGATIONS}, "host_kinds.context", id="no-name-for-the-section"),
        pytest.param({"roles": ["16a"], "context": "extension context"}, "host_kinds.obligations", id="no-obligations-section-named"),
        pytest.param(["16a"], "host_kinds", id="not-an-object"),
    ],
)
def test_a_table_whose_host_kinds_entry_is_wrong_is_refused(rule: Any, said: str) -> None:
    with pytest.raises(RecipeError) as refused:
        parse_recipes({**TABLE_DATA, "host_kinds": rule})
    assert refused.value.error.code == "E520" and said in refused.value.error.message


def test_a_host_kinds_entry_for_one_role_changes_the_packs_of_that_role_only(host: Path) -> None:
    """Next to the refusals: a section name another role uses is a legal name for the new section of this role."""
    only_16c = parse_recipes({**TABLE_DATA, "host_kinds": {"roles": ["16c"], "obligations": OBLIGATIONS, "context": "needs"}})  # "needs" is a section of 16a alone
    bare = parse_recipes({key: value for key, value in TABLE_DATA.items() if key != "host_kinds"})
    start = _plain_start("16a", host)
    assert _sections(host, only_16c, "16a", start) == _sections(host, bare, "16a", start)  # the role the entry does not name: as with no entry
    start = _plain_start("16c", host)
    sections = _sections(host, only_16c, "16c", start)
    assert sections["needs"] == [DATASTORE] and TABLE in sections[OBLIGATIONS]


# --- the exemption of the manifest entry ---------------------------------------------------------------------------------


def test_the_exemption_of_the_extension_kind_says_what_the_kind_is_now(recipe_table: RecipeTable, host: Path) -> None:
    [exemption] = [item for item in recipe_table.exempt if item.kind == "extension"]
    assert graph_of(host).decls["extension"].role == "plan"
    assert "`plan`" in exemption.authority and "record" not in exemption.authority
    for role in recipe_table.roles:  # exempt still: no pack of the host names the entry
        graph = graph_of(host)
        start = GOLDEN_16B["start"] if role == "16b" else _start(graph, role)
        assert ENTRY not in _everything({name: [entry.id for entry in rows] for name, rows in build_pack(graph, recipe_table, role, start).sections.items()})


# --- fix round 1, F9: items nested in items ------------------------------------------------------------------------------------

LIFECYCLE = {"$ref": "vc:core:graph#lifecycle"}
KEBAB = {"$ref": "vc:core:atoms#kebabId"}
INDEX_CRITERION = "tc-member-id-index"


def _columns_are_nodes(schema: dict[str, Any]) -> None:
    """The columns of a table become nodes of a context kind ``column``; a column may hold ``checks``, nodes of a context kind ``check``, and may name a datastore."""
    columns = table_fields(schema)["columns"]
    checks = {
        "type": "array",
        "x-node": {"kind": "check", "role": "context", "contract": ["rule"], "id": "check_id"},
        "items": {"type": "object", "additionalProperties": False, "required": ["check_id", "rule"], "properties": {"check_id": KEBAB, "rule": {"type": "string"}, "lifecycle": LIFECYCLE}},
    }
    mirrored = {"type": "array", "items": KEBAB, "x-link": {"kinds": ["datastore"], "required": False, "same_step_kinds": ["datastore"]}}
    columns["x-node"] = {"kind": "column", "role": "context", "contract": ["name", "type"], "id": "column_id"}
    columns["items"]["required"] = ["column_id", *columns["items"]["required"]]
    columns["items"]["properties"].update({"column_id": KEBAB, "lifecycle": LIFECYCLE, "checks": checks, "part_of": mirrored})


def _name_the_columns(document: dict[str, Any]) -> None:
    for one in document["tables"]:
        for column in one["columns"]:
            column["column_id"] = f"col-{one['name'].replace('_', '-')}-{column['name'].replace('_', '-')}"
    table(document)["columns"][0]["checks"] = [{"check_id": "chk-token-hash-length", "rule": "64 hexadecimal characters"}]


def _column_ids(document: dict[str, Any], node_id: str) -> list[str]:
    return [column["column_id"] for column in table(document, node_id)["columns"]]


def _indexes_are_obligations(schema: dict[str, Any]) -> None:
    """A table may hold ``indexes``: nodes of an obligation kind ``index``, each with ``parts`` (a context kind ``index-part``)."""
    parts = {
        "type": "array",
        "x-node": {"kind": "index-part", "role": "context", "contract": ["column"], "id": "part_id"},
        "items": {"type": "object", "additionalProperties": False, "required": ["part_id", "column"], "properties": {"part_id": KEBAB, "column": {"type": "string"}, "lifecycle": LIFECYCLE}},
    }
    properties = {
        "index_id": KEBAB, "name": {"type": "string"}, "lifecycle": LIFECYCLE, "parts": parts,
        "scope": {"$ref": "vc:core:graph#scope"}, "scope_reason": {"$ref": "vc:core:graph#scopeReason"},
        "derives_from": copy.deepcopy(table_fields(schema)["derives_from"]),
    }
    table_fields(schema)["indexes"] = {
        "type": "array",
        "x-node": {"kind": "index", "role": "obligation-system", "contract": ["name", "scope", "scope_reason"], "id": "index_id"},
        "items": {"type": "object", "additionalProperties": False, "required": ["index_id", "name"], "allOf": [{"$ref": "vc:core:graph#scopeReasonRule"}], "properties": properties},
    }


def _index(index_id: str, name: str, part: str) -> dict[str, Any]:
    return {"index_id": index_id, "name": name, "scope": "in", "derives_from": ["fr-password-reset"], "parts": [{"part_id": part, "column": "member_id"}]}


def _refine_the_index_of_the_parked_table(host: Path) -> None:
    """The review's N4: an index nested in the table no criterion refines, and one more task criterion that refines that index."""

    def write(document: dict[str, Any]) -> None:
        table(document, PARKED_TABLE)["indexes"] = [_index("idx-member-id", "member_credential by member_id", "part-member-id")]
        table(document)["indexes"] = [_index("idx-token-member", "reset_token by member_id", "part-token-member")]

    def refine(roadmap: dict[str, Any]) -> None:
        for milestone in roadmap["milestones"]:
            for task in milestone["tasks"]:
                found = [one for one in task["acceptance_criteria"] if one["criterion_id"] == CRITERION]
                if found:
                    task["acceptance_criteria"].append({**copy.deepcopy(found[0]), "criterion_id": INDEX_CRITERION, "refines": ["idx-member-id"], "verified_by": []})

    edit(host, SCHEMA_PLACE, _indexes_are_obligations)
    edit(host, DATA_PLACE, write)
    edit(host, "14_roadmap.json", refine)


def _rows(host: Path, recipe_table: RecipeTable, role: str, *, expand: bool = False) -> dict[str, list[dict[str, Any]]]:
    graph = graph_of(host)
    if role == "16b":
        start = TABLE_ITEM
    else:
        start = _start(graph, role)
    return pack_to_dict(build_pack(graph, recipe_table, role, start, expand=expand))["sections"]


@pytest.mark.parametrize("role", ROLES)
def test_the_context_children_of_a_table_of_the_pack_are_in_the_extension_context_at_any_depth(host: Path, recipe_table: RecipeTable, role: str) -> None:
    """The review's D12: the columns of the refined table, and the check one of them holds; never those of the table nothing refines."""
    edit(host, SCHEMA_PLACE, _columns_are_nodes)
    edit(host, DATA_PLACE, _name_the_columns)
    _plan_the_table(host)
    document = json.loads((host / "spec" / DATA_PLACE).read_text(encoding="utf-8"))
    own, parked = _column_ids(document, TABLE), _column_ids(document, PARKED_TABLE)
    assert len(own) == 4 and len(parked) == 3 and graph_of(host).by_id[own[0]].kind == "column"
    rows = _rows(host, recipe_table, role)
    context = {row["id"]: row for row in rows[recipe_table.host_kinds.context]}
    assert sorted(context) == sorted([DATASTORE, *own, "chk-token-hash-length"])
    assert all(TABLE in context[column]["via"] and "child" in context[column]["via"] for column in own)
    assert own[0] in context["chk-token-hash-length"]["via"] and "child" in context["chk-token-hash-length"]["via"]
    assert "part_of" in context[DATASTORE]["via"]  # the datastore is still there by the table's link
    assert not set(parked) & {row["id"] for found in rows.values() for row in found}
    assert not {*own, "chk-token-hash-length"} & {row["id"] for row in rows[OBLIGATIONS]}


@pytest.mark.parametrize("role", ROLES)
def test_with_expand_the_columns_come_with_their_content(host: Path, recipe_table: RecipeTable, role: str) -> None:
    edit(host, SCHEMA_PLACE, _columns_are_nodes)
    edit(host, DATA_PLACE, _name_the_columns)
    _plan_the_table(host)
    document = json.loads((host / "spec" / DATA_PLACE).read_text(encoding="utf-8"))
    rows = _rows(host, recipe_table, role, expand=True)
    content = {row["id"]: row["content"] for row in rows[recipe_table.host_kinds.context]}
    for column in table(document)["columns"]:
        assert content[column["column_id"]]["type"] == column["type"] and content[column["column_id"]]["name"] == column["name"]


@pytest.mark.parametrize("role", ROLES)
def test_what_a_column_links_to_is_not_in_the_pack(host: Path, recipe_table: RecipeTable, role: str) -> None:
    """The ruling kept: a context node reached only through a context node is not in a pack; a child is the one exception, its links are not."""

    def write(document: dict[str, Any]) -> None:
        _name_the_columns(document)
        document["datastores"].append({**document["datastores"][0], "datastore_id": "ds-audit", "name": "Audit store"})
        table(document)["columns"][1]["part_of"] = ["ds-audit"]

    edit(host, SCHEMA_PLACE, _columns_are_nodes)
    edit(host, DATA_PLACE, write)
    _plan_the_table(host)
    graph = graph_of(host)
    column = _column_ids(json.loads((host / "spec" / DATA_PLACE).read_text(encoding="utf-8")), TABLE)[1]
    assert [found.target for found in graph.outgoing[column]] == ["ds-audit"]
    rows = _rows(host, recipe_table, role)
    assert column in {row["id"] for row in rows[recipe_table.host_kinds.context]}
    assert "ds-audit" not in {row["id"] for found in rows.values() for row in found}


@pytest.mark.parametrize("role", ROLES)
def test_a_refined_index_comes_with_the_table_that_holds_it(host: Path, recipe_table: RecipeTable, role: str) -> None:
    """The review's N4, as a refined criterion comes with its FR: the parked table is in the pack as the holder of the index, and marked so."""
    _refine_the_index_of_the_parked_table(host)

    def realise_both(plan: dict[str, Any]) -> None:
        checklist = plan["plan"]["spec_alignment"]["checklist"]
        checklist.append({**copy.deepcopy(checklist[0]), "id": TABLE_ITEM, "realises": [CRITERION, INDEX_CRITERION], "description": "A migration creates the table and the index."})

    edit(host, PLAN, realise_both)
    graph = graph_of(host)
    assert (graph.by_id["idx-member-id"].kind, graph.by_id["idx-member-id"].parent) == ("index", PARKED_TABLE)
    rows = _rows(host, recipe_table, role)
    obligations = {row["id"]: row for row in rows[OBLIGATIONS]}
    assert {"idx-member-id", PARKED_TABLE, TABLE} <= set(obligations)
    assert obligations[PARKED_TABLE]["via"] == f"{PARENT_VIA}idx-member-id"
    pack = build_pack(graph, recipe_table, role, TABLE_ITEM if role == "16b" else _start(graph, role))
    held = {entry.id: (entry.container, entry.source_id) for entry in pack.sections[OBLIGATIONS]}
    assert held[PARKED_TABLE] == (True, "idx-member-id") and held["idx-member-id"][0] is False and held[TABLE][0] is False
    assert not obligations[TABLE]["via"].startswith(PARENT_VIA) and "refines" in obligations["idx-member-id"]["via"]


@pytest.mark.parametrize("role", ROLES)
def test_an_obligation_child_nothing_refines_is_not_in_the_pack_and_neither_is_what_it_holds(host: Path, recipe_table: RecipeTable, role: str) -> None:
    """Like a criterion, a nested obligation enters a pack when it is refined: the index of the refined table is not, the parts of the refined index are."""
    _refine_the_index_of_the_parked_table(host)

    def realise_both(plan: dict[str, Any]) -> None:
        checklist = plan["plan"]["spec_alignment"]["checklist"]
        checklist.append({**copy.deepcopy(checklist[0]), "id": TABLE_ITEM, "realises": [CRITERION, INDEX_CRITERION], "description": "A migration creates the table and the index."})

    edit(host, PLAN, realise_both)
    rows = _rows(host, recipe_table, role)
    everything = {row["id"] for found in rows.values() for row in found}
    assert TABLE in everything and not {"idx-token-member", "part-token-member"} & everything
    context = {row["id"]: row["via"] for row in rows[recipe_table.host_kinds.context]}
    assert "part-member-id" in context and "idx-member-id" in context["part-member-id"]


def test_a_host_whose_only_context_kinds_are_children_gets_the_section_too(host: Path, recipe_table: RecipeTable) -> None:
    """No table links to a context kind, yet the columns are context of the table: the section exists for them."""
    edit(host, SCHEMA_PLACE, _columns_are_nodes)
    edit(host, SCHEMA_PLACE, lambda schema: table_fields(schema)["part_of"].update({"x-link": {"kinds": ["component"], "required": True}}))
    edit(host, SCHEMA_PLACE, lambda schema: table_fields(schema)["columns"]["items"]["properties"].pop("part_of"))

    def write(document: dict[str, Any]) -> None:
        _name_the_columns(document)
        for one in document["tables"]:
            one["part_of"] = [COMPONENT]

    edit(host, DATA_PLACE, write)
    document = json.loads((host / "spec" / DATA_PLACE).read_text(encoding="utf-8"))
    rows = _rows(host, recipe_table, "16a")
    assert sorted(row["id"] for row in rows[recipe_table.host_kinds.context]) == sorted([*_column_ids(document, TABLE), "chk-token-hash-length"])


def test_the_sections_of_the_example_as_it_is_have_the_hops_they_had(host: Path, recipe_table: RecipeTable) -> None:
    """No nested kind: the table of sections is what it was, hop for hop (the packs of the example are compared whole elsewhere)."""
    placed = recipes.with_host_kinds(recipe_table, graph_of(host))
    context = [section for section in placed.sections if section.name == recipe_table.host_kinds.context]
    assert [(len(section.hops), section.hops[0].direction, sorted(section.kinds)) for section in context] == [(1, "out", ["datastore"])]
    stock = next(section for section in recipe_table.sections if section.name == OBLIGATIONS)
    widened = next(section for section in placed.sections if section.name == OBLIGATIONS and "16a" in section.roles)
    assert [hop.kinds for hop in widened.hops if hop.direction == "parent"] == [hop.kinds for hop in stock.hops if hop.direction == "parent"]


# --- fix round 1, F10: a section is added for what an OBLIGATION kind links to, and for nothing else ---------------------------


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_when_only_a_context_kind_links_to_a_context_kind_there_is_no_section_not_even_an_empty_one(host: Path, plain: Path, recipe_table: RecipeTable, role: str) -> None:
    """The datastore is part of a cluster; the table is part of a component of the toolkit.  No obligation kind names a host context kind."""

    def write(document: dict[str, Any]) -> None:
        document["clusters"] = [{"cluster_id": "cl-primary", "name": "Primary cluster"}]
        document["datastores"][0]["part_of"] = ["cl-primary"]
        for item in document["tables"]:
            item["part_of"] = [COMPONENT]

    edit(host, SCHEMA_PLACE, _declare_clusters)
    edit(host, SCHEMA_PLACE, lambda schema: table_fields(schema)["part_of"].update({"x-link": {"kinds": ["component"], "required": True}}))
    edit(host, DATA_PLACE, write)
    graph = graph_of(host)
    assert [link.target for link in graph.by_id[DATASTORE].links if link.field == "part_of"] == ["cl-primary"]  # the context link is there and resolves
    sections, before = _both(host, plain, recipe_table, role)
    assert list(sections) == list(before) and "extension context" not in sections
    assert TABLE in sections[OBLIGATIONS] and not {DATASTORE, "cl-primary"} & _everything(sections)
    # the boundary: the table names the datastore again, and the section is back with the datastore alone
    edit(host, SCHEMA_PLACE, lambda schema: table_fields(schema).update({SECOND_FIELD: {
        "type": "array", "items": {"$ref": "vc:core:atoms#kebabId"}, "x-link": {"kinds": ["datastore"], "required": False, "same_step_kinds": ["datastore"]}}}))
    edit(host, DATA_PLACE, lambda document: [item.update({SECOND_FIELD: [DATASTORE]}) for item in document["tables"]])
    sections = _sections(host, recipe_table, role, _plain_start(role, host))
    assert sections["extension context"] == [DATASTORE] and "cl-primary" not in _everything(sections)


# --- fix round 1: the cases a mutation pass over the lines of F9 asked for -------------------------------------------------------

GRANT, GRANT_CRITERION = "grant-identity-app", "tc-identity-grant"


def _a_datastore_holds_grants(host: Path) -> None:
    """An obligation kind ``grant`` nested in the datastore (a context kind), one grant, and one more task criterion that refines it."""

    def declare(schema: dict[str, Any]) -> None:
        properties = {
            "grant_id": KEBAB, "name": {"type": "string"}, "lifecycle": LIFECYCLE,
            "scope": {"$ref": "vc:core:graph#scope"}, "scope_reason": {"$ref": "vc:core:graph#scopeReason"},
            "derives_from": copy.deepcopy(table_fields(schema)["derives_from"]),
        }
        datastores(schema)["items"]["properties"]["grants"] = {
            "type": "array",
            "x-node": {"kind": "grant", "role": "obligation-system", "contract": ["name", "scope", "scope_reason"], "id": "grant_id"},
            "items": {"type": "object", "additionalProperties": False, "required": ["grant_id", "name"], "allOf": [{"$ref": "vc:core:graph#scopeReasonRule"}], "properties": properties},
        }

    def refine(roadmap: dict[str, Any]) -> None:
        for milestone in roadmap["milestones"]:
            for task in milestone["tasks"]:
                found = [one for one in task["acceptance_criteria"] if one["criterion_id"] == CRITERION]
                if found:
                    task["acceptance_criteria"].append({**copy.deepcopy(found[0]), "criterion_id": GRANT_CRITERION, "refines": [GRANT], "verified_by": []})

    edit(host, SCHEMA_PLACE, declare)
    edit(host, DATA_PLACE, lambda document: document["datastores"][0].update(grants=[{"grant_id": GRANT, "name": "app reads and writes", "scope": "in", "derives_from": ["fr-password-reset"]}]))
    edit(host, "14_roadmap.json", refine)


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_a_refined_obligation_held_by_a_context_node_comes_with_that_node(host: Path, recipe_table: RecipeTable, role: str) -> None:
    """The holder need not be an obligation: the datastore is a context node, and it is the parent the refined grant comes with."""
    _a_datastore_holds_grants(host)
    graph = graph_of(host)
    assert (graph.by_id[GRANT].kind, graph.by_id[GRANT].parent, graph.decls["datastore"].role) == ("grant", DATASTORE, "context")
    pack = build_pack(graph, recipe_table, role, _start(graph, role))
    held = {entry.id: (entry.container, entry.source_id) for entry in pack.sections[OBLIGATIONS]}
    assert held[GRANT][0] is False and held[DATASTORE] == (True, GRANT)


@pytest.mark.parametrize("role", WITH_HOST_KINDS)
def test_a_parent_hop_that_admits_every_kind_still_does_when_a_host_has_holders(host: Path, recipe_table: RecipeTable, role: str) -> None:
    """A table whose ``parent`` hop names no kind (any kind): the holders of a host are not made the only parents it takes."""
    _refine_the_index_of_the_parked_table(host)
    data = copy.deepcopy(TABLE_DATA)
    [section] = [section for section in data["sections"] if section["name"] == OBLIGATIONS]
    [parent] = [hop for hop in section["hops"] if hop["direction"] == "parent"]
    named, parent["kinds"] = parent["kinds"], []
    start = _start(graph_of(host), role)
    with_any, with_named = _sections(host, parse_recipes(data), role, start)[OBLIGATIONS], _sections(host, recipe_table, role, start)[OBLIGATIONS]
    graph = graph_of(host)
    of_the_named = [node_id for node_id in with_named if graph.by_id[node_id].kind in named]
    assert of_the_named != [] and set(of_the_named) <= set(with_any)  # the parents the toolkit's table names are still taken
    assert PARKED_TABLE in with_any and "idx-member-id" in with_any
