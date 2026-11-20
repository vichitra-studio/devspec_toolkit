"""Owner rows of the pre-graph codes that ``spec-check`` still emits (WI-M6a-01), checked against their emitters."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import step_gate_host
from specdev_tools.graph.ownership import OwnerContext, load_ownership_table, owner_for
from specdev_tools.validation.spec_check import run_spec_check_json

from ..trace._lock_support import EXAMPLE_HOST

ROOT = Path(__file__).parents[3]
MERGE_CHECK = "merge-check"
SCHEMA_URI_MISSING = "missing_schema_uri"
DEAD_CLOSURE_CODES = (
    "E560", "W562", "W563", "W564", "W565", "W568", "W569", "W575", "W576", "E535", "E536",
)


@pytest.fixture(scope="module")
def context() -> OwnerContext:
    return OwnerContext(rows=load_ownership_table(str(ROOT)))


@pytest.fixture
def host(tmp_path: Path) -> Path:
    copy = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, copy)
    return copy


def _findings(host: Path, check: str) -> list[dict[str, Any]]:
    _errors, report = run_spec_check_json(str(ROOT), str(host / "spec"), git_root=str(host))
    return report["checks"][check]["findings"]


def test_e607_row_gives_fixed_step_03(context: OwnerContext) -> None:
    assert owner_for("E607", None, context) == "step:03"


@pytest.mark.parametrize("code", ["E608", "E620", "E621", "E622", "W554"])
def test_merge_check_rows_for_legacy_codes(context: OwnerContext, code: str) -> None:
    assert owner_for(code, None, context) == MERGE_CHECK


@pytest.mark.parametrize("code", DEAD_CLOSURE_CODES)
def test_dead_closure_codes_have_no_owner_row(context: OwnerContext, code: str) -> None:
    """The readers of these codes report nothing on a 1.2.0 spec and M6c deletes them: no row, so no owner from the table."""
    assert all(code not in row.codes for row in context.rows)
    assert owner_for(code, None, context) is None


def test_e590_missing_capability_coverage_is_owned_by_step_02(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host", ["uncovered_capability"])
    (finding,) = [f for f in _findings(host, "schema-validation") if f["code"] == "E590"]
    assert "cap-account-export" in finding["message"]
    assert finding["owner"] == "step:02"


@pytest.mark.parametrize(
    ("delta", "check", "code"),
    [
        ("broken_link_in_step_04", "graph", "E700"),
        ("glossary_drift", "glossary-drift-check", "E607"),
        ("missing_seed_file", "seed-lint", "E520"),
    ],
)
def test_step_gate_delta_raises_its_code(tmp_path: Path, delta: str, check: str, code: str) -> None:
    host = step_gate_host(tmp_path / "host", [delta])
    assert code in {finding["code"] for finding in _findings(host, check)}


@pytest.mark.parametrize("delta", ["fr_nothing_uses", "open_items", "plan_ambiguity"])
def test_step_gate_delta_that_adds_content_raises_no_error_of_its_own(tmp_path: Path, delta: str) -> None:
    host = step_gate_host(tmp_path / "host", [delta])
    assert _findings(host, "schema-validation") == []
    assert _findings(host, "graph") == []


@pytest.mark.parametrize(
    ("plan", "step"),
    [
        ({}, "16a"),
        ({"execution": {"execution_results": [{"x": 1}]}}, "16b"),
        ({"review": {"verdict": "verified"}}, "16c"),
    ],
)
def test_plan_file_error_owner_follows_the_file_stage(host: Path, plan: dict[str, Any], step: str) -> None:
    for old in (host / "spec" / "impl_context").glob("*.json"):
        old.unlink()
    (host / "spec" / "impl_context" / "ms_stage_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (finding,) = [
        f for f in _findings(host, "schema-validation")
        if SCHEMA_URI_MISSING in f["message"] and "ms_stage_plan.json" in f["message"]
    ]
    assert finding["owner"] == f"step:{step}"
