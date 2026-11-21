"""``specdev plan record``: the record writer, ``--prune`` and ``--at-deploy``, on git copies of the worked example."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.lifecycle import executed
from specdev_tools.lifecycle.executed import ExecutionRecord, is_stale, item_reading
from specdev_tools.lifecycle.plan_records import Address, check_plan_records, prune_records, record_action, record_at_deploy
from specdev_tools.trace.records import prune_orphan_records
from specdev_tools.trace.lockfile import read_lock
from specdev_tools.verify.code_tree import code_tree_for_host
from unit.lifecycle._record_support import (
    AUTHOR, ITEM, alpha_binding, action, author, change_lock_hash, close_milestone, lock_path_of, no_identity, plan_document, plan_host, records_in, roots,
)
from unit.lifecycle._support import MILESTONE, PLAN
from unit.proof._support import PASSING, context
from unit.trace._lock_support import run_on_example
from unit.verify._support import edit_doc, graph_of

pytestmark = pytest.mark.usefixtures("author")
A01 = Address(ITEM, "a01")


def _refusal(call: Any) -> Any:
    with pytest.raises(FindingError) as caught:
        call()
    return caught.value.error


def _plan_bytes(host: Path) -> bytes:
    return (host / "spec" / PLAN).read_bytes()


def test_record_appended_and_valid(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    lock_before = lock_path_of(host).read_bytes()
    result = record_action(spec, repo, git, A01, "done", "edited the handler")
    (record,) = records_in(host)
    assert record == result.record
    assert (record["record_id"], record["about"], record["action"], record["outcome"], record["note"]) == ("rec-0001", [ITEM], "a01", "done", "edited the handler")
    assert record["git_author"] == AUTHOR
    assert record["realises_hash"] == executed.realises_hash(read_lock(spec), ITEM)
    assert validate_data_against_schema(repo, plan_document(host)) == []
    assert lock_path_of(host).read_bytes() == lock_before
    assert [node.id for node in graph_of(host).by_kind["execution-record"]] == ["rec-0001"]


def test_a_record_goes_beside_the_execution_content_the_plan_already_has(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    edit_doc(host, PLAN, lambda document: document.update(execution={"files_touched": ["src/hello.txt"]}))
    spec, repo, git = roots(host)
    record_action(spec, repo, git, A01, "done")
    execution = plan_document(host)["execution"]
    assert execution["files_touched"] == ["src/hello.txt"] and [r["record_id"] for r in execution["records"]] == ["rec-0001"]


def test_a_second_record_gets_the_next_id_and_the_latest_counts(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, A01, "failed")
    record_action(spec, repo, git, A01, "done")
    assert [(r["record_id"], r["outcome"]) for r in records_in(host)] == [("rec-0001", "failed"), ("rec-0002", "done")]
    assert item_reading(graph_of(host), context(host), ITEM, read_lock(spec)).executed


def test_verifier_naming_action_is_refused_e822(tmp_path: Path) -> None:
    host = plan_host(tmp_path, action("a02", "run_command", command=PASSING), bindings=(alpha_binding(),))
    spec, repo, git = roots(host)
    before = _plan_bytes(host)
    error = _refusal(lambda: record_action(spec, repo, git, Address(ITEM, "a02"), "done"))
    assert error.code == "E822" and "ver-alpha" in error.message and "verify run" in error.message
    assert _plan_bytes(host) == before


def test_frozen_plan_is_refused_e820(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    close_milestone(host)
    spec, repo, git = roots(host)
    before = _plan_bytes(host)
    assert _refusal(lambda: record_action(spec, repo, git, A01, "done")).code == "E820"
    assert _refusal(lambda: prune_records(spec, repo, MILESTONE)).code == "E820"
    assert _plan_bytes(host) == before


@pytest.mark.parametrize(
    ("address", "keep_ids", "expected"),
    [
        (Address("PWRESET_NO_SUCH_ITEM", "a01"), False, "no plan item PWRESET_NO_SUCH_ITEM"),
        (Address(ITEM, "a09"), False, "its actions are a01"),
        (Address(ITEM, "a01"), True, "its actions carry no id"),
    ],
)
def test_unknown_action_is_e821(tmp_path: Path, address: Address, keep_ids: bool, expected: str) -> None:
    host = plan_host(tmp_path, keep_ids=keep_ids)
    spec, repo, git = roots(host)
    error = _refusal(lambda: record_action(spec, repo, git, address, "done"))
    assert error.code == "E821" and expected in error.message


def test_an_id_two_actions_share_is_e821(tmp_path: Path) -> None:
    host = plan_host(tmp_path, action("a01"))
    spec, repo, git = roots(host)
    error = _refusal(lambda: record_action(spec, repo, git, A01, "done"))
    assert error.code == "E821" and "2 actions with the id a01" in error.message


def test_record_goes_stale_after_a_lock_hash_change(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, A01, "done")
    assert check_plan_records(graph_of(host), read_lock(spec), spec) == []
    change_lock_hash(host)
    lock = read_lock(spec)
    (finding,) = check_plan_records(graph_of(host), lock, spec)
    assert (finding.code, finding.node_id) == ("W825", "rec-0001")
    reading = item_reading(graph_of(host), context(host), ITEM, lock)
    assert not reading.executed and reading.actions[0].state == executed.STALE
    assert len(records_in(host)) == 1


def test_prune_removes_an_orphan_and_keeps_the_others(tmp_path: Path) -> None:
    host = plan_host(tmp_path, action("a02"))
    spec, repo, git = roots(host)
    record_action(spec, repo, git, A01, "done")
    record_action(spec, repo, git, Address(ITEM, "a02"), "done")
    document = plan_document(host)
    del document["plan"]["spec_alignment"]["checklist"][0]["implementation"]["actions"][1]
    (host / "spec" / PLAN).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    result = prune_records(spec, repo, MILESTONE)
    assert result.removed == ("rec-0002",)
    assert [r["record_id"] for r in records_in(host)] == ["rec-0001"]
    assert prune_records(spec, repo, MILESTONE).removed == ()


def test_prune_removes_a_record_of_a_dropped_item(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, A01, "done")
    document = plan_document(host)
    document["plan"]["spec_alignment"]["checklist"] = []
    (host / "spec" / PLAN).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    assert prune_records(spec, repo, MILESTONE).removed == ("rec-0001",)
    assert records_in(host) == []


def test_the_record_file_pruner_leaves_a_plan_with_an_orphan_execution_record_alone(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, A01, "done")
    document = plan_document(host)
    document["plan"]["spec_alignment"]["checklist"] = []
    (host / "spec" / PLAN).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    assert prune_orphan_records(spec, graph_of(host)) == []
    assert (host / "spec" / PLAN).exists()
    assert prune_records(spec, repo, MILESTONE).removed == ("rec-0001",)


def _at_deploy_host(tmp_path: Path, **kwargs: Any) -> Path:
    return plan_host(tmp_path, action("a02", at_deploy=["staging"]), **kwargs)


def test_at_deploy_writes_only_the_standalone_file(tmp_path: Path) -> None:
    host = _at_deploy_host(tmp_path)
    spec, repo, git = roots(host)
    before = _plan_bytes(host)
    result = record_at_deploy(spec, repo, git, Address(ITEM, "a02"), "staging", "done", "v1.2.0")
    assert _plan_bytes(host) == before
    assert result.file == "extras/verification/dep-0001.json"
    document = json.loads((host / "spec" / result.file).read_text(encoding="utf-8"))
    assert validate_data_against_schema(repo, document) == []
    record = document["records"][0]
    assert (record["deploy_id"], record["about"], record["action"], record["env"], record["tag"], record["outcome"]) == ("dep-0001", [ITEM], "a02", "staging", "v1.2.0", "done")
    assert record["tree"] == code_tree_for_host(git, spec) and record["git_author"] == AUTHOR


def test_at_deploy_refuses_an_env_not_in_the_action(tmp_path: Path) -> None:
    host = _at_deploy_host(tmp_path)
    spec, repo, git = roots(host)
    error = _refusal(lambda: record_at_deploy(spec, repo, git, Address(ITEM, "a02"), "prod", "done"))
    assert error.code == "E821" and "marked at_deploy for staging, not for prod" in error.message
    error = _refusal(lambda: record_at_deploy(spec, repo, git, A01, "staging", "done"))
    assert error.code == "E821" and "not marked at_deploy" in error.message
    assert list((host / "spec" / "extras" / "verification").glob("dep-*")) == []


def test_at_deploy_records_outcome_failed(tmp_path: Path) -> None:
    host = _at_deploy_host(tmp_path)
    spec, repo, git = roots(host)
    assert record_at_deploy(spec, repo, git, Address(ITEM, "a02"), "staging", "failed").record["outcome"] == "failed"


def test_at_deploy_works_without_a_git_identity(tmp_path: Path, no_identity: None) -> None:
    host = _at_deploy_host(tmp_path)
    spec, repo, git = roots(host)
    record = record_at_deploy(spec, repo, git, Address(ITEM, "a02"), "staging", "done").record
    assert record["git_author"] == {"name": "ci", "email": ""}
    assert _refusal(lambda: record_action(spec, repo, git, A01, "done")).code == "E767"


def test_at_deploy_stores_the_milestone(tmp_path: Path) -> None:
    host = _at_deploy_host(tmp_path)
    spec, repo, git = roots(host)
    assert record_at_deploy(spec, repo, git, Address(ITEM, "a02"), "staging", "done").record["milestone"] == MILESTONE


def test_at_deploy_works_on_a_closed_milestone(tmp_path: Path) -> None:
    host = _at_deploy_host(tmp_path)
    close_milestone(host)
    spec, repo, git = roots(host)
    before = _plan_bytes(host)
    record_at_deploy(spec, repo, git, Address(ITEM, "a02"), "staging", "done")
    assert _plan_bytes(host) == before


def test_staleness_is_skipped_for_a_closed_plan_and_without_a_lock(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, A01, "done")
    change_lock_hash(host)
    lock = read_lock(spec)
    (record,) = executed.execution_records(graph_of(host))
    assert is_stale(record, lock, frozen_plan=False)
    assert not is_stale(record, lock, frozen_plan=True)
    assert not is_stale(record, None, frozen_plan=False)
    close_milestone(host)
    assert check_plan_records(graph_of(host), lock, spec) == []


def test_a_record_written_without_a_lock_is_never_stale(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    lock_path_of(host).unlink()
    spec, repo, git = roots(host)
    assert record_action(spec, repo, git, A01, "done").record["realises_hash"] is None
    stored = ExecutionRecord("rec-0001", ITEM, "a01", "done", None, PLAN)
    assert not is_stale(stored, read_lock(spec), frozen_plan=False)


def test_at_deploy_recorded_reads_dep_records(tmp_path: Path) -> None:
    host = _at_deploy_host(tmp_path)
    spec, repo, git = roots(host)
    assert not executed.at_deploy_recorded(spec, ITEM, "a02", "staging")
    record_at_deploy(spec, repo, git, Address(ITEM, "a02"), "staging", "done")
    assert executed.at_deploy_recorded(spec, ITEM, "a02", "staging")
    assert not executed.at_deploy_recorded(spec, ITEM, "a02", "prod")
    assert not executed.at_deploy_recorded(spec, ITEM, "a01", "staging")
    record_at_deploy(spec, repo, git, Address(ITEM, "a02"), "staging", "failed")
    assert not executed.at_deploy_recorded(spec, ITEM, "a02", "staging")


def test_at_deploy_required_returns_the_triples(tmp_path: Path) -> None:
    host = plan_host(tmp_path, action("a02", at_deploy=["staging", "prod"]), action("a03", at_deploy=["prod"]))
    spec = roots(host).spec
    assert executed.at_deploy_required(spec, [MILESTONE]) == [(ITEM, "a02", "staging"), (ITEM, "a02", "prod"), (ITEM, "a03", "prod")]
    assert executed.at_deploy_required(spec, ["ms-no-plan"]) == []


def test_plan_size_is_printed_before_and_after(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    before = len(_plan_bytes(host))
    code, output = run_on_example(host, "plan", "record", f"{ITEM}/a01", "--outcome", "done")
    after = len(_plan_bytes(host))
    assert code == 0 and f"recorded rec-0001: {ITEM}/a01 done" in output
    assert f"plan file: {before} bytes before, {after} bytes after" in output
    assert after > before
