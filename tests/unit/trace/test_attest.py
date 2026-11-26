"""``specdev attest`` and ``attest --prune`` (WI-M5-06), on the worked example."""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.trace.attest import plan_node_attest, plan_step_attest, prune_text, prune_to_dict
from specdev_tools.trace.lockfile import Lock, LockEntry, lock_path, serialise_lock
from specdev_tools.trace.suspects import check_lock_orphans, missing_entries

from ..graph._synth import ROOT, git, run_cli
from ._lock_support import EXAMPLE_HOST
from ._suspects_support import CLOSED_HOLDERS, CRITERION, Example

API = "api-password-reset-confirm"
FIX_EXPIRED = "fix-password-reset-expired-token"
FIX_REUSED = "fix-password-reset-reused-token"
ERROR = "err-password-reset-confirm-token-expired"  # the fixtures `expects` it
INVARIANT = "inv-reset-token-single-use"
TASK_CRITERION = "tc-confirm-expired-token"
NEED = "need-fewer-reset-tickets"
NFR = "nfr-latency-reset-email"


@pytest.fixture
def example(tmp_path: Path) -> Example:
    """The worked example (spec, seed docs and a current lock) in a git repository with one commit."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    git(host, "init", "-q", "-b", "main")
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "one")
    return Example(host)


def _attest(example: Example, *args: str) -> tuple[int, str]:
    return run_cli("attest", *args, "--repo-root", str(ROOT), "--spec-root", str(example.spec), "--git-root", str(example.host))


def _attest_json(example: Example, *args: str, code: int = 0) -> dict[str, Any]:
    status, out = _attest(example, *args, "--json")
    assert status == code, out
    return json.loads(out)


def _lock_text(example: Example) -> str:
    return Path(lock_path(str(example.spec))).read_text(encoding="utf-8")


def _holders(document: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(link["holder"] for link in document["attested"]))


def _suspect_holders(example: Example) -> set[str]:
    return {holder for holder, _field, _target in example.suspect_keys()}


# --- one node ---------------------------------------------------------------------------------------------------------

def test_attest_shows_old_and_new_text_then_writes_only_with_yes(example: Example) -> None:
    example.edit_criterion()
    before = _lock_text(example)
    code, out = _attest(example, API)
    assert code == 0
    assert out.splitlines()[0] == "attest: would write 1 link on 1 node (run again with --yes to write)"
    assert "derives_from -> fr-password-reset (suspect, content_changed)" in out
    assert f"changed above: {CRITERION}" in out and "+text:" in out and "Also reject a token" in out
    assert _lock_text(example) == before
    code, out = _attest(example, API, "--yes", "--dry-run")
    assert code == 0 and _lock_text(example) == before
    assert out.splitlines()[0] == "attest: would write 1 link on 1 node (--dry-run: nothing is written)"  # not "run again with --yes"
    code, out = _attest(example, API, "--yes")
    assert code == 0 and out.splitlines()[0] == "attest: wrote 1 link on 1 node"
    assert _lock_text(example) != before and API not in _suspect_holders(example)


def test_attest_refused_while_target_is_suspect_node(example: Example) -> None:
    example.edit_criterion()
    before = _lock_text(example)
    code, out = _attest(example, TASK_CRITERION, "--yes")
    assert code == 1 and out.startswith("E764") and FIX_EXPIRED in out
    assert _lock_text(example) == before
    for node in (API, ERROR, FIX_EXPIRED, TASK_CRITERION):
        code, out = _attest(example, node, "--yes")
        assert code == 0, out
    assert TASK_CRITERION not in _suspect_holders(example)


def test_attest_refused_on_historical_link(example: Example) -> None:
    example.edit_criterion()
    example.close_milestone()
    before = _lock_text(example)
    assert TASK_CRITERION in CLOSED_HOLDERS
    code, out = _attest(example, TASK_CRITERION, "--yes")
    assert code == 1 and out.startswith("E765") and TASK_CRITERION in out
    assert _lock_text(example) == before


def test_attest_updates_both_values_and_clears_baseline(example: Example) -> None:
    original = example.lock()
    stale = tuple(
        replace(entry, content_hash=original.entries[0].content_hash, chain_stamp=original.entries[0].chain_stamp, baseline=True)
        if entry.source == API else entry
        for entry in original.entries
    )
    example.write_lock(Lock(stale))
    assert any(entry.baseline for entry in example.lock().entries)
    code, out = _attest(example, API, "--yes")
    assert code == 0, out
    assert example.lock() == original and "baseline" not in _lock_text(example)


def test_attest_clears_a_baseline_marker_on_a_current_entry(example: Example) -> None:
    original = example.lock()
    example.write_lock(Lock(tuple(replace(entry, baseline=True) if entry.source == API else entry for entry in original.entries)))
    document = _attest_json(example, API, "--yes")
    assert {link["reason"] for link in document["attested"]} == {"baseline"}
    assert example.lock() == original


def test_attest_creates_missing_entry(example: Example) -> None:
    original = _lock_text(example)
    example.drop_entries(lambda entry: entry.source == API)
    assert {item.holder.id for item in missing_entries(example.graph(), example.lock())} == {API}
    document = _attest_json(example, API, "--yes")
    assert {link["reason"] for link in document["attested"]} == {"missing"} and all(link["old"] is None for link in document["attested"])
    assert _lock_text(example) == original


def test_attest_field_and_target_narrow_the_links(example: Example) -> None:
    example.drop_entries(lambda entry: entry.source == NFR)
    assert len(_attest_json(example, NFR)["attested"]) == 3
    by_field = _attest_json(example, NFR, "--field", "relies_on")["attested"]
    assert [(link["field"], link["target"]) for link in by_field] == [("relies_on", "tp-mailrelay")]
    by_target = _attest_json(example, NFR, "--target", "fr-password-reset")["attested"]
    assert [(link["field"], link["target"]) for link in by_target] == [("constrains", "fr-password-reset")]
    code, out = _attest(example, NFR, "--field", "no_such_field")
    assert code == 1 and out.startswith("E706") and NFR in out


def test_attest_target_takes_an_alias_after_a_rename_and_the_e706_names_the_flags_given(example: Example) -> None:
    """``--target`` is an id or an alias: the link now spells the new id, the old id is an alias of the same node."""
    code, out = run_cli(
        "node", "rename", "fr-password-reset", "fr-password-reset-flow",
        "--repo-root", str(ROOT), "--spec-root", str(example.spec), "--git-root", str(example.host),
    )
    assert code == 0, out
    example.drop_entries(lambda entry: entry.source == NFR)
    by_alias = _attest_json(example, NFR, "--target", "fr-password-reset")["attested"]
    assert [(link["field"], link["target"]) for link in by_alias] == [("constrains", "fr-password-reset-flow")]
    assert _attest_json(example, NFR, "--target", "fr-password-reset-flow")["attested"] == by_alias
    code, out = _attest(example, NFR, "--target", "fr-no-such-node")
    assert code == 1 and out.startswith("E706") and "holds no link with target fr-no-such-node" in out and "any" not in out
    code, out = _attest(example, NFR, "--field", "nope", "--target", "fr-password-reset")
    assert code == 1 and "holds no link with field nope and target fr-password-reset" in out


def test_attest_with_nothing_to_do_says_so_and_writes_nothing(example: Example) -> None:
    before = _lock_text(example)
    code, out = _attest(example, API, "--yes")
    assert (code, out.strip()) == (0, "attest: nothing to attest") and _lock_text(example) == before


def test_attest_unknown_id_is_e706_with_nearest_ids_exit_1_and_duplicate_id_is_refused(example: Example) -> None:
    example.edit_criterion()
    before = _lock_text(example)
    code, out = _attest(example, "api-password-reset-confirmm", "--yes")
    assert code == 1 and out.startswith("E706") and f"nearest: {API}" in out
    code, out = _attest(example, "no-such-node", "--yes", "--json")
    assert code == 1 and json.loads(out)["errors"][0]["code"] == "E706"
    path = example.spec / "04_fr_list.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["functional_requirements"].append(dict(document["functional_requirements"][0]))
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    code, out = _attest(example, "fr-password-reset", "--yes")
    assert code == 1 and out.startswith("E704") and "fr-password-reset" in out and "E764" not in out and "E765" not in out
    assert _lock_text(example) == before


# --- a group of nodes -------------------------------------------------------------------------------------------------

def test_attest_group_orders_upward_first_in_one_invocation(example: Example) -> None:
    example.edit_seed()
    document = _attest_json(example, "--step", "00", "--yes")
    holders = _holders(document)
    assert document["blocked"] == [] and document["written"] is True
    assert holders.index(NEED) < holders.index("metric-recovery-time") and holders.index("asm-member-controls-email") < holders.index("risk-reset-link-takeover")
    assert not {holder for holder in _suspect_holders(example) if example.graph().by_id[holder].step == "00"}


def test_attest_step_writes_what_it_can_and_names_the_blocked_nodes(example: Example) -> None:
    example.edit_criterion()
    assert _attest(example, API, "--yes")[0] == 0
    assert _attest(example, ERROR, "--yes")[0] == 0
    document = _attest_json(example, "--step", "08", "--yes", code=1)
    assert _holders(document) == [FIX_EXPIRED] and document["written"] is True
    assert [blocked["node"] for blocked in document["blocked"]] == [FIX_REUSED]
    assert document["blocked"][0]["blockers"] == [{"field": "verifies", "target": INVARIANT}]
    code, out = _attest(example, "--step", "08")
    assert code == 1 and "E764" in out and INVARIANT in out
    assert FIX_EXPIRED not in _suspect_holders(example) and FIX_REUSED in _suspect_holders(example)


def test_attest_step_with_nothing_pending_is_a_clean_no_op(example: Example) -> None:
    before = _lock_text(example)
    code, out = _attest(example, "--step", "08", "--yes")
    assert (code, out.strip()) == (0, "attest: nothing to attest") and _lock_text(example) == before


def test_planning_writes_nothing_and_blocks_the_nodes_of_a_later_step(example: Example) -> None:
    example.edit_criterion()
    graph, lock = example.graph(), example.lock()
    seed_texts = example.seed_texts(graph)
    plan = plan_step_attest(graph, lock, seed_texts, "14")
    assert plan.links == () and {blocked.node for blocked in plan.blocked} == {TASK_CRITERION, "tc-confirm-reused-token"}
    node_plan = plan_node_attest(graph, lock, seed_texts, API)
    assert [link.new.target for link in node_plan.links] == ["fr-password-reset"] and node_plan.blocked == ()


# --- prune ------------------------------------------------------------------------------------------------------------

def _add_orphan(example: Example) -> LockEntry:
    orphan = replace(example.lock().entries[0], source=API, field="derives_from", target="fr-no-longer-linked")
    example.write_lock(Lock((*example.lock().entries, orphan)))
    return orphan


def test_prune_removes_orphans_and_ci_check_reports_them(example: Example) -> None:
    original = _lock_text(example)
    orphan = _add_orphan(example)
    graph = example.graph()
    assert [error.code for error in check_lock_orphans(graph, example.lock())] == ["E762"]
    kept = _lock_text(example)
    code, out = _attest(example, "--prune", "--dry-run")
    assert code == 0 and "would remove 1 orphan entry" in out and orphan.target in out and _lock_text(example) == kept
    code, out = _attest(example, "--prune")
    assert code == 0 and "removed 1 orphan entry" in out
    assert check_lock_orphans(example.graph(), example.lock()) == [] and _lock_text(example) == original
    assert _attest(example, "--prune")[1].strip() == "attest --prune: no orphan entries"


def test_prune_text_and_dict_give_the_records_after_the_entries_and_an_empty_list_without_records(example: Example) -> None:
    orphan = _add_orphan(example)
    records = ["extras/verification/ver-x.json"]
    assert prune_text((), written=False, records=records) == "attest --prune: would remove 1 orphan record\n  extras/verification/ver-x.json"
    assert prune_text((orphan,), written=True, records=records).splitlines()[-2:] == ["attest --prune: removed 1 orphan record", "  extras/verification/ver-x.json"]
    assert prune_text((orphan,), written=True).count("attest --prune:") == 1 and prune_text((), written=True) == "attest --prune: no orphan entries"
    assert prune_to_dict((), written=False) == {"written": False, "pruned": [], "pruned_records": []}
    assert prune_to_dict((orphan,), written=True, records=records)["pruned_records"] == records


def test_crash_during_delete_leaves_orphan_entry_that_prune_repairs(example: Example) -> None:
    """A link is deleted from its spec file and the process dies before the lock is written: the entry is an orphan."""
    original = example.lock()
    example.edit_item(NFR, lambda item: item.pop("relies_on"))
    graph = example.graph()
    assert [error.code for error in check_lock_orphans(graph, original)] == ["E762"]
    code, out = _attest(example, "--prune")
    assert code == 0 and "nfr-latency-reset-email: relies_on -> tp-mailrelay" in out
    assert check_lock_orphans(example.graph(), example.lock()) == []
    assert len(example.lock().entries) == len(original.entries) - 1


def test_prune_json_lists_the_entries_in_lock_order(example: Example) -> None:
    orphans = [replace(example.lock().entries[0], source=API, field="derives_from", target=name) for name in ("fr-z-gone", "fr-a-gone")]
    example.write_lock(Lock((*example.lock().entries, *orphans)))
    document = json.loads(_attest(example, "--prune", "--dry-run", "--json")[1])
    assert document["written"] is False and [entry["target"] for entry in document["pruned"]] == ["fr-a-gone", "fr-z-gone"]


# --- the command line ---------------------------------------------------------------------------------------------------

def test_attest_cli_has_no_hash_argument(example: Example) -> None:
    code, out = run_cli("attest", "--help")
    assert code == 0 and "hash" not in out.lower()
    code, out = _attest(example, API, "--hash", "sha256:" + "0" * 64)
    assert code == 2 and "unrecognized arguments" in out


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--prune", "--yes"], "--prune cannot be combined with --yes"),
        (["--prune", "--field", "derives_from", "--target", "x"], "--prune cannot be combined with --field, --target"),
        (["--step", "05", "--field", "derives_from"], "--step cannot be combined with --field"),
    ],
)
def test_attest_flags_that_do_not_go_together_are_a_usage_error(example: Example, argv: list[str], message: str) -> None:
    before = _lock_text(example)
    code, out = _attest(example, *argv)
    assert code == 2 and out.strip() == f"specdev attest: error: {message}" and _lock_text(example) == before


@pytest.mark.parametrize("argv", [[], [API, "--step", "05"], [API, "--prune"], ["--step", "05", "--prune"]])
def test_attest_needs_exactly_one_of_node_step_and_prune(example: Example, argv: list[str]) -> None:
    assert _attest(example, *argv)[0] == 2


def test_attest_unknown_step_is_e706_as_text_and_json(example: Example) -> None:
    code, out = _attest(example, "--step", "99", "--yes")
    assert code == 1 and out.startswith("E706") and "'99'" in out and "05" in out
    document = _attest_json(example, "--step", "99", code=1)
    assert document["errors"][0]["code"] == "E706"
    assert serialise_lock(example.lock()) == _lock_text(example)


# --- an unreadable spec file, and the graph built under the write lock (review M5 R1, F1-5) -------------------------------

def _break_fr_file(example: Example) -> None:
    """Conflict markers in the FR list: the file cannot be read, so the nodes of step 04 are not in the graph."""
    path = example.spec / "04_fr_list.json"
    path.write_text("<<<<<<< ours\n" + path.read_text(encoding="utf-8") + "=======\n>>>>>>> theirs\n", encoding="utf-8")


@pytest.mark.parametrize("argv", [["--prune"], ["--prune", "--dry-run"], [API, "--yes"], [API, "--yes", "--dry-run"], ["--step", "05", "--yes"]])
def test_attest_that_writes_refuses_while_a_spec_file_cannot_be_read(example: Example, argv: list[str]) -> None:
    """B2: the entries of the links in the unreadable file look like orphans; ``--prune`` deleted them and the state could not be rebuilt."""
    example.edit_criterion()
    _break_fr_file(example)
    before = _lock_text(example)
    code, out = _attest(example, *argv)
    assert code == 1 and "E520" in out and "04_fr_list.json cannot be read" in out, out
    assert _lock_text(example) == before


@pytest.mark.parametrize("argv", [[API], [API, "--dry-run"], ["--step", "05"], ["--step", "05", "--dry-run"]])
def test_attest_preview_prints_with_an_unreadable_file_bare_or_with_dry_run(example: Example, argv: list[str]) -> None:
    """A preview writes nothing, so it prints (with the warning of ``run_on_graph``) in both spellings, as ``stale`` does."""
    example.edit_criterion()
    _break_fr_file(example)
    before = _lock_text(example)
    code, out = _attest(example, *argv)
    assert code == 0 and "E520" not in out, out
    assert out.splitlines()[0].startswith("specdev attest: could not read 04_fr_list.json"), out
    assert "attest: " in out.split("\n", 1)[1]
    assert _lock_text(example) == before


def test_attest_previews_do_not_take_the_write_lock_and_writes_do(example: Example, monkeypatch: pytest.MonkeyPatch) -> None:
    """A preview and a dry run plan from the graph already built; ``--yes`` and ``--prune`` take the lock (its order: ``test_lockfile``)."""
    from specdev_tools.trace import commands

    calls: list[str] = []
    real = commands.locked_graph

    def spy(spec_root: str, repo_root: str, what: str) -> Any:
        calls.append(spec_root)
        return real(spec_root, repo_root, what)

    monkeypatch.setattr(commands, "locked_graph", spy)
    example.edit_criterion()
    _attest(example, API)
    _attest(example, "--prune", "--dry-run")
    _attest(example, API, "--yes", "--dry-run")
    assert calls == []
    _attest(example, API, "--yes")
    _attest(example, "--prune")
    assert len(calls) == 2
