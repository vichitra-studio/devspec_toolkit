"""End-to-end scenarios of the spec-graph design on the worked example, through the CLI (``_shared.md`` section 7.4).

Each test starts from a git copy of the example (``tests/fixtures/graph_example``) with its committed lock and runs
``specdev`` commands as an author would.

Scenarios 4 (seed edit), 5 (rename) and 6 (two-branch merge) are covered where they are tested closest to their code:
``test_seed_edit_suspects.py``, ``test_node_rename.py`` and ``test_merge_driver_git.py``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.trace.lockfile import read_lock
from specdev_tools.validation.spec_check import run_spec_check_json

from unit.graph._synth import ROOT
from unit.trace._lock_support import gap_providers, git_copy_of_example, run_on_example  # noqa: F401  (gap_providers is a fixture)
from unit.trace.test_suspects import CLOSED_HOLDERS, CLOSURE_OF_CRITERION_EDIT, CRITERION, Example

FR, SUCCESSOR = "fr-password-reset", "fr-account-recovery-link"
SUCCESSOR_CRITERION = "ac-account-recovery-link-1"
EDITED_TEXT = "Given a reset token that was issued for a different account, when it is submitted, then the request is rejected."
DAG_ORDER = ["05", "06", "07", "08", "09", "11", "14", "15", "16a"]
SUCCESSOR_FR = {
    "fr_id": SUCCESSOR,
    "priority": "must-have",
    "scope": "in",
    "statement": "The system shall let a member sign in with a magic link or recover access with a reset link.",
    "acceptance_criteria": [
        {"criterion_id": SUCCESSOR_CRITERION, "scope": "in", "text": "Given a registered member, when a magic link is requested, then a single-use sign-in link is emailed to the account address."},
        {"criterion_id": "ac-account-recovery-link-2", "scope": "in", "text": "Given a magic link that was already used, when it is opened again, then the sign-in is refused."},
    ],
    "derives_from": ["cap-account-recovery"],
    "capability_ref": {"id": "cn:project:capability:account-recovery", "kind": "capability", "version": "1.0.0"},
    "replaces": [FR],
}


@pytest.fixture
def host(tmp_path: Path, gap_providers: Any) -> Example:
    """A git copy of the example, with no coverage-gap provider registered (the role gaps of the partial example are not the subject here)."""
    return Example(git_copy_of_example(tmp_path / "host"))


def _run(host: Example, *argv: str, code: int = 0) -> str:
    status, out = run_on_example(host.host, *argv)
    assert status == code, f"specdev {' '.join(argv)} exited {status}:\n{out}"
    return out


def _findings(host: Example, check: str) -> list[dict[str, Any]]:
    _errors, context = run_spec_check_json(str(ROOT), str(host.spec), git_root=str(host.host))
    return context["checks"][check].get("findings", [])


def _stale(host: Example) -> dict[str, Any]:
    return json.loads(_run(host, "stale", "--json"))


def _suspect_links(document: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {(node["node"], link["field"], link["target"]) for step in document["steps"] for node in step["suspect_nodes"] for link in node["links"]}


def _add_successor_fr(host: Example) -> None:
    """The example's FR list needs at least two FRs (``minItems``), so a third one comes first: the successor of the FR that is retired."""
    out = _run(host, "json", "insert", "--step", "04", ".functional_requirements", json.dumps(SUCCESSOR_FR))
    assert "lock entry written: fr-account-recovery-link.derives_from -> cap-account-recovery" in out


# --- scenario 1: DOC 13.1, an upstream criterion changes --------------------------------------------------------------------

def test_scenario_upstream_criterion_change_is_replayed_step_by_step_to_a_clean_check(host: Example) -> None:
    assert _findings(host, "trace-lock") == []
    out = _run(host, "json", "patch", "--id", CRITERION, ".text", json.dumps(EDITED_TEXT))
    assert "newly suspect: 21 links (step 05: 2, step 06: 2, step 07: 1, step 08: 3, step 09: 1, step 11: 6, step 14: 4, step 15: 1, step 16a: 1)" in out

    listing = _stale(host)
    assert [step["step"] for step in listing["steps"]] == DAG_ORDER
    assert _suspect_links(listing) == CLOSURE_OF_CRITERION_EDIT
    assert {finding["code"] for finding in _findings(host, "trace-lock")} == {"E763"}

    # refused before allowed: the task criterion links the fixture, which is itself a suspect node until it is attested
    refused = _run(host, "attest", "tc-confirm-expired-token", code=1)
    assert "E764" in refused and "fix-password-reset-expired-token" in refused

    for step in DAG_ORDER:
        assert "attest: wrote" in _run(host, "attest", "--step", step, "--yes")
    assert _run(host, "stale") == "stale: no pending replay\n"
    assert _findings(host, "trace-lock") == []
    assert [finding for finding in _findings(host, "graph") if finding["code"] in {"E761", "E700"}] == []
    # the next attest has nothing to do: the lock is current
    assert _run(host, "attest", "--step", "05").strip() == "attest: nothing to attest"


# --- scenario 2: DOC 13.3, a node is retired and replaced -------------------------------------------------------------------

def _repointed(host: Example, holder: str, field: str, new: dict[str, str]) -> str:
    """The JSON value of *holder*'s *field* with each target that is a key of *new* swapped for its value."""
    node = build_graph(str(host.spec), str(ROOT)).by_id[holder]
    targets = [new.get(link.target, link.target) for link in node.links if link.field == field]
    return json.dumps(targets)


def test_scenario_retire_and_replace_leaves_resolver_errors_until_the_holders_repoint(host: Example) -> None:
    _add_successor_fr(host)
    deleted = _run(host, "json", "delete", "--id", FR)
    assert "lock entry removed: fr-password-reset.derives_from -> cap-account-recovery" in deleted
    assert "now broken (9 links point at the deleted node)" in deleted
    assert not any(entry.source == FR for entry in read_lock(str(host.spec)).entries)

    broken = [finding for finding in _findings(host, "graph") if finding["code"] == "E700"]
    holders = {finding["node_id"]: finding["owner"] for finding in broken}
    assert holders == {
        "api-password-reset-confirm": "step:05", "err-password-reset-confirm-token-expired": "step:05",
        "inv-reset-token-single-use": "step:06", "nfr-latency-reset-email": "step:07", "fix-password-reset-expired-token": "step:08",
        "milestone-account-recovery": "step:09", "ec-token-at-expiry-second": "step:11", "tc-confirm-expired-token": "step:14",
    }
    assert not {finding["code"] for finding in _findings(host, "trace-lock")} & {"E762", "E760"}

    swap = {FR: SUCCESSOR, CRITERION: SUCCESSOR_CRITERION}
    for holder, field in (
        ("api-password-reset-confirm", "derives_from"), ("err-password-reset-confirm-token-expired", "derives_from"),
        ("inv-reset-token-single-use", "constrains"), ("nfr-latency-reset-email", "constrains"),
        ("fix-password-reset-expired-token", "verifies"), ("milestone-account-recovery", "schedules"),
        ("ec-token-at-expiry-second", "mitigated_by"), ("tc-confirm-expired-token", "refines"),
    ):
        written = _run(host, "json", "patch", "--id", holder, f".{field}", _repointed(host, holder, field, swap))
        assert "lock entry written:" in written and "lock entry removed:" in written, written

    assert [finding for finding in _findings(host, "graph") if finding["code"] in {"E700", "E761"}] == []
    stale_targets = {entry.target for entry in read_lock(str(host.spec)).entries}
    assert FR not in stale_targets and CRITERION not in stale_targets


# --- scenario 3: DOC 13.4, a closed milestone whose built node changes or is deleted --------------------------------------------

def test_scenario_closed_milestone_is_outdated_not_suspect_and_a_deleted_refines_target_is_no_error(host: Example) -> None:
    """Since M7 (WI-M7-09) a deleted target of a closed criterion's `refines` is no E700: the resolver leaves a closed criterion's links alone."""
    _add_successor_fr(host)
    host.close_milestone()
    _run(host, "json", "patch", "--id", CRITERION, ".text", json.dumps(EDITED_TEXT))

    holders = {node["node"] for step in _stale(host)["steps"] for node in step["suspect_nodes"]}
    assert not holders & CLOSED_HOLDERS and holders
    assert [finding for finding in _findings(host, "trace-lock") if finding.get("node_id") in CLOSED_HOLDERS] == []

    matrix = json.loads(_run(host, "coverage", "--by", "fr", "--json"))
    criterion = next(item for entry in matrix["by_fr"] for item in entry["criteria"] if item["id"] == CRITERION)
    assert criterion["refined"] == "stale"
    closed = next(link for group in criterion["groups"] for link in group["links"] if link["node"] == "tc-confirm-expired-token")
    assert (closed["current"], closed["historical"]) == (False, True)

    refused = _run(host, "attest", "tc-confirm-expired-token", "--yes", code=1)
    assert "E765" in refused

    _run(host, "json", "delete", "--id", FR)
    graph_findings = _findings(host, "graph")
    assert [finding for finding in graph_findings if finding["code"] == "E700" and finding["node_id"] == "tc-confirm-expired-token"] == []
    assert not {finding["code"] for finding in _findings(host, "trace-lock") if finding.get("node_id") == "tc-confirm-expired-token"}
    entry = ("tc-confirm-expired-token", "refines", CRITERION)
    assert entry in {item.key for item in read_lock(str(host.spec)).entries}

    _run(host, "node", "status", "tc-confirm-expired-token", "not_applicable")
    assert [finding for finding in _findings(host, "graph") if finding.get("node_id") == "tc-confirm-expired-token"] == []
    assert entry in {item.key for item in read_lock(str(host.spec)).entries}  # kept and ignored
    assert not [finding for finding in _findings(host, "trace-lock") if finding["code"] == "E762"]
