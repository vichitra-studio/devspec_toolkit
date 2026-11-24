"""The legacy binding pass (WI-M10-17): ``align propose --kind bindings`` and ``align bind-legacy``.

Every test runs on a copy of the migrated mini host (the whole script chain registered at HEAD ran on it).  Its fixtures, the
commands its plans recorded and the invented CI workflow of ``tests/fixtures/migration/legacy_bindings`` are the shapes; a
test that needs another shape edits its own copy.  The properties asserted are those of the pass's own output, not counts
of the chain.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import refusal
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.lifecycle.anchor_store import AnchorState, read_statuses, write_legacy_close
from specdev_tools.migration import legacy_bindings
from specdev_tools.migration.proposers import KINDS
from specdev_tools.migration.registry import discover_scripts
from specdev_tools.migration.proposers.bindings import (
    CERTAIN,
    JUDGEMENT,
    MANUAL,
    BindGroup,
    BindingsPlan,
    plan_bindings,
    read_command,
)
from specdev_tools.graph.build import build_graph
from specdev_tools.migration.worklist import WORKLIST_FILE
from specdev_tools.proof.proof import proof_errors
from specdev_tools.proof.validity import ProofContext
from specdev_tools.verify.records import records_folder
from specdev_tools.validation.spec_check import run_spec_check
from specdev_tools.validation.merge_gate import MERGE_BINDINGS, closed_by_branch
from specdev_tools.validation.spec_check import run_spec_check_json

from ._bindings_support import FIXTURES, RECORDS, align, edit_capture, edit_json, fixture_of, fresh, records, run_line, tree_of
from ._support import git, migrate, REAL_ROOT, tree_digest

FEE = "fix-late-fee-two-days"
DESK = "fix-checkout-conflict"
TWICE = "fix-reserve-twice"
HAPPY = "fix-reserve-happy"
SEARCH = "fix-search-returns-matches"
RETURN = "fix-return-closes-loan"
JEST_FEE = "npx jest tests/fee.spec.ts"
RESERVATIONS = "npm test -- reservations"


@pytest.fixture(scope="module")
def migrated(tmp_path_factory) -> Path:
    host, _toolkit, _report = migrate(tmp_path_factory.mktemp("legacy_bindings"))
    return host


@pytest.fixture
def host(migrated, tmp_path) -> Path:
    return fresh(migrated, tmp_path)


@pytest.fixture
def ci_host(migrated, tmp_path) -> Path:
    """The host with the invented CI workflow and the test file it names."""
    return fresh(migrated, tmp_path, overlay=True)


def plan_of(host: Path) -> BindingsPlan:
    return plan_bindings(tree_of(host))


def group_of(plan: BindingsPlan, commands: str) -> BindGroup:
    return next(group for group in plan.groups if " && ".join(group.commands) == commands)


def verifies(host: Path, fixture: str, *ids: str) -> None:
    def change(data: dict) -> None:
        entry = next(f for f in data["fixtures"] if f["fixture_id"] == fixture)
        entry["verifies"] = [*entry.get("verifies", []), *ids]

    edit_json(host, FIXTURES, change)


def printed_lines(output: str) -> list[str]:
    return [line.strip() for line in output.splitlines() if line.strip().startswith("specdev verify bind")]


def classes_by_fixture(plan: BindingsPlan) -> dict[str, str]:
    found = {member.fixture: group.category for group in plan.groups for member in group.members}
    found.update({single.fixture: single.category for single in plan.singles})
    return found


# --- grouping and classes ------------------------------------------------------------------------------------------------


def test_fixtures_sharing_one_command_form_one_group(host):
    verifies(host, HAPPY, "api-reserve-create")
    plan = plan_of(host)
    shared = group_of(plan, RESERVATIONS)
    assert [member.fixture for member in shared.members] == [HAPPY, TWICE]
    assert len({group.commands for group in plan.groups}) == len(plan.groups)
    assert {fixture for group in plan.groups for member in group.members for fixture in [member.fixture]}.isdisjoint(single.fixture for single in plan.singles)


def test_the_classes_of_the_mini_host_follow_what_the_legacy_record_shows(host):
    assert classes_by_fixture(plan_of(host)) == {FEE: CERTAIN, DESK: JUDGEMENT, TWICE: JUDGEMENT, HAPPY: JUDGEMENT, SEARCH: JUDGEMENT, RETURN: MANUAL}


def test_a_deferred_or_dropped_plan_item_is_not_a_source_of_a_command(host):
    plan = plan_of(host)
    assert all("tests/import.spec.ts" not in " ".join(group.commands) and "waitlist" not in " ".join(group.commands) for group in plan.groups)
    evidence = next(member.evidence for group in plan.groups for member in group.members if member.fixture == SEARCH)
    assert "tests/import.spec.ts" in evidence and "deferred or dropped" in evidence
    assert group_of(plan, f"npx jest tests/catalog.spec.ts && npm test -- catalog-search").members[0].lines == ()


def test_a_sentence_is_no_command_and_becomes_the_reason_of_a_manual_fixture(host):
    edit_capture(host, "FEE_CALC_01", legacy_linked_test_expectation="two days late owes one hundred cents on the loan screen")
    edit_capture(host, "FEE_ENDPOINT_01", legacy_linked_test_expectation=None)
    single = next(single for single in plan_of(host).singles if single.fixture == FEE)
    assert single.category == MANUAL and "one hundred cents" in single.proposal


def test_a_ci_line_that_names_a_word_of_the_fixture_is_a_candidate_never_certain(ci_host):
    plan = plan_of(ci_host)
    group = group_of(plan, "pytest tests/test_return.py -q")
    assert [member.fixture for member in group.members] == [RETURN]
    assert group.category == JUDGEMENT and "CI workflow" in group.why
    assert ".github/workflows/ci.yml, job test, step 3" in group.members[0].evidence
    assert classes_by_fixture(plan)[FEE] == CERTAIN, "a CI line is not a source for a fixture whose plan names a command"
    assert all("specdev" not in " ".join(g.commands) for g in plan.groups)


def test_a_path_the_repository_does_not_track_is_not_certain(host):
    edit_capture(host, "FEE_CALC_01", legacy_linked_test_expectation="npx jest tests/missing.spec.ts")
    group = group_of(plan_of(host), "npx jest tests/missing.spec.ts")
    assert group.category == JUDGEMENT and "does not track tests/missing.spec.ts" in group.why


def test_a_fixture_that_verifies_no_node_proves_nothing_and_is_not_grouped(host):
    single = next(single for single in plan_of(host).singles if single.fixture == HAPPY)
    assert single.category == JUDGEMENT and "verifies no node" in single.reason


def test_bound_fixture_without_command_is_bound(host):
    assert classes_by_fixture(plan_of(host))[RETURN] == MANUAL
    code, _out, err = run_line(host, f"specdev verify bind {RETURN} --command 'npx jest tests/return.spec.ts' --guard 'tests/return\\.spec\\.ts'")
    assert code == 0, err
    plan = plan_of(host)
    assert RETURN in plan.bound and RETURN not in classes_by_fixture(plan)


# --- guards --------------------------------------------------------------------------------------------------------------


def test_each_proposed_guard_is_an_escaped_regex_that_compiles(host):
    plan = plan_of(host)
    guards = [group.guard for group in plan.groups if group.guard]
    assert guards
    for group in plan.groups:
        if group.guard and len(group.commands) == 1 and (paths := read_command(group.commands[0], None).paths):
            assert group.guard == re.escape(paths[0])
            assert re.compile(group.guard, re.MULTILINE).search(f"PASS {paths[0]}")


def test_a_path_with_regex_characters_gives_a_guard_that_matches_it_literally():
    path = "tests/a+b.spec.ts"
    reading = read_command(f"npx jest '{path}'", frozenset({path}))
    assert reading.certain and reading.guard is not None
    pattern = re.compile(reading.guard, re.MULTILINE)
    assert pattern.search(f"PASS {path}") and not pattern.search("PASS tests/aab.spec.ts")


@pytest.mark.parametrize(
    ("command", "runnable", "echoes", "guard"),
    [
        ("npx jest tests/fee.spec.ts", True, True, r"tests/fee\.spec\.ts"),
        ("python -m pytest tests/test_x.py::test_a -q", True, True, r"tests/test_x\.py"),
        ("bash scripts/check_fees.sh", True, False, r"scripts/check_fees\.sh"),
        ("npm test -- reservations", True, False, "reservations"),
        ("npm test", True, False, None),
        ("a reminder text arrives on a test phone", False, False, None),
        ("npx jest 'unterminated", False, False, None),
    ],
)
def test_reading_one_command(command, runnable, echoes, guard):
    reading = read_command(command, frozenset({"tests/fee.spec.ts", "tests/test_x.py", "scripts/check_fees.sh"}))
    assert (reading.runnable, reading.echoes_path, reading.guard) == (runnable, echoes, guard)
    assert not reading.certain or (reading.echoes_path and not reading.untracked)


# --- lines ---------------------------------------------------------------------------------------------------------------


def test_one_bind_line_per_fixture_per_stage_with_proves_when_stages_differ(host):
    edit_capture(host, "RESERVE_DESK_FLOW_01", legacy_linked_test_expectation=JEST_FEE)
    verifies(host, DESK, "nfr-checkout-latency")
    group = group_of(plan_of(host), JEST_FEE)
    by_fixture = {member.fixture: member.lines for member in group.members}
    assert [line.stage for line in by_fixture[DESK]] == ["dev", "staging"]
    assert by_fixture[DESK][0].proves == ("api-checkout-create", "inv-no-double-checkout") and by_fixture[DESK][1].proves == ("nfr-checkout-latency",)
    assert [(line.request.proves, line.request.stage) for line in by_fixture[DESK]] == [(line.proves, line.stage) for line in by_fixture[DESK]]
    assert [(line.request.proves, line.request.stage) for line in by_fixture[FEE]] == [((), None)]
    code, out, err = align(host, "bind-legacy", "--yes")
    assert code == 0, err
    written = {name: json.loads(data)["records"][0] for name, data in records(host).items()}
    stages = sorted((record["verifies"][0], record["stage"]) for record in written.values())
    assert stages == [(DESK, "dev"), (DESK, "staging"), (FEE, "prod")]
    assert "3 binding(s) written, 0 refused" in out
    assert all(line.present for group in plan_of(host).groups if group.category == CERTAIN for member in group.members for line in member.lines)


def test_the_driver_prints_the_exact_verify_bind_lines(host, tmp_path):
    twin = fresh(host, tmp_path / "twin")
    code, out, err = align(host, "bind-legacy")
    assert code == 0, err
    lines = printed_lines(out)
    assert len(lines) == 1 and lines[0].startswith(f"specdev verify bind {FEE} --command 'npx jest tests/fee.spec.ts' --guard 'tests/fee\\.spec\\.ts'")
    assert not records(host), "the lines were printed, not written"
    for line in lines:
        code, _out, err = run_line(twin, line.replace(str(host), str(twin)))
        assert code == 0, err
    code, out, err = align(host, "bind-legacy", "--yes")
    assert code == 0, err
    assert records(host) and records(host) == records(twin)


def test_a_binding_the_driver_writes_is_refused_with_the_code_verify_bind_gives(host, monkeypatch):
    monkeypatch.setattr(legacy_bindings, "apply_bind", lambda *args, **kwargs: (_ for _ in ()).throw(refusal("E333", "'nfr-fee-accuracy' is already proved by 'ver-x'")))
    code, out, err = align(host, "bind-legacy", "--yes")
    assert code == 1
    assert f"refused  {FEE}: E333 'nfr-fee-accuracy' is already proved by 'ver-x'" in out
    assert not records(host)


# --- manual conversions --------------------------------------------------------------------------------------------------


def manual_lines(host: Path, fixture: str) -> list[str]:
    code, out, err = align(host, "propose", "--kind", "bindings")
    assert code == 0, err
    items = json.loads((host / "spec" / WORKLIST_FILE).read_text(encoding="utf-8"))["items"]
    proposal = next(item["proposal"] for item in items if item["about"] == fixture and item["kind"] == "legacy-fixture")
    return [part.strip() for part in proposal.partition("Record it: ")[2].split("; ") if part.strip().startswith("specdev json patch")]


def schema_errors_of(host: Path, fixture: str) -> list[tuple]:
    data = json.loads((host / "spec" / FIXTURES).read_text(encoding="utf-8"))
    index = next(i for i, entry in enumerate(data["fixtures"]) if entry["fixture_id"] == fixture)
    return [found for found in validate_data_against_schema(str(REAL_ROOT), data) if tuple(found[0][:2]) == ("fixtures", index)]


def test_a_fixture_with_no_command_becomes_manual_with_a_reason_of_at_least_10_characters(host):
    lines = manual_lines(host, RETURN)
    assert len(lines) == 2 and lines[0].startswith(f"specdev json patch --id {RETURN} .manual_reason") and lines[1].endswith(".mode '\"manual\"'")
    for line in lines:
        code, out, err = run_line(host, line)
        assert code == 0, err
    entry = fixture_of(host, RETURN)
    assert entry["mode"] == "manual" and len(entry["manual_reason"]) >= 10


def test_the_manual_fixture_passes_the_step_08_schema(host):
    before = schema_errors_of(host, RETURN)
    for line in manual_lines(host, RETURN):
        assert run_line(host, line)[0] == 0
    assert fixture_of(host, RETURN)["mode"] == "manual"
    assert schema_errors_of(host, RETURN) == before == []


# --- summary -------------------------------------------------------------------------------------------------------------


def test_summary_counts_bindings_fixtures_manual_and_unbound(host):
    def summary() -> dict:
        code, out, err = align(host, "bind-legacy", "--summary", "--json")
        assert code == 0, err
        return json.loads(out)

    start = summary()
    assert (start["bindings"], start["covered"], start["manual"], start["open"]) == (0, [], [], len(start["unbound"])) and FEE in start["unbound"]
    assert align(host, "bind-legacy", "--yes")[0] == 0
    bound = summary()
    assert bound["bindings"] == 1 and bound["covered"] == [FEE] and FEE not in bound["unbound"] and bound["open"] == start["open"] - 1
    for line in [f"specdev json patch --id {RETURN} .manual_reason '\"the legacy plans name no command that runs this check\"'", f"specdev json patch --id {RETURN} .mode '\"manual\"'"]:
        assert run_line(host, line)[0] == 0
    made = summary()
    assert made["manual"] == [RETURN] and made["unattested"] == [RETURN] and made["open"] == bound["open"]
    assert run_line(host, f"specdev verify attest {RETURN}")[0] == 0
    attested = summary()
    assert attested["attested"] == [RETURN] and attested["unattested"] == [] and attested["bindings"] + len(attested["attested"]) == 2
    assert attested["open"] == bound["open"] - 1


# --- what is written and what is not run ---------------------------------------------------------------------------------


def changed(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}


def test_the_pass_writes_only_under_extras_verification_and_step_08_fixtures(host):
    start = tree_digest(host)
    assert align(host, "propose", "--kind", "bindings")[0] == 0
    proposed = tree_digest(host)
    assert changed(start, proposed) == {f"spec/{WORKLIST_FILE}"}
    assert align(host, "bind-legacy", "--yes")[0] == 0
    bound = tree_digest(host)
    done = changed(proposed, bound)
    assert done and all(path.startswith(f"{RECORDS.as_posix()}/ver-") or path == f"spec/{WORKLIST_FILE}" for path in done), done
    assert not [path for path in bound if path.startswith(f"{RECORDS.as_posix()}/evd-")]
    for line in manual_lines(host, RETURN):
        assert run_line(host, line)[0] == 0
    assert changed(bound, tree_digest(host)) - {f"spec/{WORKLIST_FILE}"} == {f"spec/{FIXTURES}"}, "the manual conversion is the one write the pass makes to step 08, by `json patch`"


def prove(host: Path, cap: str) -> list[str]:
    spec = str(host / "spec")
    graph = build_graph(spec, str(REAL_ROOT))
    return [error.render() for error in proof_errors(graph, ProofContext(str(host), spec, records_folder(spec)), [FEE], cap)]


def node_lines(host: Path, node: str) -> list[str]:
    """The findings of ``spec-check`` that name *node* (the host path left out), and the check summary lines that name no node."""
    findings = run_spec_check(str(REAL_ROOT), str(host / "spec"), str(host), str(host / "spec"))
    return sorted(error.render().replace(str(host), "HOST") for error in findings if node in error.render())


def test_state_right_after_bind_legacy_a_binding_with_no_evidence(host):
    before_check, before_dev, before_prod = node_lines(host, FEE), prove(host, "dev"), prove(host, "prod")
    assert len(before_dev) == len(before_prod) == 1 and before_dev[0].startswith(f"E348 fixture {FEE}: its verifier {FEE} has no binding")
    assert align(host, "bind-legacy", "--yes")[0] == 0
    assert node_lines(host, FEE) == before_check, "spec-check names the node as before: it does not read evidence"
    assert prove(host, "dev") == [], "the binding is a prod binding: pending its stage, no finding at dev"
    after = prove(host, "prod")
    assert len(after) == 1 and after[0].startswith(f"E347 fixture {FEE}: binding ver-late-fee-two-days has no valid evidence (NO_EVIDENCE)")
    code, _out, err = run_line(host, "specdev verify run ver-late-fee-two-days")
    assert code == 1 and "is a prod binding and this run is at dev" in err + _out


def test_a_proposal_never_runs_a_command_or_writes_a_record(host, tmp_path, monkeypatch):
    sentinel = tmp_path / "sentinel"
    (host / "tests" / "test_sentinel.py").write_text(f"from pathlib import Path\n\ndef test_it():\n    Path({str(sentinel)!r}).write_text('ran')\n", encoding="utf-8")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "sentinel")
    edit_capture(host, "FEE_CALC_01", legacy_linked_test_expectation="python -m pytest tests/test_sentinel.py")
    calls: list[list[str]] = []
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda argv, *a, **k: (calls.append(list(argv)), real(argv, *a, **k))[1])
    assert align(host, "propose", "--kind", "bindings")[0] == 0
    assert align(host, "bind-legacy")[0] == 0
    assert not records(host) and not sentinel.exists()
    assert align(host, "bind-legacy", "--yes")[0] == 0
    assert records(host) and not sentinel.exists(), "a binding is written; its command is never run"
    assert all(call[0] == "git" for call in calls), [call for call in calls if call[0] != "git"]


def test_a_dry_run_asks_nothing_and_writes_nothing(host):
    start = tree_digest(host)
    code, out, err = align(host, "bind-legacy", "--dry-run", "--yes")
    assert code == 0, err
    assert "dry run: nothing asked, nothing written" in out and tree_digest(host) == start


# --- merge ---------------------------------------------------------------------------------------------------------------


def legacy_closed(host: Path) -> str:
    """Commit the base (``ms-catalog-basics`` in progress), then legacy-close it and commit; the base commit."""
    edit_json(host, "16_impl_context.json", lambda data: next(row for row in data["plan"]["milestone_index"] if row["about"] == ["ms-catalog-basics"]).update(status="in_progress"))
    base = git(host, "rev-parse", "HEAD").strip()
    write_legacy_close(str(host / "spec"), "ms-catalog-basics", "legacy migration", repo_root=str(REAL_ROOT))
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "legacy close")
    return base


def test_unbound_fixture_not_a_merge_error(host):
    reset_config()
    spec = str(host / "spec")
    base = legacy_closed(host)
    assert FEE in legacy_bindings.summary_of(host / "spec", toolkit_root=REAL_ROOT, git_root=host).unbound
    findings, context = run_spec_check_json(str(REAL_ROOT), spec, str(host), spec, merge=True, base_ref=base)
    assert context["checks"][MERGE_BINDINGS]["status"] == "SKIP"
    assert not [found for found in findings if found.code in ("E348", "E901") or (found.code.startswith("E34") and (found.node_id or "").startswith("fix-"))]


def test_a_legacy_close_is_left_out_of_closed_by_this_branch_and_a_plain_close_is_not(host):
    spec = str(host / "spec")
    base = legacy_closed(host)
    assert closed_by_branch(read_statuses(spec), read_statuses(spec, git_ref=base, git_root=str(host))) == []
    plain = {"ms-catalog-basics": AnchorState("done", "a person", {"signed_off_by": "a person"})}
    assert closed_by_branch(plain, {}) == ["ms-catalog-basics"]


def test_the_pass_is_not_a_runner_script():
    assert "bindings" in KINDS
    assert not [script.id for script in discover_scripts() if "bind" in script.id], "align apply --auto must never run or record a command"
