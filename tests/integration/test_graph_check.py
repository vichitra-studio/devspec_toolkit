"""The ``graph`` check of ``spec-check`` end to end (WI-M4-04): which folder it reads and what it does without a registry."""
from __future__ import annotations

import json
from pathlib import Path

from specdev_tools.graph.check import run_graph_check
from specdev_tools.validation.spec_check import run_spec_check_json
from unit.graph._synth import ROOT, make_toolkit, run_specdev, write_spec

_API_DOC = {"apis": [{"api_id": "api-a", "derives_from": ["fr-ghost"]}]}
_FR_DOC = {"functional_requirements": []}


def _graph_findings(*args: str) -> list[dict[str, str]]:
    result = run_specdev("spec-check", *args, "--json")
    return json.loads(result.stdout)["checks"]["graph"]["findings"]


def test_graph_check_submodule_flags(tmp_path: Path) -> None:
    """With ``--spec-root`` the graph is built from the spec root, not from the spec folder given to the command."""
    host = tmp_path / "host"
    write_spec(host / "spec", {"05_interface_contracts.json": _API_DOC, "04_fr_list.json": _FR_DOC})
    write_spec(host / "elsewhere", {"05_interface_contracts.json": {"apis": [{"api_id": "api-b", "derives_from": ["fr-other"]}]},
                                    "04_fr_list.json": _FR_DOC})
    submodule_flags = ("--repo-root", str(ROOT), "--git-root", str(host))
    from_spec_root = _graph_findings(str(host / "elsewhere"), "--spec-root", str(host / "spec"), *submodule_flags)
    assert [(f["code"], f["node_id"], f["owner"]) for f in from_spec_root] == [("E700", "api-a", "step:05")]
    without_spec_root = _graph_findings(str(host / "elsewhere"), *submodule_flags)
    assert [(f["code"], f["node_id"]) for f in without_spec_root] == [("E700", "api-b")]


def test_missing_registry_is_one_e520_from_graph_check(tmp_path: Path) -> None:
    toolkit = make_toolkit(tmp_path / "toolkit")
    (toolkit / "tools" / "entry_key_registry.json").unlink()
    spec = write_spec(tmp_path / "spec", {"04_fr_list.json": _FR_DOC})
    errors = run_graph_check(str(spec), str(toolkit))
    assert [error.code for error in errors] == ["E520"]
    assert "entry_key_registry.json" in errors[0].message and "missing" in errors[0].message
    _errors, context = run_spec_check_json(str(toolkit), str(spec))
    graph = context["checks"]["graph"]
    assert [finding["code"] for finding in graph["findings"]] == ["E520"]
    assert context["checks"]["registry-check"]["status"] == "SKIP"


def test_graph_check_of_a_clean_spec_passes(tmp_path: Path) -> None:
    spec = write_spec(tmp_path / "spec", {"04_fr_list.json": _FR_DOC})
    assert run_graph_check(str(spec), str(ROOT)) == []
