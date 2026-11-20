"""M8 schema shapes (WI-M8-02): the plan-schema additions, the anchor ``close`` extras and the two record schemas."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.schema_validate import validate_data_against_schema

from ..graph._synth import EXAMPLE_SPEC, ROOT

PLAN_REL = "impl_context/ms_account_recovery_plan.json"
ITEM = "PWRESET_CONFIRM_EXPIRED_01"
HASH = "sha256:" + "ab" * 32
AUTHOR = {"name": "A Person", "email": "person@example.org"}
RECORD = {
    "record_id": "rec-0001",
    "about": [ITEM],
    "action": "a01",
    "outcome": "done",
    "note": "Rejected expired tokens before the password update.",
    "realises_hash": HASH,
    "recorded_at": "2026-11-21T10:00:00Z",
    "git_author": AUTHOR,
}
FINDING = {
    "id": "finding-missing-null-check",
    "type": "bug",
    "severity": "minor",
    "spec_ref": {"type": "fr", "id": "fr-password-reset-confirm"},
    "description": "Missing null check on the token lookup at src/routes/confirm.ts:42, so an unknown token raises.",
    "metadata": {"source": "code review", "impact": "A 500 instead of a 410."},
}
SIGNOFF = {
    "signoff_id": "so-ms-account-recovery-0001",
    "about": ["ms-account-recovery"],
    "tree": "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
    "git_author": AUTHOR,
    "recorded_at": "2026-11-21T10:00:00Z",
    "listed": {
        "manual_fixtures": 2,
        "attested": 1,
        "deferred_tasks": [],
        "wont_do_tasks": [],
        "open_items": 0,
        "staging_prod_proof_owed": ["fix-reset-email-delivery-time"],
    },
}
AT_DEPLOY = {
    "deploy_id": "dep-0001",
    "about": [ITEM],
    "milestone": "ms-account-recovery",
    "action": "a01",
    "env": "staging",
    "tag": "v1.2.0",
    "tree": "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
    "outcome": "done",
    "recorded_at": "2026-11-21T10:00:00Z",
    "git_author": AUTHOR,
}


def _plan() -> dict[str, Any]:
    return json.loads((EXAMPLE_SPEC / PLAN_REL).read_text(encoding="utf-8"))


def _action(plan: dict[str, Any]) -> dict[str, Any]:
    return plan["plan"]["spec_alignment"]["checklist"][0]["implementation"]["actions"][0]


def _problems(document: dict[str, Any]) -> list[str]:
    """``path: message`` of each schema violation of *document*, sorted."""
    errors = validate_data_against_schema(str(ROOT), document)
    return sorted(f"{'/'.join(str(p) for p in path)}: {message}" for path, message in errors)


def _wrap(uri: str, record: dict[str, Any]) -> dict[str, Any]:
    return {"$schema": uri, "records": [copy.deepcopy(record)]}


def test_action_accepts_id_and_at_deploy() -> None:
    plan = _plan()
    _action(plan).update({"id": "a01", "at_deploy": ["staging", "prod"]})
    assert _problems(plan) == []


@pytest.mark.parametrize("value", [[], ["dev"], ["ci"], ["staging", "staging"], "staging"], ids=["empty", "dev", "ci", "twice", "string"])
def test_action_rejects_a_bad_at_deploy_value(value: Any) -> None:
    plan = _plan()
    _action(plan)["at_deploy"] = value
    assert [p for p in _problems(plan) if "at_deploy" in p]


@pytest.mark.parametrize(("value", "valid"), [("a01", True), ("a99", True), ("a100", True), ("a1", False), ("A01", False), ("action-1", False), ("a01 ", False)])
def test_action_id_pattern(value: str, valid: bool) -> None:
    plan = _plan()
    _action(plan)["id"] = value
    assert (_problems(plan) == []) is valid


def _with_execution(**fields: Any) -> dict[str, Any]:
    plan = _plan()
    plan["execution"] = fields
    return plan


@pytest.mark.parametrize(
    "override",
    [{}, {"note": None}, {"realises_hash": None}, {"outcome": "blocked"}],
    ids=["full", "no-note", "no-hash", "blocked"],
)
def test_execution_records_shape_accepts(override: dict[str, Any]) -> None:
    record = {key: value for key, value in {**RECORD, **override}.items() if value is not None or key == "realises_hash"}
    assert _problems(_with_execution(records=[record])) == []


@pytest.mark.parametrize(
    ("change", "word"),
    [
        ({"record_id": "rec-1"}, "record_id"),
        ({"outcome": "skipped"}, "outcome"),
        ({"note": "x" * 201}, "note"),
        ({"about": [ITEM, "OTHER_ITEM_01"]}, "about"),
        ({"action": "second"}, "action"),
        ({"realises_hash": "md5:abc"}, "realises_hash"),
        ({"extra": 1}, "extra"),
    ],
)
def test_execution_records_shape_and_limits(change: dict[str, Any], word: str) -> None:
    problems = _problems(_with_execution(records=[{**RECORD, **change}]))
    assert problems and all(word in problem or "records" in problem for problem in problems)
    assert any(word in problem for problem in problems)
    assert _problems(_with_execution(records=[{**RECORD, "note": "x" * 200}])) == []
    assert _problems(_with_execution(records=[RECORD] * 1001))


def test_a_required_field_of_an_execution_record_is_named() -> None:
    record = {key: value for key, value in RECORD.items() if key != "git_author"}
    assert any("git_author" in problem for problem in _problems(_with_execution(records=[record])))


def _with_review(**fields: Any) -> dict[str, Any]:
    plan = _plan()
    plan["review"] = {"verdict": "needs_work", **fields}
    return plan


def test_review_block_shape_and_limits() -> None:
    assert _problems(_with_review(findings=[FINDING], next_actions="Fix the null check.", recorded_at="2026-11-21T10:00:00Z")) == []
    assert _problems(_with_review(findings=[{**FINDING, "description": "d" * 600}])) == []
    assert any("description" in p for p in _problems(_with_review(findings=[{**FINDING, "description": "d" * 601}])))
    assert _problems(_with_review(findings=[{**FINDING, "id": f"finding-{n}"} for n in range(50)])) == []
    assert _problems(_with_review(findings=[{**FINDING, "id": f"finding-{n}"} for n in range(51)]))
    assert _problems(_with_review(next_actions="n" * 1000)) == []
    assert any("next_actions" in p for p in _problems(_with_review(next_actions="n" * 1001)))
    assert any("recorded_at" in p for p in _problems(_with_review(recorded_at=3)))


def _anchor(row: dict[str, Any]) -> dict[str, Any]:
    anchor = json.loads((EXAMPLE_SPEC / "16_impl_context.json").read_text(encoding="utf-8"))
    anchor["plan"]["milestone_index"] = [{**anchor["plan"]["milestone_index"][0], **row}]
    return anchor


CLOSE = {
    "signed_off_by": "person@example.org",
    "tree": "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
    "signoff": "so-ms-account-recovery-0001",
    "plan_hash": HASH,
    "closed_at": "2026-11-21T10:00:00Z",
    "migrations": [{"hash_after": HASH, "note": "Renamed an item."}],
}


def test_anchor_close_extras_and_deferral_reason_limit() -> None:
    assert _problems(_anchor({"status": "done", "close": CLOSE})) == []
    legacy = {"signed_off_by": "legacy-migration", "source": "context_path status done", "signoff": None}
    assert _problems(_anchor({"status": "done", "close": legacy})) == []
    assert any("plan_hash" in p for p in _problems(_anchor({"status": "done", "close": {**CLOSE, "plan_hash": "abc"}})))
    assert any("hash_after" in p for p in _problems(_anchor({"status": "done", "close": {**CLOSE, "migrations": [{"note": "n"}]}})))
    assert any("review_verdict" in p for p in _problems(_anchor({"status": "done", "close": {**CLOSE, "review_verdict": "verified"}})))
    assert _problems(_anchor({"status": "deferred", "deferral_reason": "r" * 300})) == []
    assert any("deferral_reason" in p for p in _problems(_anchor({"status": "deferred", "deferral_reason": "r" * 301})))


def test_signoff_record_validates() -> None:
    uri = "vc:extras:signoff-record"
    assert _problems(_wrap(uri, SIGNOFF)) == []
    for change in ({"signoff_id": "signoff-1"}, {"signoff_id": "so-ms-account-recovery-1"}, {"about": []}, {"tree": ""}):
        assert _problems(_wrap(uri, {**SIGNOFF, **change})), change
    missing = {key: value for key, value in SIGNOFF.items() if key != "listed"}
    assert any("listed" in p for p in _problems(_wrap(uri, missing)))
    assert _problems({"$schema": uri, "records": [SIGNOFF, SIGNOFF]})


def test_at_deploy_record_validates() -> None:
    uri = "vc:extras:at-deploy-record"
    assert _problems(_wrap(uri, AT_DEPLOY)) == []
    assert _problems(_wrap(uri, {**AT_DEPLOY, "git_author": {"name": "ci", "email": ""}})) == []
    assert _problems(_wrap(uri, {key: value for key, value in AT_DEPLOY.items() if key != "tag"})) == []
    for change in ({"deploy_id": "ver-0001"}, {"env": "dev"}, {"outcome": "blocked"}, {"action": "second"}, {"about": []}):
        assert _problems(_wrap(uri, {**AT_DEPLOY, **change})), change
    assert _problems({"$schema": uri, "records": [AT_DEPLOY, AT_DEPLOY]})


def test_the_record_schemas_are_registered() -> None:
    registry = json.loads((ROOT / "tools" / "schema_registry.json").read_text(encoding="utf-8"))
    assert registry["vc:extras:signoff-record"] == "schema/extras/signoff_record.schema.json"
    assert registry["vc:extras:at-deploy-record"] == "schema/extras/at_deploy_record.schema.json"
    assert all((Path(ROOT) / registry[uri]).is_file() for uri in ("vc:extras:signoff-record", "vc:extras:at-deploy-record"))
