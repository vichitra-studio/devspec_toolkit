"""The anchor store: reading rows, the single row writer, the legacy close and the recorded migration."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.lifecycle import anchor_store, frozen, plans
from unit.graph._synth import git
from unit.verify._support import commit_all, example_host

from ._support import ANCHOR, HASH_A, HASH_B, MILESTONE, closed_record, edit_row, example_spec, load, toolkit_root


def test_read_row_finds_the_row_by_about(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    row = anchor_store.read_row(spec, MILESTONE)
    assert row is not None
    assert (row.anchor_id, row.milestone_id, row.status, row.index) == ("anchor-ms-account-recovery", MILESTONE, "in_progress", 0)
    assert anchor_store.read_row(spec, "ms-other") is None
    assert anchor_store.read_row(tmp_path / "nowhere", MILESTONE) is None


def test_legacy_row_without_status_reads_as_pending(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    edit_row(spec, lambda row: row.pop("status"))
    row = anchor_store.read_row(spec, MILESTONE)
    assert row is not None and row.status == "pending"
    assert anchor_store.read_statuses(spec)[MILESTONE].status == "pending"


def test_unknown_status_raises_e801_status_unknown(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    edit_row(spec, lambda row: row.update(status="finished"))
    with pytest.raises(FindingError) as caught:
        anchor_store.read_row(spec, MILESTONE)
    assert (caught.value.error.code, caught.value.error.subcode) == ("E801", "STATUS_UNKNOWN")
    assert "finished" in caught.value.error.message


def test_write_row_state_refuses_a_schema_invalid_row_and_leaves_the_file_byte_identical(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    before = (spec / ANCHOR).read_bytes()
    for status, kwargs in (("done", {}), ("finished", {}), ("deferred", {})):
        with pytest.raises(FindingError) as caught:
            anchor_store.write_row_state(spec, MILESTONE, status, repo_root=toolkit_root(), **kwargs)
        assert caught.value.error.code == "E767"
        assert (spec / ANCHOR).read_bytes() == before


def test_write_row_state_refuses_a_milestone_with_no_row(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    with pytest.raises(FindingError) as caught:
        anchor_store.write_row_state(spec, "ms-other", "in_progress", repo_root=toolkit_root())
    assert caught.value.error.code == "E767" and "ms-other" in caught.value.error.message


def test_write_row_state_changes_only_the_row_and_leaves_the_trace_lock(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    lock, anchor = (spec / "extras" / "trace.lock.json").read_bytes(), load(spec, ANCHOR)
    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(), repo_root=toolkit_root())
    row = anchor_store.read_row(spec, MILESTONE)
    assert row is not None and row.status == "done" and row.close == closed_record()
    assert (spec / "extras" / "trace.lock.json").read_bytes() == lock
    after = load(spec, ANCHOR)
    after["plan"]["milestone_index"][0].pop("close")
    after["plan"]["milestone_index"][0]["status"] = "in_progress"
    assert after == anchor


def test_write_row_state_sets_the_three_fields_together(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    anchor_store.write_row_state(spec, MILESTONE, "deferred", deferral_reason="Waits for the contract.", repo_root=toolkit_root())
    deferred = anchor_store.read_row(spec, MILESTONE)
    assert deferred is not None and (deferred.status, deferred.deferral_reason, deferred.close) == ("deferred", "Waits for the contract.", None)
    anchor_store.write_row_state(spec, MILESTONE, "in_progress", repo_root=toolkit_root())
    resumed = anchor_store.read_row(spec, MILESTONE)
    assert resumed is not None and (resumed.status, resumed.deferral_reason) == ("in_progress", None)
    assert "deferral_reason" not in load(spec, ANCHOR)["plan"]["milestone_index"][0]


def test_read_statuses_at_ref(tmp_path: Path) -> None:
    host = example_host(tmp_path)
    spec = host / "spec"
    assert anchor_store.read_statuses(spec, "HEAD")[MILESTONE].status == "in_progress"
    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(), repo_root=toolkit_root())
    commit_all(host, "close")
    head, base = anchor_store.read_statuses(spec, "HEAD"), anchor_store.read_statuses(spec, "HEAD~1")
    assert (head[MILESTONE].status, head[MILESTONE].signed_off_by) == ("done", "a@example.invalid")
    assert base[MILESTONE].status == "in_progress" and base[MILESTONE].close is None
    assert anchor_store.read_statuses(spec) == head
    git(host, "rm", "-q", "spec/" + ANCHOR)
    commit_all(host, "drop the anchor")
    assert anchor_store.read_statuses(spec, "HEAD") == {}


def test_read_statuses_at_an_unknown_ref_is_e708(tmp_path: Path) -> None:
    spec = example_host(tmp_path) / "spec"
    with pytest.raises(FindingError) as caught:
        anchor_store.read_statuses(spec, "no-such-ref")
    assert caught.value.error.code == "E708"


def test_is_legacy_close() -> None:
    assert anchor_store.is_legacy_close({"signed_off_by": "legacy-migration", "source": "14.status"})
    assert not anchor_store.is_legacy_close({"signed_off_by": "a@example.invalid"})
    assert not anchor_store.is_legacy_close({})
    assert not anchor_store.is_legacy_close(None)


def test_write_legacy_close_stores_source_and_plan_hash(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    anchor_store.write_legacy_close(spec, MILESTONE, "14.status", repo_root=toolkit_root())
    row = anchor_store.read_row(spec, MILESTONE)
    assert row is not None and row.status == "done"
    assert row.close == {
        "signed_off_by": "legacy-migration",
        "source": "14.status",
        "signoff": None,
        "plan_hash": plans.plan_hash(spec / "impl_context" / "ms_account_recovery_plan.json"),
    }
    assert anchor_store.is_legacy_close(row.close)
    assert frozen.frozen_plan_drift(spec, MILESTONE) is None


def test_write_legacy_close_without_a_plan_is_e803(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    (spec / "impl_context" / "ms_account_recovery_plan.json").unlink()
    before = (spec / ANCHOR).read_bytes()
    with pytest.raises(FindingError) as caught:
        anchor_store.write_legacy_close(spec, MILESTONE, "14.status", repo_root=toolkit_root())
    assert caught.value.error.code == "E803"
    assert (spec / ANCHOR).read_bytes() == before


def test_append_close_migration(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(), repo_root=toolkit_root())
    anchor_store.append_close_migration(spec, MILESTONE, HASH_B, "first", repo_root=toolkit_root())
    anchor_store.append_close_migration(spec, MILESTONE, HASH_A, "second", repo_root=toolkit_root())
    row = anchor_store.read_row(spec, MILESTONE)
    assert row is not None and row.close is not None
    assert row.close["migrations"] == [{"hash_after": HASH_B, "note": "first"}, {"hash_after": HASH_A, "note": "second"}]
    assert row.close["plan_hash"] == HASH_A and row.status == "done"


def test_append_close_migration_refuses_a_milestone_that_is_not_closed(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    with pytest.raises(FindingError) as caught:
        anchor_store.append_close_migration(spec, MILESTONE, HASH_B, "note", repo_root=toolkit_root())
    assert caught.value.error.code == "E801"
