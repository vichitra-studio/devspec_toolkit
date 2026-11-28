"""Tests for annotation-driven registry generation (WI-M1-04, WI-M1-05)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Callable

import pytest
from jsonschema import Draft202012Validator

from specdev_tools.core.entry_key_registry import (
    _load,
    array_leaf_key,
    array_top_key,
    get_step_for_file,
    iter_array_path,
    iter_nodes,
    list_entries,
)
from specdev_tools.core.json_utils import _collect_ids_from_file
from specdev_tools.core.registry import SchemaRegistry, clear_shared_caches
from specdev_tools.registry.annotation_scan import scan_annotations
from specdev_tools.registry.annotations import SchemaRefs
from specdev_tools.registry import generate as generate_mod
from specdev_tools.registry.generate import _serialize, generate_registry
from specdev_tools.validation.registry_check import run_registry_check

_ROOT = Path(__file__).resolve().parents[3]
_PRE_M1 = _ROOT / "tests" / "fixtures" / "entry_key_registry_pre_m1.json"
_CORPUS = _ROOT / "tests" / "fixtures" / "spec_corpus"
_REG_SCHEMA = _ROOT / "schema" / "entry_key_registry.schema.json"

S04 = "schema/04_fr_list.schema.json"
S05 = "schema/05_interface_contracts.schema.json"
SREG = "tools/schema_registry.json"








def _generate(root: Path) -> tuple[dict, dict]:
    clear_shared_caches()
    return generate_registry(str(root))


def _arrays(reg: dict, key: str) -> list[dict]:
    return reg["registry"][key]["arrays"]


def _by_path(arrays: list[dict]) -> dict[str, dict]:
    return {a["array_path"]: a for a in arrays}


# ------------------------------------------------------------ resolver

def test_make_ref_resolver_anchor_pointer_and_whole_schema():
    reg = SchemaRegistry(str(_ROOT))
    resolve = SchemaRefs(reg).resolve
    id_array, uri, ptr = resolve("vc:core:collections#kebabIdArray")
    assert uri == "vc:core:collections" and id_array.get("$anchor") == "kebabIdArray"
    kebab, uri, _ = resolve("vc:core:atoms#kebabId")
    assert uri == "vc:core:atoms" and kebab["type"] == "string"
    via_pointer, uri, ptr = resolve(f"vc:core:atoms#{ptr_of(resolve, 'vc:core:atoms#kebabId')}")
    assert via_pointer is kebab
    whole, uri, ptr = resolve("vc:core:atoms")
    assert uri == "vc:core:atoms" and ptr == "" and whole["$id"] == "vc:core:atoms"
    local, uri, _ = resolve("#/$defs/kebabId", "vc:core:atoms")
    assert local is kebab and uri == "vc:core:atoms"
    assert resolve("vc:no:such#thing") is None


def ptr_of(resolve, ref):
    return resolve(ref)[2]


# ------------------------------------------------- generate on the fixture (acc. 1)

def test_fixture_registry_has_nested_map_keyed_roles_and_links(mini_toolkit):
    reg, ext = _generate(mini_toolkit)
    fr = _by_path(_arrays(reg, "04_fr_list.json"))
    assert set(fr) == {".functional_requirements", ".ambiguities"}
    frs = fr[".functional_requirements"]
    assert frs["id_field"] == "fr_id" and frs["kind"] == "fr" and frs["source"] == "x-node"
    assert frs["role"] == "obligation-system"
    assert frs["contract"] == ["statement", "priority", "preconditions", "postconditions"]
    assert [n["array_path"] for n in frs["nested"]] == [".acceptance_criteria"]
    assert frs["nested"][0]["kind"] == "criterion"
    links = {lk["field"]: lk for lk in frs["links"]}
    assert links["derives_from"] == {
        "field": "derives_from", "kinds": ["capability"], "required": True,
        "built": True, "same_step_kinds": [],
    }
    assert links["depends_on"]["built"] is False
    # the shared definition is registered once per occurrence, with its own role
    assert fr[".ambiguities"]["kind"] == "ambiguity-item"
    assert fr[".ambiguities"]["role"] == "record"

    env = _arrays(reg, "02a_delivery_baseline.json")
    assert len(env) == 1
    assert env[0]["array_path"] == ".environments{}"
    assert env[0]["map_keyed"] is True and "id_field" not in env[0]
    assert env[0]["kind"] == "environment" and env[0]["role"] == "obligation-delivery"
    assert env[0]["links"][0]["field"] == "derives_from"

    assert _arrays(reg, "05_interface_contracts.json")[0]["array_path"] == ".interface.apis"
    # the plan schema describes the per-milestone plan files: its entries sit under their glob key
    assert _arrays(reg, "impl_context/ms_*_plan.json")[0]["array_path"] == ".plan_items"
    assert _arrays(reg, "01_capabilities.json")[0]["array_path"] == ".capabilities"
    assert reg["external_kinds"] == [{
        "kind": "seed", "source_file": "common/seed_manifest.json",
        "array_path": ".seeds", "id_field": "seed_id", "top_of_graph": True,
    }]
    assert reg["_format_version"] == "1.1.0"
    # extraction_paths lists annotation-derived entries in the legacy shape; no external_kinds
    assert ext["02a"]["02a_delivery_baseline.json"] == [".environments{}"]
    assert ext["04"]["04_fr_list.json"] == [
        ".functional_requirements", ".functional_requirements[].acceptance_criteria", ".ambiguities"
    ]
    assert "external_kinds" not in ext
    assert not any("seed" in str(v) for v in ext.values())


def test_fixture_output_is_byte_deterministic(mini_toolkit):
    root = mini_toolkit
    first = [_serialize(d) for d in _generate(root)]
    second = [_serialize(d) for d in _generate(root)]
    assert first == second


def test_fixture_registry_validates_against_widened_schema(mini_toolkit):
    reg, _ = _generate(mini_toolkit)
    schema = json.loads(_REG_SCHEMA.read_text())
    errs = list(Draft202012Validator(schema).iter_errors(reg))
    assert errs == []


# ----------------------------------------------- seed top-of-graph kind (WI-M1-05)

def test_real_registry_lists_seed_external_kind():
    reg, ext = generate_registry(str(_ROOT))
    assert reg["external_kinds"] == [{
        "kind": "seed", "source_file": "common/seed_manifest.json",
        "array_path": ".seeds", "id_field": "seed_id", "top_of_graph": True,
    }]
    assert "role" not in reg["external_kinds"][0]
    assert "seed_manifest" not in json.dumps(reg["registry"])
    assert "seed_manifest" not in json.dumps(ext)


def test_scan_of_real_toolkit_finds_seed_and_step_13_declares_only_extension_and_ambiguity_kinds():
    """Step 13 declares two kinds: its ``extension`` entry, whose one link names the upstream nodes that justify it (DEVSPEC-245), and the shared ambiguity list."""
    scan = scan_annotations(str(_ROOT))
    assert [e["kind"] for e in scan.external_kinds] == ["seed"]
    host = scan.host("schema/13_extension_manifest.schema.json")
    assert host is not None
    assert {occ.entry["kind"] for occ in host.occurrences} == {"ambiguity-item", "extension"}
    assert [[link["field"] for link in occ.entry["links"]] for occ in host.occurrences if occ.entry["kind"] == "extension"] == [["justified_by"]]


# ----------------------------------------- unannotated files unchanged (acc. 2)

_AMBIGUITY_PATHS = frozenset({".ambiguities", ".plan.ambiguities", ".execution.emergent_ambiguities"})


def _without_ambiguities(registry: dict) -> dict:
    """Registry view without the ambiguity arrays every step gained in 1.2.0 (WI-M3-03); a file left empty is dropped."""
    view = {
        key: {**entry, "arrays": [a for a in entry["arrays"] if a["array_path"] not in _AMBIGUITY_PATHS]}
        for key, entry in registry.items()
    }
    return {key: entry for key, entry in view.items() if entry["arrays"]}


def test_unannotated_files_are_byte_identical_to_pre_m1():
    reg, _ = generate_registry(str(_ROOT))
    pre = json.loads(_PRE_M1.read_text())
    view = _without_ambiguities(reg["registry"])
    annotated = {
        k for k, v in view.items()
        if any(a.get("source") == "x-node" for a in v["arrays"])
    }
    for key, entry in pre["registry"].items():
        if key in annotated:
            continue
        assert view[key] == entry, key
    assert set(view) - set(pre["registry"]) == annotated - set(pre["registry"])
    assert reg["_sentinels"] == pre["_sentinels"]
    annotated_deferred = {"16a"}  # registered through an x-node files glob since WI-M3-18
    inside_plan_file = {e["step"] for e in pre["steps_with_deferred_registration"]} - annotated_deferred
    assert {e["step"] for e in reg["steps_without_entry_arrays"]} - {e["step"] for e in pre["steps_without_entry_arrays"]} == inside_plan_file
    ambiguity_only = set(reg["registry"]) - set(view)
    annotated_steps = {k.split("_")[0] for k in annotated | ambiguity_only} | {"13a"}  # 13a: retired by M6c
    unchanged_steps = annotated_steps | inside_plan_file
    for key in ("steps_without_entry_arrays",):
        assert [e for e in reg[key] if e["step"] not in unchanged_steps] == [
            e for e in pre[key] if e["step"] not in unchanged_steps
        ], key
    differing = {k for k in set(reg) | set(pre) if reg.get(k) != pre.get(k)}
    # the registry map itself differs once any step is annotated; its keys are compared above
    assert differing - {"registry", "steps_without_entry_arrays"} == {
        "_format_version", "external_kinds", "steps_with_deferred_registration",
    }


def test_committed_registry_matches_generator_output():
    reg, ext = generate_registry(str(_ROOT))
    assert _serialize(reg) == (_ROOT / "tools" / "entry_key_registry.json").read_text()
    assert _serialize(ext) == (_ROOT / "tools" / "extraction_paths.json").read_text()


# --------------------------------------------------------------- path grammar (acc. 3)

_PATH_RE = re.compile(
    json.loads(_REG_SCHEMA.read_text())["$defs"]["arrayEntry"]["properties"]["array_path"]["pattern"]
)


@pytest.mark.parametrize("path", [
    ".functional_requirements", ".milestones[].tasks", ".milestones[].tasks[].acceptance_criteria",
    ".plan.items", ".environments{}", ".environments{}.checks", ".milestones[].envs{}",
])
def test_path_grammar_accepts(path):
    assert _PATH_RE.match(path)


@pytest.mark.parametrize("path", [
    "functional_requirements", ".a[]", ".a{}{}", ".a..b", ".1a", ".a[].", ".a b", "", ".",
])
def test_path_grammar_rejects(path):
    assert not _PATH_RE.match(path)


def test_registry_schema_rejects_malformed_array_path(mini_toolkit):
    reg, _ = _generate(mini_toolkit)
    bad = copy.deepcopy(reg)
    bad["registry"]["04_fr_list.json"]["arrays"][0]["array_path"] = ".a..b"
    schema = json.loads(_REG_SCHEMA.read_text())
    assert list(Draft202012Validator(schema).iter_errors(bad))


def test_registry_schema_requires_id_field_unless_map_keyed(mini_toolkit):
    reg, _ = _generate(mini_toolkit)
    bad = copy.deepcopy(reg)
    arr = bad["registry"]["04_fr_list.json"]["arrays"][0]
    del arr["id_field"]
    assert list(Draft202012Validator(json.loads(_REG_SCHEMA.read_text())).iter_errors(bad))


# ------------------------------------------- object paths, {type,id} lists, kinds (acc. 4)

_S07 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "vc:07-nfrs-fixture",
    "title": "NFRs (fixture)",
    "type": "object",
    "properties": {
        "plan": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "x-node": {"kind": "plan-thing", "id": "thing_id", "role": "record",
                               "contract": ["title"]},
                    "items": {
                        "type": "object",
                        "properties": {"thing_id": {"$ref": "vc:core:atoms#kebabId"},
                                       "title": {"type": "string"}},
                        "required": ["thing_id"],
                    },
                },
            },
        },
        "threats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "mitigations": {
                        "type": "array",
                        "items": {"type": "object",
                                  "properties": {"type": {"type": "string"},
                                                 "id": {"type": "string"}}},
                    },
                },
            },
        },
        "risks": {
            "type": "array",
            "x-node": {"kind": "risk-a", "id": "id", "role": "record", "contract": ["text"]},
            "items": {"type": "object",
                      "properties": {"id": {"$ref": "vc:core:atoms#kebabId"},
                                     "text": {"type": "string"}},
                      "required": ["id"]},
        },
        "issues": {
            "type": "array",
            "x-node": {"kind": "issue-b", "id": "id", "role": "record", "contract": ["text"]},
            "items": {"type": "object",
                      "properties": {"id": {"$ref": "vc:core:atoms#kebabId"},
                                     "text": {"type": "string"}},
                      "required": ["id"]},
        },
    },
}


EditJson = Callable[[Path, str, Callable[[dict], None]], None]


def _with_s07(root: Path, edit_json: EditJson) -> Path:
    """The mini toolkit at *root* plus a registered step-07 schema (``_S07``)."""
    (root / "schema" / "07_nfrs.schema.json").write_text(json.dumps(_S07, indent=2))
    edit_json(root, SREG, lambda d: d.update({"vc:07-nfrs-fixture": "schema/07_nfrs.schema.json"}))
    return root


def test_object_path_unannotated_type_id_list_and_distinct_kinds(mini_toolkit, edit_json):
    reg, _ = _generate(_with_s07(mini_toolkit, edit_json))
    arrays = _by_path(_arrays(reg, "07_nfrs.json"))
    assert set(arrays) == {".plan.items", ".risks", ".issues"}
    assert arrays[".plan.items"]["id_field"] == "thing_id"
    assert arrays[".risks"]["kind"] == "risk-a"
    assert arrays[".issues"]["kind"] == "issue-b"
    assert arrays[".risks"]["id_field"] == arrays[".issues"]["id_field"] == "id"


# --------------------------------------- $ref-only vs own annotation (acc. 7, X2-03)

def test_an_array_with_no_x_node_is_not_registered(edit_json, mini_toolkit):
    root = mini_toolkit

    def only_ref(doc):
        # 05: drop its own x-node + x-link; add an un-annotated array and reach the
        # shared ambiguity definition by $ref.
        apis = doc["properties"]["interface"]["properties"]["apis"]
        apis.pop("x-node")
        apis["items"]["properties"]["derives_from"].pop("x-link")
        doc["properties"]["things"] = {
            "type": "array",
            "items": {"type": "object", "properties": {"thing_id": {"type": "string"}}},
        }
        doc["properties"]["ambiguities"] = {"$ref": "vc:core:ambiguity-fixture#/$defs/ambiguityList"}

    def own_annotation(doc):
        # an un-annotated array of a file that keeps its own x-node is not registered either.
        doc["properties"]["legacy_things"] = {
            "type": "array",
            "items": {"type": "object", "properties": {"legacy_id": {"type": "string"}}},
        }

    edit_json(root, S05, only_ref)
    edit_json(root, S04, own_annotation)
    reg, _ = _generate(root)
    ref_only = _by_path(_arrays(reg, "05_interface_contracts.json"))
    assert ".things" not in ref_only
    assert ref_only[".ambiguities"]["kind"] == "ambiguity-item"
    assert ".interface.apis" not in ref_only
    annotated = _by_path(_arrays(reg, "04_fr_list.json"))
    assert ".legacy_things" not in annotated
    assert ".ambiguities" in annotated
    # the shared kind is registered once per occurrence: in both hosts
    kinds = [a["kind"] for k in ("04_fr_list.json", "05_interface_contracts.json")
             for a in _arrays(reg, k) if a["kind"] == "ambiguity-item"]
    assert len(kinds) == 2


# ----------------------------------------------------- glob file keys (x-node files)

def test_files_glob_becomes_registry_key(edit_json, mini_toolkit):
    root = mini_toolkit
    edit_json(root, "schema/16_impl_context.schema.json",
          lambda d: d["properties"]["plan_items"]["x-node"].update({"files": ["impl_context/ms_*_plan.json"]}))
    reg, ext = _generate(root)
    assert "16_impl_context.json" not in reg["registry"]
    entry = reg["registry"]["impl_context/ms_*_plan.json"]
    assert entry["step"] == "16a" and entry["arrays"][0]["array_path"] == ".plan_items"
    assert "impl_context/ms_*_plan.json" in ext["16a"]
    assert list(Draft202012Validator(json.loads(_REG_SCHEMA.read_text())).iter_errors(reg)) == []
    assert not any(s["step"] == "16" for s in reg["steps_without_entry_arrays"])


# ---------------------------------------------------- readers and helpers (acc. 5)

def test_iter_nodes_map_keyed_yields_key_as_id():
    data = {"environments": {"prod": {"url": "p"}, "dev-1": {"url": "d"}, "bad": 3}}
    got = list(iter_nodes(data, ".environments{}"))
    assert got == [
        ({"url": "p"}, '.environments["prod"]', "prod"),
        ({"url": "d"}, '.environments["dev-1"]', "dev-1"),
    ]


def test_iter_nodes_dotted_and_nested_paths():
    data = {"plan": {"items": [{"id": "a"}, 5, {"id": "b"}]},
            "milestones": [{"tasks": [{"id": "t1"}]}, {"tasks": [{"id": "t2"}]}, "x"],
            "envs": {"p": {"checks": [{"id": "c1"}]}}}
    assert [(i["id"], p, k) for i, p, k in iter_nodes(data, ".plan.items")] == [
        ("a", ".plan.items[0]", None), ("b", ".plan.items[2]", None)]
    assert [p for _, p, _ in iter_nodes(data, ".milestones[].tasks")] == [
        ".milestones[0].tasks[0]", ".milestones[1].tasks[0]"]
    assert [p for _, p, _ in iter_nodes(data, ".envs{}.checks")] == ['.envs["p"].checks[0]']
    assert list(iter_nodes({"plan": []}, ".plan.items")) == []
    assert list(iter_nodes([], ".plan")) == []


def test_array_key_helpers():
    assert array_top_key(".functional_requirements") == "functional_requirements"
    assert array_top_key(".milestones[].tasks") == "milestones"
    assert array_top_key(".plan.items") == "plan"
    assert array_top_key(".environments{}") == "environments"
    assert array_leaf_key(".functional_requirements") == "functional_requirements"
    assert array_leaf_key(".milestones[].tasks[].acceptance_criteria") == "acceptance_criteria"
    assert array_leaf_key(".plan.items") == "items"
    assert array_leaf_key(".environments{}") == "environments"
    assert array_leaf_key(".environments{}.checks") == "checks"


def _legacy_iter_array_path(data, array_path):
    """The pre-1.2.0 implementation, kept here as the reference."""
    if not isinstance(data, dict):
        return
    segments = array_path.lstrip(".").split("[].")

    def _descend(node, seg_index, prefix):
        key = segments[seg_index]
        is_last = seg_index == len(segments) - 1
        if not isinstance(node, dict):
            return
        val = node.get(key)
        if not isinstance(val, list):
            return
        for idx, item in enumerate(val):
            item_path = f"{prefix}.{key}[{idx}]"
            if is_last:
                if isinstance(item, dict):
                    yield item, item_path
            elif isinstance(item, dict):
                yield from _descend(item, seg_index + 1, item_path)

    yield from _descend(data, 0, "")


def test_iter_array_path_unchanged_on_the_spec_corpus():
    registry = json.loads((_ROOT / "tools" / "entry_key_registry.json").read_text())["registry"]
    checked = 0
    for basename in registry:
        corpus_file = _CORPUS / basename
        if not corpus_file.is_file():
            continue
        data = json.loads(corpus_file.read_text())
        for entry in list_entries(basename, str(_ROOT)) or []:
            old = [(id(i), p) for i, p in _legacy_iter_array_path(data, entry.array_path)]
            new = [(id(i), p) for i, p in iter_array_path(data, entry.array_path)]
            assert new == old, (basename, entry.array_path)
            checked += len(new)
    assert checked > 0


# --------------------------------- consumers parse the wider grammar and glob keys

def _registry_toolkit(tmp_path: Path, registry: dict[str, Any]) -> Path:
    root = tmp_path / "rt"
    (root / "tools").mkdir(parents=True)
    doc = {
        "$schema": "vc:entry-key-registry", "_format_version": "1.1.0", "_note": "t",
        "registry": registry, "_sentinels": [],
        "steps_without_entry_arrays": [],
        "external_kinds": [{"kind": "seed", "source_file": "common/seed_manifest.json",
                            "array_path": ".seeds", "id_field": "seed_id", "top_of_graph": True}],
    }
    (root / "tools" / "entry_key_registry.json").write_text(json.dumps(doc))
    return root


_WIDE_REGISTRY = {
    "02a_delivery_baseline.json": {"step": "02a", "arrays": [
        {"array_path": ".environments{}", "kind": "environment", "map_keyed": True,
         "source": "x-node"}]},
    "07_nfrs.json": {"step": "07", "arrays": [
        {"array_path": ".plan.items", "id_field": "thing_id", "kind": "plan-thing"}]},
    "impl_context/ms_*_plan.json": {"step": "16", "arrays": [
        {"array_path": ".plan_items", "id_field": "item_id", "kind": "plan-item"}]},
}


def test_json_id_collection_on_wide_paths(tmp_path):
    root = str(_registry_toolkit(tmp_path, _WIDE_REGISTRY))
    envs = {"environments": {"prod": {"url": "p"}, "dev": {"url": "d"}}}
    ids, id_map = _collect_ids_from_file(envs, "02a_delivery_baseline.json", root)
    assert ids == ["prod", "dev"]
    assert id_map["prod"] == ("environment", '.environments["prod"]', {"url": "p"})
    plan = {"plan": {"items": [{"thing_id": "a"}, {"thing_id": "b"}]}}
    ids, id_map = _collect_ids_from_file(plan, "07_nfrs.json", root)
    assert ids == ["a", "b"] and id_map["b"][:2] == ("plan-thing", ".plan.items[1]")


def test_glob_key_in_list_entries_and_step_lookup(tmp_path):
    root = str(_registry_toolkit(tmp_path, _WIDE_REGISTRY))
    entries = list_entries("spec/impl_context/ms_1_plan.json", root)
    assert [(e.array_path, e.id_field, e.kind) for e in entries] == [(".plan_items", "item_id", "plan-item")]
    assert list_entries("spec/other/ms_1_plan.json", root) is None
    assert get_step_for_file("impl_context/ms_2_plan.json", root) == "16"
    reg, _ = _load(root)
    assert "external_kinds" not in reg


def _write_checked_toolkit(tmp_path: Path) -> tuple[Path, Path]:
    root = _registry_toolkit(tmp_path, _WIDE_REGISTRY)
    paths = {"_meta": {}, "02a": {"02a_delivery_baseline.json": [".environments{}"]},
             "07": {"07_nfrs.json": [".plan.items"]},
             "16": {"impl_context/ms_*_plan.json": [".plan_items"]}}
    (root / "tools" / "extraction_paths.json").write_text(json.dumps(paths))
    spec = tmp_path / "spec"
    spec.mkdir()
    return root, spec


def test_registry_check_glob_key_without_matching_file_is_silent(tmp_path):
    root, spec = _write_checked_toolkit(tmp_path)
    errs = run_registry_check(str(spec), str(root))
    assert [e.code for e in errs if e.code in ("E621", "E622")] == []


def test_registry_check_glob_key_checks_matching_files(tmp_path):
    root, spec = _write_checked_toolkit(tmp_path)
    (spec / "impl_context").mkdir()
    (spec / "impl_context" / "ms_1_plan.json").write_text(json.dumps({"plan_items": [{"wrong": 1}]}))
    errs = run_registry_check(str(spec), str(root))
    assert [e.code for e in errs] == ["E622"]
    assert "impl_context/ms_1_plan.json" in errs[0].message
    (spec / "impl_context" / "ms_1_plan.json").write_text(json.dumps({"plan_items": [{"item_id": "X"}]}))
    assert run_registry_check(str(spec), str(root)) == []


def test_registry_check_wide_paths_do_not_misfire(tmp_path):
    root, spec = _write_checked_toolkit(tmp_path)
    (spec / "02a_delivery_baseline.json").write_text(json.dumps({"environments": {"prod": {}}}))
    (spec / "07_nfrs.json").write_text(json.dumps({"plan": {"items": [{"thing_id": "a"}]}}))
    assert run_registry_check(str(spec), str(root)) == []
    (spec / "07_nfrs.json").write_text(json.dumps({"plan": {"items": [{"other": "a"}]}}))
    assert [e.code for e in run_registry_check(str(spec), str(root))] == ["E622"]


def _wide_check(tmp_path, registry, spec_files):
    root = _registry_toolkit(tmp_path, registry)
    paths = {"_meta": {}, **{e["step"]: {k: [a["array_path"] for a in e["arrays"]]} for k, e in registry.items()}}
    (root / "tools" / "extraction_paths.json").write_text(json.dumps(paths))
    spec = tmp_path / "spec"
    spec.mkdir()
    for name, body in spec_files.items():
        (spec / name).write_text(json.dumps(body))
    return [e for e in run_registry_check(str(spec), str(root)) if e.code in ("E621", "E622")]


_NFR_REGISTRY = {"07_nfrs.json": _WIDE_REGISTRY["07_nfrs.json"]}


def test_registry_check_wide_root_entry_absent_first_hop_is_not_drift(tmp_path):
    assert _wide_check(tmp_path, _NFR_REGISTRY, {"07_nfrs.json": {}}) == []
    assert _wide_check(tmp_path / "b", _NFR_REGISTRY, {"07_nfrs.json": {"plan": {}}}) == []


def test_registry_check_wide_root_entry_wrong_type_is_e622_and_empty_is_silent(tmp_path):
    errs = _wide_check(tmp_path, _NFR_REGISTRY, {"07_nfrs.json": {"plan": {"items": {"a": 1}}}})
    assert [e.code for e in errs] == ["E622"] and "not an array" in errs[0].message
    assert _wide_check(tmp_path / "b", _NFR_REGISTRY, {"07_nfrs.json": {"plan": {"items": []}}}) == []


def test_registry_check_wide_root_map_entry_absent_is_silent_and_wrong_type_is_e622(tmp_path):
    reg = {"02a_delivery_baseline.json": _WIDE_REGISTRY["02a_delivery_baseline.json"]}
    assert _wide_check(tmp_path, reg, {"02a_delivery_baseline.json": {}}) == []
    errs = _wide_check(tmp_path / "b", reg, {"02a_delivery_baseline.json": {"environments": []}})
    assert [e.code for e in errs] == ["E622"] and "not a map" in errs[0].message
    assert _wide_check(tmp_path / "c", reg, {"02a_delivery_baseline.json": {"environments": {}}}) == []


def test_registry_check_glob_key_with_bracket_in_spec_root(tmp_path):
    base = tmp_path / "we[ird]"
    base.mkdir()
    root, spec = _write_checked_toolkit(base)
    (spec / "impl_context").mkdir()
    (spec / "impl_context" / "ms_1_plan.json").write_text(json.dumps({"plan_items": [{"wrong": 1}]}))
    assert [e.code for e in run_registry_check(str(spec), str(root))] == ["E622"]


def test_match_glob_key_star_does_not_cross_a_slash():
    from specdev_tools.core.entry_key_registry import match_glob_key

    assert match_glob_key("spec/impl_context/ms_1_plan.json", "impl_context/ms_*_plan.json")
    assert match_glob_key("impl_context/ms_1_plan.json", "impl_context/ms_*_plan.json")
    assert not match_glob_key("impl_context/ms_1/x_plan.json", "impl_context/ms_*_plan.json")
    assert not match_glob_key("impl_context/sub/ms_1_plan.json", "impl_context/*_plan.json")


def test_corpus_excluded_wide_path_is_keyed_by_top_key(tmp_path):
    from specdev_tools.core.entry_key_registry import is_corpus_excluded

    reg = {"07_nfrs.json": {"step": "07", "arrays": [
        {"array_path": ".plan.items", "id_field": "thing_id", "kind": "plan-thing", "corpus_excluded": True}]}}
    root = str(_registry_toolkit(tmp_path, reg))
    assert is_corpus_excluded("plan", root)


# ------------------------------------------- record hosts (registered non-step schemas)

def test_non_step_schema_with_files_is_a_record_host(mini_toolkit):
    root = mini_toolkit
    reg, ext = _generate(root)
    entry = reg["registry"]["extras/sample/*.json"]
    assert entry["step"] == "extras"
    assert [(a["kind"], a["array_path"], a["role"]) for a in entry["arrays"]] == [
        ("sample-record", ".records", "record")]
    assert "extras" not in ext
    assert list(Draft202012Validator(json.loads(_REG_SCHEMA.read_text())).iter_errors(reg)) == []
    spec = root / "spec" / "extras" / "sample"
    spec.mkdir(parents=True)
    (spec / "a.json").write_text(json.dumps({"records": [{"record_id": "rec-1", "note": "n"}]}))
    reg_path = root / "tools" / "entry_key_registry.json"
    reg_path.write_text(json.dumps(reg))
    entries = list_entries("spec/extras/sample/a.json", str(root))
    assert [(e.array_path, e.id_field, e.kind) for e in entries] == [(".records", "record_id", "sample-record")]
    data = json.loads((spec / "a.json").read_text())
    assert [i["record_id"] for i, _, _ in iter_nodes(data, entries[0].array_path)] == ["rec-1"]


def _add_second_record_host(
    root: Path, edit_json: EditJson, x_node_edit: Callable[[dict], None] = lambda x: None) -> None:
    """A second registered record host that claims the same ``files`` glob as the sample host."""
    doc = json.loads((root / "schema/extras/sample_record.schema.json").read_text())
    doc["$id"] = "vc:extras-other-record"
    xn = doc["properties"]["records"]["x-node"]
    xn["kind"] = "other-record"
    x_node_edit(xn)
    (root / "schema/extras/other_record.schema.json").write_text(json.dumps(doc))
    edit_json(root, SREG, lambda d: d.update(
        {"vc:extras-other-record": "schema/extras/other_record.schema.json"}))


def test_record_host_ignores_x_node_step(edit_json, mini_toolkit):
    root = mini_toolkit
    edit_json(root, "schema/extras/sample_record.schema.json",
          lambda d: d["properties"]["records"]["x-node"].update(step="05"))
    reg, ext = _generate(root)
    assert reg["registry"]["extras/sample/*.json"]["step"] == "extras"
    assert not any("extras/sample/*.json" in block for block in ext.values() if isinstance(block, dict))


def test_record_host_reached_through_a_step_ref_is_registered_once(edit_json, mini_toolkit):
    root = mini_toolkit
    edit_json(root, "schema/extras/sample_record.schema.json",
          lambda d: d["properties"]["records"]["x-node"].update(step="04"))
    edit_json(root, S04, lambda d: d.setdefault("allOf", []).append({"$ref": "vc:extras-sample-record"}))
    reg, _ = _generate(root)
    assert [a["kind"] for a in _arrays(reg, "extras/sample/*.json")] == ["sample-record"]
    assert reg["registry"]["extras/sample/*.json"]["step"] == "extras"


def test_two_record_hosts_on_one_glob_both_register_under_extras(mini_toolkit, edit_json):
    root = mini_toolkit
    _add_second_record_host(root, edit_json, lambda xn: xn.update(step="05"))
    reg, _ = _generate(root)
    entry = reg["registry"]["extras/sample/*.json"]
    assert entry["step"] == "extras"
    assert sorted(a["kind"] for a in entry["arrays"]) == ["other-record", "sample-record"]


def test_run_collects_annotations_once_with_step_order_out(tmp_path, monkeypatch, mini_toolkit):
    root = mini_toolkit
    calls = []
    real = generate_mod.collect_annotations
    counting = lambda r: calls.append(r) or real(r)  # noqa: E731
    monkeypatch.setattr(generate_mod, "collect_annotations", counting)
    clear_shared_caches()
    generate_mod.run(
        str(root), str(tmp_path / "r.json"), str(tmp_path / "e.json"),
        step_order_out=str(tmp_path / "o.json"),
    )
    assert len(calls) == 1
    assert json.loads((tmp_path / "o.json").read_text())["steps"]
