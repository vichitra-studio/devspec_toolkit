"""The context pack of the worked example against the design document (WI-M4-09): ``specdev trace PWRESET_CONFIRM_EXPIRED_01
--recipe 16b`` of section 12.22, checked section by section as id sets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.graph.recipes import PARENT_VIA, build_pack, load_recipes, pack_to_dict, render_text
from unit.graph._synth import EXAMPLE_SPEC, ROOT, copy_example, graph_check, load_doc, run_specdev, write_json

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
    found = {
        name: {
            "members": {row["id"] for row in rows if not row["via"].startswith(PARENT_VIA)},
            "containers": {row["id"] for row in rows if row["via"].startswith(PARENT_VIA)},
        }
        for name, rows in pack_json["sections"].items()
    }
    assert found == {name: {part: set(ids) for part, ids in parts.items()} for name, parts in expected["sections"].items()}
    # DOC 12.22: the criterion in "core criteria" sits in its task and milestone, "obligations" holds the criterion
    # in its FR, and "lineage" is exactly the three ids of its chain.
    assert expected["sections"]["core criteria"]["members"] == ["tc-confirm-expired-token"]
    assert expected["sections"]["obligations"] == {"members": ["ac-password-reset-3"], "containers": ["fr-password-reset"]}
    assert found["lineage"] == {
        "members": {"fr-password-reset", "cap-account-recovery", "scope-password-reset"},
        "containers": set(),
    }
    pins = {row["id"]: row["pin"] for row in pack_json["sections"]["third parties"]}
    assert pins == expected["pins"] == {"tp-argon2": "0.41.1", "tp-mailrelay": "api-v3"}
    assert all(row["pin"] in row["label"] for row in pack_json["sections"]["third parties"])


def test_pack_16b_text_puts_the_containers_after_their_member(expected: dict[str, Any]) -> None:
    graph = build_graph(str(EXAMPLE_SPEC), str(ROOT))
    lines = render_text(build_pack(graph, load_recipes(str(ROOT)), expected["role"], expected["start"])).splitlines()
    rows = {line.split("  ")[0].strip(): line.split("  ", 1)[1].strip() for line in lines[1:] if line[:1].isalpha()}
    assert rows["core criteria"] == "tc-confirm-expired-token (ms-account-recovery, task-implement-password-reset-confirm)"
    assert rows["obligations"] == "ac-password-reset-3 (fr-password-reset)"
    assert rows["lineage"] == "scope-password-reset, cap-account-recovery, fr-password-reset"


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


# --- the worked example under the commands and the mutations of the test plan (section 7, items 3 and 6) ------------

_CAPABILITY = "cap-account-recovery"
_FR = "fr-password-reset"


def _flags(spec: Path) -> list[str]:
    return ["--repo-root", str(ROOT), "--spec-root", str(spec), "--git-root", str(spec.parent)]


def _step_order() -> list[str]:
    return json.loads((ROOT / "tools" / "step_order.json").read_text(encoding="utf-8"))["steps"]


def test_candidates_for_a_kind_offer_the_capability_and_nothing_from_step_05_on(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")
    result = run_specdev("node", "candidates", "--kind", "fr", "--field", "derives_from", *_flags(spec), "--json")
    assert result.returncode == 0, result.stderr
    offered = json.loads(result.stdout)["candidates"]
    assert _CAPABILITY in {item["id"] for item in offered}
    assert {item["kind"] for item in offered} == {"capability"}
    order = _step_order()
    assert all(order.index(item["step"]) < order.index("05") for item in offered)


def test_candidates_for_a_node_leave_out_the_target_it_already_links(tmp_path: Path) -> None:
    """PD-10: the FR already derives from the only capability, so there is nothing left to offer."""
    spec = copy_example(tmp_path / "spec")
    assert _CAPABILITY in {link.target for link in build_graph(str(spec), str(ROOT)).by_id[_FR].links}
    result = run_specdev("node", "candidates", "--for", _FR, "--field", "derives_from", *_flags(spec))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0 candidates for fr.derives_from (showing 0)"
    assert json.loads(run_specdev("node", "candidates", "--for", _FR, "--field", "derives_from", *_flags(spec), "--json").stdout)["total"] == 0


def test_deleting_a_capability_is_e700_owned_by_the_step_of_the_fr(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")
    document = load_doc(spec, "01_capabilities.json")
    document["capabilities"] = [item for item in document["capabilities"] if item["capability_id"] != _CAPABILITY]
    write_json(spec, "01_capabilities.json", document)
    findings = graph_check(spec)["findings"]
    broken = [finding for finding in findings if finding["code"] == "E700" and finding["node_id"] == _FR]
    assert [(finding["owner"], finding["file"]) for finding in broken] == [("step:04", "04_fr_list.json")]
    assert f"target '{_CAPABILITY}'" in broken[0]["message"] and "no node has that id" in broken[0]["message"]
    assert {finding["code"] for finding in findings} == {"E700"}


def test_deprecating_a_capability_is_no_graph_finding(tmp_path: Path) -> None:
    spec = copy_example(tmp_path / "spec")
    done = run_specdev("node", "status", _CAPABILITY, "deprecated", *_flags(spec))
    assert done.returncode == 0, done.stderr
    assert load_doc(spec, "01_capabilities.json")["capabilities"][0]["lifecycle"] == "deprecated"
    check = graph_check(spec)
    assert (check["status"], check["findings"]) == ("PASS", [])
