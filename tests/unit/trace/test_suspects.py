"""Suspect links, missing and orphan lock entries, historical nodes and the lock hook (WI-M5-03), on the worked example."""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError
from specdev_tools.graph.check import run_graph_check
from specdev_tools.graph.model import Graph
from specdev_tools.graph.ownership import OwnerContext, load_ownership_table, owner_for
from specdev_tools.graph.resolve import resolve_graph
from specdev_tools.trace.history import historical_node_ids
from specdev_tools.trace.lockfile import Lock, LockEntry, LockError, parse_lock, serialise_lock
from specdev_tools.trace.suspects import (
    CAUSE_CONTENT,
    CAUSE_UPSTREAM,
    LockHook,
    check_lock,
    check_lock_orphans,
    find_suspects,
    lock_links,
    missing_entries,
    orphan_entries,
)
from specdev_tools.validation.spec_check import run_spec_check_json

from ..graph._synth import ROOT
from ._lock_support import EXAMPLE_HOST, lock_for
from ._suspects_support import ANCHOR, CLOSED_HOLDERS, CLOSURE_OF_CRITERION_EDIT, CRITERION, Example

FR_FILE, CHARTER_FILE, ROADMAP_FILE = "04_fr_list.json", "00_charter.json", "14_roadmap.json"
CLOSED_MILESTONE = "ms-account-recovery"


@pytest.fixture
def example(tmp_path: Path) -> Example:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    return Example(host)


def _codes(errors: list[SpecError]) -> list[str]:
    return [error.code for error in errors]


# --- the committed lock and the links that carry an entry -------------------------------------------------------------

def test_committed_lock_is_what_the_code_regenerates(example: Example) -> None:
    graph = example.graph()
    regenerated = serialise_lock(lock_for(graph, example.host))
    assert (EXAMPLE_HOST / "spec" / "extras" / "trace.lock.json").read_text(encoding="utf-8") == regenerated


def test_committed_lock_is_current_on_the_worked_example(example: Example) -> None:
    graph = example.graph()
    assert example.suspects() == []
    assert missing_entries(graph, example.lock()) == []
    assert orphan_entries(graph, example.lock()) == []


def test_lock_links_leave_out_records_and_history_links(example: Example) -> None:
    graph = example.graph()
    keys = {item.key for item in lock_links(graph)}
    assert all(holder != ANCHOR for holder, _field, _target in keys)
    assert {field for _holder, field, _target in keys}.isdisjoint({"replaces", "removes"})
    assert {entry.key for entry in example.lock().entries} == keys


def test_lock_get_finds_an_entry_by_its_key(example: Example) -> None:
    entry = example.lock().entries[0]
    assert example.lock().get(entry.source, entry.field, entry.target) == entry
    assert example.lock().get(entry.source, entry.field, "no-such-target") is None


# --- suspects ---------------------------------------------------------------------------------------------------------

def test_upstream_criterion_edit_marks_full_closure(example: Example) -> None:
    example.edit_criterion()
    suspects = example.suspects()
    assert {suspect.key for suspect in suspects} == CLOSURE_OF_CRITERION_EDIT
    assert len(suspects) == len(CLOSURE_OF_CRITERION_EDIT)
    assert {suspect.holder_step for suspect in suspects} == {"05", "06", "07", "08", "09", "11", "14", "15", "16a"}


def test_suspect_cause_and_roots_name_the_edited_criterion(example: Example) -> None:
    example.edit_criterion()
    by_key = {suspect.key: suspect for suspect in example.suspects()}
    direct = by_key[("err-password-reset-confirm-token-expired", "derives_from", CRITERION)]
    far = by_key[("scaffold-password-reset-confirm", "realises", "api-password-reset-confirm")]
    assert (direct.cause, far.cause) == (CAUSE_CONTENT, CAUSE_UPSTREAM)
    assert direct.roots == far.roots == (CRITERION,)


def test_intermediate_level_confirms_but_below_stays_suspect(example: Example) -> None:
    example.edit_seed()
    assert ("scope-password-reset", "derives_from", "seed-accounts") in example.suspect_keys()
    for holder in ("scope-password-reset", "cap-account-recovery", "fr-password-reset"):
        example.attest(holder)
    remaining = example.suspect_keys()
    assert not {key for key in remaining if key[0] in {"scope-password-reset", "cap-account-recovery", "fr-password-reset"}}
    assert ("tc-confirm-expired-token", "refines", CRITERION) in remaining


def test_historical_links_excluded(example: Example) -> None:
    example.close_milestone()
    example.edit_criterion()
    graph = example.graph()
    assert CLOSED_HOLDERS | {"task-implement-password-reset-confirm"} <= historical_node_ids(graph)
    held_by_closed = {key for key in CLOSURE_OF_CRITERION_EDIT if key[0] in CLOSED_HOLDERS}
    assert held_by_closed
    assert example.suspect_keys() == CLOSURE_OF_CRITERION_EDIT - held_by_closed
    gone = next(iter(held_by_closed))
    example.drop_entries(lambda entry: entry.key == gone)
    assert [item.key for item in missing_entries(example.graph(), example.lock())] == [gone]
    example.write_lock(Lock((*example.lock().entries, LockEntry("tc-confirm-expired-token", "refines", "ac-gone", *["sha256:" + "0" * 64] * 2))))
    assert [entry.target for entry in orphan_entries(example.graph(), example.lock())] == ["ac-gone"]


@pytest.mark.parametrize(
    "change",
    [{"status": "accepted"}, {"notes": "reworded note"}, {"tags": ["draft"]}, {"owner": "ops"}],
    ids=["status", "notes", "tags", "owner"],
)
def test_status_note_tag_edits_create_no_suspects(example: Example, change: dict[str, Any]) -> None:
    for node_id in (CRITERION, "fr-password-reset", "cap-account-recovery"):
        example.edit_item(node_id, lambda item: item.update(change))
    assert example.suspects() == []


def test_not_applicable_nodes_skipped(example: Example) -> None:
    example.edit_criterion()
    example.edit_item("tc-confirm-expired-token", lambda item: item.update(lifecycle="not_applicable"))
    example.edit_item("fix-password-reset-expired-token", lambda item: item.update(lifecycle="not_applicable"))
    graph = example.graph()
    suspects = find_suspects(graph, example.lock(), example.seed_texts(graph))
    ends = {end for suspect in suspects for end in (suspect.holder, suspect.target)}
    assert ends.isdisjoint({"tc-confirm-expired-token", "fix-password-reset-expired-token"})
    assert {item.link.target for item in lock_links(graph)}.isdisjoint({"tc-confirm-expired-token", "fix-password-reset-expired-token"})
    assert orphan_entries(graph, example.lock()) == []
    assert missing_entries(graph, example.lock()) == []
    assert "tc-confirm-expired-token" not in historical_node_ids(graph)


def test_an_entry_of_a_not_applicable_holder_is_kept_and_ignored(example: Example) -> None:
    example.edit_item("fix-password-reset-expired-token", lambda item: item.update(lifecycle="not_applicable", verifies=[]))
    graph = example.graph()
    assert any(entry.source == "fix-password-reset-expired-token" for entry in example.lock().entries)
    assert orphan_entries(graph, example.lock()) == []


# --- missing and orphan entries ---------------------------------------------------------------------------------------

def test_crash_between_spec_and_lock_write_leaves_missing_entry_not_orphan(example: Example) -> None:
    """The spec file was replaced first; the lock write never happened."""
    example.edit_item("scope-sms-reset", lambda item: item["derives_from"].append("need-fewer-reset-tickets"))
    graph = example.graph()
    added = ("scope-sms-reset", "derives_from", "need-fewer-reset-tickets")
    assert [item.key for item in missing_entries(graph, example.lock())] == [added]
    assert orphan_entries(graph, example.lock()) == []
    findings = run_graph_check(str(example.spec), str(ROOT), lock=example.lock())
    assert [(error.code, error.node_id) for error in findings] == [("E761", "scope-sms-reset")]


def test_a_removed_link_leaves_an_orphan_entry_not_a_missing_one(example: Example) -> None:
    example.edit_item("scope-password-reset", lambda item: item["derives_from"].remove("need-fewer-reset-tickets"))
    graph = example.graph()
    assert missing_entries(graph, example.lock()) == []
    (orphan,) = orphan_entries(graph, example.lock())
    assert orphan.key == ("scope-password-reset", "derives_from", "need-fewer-reset-tickets")


def test_an_entry_naming_an_alias_is_not_an_orphan(example: Example) -> None:
    graph = example.graph()
    graph.alias_index["need-old-name"] = "need-fewer-reset-tickets"
    entries = [
        replace(entry, target="need-old-name") if entry.target == "need-fewer-reset-tickets" else entry
        for entry in example.lock().entries
    ]
    lock = Lock(tuple(entries))
    assert orphan_entries(graph, lock) == []
    assert missing_entries(graph, lock) == []
    assert LockHook(graph, lock).on_link(*_first_link_to(graph, "need-fewer-reset-tickets")) == []


def test_two_entries_for_one_link_after_a_rename_merge_leave_the_old_spelling_as_an_orphan(example: Example) -> None:
    """C-08: one branch renamed the target (the entry is re-keyed), the other attested under the old id: the old spelling is the orphan."""
    graph = example.graph()
    graph.alias_index["need-old-name"] = "need-fewer-reset-tickets"
    current = next(entry for entry in example.lock().entries if entry.target == "need-fewer-reset-tickets")
    old_spelling = replace(current, target="need-old-name", content_hash="sha256:" + "a" * 64, chain_stamp="sha256:" + "b" * 64)
    lock = Lock((*example.lock().entries, old_spelling))
    assert orphan_entries(graph, lock) == [old_spelling]
    assert [error.code for error in check_lock_orphans(graph, lock)] == ["E762"]
    # both entries under an old spelling, none under the id: one stays, so the link keeps an entry
    second_old = replace(old_spelling, target="need-older-name")
    graph.alias_index["need-older-name"] = "need-fewer-reset-tickets"
    only_old = Lock((*(entry for entry in example.lock().entries if entry is not current and entry != current), old_spelling, second_old))
    assert orphan_entries(graph, only_old) == [second_old] and missing_entries(graph, only_old) == []


def _first_link_to(graph: Graph, target: str) -> tuple[Any, Any, Any]:
    item = next(item for item in lock_links(graph) if item.link.target == target)
    return item.link, item.holder, item.target


def test_a_deleted_target_leaves_the_entries_of_its_holders_not_orphans(example: Example) -> None:
    path = example.spec / FR_FILE
    document = json.loads(path.read_text(encoding="utf-8"))
    document["functional_requirements"] = [fr for fr in document["functional_requirements"] if fr["fr_id"] != "fr-password-reset"]
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    graph = example.graph()
    orphans = {entry.key for entry in orphan_entries(graph, example.lock())}
    assert {source for source, _field, _target in orphans} == {"fr-password-reset"}
    assert any(entry.target == "fr-password-reset" for entry in example.lock().entries)
    assert {error.code for error in resolve_graph(graph)} == {"E700"}


def test_deleted_holder_and_target_make_the_entry_an_orphan(example: Example) -> None:
    graph = example.graph()
    lock = Lock((*example.lock().entries, LockEntry("ghost-holder", "derives_from", "ghost-target", *["sha256:" + "1" * 64] * 2)))
    (orphan,) = orphan_entries(graph, lock)
    assert orphan.source == "ghost-holder"
    (error,) = check_lock_orphans(graph, lock)
    assert (error.code, error.owner, error.node_id) == ("E762", "merge-check", None)


def test_missing_entry_and_orphan_entry_errors_have_owners(example: Example) -> None:
    example.drop_entries(lambda entry: entry.source == "fr-password-reset")
    ghost = LockEntry("scope-password-reset", "derives_from", "need-ghost", *["sha256:" + "2" * 64] * 2)
    example.write_lock(Lock((*example.lock().entries, ghost)))
    graph = example.graph()
    (missing,) = run_graph_check(str(example.spec), str(ROOT), graph=graph, lock=example.lock())
    (orphan,) = check_lock(graph, example.lock(), example.seed_texts(graph))
    assert (missing.code, missing.owner, missing.node_id) == ("E761", "step:04", "fr-password-reset")
    assert (orphan.code, orphan.owner, orphan.node_id) == ("E762", "merge-check", "scope-password-reset")
    example.edit_criterion()
    edited = example.graph()
    suspect = next(error for error in check_lock(edited, example.lock(), example.seed_texts(edited)) if error.code == "E763")
    assert suspect.owner == "merge-check"
    assert suspect.node_id is not None


def test_live_baseline_entry_is_e882_historical_is_not(example: Example) -> None:
    example.close_milestone()
    marked = {("api-password-reset-confirm", "derives_from", "fr-password-reset"), ("tc-confirm-expired-token", "refines", CRITERION)}
    example.write_lock(Lock(tuple(replace(entry, baseline=entry.key in marked) for entry in example.lock().entries)))
    graph = example.graph()
    (error,) = [e for e in check_lock(graph, example.lock(), example.seed_texts(graph)) if e.code == "E882"]
    assert (error.owner, error.node_id) == ("step:05", "api-password-reset-confirm")
    example.attest("api-password-reset-confirm")
    assert [e for e in check_lock(graph, example.lock(), example.seed_texts(graph)) if e.code == "E882"] == []
    assert any(entry.baseline for entry in example.lock().entries)


# --- the lock hook ----------------------------------------------------------------------------------------------------

def _deprecate_capability(example: Example) -> tuple[str, str, str]:
    example.edit_item("cap-account-recovery", lambda item: item.update(lifecycle="deprecated"))
    return ("fr-password-reset", "derives_from", "cap-account-recovery")


def test_resolver_hook_fires(example: Example) -> None:
    graph = example.graph()
    assert resolve_graph(graph, hooks=LockHook(graph, example.lock())) == []
    errors = resolve_graph(graph, hooks=LockHook(graph, Lock()))
    assert set(_codes(errors)) == {"E761"}
    assert len(errors) == len(lock_links(graph))
    by_node = {error.node_id: error.owner for error in errors}
    assert by_node["fr-password-reset"] == "step:04"
    assert by_node["PWRESET_CONFIRM_EXPIRED_01"] == "step:16a"


def test_w720_emitted_only_for_new_link_to_deprecated_target(example: Example) -> None:
    key = _deprecate_capability(example)
    example.drop_entries(lambda entry: entry.key == key)
    errors = run_graph_check(str(example.spec), str(ROOT), lock=example.lock())
    assert [(error.code, error.owner, error.node_id) for error in errors] == [
        ("E761", "step:04", "fr-password-reset"), ("W720", "step:04", "fr-password-reset"),
    ]


def test_w720_silent_when_lock_entry_exists(example: Example) -> None:
    _deprecate_capability(example)
    assert run_graph_check(str(example.spec), str(ROOT), lock=example.lock()) == []


def test_no_lock_means_no_lock_findings(example: Example) -> None:
    assert run_graph_check(str(example.spec), str(ROOT)) == []


def test_no_finding_reported_twice_by_graph_and_trace_lock(example: Example) -> None:
    example.edit_criterion()
    example.drop_entries(lambda entry: entry.source == "scope-sms-reset")
    example.write_lock(Lock((*example.lock().entries, LockEntry("ghost", "derives_from", "ghost-target", *["sha256:" + "3" * 64] * 2))))
    example.edit_item("cap-account-recovery", lambda item: item.update(lifecycle="deprecated"))
    _errors, context = run_spec_check_json(str(ROOT), str(example.spec), git_root=str(example.host))
    checks = context["checks"]
    graph_codes = {finding["code"] for finding in checks["graph"]["findings"]}
    lock_codes = {finding["code"] for finding in checks["trace-lock"]["findings"]}
    assert graph_codes == {"E761"} and lock_codes == {"E762", "E763"}
    seen = [
        (finding["code"], finding.get("node_id"), finding["message"])
        for name in ("graph", "trace-lock")
        for finding in checks[name]["findings"]
    ]
    assert len(seen) == len(set(seen))


def test_owner_for_agrees_with_stamped_owner_for_every_m5_code(example: Example) -> None:
    example.edit_criterion()
    example.drop_entries(lambda entry: entry.source == "scope-sms-reset")
    entries = [replace(entry, baseline=True) if entry.source == "cap-account-recovery" else entry for entry in example.lock().entries]
    ghost = LockEntry("ghost", "derives_from", "ghost-target", *["sha256:" + "4" * 64] * 2)
    lock = Lock((*entries, ghost))
    graph = example.graph()
    found = [*run_graph_check(str(example.spec), str(ROOT), graph=graph, lock=lock), *check_lock(graph, lock, example.seed_texts(graph))]
    with pytest.raises(LockError) as raised:
        parse_lock("{", "trace.lock.json")
    found.append(raised.value.error)
    context = OwnerContext(load_ownership_table(str(ROOT)))
    assert {"E760", "E761", "E762", "E763", "E882"} <= set(_codes(found))
    for error in found:
        node = graph.by_id.get(error.node_id or "")
        table_owner = owner_for(error.code, node, context)
        assert error.owner is not None
        assert table_owner in (None, error.owner), error.code


# --- historical nodes -------------------------------------------------------------------------------------------------

def test_historical_nodes_are_the_done_milestone_its_contents_and_its_plans(example: Example) -> None:
    assert historical_node_ids(example.graph()) == set()
    example.close_milestone()
    assert historical_node_ids(example.graph()) == {CLOSED_MILESTONE, "task-implement-password-reset-confirm", *CLOSED_HOLDERS}


@pytest.mark.parametrize("status", ["pending", "in_progress", "blocked"])
def test_a_milestone_is_historical_only_when_its_anchor_row_is_done(example: Example, status: str) -> None:
    example.edit_item(ANCHOR, lambda item: item.update(status=status))
    assert historical_node_ids(example.graph()) == set()


def test_an_anchor_row_without_a_status_reads_pending(example: Example) -> None:
    example.edit_item(ANCHOR, lambda item: item.pop("status"))
    assert historical_node_ids(example.graph()) == set()
