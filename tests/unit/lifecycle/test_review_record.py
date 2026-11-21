"""``specdev review record``: the verdict, the findings mapped from a converged findings file, the refusals."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.lifecycle.review_record import VERDICTS, ReviewRequest, record_review
from unit.lifecycle._record_support import ITEM, close_milestone, plan_document, plan_host, roots
from unit.lifecycle._support import MILESTONE, PLAN
from unit.trace._lock_support import run_on_example

RATINGS = {"spec_completeness": 4, "code_quality": 4, "tests_completeness": 3, "docs_completeness": 3, "metadata_usage": 4}
BUG = {
    "kind": "bug",
    "location": "src/routes/password-resets/confirm.ts#confirm",
    "signature": "abc123",
    "message": "The handler updates the password before it checks the token age, so an expired token still changes the hash.",
    "severity": "P0",
    "evidence": ["confirm.ts:42 awaits setPassword first"],
    "suggested_fix": "Check the token age before setPassword.",
}
GAP = {"kind": "gap", "location": "docs/api/password-resets.md", "signature": "def456", "message": "The docs omit the 410 response.", "severity": "P2", "upstream_refs": [ITEM, "fr-password-reset-request"]}


def _findings(tmp_path: Path, findings: list[dict[str, Any]], *, scope: str = "ms-account-recovery-plan", **top: Any) -> str:
    document = {"$schema": "vc:infra:findings", "round": 1, "scope": scope, "generated_at": 1700000000, "findings": findings, **top}
    document = {key: value for key, value in document.items() if value is not None}
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


def _record(host: Path, verdict: str, **given: Any) -> Any:
    spec, repo, _git = roots(host)
    return record_review(spec, repo, ReviewRequest(MILESTONE, verdict, **given))


def _refusal(call: Any) -> Any:
    with pytest.raises(FindingError) as caught:
        call()
    return caught.value.error


def _review(host: Path) -> dict[str, Any]:
    return plan_document(host)["review"]


def test_unknown_verdict_is_e823(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    error = _refusal(lambda: _record(host, "approved"))
    assert error.code == "E823" and "approved" in error.message and "needs_work" in error.message


def test_verdicts_are_the_schema_enum() -> None:
    from specdev_tools.core.json_utils import find_schema_dir

    schema = json.loads((Path(find_schema_dir(None) or "") / "16_impl_context.schema.json").read_text(encoding="utf-8"))
    assert tuple(schema["properties"]["review"]["properties"]["verdict"]["enum"]) == VERDICTS


def test_finding_naming_an_unknown_item_is_e823(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    path = _findings(tmp_path, [{**GAP, "upstream_refs": ["PWRESET_NO_SUCH_ITEM"]}])
    error = _refusal(lambda: _record(host, "needs_work", findings_file=path))
    assert error.code == "E823" and "PWRESET_NO_SUCH_ITEM" in error.message and "finding 1" in error.message
    assert "review" not in plan_document(host)


@pytest.mark.parametrize("finding", [BUG, {**BUG, "severity": "P1"}])
def test_verified_with_a_blocking_finding_is_accepted(tmp_path: Path, finding: dict[str, Any]) -> None:
    host = plan_host(tmp_path)
    _record(host, "verified", findings_file=_findings(tmp_path, [finding]))
    review = _review(host)
    assert review["verdict"] == "verified" and review["findings"][0]["severity"] in ("blocking", "major")


def test_verified_with_red_security_is_accepted(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    _record(host, "verified", security_status="red", findings_file=_findings(tmp_path, []))
    assert (_review(host)["verdict"], _review(host)["security_status"]) == ("verified", "red")


def test_needs_work_with_findings(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    result = _record(host, "needs_work", findings_file=_findings(tmp_path, [BUG, GAP], scope=ITEM), next_actions="Fix finding-01.", ratings_json=json.dumps(RATINGS))
    first, second = _review(host)["findings"]
    assert (first["id"], first["type"], first["severity"], first["related_checklist_ids"]) == ("finding-01", "bug", "blocking", [ITEM])
    assert first["spec_ref"] == {"type": "code", "id": MILESTONE, "note": BUG["location"]}
    assert first["remediation_task"] == {"task_id": "fix-finding-01", "summary": BUG["suggested_fix"], "files_to_touch": ["src/routes/password-resets/confirm.ts"], "checklist_ids": [ITEM]}
    assert first["metadata"] == {"source": f"findings round 1, scope {ITEM}", "impact": BUG["evidence"][0]}
    assert (second["type"], second["severity"], second["metadata"]["impact"]) == ("gap", "minor", "gap") and "remediation_task" not in second
    assert _review(host)["ratings"] == RATINGS and _review(host)["next_actions"] == "Fix finding-01."
    assert result.block == _review(host)


def test_a_finding_already_verified_is_left_out(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    _record(host, "needs_work", findings_file=_findings(tmp_path, [{**BUG, "status": "verified"}, GAP]))
    assert [finding["description"] for finding in _review(host)["findings"]] == [GAP["message"]]


def test_block_is_replaced_not_appended(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    _record(host, "needs_work", findings_file=_findings(tmp_path, [BUG]), next_actions="Fix it.")
    _record(host, "verified", findings_file=_findings(tmp_path, []))
    review = _review(host)
    assert review["findings"] == [] and review["verdict"] == "verified" and "next_actions" not in review
    assert set(review) == {"findings", "verdict", "recorded_at"}


def test_block_validates_against_the_schema(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    _record(host, "needs_work", findings_file=_findings(tmp_path, [BUG, GAP]), security_status="green", ratings_json=json.dumps(RATINGS))
    assert validate_data_against_schema(str(roots(host).repo), plan_document(host)) == []


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ({"security_status": "amber"}, "security_status"),
        ({"ratings_json": '{"code_quality": 4}'}, "docs_completeness"),
        ({"ratings_json": "not json"}, "--ratings-json is not JSON"),
        ({"ratings_json": "[1]"}, "not a JSON object"),
    ],
)
def test_a_block_that_breaks_the_schema_or_the_input_is_e823(tmp_path: Path, given: dict[str, Any], expected: str) -> None:
    host = plan_host(tmp_path)
    error = _refusal(lambda: _record(host, "blocked", **given))
    assert error.code == "E823" and expected in error.message
    assert "review" not in plan_document(host)


def _without_schema(tmp_path: Path) -> str:
    path = tmp_path / "plain.json"
    path.write_text(json.dumps({"round": 1, "scope": "x", "generated_at": 1, "findings": []}), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    ("make", "expected"),
    [
        (_without_schema, 'has no "$schema"'),
        (lambda tmp: _findings(tmp, [{key: value for key, value in BUG.items() if key != "message"}]), "'message' is a required property"),
        (lambda tmp: _findings(tmp, [], round=None), "'round' is a required property"),
        (lambda tmp: _findings(tmp, [{**BUG, "message": "x" * 601}]), "above 600"),
        (lambda tmp: str(tmp / "missing.json"), "cannot be read as JSON"),
    ],
)
def test_a_findings_file_that_is_not_usable_is_e823_and_names_what_is_wrong(tmp_path: Path, make: Any, expected: str) -> None:
    host = plan_host(tmp_path)
    error = _refusal(lambda: _record(host, "needs_work", findings_file=make(tmp_path)))
    assert error.code == "E823" and expected in error.message


def test_frozen_plan_is_refused_e820(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    close_milestone(host)
    before = (host / "spec" / PLAN).read_bytes()
    assert _refusal(lambda: _record(host, "verified")).code == "E820"
    assert (host / "spec" / PLAN).read_bytes() == before


def test_no_plan_for_the_milestone_is_e803(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    spec, repo, _git = roots(host)
    assert _refusal(lambda: record_review(spec, repo, ReviewRequest("ms-nope", "verified"))).code == "E803"


def test_plan_size_report_is_printed(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    before = len((host / "spec" / PLAN).read_bytes())
    code, output = run_on_example(host, "review", "record", MILESTONE, "--verdict", "deferred")
    after = len((host / "spec" / PLAN).read_bytes())
    assert code == 0 and "verdict deferred" in output
    assert f"plan file: {before} bytes before, {after} bytes after" in output
