"""The step gate in migration mode (``validation.migration_mode``, WI-M10-10): when it is on, which steps are passed, and where the gate picks the provider."""
from __future__ import annotations

from pathlib import Path

from integration._step_gate_support import step_gate_host
from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.git_base import BaselineResult, BaseResolution
from specdev_tools.validation.migration_mode import (
    BASELINE_MARKER_CODE,
    MIGRATION_NOTE,
    migration_aware_provider,
    migration_resolution,
    not_passed_owners,
)
from specdev_tools.validation.step_gate_run import run_step_gate
from unit.graph._synth import ROOT, git

STAMP = "specdev_version"


def _stamp(spec: Path, version: str) -> None:
    spec.mkdir(parents=True, exist_ok=True)
    (spec / STAMP).write_text(f"toolkit_version: {version}\n", encoding="utf-8")


def _repo(tmp_path: Path, *, committed: str | None, branch: str = "main") -> Path:
    """A git repository with one commit whose ``spec/specdev_version`` holds *committed* (absent for ``None``)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", branch)
    (repo / "spec").mkdir()
    (repo / "spec" / "00_charter.json").write_text("{}\n", encoding="utf-8")
    if committed is not None:
        _stamp(repo / "spec", committed)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def _error(code: str, owner: str | None, message: str = "m") -> SpecError:
    return make_error(code, message, owner=owner)


def test_migration_mode_is_on_when_the_stamp_differs_from_the_stamp_at_the_merge_base(tmp_path: Path) -> None:
    repo = _repo(tmp_path, committed="1.1.1")
    _stamp(repo / "spec", "1.2.0")
    resolution = migration_resolution(repo / "spec", str(repo))
    assert resolution is not None and resolution.commit == git(repo, "rev-parse", "HEAD")


def test_migration_mode_is_on_when_the_stamp_is_absent_at_the_merge_base(tmp_path: Path) -> None:
    repo = _repo(tmp_path, committed=None)
    _stamp(repo / "spec", "1.2.0")
    assert migration_resolution(repo / "spec", str(repo)) is not None


def test_migration_mode_is_off_when_the_stamps_agree(tmp_path: Path) -> None:
    repo = _repo(tmp_path, committed="1.1.1")
    assert migration_resolution(repo / "spec", str(repo)) is None


def test_migration_mode_is_off_when_the_working_tree_has_no_stamp(tmp_path: Path) -> None:
    repo = _repo(tmp_path, committed=None)
    assert migration_resolution(repo / "spec", str(repo)) is None


def test_migration_mode_is_off_when_no_base_resolves(tmp_path: Path) -> None:
    repo = _repo(tmp_path, committed="1.1.1", branch="work")
    _stamp(repo / "spec", "1.2.0")
    assert migration_resolution(repo / "spec", str(repo)) is None


def test_migration_mode_is_off_outside_a_git_repository(tmp_path: Path) -> None:
    _stamp(tmp_path / "spec", "1.2.0")
    assert migration_resolution(tmp_path / "spec", str(tmp_path)) is None


def test_the_provider_returns_the_errors_of_steps_that_still_carry_an_e882(tmp_path: Path) -> None:
    repo = _repo(tmp_path, committed="1.1.1")
    _stamp(repo / "spec", "1.2.0")
    marker = _error(BASELINE_MARKER_CODE, "step:03")
    carried = _error("E700", "step:03", "carried")
    passed = _error("E700", "step:02", "passed")
    result = migration_aware_provider([marker, carried, passed], _unused)(repo / "spec", str(repo))
    assert (result.mode, result.errors) == ("ok", (marker, carried))
    assert result.resolution is not None and result.resolution.note == MIGRATION_NOTE


def test_a_passed_step_contributes_no_baseline_error() -> None:
    errors = [_error(BASELINE_MARKER_CODE, "step:04"), _error("E700", "step:02"), _error("E700", "merge-check")]
    assert not_passed_owners(errors) == {"step:04"}


def test_a_step_with_no_converted_links_counts_as_passed() -> None:
    assert not_passed_owners([_error("E700", "step:03"), _error("E701", "step:03")]) == frozenset()


def test_the_provider_is_the_default_outside_migration_mode(tmp_path: Path) -> None:
    repo = _repo(tmp_path, committed="1.1.1")
    answer = BaselineResult("unavailable", resolution=BaseResolution(None, None, "unavailable", "default"))
    result = migration_aware_provider([_error(BASELINE_MARKER_CODE, "step:03")], lambda spec_dir, git_root: answer)(repo / "spec", str(repo))
    assert result is answer


def _unused(spec_dir: Path, git_root: str) -> BaselineResult:
    raise AssertionError("the default provider is not used in migration mode")


def _gate(host: Path, **kwargs: object) -> tuple[BaselineResult, tuple[str, ...]]:
    spec = str(host / "spec")
    run = run_step_gate(str(ROOT), spec, steps=["05"], git_root=str(host), spec_root=spec, **kwargs)  # type: ignore[arg-type]
    return run.baseline, run.notes


def _stamped_host(tmp_path: Path, committed: str, working: str) -> Path:
    host = step_gate_host(tmp_path / "host")
    _stamp(host / "spec", committed)
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", "stamp")
    _stamp(host / "spec", working)
    return host


def test_run_step_gate_uses_the_migration_provider_only_in_migration_mode(tmp_path: Path) -> None:
    migrating = _stamped_host(tmp_path / "a", "1.1.1", "1.2.0")
    steady = _stamped_host(tmp_path / "b", "1.1.1", "1.1.1")
    assert f"note: {MIGRATION_NOTE}" in _gate(migrating)[1]
    assert f"note: {MIGRATION_NOTE}" not in _gate(steady)[1]


def test_an_explicit_provider_still_wins(tmp_path: Path) -> None:
    host = _stamped_host(tmp_path, "1.1.1", "1.2.0")
    reason = "explicit"
    baseline, notes = _gate(host, provider=lambda spec_dir, git_root: BaselineResult("unavailable", resolution=BaseResolution(None, None, "unavailable", reason)))
    assert (baseline.mode, notes) == ("unavailable", (f"note: {reason}",))
