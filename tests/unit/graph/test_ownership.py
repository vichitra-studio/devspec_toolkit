"""Error ownership: the table, the owner rules, and the owner stamped on per-file errors."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core.config import reset_config
from specdev_tools.core.errors import ERROR_CODES, SpecError, make_error
from specdev_tools.graph.model import Node
from specdev_tools.graph.ownership import (
    OwnerContext,
    OwnershipRow,
    load_ownership_table,
    owner_for,
    stamp_file_owner,
    step_for_file,
)
from specdev_tools.validation.spec_check import run_spec_check_json
from specdev_tools.validation.validate import _apply_we_promotion

ROOT = Path(__file__).parents[3]
OWNED_CODES = ("E700", "E701", "E702", "E703", "W720")
USAGE_CODES = ("E705", "E706", "E707", "E708", "E709")
SCHEMA_URI_MISSING = "missing_schema_uri"


def _node(step: str | None = "04", kind: str = "fr") -> Node:
    return Node(
        id="fr-login", kind=kind, step=step, role=None, file="04_fr_list.json", jq_path=".fr[0]",
        parent=None, children=(), lifecycle="active", scope=None, links=(), label="fr-login",
    )


@pytest.fixture(scope="module")
def table() -> tuple[OwnershipRow, ...]:
    return load_ownership_table(str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_config():
    reset_config()
    yield
    reset_config()


@pytest.fixture
def spec_dir(tmp_path: Path) -> Path:
    """A spec folder of three files, none with a ``$schema``: a step 04 file, a plan file in the 16c stage, a file with no step."""
    spec = tmp_path / "spec"
    (spec / "impl_context").mkdir(parents=True)
    (spec / "04_fr_list.json").write_text("{}", encoding="utf-8")
    (spec / "impl_context" / "ms_a_plan.json").write_text(
        json.dumps({"review": {"verdict": "verified"}}), encoding="utf-8"
    )
    (spec / "notastep.json").write_text("{}", encoding="utf-8")
    return spec


def _schema_findings(spec: Path) -> dict[str, dict]:
    """The schema-validation findings of ``spec-check --json`` by file base name."""
    _errors, context = run_spec_check_json(str(ROOT), str(spec))
    findings = context["checks"]["schema-validation"]["findings"]
    return {Path(f["message"].split(":", 1)[0]).name: f for f in findings if SCHEMA_URI_MISSING in f["message"]}


def test_every_gate_code_has_owner_and_node_id(table):
    ctx = OwnerContext(rows=table)
    node = _node()
    for code in OWNED_CODES:
        err = make_error(code, f"{code} message", owner=owner_for(code, node, ctx), node_id=node.id)
        assert err.owner == "step:04", code
        assert err.node_id == "fr-login", code
    for code in USAGE_CODES:
        err = make_error(code, f"{code} message")
        assert (err.owner, err.node_id) == (None, None), code
        assert owner_for(code, node, ctx) is None, code


def test_owner_for_finds_code_in_any_row_list():
    ctx = OwnerContext(
        rows=(
            OwnershipRow("a", "fixed_step:14", ("E901",), ""),
            OwnershipRow("b", "node_step", ("E902", "E903"), ""),
            OwnershipRow("c", "close-gate", ("E904",), ""),
            OwnershipRow("d", "furthest_usable_step", ("E905",), ""),
        ),
        furthest_step={"fr": "07"},
    )
    node = _node(step="05")
    assert owner_for("E901", node, ctx) == "step:14"
    assert owner_for("E903", node, ctx) == "step:05"
    assert owner_for("E904", None, ctx) == "close-gate"
    assert owner_for("E905", node, ctx) == "step:07"
    assert owner_for("E999", node, ctx) is None


def test_ownership_table_codes_exist(table):
    assert len(table) == 15
    for row in table:
        for code in row.codes:
            assert code in ERROR_CODES, f"{row.class_name}: {code}"


def test_per_check_finding_carries_owner(spec_dir):
    findings = _schema_findings(spec_dir)
    assert findings["04_fr_list.json"]["owner"] == "step:04"
    assert "node_id" not in findings["04_fr_list.json"]


def test_promoted_code_keeps_owner_and_node_id(monkeypatch):
    monkeypatch.setenv("SPECDEV_WARNINGS_AS_ERRORS", "1")
    reset_config()
    warning = SpecError(code="W615", message="m", owner="step:06", node_id="inv-x")
    (promoted,) = _apply_we_promotion([warning])
    assert promoted.code == "E615"
    assert (promoted.owner, promoted.node_id) == ("step:06", "inv-x")


def test_legacy_per_file_error_gets_step_owner(spec_dir):
    findings = _schema_findings(spec_dir)
    assert findings["04_fr_list.json"]["owner"] == "step:04"
    assert "owner" not in findings["notastep.json"]


@pytest.mark.parametrize(
    ("document", "step"),
    [
        ({}, "16a"),
        ({"execution": {"execution_results": [{"x": 1}]}}, "16b"),
        ({"review": {"verdict": "verified"}}, "16c"),
    ],
)
def test_plan_file_error_owner_substep(document, step):
    path = "spec/impl_context/ms_a_plan.json"
    assert step_for_file(path, document) == step
    (stamped,) = stamp_file_owner([make_error("E520", "m")], step_for_file(path, document))
    assert stamped.owner == f"step:{step}"


def test_plan_file_in_spec_check_gets_16c_owner(spec_dir):
    assert _schema_findings(spec_dir)["ms_a_plan.json"]["owner"] == "step:16c"


@pytest.mark.parametrize("path", ["spec/common/seed_manifest.json", "spec/canon/manifest.json"])
def test_step_for_file_is_none_without_a_step(path):
    assert step_for_file(path, {}) is None


def test_stamp_file_owner_keeps_an_owner_already_set():
    owned = make_error("E700", "m", owner="step:12", node_id="job-x")
    plain = make_error("E520", "m")
    kept, stamped = stamp_file_owner([owned, plain], "04")
    assert (kept.owner, kept.node_id) == ("step:12", "job-x")
    assert (stamped.owner, stamped.node_id) == ("step:04", None)
    assert plain.owner is None
    assert stamp_file_owner([plain], None) == [plain]
