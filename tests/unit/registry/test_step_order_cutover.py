"""The step-order cutover (WI-M3-16): ``tools/step_order.json`` is generated from the annotations.

The committed file is the output of ``registry-generate``; ``version``, ``steps``, ``policy``,
``coverage_thresholds`` and ``declared_edges`` are carried by hand inside it.  The differences
from the 1.1.1 hand file (``tests/fixtures/step_order/step_order_1.1.1.json``) are pinned here
edge by edge, so an unplanned annotation change that moves an edge fails a test.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from specdev_tools.core.registry import clear_shared_caches
from specdev_tools.registry.generate import run as registry_run
from specdev_tools.registry.step_order_gen import (
    build_step_order_document,
    declared_edge_pairs,
    derive_step_order,
    diff_against_hand,
)

_ROOT = Path(__file__).resolve().parents[3]
_COMMITTED = _ROOT / "tools" / "step_order.json"
_FIXTURE_1_1_1 = _ROOT / "tests" / "fixtures" / "step_order" / "step_order_1.1.1.json"

# (consumer, input) pairs the annotations derive and the 1.1.1 hand file lacks, with the
# x-link that causes each (schema file, field, target kind).
_ADDED_EDGES = {
    ("02", "00"): "02_system_sketch field 'assumes' kind 'assumption'",
    ("02a", "00"): "02a_delivery_baseline field 'assumes' kind 'assumption'",
    ("05", "00"): "05_interface_contracts field 'assumes' kind 'assumption'",
    ("06", "00"): "06_invariants field 'assumes' kind 'assumption'",
    ("07", "05"): "07_nfrs field 'constrains' kind 'api'",
    ("09", "06"): "09_impl_plan field 'schedules' kind 'invariant'",
    ("11", "00"): "11_redteam field 'assumes' kind 'assumption'",
    ("11", "02a"): "11_redteam field 'mitigated_by' kind 'gate'",
    ("11", "10"): "11_redteam field 'mitigated_by' kind 'rule'",
    ("12", "07"): "12_ci_gates field 'verifies' kind 'nfr'",
    ("14", "02a"): "14_roadmap field 'refines' kind 'environment'",
    ("14", "05"): "14_roadmap field 'refines' kind 'api'",
    ("14", "06"): "14_roadmap field 'refines' kind 'invariant'",
    ("14", "07"): "14_roadmap field 'refines' kind 'nfr'",
    ("14", "10"): "14_roadmap field 'refines' kind 'rule'",
}

# (consumer, input) pairs of the 1.1.1 hand file that no stored x-link carries: context reads
# of the prompts (03 reads 00-02 by label; 07 reads 02a and 03; every later step reads the
# steps whose artifacts it only cites).  The pairs of 16a are carried by declared_edges until M8.
# The ten pairs that name step 13a go with the step (M6c retires it).
_REMOVED_EDGES = {
    ("13a", "00"), ("13a", "01"), ("13a", "04"), ("13a", "05"), ("13a", "08"), ("13a", "12"), ("13a", "13"),
    ("14", "13a"), ("16a", "13a"), ("16b", "13a"),
    ("03", "00"), ("03", "01"), ("03", "02"),
    ("04", "03"), ("05", "03"),
    ("07", "02a"), ("07", "03"),
    ("08", "02"), ("08", "02a"),
    ("09", "01"), ("09", "08"),
    ("10", "02"), ("10", "09"),
    ("11", "01"),
    ("14", "02"),
    ("15", "02"), ("15", "02a"), ("15", "04"), ("15", "08"), ("15", "11"), ("15", "14"),
    ("16", "04"), ("16", "05"), ("16", "08"), ("16", "09"), ("16", "11"), ("16", "12"), ("16", "15"),
}

# W595 staleness reads ``downstream_consumers``: producer -> consumers that lose the context read.
_LOST_CONSUMERS = {
    "00": ["03", "13a"],
    "01": ["03", "09", "11", "13a"],
    "02": ["03", "08", "10", "14", "15"],
    "02a": ["07", "08", "15"],
    "03": ["04", "05", "07"],
    "04": ["13a", "15", "16"],
    "05": ["13a", "16"],
    "08": ["09", "13a", "15", "16"],
    "09": ["10", "16"],
    "11": ["15", "16"],
    "12": ["13a", "16"],
    "13": ["13a"],
    "13a": ["14", "16a", "16b"],
    "14": ["15"],
    "15": ["16"],
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _generate(out: Path) -> bytes:
    """Run ``registry-generate`` with every output under *out*'s folder; return the step order bytes."""
    clear_shared_caches()
    registry_run(
        str(_ROOT),
        str(out.parent / "reg.json"),
        str(out.parent / "ext.json"),
        step_order_out=str(out),
    )
    return out.read_bytes()


def _computed_diff() -> list:
    committed = _load(_COMMITTED)
    declared = declared_edge_pairs(committed)
    clear_shared_caches()
    derived = derive_step_order(str(_ROOT), declared)
    return diff_against_hand(derived, _load(_FIXTURE_1_1_1), declared)


def test_registry_generate_step_order_is_byte_deterministic(tmp_path):
    first = _generate(tmp_path / "a" / "step_order.json")
    second = _generate(tmp_path / "b" / "step_order.json")
    assert first == second == _COMMITTED.read_bytes()


def test_steps_is_topological_order_of_derived_plus_declared_edges():
    doc = _load(_COMMITTED)
    position = {s: i for i, s in enumerate(doc["steps"])}
    declared = declared_edge_pairs(doc)
    clear_shared_caches()
    derived = derive_step_order(str(_ROOT), declared)
    pairs = {(c, p) for c, meta in derived["step_metadata"].items() for p in meta["required_spec_inputs"]}
    assert pairs >= set(declared)
    assert [(c, p) for c, p in sorted(pairs) if position[p] >= position[c]] == []


def test_steps_contains_every_derived_step():
    doc = _load(_COMMITTED)
    clear_shared_caches()
    derived = derive_step_order(str(_ROOT), declared_edge_pairs(doc))
    assert set(derived["steps"]) <= set(doc["steps"])
    assert set(doc["step_metadata"]) == set(doc["downstream_consumers"]) == set(doc["steps"])


def test_expected_diff_list_is_pinned():
    diff = _computed_diff()
    added = {(d.consumer, d.input) for d in diff if d.kind == "missing_in_hand"}
    removed = {(d.consumer, d.input) for d in diff if d.kind == "extra_in_hand"}
    assert added == set(_ADDED_EDGES)
    assert removed == _REMOVED_EDGES
    assert (len(added), len(removed), len(diff)) == (15, 38, 53)


def test_w595_narrowing_lists_consumers_that_lose_a_context_read():
    hand = _load(_FIXTURE_1_1_1)["downstream_consumers"]
    generated = _load(_COMMITTED)["downstream_consumers"]
    lost = {
        producer: sorted(set(consumers) - set(generated.get(producer, [])))
        for producer, consumers in hand.items()
    }
    assert {p: c for p, c in lost.items() if c} == _LOST_CONSUMERS
    by_input: dict[str, list[str]] = {}
    for consumer, producer in sorted(_REMOVED_EDGES):
        by_input.setdefault(producer, []).append(consumer)
    assert by_input == _LOST_CONSUMERS


def test_declared_edges_09_14_and_14_16_present():
    declared = _load(_COMMITTED)["declared_edges"]
    assert ["09", "14"] in declared and ["14", "16"] in declared
    assert len({tuple(edge) for edge in declared}) == len(declared)
    assert all([p, "16a"] in declared for p in ("02a", "04", "05", "06", "07", "08", "11", "12", "15", "16"))
    consumers = _load(_COMMITTED)["downstream_consumers"]
    assert "14" in consumers["09"] and "16" in consumers["14"]


def test_build_step_order_document_keeps_hand_steps_and_declared_edges():
    hand = _load(_COMMITTED)
    derived = {
        "steps": ["00"],
        "step_metadata": {"00": {"required_spec_inputs": []}},
        "downstream_consumers": {"00": ["01"]},
    }
    doc = build_step_order_document(derived, hand)
    assert doc["steps"] == hand["steps"] and doc["declared_edges"] == hand["declared_edges"]
    assert set(doc["_notes"]) == {"downstream_consumers", "declared_edges", "step_metadata"}
    assert doc["step_metadata"]["01"] == {"required_spec_inputs": []}
    assert doc["downstream_consumers"]["00"] == ["01"] and doc["downstream_consumers"]["01"] == []


@pytest.mark.parametrize("declared", [None, "x", [["09"], ["09", 14], "09", ["09", "14", "16"]]])
def test_declared_edge_pairs_ignores_wrong_typed_values(declared):
    assert declared_edge_pairs({"declared_edges": declared}) == []


def test_declared_edge_pairs_swaps_producer_and_consumer():
    assert declared_edge_pairs({"declared_edges": [["09", "14"]]}) == [("14", "09")]


def _run_cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "registry-generate", "--repo-root", str(root), *args],
        capture_output=True, text=True, cwd=_ROOT / "tools",
    )


def _toolkit_copy(dest: Path) -> Path:
    """The schemas and tool data files of the toolkit, enough for ``registry-generate``."""
    shutil.copytree(_ROOT / "schema", dest / "schema")
    (dest / "tools").mkdir()
    for f in (_ROOT / "tools").glob("*.json"):
        shutil.copy(f, dest / "tools")
    return dest


def test_step_order_default_path_only_when_out_absent(tmp_path):
    root = _toolkit_copy(tmp_path / "tk")
    path = root / "tools" / "step_order.json"
    stale = _load(_COMMITTED)
    stale["step_metadata"]["06"]["required_spec_inputs"].append("01")
    stale_text = json.dumps(stale, sort_keys=True, indent=2) + "\n"
    path.write_text(stale_text)
    with_out = _run_cli(
        root, "--out", str(tmp_path / "reg.json"), "--extraction-paths-out", str(tmp_path / "ext.json")
    )
    assert with_out.returncode == 0, with_out.stderr
    assert path.read_text() == stale_text
    without_out = _run_cli(root)
    assert without_out.returncode == 0, without_out.stderr
    assert path.read_bytes() == _COMMITTED.read_bytes()


def test_ci_step_fails_on_stale_step_order(tmp_path):
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert '--step-order-out "$TMPDIR/step_order.json"' in ci
    assert 'diff -q "$TMPDIR/step_order.json" tools/step_order.json' in ci
    tampered = tmp_path / "tampered.json"
    doc = _load(_COMMITTED)
    doc["step_metadata"]["06"]["required_spec_inputs"].append("01")
    tampered.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n")
    regenerated = tmp_path / "regen" / "step_order.json"
    _generate(regenerated)
    stale = subprocess.run(["diff", "-q", str(regenerated), str(tampered)], capture_output=True)
    fresh = subprocess.run(["diff", "-q", str(regenerated), str(_COMMITTED)], capture_output=True)
    assert (stale.returncode, fresh.returncode) == (1, 0)
