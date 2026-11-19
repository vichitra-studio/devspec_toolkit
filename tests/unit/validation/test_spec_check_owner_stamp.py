"""The owner of a ``spec-check`` finding: the one it carries, else the row of the ownership table, else the check's default."""
from __future__ import annotations

import shutil
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.graph.ownership import OwnerContext, OwnershipRow
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import (
    CheckContext,
    CheckSpec,
    _with_default_owner,
    register_check,
    run_registered_checks,
)

from ..trace._lock_support import EXAMPLE_HOST

ROOT = Path(__file__).parents[3]
DEFAULT = "step:08"


def _context(rule: str, *codes: str) -> OwnerContext:
    return OwnerContext(rows=(OwnershipRow(class_name="row", owner_rule=rule, codes=codes, authority=""),))


def _finding(code: str, owner: str | None = None) -> SpecError:
    return SpecError(code=code, message="m", owner=owner)


def _owners(errors: list[SpecError], context: OwnerContext) -> list[str | None]:
    stamped = _with_default_owner({"status": "FAIL", "errors": errors}, DEFAULT, context)
    return [error.owner for error in stamped["errors"]]


def test_a_code_with_a_fixed_step_row_gets_that_step() -> None:
    assert _owners([_finding("E901")], _context("fixed_step:04", "E901")) == ["step:04"]


def test_a_code_with_a_gate_row_gets_the_gate() -> None:
    assert _owners([_finding("E901")], _context("close-gate", "E901")) == ["close-gate"]


def test_a_code_with_no_row_gets_the_default_of_the_check() -> None:
    assert _owners([_finding("E902")], _context("fixed_step:04", "E901")) == [DEFAULT]


def test_a_node_rule_row_has_no_answer_without_a_node_and_falls_to_the_default() -> None:
    assert _owners([_finding("E901")], _context("holder_step", "E901")) == [DEFAULT]


def test_a_finding_that_carries_an_owner_keeps_it() -> None:
    error = _finding("E901", "step:12")
    assert _owners([error], _context("fixed_step:04", "E901")) == ["step:12"]


def test_a_result_with_no_findings_is_returned_as_it_is() -> None:
    result = {"status": "PASS"}
    assert _with_default_owner(result, DEFAULT, _context("fixed_step:04", "E901")) is result


@pytest.mark.parametrize(("rule", "owner"), [("fixed_step:04", "step:04"), ("merge-check", "merge-check")])
def test_the_run_follows_the_table_it_is_given_as_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rule: str, owner: str
) -> None:
    """The mutation of WI-M6a-12 (rows of E607 changed, owners unchanged) is killed here: the E607 row decides the owner."""
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    finding = make_error("E607", "drift")
    registry: list[CheckSpec] = []
    monkeypatch.setattr(check_registry, "CHECK_REGISTRY", registry)
    register_check("table-probe", lambda _ctx: {"status": "FAIL", "errors": [finding]}, default_owner=DEFAULT)
    ctx = CheckContext(repo_root=str(ROOT), spec_dir=str(host / "spec"))
    ctx.owner_context = _context(rule, "E607")
    checks: OrderedDict[str, dict[str, Any]] = run_registered_checks(ctx)
    assert [error.owner for error in checks["table-probe"]["errors"]] == [owner]
