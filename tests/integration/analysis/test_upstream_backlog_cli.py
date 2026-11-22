"""End-to-end CLI subprocess test for specdev upstream-backlog.

Exercises the full `python -m specdev_tools.cli upstream-backlog` path —
argparse parsing, dispatch, stdout/stderr routing, and exit code — which
mirrors the invocation performed by `./tools/run_specdev.sh`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


TOOLKIT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = TOOLKIT_ROOT / "tests" / "fixtures" / "analysis" / "upstream_backlog"
GRAPH_EXAMPLE_SPEC = TOOLKIT_ROOT / "tests" / "fixtures" / "graph_example" / "spec"
IMPACT_PIPELINE = (
    '[.records[]?.impact[]?'
    ' | if type == "string" and test(":") then split(":") | {file: .[0], id: .[1]}'
    ' elif type == "object" then {file, id} else empty end]'
)


def _run_cli(spec_dir: Path, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(TOOLKIT_ROOT / "tools")}
    return subprocess.run(
        [sys.executable, "-m", "specdev_tools.cli", "upstream-backlog",
         str(spec_dir), *extra],
        cwd=str(TOOLKIT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _stage(spec_dir: Path, *names: str) -> Path:
    """Copy fixtures into ``spec_dir/impl_context`` as milestone plan files (``ms_<name>_plan.json``)."""
    impl = spec_dir / "impl_context"
    impl.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(FIXTURE_DIR / name, impl / f"ms_{name.removesuffix('.json')}_plan.json")
    return spec_dir


@pytest.fixture
def clean_spec(tmp_path: Path) -> Path:
    return _stage(tmp_path / "spec", "plan_with_six_ambiguities.json", "plan_with_no_execution.json")


@pytest.fixture
def unified_spec(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "spec"
    shutil.copytree(GRAPH_EXAMPLE_SPEC, spec_dir)
    return _stage(spec_dir, "unified_items_plan.json")


@pytest.fixture
def legacy_spec(tmp_path: Path) -> Path:
    return _stage(tmp_path / "spec", "legacy_impact_two_steps_plan.json")


@pytest.fixture
def dual_origin_spec(tmp_path: Path) -> Path:
    return _stage(tmp_path / "spec", "plan_with_dual_origin_ambiguities.json")


def _records(r: subprocess.CompletedProcess) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for rec in json.loads(r.stdout)["records"]:
        out.setdefault(rec["item_id"], []).append(rec)
    return out


def test_clean_run_exits_zero_and_groups_legacy_items_by_step(clean_spec: Path):
    r = _run_cli(clean_spec)
    assert r.returncode == 0, r.stderr
    assert "09 - 1 item(s)" in r.stdout
    assert "unplaced - " in r.stdout


def test_clean_run_emits_w613_for_open_unplaced_items(clean_spec: Path):
    r = _run_cli(clean_spec)
    assert r.returncode == 0
    w613 = [ln for ln in r.stderr.splitlines() if ln.startswith("W613 UPSTREAM_BACKLOG_UNCLASSIFIED")]
    assert len(w613) == 4


def test_status_all_includes_resolved_unplaced_item(clean_spec: Path):
    r = _run_cli(clean_spec, "--status", "all")
    assert r.returncode == 0
    w613 = [ln for ln in r.stderr.splitlines() if ln.startswith("W613 UPSTREAM_BACKLOG_UNCLASSIFIED")]
    assert len(w613) == 5


def test_json_output_is_valid_with_schema_version_2(clean_spec: Path):
    r = _run_cli(clean_spec, "--json")
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["schema_version"] == "2"
    assert {"summary", "records", "warnings"} <= set(payload)


def test_malformed_plan_triggers_exit_two(clean_spec: Path):
    _stage(clean_spec.parent / "spec", "plan_malformed.json")
    r = _run_cli(clean_spec)
    assert r.returncode == 2
    assert "E520" in r.stderr and "ms_plan_malformed_plan.json" in r.stderr


def test_unreadable_utf8_plan_triggers_exit_two(tmp_path: Path):
    impl = tmp_path / "spec" / "impl_context"
    impl.mkdir(parents=True)
    (impl / "ms_bad_plan.json").write_bytes(b'{"id": "ms-bad", "execution": \xff\xfe}')
    r = _run_cli(tmp_path / "spec")
    assert r.returncode == 2
    assert "E520" in r.stderr and "ms_bad_plan.json" in r.stderr


def test_severity_high_filters_out_lower_legacy_items(clean_spec: Path):
    r = _run_cli(clean_spec, "--severity", "high")
    assert r.returncode == 0
    assert "amb-new-responsive-375" in r.stdout
    assert "amb-new-wcag-pairing-ratchet" not in r.stdout
    assert "09 - " not in r.stdout


def test_record_level_e520_triggers_exit_two_and_siblings_still_render(tmp_path: Path):
    r = _run_cli(_stage(tmp_path / "spec", "plan_with_record_level_e520.json"))
    assert r.returncode == 2
    assert "E520" in r.stderr and "missing_id" in r.stderr
    assert "amb-good" in r.stdout


def test_null_execution_plan_is_skipped_silently(tmp_path: Path):
    r = _run_cli(_stage(tmp_path / "spec", "plan_with_null_execution.json"))
    assert r.returncode == 0, r.stderr
    assert "E520" not in r.stderr
    assert "0 items" in r.stdout


def test_plan_ambiguities_16a_are_scanned(dual_origin_spec: Path):
    """DEVSPEC-123 regression: plan.ambiguities[] (16a) is as visible as execution.emergent_ambiguities[]."""
    r = _run_cli(dual_origin_spec, "--status", "all", "--json")
    assert r.returncode == 0, r.stderr
    found = _records(r)
    assert set(found) == {"amb-16a-open-blocking", "amb-16a-resolved-non-blocking", "amb-16b-open-high", "amb-16c-resolved-critical"}
    assert found["amb-16a-open-blocking"][0]["step"] == "16a"
    assert found["amb-16b-open-high"][0]["step"] == "16b"


def test_plan_blocking_severity_ranks_as_critical(dual_origin_spec: Path):
    r = _run_cli(dual_origin_spec, "--status", "all", "--severity", "critical", "--json")
    ids = set(_records(r))
    assert "amb-16a-open-blocking" in ids
    assert "amb-16a-resolved-non-blocking" not in ids


def test_default_status_open_hides_resolved_and_emits_w617(dual_origin_spec: Path):
    r = _run_cli(dual_origin_spec)
    assert r.returncode == 0, r.stderr
    w617 = [ln for ln in r.stderr.splitlines() if ln.startswith("W617 UPSTREAM_BACKLOG_STATUS_FILTERED")]
    assert len(w617) == 1 and "2 record(s)" in w617[0]
    assert "amb-16a-resolved-non-blocking" not in r.stdout


def test_status_all_suppresses_w617(dual_origin_spec: Path):
    r = _run_cli(dual_origin_spec, "--status", "all")
    assert "W617" not in r.stderr


def test_unified_items_alone_never_trigger_w617(unified_spec: Path):
    assert "W617" not in _run_cli(unified_spec).stderr


def test_json_summary_carries_hidden_by_status_count(dual_origin_spec: Path):
    assert json.loads(_run_cli(dual_origin_spec, "--json").stdout)["summary"]["hidden_by_status_count"] == 2
    assert json.loads(_run_cli(dual_origin_spec, "--status", "all", "--json").stdout)["summary"]["hidden_by_status_count"] == 0


@pytest.mark.parametrize("fixture", ["anchor_misfiled_in_impl_context.json", "anchor_misfiled_whitespace_role.json"])
def test_anchor_misfiled_in_impl_context_is_not_read_as_a_plan(tmp_path: Path, fixture: str):
    """A Trinity Anchor misfiled under impl_context/ (W609) is not a milestone plan file, so it is never read."""
    impl = tmp_path / "spec" / "impl_context"
    impl.mkdir(parents=True)
    shutil.copy(FIXTURE_DIR / fixture, impl / fixture)
    r = _run_cli(tmp_path / "spec", "--status", "all", "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["records"] == []


def test_unified_items_are_grouped_by_the_step_of_their_about_nodes(unified_spec: Path):
    r = _run_cli(unified_spec, "--json")
    assert r.returncode == 0, r.stderr
    found = _records(r)
    assert [x["group"] for x in found["amb-about-seed"]] == ["seed"]
    assert [x["group"] for x in found["amb-about-criterion"]] == ["04"]
    assert [x["group"] for x in found["amb-two-steps"]] == ["04", "05"]
    assert found["amb-two-steps"][1]["also_in"] == ["04"]
    assert [x["group"] for x in found["amb-silent-criterion"]] == ["04"]
    assert [x["group"] for x in found["amb-unresolved"]] == ["unplaced"]
    summary = json.loads(r.stdout)["summary"]
    assert (summary["items"], summary["with_answer"], summary["needing_answer"], summary["unplaced_count"]) == (5, 1, 4, 1)


def test_unified_plain_output_orders_groups_seed_first_unplaced_last(unified_spec: Path):
    r = _run_cli(unified_spec)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert out.index("seed - ") < out.index("04 - ") < out.index("05 - ") < out.index("unplaced - ")
    assert "answer known" in out and "needs operator answer" in out
    assert "(also in 04)" in out
    assert out.splitlines()[-1] == "Totals: 5 items / 1 with answer / 4 needing answer."
    assert [ln for ln in r.stderr.splitlines() if ln.startswith("W613")] == [
        "W613 UPSTREAM_BACKLOG_UNCLASSIFIED impl_context/ms_unified_items_plan_plan.json:amb-unresolved"
    ]


def test_legacy_item_widened_across_steps_lands_in_the_earliest_flagged_legacy(legacy_spec: Path):
    r = _run_cli(legacy_spec, "--json")
    assert r.returncode == 0, r.stderr
    rec = _records(r)["amb-legacy-widened"][0]
    assert (rec["group"], rec["shape"]) == ("04", "legacy")
    assert _records(r)["amb-legacy-no-step"][0]["group"] == "unplaced"
    assert "legacy" in _run_cli(legacy_spec).stdout


@pytest.mark.parametrize("fixture", ["legacy_spec", "unified_spec"])
def test_context_skill_jq_pipeline_yields_pointers(request: pytest.FixtureRequest, fixture: str):
    """specdev-context SKILL.md pipes ``.records[]?.impact[]?`` of the JSON into resolve-pointers."""
    if shutil.which("jq") is None:
        pytest.skip("jq is not installed")
    spec_dir: Path = request.getfixturevalue(fixture)
    r = _run_cli(spec_dir, "--json")
    jq = subprocess.run(["jq", IMPACT_PIPELINE], input=r.stdout, capture_output=True, text=True, check=True)
    pointers = json.loads(jq.stdout)
    assert pointers and all(p["file"].startswith("spec/") and p["id"] for p in pointers)
