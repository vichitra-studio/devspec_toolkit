"""``specdev milestone start`` and ``defer``: the transitions, the refusals and what each leaves untouched."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.lifecycle import anchor_store
from specdev_tools.lifecycle.milestone import NO_LOCK_NOTE, MilestoneRefusal, defer_milestone, start_milestone
from unit.lifecycle._milestone_support import change_stamp, cli_run, set_row
from unit.lifecycle._record_support import author, plan_host, roots
from unit.lifecycle._support import ANCHOR, MILESTONE, PLAN, closed_record
from unit.proof._support import CRITERION
from unit.verify._support import edit_doc

pytestmark = pytest.mark.usefixtures("author")


def _start(host: Path, given: str = MILESTONE) -> Any:
    spec, repo, git = roots(host)
    return start_milestone(spec, repo, git, given)


def _refusal(call: Any) -> Any:
    with pytest.raises(FindingError) as caught:
        call()
    return caught.value


def _row(host: Path) -> anchor_store.AnchorRow:
    row = anchor_store.read_row(host / "spec", MILESTONE)
    assert row is not None
    return row


def test_start_without_a_lock_file_proceeds_with_the_note(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    (host / "spec" / "extras" / "trace.lock.json").unlink()
    set_row(host, "pending")
    result = _start(host)
    assert result.notes == (NO_LOCK_NOTE,) and _row(host).status == "in_progress"
    code, out, _ = cli_run(host, "milestone", "start", MILESTONE)
    assert code == 0 and "already in progress" in out


def test_start_on_a_plan_without_milestone_key_stops_with_e803(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    set_row(host, "pending")
    edit_doc(host, PLAN, lambda document: document.pop("milestone"))
    error = _refusal(lambda: _start(host)).error
    assert (error.code, error.subcode) == ("E803", "MILESTONE_KEY_MISSING")
    assert _row(host).status == "pending"


def test_start_from_pending(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    set_row(host, "pending")
    result = _start(host)
    assert (result.previous, result.resumed, result.noop) == ("pending", False, False)
    assert _row(host).status == "in_progress"


def test_start_from_deferred_resumes_and_clears_the_reason(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    set_row(host, "deferred", deferral_reason="waiting")
    before = (host / "spec" / PLAN).read_bytes()
    result = _start(host)
    assert (result.previous, result.resumed) == ("deferred", True)
    row = _row(host)
    assert (row.status, row.deferral_reason) == ("in_progress", None)
    assert (host / "spec" / PLAN).read_bytes() == before


def test_start_from_in_progress_is_a_no_op(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    before = (host / "spec" / ANCHOR).read_bytes()
    result = _start(host)
    assert result.noop and (host / "spec" / ANCHOR).read_bytes() == before


def test_start_from_done_is_e800(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    set_row(host, "done", close=closed_record())
    error = _refusal(lambda: _start(host)).error
    assert (error.code, error.subcode) == ("E800", "STATUS_NOT_STARTABLE")
    assert _row(host).status == "done"


def test_start_with_a_suspect_link_on_the_chain_is_e800(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    set_row(host, "pending")
    change_stamp(host, "tc-confirm-expired-token", CRITERION)
    refusal = _refusal(lambda: _start(host))
    assert isinstance(refusal, MilestoneRefusal) and (refusal.error.code, refusal.error.subcode) == ("E800", "PENDING_REPLAY_ON_CHAIN")
    assert [(found.code, found.node_id) for found in refusal.details] == [("E763", "tc-confirm-expired-token")]
    assert _row(host).status == "pending"
    code, _, err = cli_run(host, "milestone", "start", MILESTONE)
    assert code == 1 and err.startswith("E800") and "E763" in err and "merge-check" in err


def test_start_with_a_suspect_link_on_an_unrelated_chain_passes(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    set_row(host, "pending")
    change_stamp(host, "nfr-latency-reset-email", "tp-mailrelay")
    assert _start(host).previous == "pending" and _row(host).status == "in_progress"


def test_start_names_the_way_out_for_a_missing_row_and_a_batch_id(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    assert (_refusal(lambda: _start(host, "ms-nothing")).error.subcode) == "ANCHOR_ROW_MISSING"
    error = _refusal(lambda: _start(host, "account_recovery")).error
    assert error.code == "E803" and "milestone-state --batch-id account_recovery" in error.message
    assert _row(host).status == "in_progress"


def test_defer_without_reason_is_e802(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, _ = roots(host)
    for reason in (None, "", "   ", "x" * 301):
        assert _refusal(lambda: defer_milestone(spec, repo, MILESTONE, reason)).error.code == "E802"
    assert _row(host).status == "in_progress"


def test_defer_a_done_milestone_is_e801(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    set_row(host, "done", close=closed_record())
    spec, repo, _ = roots(host)
    assert _refusal(lambda: defer_milestone(spec, repo, MILESTONE, "later")).error.code == "E801"
    set_row(host, "deferred", deferral_reason="x")
    assert _refusal(lambda: defer_milestone(spec, repo, MILESTONE, "later")).error.code == "E801"


def test_defer_leaves_the_plan_byte_identical(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, _ = roots(host)
    before = (host / "spec" / PLAN).read_bytes()
    result = defer_milestone(spec, repo, MILESTONE, "  waiting on the identity provider  ")
    assert (result.previous, result.reason) == ("in_progress", "waiting on the identity provider")
    row = _row(host)
    assert (row.status, row.deferral_reason) == ("deferred", "waiting on the identity provider")
    assert (host / "spec" / PLAN).read_bytes() == before
    document = json.loads((host / "spec" / ANCHOR).read_text(encoding="utf-8"))
    assert set(document["plan"]["milestone_index"][0]) == {"anchor_id", "about", "status", "checklist_id_prefix", "summary", "deferral_reason"}


def test_defer_then_start_through_the_cli(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    assert cli_run(host, "milestone", "defer", MILESTONE)[0] == 1
    code, out, _ = cli_run(host, "milestone", "defer", MILESTONE, "--reason", "waiting")
    assert code == 0 and "in_progress -> deferred" in out
    code, out, _ = cli_run(host, "milestone", "start", MILESTONE)
    assert code == 0 and "resumed" in out and _row(host).deferral_reason is None
