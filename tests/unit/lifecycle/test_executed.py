"""The executed reading of a plan item: which actions are satisfied by a record, by evidence, or by neither (at-deploy, later stage)."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.lifecycle import executed
from specdev_tools.lifecycle.executed import item_reading, naming_bindings
from specdev_tools.lifecycle.plan_records import Address, record_action
from specdev_tools.proof.proof import PROVEN
from specdev_tools.trace.lockfile import read_lock
from unit.lifecycle._record_support import ALPHA, ITEM, STAGED, STAGED_COMMAND, action, alpha_binding, author, plan_host, roots
from unit.lifecycle._support import PLAN
from unit.proof._support import PASSING, binding_item, context, run
from unit.verify._support import edit_doc, graph_of

pytestmark = pytest.mark.usefixtures("author")


def _host(tmp_path: Path) -> Path:
    """Four actions: a record decides ``a01``, a dev binding ``a02``, a staging binding ``a03``; ``a04`` is at-deploy."""
    return plan_host(
        tmp_path,
        action("a02", "run_command", command=PASSING),
        action("a03", "run_command", command=STAGED_COMMAND),
        action("a04", at_deploy=["staging"]),
        bindings=(alpha_binding(), binding_item(STAGED, stage="staging", commands=(STAGED_COMMAND,), proves=())),
    )


def _states(host: Path) -> dict[str, str]:
    reading = item_reading(graph_of(host), context(host), ITEM, read_lock(roots(host).spec))
    return {entry.action: entry.state for entry in reading.actions}


def test_truth_table_a_b_c_and_at_deploy(tmp_path: Path) -> None:
    host = _host(tmp_path)
    spec, repo, git = roots(host)
    owed = {"a01": executed.NO_RECORD, "a02": executed.NEEDS_EVIDENCE, "a03": executed.LATER_STAGE, "a04": executed.AT_DEPLOY}
    assert _states(host) == owed
    assert not item_reading(graph_of(host), context(host), ITEM, read_lock(spec)).executed

    record_action(spec, repo, git, Address(ITEM, "a01"), "blocked")
    assert _states(host)["a01"] == executed.NOT_DONE
    record_action(spec, repo, git, Address(ITEM, "a01"), "done")
    assert _states(host) == {**owed, "a01": executed.RECORDED}

    assert [result.passed for result in run(host, [ALPHA])] == [True]
    assert _states(host) == {"a01": executed.RECORDED, "a02": PROVEN, "a03": executed.LATER_STAGE, "a04": executed.AT_DEPLOY}
    graph, ctx, lock = graph_of(host), context(host), read_lock(spec)
    assert item_reading(graph, ctx, ITEM, lock).executed
    assert item_reading(graph, ctx, ITEM, lock).owed == ()


def test_a_later_failed_record_takes_the_item_out_of_executed(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, git = roots(host)
    record_action(spec, repo, git, Address(ITEM, "a01"), "done")
    record_action(spec, repo, git, Address(ITEM, "a01"), "failed")
    reading = item_reading(graph_of(host), context(host), ITEM, read_lock(spec))
    assert not reading.executed and [entry.action for entry in reading.owed] == ["a01"]


def test_an_item_with_no_action_is_executed_and_an_unknown_item_is_not_found(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    edit_doc(host, PLAN, lambda document: document["plan"]["spec_alignment"]["checklist"][0]["implementation"].update(actions=[]))
    graph, ctx = graph_of(host), context(host)
    assert item_reading(graph, ctx, ITEM, None).executed
    with pytest.raises(KeyError):
        item_reading(graph, ctx, "NO_SUCH_ITEM", None)


@pytest.mark.parametrize(
    ("command", "names"),
    [
        (PASSING, True),
        ("  echo   expected\tline ", True),
        ('echo "expected line"', False),
        ("echo expected line --verbose", False),
        ("", False),
    ],
)
def test_naming_a_verifier_compares_after_collapsing_whitespace(tmp_path: Path, command: str, names: bool) -> None:
    host = plan_host(tmp_path, action("a02", "run_command", command=command or "true"), bindings=(alpha_binding(),))
    graph = graph_of(host)
    item = graph.by_id[ITEM]
    candidate = {"id": "a02", "type": "run_command", "command": command}
    assert bool(naming_bindings(graph, item, candidate)) is names


def test_other_quoting_is_not_naming_a_verifier_and_the_message_says_so(tmp_path: Path) -> None:
    host = plan_host(tmp_path, action("a02", "run_command", command='echo "expected line"'), bindings=(alpha_binding(),))
    spec, repo, git = roots(host)
    result = record_action(spec, repo, git, Address(ITEM, "a02"), "done")
    assert result.record["action"] == "a02"
    (note,) = result.notes
    assert "does not name a verifier" in note and ALPHA in note and "collapsing whitespace" in note
