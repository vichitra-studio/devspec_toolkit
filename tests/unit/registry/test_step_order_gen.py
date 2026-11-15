"""Tests for the annotation-derived step order (WI-M1-07)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from specdev_tools.core.registry import SchemaRegistry, clear_shared_caches
from specdev_tools.registry.annotations import AnnotationError
from specdev_tools.registry.generate import run as registry_run
from specdev_tools.registry.step_order_gen import (
    Disagreement,
    build_step_order_document,
    derive_step_order,
    diff_against_hand,
)

_ROOT = Path(__file__).resolve().parents[3]
_MINI = _ROOT / "tests" / "fixtures" / "graph" / "mini_toolkit"


@pytest.fixture(autouse=True)
def _fresh_caches():
    clear_shared_caches()
    yield
    clear_shared_caches()


def _kind_schema(step: str, kind: str, role: str, links: list[tuple]) -> dict:
    """One schema file holding one node kind and its x-link fields.

    links: (verb, kinds, same_step_kinds or None)
    """
    id_name = kind.replace("-", "_") + "_id"
    props: dict = {
        id_name: {"$ref": "vc:core:atoms#kebabId"},
        "lifecycle": {"$ref": "vc:core:graph#lifecycle"},
        "scope": {"$ref": "vc:core:graph#scope"},
        "scope_reason": {"$ref": "vc:core:graph#scopeReason"},
        "text": {"type": "string"},
    }
    for verb, kinds, same in links:
        xl: dict = {"kinds": kinds, "required": False}
        if same:
            xl["same_step_kinds"] = same
        props[verb] = {"type": "array", "items": {"$ref": "vc:core:atoms#kebabId"}, "x-link": xl}
    item: dict = {"type": "object", "properties": props, "required": [id_name]}
    if role != "record":
        item["allOf"] = [{"$ref": "vc:core:graph#scopeReasonRule"}]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"vc:t{step}-{kind}",
        "type": "object",
        "properties": {
            "things": {
                "type": "array",
                "x-node": {"kind": kind, "id": id_name, "role": role, "contract": ["text"]},
                "items": item,
            }
        },
    }


def _toolkit(tmp_path: Path, nodes: list[tuple]) -> Path:
    """nodes: (step, kind, role, links)."""
    root = tmp_path / "tk"
    (root / "tools").mkdir(parents=True)
    (root / "schema" / "core").mkdir(parents=True)
    shutil.copy(_ROOT / "tools" / "step_order.json", root / "tools")
    shutil.copy(_ROOT / "schema" / "step_order.schema.json", root / "schema")
    for name in ("graph", "atoms", "collections"):
        shutil.copy(_ROOT / "schema" / "core" / f"{name}.schema.json", root / "schema" / "core")
    reg = {
        "vc:core:atoms": "schema/core/atoms.schema.json",
        "vc:core:graph": "schema/core/graph.schema.json",
    }
    for step, kind, role, links in nodes:
        rel = f"schema/{step}_{kind.replace('-', '_')}.schema.json"
        doc = _kind_schema(step, kind, role, links)
        (root / rel).write_text(json.dumps(doc, indent=2) + "\n")
        reg[doc["$id"]] = rel
    (root / "tools" / "schema_registry.json").write_text(json.dumps(reg, indent=2) + "\n")
    return root


def _derive(root: Path, extra_edges=()):
    clear_shared_caches()
    return derive_step_order(str(root), extra_edges)


def _N(step, kind, links=(), role="obligation-system"):
    return (step, kind, role, list(links))


def test_edges_same_step_link_is_not_an_edge(tmp_path):
    root = _toolkit(tmp_path, [
        _N("01", "capability"),
        _N("04", "fr", [("derives_from", ["capability"], None), ("depends_on", ["fr"], ["fr"])]),
        _N("05", "api", [("derives_from", ["fr"], None)]),
        _N("06", "component", [("derives_from", ["api"], None)]),
    ])
    d = _derive(root)
    assert d["steps"] == ["01", "04", "05", "06"]
    meta = {s: m["required_spec_inputs"] for s, m in d["step_metadata"].items()}
    assert meta == {"01": [], "04": ["01"], "05": ["04"], "06": ["05"]}
    assert d["downstream_consumers"] == {"01": ["04"], "04": ["05"], "05": ["06"], "06": []}


def test_criterion_to_fr_in_same_step_needs_declaration_else_annot_21(tmp_path):
    root = _toolkit(tmp_path, [
        _N("04", "fr"),
        _N("04", "criterion", [("derives_from", ["fr"], None)]),
    ])
    # the criterion links into the same step without declaring it
    with pytest.raises(AnnotationError) as ei:
        _derive(root)
    assert any(i.startswith("ANNOT-21") for i in ei.value.issues)
    assert "same step" in ei.value.issues[0]


def test_two_step_cycle_annot_20_names_edges(tmp_path):
    root = _toolkit(tmp_path, [
        _N("04", "fr", [("derives_from", ["api"], None)]),
        _N("05", "api", [("derives_from", ["fr"], None)]),
    ])
    with pytest.raises(AnnotationError) as ei:
        _derive(root)
    (issue,) = ei.value.issues
    assert issue.startswith("ANNOT-20")
    assert "04 -> 05 -> 04" in issue
    assert "schema/04_fr.schema.json field 'derives_from' kind 'api'" in issue
    assert "schema/05_api.schema.json field 'derives_from' kind 'fr'" in issue


@pytest.mark.parametrize("a,b", [("02a", "03"), ("13", "13a"), ("16", "16a")])
def test_substep_pairs_cycle(tmp_path, a, b):
    root = _toolkit(tmp_path, [
        _N(a, "ka", [("derives_from", ["kb"], None)]),
        _N(b, "kb", [("derives_from", ["ka"], None)]),
    ])
    with pytest.raises(AnnotationError) as ei:
        _derive(root)
    assert f"{a} -> {b} -> {a}" in ei.value.issues[0]


def test_lone_forward_by_id_link_is_not_an_error(tmp_path):
    root = _toolkit(tmp_path, [
        _N("04", "fr", [("derives_from", ["api"], None)]),
        _N("05", "api"),
        _N("02a", "env", [("derives_from", ["term"], None)]),
        _N("03", "term"),
    ])
    d = _derive(root)
    assert d["steps"].index("05") < d["steps"].index("04")
    assert d["steps"].index("03") < d["steps"].index("02a")


def test_three_step_cycle_reported_once(tmp_path):
    root = _toolkit(tmp_path, [
        _N("04", "ka", [("derives_from", ["kb"], None)]),
        _N("05", "kb", [("derives_from", ["kc"], None)]),
        _N("06", "kc", [("derives_from", ["ka"], None)]),
    ])
    with pytest.raises(AnnotationError) as ei:
        _derive(root)
    cycles = [i for i in ei.value.issues if i.startswith("ANNOT-20")]
    assert len(cycles) == 1
    assert "04 -> 05 -> 06 -> 04" in cycles[0]


def test_no_edge_rules_wildcard_record_external_and_unknown(tmp_path):
    root = _toolkit(tmp_path, [
        _N("04", "fr", [("about", "*", None)]),
        _N("05", "note", [("derives_from", ["fr"], None)], role="record"),
        _N("06", "api", [("derives_from", ["seed"], None)]),
    ])
    d = _derive(root)
    assert d["steps"] == ["04", "05", "06"]
    assert all(m["required_spec_inputs"] == [] for m in d["step_metadata"].values())


def test_plan_holder_realises_edge_but_record_about_none(tmp_path):
    root = _toolkit(tmp_path, [
        _N("14", "milestone"),
        _N("16a", "plan-item", [("realises", ["milestone"], None)], role="plan"),
        _N("16b", "exec-record", [("about", "*", None)], role="record"),
    ])
    d = _derive(root)
    assert d["step_metadata"]["16a"]["required_spec_inputs"] == ["14"]
    assert d["step_metadata"]["16b"]["required_spec_inputs"] == []


def test_deterministic_and_ties_by_step_id(tmp_path):
    nodes = [_N("13a", "x"), _N("13", "y"), _N("02a", "z"), _N("02", "w"), _N("16", "v")]
    root = _toolkit(tmp_path, nodes)
    d1, d2 = _derive(root), _derive(root)
    assert d1 == d2
    assert d1["steps"] == ["02", "02a", "13", "13a", "16"]
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)


def test_extra_edge_shapes_order_and_is_not_a_disagreement(tmp_path):
    root = _toolkit(tmp_path, [_N("04", "fr"), _N("05", "api")])
    assert _derive(root)["steps"] == ["04", "05"]
    d = _derive(root, extra_edges=[("04", "05")])
    assert d["steps"] == ["05", "04"]
    assert d["step_metadata"]["04"]["required_spec_inputs"] == ["05"]
    hand = {"step_metadata": {"04": {"required_spec_inputs": []}, "05": {"required_spec_inputs": []}}}
    assert diff_against_hand(d, hand, extra_edges=[("04", "05")]) == []
    assert diff_against_hand(d, hand) == [Disagreement("missing_in_hand", "04", "05")]


def test_diff_against_hand_reports_planted_disagreements():
    generated = {
        "step_metadata": {
            "01": {"required_spec_inputs": []},
            "04": {"required_spec_inputs": ["01"]},
            "05": {"required_spec_inputs": ["04", "01"]},
        }
    }
    hand = {
        "step_metadata": {
            "04": {"required_spec_inputs": ["01"]},
            "05": {"required_spec_inputs": ["04", "03"]},
        },
        "downstream_consumers": {"04": ["05"]},
    }
    assert diff_against_hand(generated, hand) == [
        Disagreement("extra_in_hand", "05", "03"),
        Disagreement("missing_in_hand", "05", "01"),
    ]


def test_toolkit_without_kinds_derives_no_steps(tmp_path):
    root = _toolkit(tmp_path, [])
    assert _derive(root)["steps"] == []


def test_step_order_out_validates_against_schema_and_copies_policy(tmp_path):
    root = _toolkit(tmp_path, [
        _N("01", "capability"),
        _N("04", "fr", [("derives_from", ["capability"], None)]),
    ])
    before = (root / "tools" / "step_order.json").read_bytes()
    out = tmp_path / "out" / "step_order.generated.json"
    clear_shared_caches()
    registry_run(
        str(root),
        str(tmp_path / "reg.json"),
        str(tmp_path / "ext.json"),
        step_order_out=str(out),
    )
    doc = json.loads(out.read_text())
    hand = json.loads(before)
    assert doc["steps"] == ["01", "04"]
    assert doc["policy"] == hand["policy"] and doc["coverage_thresholds"] == hand["coverage_thresholds"]
    reg = SchemaRegistry(str(_ROOT))
    schema = json.loads((_ROOT / "schema" / "step_order.schema.json").read_text())
    Draft202012Validator(schema, registry=reg.to_referencing_registry()).validate(doc)
    assert (root / "tools" / "step_order.json").read_bytes() == before
    assert build_step_order_document(
        {"steps": ["01"], "step_metadata": {}, "downstream_consumers": {}}, hand
    )["version"] == hand["version"]


def test_without_step_order_out_nothing_extra_is_written(tmp_path):
    root = _toolkit(tmp_path, [_N("01", "capability")])
    clear_shared_caches()
    registry_run(str(root), str(tmp_path / "r.json"), str(tmp_path / "e.json"))
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ["e.json", "r.json"]
