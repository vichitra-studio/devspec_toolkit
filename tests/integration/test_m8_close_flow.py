"""The life of a milestone through the commands, on the worked example: start, bind and run, record, review, sign off, close, and what a closed milestone refuses.

Every test works on a git copy of the worked example (``tests/fixtures/graph_example``) made in a temporary folder; ``tests/fixtures/m8_account_recovery/``
holds only what the example lacks (the code the bindings run, drafts the commands are fed, findings files).  Each step asserts the exit code, the words
of the output that matter, the file written, and what ``spec-check`` says compared with the pinned summary of the pristine example
(``tests/fixtures/step_gate/spec_check_summary.golden``): the difference by check name, and by code against a run on the pristine copy.

Commands run in this process through ``run_on_example`` (``unit.trace._lock_support``: the repository's helper for ``specdev <argv>`` with the three
root flags).  Where a library entry point is used instead, the test says so.
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.lifecycle import plans
from specdev_tools.lifecycle.attest import review_rule_attested
from unit.lifecycle._record_support import author  # noqa: F401  (the fixture ``author``)
from unit.proof._support import context, graph_of
from unit.trace._lock_support import ROOT, git_copy_of_example, run_on_example
from unit.verify._support import commit_all, edit_doc

FX = ROOT / "tests" / "fixtures" / "m8_account_recovery"
GOLDEN = ROOT / "tests" / "fixtures" / "step_gate" / "spec_check_summary.golden"

MS = "ms-account-recovery"
BATCH = "account_recovery"
ITEM = "PWRESET_CONFIRM_EXPIRED_01"
SECOND_ITEM = "PWRESET_CONFIRM_REUSED_01"
CRITERION = "tc-confirm-expired-token"
SECOND_CRITERION = "tc-confirm-reused-token"
FIXTURE = "fix-password-reset-expired-token"
SECOND_FIXTURE = "fix-password-reset-reused-token"
BINDING = "ver-password-reset-expired-token"
SECOND_BINDING = "ver-password-reset-reused-token"
RULE = "rule-security-review-of-token-handling"
ANCHOR_ROW = "anchor-ms-account-recovery"
PLAN = Path("spec") / "impl_context" / "ms_account_recovery_plan.json"
ANCHOR = Path("spec") / "16_impl_context.json"
LOCK = Path("spec") / "extras" / "trace.lock.json"
VERIFICATION = Path("spec") / "extras" / "verification"
SIGNOFF = Path("spec") / "extras" / "signoff"
CODE_FILE = Path("src") / "expired_token_test.py"
SCAFFOLD = Path("src") / "routes" / "password-resets" / "confirm.ts"
EXPIRED_COMMAND = "python3 src/expired_token_test.py"

CHECK_LINE = re.compile(r"\[(?:PASS|FAIL|WARN|SKIP)\]\s+(\S+)\s+(\d+) errors\s+(\d+) warnings")
CODE_LINE = re.compile(r"^([EW]\d{3}) ", re.MULTILINE)


# --- the commands and what they print ---------------------------------------------------------------------------------


def run(host: Path, *argv: str, want: int | None = 0) -> str:
    """Run ``specdev <argv>`` on *host* (three root flags added); asserts the exit code *want* (``None``: any) and returns what it printed."""
    code, out = run_on_example(host, *argv)
    if want is not None:
        assert code == want, f"specdev {' '.join(argv)} exited {code}, wanted {want}:\n{out}"
    return out


def refused(host: Path, code: str, *argv: str) -> str:
    """Run a command that must be refused with *code* (exit 1); returns the output."""
    out = run(host, *argv, want=1)
    assert code in out, f"specdev {' '.join(argv)} did not name {code}:\n{out}"
    return out


def summary(text: str) -> dict[str, tuple[int, int]]:
    """The per-check ``(errors, warnings)`` of a ``spec-check`` summary."""
    return {name: (int(errors), int(warnings)) for name, errors, warnings in CHECK_LINE.findall(text)}


GOLDEN_CHECKS = summary(GOLDEN.read_text(encoding="utf-8"))


def spec_check(host: Path) -> tuple[dict[str, tuple[int, int]], Counter[str]]:
    """``spec-check`` on *host*: the summary per check and the count of every code it printed."""
    out = run(host, "spec-check", str(host / "spec"), want=None)
    return summary(out), Counter(CODE_LINE.findall(out))


def difference(host: Path, baseline_codes: Counter[str]) -> tuple[dict[str, tuple[int, int]], dict[str, int]]:
    """What ``spec-check`` on *host* says beyond the golden: ``{check: (errors, warnings) more}`` and ``{code: count more}``; a check or code that has fewer shows negative."""
    checks, codes = spec_check(host)
    names = set(checks) | set(GOLDEN_CHECKS)
    by_check = {}
    for name in sorted(names):
        now, then = checks.get(name, (0, 0)), GOLDEN_CHECKS.get(name, (0, 0))
        if now != then:
            by_check[name] = (now[0] - then[0], now[1] - then[1])
    by_code = {code: codes[code] - baseline_codes[code] for code in sorted(set(codes) | set(baseline_codes)) if codes[code] != baseline_codes[code]}
    return by_check, by_code


def tree_bytes(host: Path) -> dict[str, bytes]:
    """Every file of the spec folder of *host* by relative path."""
    spec = host / "spec"
    return {str(path.relative_to(spec)): path.read_bytes() for path in sorted(spec.rglob("*")) if path.is_file()}


def read(host: Path, rel: Path) -> Any:
    return json.loads((host / rel).read_text(encoding="utf-8"))


def row(host: Path) -> dict[str, Any]:
    """The anchor row of the milestone."""
    return read(host, ANCHOR)["plan"]["milestone_index"][0]


def clone(source: Path, tmp_path: Path, name: str) -> Path:
    """A copy of the host *source* (its git folder too) under *tmp_path*."""
    return Path(shutil.copytree(source, tmp_path / name, symlinks=True))


# --- the hosts ---------------------------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _git_author(author: None) -> None:
    """Every record names the same person (``AUTHOR`` of the repository's record tests), whatever git is configured to say on this machine."""


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The worked example as a git host with the code its bindings run and the scaffold file its row names, committed; it is only read: tests copy it."""
    host = git_copy_of_example(tmp_path_factory.mktemp("m8-template") / "host")
    (host / "src").mkdir()
    for script in sorted((FX / "code" / "src").glob("*.py")):
        shutil.copy(script, host / "src" / script.name)
    commit_all(host, "the code the bindings run")
    return host


@pytest.fixture(scope="module")
def baseline(template: Path) -> Counter[str]:
    """The codes ``spec-check`` prints on the pristine example, and a check that this is the golden."""
    checks, codes = spec_check(template)
    assert checks == GOLDEN_CHECKS, "the pristine example no longer gives the pinned summary"
    return codes


def make_manual(host: Path) -> None:
    """Make the second fixture manual, by commands: the reason first (a contract fixture may carry it), then the mode."""
    run(host, "json", "patch", "--id", SECOND_FIXTURE, ".manual_reason", '"A person redeems a token twice."')
    run(host, "json", "patch", "--id", SECOND_FIXTURE, ".mode", '"manual"')


def add_scaffold_file(host: Path) -> None:
    """The file the scaffold row names, tracked: without it the close gate says E746 (not a tracked file)."""
    assert "E746" in run(host, "status", "--milestone", MS), "the dry run names the untracked scaffold file"
    (host / SCAFFOLD).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FX / "code" / SCAFFOLD, host / SCAFFOLD)
    commit_all(host, "the scaffold file")


def make_ready(host: Path, *, manual_second: bool = False) -> None:
    """Bring *host* to the state the person signs off from, by commands: started, both criteria bound, run, the plan executed, a verified review.

    With *manual_second* the second criterion's fixture is manual (a person attests it) instead of bound and run.
    """
    plan = str(host / PLAN)
    run(host, "json", "patch", "--id", ANCHOR_ROW, ".status", '"pending"')
    run(host, "milestone", "start", MS)
    add_scaffold_file(host)
    run(host, "verify", "bind", FIXTURE, "--command", EXPIRED_COMMAND, "--guard", "expired token .*passed", "--id", BINDING)
    if manual_second:
        make_manual(host)
        commit_all(host, "a manual fixture")
    else:
        run(host, "verify", "bind", SECOND_FIXTURE, "--command", "python3 src/reused_token_test.py", "--guard", "reused token .*passed")
    run(host, "json", "insert", plan, ".plan.spec_alignment.checklist", (FX / "second_plan_item.json").read_text(encoding="utf-8"))
    run(host, "plan", "record", f"{ITEM}/a01", "--outcome", "done")
    run(host, "plan", "record", f"{SECOND_ITEM}/a01", "--outcome", "done")
    if manual_second:
        run(host, "verify", "run", BINDING, "--stage", "dev")
        run(host, "verify", "attest", SECOND_FIXTURE)
    else:
        run(host, "verify", "run", "--all", "--stage", "dev")
    run(host, "review", "record", MS, "--verdict", "verified", "--findings-file", str(FX / "findings_converged.json"))


@pytest.fixture(scope="module")
def ready(template: Path, tmp_path_factory: pytest.TempPathFactory, author_module: None) -> Path:
    """A host ready to be signed off; only read."""
    host = clone(template, tmp_path_factory.mktemp("m8-ready"), "host")
    make_ready(host)
    return host


@pytest.fixture(scope="module")
def author_module() -> Iterator[None]:
    """The author of every record, for the module-scoped hosts."""
    mp = pytest.MonkeyPatch()
    mp.setenv("GIT_AUTHOR_NAME", "Ada Lovelace")
    mp.setenv("GIT_AUTHOR_EMAIL", "ada@example.invalid")
    yield
    mp.undo()


@pytest.fixture(scope="module")
def closed(ready: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A host whose milestone is signed off and closed; only read."""
    host = clone(ready, tmp_path_factory.mktemp("m8-closed"), "host")
    run(host, "milestone", "sign-off", MS)
    run(host, "milestone", "close", MS)
    return host


# --- the life of a milestone -------------------------------------------------------------------------------------------


def test_the_life_of_a_milestone_through_the_commands(template: Path, baseline: Counter[str], tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    plan = str(host / PLAN)

    # 1. the milestone id comes from the batch
    out = json.loads(run(host, "milestone-state", "--batch-id", BATCH))
    assert out["milestone"] == MS, "step 1: milestone-state --batch-id names the milestone of the plan"
    assert difference(host, baseline) == ({}, {}), "step 1: the pristine example is the golden"
    refused(host, "E803", "milestone", "start", BATCH)  # a batch id is not a milestone id

    # 2. start (the example's row is in_progress; a pending row is what a roadmap milestone starts from)
    run(host, "json", "patch", "--id", ANCHOR_ROW, ".status", '"pending"')
    out = run(host, "milestone", "start", MS)
    assert "started (pending -> in_progress)" in out and row(host)["status"] == "in_progress", "step 2: start writes the status"
    assert "already in progress" in run(host, "milestone", "start", MS), "step 2: a second start is a no-op"
    assert difference(host, baseline) == ({}, {}), "step 2: start leaves spec-check as it was"

    # 3. what is owed
    out = run(host, "status", "--milestone", MS)
    for words in ("criteria in play (2)", f"{CRITERION} (task task-implement-password-reset-confirm): unproven", f"{SECOND_CRITERION} (task task-implement-password-reset-confirm): unbound",
                  "plan items not executed: 1 (PWRESET_CONFIRM_EXPIRED_01)", "close gate (dry run): 7 error(s)"):
        assert words in out, f"step 3: status --milestone does not say {words!r}:\n{out}"
    for code in ("E810", "E811", "E812", "E813", "E746", "E814"):
        assert code in out, f"step 3: the dry run does not list {code}"

    # 4. the binding, the run, the record
    out = run(host, "milestone", "close", MS, "--check", want=1)
    assert "has no sign-off record" in out, "step 4: the gate is read"
    add_scaffold_file(host)
    out = run(host, "verify", "bind", FIXTURE, "--command", EXPIRED_COMMAND, "--guard", "expired token .*passed", "--id", BINDING)
    assert f"binding {BINDING} replaced (stage dev" in out and (host / VERIFICATION / f"{BINDING}.json").is_file(), "step 4: bind replaces the example's record"
    out = run(host, "verify", "bind", SECOND_FIXTURE, "--command", "python3 src/reused_token_test.py", "--guard", "reused token .*passed")
    assert f"binding {SECOND_BINDING} written (stage dev" in out, "step 4: bind writes the second record"
    run(host, "json", "insert", "--id", ITEM, ".implementation.actions", (FX / "verifier_action.json").read_text(encoding="utf-8"))
    out = refused(host, "E822", "plan", "record", f"{ITEM}/a02", "--outcome", "done")
    assert BINDING in out and "verify run" in out, "step 4: the action that names a verifier is refused and points at verify run"
    assert "execution" not in read(host, PLAN), "step 4: the refusal wrote nothing"
    assert difference(host, baseline) == ({"canonical-integrity": (1, 0)}, {"E210": 1}), "step 4: the action's command is not registered in the project canon: that is all spec-check adds"
    run(host, "json", "delete", plan, ".plan.spec_alignment.checklist[0].implementation.actions[1]")
    assert difference(host, baseline) == ({}, {}), "step 4: deleting the action clears it"
    run(host, "json", "insert", plan, ".plan.spec_alignment.checklist", (FX / "second_plan_item.json").read_text(encoding="utf-8"))
    by_check, by_code = difference(host, baseline)
    assert by_check == {"graph": (1, 0)} and by_code == {"E761": 1}, f"step 4: the second item is a link with no lock entry, nothing else: {by_check} {by_code}"
    out = run(host, "verify", "run", "--all", "--stage", "dev")
    assert "2 run, 2 passed, 0 failed" in out, "step 4: both bindings pass"
    assert {path.name for path in (host / VERIFICATION).glob("evd-*")} == {"evd-password-reset-expired-token-dev.json", "evd-password-reset-reused-token-dev.json"}, "step 4: one evidence file per run"
    out = run(host, "plan", "record", f"{ITEM}/a01", "--outcome", "done")
    assert "recorded rec-0001" in out and read(host, PLAN)["execution"]["records"][0]["action"] == "a01", "step 4: the record is in the plan"
    run(host, "plan", "record", f"{SECOND_ITEM}/a01", "--outcome", "done")

    # 5. an open item, by the two forms
    item = (FX / "open_item.json").read_text(encoding="utf-8")
    run(host, "json", "patch", plan, ".execution.emergent_ambiguities", f"[{item}]")
    out = refused(host, "E632", "milestone", "close", MS, "--check")
    assert "amb-token-store" in out, "step 5: the open item written by patch blocks close"
    run(host, "json", "delete", plan, ".execution.emergent_ambiguities[0]")
    assert "E632" not in run(host, "milestone", "close", MS, "--check", want=1), "step 5: deleting the item clears E632"
    run(host, "json", "insert", plan, ".execution.emergent_ambiguities", item)
    assert "amb-token-store" in refused(host, "E632", "milestone", "close", MS, "--check"), "step 5: the open item written by insert blocks close"
    run(host, "json", "delete", plan, ".execution.emergent_ambiguities")
    assert "E632" not in run(host, "milestone", "close", MS, "--check", want=1), "step 5: deleting the list clears E632"

    # 6. the review: a verdict other than verified keeps close refused
    out = run(host, "review", "record", MS, "--verdict", "needs_work", "--findings-file", str(FX / "findings_needs_work.json"))
    assert "verdict needs_work, 1 finding(s)" in out and read(host, PLAN)["review"]["verdict"] == "needs_work", "step 6: needs_work is recorded"
    assert "the verdict is needs_work" in refused(host, "E813", "milestone", "close", MS, "--check"), "step 6: close is refused while the verdict is needs_work"
    out = run(host, "review", "record", MS, "--verdict", "verified", "--findings-file", str(FX / "findings_converged.json"))
    review = read(host, PLAN)["review"]
    assert "verdict verified, 0 finding(s)" in out and review["verdict"] == "verified" and review["findings"] == [], "step 6: verified replaces the block"
    assert "E813" not in run(host, "milestone", "close", MS, "--check", want=1), "step 6: E813 is cleared"

    # 7. close --check before the sign-off: E814 and nothing written
    before = tree_bytes(host)
    out = refused(host, "E814", "milestone", "close", MS, "--check")
    assert "milestone sign-off" in out and out.count("E8") == 1, f"step 7: E814 is the only refusal left:\n{out}"
    refused(host, "E814", "milestone", "close", MS)
    assert tree_bytes(host) == before, "step 7: a refused close, or a check, writes nothing"
    assert "Milestones awaiting sign-off" in run(host, "status"), "step 7: status has the section"

    # 8. sign-off
    out = run(host, "milestone", "sign-off", MS)
    assert "recorded so-ms-account-recovery-0001" in out and "signed by Ada Lovelace <ada@example.invalid>" in out, "step 8: the sign-off names the author git gives"
    signoff = read(host, SIGNOFF / "so-ms-account-recovery-0001.json")["records"][0]
    assert signoff["signoff_id"] == "so-ms-account-recovery-0001" and signoff["about"] == [MS], "step 8: the record is in extras/signoff"
    assert "the close gate passes" in run(host, "milestone", "close", MS, "--check") and row(host)["status"] == "in_progress", "step 8: --check passes and writes nothing"

    # 9. close
    plan_before = (host / PLAN).read_bytes()
    out = run(host, "milestone", "close", MS)
    assert f"milestone {MS}: closed" in out and "the plan is frozen" in out, "step 9: close says so"
    closed_row = row(host)
    assert closed_row["status"] == "done", "step 9: the row is done"
    assert set(closed_row["close"]) == {"signed_off_by", "signoff", "tree", "plan_hash", "closed_at", "migrations"}, "step 9: the keys of the close record"
    assert closed_row["close"]["signoff"] == signoff["signoff_id"] and closed_row["close"]["signed_off_by"] == "ada@example.invalid" and closed_row["close"]["migrations"] == [], "step 9: the close names the sign-off"
    assert (host / PLAN).read_bytes() == plan_before, "step 9: close does not touch the plan"
    checks, _codes = spec_check(host)
    assert checks["frozen-plans"] == (0, 0) and checks["plan-records"] == (0, 0) and checks["prose-ids"] == (0, 0), "step 9: the closed plan is clean"
    by_check, by_code = difference(host, baseline)
    assert by_check == {"cross-cutting": (-1, 0), "graph": (1, 0)} and by_code == {"E744": -1, "E761": 1}, \
        f"step 9: the tasks of a closed milestone are not checked for cross-cutting nodes (E744 goes), and the hand-made second item is left over (E761): {by_check} {by_code}"
    assert "E752" not in "".join(by_code), "step 9: no E752 on the anchor row"

    # 10. what a closed milestone refuses
    refused(host, "E820", "plan", "record", f"{ITEM}/a01", "--outcome", "done")
    refused(host, "E820", "review", "record", MS, "--verdict", "verified")
    refused(host, "E801", "milestone", "close", MS)
    assert (host / PLAN).read_bytes() == plan_before and row(host) == closed_row, "step 10: nothing was written"
    out = run(host, "status", "--milestone", MS)
    assert f"milestone {MS}: done" in out and "close gate" not in out, "step 10: status says the milestone is done and runs no gate (ruling L33)"
    edit_doc(host, "impl_context/ms_account_recovery_plan.json", lambda document: document["plan"]["summary"].update(functional_summary="Edited after the close."))
    out = run(host, "spec-check", str(host / "spec"), want=1)
    assert "E827" in out and "[FAIL] frozen-plans" in out, "step 10: a hand edit of the frozen plan is E827"


def test_step11_defer_then_start_resumes(template: Path, tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    run(host, "json", "patch", "--id", ANCHOR_ROW, ".status", '"pending"')
    plan_before = (host / PLAN).read_bytes()
    refused(host, "E802", "milestone", "defer", MS)
    out = run(host, "milestone", "defer", MS, "--reason", "waiting on the identity provider contract")
    assert "deferred (pending -> deferred)" in out, "defer from pending"
    assert row(host)["status"] == "deferred" and row(host)["deferral_reason"] == "waiting on the identity provider contract", "the row holds the reason"
    assert (host / PLAN).read_bytes() == plan_before, "defer writes the row only"
    refused(host, "E801", "milestone", "defer", MS, "--reason", "again")
    refused(host, "E801", "milestone", "sign-off", MS)
    status = run(host, "status", "--milestone", MS)
    assert f"milestone {MS}: deferred" in status, "status names the deferred milestone"
    out = run(host, "milestone", "start", MS)
    assert "resumed (deferred -> in_progress)" in out, "start resumes it"
    assert row(host)["status"] == "in_progress" and "deferral_reason" not in row(host), "the reason is cleared"


def test_step12_a_second_plan_for_the_same_milestone_is_refused_and_one_for_another_milestone_is_created(template: Path, baseline: Counter[str], tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    draft = tmp_path / "same_milestone.json"
    draft.write_text((FX / "plan_draft_second_milestone.json").read_text(encoding="utf-8").replace("ms-account-lockout", MS), encoding="utf-8")
    before = tree_bytes(host)
    out = refused(host, "E767", "step", "create", "16a", "second", "--from", str(draft))
    assert "already has the plan file" in out and tree_bytes(host) == before, "the same milestone has one plan file, whatever the batch is called"
    refused(host, "E767", "step", "create", "16a", BATCH, "--from", str(FX / "plan_draft_second_milestone.json"))
    out = run(host, "step", "create", "16a", "account_lockout", "--from", str(FX / "plan_draft_second_milestone.json"))
    created = host / "spec" / "impl_context" / "ms_account_lockout_plan.json"
    assert "created plan-ms-account-lockout" in out and created.is_file(), "another milestone gets its plan"
    assert read(host, Path("spec/impl_context/ms_account_lockout_plan.json"))["milestone"] == "ms-account-lockout"
    by_check, by_code = difference(host, baseline)
    assert by_check == {"schema-validation": (1, 1)} and by_code == {"E304": 1, "W611": 1}, f"only that the milestone of the draft is not in the roadmap: {by_check} {by_code}"
    refused(host, "E767", "step", "create", "16a", "account_lockout", "--from", str(FX / "plan_draft_second_milestone.json"))


# --- the pack's named tests ---------------------------------------------------------------------------------------------


def _suspect(host: Path, source: str, target: str) -> None:
    """Give the lock entry of the link *source* to *target* a chain stamp the target no longer has: the link is suspect."""
    path = host / LOCK
    document = json.loads(path.read_text(encoding="utf-8"))
    hit = [entry for entry in document["entries"] if entry["source"] == source and entry["target"] == target]
    assert hit, f"no lock entry from {source} to {target}"
    hit[0]["chain_stamp"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def test_step1_milestone_start_refuses_a_suspect_chain_link_and_accepts_an_unrelated_one(template: Path, tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    run(host, "json", "patch", "--id", ANCHOR_ROW, ".status", '"pending"')
    _suspect(host, "nfr-latency-reset-email", "tp-mailrelay")
    out = run(host, "milestone", "start", MS)
    assert "started" in out and row(host)["status"] == "in_progress", "a suspect link off the chain does not stop a start"
    run(host, "json", "patch", "--id", ANCHOR_ROW, ".status", '"pending"')
    _suspect(host, CRITERION, "ac-password-reset-3")
    out = refused(host, "E800", "milestone", "start", MS)
    assert "1 suspect link(s)" in out and "E763" in out and "ac-password-reset-3" in out, "a suspect link on the chain does"
    assert row(host)["status"] == "pending", "the refused start wrote nothing"


def test_step2_plan_record_refuses_a_verifier_naming_action(template: Path, tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    run(host, "verify", "bind", FIXTURE, "--command", EXPIRED_COMMAND, "--guard", "expired token .*passed", "--id", BINDING)
    run(host, "json", "insert", "--id", ITEM, ".implementation.actions", (FX / "verifier_action.json").read_text(encoding="utf-8"))
    before = (host / PLAN).read_bytes()
    out = refused(host, "E822", "plan", "record", f"{ITEM}/a02", "--outcome", "done")
    assert f"binding {BINDING}" in out and f"verify run {BINDING}" in out
    assert (host / PLAN).read_bytes() == before
    run(host, "plan", "record", f"{ITEM}/a01", "--outcome", "done")  # the action that names no verifier is recorded


def test_step2_verify_run_writes_the_evidence_for_the_dev_binding(template: Path, tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    run(host, "verify", "bind", FIXTURE, "--command", EXPIRED_COMMAND, "--guard", "expired token .*passed", "--id", BINDING)
    out = run(host, "verify", "run", BINDING, "--stage", "dev")
    assert f"PASS {BINDING} at dev" in out and "1 run, 1 passed" in out
    evidence = read(host, VERIFICATION / "evd-password-reset-expired-token-dev.json")["records"][0]
    assert evidence["stage"] == "dev" and evidence["type"] == "run" and evidence["tested_tree"], "the evidence names the stage and the code tree it ran on"
    assert evidence["about"] == [BINDING] and evidence["exit_code"] == 0 and evidence["guard_matched"] is True, "the evidence belongs to the binding and says it passed"


def test_step3_status_milestone_lists_what_doc_l2313_names(ready: Path, author_module: None) -> None:
    out = run(ready, "status", "--milestone", MS)
    for words in (f"milestone {MS}: in_progress", "code tree: ", "sign-offs: none", "criteria in play (2)", f"{CRITERION} (task task-implement-password-reset-confirm): proven",
                  f"{SECOND_CRITERION} (task task-implement-password-reset-confirm): proven", "manual share: 0 node(s) a person attests, 0 attested",
                  "deferred and won't-do tasks (0)", "open items: 0", "plan items not executed: 0", "proof owed at staging or prod: none"):
        assert words in out, f"status --milestone does not say {words!r}:\n{out}"
    assert "E814" in out and "1 error(s)" in out, "the dry run of the gate lists the sign-off as the one thing owed"
    sections = json.loads(run(ready, "status", "--milestone", MS, "--json"))
    for key in ("milestone", "status", "plan", "tree", "signoffs", "criteria", "manual", "paused_tasks", "open_items", "items_not_executed", "proof_owed_later", "close_gate"):
        assert key in sections, f"--json has no {key}"
    plain = run(ready, "status")
    for title in ("Pending replay by step", "Open items by owner", "Milestones awaiting sign-off", "Outdated and removed realisations", "Gate-owned errors by owner"):
        assert title in plain, f"status has no section {title!r}"
    assert MS in plain.split("Milestones awaiting sign-off")[1].split("Outdated")[0], "a verified, unsigned milestone is listed as awaiting sign-off"


def test_step3_code_edit_after_verify_run_fails_close_e811_until_run_again(ready: Path, tmp_path: Path) -> None:
    host = clone(ready, tmp_path, "host")
    run(host, "milestone", "sign-off", MS)
    assert "the close gate passes" in run(host, "milestone", "close", MS, "--check")
    (host / CODE_FILE).write_text("print('expired token case passed')\n# edited after the run\n", encoding="utf-8")
    out = refused(host, "E811", "milestone", "close", MS, "--check")
    assert CRITERION in out and "STALE_TREE" in out and f"verify run {BINDING}" in out, f"the run no longer matches the code:\n{out}"
    run(host, "verify", "run", "--all", "--stage", "dev")
    out = run(host, "milestone", "close", MS, "--check")
    assert "the close gate passes" in out, "a new run clears E811"


def test_step4_close_fails_e814_then_signoff_then_close_check_then_close_writes_done(ready: Path, tmp_path: Path) -> None:
    host = clone(ready, tmp_path, "host")
    assert refused(host, "E814", "milestone", "close", MS, "--check").count("E8") == 1
    assert row(host)["status"] == "in_progress"
    run(host, "milestone", "sign-off", MS)
    assert "the close gate passes; nothing written" in run(host, "milestone", "close", MS, "--check")
    run(host, "milestone", "close", MS)
    assert row(host)["status"] == "done" and row(host)["close"]["signoff"] == "so-ms-account-recovery-0001"


def test_step4_plan_bytes_unchanged_and_writers_refuse_e820(closed: Path, tmp_path: Path) -> None:
    host = clone(closed, tmp_path, "host")
    plan_hash = row(host)["close"]["plan_hash"]
    assert plan_hash == plans.plan_hash(host / PLAN), "the plan on disk is the one the close record hashed"  # library entry point: no command prints a plan hash
    before = tree_bytes(host)
    refused(host, "E820", "plan", "record", f"{ITEM}/a01", "--outcome", "done")
    refused(host, "E820", "plan", "record", "--prune", MS)
    refused(host, "E820", "review", "record", MS, "--verdict", "needs_work", "--findings-file", str(FX / "findings_needs_work.json"))
    assert tree_bytes(host) == before, "no refused writer wrote anything"
    assert "[PASS] frozen-plans" in run(host, "spec-check", str(host / "spec"), want=None)


def test_step5_at_deploy_records_after_close_leave_the_plan_byte_identical(ready: Path, tmp_path: Path) -> None:
    host = clone(ready, tmp_path, "host")
    run(host, "json", "insert", "--id", ITEM, ".implementation.actions", (FX / "at_deploy_action.json").read_text(encoding="utf-8"))
    run(host, "milestone", "sign-off", MS)
    assert "the close gate passes" in run(host, "milestone", "close", MS, "--check"), "an action marked at_deploy does not hold close up"
    run(host, "milestone", "close", MS)
    plan_bytes = (host / PLAN).read_bytes()
    out = run(host, "plan", "record", "--at-deploy", f"{ITEM}/a03", "--env", "staging")
    assert "recorded dep-0001" in out and "done at staging" in out
    out = run(host, "plan", "record", "--at-deploy", f"{ITEM}/a03", "--env", "prod")
    assert "recorded dep-0002" in out and "done at prod" in out
    assert (host / PLAN).read_bytes() == plan_bytes, "the plan is byte-identical"
    deploys = sorted(path.name for path in (host / VERIFICATION).glob("dep-*"))
    assert deploys == ["dep-0001.json", "dep-0002.json"], "each record is its own file"
    assert "[PASS] frozen-plans" in run(host, "spec-check", str(host / "spec"), want=None)


def test_step6_reattest_changes_a_lock_hash_and_close_fails_e812(ready: Path, tmp_path: Path) -> None:
    host = clone(ready, tmp_path, "host")
    run(host, "milestone", "sign-off", MS)
    lock_before = (host / LOCK).read_bytes()
    run(host, "json", "patch", "--id", CRITERION, ".text", '"POST /v1/password-resets/{token} with a token issued 31 minutes earlier returns HTTP 410 token-expired."')
    run(host, "attest", ITEM, "--yes", want=None)
    run(host, "attest", CRITERION, "--yes", want=None)
    assert (host / LOCK).read_bytes() != lock_before, "re-attesting the changed criterion changed a lock hash"
    out = refused(host, "E812", "milestone", "close", MS, "--check")
    assert ITEM in out and "rec-0001 is stale" in out and "record it" in out, f"the record of the action is stale:\n{out}"
    run(host, "plan", "record", f"{ITEM}/a01", "--outcome", "done")
    assert "E812" not in run(host, "milestone", "close", MS, "--check", want=None), "recording the action again clears E812"


def test_step6_staging_stage_action_does_not_hold_close_up(ready: Path, tmp_path: Path) -> None:
    host = clone(ready, tmp_path, "host")
    run(host, "json", "insert", "--id", ITEM, ".implementation.actions", (FX / "at_deploy_action.json").read_text(encoding="utf-8"))
    run(host, "milestone", "sign-off", MS)
    out = run(host, "milestone", "close", MS, "--check")
    assert "the close gate passes" in out
    before = tree_bytes(host)
    refused(host, "E330", "verify", "bind", SECOND_FIXTURE, "--command", "python3 src/reused_token_test.py", "--guard", "reused token .*passed", "--stage", "staging")
    assert tree_bytes(host) == before, "a binding at a stage its nodes do not need is refused and writes nothing"
    run(host, "json", "insert", "--id", ITEM, ".implementation.actions", (FX / "verifier_action.json").read_text(encoding="utf-8"))
    refused(host, "E822", "plan", "record", f"{ITEM}/a02", "--outcome", "done")


def test_step6_defer_then_start_resumes(template: Path, tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    out = run(host, "milestone", "defer", MS, "--reason", "waiting on the identity provider contract")
    assert "(in_progress -> deferred)" in out and row(host)["status"] == "deferred"
    run(host, "milestone", "start", MS)
    assert row(host)["status"] == "in_progress" and "deferral_reason" not in row(host)


def test_step6_removes_criterion_closes_via_its_fixture(ready: Path, tmp_path: Path) -> None:
    host = clone(ready, tmp_path, "host")

    def remove(document: dict[str, Any]) -> None:
        criteria = document["milestones"][0]["tasks"][0]["acceptance_criteria"]
        criteria[1] = {"criterion_id": SECOND_CRITERION, "text": "The reuse rule is retired.", "removes": ["fr-password-reset-request"], "verified_by": [SECOND_FIXTURE]}

    edit_doc(host, "14_roadmap.json", remove)
    run(host, "milestone", "sign-off", MS)
    out = run(host, "milestone", "close", MS, "--check", want=None)
    assert "the close gate passes" in out, f"a criterion that removes a node is proven by its fixture's run:\n{out}"


def test_step6_attest_rule_and_manual_fixture_in_one_command_all_or_nothing(template: Path, tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    make_manual(host)
    commit_all(host, "a manual fixture")
    before = tree_bytes(host)
    out = refused(host, "E824", "verify", "attest", SECOND_FIXTURE, RULE, "fix-password-reset-reusd-token")
    assert "nearest" in out and tree_bytes(host) == before, "one bad id: nothing is written"
    out = run(host, "verify", "attest", SECOND_FIXTURE, RULE)
    assert f"attested {SECOND_FIXTURE}" in out and f"attested {RULE}" in out
    assert (host / VERIFICATION / f"evd-{SECOND_FIXTURE}-attested.json").is_file() and (host / VERIFICATION / f"evd-{RULE}-attested.json").is_file()


def test_step6_a_manual_fixture_in_the_chain_holds_close_up_until_it_is_attested(template: Path, tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    make_ready(host, manual_second=True)
    run(host, "json", "patch", "--id", SECOND_FIXTURE, ".manual_reason", '"A person redeems a token twice, twice."')
    out = refused(host, "E811", "milestone", "close", MS, "--check")
    assert SECOND_FIXTURE in out and "verify attest" in out, f"the changed fixture needs a new attestation:\n{out}"
    run(host, "attest", SECOND_CRITERION, "--yes")  # the criterion that lists the fixture accepts the edit
    run(host, "verify", "attest", SECOND_FIXTURE)
    run(host, "milestone", "sign-off", MS)
    assert "the close gate passes" in run(host, "milestone", "close", MS, "--check")


def test_step6_attestation_invalid_after_the_rule_text_changes(template: Path, tmp_path: Path) -> None:
    host = clone(template, tmp_path, "host")
    run(host, "verify", "attest", RULE)
    # no command reports the release-gate finding in this release: the library entry point is called (``review_rule_attested``)
    assert review_rule_attested(RULE, graph_of(host), context(host)) == []
    run(host, "json", "patch", "--id", RULE, ".text", '"A person reviews every change to reset-token handling and its tests before release."')
    findings = review_rule_attested(RULE, graph_of(host), context(host))
    assert [finding.code for finding in findings] == ["E830"] and "STALE_HASH" in findings[0].message
    run(host, "verify", "attest", RULE)
    assert review_rule_attested(RULE, graph_of(host), context(host)) == []


def test_step7_plan_shaped_like_p_closes_with_no_halt(closed: Path) -> None:
    plan = read(closed, PLAN)
    items = plan["plan"]["spec_alignment"]["checklist"]
    assert items and all(item["type"] != "fr" for item in items), "task items that realise task criteria, none of type fr"
    assert all(item["realises"] and item["realises"][0].startswith("tc-") for item in items)
    assert row(closed)["status"] == "done", "the plan went through start, record, review, sign-off and close with no halt"
