"""The golden of the worked example under the graph checks (WI-M6b-13): DOC section 12, row by row, run through ``spec-check``.

The truth pinned here was measured by running the real command on a git copy of ``tests/fixtures/graph_example``
(``reports/M6b/WI-M6b-13.md``).  Each test pins ``(code, node id, owner)`` triples as data; a delta test says in one line what it
changes (the delta files are in ``tests/fixtures/graph_checks/deltas``) and which finding must appear or disappear.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import GRAPH_CHECK_DELTAS, apply_delta, attest, run_split
from specdev_tools.graph.build import build_graph
from specdev_tools.trace.lockfile import read_lock
from specdev_tools.validation.graph_checks.built import BuiltState, compute_built
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from specdev_tools.validation.graph_checks.cross_cutting import check_cross_cutting
from specdev_tools.validation.graph_checks.scaffold import check_scaffold_paths
from specdev_tools.validation.spec_check import run_spec_check_json
from unit.graph._synth import git
from unit.trace._lock_support import ROOT, git_copy_of_example

Triple = tuple[str, str, str]

GRAPH_CHECKS = ("no-dangling", "term-use", "verifier-rules", "cross-cutting", "refinement", "scaffold-paths", "seed-routes", "prose-ids")
SCAFFOLD_PATH = "src/routes/password-resets/confirm.ts"
SCAFFOLD_ROW = "scaffold-password-reset-confirm"
NFR = "nfr-latency-reset-email"
TASK = "task-implement-password-reset-confirm"
TC1, TC2 = "tc-confirm-expired-token", "tc-confirm-reused-token"
FX1, FX2 = "fix-password-reset-expired-token", "fix-password-reset-reused-token"

# --- what the example pins ------------------------------------------------------------------------------------------------

# Each node of the example that something uses, through a holder that is not a verifier (the use table).  A rename of any of
# them makes test_used_nodes_have_no_e740 fail on the id, not pass on an absent node.
USED = (
    "ac-password-reset-3", "inv-reset-token-single-use", "fr-password-reset", "cap-account-recovery", "scope-password-reset",
    "api-password-reset-confirm", "risk-reset-link-takeover", "contract-tests", "ci", "rule-contract-tests-on-every-pr",
    "con-staged-delivery", "asm-member-controls-email", "need-fewer-reset-tickets", "sh-support-lead", "conn-identity-to-mailrelay",
    "tp-argon2", "tp-mailrelay", "seg-registered-member", "metric-recovery-time", "identity-service", "term-reset-token",
)

# The 17 dangling nodes with their owners (R9: the design's table shows 11 "No use shown" rows; the fixture holds six more
# unused nodes), each with the part the example leaves out (DS H3).
DANGLING: dict[str, tuple[str, str]] = {
    "metric-reset-completion-rate": ("step:07", "no requirement derives from this metric: the NFR of the example derives from metric-recovery-time only"),
    "ac-password-reset-1": ("step:14", "no task criterion refines the criterion (the task has criteria for 3 only)"),
    "ac-password-reset-2": ("step:14", "no task criterion refines the criterion (the task has criteria for 3 only)"),
    "ac-password-reset-request-1": ("step:14", "the request requirement is not covered by any task criterion"),
    "ac-password-reset-request-2": ("step:14", "the request requirement is not covered by any task criterion"),
    "fr-password-reset-request": ("step:14", "none of its criteria is refined, so nothing below uses the requirement"),
    "err-password-reset-confirm-token-expired": ("step:14", "no task criterion refines the error (the API has its own fixture)"),
    "nfr-latency-reset-email": ("step:14", "no task criterion refines it; no fixture and no job verifies it (and a verifier is not a use)"),
    "threat-reset-token-replay": ("step:14", "no task criterion refines the threat"),
    "ec-token-at-expiry-second": ("step:14", "no task criterion refines the edge case"),
    "rule-spec-check-on-every-pr": ("step:14", "no criterion refines the rule and no job realises it"),
    "rule-security-review-of-token-handling": ("step:14", "no criterion refines the rule and no job realises it"),
    "dev": ("step:12", "no job of step 12 realises the environment"),
    "staging": ("step:12", "no job of step 12 realises the environment"),
    "prod": ("step:12", "no job of step 12 realises the environment"),
    "secret-mailrelay-api-key": ("step:12", "no job of step 12 uses the secret"),
    "secret-reset-token-signing-key": ("step:12", "no job of step 12 uses the secret"),
}
DANGLING_TRIPLES: list[Triple] = sorted(("E740", node, owner) for node, (owner, _part) in DANGLING.items())

MISSING_VERIFIERS: list[Triple] = sorted(
    ("E743", node, "step:08")
    for node in ("ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-request-1", "ac-password-reset-request-2", NFR)
)
NOT_MISSING = ("ac-password-reset-3", "api-password-reset-confirm", "inv-reset-token-single-use", "err-password-reset-confirm-token-expired")

BUILT_WHEN_CLOSED: dict[str, list[str]] = {
    "BUILT": ["ac-password-reset-3", "inv-reset-token-single-use"],
    "NOT_BUILT": [
        "ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-request-1", "ac-password-reset-request-2",
        "api-password-reset-confirm", "cap-account-recovery", "err-password-reset-confirm-token-expired", "fr-password-reset",
        "fr-password-reset-request", "nfr-latency-reset-email", "scope-password-reset",
    ],
    "PENDING_EVIDENCE": [
        "ci", "con-staged-delivery", "contract-tests", "dev", "ec-token-at-expiry-second", "prod", "risk-reset-link-takeover",
        "rule-contract-tests-on-every-pr", "rule-security-review-of-token-handling", "rule-spec-check-on-every-pr",
        "secret-mailrelay-api-key", "secret-reset-token-signing-key", "staging", "threat-reset-token-replay",
    ],
}

# --- helpers --------------------------------------------------------------------------------------------------------------


def _host(destination: Path, *deltas: str, attested: bool = True) -> Path:
    """A git copy of the example with *deltas* (graph check variants) applied; the lock follows them unless *attested* is false."""
    host = git_copy_of_example(destination)
    for name in deltas:
        apply_delta(host, name, folder=GRAPH_CHECK_DELTAS)
    if attested:
        attest(host)
    return host


def _checks(host: Path) -> dict[str, Any]:
    """The per-check results of the registered ``spec-check`` run on *host* (what ``--json`` prints under ``checks``)."""
    _errors, report = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host), spec_root=str(host / "spec"))
    return report["checks"]


def _triples(checks: dict[str, Any], name: str) -> list[Triple]:
    return sorted((f["code"], f["node_id"], f["owner"]) for f in checks[name]["findings"])


def _ids(checks: dict[str, Any], name: str, code: str) -> set[str]:
    return {node for found, node, _owner in _triples(checks, name) if found == code}


def _context(host: Path) -> GraphCheckContext:
    graph = build_graph(str(host / "spec"), str(ROOT))
    return GraphCheckContext.from_graph(graph, read_lock(str(host / "spec")), str(ROOT), git_root=str(host), spec_root=str(host / "spec"))


def _built(host: Path) -> dict[str, list[str]]:
    by_state: dict[str, list[str]] = defaultdict(list)
    for node_id, result in compute_built(_context(host)).items():
        if result.state is not BuiltState.IGNORED:
            by_state[result.state.name].append(node_id)
    return {state: sorted(ids) for state, ids in by_state.items()}


@pytest.fixture(scope="module")
def example_checks(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """The checks of the unchanged example, run once for the module (the tests read it, none changes it)."""
    return _checks(_host(tmp_path_factory.mktemp("example") / "host"))


# --- no-dangling (DOC 12 table, rows "used" and "No use shown") -----------------------------------------------------------


def test_used_nodes_have_no_e740(example_checks: dict[str, Any]) -> None:
    """Every node a holder uses is a node of the example and is not reported dangling."""
    graph = build_graph(str(ROOT / "tests" / "fixtures" / "graph_example" / "spec"), str(ROOT))
    assert [node_id for node_id in USED if node_id not in graph.by_id] == []
    assert _ids(example_checks, "no-dangling", "E740")  # the check ran: it has findings, none of them a used node
    assert set(USED).isdisjoint(_ids(example_checks, "no-dangling", "E740"))


def test_dangling_nodes_are_exactly_the_no_use_shown_rows_with_owners(example_checks: dict[str, Any]) -> None:
    """The 17 E740 of the example (R9), each with its owner step; the design's 11 rows are among them."""
    assert _triples(example_checks, "no-dangling") == DANGLING_TRIPLES
    design_rows = {
        "err-password-reset-confirm-token-expired", NFR, "threat-reset-token-replay", "ec-token-at-expiry-second",
        "rule-spec-check-on-every-pr", "rule-security-review-of-token-handling", "dev", "staging", "prod",
        "secret-mailrelay-api-key", "secret-reset-token-signing-key",
    }
    assert design_rows <= set(DANGLING)
    assert example_checks["no-dangling"]["status"] == "FAIL" and example_checks["no-dangling"]["error_count"] == 17


def test_every_dangling_node_has_its_left_out_part_named(example_checks: dict[str, Any]) -> None:
    """DS H3: the table above names, for each dangling node, the part the example leaves out; the message names the kind and the ways to use it."""
    assert all(part.strip() for _owner, part in DANGLING.values())
    findings = {f["node_id"]: f["message"] for f in example_checks["no-dangling"]["findings"]}
    assert set(findings) == set(DANGLING)
    assert all(" is not used by any node" in message and "link it" in message for message in findings.values())
    schedulable = {"ac-password-reset-1", "ac-password-reset-2", "ac-password-reset-request-1", "ac-password-reset-request-2", "fr-password-reset-request", NFR}
    assert {node_id for node_id, message in findings.items() if "schedule it" in message} == schedulable
    assert findings["metric-reset-completion-rate"].endswith("link it")
    assert all(message.endswith("or set scope later or out with a scope_reason") for node_id, message in findings.items() if node_id != "metric-reset-completion-rate")


def test_dangling_owners_are_unchanged_without_the_step_14_artifact_and_pending_in_the_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], example_checks: dict[str, Any]
) -> None:
    """DOC 13.2 row 3, 13.9 rows 3-4: delete 14_roadmap.json; the 17 E740 keep their owners, those of 12 and 14 are pending at step 11, none blocks."""
    half = _host(tmp_path / "half", attested=False)
    (half / "spec" / "14_roadmap.json").unlink()
    assert _triples(_checks(half), "no-dangling") == DANGLING_TRIPLES == _triples(example_checks, "no-dangling")

    flags = ["--repo-root", str(ROOT), "--spec-root", str(half / "spec"), "--git-root", str(half)]
    _code, out, _err = run_split(capsys, "spec-check", str(half / "spec"), *flags, "--step", "11", "--json")
    gate = json.loads(out)["step_gate"]
    assert gate["result"] == "clear" and gate["blocking"] == []
    pending = {step: {f["node_id"] for f in found if f["code"] == "E740"} for step, found in gate["pending"].items()}
    assert pending["12"] == {node for node, (owner, _p) in DANGLING.items() if owner == "step:12"}
    assert pending["14"] == {node for node, (owner, _p) in DANGLING.items() if owner == "step:14"}
    assert {f["node_id"] for f in gate["upstream_debt"] if f["code"] == "E740"} == {"metric-reset-completion-rate"}  # owner 07, before the gate
    # the criteria that used the fixtures are gone; FX1 is still used through its binding record (the record_users seam, WI-M7-08), FX2 has none
    assert {f["node_id"] for f in gate["pending"]["14"] if f["code"] == "E742"} == {FX2}


def test_scope_out_holder_produces_no_error_and_does_not_count_as_use(tmp_path: Path, example_checks: dict[str, Any]) -> None:
    """scope-sms-reset (scope out) has no finding; a need only it derives from is E740, and is not once the item is in scope."""
    assert "scope-sms-reset" not in {node for _code, node, _owner in _triples(example_checks, "no-dangling")}
    only_out = _checks(_host(tmp_path / "out", "sms_scope_sole_user"))
    assert _ids(only_out, "no-dangling", "E740") - _ids(example_checks, "no-dangling", "E740") == {"need-sms-reset"}
    in_scope = _checks(_host(tmp_path / "in", "sms_scope_sole_user", "sms_scope_in"))
    assert "need-sms-reset" not in _ids(in_scope, "no-dangling", "E740")


# --- built (DOC 12 table, "Built" rows) -----------------------------------------------------------------------------------


def test_built_states_after_the_milestone_is_done(tmp_path: Path) -> None:
    """Delta milestone_done: ac-3 and the invariant BUILT, the API, the FRs, the capability and the scope item NOT_BUILT, the rest PENDING_EVIDENCE; open, nothing is built."""
    assert _built(_host(tmp_path / "closed", "milestone_done")) == BUILT_WHEN_CLOSED
    still_open = _built(_host(tmp_path / "open"))
    assert "BUILT" not in still_open
    assert still_open["NOT_BUILT"] == sorted(BUILT_WHEN_CLOSED["NOT_BUILT"] + BUILT_WHEN_CLOSED["BUILT"])


def test_editing_the_criterion_text_makes_it_not_built(tmp_path: Path) -> None:
    """Delta criterion_text_edit (the lock still has the old hash): ac-3 is NOT_BUILT, the invariant stays BUILT; with the lock attested again it is BUILT."""
    edited = _built(_host(tmp_path / "edited", "milestone_done", "criterion_text_edit", attested=False))
    assert edited["BUILT"] == ["inv-reset-token-single-use"] and "ac-password-reset-3" in edited["NOT_BUILT"]
    attested_again = _built(_host(tmp_path / "again", "milestone_done", "criterion_text_edit"))
    assert attested_again["BUILT"] == BUILT_WHEN_CLOSED["BUILT"]


# --- verifier rules and refinement ---------------------------------------------------------------------------------------


def test_no_unused_verifier_in_the_example(tmp_path: Path, example_checks: dict[str, Any]) -> None:
    """FX1, FX2 and the job are all used (no E742); delta tc1_without_fixture leaves FX1 used through its binding record (``record_users``); with the record gone too, FX1 is unused: E742 on it alone."""
    assert _ids(example_checks, "verifier-rules", "E742") == set()
    host = _host(tmp_path / "v", "tc1_without_fixture")
    assert _ids(_checks(host), "verifier-rules", "E742") == set()
    (host / "spec" / "extras" / "verification" / "ver-password-reset-expired-token.json").unlink()
    variant = _checks(host)
    assert _triples(variant, "verifier-rules")[0] == ("E742", FX1, "step:14")
    assert _ids(variant, "verifier-rules", "E742") == {FX1}


def test_missing_verifiers_of_the_example(example_checks: dict[str, Any]) -> None:
    """Five E743 owned by step 08 (R3: none for the API error); none for ac-3, the API or the invariant."""
    assert _triples(example_checks, "verifier-rules") == MISSING_VERIFIERS
    assert set(NOT_MISSING).isdisjoint(_ids(example_checks, "verifier-rules", "E743"))


def test_nfr_verified_through_a_job_gives_no_e743_and_without_the_job_gives_e743(tmp_path: Path, example_checks: dict[str, Any]) -> None:
    """The example has no job that verifies the NFR: E743 on it; delta job_verifies_nfr clears that one and the other four stay (the job is not a use: E740 stays)."""
    assert NFR in _ids(example_checks, "verifier-rules", "E743")
    variant = _checks(_host(tmp_path / "job", "job_verifies_nfr"))
    assert _triples(variant, "verifier-rules") == [t for t in MISSING_VERIFIERS if t[1] != NFR]
    assert NFR in _ids(variant, "no-dangling", "E740")


def test_refinement_check_passes_tc1_fx1_and_tc2_fx2(tmp_path: Path, example_checks: dict[str, Any]) -> None:
    """TC1 names FX1 which verifies ac-3, TC2 names FX2 which verifies the invariant: no E745; delta tc1_without_fixture gives E745 for TC1 and none for TC2."""
    assert example_checks["refinement"]["status"] == "PASS" and _triples(example_checks, "refinement") == []
    variant = _checks(_host(tmp_path / "v", "tc1_without_fixture"))
    assert _triples(variant, "refinement") == [("E745", TC1, "step:14")]


def test_cross_cutting_e744_for_the_task_against_the_nfr_and_cleared_by_a_refining_criterion(tmp_path: Path, example_checks: dict[str, Any]) -> None:
    """One E744 on the confirm task, target the refinement of the NFR (owner 14); delta criterion_refines_nfr clears it, and E743 and E740 of the NFR with it."""
    assert _triples(example_checks, "cross-cutting") == [("E744", TASK, "step:14")]
    (error,) = check_cross_cutting(_context(_host(tmp_path / "plain")), "merge")
    assert (error.node_id, error.target, error.owner) == (TASK, f"refines->{NFR}", "step:14")
    cleared = _checks(_host(tmp_path / "refined", "criterion_refines_nfr"))
    assert _triples(cleared, "cross-cutting") == [] and _triples(cleared, "refinement") == []
    assert NFR not in _ids(cleared, "verifier-rules", "E743") | _ids(cleared, "no-dangling", "E740")


# --- seed routes ----------------------------------------------------------------------------------------------------------


def test_seed_routes_pass_on_the_example(example_checks: dict[str, Any]) -> None:
    """The seed is routed to 00 and 02 and nodes of both link it: no E747, E748 or E749; the other checks of this family are silent too."""
    for name in ("seed-routes", "term-use", "scaffold-paths", "prose-ids"):
        assert _triples(example_checks, name) == [], name


def test_derives_from_seed_from_an_unrouted_02a_node_gives_e749(tmp_path: Path) -> None:
    """Delta seed_link_from_02a: the environment dev (step 02a, not a route of the seed) derives from the seed: E749 on it, owner 02a."""
    checks = _checks(_host(tmp_path / "h", "seed_link_from_02a"))
    assert _triples(checks, "seed-routes") == [("E749", "dev", "step:02a")]


def test_derives_from_seed_from_a_04_node_gives_e701_not_e749(tmp_path: Path) -> None:
    """Delta seed_link_from_04: a requirement of step 04 cannot link a seed: E701 from the graph check, and no E749."""
    checks = _checks(_host(tmp_path / "h", "seed_link_from_04"))
    assert _triples(checks, "graph") == [("E701", "fr-password-reset", "step:04")]
    assert _triples(checks, "seed-routes") == []


# --- scaffold paths -------------------------------------------------------------------------------------------------------


def _track_scaffold_file(host: Path) -> None:
    path = host / SCAFFOLD_PATH
    path.parent.mkdir(parents=True)
    path.write_text("export const confirm = () => undefined;\n", encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "the confirm route")


def _e746(host: Path, mode: Any) -> list[tuple[str, str | None, str | None]]:
    return [(error.code, error.node_id, error.owner) for error in check_scaffold_paths(_context(host), mode)]


def test_a_context_built_from_a_graph_gives_the_e746_of_the_registered_check_and_has_seed_texts(tmp_path: Path) -> None:
    """``from_graph(..., git_root=...)`` is what a close or release gate builds: the same E746 as ``spec-check``, and the seed texts."""
    built = _host(tmp_path / "built", "milestone_done", "criterion_refines_api")
    context = _context(built)
    assert [(e.code, e.node_id, e.owner) for e in check_scaffold_paths(context, "merge")] == _triples(_checks(built), "scaffold-paths") != []
    assert context.git_root == str(built) and context.spec_root == str(built / "spec")
    assert context.seed_texts and all(context.seed_texts.values())
    assert _e746(built, "close") != [] and not GraphCheckContext.from_graph(context.graph, None, str(ROOT)).seed_texts


def test_scaffold_row_tracked_passes_and_removed_gives_e746_in_close_mode_and_in_merge_mode_only_when_the_api_is_built(tmp_path: Path) -> None:
    """Close mode checks every row; merge mode only a row whose API is built (delta milestone_done and criterion_refines_api build it)."""
    expected = [("E746", SCAFFOLD_ROW, "step:15")]
    open_host = _host(tmp_path / "open")
    assert _e746(open_host, "close") == expected  # the example tracks no src/ file
    assert _e746(open_host, "merge") == []  # the API is not built: the row is not read
    assert _triples(_checks(open_host), "scaffold-paths") == []

    built = _host(tmp_path / "built", "milestone_done", "criterion_refines_api")
    assert compute_built(_context(built))["api-password-reset-confirm"].state is BuiltState.BUILT
    assert _e746(built, "merge") == expected == _e746(built, "close")
    assert _triples(_checks(built), "scaffold-paths") == [("E746", SCAFFOLD_ROW, "step:15")]

    _track_scaffold_file(built)
    assert _e746(built, "close") == [] == _e746(built, "merge")
    git(built, "rm", "-q", SCAFFOLD_PATH)
    assert _e746(built, "close") == expected == _e746(built, "merge")
    git(built, "reset", "-q", "--hard", "HEAD")  # the file is tracked again
    assert _e746(built, "close") == []


def test_delta_ops_set_and_remove_change_exactly_the_path_they_name(tmp_path: Path) -> None:
    """The support ops: ``set`` puts a value at an object key or array position, ``remove`` deletes one; a path that is not there raises."""
    from integration._step_gate_support import DeltaError, _apply_op

    host = git_copy_of_example(tmp_path / "h")
    spec = host / "spec" / "12_ci_gates.json"
    before = json.loads(spec.read_text(encoding="utf-8"))
    _apply_op(host, {"op": "set", "file": "spec/12_ci_gates.json", "path": ["jobs", 0, "name"], "value": "Renamed"}, "spec")
    _apply_op(host, {"op": "remove", "file": "spec/12_ci_gates.json", "path": ["jobs", 0, "steps", 0]}, "spec")
    after = json.loads(spec.read_text(encoding="utf-8"))
    assert after["jobs"][0]["name"] == "Renamed" and after["jobs"][0]["steps"] == []
    assert {k: v for k, v in after["jobs"][0].items() if k not in ("name", "steps")} == {k: v for k, v in before["jobs"][0].items() if k not in ("name", "steps")}
    for bad in (["jobs", 5, "name"], ["jobs", "name"], ["nothing", "x"]):
        with pytest.raises(DeltaError):
            _apply_op(host, {"op": "remove", "file": "spec/12_ci_gates.json", "path": bad}, "spec")


def test_the_example_design_milestone_is_realised_through_containment(example_checks: dict[str, Any]) -> None:
    """The 09 milestone schedules ``fr-password-reset``; the 14 criteria refine a criterion of it: it is computed, not unrealised (ruling R17)."""
    from specdev_tools.validation.graph_checks.design_milestones import matching_milestones, unrealised_design_milestones, unrefined_scheduled

    context = GraphCheckContext.from_graph(build_graph(str(ROOT / "tests/fixtures/graph_example/spec"), str(ROOT)), None, str(ROOT))
    assert [design.id for design, _roadmap in matching_milestones(context)] == ["milestone-account-recovery"]
    assert unrealised_design_milestones(context) == []
    assert unrefined_scheduled(context) == []  # the FR is refined through one criterion; the scheduled risk is outside it (ruling R18)
