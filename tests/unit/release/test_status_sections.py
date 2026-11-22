"""The release sections of ``specdev status``: the production verification of the previous release (five states) and the merge-check and release-gate findings."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools import cli
from specdev_tools.core.errors import make_error
from specdev_tools.graph.ownership import RELEASE_OWNER
from specdev_tools.release import status_sections
from specdev_tools.release.gate import ReleaseGateResult
from specdev_tools.lifecycle import status as status_module
from specdev_tools.release import records
from specdev_tools.release.status_sections import NONE, NOT_VERIFIED, PREDATES, ROLLBACK, VERIFIED, ProductionVerification, production_verification
from unit.lifecycle._milestone_support import cli_run
from unit.release._support import PATTERN, advance, commit, latency_host, release_host, stamp, tag
from unit.graph._synth import ROOT

REPO = str(ROOT)


def _state(host: Path) -> ProductionVerification:
    return production_verification(str(host), str(host / "spec"), REPO)


def _released(tmp_path: Path, version: str | None) -> Path:
    """A release-ready host stamped *version* (not stamped when ``None``), tagged v1.0.0 and one commit further on."""
    host = release_host(tmp_path)
    if version is None:
        (host / "spec" / "specdev_version").unlink()
    else:
        stamp(host, version)
    commit(host, "release one")
    tag(host, "v1.0.0")
    advance(host)
    return host


def _unverified(tmp_path: Path, *, run_it: bool) -> Path:
    host = latency_host(tmp_path, run_it=run_it)
    tag(host, "v1.0.0")
    advance(host)
    return host


def test_status_shows_production_verification_states(tmp_path: Path) -> None:
    assert _state(release_host(tmp_path / "a")) == ProductionVerification(None, NONE)
    assert _state(_released(tmp_path / "b", None)) == ProductionVerification("v1.0.0", PREDATES)
    unverified = _unverified(tmp_path / "c", run_it=False)
    found = _state(unverified)
    assert (found.tag, found.state) == ("v1.0.0", NOT_VERIFIED) and found.missing and found.missing[0].startswith("E920") and "ver-latency" in found.missing[0]
    records.write_rollback(str(unverified), str(unverified / "spec"), "v1.0.0", "rolled back before production", PATTERN)
    assert _state(unverified) == ProductionVerification("v1.0.0", ROLLBACK)
    assert _state(_unverified(tmp_path / "d", run_it=True)) == ProductionVerification("v1.0.0", VERIFIED)


def test_the_five_states_are_the_five_the_plan_names() -> None:
    assert (VERIFIED, ROLLBACK, NOT_VERIFIED, PREDATES, NONE) == ("verified in production", "rollback recorded", "not verified", "none (previous tag predates 1.2.0)", "none")


def test_status_prints_the_state_of_the_previous_release(tmp_path: Path) -> None:
    host = _unverified(tmp_path, run_it=False)
    code, out, _ = cli_run(host, "status")
    assert code == 0
    section = out.split("Production verification\n")[1]
    assert section.startswith("  previous release: v1.0.0\n  state: not verified (released, awaiting production proof)\n  E920 ")
    code, out, _ = cli_run(host, "status", "--json")
    data = json.loads(out)["sections"]["production_verification"]["data"]
    assert data["tag"] == "v1.0.0" and data["state"] == NOT_VERIFIED and data["missing"][0].startswith("E920")


def test_status_without_a_release_pattern_says_so_instead_of_failing(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    (host / "spec" / "common" / "host_declarations.json").unlink()
    code, out, _ = cli_run(host, "status")
    assert code == 0 and "not read: E911" in out.split("Production verification\n")[1]


def test_status_section6_merge_release_part_registered(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    cli.build_parser()
    assert list(status_module.SECTIONS)[-2:] == [status_module.MERGE_RELEASE_SECTION, status_module.PRODUCTION_SECTION], "registering replaced the defaults in their places"
    code, out, _ = cli_run(host, "status")
    section = out.split("Merge-check and release-gate errors\n")[1].split("\n\n")[0]
    assert code == 0 and status_module.RELEASE_NOT_INSTALLED not in out
    assert section.startswith("  release gate: 0 error(s), ") and "28 listed (not blocking)" in section.splitlines()[0]
    code, out, _ = cli_run(host, "status", "--json")
    data = json.loads(out)["sections"]["merge_release_gates"]["data"]
    assert data["errors"] == {} and len(data["listed"]) == 28


def test_status_section6_lists_the_errors_by_owner(tmp_path: Path) -> None:
    host = release_host(tmp_path, "inv-reset-token-single-use")
    code, out, _ = cli_run(host, "status")
    section = out.split("Merge-check and release-gate errors\n")[1].split("\n\n")[0]
    assert code == 0 and "E914 invariant inv-reset-token-single-use" in section
    assert any(line.startswith("  step:06 (") for line in section.splitlines())


def test_a_release_gate_finding_without_an_owner_is_listed_under_the_release_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = release_host(tmp_path)
    ownerless = make_error("E914", "a finding no step claims")
    assert ownerless.owner is None
    monkeypatch.setattr(status_sections, "run_release_gate", lambda *args: ReleaseGateResult((ownerless,), (), (), (), (), None))
    code, out, _ = cli_run(host, "status")
    section = out.split("Merge-check and release-gate errors\n")[1].split("\n\n")[0]
    assert code == 0 and f"  {RELEASE_OWNER} (1):" in section and "a finding no step claims" in section
    code, out, _ = cli_run(host, "status", "--json")
    assert list(json.loads(out)["sections"]["merge_release_gates"]["data"]["errors"]) == [RELEASE_OWNER]


def test_status_for_a_milestone_has_no_release_sections(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    code, out, _ = cli_run(host, "status", "--milestone", "ms-account-recovery")
    assert code == 0 and "release gate" not in out and "Production verification" not in out


@pytest.mark.parametrize("name", [status_module.MERGE_RELEASE_SECTION, status_module.PRODUCTION_SECTION])
def test_install_is_repeatable_and_keeps_the_places(name: str) -> None:
    cli.build_parser()
    before = list(status_module.SECTIONS)
    cli.build_parser()
    assert list(status_module.SECTIONS) == before and name in before
