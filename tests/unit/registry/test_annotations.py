"""Tests for the x-node / x-link annotation reader and lint (WI-M1-03)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

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


def _lint(root: Path) -> list[str]:
    clear_shared_caches()
    return lint_annotations(collect_annotations(str(root)))


def _with(issues: list[str], code: str) -> list[str]:
    return [i for i in issues if i.startswith(code)]


def _fr_item(doc: dict) -> dict:
    return doc["properties"]["functional_requirements"]["items"]


# ---------------------------------------------------------------- positive

def test_fixture_toolkit_lints_clean(mini_toolkit):
    assert _lint(mini_toolkit) == []


def test_collect_reads_nodes_and_links(mini_toolkit):
    decls = collect_annotations(str(mini_toolkit))
    kinds = sorted(n.kind for n in decls.nodes)
    assert kinds == [
        "ambiguity-item", "api", "capability", "criterion", "environment", "fr", "plan-item",
        "sample-record", "seed",
    ]
    holders = {(l.field_name, tuple(sorted(l.holders))) for l in decls.links}
    assert ("derives_from", ("fr",)) in holders
    assert ("realises", ("plan-item",)) in holders
    assert ("about", ("ambiguity-item",)) in holders


def test_shared_definition_referenced_from_two_files_counts_once(mini_toolkit):
    decls = collect_annotations(str(mini_toolkit))
    amb = [n for n in decls.nodes if n.kind == "ambiguity-item"]
    assert len(amb) == 1
    assert amb[0].schema_file == AMB


def test_same_definition_reached_in_then_and_else_is_no_error(edit_json, mini_toolkit):
    root = mini_toolkit
    ref = {"$ref": "vc:core:ambiguity-fixture#/$defs/ambiguityList"}

    def add(doc):
        doc["allOf"] = [{
            "if": {"required": ["ambiguities"]},
            "then": {"properties": {"amb_then": ref}},
            "else": {"properties": {"amb_else": ref}},
        }]

    edit_json(root, S04, add)
    assert _lint(root) == []


def test_record_item_without_lifecycle_passes(mini_toolkit):
    root = mini_toolkit
    amb = json.loads((root / AMB).read_text())["$defs"]["ambiguityList"]
    assert "lifecycle" not in amb["items"]["properties"]
    assert _lint(root) == []


def test_map_keyed_item_under_additional_properties_lints_clean(mini_toolkit):
    decls = collect_annotations(str(mini_toolkit))
    env = next(n for n in decls.nodes if n.kind == "environment")
    assert env.value["map_keyed"] is True
    assert env.path == "/properties/environments"


def test_real_toolkit_schemas_lint_clean():
    clear_shared_caches()
    assert lint_annotations(collect_annotations(str(_ROOT))) == []


# ------------------------------------------------------------------ skips

def test_toolkit_without_graph_schema_is_skipped(mini_toolkit):
    root = mini_toolkit
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


def test_generate_registry_raises_annotation_error(tmp_path, edit_json):
    root = _generator_toolkit(tmp_path, with_fixture=True)
    edit_json(root, S04, lambda d: _fr_item(d)["properties"].pop("fr_id"))
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


def test_annot03_does_not_read_fields_beside_additional_properties(mini_toolkit):
    root = mini_toolkit
    shutil.copy(_FIXTURES / "neg_map_beside_additional.schema.json", root / S02A)
    issues = _lint(root)
    assert _with(issues, "ANNOT-03") == []
    # the item is the additionalProperties value: its missing lifecycle is what fails
    assert any(i.startswith("ANNOT-08") and S02A in i and "lifecycle" in i for i in issues)


def _realises(d: dict) -> dict:
    return d["properties"]["plan_items"]["items"]["properties"]


def test_annot05_field_not_an_array_of_id_atoms(tmp_path, edit_json, mini_toolkit_at, mini_toolkit):
    root = mini_toolkit
    edit_json(root, S16, lambda d: _realises(d)["realises"].update(type="string"))
    assert _with(_lint(root), "ANNOT-05")
    root2 = mini_toolkit_at(tmp_path / "two")
    edit_json(root2, S16, lambda d: _realises(d)["realises"].update(items={"type": "string"}))
    issues = _with(_lint(root2), "ANNOT-05")
    assert issues and S16 in issues[0]


def test_annot05_nodeid_and_screaming_snake_atoms_are_allowed(tmp_path, edit_json, mini_toolkit_at, mini_toolkit):
    root = mini_toolkit
    edit_json(root, S16, lambda d: _realises(d)["realises"].update(
        items={"$ref": "vc:core:graph#nodeId"}))
    assert _lint(root) == []
    root2 = mini_toolkit_at(tmp_path / "two")
    edit_json(root2, S16, lambda d: _realises(d)["realises"].update(
        items={"$ref": "vc:core:atoms#screamingSnakeId"}))
    assert _lint(root2) == []


def test_annot05_wildcard_and_about_fields_must_reference_nodeid(tmp_path, edit_json, mini_toolkit_at, mini_toolkit):
    root = mini_toolkit
    # kinds "*" with a plain kebabId must fail
    edit_json(root, S16, lambda d: _realises(d)["realises"]["x-link"].update(kinds="*"))
    issues = _with(_lint(root), "ANNOT-05")
    assert issues and "nodeId" in issues[0]
    # the same with nodeId is clean
    edit_json(root, S16, lambda d: _realises(d)["realises"].update(items={"$ref": "vc:core:graph#nodeId"}))
    assert _with(_lint(root), "ANNOT-05") == []
    # verb about with kebabId (explicit kinds) must fail
    root2 = mini_toolkit_at(tmp_path / "two")
    edit_json(root2, S16, lambda d: _realises(d).__setitem__("about", _realises(d).pop("realises")))
    issues = _with(_lint(root2), "ANNOT-05")
    assert any("about" in i and "nodeId" in i for i in issues)


def test_annot07_seed_is_an_allowed_external_kind(edit_json, mini_toolkit):
    root = mini_toolkit
    edit_json(root, S16, lambda d: _realises(d)["realises"]["x-link"].update(kinds=["seed"]))
    assert _with(_lint(root), "ANNOT-07") == []


def test_annot08_top_of_graph_is_exempt(mini_toolkit):
    root = mini_toolkit
    seed = json.loads((root / "schema/seed_manifest.schema.json").read_text())
    assert "lifecycle" not in seed["properties"]["seeds"]["items"]["properties"]
    assert _with(_lint(root), "ANNOT-08") == []


# ------------------------------------------- one edit, one ANNOT code expected

def _pop_link_required(d: dict) -> None:
    d["properties"]["plan_items"]["items"]["properties"]["realises"]["x-link"].pop("required")


def _kind_of_apis_is_fr(d: dict) -> None:
    d["properties"]["interface"]["properties"]["apis"]["x-node"]["kind"] = "fr"


def _plan_item_is_context_without_lifecycle(d: dict) -> None:
    d["properties"]["plan_items"]["x-node"]["role"] = "context"
    _realises(d).pop("lifecycle")


def _add_stray_link(d: dict) -> None:
    d["properties"]["depends_on"] = {
        "type": "array", "items": {"$ref": "vc:core:atoms#kebabId"},
        "x-link": {"kinds": ["fr"], "required": False},
    }


# (id, schema, edit, code, expected issue count or None for "at least one", texts in the first issue)
_EDIT_CASES = [
    ("annot01-x-node", S01, lambda d: d["properties"]["capabilities"]["x-node"].pop("contract"),
     "ANNOT-01", None, [S01, "/properties/capabilities"]),
    ("annot01-x-link", S16, _pop_link_required, "ANNOT-01", None, [S16, "realises"]),
    ("annot02-two-sites", S05, _kind_of_apis_is_fr, "ANNOT-02", 1, [S04, S05]),
    ("annot02-kebab", S01, lambda d: d["properties"]["capabilities"]["x-node"].update(kind="Bad_Kind"),
     "ANNOT-02", None, [S01]),
    ("annot03-id-missing", S04, lambda d: _fr_item(d)["properties"].pop("fr_id"),
     "ANNOT-03", 1, [S04, "fr_id", "/properties/functional_requirements"]),
    ("annot03-id-not-string",
     S04, lambda d: _fr_item(d)["properties"].__setitem__("fr_id", {"type": "integer"}),
     "ANNOT-03", 1, ["not a string"]),
    ("annot03-map-keyed", S02A,
     lambda d: d["properties"]["environments"].__setitem__("additionalProperties", True),
     "ANNOT-03", 1, [S02A, "additionalProperties"]),
    ("annot05-not-a-verb", S16,
     lambda d: _realises(d).__setitem__("relates_to", _realises(d).pop("realises")),
     "ANNOT-05", None, [S16, "relates_to"]),
    ("annot05-stray-link", S04, _add_stray_link, "ANNOT-05", None, [S04, "node item"]),
    ("annot07-unknown-kind", S16, lambda d: _realises(d)["realises"]["x-link"].update(kinds=["nope"]),
     "ANNOT-07", 1, [S16, "'nope'"]),
    ("annot07-same-step", S16,
     lambda d: _realises(d)["realises"]["x-link"].update(kinds=["fr"], same_step_kinds=["api"]),
     "ANNOT-07", 1, ["same_step_kinds"]),
    ("annot08-context-no-lifecycle", S16, _plan_item_is_context_without_lifecycle,
     "ANNOT-08", 1, [S16, "lifecycle"]),
    ("annot08-no-scope", S04, lambda d: _fr_item(d)["properties"].pop("scope"), "ANNOT-08", 1, ["scope"]),
    ("annot08-no-scope-reason-rule", S04, lambda d: _fr_item(d).pop("allOf"),
     "ANNOT-08", 1, ["scopeReasonRule"]),
]


@pytest.mark.parametrize(
    ("schema", "edit", "code", "count", "texts"),
    [pytest.param(*case[1:], id=case[0]) for case in _EDIT_CASES],
)
def test_schema_edit_raises_the_annot_issue(mini_toolkit, edit_json, schema, edit, code, count, texts):
    edit_json(mini_toolkit, schema, edit)
    issues = _with(_lint(mini_toolkit), code)
    assert issues if count is None else len(issues) == count
    assert all(text in issues[0] for text in texts)
