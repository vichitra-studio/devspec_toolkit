"""``spec-check --merge`` on git copies of the worked example: each merge check provoked and cleared, and which milestones a branch closes.

The example's own known findings (24 errors, see ``tests/fixtures/step_gate/spec_check_summary.golden``) are in every mode, so the exit code of a
merge run on it is 1 whatever the merge checks say: these tests read the per-check lines and the codes of the output.  A host here is the example on
``main`` (its anchor row ``in_progress``, its binding a command that passes) with a ``feature`` branch that changes it; the commands are the real ones.
"""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.validation import merge_gate
from unit.graph._synth import git
from unit.lifecycle._record_support import author  # noqa: F401  (the fixture ``author``)
from unit.trace._lock_support import ROOT, git_copy_of_example, run_on_example
from unit.verify._support import commit_all, edit_binding, edit_doc, write_json

FX = ROOT / "tests" / "fixtures" / "m8_account_recovery"
MS = "ms-account-recovery"
ANCHOR_ROW = "anchor-ms-account-recovery"
FIXTURE, BINDING = "fix-password-reset-expired-token", "ver-password-reset-expired-token"
SECOND_FIXTURE, SECOND_BINDING = "fix-password-reset-reused-token", "ver-password-reset-reused-token"
PLAN = Path("spec") / "impl_context" / "ms_account_recovery_plan.json"
ANCHOR = Path("spec") / "16_impl_context.json"
VERIFICATION = Path("spec") / "extras" / "verification"
LOCK = Path("spec") / "extras" / "trace.lock.json"
NULL_SHA = "0" * 40
UNKNOWN_SHA = "1" * 40
PASSING = ["echo ok"]
FAILING = ["sh -c 'echo no; exit 3'"]

CHECK_LINE = re.compile(r"\[(PASS|FAIL|WARN|SKIP)\]\s+(\S+)")
CODE_LINE = re.compile(r"^([EW]\d{3}) ", re.MULTILINE)


@dataclass(frozen=True)
class Report:
    """What one ``spec-check`` run printed: the status of each check, the count of each code, and the text."""

    out: str
    statuses: dict[str, str]
    codes: Counter[str]

    def status(self, check: str) -> str:
        return self.statuses[check]


def report_of(out: str) -> Report:
    return Report(out, {name: status for status, name in CHECK_LINE.findall(out)}, Counter(CODE_LINE.findall(out)))


def run(host: Path, *argv: str, want: int | None = 0) -> str:
    code, out = run_on_example(host, *argv)
    if want is not None:
        assert code == want, f"specdev {' '.join(argv)} exited {code}, wanted {want}:\n{out}"
    return out


def merge(host: Path, *flags: str) -> Report:
    """``spec-check --merge`` with *flags*; the exit code is 1 on the example whatever the merge checks say, so it is not asserted."""
    return report_of(run(host, "spec-check", str(host / "spec"), "--merge", *flags, want=None))


def plain(host: Path) -> Report:
    return report_of(run(host, "spec-check", str(host / "spec"), want=None))


def clone(source: Path, tmp_path: Path, name: str = "host") -> Path:
    return Path(shutil.copytree(source, tmp_path / name, symlinks=True))


def read(host: Path, rel: Path) -> Any:
    return json.loads((host / rel).read_text(encoding="utf-8"))


def set_binding(host: Path, binding_id: str, commands: list[str], stage: str = "dev") -> None:
    """The commands and stage of a binding record, edited in place (a stage other than the one its nodes need is E330 elsewhere, which these tests do not read)."""
    def edit(record: dict[str, Any]) -> None:
        record.update(commands=commands, output_guard=".*", stage=stage)

    edit_binding(host, binding_id, edit)


def mark_done(host: Path, signed_off_by: str = "Ada Lovelace") -> None:
    """Give the anchor row the status ``done`` and a close record that names who signed off (no sign-off record exists: the merge gate does not ask)."""
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"]["milestone_index"][0].update(status="done", close={"signed_off_by": signed_off_by}))


def close(host: Path, message: str = "close the milestone") -> str:
    """Close the milestone on the branch (``mark_done``) and commit it; the commit id."""
    mark_done(host)
    commit_all(host, message)
    return git(host, "rev-parse", "HEAD")


@pytest.fixture(autouse=True)
def _git_author(author: None) -> None:
    """Every record names the same person, whatever git is configured to say on this machine."""


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The worked example on ``main``, its first binding re-bound to a command that passes, committed; only read: tests copy it."""
    host = git_copy_of_example(tmp_path_factory.mktemp("merge-template") / "host")
    set_binding(host, BINDING, PASSING)
    commit_all(host, "the binding passes")
    return host


@pytest.fixture
def host(template: Path, tmp_path: Path) -> Path:
    """A copy of the template on a ``feature`` branch (it differs from ``main`` by nothing yet)."""
    copy = clone(template, tmp_path)
    git(copy, "checkout", "-q", "-b", "feature")
    return copy


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], dict[str, Any]]]:
    """The calls the merge gate makes to ``run_bindings`` (ids and keywords); the real function still runs."""
    calls: list[tuple[list[str], dict[str, Any]]] = []
    real = merge_gate.run_bindings

    def recording(ids: list[str], *args: Any, **kwargs: Any) -> Any:
        calls.append((list(ids), kwargs))
        return real(ids, *args, **kwargs)

    monkeypatch.setattr(merge_gate, "run_bindings", recording)
    return calls


def test_the_example_on_a_clean_branch_adds_only_clean_merge_lines(host: Path) -> None:
    report = merge(host, "--base-ref", "main")
    assert report.status("merge-open-items") == "PASS" and report.status("third-party-pins") == "PASS" and report.status("merge-bindings") == "SKIP"
    assert report.codes == plain(host).codes, "the merge mode adds no finding to the example"
    assert "spec-check: 31 checks run, 24 errors, 1 warnings" in report.out


# --- open items -----------------------------------------------------------------------------------------------------


def add_open_item(host: Path) -> None:
    run(host, "json", "patch", str(host / PLAN), ".execution.emergent_ambiguities", f"[{(FX / 'open_item.json').read_text(encoding='utf-8')}]")


def test_open_item_fails_merge_not_step_mode(host: Path) -> None:
    add_open_item(host)
    commit_all(host, "an open item")
    step_run = report_of(run(host, "spec-check", str(host / "spec"), "--step", "16", want=None))
    assert "E631" not in step_run.out and plain(host).codes["E631"] == 0
    assert plain(host).codes["W630"] == 1, "the step gate says W630 for it"
    report = merge(host, "--base-ref", "main")
    assert report.status("merge-open-items") == "FAIL" and report.codes["E631"] == 1 and "amb-token-store" in report.out


def test_a_legacy_open_item_in_a_closed_plan_is_listed_not_failed(host: Path) -> None:
    add_open_item(host)
    close(host)
    report = merge(host, "--base-ref", "main")
    assert report.status("merge-open-items") == "WARN" and report.codes["W633"] == 1 and report.codes["E631"] == 0


# --- the trace lock: the registered check says it in every mode ------------------------------------------------------


def test_suspect_link_fails_merge(host: Path) -> None:
    path = host / LOCK
    document = json.loads(path.read_text(encoding="utf-8"))
    entry = next(e for e in document["entries"] if e["source"] == "nfr-latency-reset-email" and e["target"] == "tp-mailrelay")
    entry["chain_stamp"] = "sha256:" + "0" * 64
    write_json(path, document)
    commit_all(host, "a suspect link")
    report = merge(host, "--base-ref", "main")
    assert report.status("trace-lock") == "FAIL" and report.codes["E763"] == 1 and "nfr-latency-reset-email" in report.out


def test_orphan_lock_entry_fails_merge(host: Path) -> None:
    path = host / LOCK
    document = json.loads(path.read_text(encoding="utf-8"))
    document["entries"].append({**document["entries"][0], "source": "tc-no-such-node"})
    write_json(path, document)
    commit_all(host, "an orphan entry")
    report = merge(host, "--base-ref", "main")
    assert report.status("trace-lock") == "FAIL" and report.codes["E762"] >= 1 and "tc-no-such-node" in report.out


# --- pins ------------------------------------------------------------------------------------------------------------


def declare_pin(host: Path, lock_version: str) -> None:
    """Declare that the pin of ``tp-argon2`` is the version in the host's ``package-lock.json`` (the pin is 0.41.1), and write the file."""
    write_json(host / "package-lock.json", {"packages": {"node_modules/argon2": {"version": lock_version}}})
    write_json(host / "spec" / "common" / "host_declarations.json", {
        "$schema": "vc:host-declarations",
        "pin_sources": {"tp-argon2": [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version"}]},
    })
    commit_all(host, f"the lock file says {lock_version}")


def test_pin_mismatch_fails_merge_and_plain(host: Path) -> None:
    declare_pin(host, "0.41.1")
    assert merge(host, "--base-ref", "main").status("third-party-pins") == "PASS", "a matching pin passes"
    declare_pin(host, "0.40.0")
    assert plain(host).codes["E337"] == 1, "the plain run reads the pin sources too (the check of step 02, third-party-pins)"
    report = merge(host, "--base-ref", "main")
    assert report.status("third-party-pins") == "FAIL" and report.codes["E337"] == 1 and "0.40.0" in report.out
    assert "merge-pins" not in report.out, "one check per fact: the merge run does not read the pin sources a second time"
    header = re.compile(r"spec-check: (\d+) checks run, (\d+) errors")
    assert int(header.search(report.out).group(2)) == int(header.search(plain(host).out).group(2)), "the merge run counts the pin finding once"
    declare_pin(host, "0.41.1")
    assert merge(host, "--base-ref", "main").status("third-party-pins") == "PASS", "making them equal clears it"


# --- the milestones the branch closes and their bindings --------------------------------------------------------------


def bind_second(host: Path, commands: list[str], stage: str) -> None:
    """Bind the second fixture (it proves a criterion of the same milestone) and give it *commands* at *stage*."""
    run(host, "verify", "bind", SECOND_FIXTURE, "--command", "true", "--guard", ".*")
    set_binding(host, SECOND_BINDING, commands, stage)
    commit_all(host, f"a {stage} binding")


def test_branch_closing_milestone_runs_dev_and_ci_bindings(host: Path, spy: list[tuple[list[str], dict[str, Any]]]) -> None:
    bind_second(host, FAILING, "ci")
    close(host)
    report = merge(host, "--base-ref", "main")
    (ids, keywords), = spy
    assert ids == [BINDING, SECOND_BINDING] and keywords["record"] is False and keywords["stage"] == "ci"
    assert report.status("merge-bindings") == "FAIL" and report.codes["E901"] == 1, "the dev binding passes, the CI binding fails"
    assert SECOND_BINDING in report.out and "exit code 3" in report.out and f"of {MS}" in report.out


def test_a_staging_binding_is_not_run_at_merge(host: Path, spy: list[tuple[list[str], dict[str, Any]]]) -> None:
    bind_second(host, FAILING, "staging")
    close(host)
    report = merge(host, "--base-ref", "main")
    assert [ids for ids, _ in spy] == [[BINDING]]
    assert report.status("merge-bindings") == "PASS" and report.codes["E901"] == 0


def test_failing_binding_is_E901(host: Path) -> None:
    set_binding(host, BINDING, FAILING)
    close(host)
    report = merge(host, "--base-ref", "main")
    assert report.status("merge-bindings") == "FAIL" and report.codes["E901"] == 1
    assert f"binding '{BINDING}' of {MS}, which this branch closes, failed in this run: exit code 3" in report.out
    set_binding(host, BINDING, PASSING)
    commit_all(host, "the binding passes again")
    assert merge(host, "--base-ref", "main").status("merge-bindings") == "PASS", "a binding that passes clears it"


def test_milestone_closed_on_base_is_not_rerun(template: Path, tmp_path: Path, spy: list[tuple[list[str], dict[str, Any]]]) -> None:
    host = clone(template, tmp_path)
    set_binding(host, BINDING, FAILING)
    close(host)
    git(host, "checkout", "-q", "-b", "feature")
    (host / "notes.txt").write_text("unrelated", encoding="utf-8")
    commit_all(host, "an unrelated change")
    report = merge(host, "--base-ref", "main")
    assert spy == [] and report.status("merge-bindings") == "SKIP" and report.codes["E901"] == 0


def test_new_milestone_done_in_branch_runs_bindings(template: Path, tmp_path: Path, spy: list[tuple[list[str], dict[str, Any]]]) -> None:
    host = clone(template, tmp_path)
    original = read(host, ANCHOR)["plan"]["milestone_index"]
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"].update(milestone_index=[]))
    commit_all(host, "no row yet")
    git(host, "checkout", "-q", "-b", "feature")
    set_binding(host, BINDING, FAILING)
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"].update(milestone_index=[{**original[0], "status": "done", "close": {"signed_off_by": "Ada Lovelace"}}]))
    commit_all(host, "the milestone arrives done")
    report = merge(host, "--base-ref", "main")
    assert [ids for ids, _ in spy] == [[BINDING]] and report.codes["E901"] == 1


def test_missing_anchor_at_base_counts_as_not_done(template: Path, tmp_path: Path, spy: list[tuple[list[str], dict[str, Any]]]) -> None:
    host = clone(template, tmp_path)
    anchor = (host / ANCHOR).read_text(encoding="utf-8")
    (host / ANCHOR).unlink()
    commit_all(host, "no anchor file")
    git(host, "checkout", "-q", "-b", "feature")
    (host / ANCHOR).write_text(anchor, encoding="utf-8")
    set_binding(host, BINDING, FAILING)
    mark_done(host)
    commit_all(host, "the anchor file arrives, done")
    report = merge(host, "--base-ref", "main")
    assert [ids for ids, _ in spy] == [[BINDING]] and report.codes["E901"] == 1


def test_root_commit_base_is_empty_tree(host: Path, spy: list[tuple[list[str], dict[str, Any]]]) -> None:
    set_binding(host, BINDING, FAILING)
    mark_done(host)
    shutil.rmtree(host / ".git")
    git(host, "init", "-q", "-b", "main")
    commit_all(host, "one commit")
    report = merge(host, "--base-ref", NULL_SHA)
    assert "E900" not in report.out and [ids for ids, _ in spy] == [[BINDING]] and report.codes["E901"] == 1, "every done milestone counts as closed"


def test_legacy_closed_milestone_not_rerun_in_merge(host: Path, spy: list[tuple[list[str], dict[str, Any]]]) -> None:
    set_binding(host, BINDING, FAILING)
    edit_doc(host, "16_impl_context.json", lambda doc: doc["plan"]["milestone_index"][0].update(status="done", close={"signed_off_by": "legacy-migration", "source": "the status column of the roadmap", "signoff": None}))
    commit_all(host, "closed by the migration")
    report = merge(host, "--base-ref", "main")
    assert spy == [] and report.status("merge-bindings") == "SKIP" and report.codes["E901"] == 0


def test_branch_updated_after_close_still_passes_because_run_is_proof(host: Path, spy: list[tuple[list[str], dict[str, Any]]]) -> None:
    close(host)
    (host / "src").mkdir()
    (host / "src" / "later.py").write_text("print('written after the close')\n", encoding="utf-8")
    commit_all(host, "an unrelated code file after the close")
    report = merge(host, "--base-ref", "main")
    assert [ids for ids, _ in spy] == [[BINDING]] and report.status("merge-bindings") == "PASS"


def test_default_branch_push_base_is_before_or_first_parent(template: Path, tmp_path: Path) -> None:
    host = clone(template, tmp_path)
    before = git(host, "rev-parse", "HEAD")
    set_binding(host, BINDING, FAILING)
    close(host)
    assert merge(host, "--base-ref", before).codes["E901"] == 1, "the push's before commit is the base"
    assert merge(host, "--base-ref", UNKNOWN_SHA).codes["E901"] == 1, "a before commit this clone lacks gives the first parent"
    assert merge(host, "--base-ref", NULL_SHA).codes["E901"] == 1, "so does the null commit of a first push"


def test_merge_mode_does_not_check_signoff(host: Path) -> None:
    close(host)
    assert not list((host / "spec" / "extras").glob("signoff*")), "the milestone has no sign-off"
    report = merge(host, "--base-ref", "main")
    assert report.codes["E814"] == 0 and report.status("merge-bindings") == "PASS"


def test_merge_mode_leaves_working_tree_clean(host: Path) -> None:
    close(host)
    before = sorted(path.name for path in (host / VERIFICATION).iterdir())
    report = merge(host, "--base-ref", "main")
    assert report.status("merge-bindings") == "PASS"
    assert git(host, "status", "--porcelain") == "", "nothing was written"
    assert sorted(path.name for path in (host / VERIFICATION).iterdir()) == before, "no evidence file was stored"


# --- the base at the command line -------------------------------------------------------------------------------------


def test_cli_push_null_sha_base_falls_back_to_first_parent(host: Path) -> None:
    close(host)
    report = merge(host, "--base-ref", NULL_SHA)
    assert "E900" not in report.out and report.status("merge-bindings") == "PASS"


def test_cli_push_unknown_before_sha_falls_back_to_first_parent(host: Path) -> None:
    close(host)
    report = merge(host, "--base-ref", UNKNOWN_SHA)
    assert "E900" not in report.out and report.status("merge-bindings") == "PASS"


def test_an_unresolvable_base_is_one_E900_in_the_bindings_check(host: Path) -> None:
    close(host)
    report = merge(host, "--base-ref", "origin/nowhere")
    assert report.status("merge-bindings") == "FAIL" and report.codes["E900"] == 1 and "origin/nowhere" in report.out
    assert report.status("merge-open-items") == "PASS", "the other merge checks still ran"
