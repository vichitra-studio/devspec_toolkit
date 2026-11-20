"""Tests for the annotation-derived step order (WI-M1-07)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from specdev_tools.core.registry import SchemaRegistry, clear_shared_caches
from specdev_tools.registry.annotations import (
    AnnotationDecls,
    AnnotationError,
    LinkDecl,
    NodeDecl,
)
from specdev_tools.registry.generate import run as registry_run
from specdev_tools.registry.step_order_gen import (
    Disagreement,
    StepOrderError,
    build_step_order_document,
    derive_from_decls,
    derive_step_order,
    diff_against_hand,
)

_ROOT = Path(__file__).resolve().parents[3]




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
        atom = "vc:core:graph#nodeId" if kinds == "*" or verb == "about" else "vc:core:atoms#kebabId"
        props[verb] = {"type": "array", "items": {"$ref": atom}, "x-link": xl}
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


def test_record_host_x_node_step_is_not_a_step_order_input(tmp_path):
    root = _toolkit(tmp_path, [_N("04", "fr")])
    doc = _kind_schema("99", "rec", "record", [])
    node = doc["properties"]["things"]["x-node"]
    node.update(step="99", files=["extras/rec/*.json"])
    (root / "schema" / "extras_rec.schema.json").write_text(json.dumps(doc))
    reg_path = root / "tools" / "schema_registry.json"
    reg = json.loads(reg_path.read_text())
    reg[doc["$id"]] = "schema/extras_rec.schema.json"
    reg_path.write_text(json.dumps(reg))
    assert "99" not in _derive(root)["steps"]


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
    assert doc["steps"] == hand["steps"]
    assert doc["step_metadata"]["04"]["required_spec_inputs"] == ["01"]
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


def test_record_holder_same_step_link_still_raises_annot_21(tmp_path):
    root = _toolkit(tmp_path, [
        _N("04", "fr"),
        _N("04", "note", [("derives_from", ["fr"], None)], role="record"),
    ])
    with pytest.raises(AnnotationError) as ei:
        _derive(root)
    assert any(i.startswith("ANNOT-21") and "'note'" in i for i in ei.value.issues)


def test_step_order_out_failure_writes_nothing(tmp_path):
    root = _toolkit(tmp_path, [])  # no annotated step: --step-order-out raises
    r, e, o = tmp_path / "r.json", tmp_path / "e.json", tmp_path / "o.json"
    clear_shared_caches()
    with pytest.raises(ValueError, match="no annotated step"):
        registry_run(str(root), str(r), str(e), step_order_out=str(o))
    assert not r.exists() and not e.exists() and not o.exists()


def _edit_hand(root: Path, edit) -> None:
    path = root / "tools" / "step_order.json"
    hand = json.loads(path.read_text())
    path.write_text(json.dumps(edit(hand)))


def _without(key: str):
    return lambda hand: {k: v for k, v in hand.items() if k != key}


@pytest.mark.parametrize(
    "edit, fragment",
    [(_without(key), key) for key in ("version", "steps", "policy", "coverage_thresholds")]
    + [
        (lambda hand: {**hand, "steps": None}, "steps"),
        (lambda hand: {**hand, "steps": 5}, "steps"),
        (lambda hand: {**hand, "steps": "01"}, "steps"),
        (lambda hand: {**hand, "steps": [1, 2]}, "steps"),
        (lambda hand: {**hand, "steps": []}, "steps"),
        (lambda hand: {**hand, "steps": hand["steps"] + hand["steps"][:1]}, "listed twice"),
        (lambda hand: {**hand, "version": 5}, "version"),
        (lambda hand: {**hand, "policy": None}, "policy"),
        (lambda hand: [hand], "JSON object"),
        (lambda hand: None, "JSON object"),
        (lambda hand: {**hand, "declared_edges": [["01", "01"]]}, "declared_edges: must be a list"),  # a self edge
        (lambda hand: {**hand, "declared_edges": [["01", "04"]], "steps": ["01"]},
         "declared_edges: names step.s. 04 that steps does not list"),
        (lambda hand: {**_without("declared_edges")(hand), "steps": ["01"]}, "annotated step.*04"),
        (lambda hand: {**hand, "declared_edges": "abc"}, "declared_edges"),
        (lambda hand: {**hand, "declared_edges": None}, "declared_edges"),
        (lambda hand: {**hand, "declared_edges": [["01"], [1, 2]]}, "declared_edges"),
    ],
)
def test_hand_kept_keys_that_cannot_be_used_fail_and_write_nothing(edit, fragment, tmp_path):
    root = _toolkit(tmp_path, [
        _N("01", "capability"),
        _N("04", "fr", [("derives_from", ["capability"], None)]),
    ])
    _edit_hand(root, edit)
    r, e, o = tmp_path / "r.json", tmp_path / "e.json", tmp_path / "o.json"
    clear_shared_caches()
    with pytest.raises(StepOrderError, match=fragment):
        registry_run(str(root), str(r), str(e), step_order_out=str(o))
    assert not r.exists() and not e.exists() and not o.exists()


def test_registry_alone_fails_when_steps_leaves_out_an_annotated_step(tmp_path):
    """Without ``step_order_out`` the registry would silently lose the step; the run fails and writes nothing."""
    root = _toolkit(tmp_path, [
        _N("01", "capability"),
        _N("04", "fr", [("derives_from", ["capability"], None)]),
    ])
    _edit_hand(root, lambda hand: {"steps": ["01"]})
    r, e = tmp_path / "r.json", tmp_path / "e.json"
    clear_shared_caches()
    with pytest.raises(StepOrderError, match="annotated step.*04"):
        registry_run(str(root), str(r), str(e))
    assert not r.exists() and not e.exists()


def test_registry_alone_needs_only_steps_of_the_hand_file(tmp_path):
    root = _toolkit(tmp_path, [_N("01", "capability")])
    _edit_hand(root, lambda hand: {"steps": hand["steps"]})
    clear_shared_caches()
    registry_run(str(root), str(tmp_path / "r.json"), str(tmp_path / "e.json"))
    assert (tmp_path / "r.json").exists()


def test_a_step_order_file_that_is_not_json_fails_and_writes_nothing(tmp_path):
    root = _toolkit(tmp_path, [_N("01", "capability")])
    (root / "tools" / "step_order.json").write_text("{")
    r, e = tmp_path / "r.json", tmp_path / "e.json"
    clear_shared_caches()
    with pytest.raises(StepOrderError, match="step_order.json"):
        registry_run(str(root), str(r), str(e))
    assert not r.exists() and not e.exists()


def test_cli_step_order_failure_is_a_clean_error(tmp_path):
    import subprocess
    import sys

    root = _toolkit(tmp_path, [])
    res = subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "registry-generate", "--repo-root", str(root),
         "--out", str(tmp_path / "r.json"), "--extraction-paths-out", str(tmp_path / "e.json"),
         "--step-order-out", str(tmp_path / "o.json")],
        capture_output=True, text=True, cwd=_ROOT / "tools",
    )
    assert res.returncode != 0
    assert "no annotated step" in res.stderr and "Traceback" not in res.stderr
    assert not (tmp_path / "r.json").exists()


def test_cli_annotation_error_prints_issue_list_without_traceback(tmp_path):
    import subprocess
    import sys

    root = _toolkit(tmp_path, [_N("04", "fr", [("depends_on", ["fr"], None)])])
    res = subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "registry-generate", "--repo-root", str(root),
         "--out", str(tmp_path / "r.json"), "--extraction-paths-out", str(tmp_path / "e.json"),
         "--step-order-out", str(tmp_path / "o.json")],
        capture_output=True, text=True, cwd=_ROOT / "tools",
    )
    assert res.returncode != 0
    assert "ANNOT-21" in res.stderr and "Traceback" not in res.stderr
    assert not (tmp_path / "o.json").exists()


# derive_from_decls on in-memory declarations: no toolkit on disk.

def _node(step: str, kind: str, role: str = "obligation-system") -> NodeDecl:
    file = f"schema/{step}_{kind}.schema.json"
    return NodeDecl(kind, {"id": "id", "role": role}, (f"vc:{kind}", "/x"), "/x", file, {}, f"vc:{kind}")


def _link(step: str, holder: str, kinds: list[str], same_step_kinds: list[str] | None = None) -> LinkDecl:
    value: dict = {"kinds": kinds}
    if same_step_kinds:
        value["same_step_kinds"] = same_step_kinds
    file = f"schema/{step}_{holder}.schema.json"
    return LinkDecl("derives_from", value, (f"vc:{holder}", "/l"), "/l", file, {}, f"vc:{holder}", {holder})


def _decls(nodes: list[NodeDecl], links: list[LinkDecl] = ()) -> AnnotationDecls:
    return AnnotationDecls(nodes=nodes, links=list(links), graph_present=True)


def test_from_decls_edge_orders_target_first():
    d = derive_from_decls(_decls([_node("01", "a"), _node("04", "b")], [_link("04", "b", ["a"])]))
    assert d["steps"] == ["01", "04"]
    assert d["step_metadata"]["04"] == {"required_spec_inputs": ["01"]}
    assert d["downstream_consumers"] == {"01": ["04"], "04": []}


def test_from_decls_cycle_raises_annot_20_with_legs():
    decls = _decls(
        [_node("04", "a"), _node("05", "b")],
        [_link("04", "a", ["b"]), _link("05", "b", ["a"])],
    )
    with pytest.raises(AnnotationError) as ei:
        derive_from_decls(decls)
    (issue,) = ei.value.issues
    assert issue.startswith("ANNOT-20") and "04 -> 05 -> 04" in issue


@pytest.mark.parametrize("allowed,raises", [([], True), (["a"], False)])
def test_from_decls_same_step_link_needs_declaration(allowed, raises):
    decls = _decls([_node("04", "a"), _node("04", "b")], [_link("04", "b", ["a"], allowed)])
    if not raises:
        assert derive_from_decls(decls)["steps"] == ["04"]
        return
    with pytest.raises(AnnotationError) as ei:
        derive_from_decls(decls)
    assert ei.value.issues[0].startswith("ANNOT-21")


def test_from_decls_extra_edge_adds_unknown_step_and_orders():
    decls = _decls([_node("04", "a")])
    d = derive_from_decls(decls, extra_edges=[("04", "02")])
    assert d["steps"] == ["02", "04"]
    assert d["step_metadata"]["04"] == {"required_spec_inputs": ["02"]}


def test_from_decls_cycle_through_extra_edge_names_it_as_extra():
    decls = _decls([_node("04", "a"), _node("05", "b")], [_link("04", "a", ["b"])])
    with pytest.raises(AnnotationError) as ei:
        derive_from_decls(decls, extra_edges=[("05", "04")])
    assert "(extra edge)" in ei.value.issues[0]


def test_from_decls_annot_21_is_raised_before_extra_edges_are_considered():
    decls = _decls([_node("04", "a"), _node("04", "b")], [_link("04", "b", ["a"])])
    with pytest.raises(AnnotationError) as ei:
        derive_from_decls(decls, extra_edges=[("04", "05"), ("05", "04")])
    assert ei.value.issues[0].startswith("ANNOT-21")
