"""The step gate run (``validation.step_gate_run``) and the registry of checks (``validation.check_registry``) without the CLI (WI-M6a-04).

The flag rules, the note order and the empty run are functions here, so they are called directly; the last tests start the
command to pin what a refusal prints and the exit code it gives.
"""
from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from integration._step_gate_support import run_split, step_gate_host
from specdev_tools.core import ambiguity_items
from specdev_tools.core.ambiguity_items import AmbiguityItem
from specdev_tools.core.errors import FindingError
from specdev_tools.core.git_base import BaselineResult, BaseResolution
from specdev_tools.graph.ownership import OwnershipTableError
from specdev_tools.validation import check_registry
from specdev_tools.validation.check_registry import CheckContext, register_check, unregister_check
from specdev_tools.validation.step_gate_run import (
    EMPTY_BASE_REF_USAGE,
    FORWARD_REPLAY_USAGE,
    GATE_ONLY_USAGE,
    NO_STEP_NOTE,
    gate_run,
    gate_usage_error,
    run_step_gate,
)
from specdev_tools.validation.touched_steps import SEED_EDIT_NOTE
from unit.graph._synth import ROOT

SEED_PATH = "docs/seed/seed_accounts.md"
REASON = "the baseline is not available for this test"


def _unavailable(spec_dir: Path, git_root: str) -> BaselineResult:
    return BaselineResult("unavailable", resolution=BaseResolution(None, None, "unavailable", REASON))


def _gate(host: Path, **kwargs: Any) -> Any:
    spec = str(host / "spec")
    return gate_run(str(ROOT), spec, git_root=str(host), spec_root=spec, **{"steps": None, "paths": None, **kwargs})


# --- the flag rules ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("flags", "message"),
    [
        ({"steps": ["05"], "include_forward_replay": True}, FORWARD_REPLAY_USAGE),
        ({"paths": [], "include_forward_replay": True}, FORWARD_REPLAY_USAGE),
        ({"base_ref": "main"}, GATE_ONLY_USAGE),
        ({"detail": "all"}, GATE_ONLY_USAGE),
        ({"steps": ["05"], "base_ref": ""}, EMPTY_BASE_REF_USAGE),
        ({"paths": ["a.json"], "base_ref": ""}, EMPTY_BASE_REF_USAGE),
        ({"steps": ["05"], "base_ref": "main", "detail": "summary"}, None),
        ({"include_forward_replay": True}, None),
        ({}, None),
    ],
)
def test_gate_usage_error_names_the_refused_combination(flags: dict[str, Any], message: str | None) -> None:
    given = {"steps": None, "paths": None, "include_forward_replay": False, "base_ref": None, "detail": None, **flags}
    assert gate_usage_error(**given) == message


# --- the run: notes and the empty run -----------------------------------------------------------------------------

def test_paths_that_map_to_no_step_give_the_empty_run_with_one_note_and_no_baseline_note(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    run = _gate(host, paths=["README.md"], provider=_unavailable)
    assert (run.results, run.baseline.mode, run.baseline.resolution, run.notes) == ((), "unavailable", None, (NO_STEP_NOTE,))


def test_an_empty_paths_list_gives_the_empty_run_with_no_note(tmp_path: Path) -> None:
    run = _gate(step_gate_host(tmp_path / "host"), paths=[])
    assert (run.results, run.notes) == ((), ())


def test_the_notes_come_in_order_paths_then_missing_artifacts_then_the_run(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    run = _gate(host, paths=["../outside.md", SEED_PATH], provider=_unavailable)
    assert len(run.notes) == 3 and "outside the host root" in run.notes[0]
    assert run.notes[1:] == (SEED_EDIT_NOTE, f"note: {REASON}")


def test_a_step_with_no_artifact_is_noted_before_the_notes_of_the_run_and_the_gate_still_runs(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    run = _gate(host, steps=["13a"], provider=_unavailable)
    assert run.notes == (f"step 13a has no artifact in {host / 'spec'}", f"note: {REASON}")
    assert [result.step for result in run.results] == ["13a"]


def test_a_step_given_twice_is_gated_once(tmp_path: Path) -> None:
    run = _gate(step_gate_host(tmp_path / "host"), steps=["05", "04", "05"], provider=_unavailable)
    assert [result.step for result in run.results] == ["05", "04"]


def test_an_unknown_step_is_refused_before_any_note_or_check(tmp_path: Path) -> None:
    with pytest.raises(FindingError) as refused:
        _gate(step_gate_host(tmp_path / "host"), steps=["99"], provider=_unavailable)
    assert refused.value.error.code == "E706"


def test_a_spec_folder_that_does_not_exist_is_refused_with_e520(tmp_path: Path) -> None:
    with pytest.raises(FindingError) as refused:
        gate_run(str(ROOT), str(tmp_path / "nospec"), steps=["05"], paths=None)
    assert (refused.value.error.code, refused.value.error.message) == (
        "E520", f"UNRESOLVED_INPUT missing_spec_dir {tmp_path / 'nospec'}"
    )


# --- the baseline provider is an argument -------------------------------------------------------------------------

def test_the_gate_measures_the_baseline_with_the_provider_it_is_given(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    spec = str(host / "spec")
    seen: list[tuple[Path, str]] = []

    def provider(spec_dir: Path, git_root: str) -> BaselineResult:
        seen.append((spec_dir, git_root))
        return _unavailable(spec_dir, git_root)

    run = run_step_gate(str(ROOT), spec, ["05"], git_root=str(host), spec_root=spec, provider=provider)
    assert seen == [(Path(spec), str(host))]
    assert (run.baseline.mode, run.notes) == ("unavailable", (f"note: {REASON}",))


def test_a_provider_given_to_one_run_does_not_outlive_it(tmp_path: Path) -> None:
    host = step_gate_host(tmp_path / "host")
    spec = str(host / "spec")
    run_step_gate(str(ROOT), spec, ["05"], git_root=str(host), spec_root=spec, provider=_unavailable)
    run = run_step_gate(str(ROOT), spec, ["05"], git_root=str(host), spec_root=spec)
    assert run.baseline.mode == "ok"


# --- the items are read once per run -------------------------------------------------------------------------------

def test_the_open_items_are_read_once_for_the_check_and_the_waiting_map(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    host = step_gate_host(tmp_path / "host", ["open_items"])
    spec = str(host / "spec")
    reads: list[str] = []
    real = ambiguity_items.iter_ambiguity_items

    def counting(spec_dir: str) -> Iterator[AmbiguityItem]:
        reads.append(spec_dir)
        return real(spec_dir)

    monkeypatch.setattr(ambiguity_items, "iter_ambiguity_items", counting)
    run_step_gate(str(ROOT), spec, ["05"], git_root=str(host), spec_root=spec, provider=_unavailable)
    assert reads == [spec]


# --- the registry --------------------------------------------------------------------------------------------------

def test_importing_the_registry_does_not_import_spec_check() -> None:
    code = "import specdev_tools.validation.check_registry as m, sys; print('specdev_tools.validation.spec_check' in sys.modules)"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT / "tools")})
    assert done.stdout.strip() == "False", done.stderr


def test_unregister_check_removes_a_registered_check(registered_checks: None) -> None:
    register_check("probe-to-remove", lambda ctx: {"status": "PASS"})
    unregister_check("probe-to-remove")
    assert "probe-to-remove" not in [spec.name for spec in check_registry.CHECK_REGISTRY]
    with pytest.raises(ValueError, match="not registered"):
        unregister_check("probe-to-remove")


def test_the_registered_checks_fixture_removes_what_a_test_registered(registered_checks: None) -> None:
    register_check("left-by-a-test", lambda ctx: {"status": "PASS"})


def test_the_check_left_by_the_previous_test_is_gone() -> None:
    assert "left-by-a-test" not in [spec.name for spec in check_registry.CHECK_REGISTRY]


def test_a_toolkit_without_an_ownership_table_is_refused_with_one_e520_naming_the_file(tmp_path: Path) -> None:
    with pytest.raises(FindingError) as refused:
        CheckContext(repo_root=str(tmp_path), spec_dir=str(tmp_path)).owner_context
    error = refused.value.error
    assert error.code == "E520" and str(tmp_path / "tools" / "error_ownership.json") in error.message


# --- what the command prints ---------------------------------------------------------------------------------------

def _stderr_lines(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.strip()]


def test_a_missing_spec_folder_is_one_e520_line_and_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nospec"
    for scope in (["--step", "05"], ["--paths", "spec/04_fr_list.json"]):
        code, out, err = run_split(capsys, "spec-check", str(missing), "--repo-root", str(ROOT), *scope)
        assert (code, out, _stderr_lines(err)) == (1, "", [f"E520 UNRESOLVED_INPUT missing_spec_dir {missing}"])


def test_an_empty_base_ref_is_a_usage_error_with_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host")
    code, out, err = run_split(capsys, "spec-check", str(host / "spec"), "--repo-root", str(ROOT), "--step", "05", "--base-ref", "")
    assert (code, out) == (2, "") and EMPTY_BASE_REF_USAGE in err and "Traceback" not in err


def test_a_step_given_twice_prints_one_block(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = step_gate_host(tmp_path / "host")
    _code, out, _err = run_split(
        capsys, "spec-check", str(host / "spec"), "--repo-root", str(ROOT), "--git-root", str(host), "--step", "05", "--step", "05"
    )
    assert out.count("step gate: step 05") == 1


@pytest.mark.parametrize("scope", [[], ["--step", "05"]], ids=["plain", "step-gate"])
@pytest.mark.parametrize("json_output", [False, True], ids=["text", "json"])
def test_an_unreadable_ownership_table_is_one_e520_line_and_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, scope: list[str], json_output: bool
) -> None:
    table = tmp_path / "tools" / "error_ownership.json"

    def unreadable(_repo_root: str) -> None:
        raise OwnershipTableError(f"{table}: unreadable or not a JSON object")

    monkeypatch.setattr(check_registry, "load_ownership_table", unreadable)
    host = step_gate_host(tmp_path / "host")
    flags = ["--repo-root", str(ROOT), "--git-root", str(host), *scope, *(["--json"] if json_output else [])]
    code, out, err = run_split(capsys, "spec-check", str(host / "spec"), *flags)
    assert code == 1 and "Traceback" not in err
    refusal = out if json_output else err
    assert str(table) in refusal and "E520" in refusal
    if not json_output:
        assert len(_stderr_lines(err)) == 1
