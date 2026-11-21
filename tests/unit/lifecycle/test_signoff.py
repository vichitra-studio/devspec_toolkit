"""``specdev milestone sign-off``: the record it writes, its numbering, its refusals and the view it prints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.errors import FindingError
from specdev_tools.core.loaders import iter_spec_artifacts
from specdev_tools.core.schema_validate import validate_data_against_schema
from specdev_tools.graph.build import build_graph
from specdev_tools.lifecycle.close_gate import latest_signoff, signoff_records
from specdev_tools.lifecycle.signoff import sign_off
from specdev_tools.trace.records import record_files
from unit.graph._synth import ROOT
from unit.lifecycle._milestone_support import cli_run, providers_of, ready_host, set_row
from unit.lifecycle._record_support import AUTHOR, author, plan_host, roots
from unit.lifecycle._support import MILESTONE, closed_record

pytestmark = pytest.mark.usefixtures("author")
SIGNOFF_DIR = Path("spec") / "extras" / "signoff"


def _sign(host: Path) -> Any:
    spec, repo, git = roots(host)
    return sign_off(spec, repo, git, MILESTONE, providers_of(host))


def test_record_written_with_tree_and_author(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    result = _sign(host)
    written = json.loads((host / SIGNOFF_DIR / "so-ms-account-recovery-0001.json").read_text(encoding="utf-8"))
    (record,) = written["records"]
    assert record == result.record and result.file == "extras/signoff/so-ms-account-recovery-0001.json"
    assert (record["signoff_id"], record["about"], record["git_author"]) == ("so-ms-account-recovery-0001", [MILESTONE], AUTHOR)
    assert record["tree"] == result.view.tree != ""
    assert record["listed"] == {"manual_fixtures": 0, "attested": 0, "deferred_tasks": [], "wont_do_tasks": [], "open_items": 0, "staging_prod_proof_owed": []}
    assert latest_signoff(host / "spec", MILESTONE).signoff_id == "so-ms-account-recovery-0001"


def test_second_signoff_gets_id_0002(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    _sign(host)
    second = _sign(host)
    assert second.record["signoff_id"] == "so-ms-account-recovery-0002"
    assert [r.signoff_id for r in signoff_records(host / "spec", MILESTONE)] == ["so-ms-account-recovery-0001", "so-ms-account-recovery-0002"]


def test_signoff_on_the_wrong_status_is_e801(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    for status, extra in (("pending", {}), ("deferred", {"deferral_reason": "x"}), ("done", {"close": closed_record()})):
        set_row(host, status, **extra)
        with pytest.raises(FindingError) as caught:
            _sign(host)
        assert caught.value.error.code == "E801"
    assert not (host / SIGNOFF_DIR).exists()


def test_signoff_record_validates_against_its_schema(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    _sign(host)
    document = json.loads((host / SIGNOFF_DIR / "so-ms-account-recovery-0001.json").read_text(encoding="utf-8"))
    assert validate_data_against_schema(str(ROOT), document) == []


def test_signoff_folder_is_not_loaded_as_a_step(tmp_path: Path) -> None:
    host = ready_host(tmp_path)
    _sign(host)
    walked = {Path(path).name for path in iter_spec_artifacts(str(host / "spec"))}
    assert "so-ms-account-recovery-0001.json" not in walked
    assert "extras/signoff/so-ms-account-recovery-0001.json" in record_files(str(host / "spec"))
    assert not build_graph(str(host / "spec"), str(ROOT)).load_errors


def test_signoff_prints_the_view_and_does_not_check_the_review(tmp_path: Path) -> None:
    host = plan_host(tmp_path)
    code, out, _ = cli_run(host, "milestone", "sign-off", MILESTONE)
    assert code == 0 and "close gate (dry run)" in out and "recorded so-ms-account-recovery-0001" in out
    code, out, _ = cli_run(host, "milestone", "sign-off", MILESTONE, "--json")
    assert code == 0 and json.loads(out)["record"]["signoff_id"] == "so-ms-account-recovery-0002"
    code, _, err = cli_run(host, "milestone", "sign-off", "account_recovery")
    assert code == 1 and "milestone-state --batch-id account_recovery" in err
