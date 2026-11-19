"""``specdev stale`` end to end, on the worked example in a git repository (WI-M5-05)."""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.build import build_graph
from specdev_tools.trace import history
from specdev_tools.trace.history import MAX_COMMITS, NOTE_BASELINE, NOTE_NO_EARLIER, NOTE_NO_HISTORY, OldTextResolver
from specdev_tools.trace.lockfile import Lock, lock_path, read_lock, write_lock
from specdev_tools.trace.merge_driver import install_driver

from unit.graph._synth import ROOT, git, run_cli
from unit.trace._lock_support import EXAMPLE_HOST
from unit.trace.test_suspects import CRITERION, Example

from .test_merge_driver_git import DRIVER_COMMAND

FR_FILE = "04_fr_list.json"
RENAMED = "ac-password-reset-3b"
API = "api-password-reset-confirm"
INVARIANT = "inv-reset-token-single-use"
EDIT = " Also reject a token issued for another account."
DAG_ORDER = ["05", "06", "07", "08", "09", "11", "14", "15", "16a"]
# DOC L2144: the nodes the criterion edit puts into replay, one per kind the document names.
NAMED_NODES = {
    "err-password-reset-confirm-token-expired", "fix-password-reset-expired-token", INVARIANT, "nfr-latency-reset-email",
    "threat-reset-token-replay", "scaffold-password-reset-confirm", "milestone-account-recovery", "tc-confirm-expired-token",
    "PWRESET_CONFIRM_EXPIRED_01",
}


@pytest.fixture
def host(tmp_path: Path) -> Example:
    """The worked example (spec, seed docs and a current lock) in a git repository with one commit."""
    root = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, root)
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "one")
    return Example(root)


def _commit(example: Example, message: str) -> None:
    git(example.host, "add", "-A")
    git(example.host, "commit", "-q", "-m", message)


def _edit_criterion(example: Example) -> None:
    example.edit_item(CRITERION, lambda item: item.update(text=item["text"] + EDIT))


def _stale(example: Example, *args: str) -> tuple[int, str]:
    return run_cli("stale", *args, "--repo-root", str(ROOT), "--spec-root", str(example.spec), "--git-root", str(example.host))


def _stale_json(example: Example, *args: str) -> dict[str, Any]:
    code, out = _stale(example, *args, "--json")
    assert code == 0, out
    return json.loads(out)


def _rewrite_entries_to(example: Example, target: str, **changes: Any) -> None:
    lock = example.lock()
    write_lock(str(example.spec), Lock(tuple(replace(entry, **changes) if entry.target == target else entry for entry in lock.entries)))


# --- the listing ----------------------------------------------------------------------------------------------------

def test_stale_lists_pending_by_step_in_dag_order(host: Example) -> None:
    _edit_criterion(host)
    document = _stale_json(host)
    assert [step["step"] for step in document["steps"]] == DAG_ORDER
    listed = {node["node"] for step in document["steps"] for node in step["suspect_nodes"]}
    assert NAMED_NODES <= listed
    code, text = _stale(host)
    assert code == 0
    assert [line.split(":")[0] for line in text.splitlines() if line.startswith("step ")] == [f"step {step}" for step in DAG_ORDER]
    assert text.splitlines()[0] == "stale: pending replay by step"
    assert "  api-password-reset-confirm\n    derives_from -> fr-password-reset (content_changed, roots: ac-password-reset-3)" in text
    assert text.splitlines()[-1] == "total: 21 suspect links in 13 nodes, 0 coverage gaps"


def test_stale_with_nothing_pending_exits_0(host: Example) -> None:
    assert _stale(host) == (0, "stale: no pending replay\n")


def test_stale_step_slice_only_upstream_into_nn(host: Example) -> None:
    """Only a step 05 node changed: ``--step 06`` lists the suspects step 06 holds and none held by a later step."""
    host.edit_item(API, lambda item: item.update(path="/v2/password-resets/{token}"))
    everything = _stale_json(host)
    assert [step["step"] for step in everything["steps"]][:3] == ["06", "08", "11"]
    sliced = _stale_json(host, "--step", "06")
    assert [step["step"] for step in sliced["steps"]] == ["06"]
    assert [node["node"] for node in sliced["steps"][0]["suspect_nodes"]] == [INVARIANT]
    assert [(link["target"], link["roots"]) for link in sliced["steps"][0]["suspect_nodes"][0]["links"]] == [(API, [API])]
    assert sliced["totals"] == {"suspect_nodes": 1, "suspect_links": 1, "coverage_gaps": 0}
    assert _stale_json(host, "--step", "05")["steps"] == []
    assert _stale_json(host, "--step", "10")["steps"] == []


@pytest.mark.parametrize("step", ["99", "6", "seed"])
def test_stale_step_that_is_not_a_step_of_the_pipeline_is_e706_as_text_and_json(host: Example, step: str) -> None:
    code, text = _stale(host, "--step", step)
    assert code == 1 and text.startswith("E706") and f"no step {step!r}" in text and "known steps: 00, 01, 02, 02a" in text
    code, out = _stale(host, "--step", step, "--json")
    assert code == 1
    (error,) = json.loads(out)["errors"]
    assert error["code"] == "E706" and f"no step {step!r}" in error["message"]


def test_stale_json_schema_stable(host: Example) -> None:
    _edit_criterion(host)
    document = _stale_json(host)
    assert set(document) == {"steps", "totals"}
    assert set(document["totals"]) == {"suspect_nodes", "suspect_links", "coverage_gaps"}
    step = document["steps"][0]
    assert set(step) == {"step", "suspect_nodes", "coverage_gaps"}
    node = step["suspect_nodes"][0]
    assert set(node) == {"node", "links"}
    assert set(node["links"][0]) == {"field", "target", "cause", "roots"}
    assert node["links"][0]["cause"] in {"content_changed", "upstream_changed"}
    assert set(_stale_json(host, "--diff")) == {"steps", "totals", "diffs"}


# --- the old text ---------------------------------------------------------------------------------------------------

def test_old_text_from_hash_matching_commit(host: Example) -> None:
    _edit_criterion(host)
    _commit(host, "two")
    document = _stale_json(host, "--diff")
    (diff,) = document["diffs"]
    assert diff["root"] == CRITERION and diff["note"] is None
    removed = [line for line in diff["diff"] if line.startswith("-text: ")]
    added = [line for line in diff["diff"] if line.startswith("+text: ")]
    assert len(removed) == len(added) == 1 and added[0] == removed[0].replace("-", "+", 1) + EDIT
    code, text = _stale(host, "--diff")
    assert code == 0 and f"changed above: {CRITERION}" in text and f"  {removed[0]}" in text


def test_old_text_of_a_seed_is_read_from_the_seed_file_at_the_commit(host: Example) -> None:
    """The seed document sits beside ``spec/``, not in it: its text at the commit comes from the git root."""
    host.edit_seed()
    _commit(host, "two")
    document = _stale_json(host, "--diff")
    (diff,) = (item for item in document["diffs"] if item["root"] == "seed-accounts")
    assert diff["note"] is None
    assert [line for line in diff["diff"] if line.startswith("+") and not line.startswith("+++")] == ["+The link is also sent to the member's phone."]


@pytest.mark.parametrize(
    ("setup", "note"),
    [
        ("bogus hash", NOTE_NO_EARLIER),
        ("baseline", NOTE_BASELINE),
        ("no git", NOTE_NO_HISTORY),
    ],
)
def test_old_text_fallbacks_are_printed_not_silent(host: Example, tmp_path: Path, setup: str, note: str) -> None:
    _edit_criterion(host)
    _commit(host, "two")
    if setup == "bogus hash":
        _rewrite_entries_to(host, CRITERION, content_hash="sha256:" + "0" * 64)
    elif setup == "baseline":
        _rewrite_entries_to(host, CRITERION, baseline=True)
    else:
        shutil.rmtree(host.host / ".git")
    code, text = _stale(host, "--diff")
    assert code == 0
    assert f"changed above: {CRITERION}\n  ({note})" in text


def _contract_fields_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """After this, ``text`` is no contract field: no hash computed before matches the same text now."""
    monkeypatch.setattr("specdev_tools.graph.contract.EXCLUDED_FIELDS", frozenset({"status", "notes", "tags", "owner", "text"}))


def test_old_text_falls_back_when_contract_fields_changed(host: Example, monkeypatch: pytest.MonkeyPatch) -> None:
    _edit_criterion(host)
    _commit(host, "two")
    _contract_fields_change(monkeypatch)
    code, text = _stale(host, "--diff")
    assert code == 0
    assert f"changed above: {CRITERION}\n  ({NOTE_NO_EARLIER})" in text


def test_the_resolver_probes_at_most_fifty_commits_of_the_target_file(host: Example, monkeypatch: pytest.MonkeyPatch) -> None:
    for number in range(MAX_COMMITS + 5):
        host.edit_item(CRITERION, lambda item, n=number: item.update(notes=f"note {n}"))
        _commit(host, f"touch {number}")
    _contract_fields_change(monkeypatch)
    graph = build_graph(str(host.spec), str(ROOT))
    entry = next(entry for entry in read_lock(str(host.spec)).entries if entry.target == CRITERION)
    probed: list[str] = []
    real = history.load_graph_at
    monkeypatch.setattr(history, "load_graph_at", lambda commit, *rest: probed.append(commit) or real(commit, *rest))
    resolver = OldTextResolver(graph, git_root=str(host.host), spec_root=str(host.spec), repo_root=str(ROOT))
    answer = resolver.old_text(entry)
    assert (answer.lines, answer.note) == (None, NOTE_NO_EARLIER)
    assert len(probed) == MAX_COMMITS == len(set(probed))


def test_rename_and_merge_driver_commits_do_not_hide_old_text(host: Example) -> None:
    """After the edit, a real ``node rename`` commit (it touches the target's file and re-keys the lock) and a real merge
    commit made by the lock merge driver sit between the edit and today; the old text of the changed criterion is still found."""
    install_driver(str(host.host), "spec", DRIVER_COMMAND)
    _edit_criterion(host)
    _commit(host, "two")
    git(host.host, "checkout", "-q", "-b", "theirs")
    host.attest("api-password-reset-confirm")
    _commit(host, "three: another holder attested on a branch")
    git(host.host, "checkout", "-q", "main")
    code, out = run_cli("node", "rename", CRITERION, RENAMED, "--repo-root", str(ROOT), "--spec-root", str(host.spec), "--git-root", str(host.host))
    assert code == 0, out
    _commit(host, "four: node rename")
    git(host.host, "merge", "--no-edit", "theirs")
    assert "<<<<<<<" not in Path(lock_path(str(host.spec))).read_text(encoding="utf-8")
    assert (host.spec / FR_FILE).read_text(encoding="utf-8").count(RENAMED) == 1
    (diff,) = _stale_json(host, "--diff")["diffs"]
    assert diff["note"] is None
    assert [line for line in diff["diff"] if line.startswith("+text: ")][0].endswith(EDIT)


# --- which accepted version a diff is against (review M5 R1, F1-3) --------------------------------------------------------

ERR_HOLDER = "err-password-reset-confirm-token-expired"
UNCHANGED_NOTE = "its own contract text is unchanged"


def _attest(example: Example, *args: str) -> None:
    code, out = run_cli("attest", *args, "--yes", "--repo-root", str(ROOT), "--spec-root", str(example.spec), "--git-root", str(example.host))
    assert code == 0, out


def _set_criterion_text(example: Example, suffix: str) -> None:
    example.edit_item(CRITERION, lambda item: item.update(text=item["text"].split(" #")[0] + suffix))
    _commit(example, f"criterion{suffix}")


def _diffs_of(example: Example, root: str) -> list[dict[str, Any]]:
    return [diff for diff in _stale_json(example, "--diff")["diffs"] if diff["root"] == root]


def test_diff_after_one_holder_of_the_root_was_attested_still_shows_the_change(host: Example) -> None:
    """A1-02: the holders attested first had accepted the change; the first entry in lock order must not decide the old text."""
    _set_criterion_text(host, " #1")
    for holder in (API, "fix-password-reset-expired-token", "ec-token-at-expiry-second"):
        _attest(host, holder)
    assert ERR_HOLDER in {node["node"] for step in _stale_json(host)["steps"] for node in step["suspect_nodes"]}
    code, out = _stale(host, "--diff")
    assert code == 0 and UNCHANGED_NOTE not in out, out
    (diff,) = _diffs_of(host, CRITERION)
    assert diff["note"] is None and any(line.startswith("-text: Given a reset token") for line in diff["diff"])
    assert any(line.startswith("+text:") and line.endswith("#1") for line in diff["diff"])
    preview = run_cli("attest", ERR_HOLDER, "--repo-root", str(ROOT), "--spec-root", str(host.spec), "--git-root", str(host.host))[1]
    assert UNCHANGED_NOTE not in preview and "+text:" in preview


def test_diff_of_two_edits_with_an_attest_between_shows_each_accepted_version(host: Example) -> None:
    """C-04: ``err-`` accepted the first edit, the others the original; each diff is against the version its holders accepted."""
    _set_criterion_text(host, " #1")
    _attest(host, ERR_HOLDER)
    _set_criterion_text(host, " #2")
    diffs = _diffs_of(host, CRITERION)
    assert len(diffs) == 2
    by_holders = {tuple(diff["accepted_by"]): diff["diff"] for diff in diffs}
    assert (ERR_HOLDER,) in by_holders
    after_err = by_holders.pop((ERR_HOLDER,))
    assert any(line.startswith("-text:") and line.endswith("#1") for line in after_err)
    assert any(line.startswith("+text:") and line.endswith("#2") for line in after_err)
    (others,) = by_holders.values()
    assert any(line.startswith("-text: Given a reset token") for line in others)
    text = _stale(host, "--diff")[1]
    assert f"changed above: {CRITERION} (as accepted by {ERR_HOLDER})" in text


def test_diff_after_the_text_was_restored_is_against_what_the_holder_accepted(host: Example) -> None:
    """C-04: ``err-`` accepted the first edit and the text went back to the original: still suspect, and the diff says what changed."""
    _set_criterion_text(host, " #1")
    _attest(host, ERR_HOLDER)
    host.edit_item(CRITERION, lambda item: item.update(text=item["text"].split(" #")[0]))
    _commit(host, "restored")
    (diff,) = _diffs_of(host, CRITERION)
    assert diff["note"] is None and diff["accepted_by"] == []
    assert any(line.startswith("-text:") and line.endswith("#1") for line in diff["diff"])
    assert not any(UNCHANGED_NOTE in line for line in diff["diff"])


def test_upstream_links_with_no_root_left_say_the_change_was_already_accepted(host: Example) -> None:
    """B8: every holder that pointed at the changed node accepted it; the links below show no root, and one line says why."""
    _set_criterion_text(host, " #1")
    for step in ("05", "06", "07", "08", "09", "11", "14"):
        _attest(host, "--step", step)
    code, out = _stale(host, "--diff")
    note = "changed upstream with no root left: the change above was already accepted by the links that point at it"
    assert code == 0 and out.count(note) == 1 and "changed above" not in out, out
    assert note not in _stale(host)[1]
