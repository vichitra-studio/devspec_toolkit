"""The context pack of the worked example against the design document (WI-M4-09): ``specdev trace PWRESET_CONFIRM_EXPIRED_01
--recipe 16b`` of section 12.22, checked section by section as id sets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.recipes import build_pack, load_recipes, pack_to_dict
from unit.graph._synth import EXAMPLE_SPEC, ROOT

EXPECTED = ROOT / "tests" / "fixtures" / "graph" / "pack_16b_expected.json"
SCAFFOLD_POINTER = "15_scaffold.json"


@pytest.fixture(scope="module")
def expected() -> dict[str, Any]:
    return json.loads(EXPECTED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pack_json(expected: dict[str, Any]) -> dict[str, Any]:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    return pack_to_dict(build_pack(graph, load_recipes(str(ROOT)), expected["role"], expected["start"]))


def _ids(spec_file: str, id_field: str) -> set[str]:
    document = json.loads((EXAMPLE_SPEC / spec_file).read_text(encoding="utf-8"))
    return {item[id_field] for rows in document.values() if isinstance(rows, list) for item in rows if isinstance(item, dict) and id_field in item}


def test_pack_16b_matches_doc_12_22(expected: dict[str, Any], pack_json: dict[str, Any]) -> None:
    assert pack_json["role"] == "16b" and pack_json["start"]["id"] == expected["start"]
    found = {name: {row["id"] for row in rows} for name, rows in pack_json["sections"].items()}
    assert found == {name: set(ids) for name, ids in expected["sections"].items()}
    pins = {row["id"]: row["pin"] for row in pack_json["sections"]["third parties"]}
    assert pins == expected["pins"] == {"tp-argon2": "0.41.1", "tp-mailrelay": "api-v3"}
    assert all(row["pin"] in row["label"] for row in pack_json["sections"]["third parties"])


def test_pack_16b_universal_row_follows_the_fixture_files(pack_json: dict[str, Any]) -> None:
    universal = {row["id"] for row in pack_json["sections"]["universal"]}
    rules = _ids("10_governance.json", "rule_id")
    assert "rule-contract-tests-on-every-pr" in rules
    assert universal == rules | {"term-reset-token", SCAFFOLD_POINTER}
    assert "term-reset-token" in _ids("03_glossary.json", "term_id")
    scaffold = json.loads((EXAMPLE_SPEC / SCAFFOLD_POINTER).read_text(encoding="utf-8"))
    assert "interface_map" in scaffold
    pointer = next(row for row in pack_json["sections"]["universal"] if row["id"] == SCAFFOLD_POINTER)
    assert pointer["label"] == ".interface_map"


def test_pack_16b_leaves_out_what_the_doc_leaves_out(pack_json: dict[str, Any]) -> None:
    everything = {row["id"] for rows in pack_json["sections"].values() for row in rows}
    assert everything.isdisjoint({"identity-service", "seed-accounts", "seg-registered-member", "need-fewer-reset-tickets"})
    assert everything.isdisjoint({"fix-password-reset-reused-token", "term-reset-email-delivery-time-p95"})
    assert not any(name.startswith("ver-") for name in everything)
