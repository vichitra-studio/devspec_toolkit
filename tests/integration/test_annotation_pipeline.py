"""End-to-end proof of the x-node / x-link annotation pipeline (WI-M1-10).

Runs the DOC section 12 worked-example shapes (``tests/fixtures/graph/mini_toolkit``) through
lint -> registry -> derived step order.  The resolver and the checks on spec data are M4.
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from specdev_tools.core.entry_key_registry import iter_nodes
from specdev_tools.core.registry import clear_shared_caches
from specdev_tools.registry.annotations import AnnotationError
from specdev_tools.registry.generate import generate_registry
from specdev_tools.registry.step_order_gen import derive_step_order

_ROOT = Path(__file__).parents[2]
_FIX = _ROOT / "tests" / "fixtures" / "graph"
_MINI = _FIX / "mini_toolkit"


@pytest.fixture(autouse=True)
def _fresh_caches():
    clear_shared_caches()
    yield
    clear_shared_caches()


def _toolkit(tmp_path: Path) -> Path:
    """Self-contained copy of the mini toolkit plus the real core schemas it references."""
    root = tmp_path / "mini"
    shutil.copytree(_MINI, root)
    for name in ("graph", "atoms", "collections"):
        shutil.copy(_ROOT / "schema" / "core" / f"{name}.schema.json", root / "schema" / "core")
    shutil.copy(_ROOT / "tools" / "step_order.json", root / "tools")
    shutil.copy(_ROOT / "schema" / "step_order.schema.json", root / "schema")
    return root


def _edit(root: Path, rel: str, fn) -> None:
    p = root / rel
    doc = json.loads(p.read_text())
    fn(doc)
    p.write_text(json.dumps(doc, indent=2) + "\n")


def _kinds(registry: dict) -> dict[str, dict]:
    """kind -> {step, path, entry}; nested arrays carry the full path."""
    out: dict[str, dict] = {}

    def walk(entry, step, parent):
        path = (parent + "[]" if parent else "") + entry["array_path"]
        out[entry["kind"]] = {"step": step, "path": path, "entry": entry}
        for nested in entry.get("nested", []):
            walk(nested, step, path)

    for fdoc in registry["registry"].values():
        for arr in fdoc["arrays"]:
            walk(arr, fdoc["step"], "")
    return out


@pytest.fixture
def pipeline(tmp_path):
    root = _toolkit(tmp_path)
    registry, _ = generate_registry(str(root))
    return root, registry, _kinds(registry)


def test_registry_emits_the_worked_example_kinds(pipeline):
    _, registry, kinds = pipeline
    assert {"fr", "criterion", "capability", "environment"} <= set(kinds)
    assert kinds["fr"]["path"] == ".functional_requirements"
    assert kinds["criterion"]["path"] == ".functional_requirements[].acceptance_criteria"
    assert kinds["capability"]["path"] == ".capabilities"
    assert kinds["environment"]["path"] == ".environments{}"
    assert kinds["environment"]["entry"]["map_keyed"] is True
    assert "id_field" not in kinds["environment"]["entry"]
    seeds = [e for e in registry["external_kinds"] if e["kind"] == "seed"]
    assert len(seeds) == 1 and seeds[0]["top_of_graph"] is True


def test_roles_equal_the_kind_role_table(pipeline):
    _, registry, kinds = pipeline
    table = json.loads((_FIX / "kind_role_table.json").read_text())["kinds"]
    for kind in ("fr", "criterion", "capability", "environment", "api", "plan-item", "ambiguity-item"):
        assert kinds[kind]["entry"]["role"] == table[kind]["role"], kind
    for kind in ("fr", "criterion", "capability", "environment", "api"):
        assert kinds[kind]["step"] == table[kind]["step"], kind
    assert table["seed"]["role"] is None and table["seed"]["top_of_graph"] is True
    (seed,) = [e for e in registry["external_kinds"] if e["kind"] == "seed"]
    assert "role" not in seed or seed["role"] is None


def test_shared_node_and_plan_item_shapes(pipeline):
    _, _, kinds = pipeline
    amb = kinds["ambiguity-item"]["entry"]
    assert amb["role"] == "record"
    assert amb["links"][0]["field"] == "about" and amb["links"][0]["kinds"] == "*"
    plan = kinds["plan-item"]["entry"]
    assert plan["id_field"] == "item_id"
    assert plan["links"][0]["field"] == "realises" and plan["links"][0]["kinds"] == ["fr"]


def test_derived_step_order(pipeline):
    root, _, _ = pipeline
    d = derive_step_order(str(root))
    meta = {s: m["required_spec_inputs"] for s, m in d["step_metadata"].items()}
    assert meta["01"] == []
    assert meta["04"] == ["01"]  # 01 -> 04
    assert d["steps"].index("01") < d["steps"].index("04")
    # the map-keyed 02a node has no outgoing edge: nothing is derived from it
    assert d["downstream_consumers"]["02a"] == []
    assert "02a" not in [i for ins in meta.values() for i in ins]


def test_cycle_between_04_and_05_fails_annot_20(tmp_path):
    root = _toolkit(tmp_path)

    def wrong(doc):
        link = doc["properties"]["functional_requirements"]["items"]["properties"]["derives_from"]["x-link"]
        link["kinds"] = ["capability", "api"]

    _edit(root, "schema/04_fr_list.schema.json", wrong)
    with pytest.raises(AnnotationError) as ei:
        derive_step_order(str(root))
    (issue,) = [i for i in ei.value.issues if i.startswith("ANNOT-20")]
    assert "04 -> 05 -> 04" in issue


def test_lint_runs_inside_registry_generate(tmp_path):
    root = _toolkit(tmp_path)
    shutil.copy(_FIX / "neg_map_beside_additional.schema.json", root / "schema" / "02a_delivery_baseline.schema.json")
    clear_shared_caches()
    with pytest.raises(AnnotationError) as ei:
        generate_registry(str(root))
    # node fields beside additionalProperties are not read: the item (the additionalProperties
    # value) is what fails, with ANNOT-08 for its missing lifecycle, and ANNOT-03 stays silent
    assert not any(i.startswith("ANNOT-03") for i in ei.value.issues)
    assert any(i.startswith("ANNOT-08") and "lifecycle" in i for i in ei.value.issues)


def test_worked_example_data_yields_both_ids(pipeline):
    _, _, kinds = pipeline
    data = {
        "functional_requirements": [
            {
                "fr_id": "fr-password-reset",
                "scope": "in",
                "statement": "The system shall let a registered member set a new password.",
                "acceptance_criteria": [
                    {"criterion_id": "ac-password-reset-3", "scope": "in", "text": "Expired token is rejected."}
                ],
                "derives_from": ["cap-account-recovery"],
            }
        ]
    }
    fr_id = kinds["fr"]["entry"]["id_field"]
    crit_id = kinds["criterion"]["entry"]["id_field"]
    frs = [n[fr_id] for n, _, _ in iter_nodes(data, kinds["fr"]["path"])]
    crits = [n[crit_id] for n, _, _ in iter_nodes(data, kinds["criterion"]["path"])]
    assert frs == ["fr-password-reset"]
    assert crits == ["ac-password-reset-3"]
    assert [n["derives_from"] for n, _, _ in iter_nodes(data, kinds["fr"]["path"])] == [["cap-account-recovery"]]


def test_map_keyed_environments_read_by_key(pipeline):
    _, _, kinds = pipeline
    data = {"environments": {"dev": {"config": {}}, "prod": {"config": {}}}}
    keys = [k for _, _, k in iter_nodes(data, kinds["environment"]["path"])]
    assert keys == ["dev", "prod"]
