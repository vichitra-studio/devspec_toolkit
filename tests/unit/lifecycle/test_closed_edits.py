"""``json patch|insert|delete --id`` on a closed milestone's step-14 nodes: refused outside a migration, allowed and recorded once inside one."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from specdev_tools.lifecycle import anchor_store, frozen
from unit.lifecycle._milestone_support import cli_run
from unit.lifecycle._record_support import closed_row, plan_host
from unit.lifecycle._support import ANCHOR, MILESTONE
from unit.verify._support import commit_all

CRITERION = "tc-confirm-expired-token"
OTHER_CRITERION = "tc-confirm-reused-token"
TASK = "task-implement-password-reset-confirm"
EDIT = ("json", "patch", "--id", CRITERION, ".text", '"Reworded after the close."')


def _closed_host(tmp_path: Path, *, closed: bool = True) -> Path:
    host = plan_host(tmp_path)
    if closed:
        closed_row(host)
    return host


def _stamp(host: Path, status: str | None) -> None:
    stamp = {"toolkit_version": "1.2.0", "migration_history": [{"from": "1.1.1", "to": "1.2.0", "date": "2026-11-23T00:00:00Z", "notes": "x"}]}
    if status is not None:
        stamp["migration_status"] = status
    (host / "spec" / "specdev_version").write_text(yaml.safe_dump(stamp), encoding="utf-8")


def _migrations(host: Path) -> list[dict]:
    row = anchor_store.read_row(host / "spec", MILESTONE)
    assert row is not None and row.close is not None
    return list(row.close.get("migrations", []))


def _bytes(host: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in (host / "spec").rglob("*") if path.is_file()}


@pytest.mark.parametrize(
    "command",
    [EDIT, ("json", "insert", "--id", CRITERION, ".refines", '"fr-password-reset"'), ("json", "delete", "--id", OTHER_CRITERION), ("json", "patch", "--id", TASK, ".description", '"x"')],
    ids=["patch", "insert", "delete", "patch-task"],
)
def test_a_closed_milestones_step_14_node_is_not_written_outside_a_migration(tmp_path: Path, command: tuple[str, ...]) -> None:
    host = _closed_host(tmp_path)
    before = _bytes(host)
    code, _, err = cli_run(host, *command)
    assert code == 1 and "E767" in err and "is closed" in err and "node status" in err
    assert _bytes(host) == before


def test_a_stamp_without_a_migration_in_progress_changes_nothing(tmp_path: Path) -> None:
    host = _closed_host(tmp_path)
    _stamp(host, None)
    assert cli_run(host, *EDIT)[0] == 1


def test_node_status_not_applicable_is_still_the_way_to_park_a_closed_task_criterion(tmp_path: Path) -> None:
    host = _closed_host(tmp_path)
    code, out, err = cli_run(host, "node", "status", OTHER_CRITERION, "not_applicable")
    assert code == 0, err
    assert f"{OTHER_CRITERION}: active -> not_applicable" in out


def test_the_nodes_of_an_open_milestone_are_written(tmp_path: Path) -> None:
    host = _closed_host(tmp_path, closed=False)
    code, _, err = cli_run(host, *EDIT)
    assert code == 0, err
    assert "Reworded after the close." in (host / "spec" / "14_roadmap.json").read_text(encoding="utf-8")


def test_a_node_that_is_not_step_14_is_written_on_a_closed_milestone(tmp_path: Path) -> None:
    host = _closed_host(tmp_path)
    code, _, err = cli_run(host, "json", "patch", "--id", "fr-password-reset", ".statement", '"A reworded statement."')
    assert code == 0, err
    assert "A reworded statement." in (host / "spec" / "04_fr_list.json").read_text(encoding="utf-8")


def test_inside_a_migration_the_edit_is_written_and_the_milestone_gets_one_record(tmp_path: Path) -> None:
    host = _closed_host(tmp_path)
    _stamp(host, "in_progress")
    plan_hash = json.loads((host / "spec" / ANCHOR).read_text(encoding="utf-8"))["plan"]["milestone_index"][0]["close"]["plan_hash"]
    code, _, err = cli_run(host, *EDIT)
    assert code == 0, err
    assert "Reworded after the close." in (host / "spec" / "14_roadmap.json").read_text(encoding="utf-8")
    assert _migrations(host) == [{"hash_after": plan_hash, "note": "step-14 nodes edited by the migration from 1.1.1 to 1.2.0"}]
    # a second edit of the same milestone, of another node and by another action, adds nothing
    code, _, err = cli_run(host, "json", "patch", "--id", OTHER_CRITERION, ".text", '"The reuse of a token is refused after the close."'); assert code == 0, err
    assert cli_run(host, "json", "insert", "--id", CRITERION, ".refines", '"fr-password-reset"')[0] == 0
    assert len(_migrations(host)) == 1
    assert frozen.check_frozen_plans(str(host / "spec")).errors == ()


def test_a_dry_run_inside_a_migration_records_nothing(tmp_path: Path) -> None:
    host = _closed_host(tmp_path)
    _stamp(host, "in_progress")
    before = _bytes(host)
    code, _, err = cli_run(host, *EDIT, "--dry-run")
    assert code == 0, err
    assert _bytes(host) == before


def test_once_the_migration_is_closed_the_refusal_is_back(tmp_path: Path) -> None:
    host = _closed_host(tmp_path)
    _stamp(host, "in_progress")
    assert cli_run(host, *EDIT)[0] == 0
    _stamp(host, None)
    code, _, err = cli_run(host, "json", "patch", "--id", OTHER_CRITERION, ".text", '"The reuse of a token is refused late, after the migration."')
    assert code == 1 and "is closed" in err


# --- the other ways to change such a node: a lifecycle by `node status`, a rename, `.lifecycle` by id -----------------


@pytest.mark.parametrize("node", [CRITERION, TASK, MILESTONE])
def test_node_status_deprecated_is_refused_on_a_closed_milestones_step_14_node(tmp_path: Path, node: str) -> None:
    host = _closed_host(tmp_path)
    before = _bytes(host)
    code, _, err = cli_run(host, "node", "status", node, "deprecated")
    assert code == 1 and "E705" in err and f"'{node}'" in err and "only not_applicable" in err
    assert _bytes(host) == before


def test_a_not_applicable_closed_node_is_taken_back_with_active_and_nothing_else(tmp_path: Path) -> None:
    host = _closed_host(tmp_path)
    assert cli_run(host, "node", "status", CRITERION, "not_applicable")[0] == 0
    code, _, err = cli_run(host, "node", "status", CRITERION, "deprecated")
    assert code == 1 and "E705" in err
    code, out, err = cli_run(host, "node", "status", CRITERION, "active")
    assert code == 0, err
    assert f"{CRITERION}: not_applicable -> active" in out


def test_node_status_deprecated_is_written_on_an_open_milestones_step_14_node(tmp_path: Path) -> None:
    host = _closed_host(tmp_path, closed=False)
    code, out, err = cli_run(host, "node", "status", CRITERION, "deprecated")
    assert code == 0, err
    assert f"{CRITERION}: active -> deprecated" in out


RENAME = ("node", "rename", CRITERION, "tc-confirm-expired-token-renamed")


def test_a_rename_of_a_closed_milestones_step_14_node_is_refused_outside_a_migration(tmp_path: Path) -> None:
    host = _closed_host(tmp_path)
    before = _bytes(host)
    for extra in ((), ("--dry-run",)):
        code, _, err = cli_run(host, *RENAME, *extra)
        assert code == 1 and "E767" in err and f"'{CRITERION}'" in err and "`node rename`" in err and "is closed" in err
    assert _bytes(host) == before


def test_a_rename_inside_a_migration_is_written_and_recorded_once(tmp_path: Path) -> None:
    host = _closed_host(tmp_path)
    _stamp(host, "in_progress")
    assert cli_run(host, *RENAME, "--dry-run")[0] == 0 and _migrations(host) == []
    code, _, err = cli_run(host, *RENAME)
    assert code == 0, err
    assert "tc-confirm-expired-token-renamed" in (host / "spec" / "14_roadmap.json").read_text(encoding="utf-8")
    assert len(_migrations(host)) == 1
    # a second edit of the same milestone, here an id write of another node, adds no second record
    assert cli_run(host, "json", "patch", "--id", OTHER_CRITERION, ".text", '"The reuse of a token is refused after the close."')[0] == 0
    assert len(_migrations(host)) == 1


def test_a_rename_on_an_open_milestone_is_written(tmp_path: Path) -> None:
    host = _closed_host(tmp_path, closed=False)
    code, _, err = cli_run(host, *RENAME)
    assert code == 0, err
    assert "tc-confirm-expired-token-renamed" in (host / "spec" / "14_roadmap.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("node", [CRITERION, "fr-password-reset", "cap-account-recovery"])
@pytest.mark.parametrize("action", ["patch", "insert"])
def test_the_lifecycle_is_not_written_by_an_id_write(tmp_path: Path, node: str, action: str) -> None:
    host = _closed_host(tmp_path, closed=False)
    before = _bytes(host)
    code, _, err = cli_run(host, "json", action, "--id", node, ".lifecycle", '"not_applicable"')
    assert code == 1 and "E767" in err and "specdev node status <id> <value>" in err and f"'{node}'" in err
    assert _bytes(host) == before


def test_node_status_itself_still_writes_the_lifecycle(tmp_path: Path) -> None:
    host = _closed_host(tmp_path, closed=False)
    code, out, err = cli_run(host, "node", "status", "fr-password-reset", "deprecated")
    assert code == 0, err
    assert "fr-password-reset: active -> deprecated" in out
