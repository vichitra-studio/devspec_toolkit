"""``upstream-backlog`` on a host copy of the worked example: the DOC 13.2 scenario through the CLI (WI-M6a-12).

The items are the ones of ``tests/fixtures/step_gate/deltas/open_items.json`` (a step file) and
``open_items_in_anchor_and_plan.json`` (the anchor and a milestone plan).  Unit and fixture-level cases are in
``tests/integration/analysis/test_upstream_backlog_cli.py``.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import (
    insert_delta_items_with_the_cli,
    json_command,
    run_split,
    skill_backlog_jq,
    step_gate_host,
)
from specdev_tools.validation.open_items import check_open_items
from unit.trace._lock_support import ROOT

ITEM_DELTAS = ["open_items", "open_items_in_anchor_and_plan"]
GROUPED = [
    ("seed", "amb-reset-seed", "05_interface_contracts.json"),
    ("04", "amb-reset-criterion", "08_fixtures.json"),
    ("04", "amb-anchor-lockout", "16_impl_context.json"),
    ("04", "amb-plan-lockout-contract", "impl_context/ms_account_recovery_plan.json"),
    ("05", "amb-plan-lockout-contract", "impl_context/ms_account_recovery_plan.json"),
]
TOTALS = "Totals: 4 items / 2 with answer / 2 needing answer."
EMPTY_TOTALS = "Totals: 0 items / 0 with answer / 0 needing answer."


def _backlog(capsys: pytest.CaptureFixture[str], host: Path, *flags: str) -> tuple[int, str, str]:
    return run_split(capsys, "upstream-backlog", str(host / "spec"), "--repo-root", str(ROOT), *flags)


def _tree_digest(root: Path) -> str:
    """One hash over every file under *root* (name and bytes), to show that a command wrote nothing."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode() + path.read_bytes())
    return digest.hexdigest()


def test_backlog_groups_after_the_13_2_scenario(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host", ITEM_DELTAS)
    before = _tree_digest(host)
    code, out, err = _backlog(capsys, host, "--json")
    assert code == 0, err
    payload = json.loads(out)
    assert payload["schema_version"] == "2"
    records = payload["records"]
    assert [(r["group"], r["item_id"], r["artifact"]) for r in records] == GROUPED
    also_in = {(r["group"], r["item_id"]): r["also_in"] for r in records if r["also_in"]}
    assert also_in == {("05", "amb-plan-lockout-contract"): ["04"]}
    assert {r["item_id"] for r in records if r["decision"]} == {"amb-reset-seed", "amb-plan-lockout-contract"}
    assert payload["summary"] == {
        "items": 4, "with_answer": 2, "needing_answer": 2, "unplaced_count": 0, "hidden_by_status_count": 0
    }
    assert _tree_digest(host) == before


def test_backlog_plain_output_lists_groups_seed_first_with_also_in_and_the_totals_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = step_gate_host(tmp_path / "host", ITEM_DELTAS)
    code, out, err = _backlog(capsys, host)
    assert code == 0 and err == "", err
    assert out.index("seed - 1 item(s)") < out.index("04 - 3 item(s)") < out.index("05 - 1 item(s)")
    assert "amb-plan-lockout-contract - answer known (also in 04)" in out
    assert "amb-reset-criterion - needs operator answer" in out
    assert out.splitlines()[-1] == TOTALS


def test_skill_jq_expression_turns_the_backlog_json_into_pointers_that_resolve(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    host = step_gate_host(tmp_path / "host", ITEM_DELTAS)
    _code, backlog_json, _err = _backlog(capsys, host, "--json")
    piped = subprocess.run(["jq", skill_backlog_jq()], input=backlog_json, capture_output=True, text=True, check=True)
    pointers = json.loads(piped.stdout)
    assert {(p["file"], p["id"]) for p in pointers} == {
        ("spec/04_fr_list.json", "ac-password-reset-3"),
        ("spec/04_fr_list.json", "fr-password-reset"),
        ("spec/05_interface_contracts.json", "api-password-reset-confirm"),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(piped.stdout))
    code, out, err = run_split(
        capsys, "json", "resolve-pointers", "--repo-root", str(ROOT), "--git-root", str(host)
    )
    assert code == 0, err
    results = json.loads(out)["results"]
    assert len(results) == len(pointers) and all(result["exists"] for result in results)


def test_backlog_refuses_a_spec_folder_that_does_not_exist(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = _backlog(capsys, tmp_path / "no_host")
    assert (code, out) == (2, "")
    assert err.strip() == f"E520 UNRESOLVED_INPUT missing_spec_dir {tmp_path / 'no_host' / 'spec'}"


def test_backlog_is_empty_after_the_answers_are_applied(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host")
    insert_delta_items_with_the_cli(host, capsys, "open_items")
    code, out, _err = _backlog(capsys, host)
    assert code == 0 and "Totals: 2 items / 1 with answer / 1 needing answer." in out
    seed = host / "docs" / "seed" / "seed_accounts.md"
    seed.write_text(seed.read_text(encoding="utf-8") + "A reset link is sent by email only.\n", encoding="utf-8")
    for artifact in ("05_interface_contracts", "08_fixtures"):
        json_command(capsys, "delete", str(host / "spec" / f"{artifact}.json"), ".ambiguities[0]")
    code, out, err = _backlog(capsys, host)
    assert (code, out, err) == (0, EMPTY_TOTALS + "\n", "")
    code, out, _err = _backlog(capsys, host, "--json")
    payload: dict[str, Any] = json.loads(out)
    assert payload["records"] == [] and payload["summary"]["items"] == 0
    assert check_open_items(str(host / "spec"), gate="merge") == []
