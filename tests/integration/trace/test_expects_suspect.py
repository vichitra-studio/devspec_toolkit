"""An edit of an API error's ``protocol_status`` makes suspect the links that point at the error: a fixture's ``expects`` and an invariant's ``constrains``."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from unit.trace._lock_support import gap_providers, git_copy_of_example, run_on_example  # noqa: F401  (gap_providers is a fixture)
from unit.validation.graph_checks._example_support import edit_documents

ERROR = "err-password-reset-confirm-token-expired"
FIXTURES = ("fix-password-reset-expired-token", "fix-password-reset-reused-token")
INVARIANT = "inv-reset-token-single-use"


def _run(host: Path, *argv: str) -> str:
    code, out = run_on_example(host, *argv)
    assert code == 0, f"specdev {' '.join(argv)} exited {code}:\n{out}"
    return out


def _suspect(host: Path) -> tuple[list[str], set[tuple[str, str, str]]]:
    document = json.loads(_run(host, "stale", "--json"))
    nodes = [node for step in document["steps"] for node in step["suspect_nodes"]]
    return [node["node"] for node in nodes], {(node["node"], link["field"], link["target"]) for node in nodes for link in node["links"]}


def _set_inputs(spec: Path) -> None:
    """The error has a status, both fixtures expect it and the invariant constrains it, whatever the example holds."""
    def error(doc: dict[str, Any]) -> None:
        doc["apis"][0]["errors"][0]["protocol_status"] = 410

    def invariant(doc: dict[str, Any]) -> None:
        rule = doc["rules"][0]
        rule["constrains"] = [*(target for target in rule["constrains"] if target != ERROR), ERROR]

    def fixtures(doc: dict[str, Any]) -> None:
        for item in doc["fixtures"]:
            item["expects"] = [ERROR]

    edit_documents(spec, **{"05_interface_contracts.json": error, "06_invariants.json": invariant, "08_fixtures.json": fixtures})


def test_editing_the_status_of_an_error_makes_expects_and_constrains_suspect(tmp_path: Path, gap_providers: Any) -> None:
    host = git_copy_of_example(tmp_path / "host")
    _set_inputs(host / "spec")
    for node in (INVARIANT, *FIXTURES):  # the links the inputs add
        run_on_example(host, "attest", node, "--yes")
    for _round in range(10):  # a node that links to a suspect node is refused (E764): the next round takes it
        nodes, _links = _suspect(host)
        if not nodes:
            break
        for node in nodes:
            run_on_example(host, "attest", node, "--yes")
    assert _suspect(host) == ([], set())

    _run(host, "json", "patch", "--id", ERROR, ".protocol_status", "409")

    _nodes, links = _suspect(host)
    assert {(FIXTURES[0], "expects", ERROR), (FIXTURES[1], "expects", ERROR), (INVARIANT, "constrains", ERROR)} <= links
