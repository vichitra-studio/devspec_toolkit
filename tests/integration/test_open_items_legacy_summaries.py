"""The legacy open items of one plan give one W630 for each array, through ``spec-check`` (M6a review round 2, G1-2).

A plan with items of the 1.1.1 shape in both ``plan.ambiguities`` (step 16a) and ``execution.emergent_ambiguities``
(step 16b), the same number in each, must show two W630: the dedupe of ``spec-check`` drops a finding with the same
code, message and path, so the summaries must differ in their text.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import attest, run_split, step_gate_host
from unit.graph._synth import ROOT

PLAN = "impl_context/ms_account_recovery_plan.json"
PLAN_16A = "plan.ambiguities"
EMERGENT_16B = "execution.emergent_ambiguities"


def _legacy(item_id: str) -> dict[str, Any]:
    return {"id": item_id, "description": "old question", "severity": "low", "status": "open", "impact": ["x"]}


@pytest.fixture
def host(tmp_path: Path) -> Path:
    folder = step_gate_host(tmp_path / "host")
    path = folder / "spec" / PLAN
    document = json.loads(path.read_text(encoding="utf-8"))
    document.setdefault("plan", {})["ambiguities"] = [_legacy("amb-a1"), _legacy("amb-a2")]
    document.setdefault("execution", {})["emergent_ambiguities"] = [_legacy("amb-e1"), _legacy("amb-e2")]
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    attest(folder)
    return folder


def _run(capsys: pytest.CaptureFixture[str], host: Path, *flags: str) -> tuple[int, str, str]:
    spec = str(host / "spec")
    return run_split(capsys, "spec-check", spec, "--repo-root", str(ROOT), "--spec-root", spec, "--git-root", str(host), *flags)


def _w630(findings: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return sorted((f["owner"], f["message"]) for f in findings if f["code"] == "W630")


def _expected(owner: str, array: str) -> tuple[str, str]:
    return owner, f"2 legacy open items in {PLAN} ({array}); see `upstream-backlog`"


def test_plain_spec_check_json_has_one_summary_for_each_array(host: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _code, out, err = _run(capsys, host, "--json")

    findings = json.loads(out)["checks"]["open-items"]["findings"]
    assert _w630(findings) == [_expected("step:16a", PLAN_16A), _expected("step:16b", EMERGENT_16B)]


def test_plain_spec_check_text_counts_both_summaries(host: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _code, _out, err = _run(capsys, host)

    assert any(line.strip().startswith("[WARN] open-items") and "2 warnings" in line for line in err.splitlines())


@pytest.mark.parametrize(
    ("step", "owner", "array"), [("16a", "step:16a", PLAN_16A), ("16b", "step:16b", EMERGENT_16B)]
)
def test_each_step_gate_lists_the_summary_of_its_own_array(
    host: Path, capsys: pytest.CaptureFixture[str], step: str, owner: str, array: str
) -> None:
    _code, out, _err = _run(capsys, host, "--step", step, "--json")

    gate = json.loads(out)["step_gate"]
    assert _w630(gate["own_warnings"]) == [_expected(owner, array)]
