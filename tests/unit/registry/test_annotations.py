"""Tests for the x-node / x-link annotation reader and lint (WI-M1-03)."""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Callable

import pytest

from specdev_tools.core.registry import clear_shared_caches
from specdev_tools.registry.annotations import (
    AnnotationError,
    collect_annotations,
    lint_annotations,
)
from specdev_tools.registry.generate import _serialize, generate_registry

_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _ROOT / "tests" / "fixtures" / "graph"
_MINI = _FIXTURES / "mini_toolkit"

S01 = "schema/01_capabilities.schema.json"
S02A = "schema/02a_delivery_baseline.schema.json"
S04 = "schema/04_fr_list.schema.json"
S05 = "schema/05_interface_contracts.schema.json"
S16 = "schema/16_impl_context.schema.json"
AMB = "schema/core/ambiguity.schema.json"
LIFE = {"$ref": "vc:core:graph#lifecycle"}


@pytest.fixture(autouse=True)
def _fresh_caches():
    clear_shared_caches()
    yield
    clear_shared_caches()


def _build(tmp_path: Path) -> Path:
    root = tmp_path / "tk"
    shutil.copytree(_MINI, root)
    for name in ("graph", "atoms"):
        shutil.copy(_ROOT / "schema" / "core" / f"{name}.schema.json", root / "schema" / "core")
    return root


def _edit(root: Path, rel: str, fn: Callable[[dict], None]) -> None:
    p = root / rel
    doc = json.loads(p.read_text())
    fn(doc)
    p.write_text(json.dumps(doc, indent=2) + "\n")


def _lint(root: Path) -> list[str]:
    clear_shared_caches()
    return lint_annotations(collect_annotations(str(root)))


def _with(issues: list[str], code: str) -> list[str]:
    return [i for i in issues if i.startswith(code)]


def _fr_item(doc: dict) -> dict:
    return doc["properties"]["functional_requirements"]["items"]


# ---------------------------------------------------------------- positive

def test_fixture_toolkit_lints_clean(tmp_path):
    assert _lint(_build(tmp_path)) == []


def test_collect_reads_nodes_and_links(tmp_path):
    decls = collect_annotations(str(_build(tmp_path)))
    kinds = sorted(n.kind for n in decls.nodes)
    assert kinds == [
        "ambiguity-item", "api", "capability", "criterion", "environment", "fr", "plan-item", "seed",
    ]
    holders = {(l.field_name, tuple(sorted(l.holders))) for l in decls.links}
    assert ("derives_from", ("fr",)) in holders
    assert ("realises", ("plan-item",)) in holders
    assert ("about", ("ambiguity-item",)) in holders


def test_shared_definition_referenced_from_two_files_counts_once(tmp_path):
    decls = collect_annotations(str(_build(tmp_path)))
    amb = [n for n in decls.nodes if n.kind == "ambiguity-item"]
    assert len(amb) == 1
    assert amb[0].schema_file == AMB


def test_same_definition_reached_in_then_and_else_is_no_error(tmp_path):
    root = _build(tmp_path)
    ref = {"$ref": "vc:core:ambiguity-fixture#/$defs/ambiguityList"}

    def add(doc):
        doc["allOf"] = [{
            "if": {"required": ["ambiguities"]},
            "then": {"properties": {"amb_then": ref}},
            "else": {"properties": {"amb_else": ref}},
        }]

    _edit(root, S04, add)
    assert _lint(root) == []


def test_record_item_without_lifecycle_passes(tmp_path):
    root = _build(tmp_path)
    amb = json.loads((root / AMB).read_text())["$defs"]["ambiguityList"]
    assert "lifecycle" not in amb["items"]["properties"]
    assert _lint(root) == []


def test_map_keyed_item_under_additional_properties_lints_clean(tmp_path):
    decls = collect_annotations(str(_build(tmp_path)))
    env = next(n for n in decls.nodes if n.kind == "environment")
    assert env.value["map_keyed"] is True
    assert env.path == "/properties/environments"


def test_real_toolkit_schemas_lint_clean():
    clear_shared_caches()
    assert lint_annotations(collect_annotations(str(_ROOT))) == []


# ------------------------------------------------------------------ skips

def test_toolkit_without_graph_schema_is_skipped(tmp_path):
    root = _build(tmp_path)
    reg = json.loads((root / "tools/schema_registry.json").read_text())
    del reg["vc:core:graph"]
    (root / "tools/schema_registry.json").write_text(json.dumps(reg))
    decls = collect_annotations(str(root))
    assert decls.empty
    assert lint_annotations(decls) == []


def test_toolkit_without_annotations_is_skipped(tmp_path):
    root = tmp_path / "plain"
    (root / "tools").mkdir(parents=True)
    (root / "schema" / "core").mkdir(parents=True)
    shutil.copy(_ROOT / "schema" / "core" / "graph.schema.json", root / "schema" / "core")
    (root / "tools/schema_registry.json").write_text(json.dumps({"vc:core:graph": "schema/core/graph.schema.json"}))
    assert collect_annotations(str(root)).empty


def test_toolkit_without_registry_file_is_skipped(tmp_path):
    assert collect_annotations(str(tmp_path)).empty


# ----------------------------------------------------- generate_registry

def _generator_toolkit(tmp_path: Path, with_fixture: bool) -> Path:
    root = tmp_path / "gen"
    (root / "tools").mkdir(parents=True)
    (root / "schema" / "core").mkdir(parents=True)
    shutil.copy(_ROOT / "tools" / "step_order.json", root / "tools")
    shutil.copy(_ROOT / "schema" / "core" / "collections.schema.json", root / "schema" / "core")
    if with_fixture:
        for sub in ("tools/schema_registry.json", "schema"):
            src = _MINI / sub
            if src.is_dir():
                shutil.copytree(src, root / sub, dirs_exist_ok=True)
            else:
                shutil.copy(src, root / sub)
        for name in ("graph", "atoms"):
            shutil.copy(_ROOT / "schema" / "core" / f"{name}.schema.json", root / "schema" / "core")
    return root


def test_generate_registry_raises_annotation_error(tmp_path):
    root = _generator_toolkit(tmp_path, with_fixture=True)
    _edit(root, S04, lambda d: _fr_item(d)["properties"].pop("fr_id"))
    clear_shared_caches()
    with pytest.raises(AnnotationError) as exc:
        generate_registry(str(root))
    assert isinstance(exc.value, ValueError)
    assert any(i.startswith("ANNOT-03") for i in exc.value.issues)


def test_generate_registry_clean_fixture_does_not_raise(tmp_path):
    clear_shared_caches()
    generate_registry(str(_generator_toolkit(tmp_path, with_fixture=True)))


def test_legacy_output_byte_identical_without_graph_schema(tmp_path, monkeypatch):
    import specdev_tools.registry.generate as gen

    root = _generator_toolkit(tmp_path, with_fixture=False)
    assert collect_annotations(str(root)).empty
    clear_shared_caches()
    actual = [_serialize(d) for d in generate_registry(str(root))]
    monkeypatch.setattr(gen, "lint_annotations", lambda decls: [])
    clear_shared_caches()
    baseline = [_serialize(d) for d in generate_registry(str(root))]
    assert actual == baseline


# ---------------------------------------------------------- ANNOT-01

def test_annot01_invalid_x_node(tmp_path):
    root = _build(tmp_path)
    _edit(root, S01, lambda d: d["properties"]["capabilities"]["x-node"].pop("contract"))
    issues = _with(_lint(root), "ANNOT-01")
    assert issues and S01 in issues[0] and "/properties/capabilities" in issues[0]


def test_annot01_invalid_x_link(tmp_path):
    root = _build(tmp_path)

    def bad(d):
        d["properties"]["plan_items"]["items"]["properties"]["realises"]["x-link"].pop("required")

    _edit(root, S16, bad)
    issues = _with(_lint(root), "ANNOT-01")
    assert issues and S16 in issues[0] and "realises" in issues[0]


# ---------------------------------------------------------- ANNOT-02

def test_annot02_two_sites_one_kind(tmp_path):
    root = _build(tmp_path)

    def dup(d):
        d["properties"]["interface"]["properties"]["apis"]["x-node"]["kind"] = "fr"

    _edit(root, S05, dup)
    issues = _with(_lint(root), "ANNOT-02")
    assert len(issues) == 1
    assert S04 in issues[0] and S05 in issues[0]


def test_annot02_kind_must_be_kebab_case(tmp_path):
    root = _build(tmp_path)
    _edit(root, S01, lambda d: d["properties"]["capabilities"]["x-node"].update(kind="Bad_Kind"))
    issues = _with(_lint(root), "ANNOT-02")
    assert issues and S01 in issues[0]


# ---------------------------------------------------------- ANNOT-03

def test_annot03_id_property_missing(tmp_path):
    root = _build(tmp_path)
    _edit(root, S04, lambda d: _fr_item(d)["properties"].pop("fr_id"))
    issues = _with(_lint(root), "ANNOT-03")
    assert len(issues) == 1 and S04 in issues[0] and "fr_id" in issues[0]
    assert "/properties/functional_requirements" in issues[0]


def test_annot03_id_property_not_a_string(tmp_path):
    root = _build(tmp_path)
    _edit(root, S04, lambda d: _fr_item(d)["properties"].__setitem__("fr_id", {"type": "integer"}))
    issues = _with(_lint(root), "ANNOT-03")
    assert len(issues) == 1 and "not a string" in issues[0]


def test_annot03_map_keyed_needs_additional_properties_object(tmp_path):
    root = _build(tmp_path)
    _edit(root, S02A, lambda d: d["properties"]["environments"].__setitem__("additionalProperties", True))
    issues = _with(_lint(root), "ANNOT-03")
    assert len(issues) == 1 and S02A in issues[0] and "additionalProperties" in issues[0]


def test_annot03_does_not_read_fields_beside_additional_properties(tmp_path):
    root = _build(tmp_path)
    shutil.copy(_FIXTURES / "neg_map_beside_additional.schema.json", root / S02A)
    issues = _lint(root)
    assert _with(issues, "ANNOT-03") == []
    # the item is the additionalProperties value: its missing lifecycle is what fails
    assert any(i.startswith("ANNOT-08") and S02A in i and "lifecycle" in i for i in issues)


# ---------------------------------------------------------- ANNOT-05

def _realises(d: dict) -> dict:
    return d["properties"]["plan_items"]["items"]["properties"]


def test_annot05_field_name_not_a_verb(tmp_path):
    root = _build(tmp_path)
    _edit(root, S16, lambda d: _realises(d).__setitem__("relates_to", _realises(d).pop("realises")))
    issues = _with(_lint(root), "ANNOT-05")
    assert issues and S16 in issues[0] and "relates_to" in issues[0]


def test_annot05_field_not_an_array_of_id_atoms(tmp_path):
    root = _build(tmp_path)
    _edit(root, S16, lambda d: _realises(d)["realises"].update(type="string"))
    assert _with(_lint(root), "ANNOT-05")
    root2 = _build(tmp_path / "two")
    _edit(root2, S16, lambda d: _realises(d)["realises"].update(items={"type": "string"}))
    issues = _with(_lint(root2), "ANNOT-05")
    assert issues and S16 in issues[0]


def test_annot05_nodeid_and_screaming_snake_atoms_are_allowed(tmp_path):
    root = _build(tmp_path)
    _edit(root, S16, lambda d: _realises(d)["realises"].update(
        items={"$ref": "vc:core:graph#nodeId"}))
    assert _lint(root) == []
    root2 = _build(tmp_path / "two")
    _edit(root2, S16, lambda d: _realises(d)["realises"].update(
        items={"$ref": "vc:core:atoms#screamingSnakeId"}))
    assert _lint(root2) == []


def test_annot05_wildcard_and_about_fields_must_reference_nodeid(tmp_path):
    root = _build(tmp_path)
    # kinds "*" with a plain kebabId must fail
    _edit(root, S16, lambda d: _realises(d)["realises"]["x-link"].update(kinds="*"))
    issues = _with(_lint(root), "ANNOT-05")
    assert issues and "nodeId" in issues[0]
    # the same with nodeId is clean
    _edit(root, S16, lambda d: _realises(d)["realises"].update(items={"$ref": "vc:core:graph#nodeId"}))
    assert _with(_lint(root), "ANNOT-05") == []
    # verb about with kebabId (explicit kinds) must fail
    root2 = _build(tmp_path / "two")
    _edit(root2, S16, lambda d: _realises(d).__setitem__("about", _realises(d).pop("realises")))
    issues = _with(_lint(root2), "ANNOT-05")
    assert any("about" in i and "nodeId" in i for i in issues)


def test_annot05_link_must_sit_on_a_node_item(tmp_path):
    root = _build(tmp_path)

    def stray(d):
        d["properties"]["depends_on"] = {
            "type": "array", "items": {"$ref": "vc:core:atoms#kebabId"},
            "x-link": {"kinds": ["fr"], "required": False},
        }

    _edit(root, S04, stray)
    issues = _with(_lint(root), "ANNOT-05")
    assert issues and S04 in issues[0] and "node item" in issues[0]


# ---------------------------------------------------------- ANNOT-07

def test_annot07_unknown_kind(tmp_path):
    root = _build(tmp_path)
    _edit(root, S16, lambda d: _realises(d)["realises"]["x-link"].update(kinds=["nope"]))
    issues = _with(_lint(root), "ANNOT-07")
    assert len(issues) == 1 and S16 in issues[0] and "'nope'" in issues[0]


def test_annot07_seed_is_an_allowed_external_kind(tmp_path):
    root = _build(tmp_path)
    _edit(root, S16, lambda d: _realises(d)["realises"]["x-link"].update(kinds=["seed"]))
    assert _with(_lint(root), "ANNOT-07") == []


def test_annot07_same_step_kinds_must_be_subset(tmp_path):
    root = _build(tmp_path)
    _edit(root, S16, lambda d: _realises(d)["realises"]["x-link"].update(
        kinds=["fr"], same_step_kinds=["api"]))
    issues = _with(_lint(root), "ANNOT-07")
    assert len(issues) == 1 and "same_step_kinds" in issues[0]


# ---------------------------------------------------------- ANNOT-08

def test_annot08_context_role_without_lifecycle_fails(tmp_path):
    root = _build(tmp_path)

    def ctx(d):
        d["properties"]["plan_items"]["x-node"]["role"] = "context"
        _realises(d).pop("lifecycle")

    _edit(root, S16, ctx)
    issues = _with(_lint(root), "ANNOT-08")
    assert len(issues) == 1 and S16 in issues[0] and "lifecycle" in issues[0]


def test_annot08_obligation_without_scope_fails(tmp_path):
    root = _build(tmp_path)
    _edit(root, S04, lambda d: _fr_item(d)["properties"].pop("scope"))
    issues = _with(_lint(root), "ANNOT-08")
    assert len(issues) == 1 and "scope" in issues[0]


def test_annot08_obligation_without_scope_reason_rule_fails(tmp_path):
    root = _build(tmp_path)
    _edit(root, S04, lambda d: _fr_item(d).pop("allOf"))
    issues = _with(_lint(root), "ANNOT-08")
    assert len(issues) == 1 and "scopeReasonRule" in issues[0]


def test_annot08_top_of_graph_is_exempt(tmp_path):
    root = _build(tmp_path)
    seed = json.loads((root / "schema/seed_manifest.schema.json").read_text())
    assert "lifecycle" not in seed["properties"]["seeds"]["items"]["properties"]
    assert _with(_lint(root), "ANNOT-08") == []
