"""Path-to-steps mapping of the ``spec-check --paths`` hook (WI-M6a-09, S-024): the layouts, the seed rows and the unmapped paths."""
from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.core.step_order import load_step_order
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.gitview import GitViewError
from specdev_tools.graph.model import Graph
from specdev_tools.validation.touched_steps import (
    PLAN_FILE_STEPS,
    SEED_EDIT_NOTE,
    TouchedSteps,
    outside_root_note,
    steps_for_paths,
)

from ..trace._lock_support import EXAMPLE_HOST

ROOT = Path(__file__).parents[3]
STEP_ORDER = tuple(load_step_order(str(ROOT))["steps"])
SEED_PATH = "docs/seed/seed_accounts.md"
OTHER_SEED = "docs/seed/seed_other.md"


def _no_graph() -> Graph:
    raise AssertionError("the graph must not be loaded")


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the example host (spec folder directly under the root); the current folder is another folder, so no case depends on it."""
    copy = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, copy)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return copy


@pytest.fixture
def manifest(host: Path) -> dict[str, Any]:
    """The example's seed manifest: ``seed-accounts`` routed to steps 00 and 02, linked from 00 and 02."""
    return json.loads((host / "spec" / "common" / "seed_manifest.json").read_text(encoding="utf-8"))


def _example_graph(host: Path) -> Callable[[], Graph]:
    return lambda: build_graph(str(host / "spec"), str(ROOT))


def _touched(
    host: Path,
    paths: list[str],
    manifest: dict[str, Any],
    graph: Callable[[], Graph] = _no_graph,
    *,
    spec: str = "spec",
    git_root: str | None = None,
) -> TouchedSteps:
    return steps_for_paths(paths, str(host / spec), manifest, graph, step_order=STEP_ORDER, git_root=git_root)


@pytest.mark.parametrize(
    ("path", "step"),
    [("spec/04_fr_list.json", "04"), ("spec/02a_delivery_baseline.json", "02a"), ("spec/00_charter.json", "00")],
)
def test_step_file_maps_to_its_step(host: Path, manifest: dict[str, Any], path: str, step: str) -> None:
    assert _touched(host, [path], manifest).steps == (step,)


def test_anchor_maps_to_step_16(host: Path, manifest: dict[str, Any]) -> None:
    assert _touched(host, ["spec/16_impl_context.json"], manifest).steps == ("16",)


def test_plan_file_maps_to_16a_16b_16c(host: Path, manifest: dict[str, Any]) -> None:
    assert _touched(host, ["spec/impl_context/ms_account_recovery_plan.json"], manifest).steps == ("16a", "16b", "16c")


def test_seed_maps_to_the_union_of_linked_and_routed_steps(host: Path, manifest: dict[str, Any]) -> None:
    manifest["step_requirements"]["09"] = ["seed-accounts"]
    touched = _touched(host, [SEED_PATH], manifest, _example_graph(host))
    assert touched.steps == ("00", "02", "09")
    assert touched.seed_edited


def test_seed_routed_to_the_16_umbrella_maps_to_the_trinity_steps(host: Path, manifest: dict[str, Any]) -> None:
    manifest["step_requirements"] = {"16": ["seed-accounts"]}
    manifest["seeds"].append({"seed_id": "seed-other", "path": OTHER_SEED})
    manifest["step_requirements"]["16"].append("seed-other")
    assert _touched(host, [OTHER_SEED], manifest, _example_graph(host)).steps == ("16", "16a", "16b", "16c")


def test_seed_routed_and_linked_nowhere_maps_to_step_00(host: Path, manifest: dict[str, Any]) -> None:
    manifest["seeds"].append({"seed_id": "seed-other", "path": OTHER_SEED})
    assert _touched(host, [OTHER_SEED], manifest, _example_graph(host)).steps == ("00",)


def test_seed_manifest_maps_to_step_00_and_every_routed_step(host: Path, manifest: dict[str, Any]) -> None:
    manifest["step_requirements"]["09"] = ["seed-accounts"]
    manifest["step_requirements"]["99"] = ["seed-accounts"]
    touched = _touched(host, ["spec/common/seed_manifest.json"], manifest)
    assert touched.steps == ("00", "02", "09")
    assert not touched.seed_edited


@pytest.mark.parametrize(
    "path",
    [
        "spec/extras/trace.lock.json",
        "spec/extras/02_not_a_step_file.json",
        "spec/canon/manifest.json",
        "spec/impl_context/notes.md",
        "spec/12_ci_gates.md",
        "spec/99_unknown_step.json",
        "README.md",
    ],
)
def test_extras_and_unrelated_paths_map_to_no_step(host: Path, manifest: dict[str, Any], path: str) -> None:
    assert _touched(host, [path], manifest).steps == ()


def test_no_mapped_path_returns_no_steps_without_loading_the_graph(host: Path, manifest: dict[str, Any]) -> None:
    touched = _touched(host, ["README.md", "spec/extras/trace.lock.json", "spec/04_fr_list.json"], manifest)
    assert touched.steps == ("04",)
    assert _touched(host, ["README.md"], manifest) == TouchedSteps((), (), False)


def test_touched_step_with_no_artifact_is_skipped(host: Path, manifest: dict[str, Any]) -> None:
    (host / "spec" / "09_impl_plan.json").unlink()
    manifest["step_requirements"]["09"] = ["seed-accounts"]
    assert _touched(host, ["spec/common/seed_manifest.json"], manifest).steps == ("00", "02")


def test_graph_is_loaded_once_for_several_seeds(host: Path, manifest: dict[str, Any]) -> None:
    manifest["seeds"].append({"seed_id": "seed-other", "path": OTHER_SEED})
    loads: list[int] = []

    def counting() -> Graph:
        loads.append(1)
        return _example_graph(host)()

    _touched(host, [SEED_PATH, OTHER_SEED], manifest, counting)
    assert len(loads) == 1


def test_absolute_and_git_root_relative_paths_map_the_same_from_another_cwd(host: Path, manifest: dict[str, Any]) -> None:
    relative = _touched(host, ["spec/04_fr_list.json"], manifest, git_root=str(host))
    absolute = _touched(host, [str(host / "spec" / "04_fr_list.json")], manifest, git_root=str(host))
    derived = _touched(host, ["spec/04_fr_list.json"], manifest)
    assert relative == absolute == derived
    assert relative.steps == ("04",)


def test_a_relative_path_is_taken_from_the_host_root_not_the_current_folder(
    host: Path, manifest: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(host / "docs")
    assert _touched(host, ["spec/04_fr_list.json"], manifest).steps == ("04",)
    assert _touched(host, ["../spec/04_fr_list.json"], manifest).outside_root == ("../spec/04_fr_list.json",)


def _nest(host: Path) -> None:
    """Move the spec folder to ``sub/spec``; the seed documents stay at the top."""
    (host / "sub").mkdir()
    shutil.move(str(host / "spec"), str(host / "sub" / "spec"))


def test_nested_layout_with_the_git_root_maps_spec_files_from_the_repository_top(host: Path, manifest: dict[str, Any]) -> None:
    _nest(host)
    touched = _touched(host, ["sub/spec/04_fr_list.json"], manifest, spec="sub/spec", git_root=str(host))
    assert touched.steps == ("04",)
    assert touched.outside_root == ()


def test_nested_layout_without_the_git_root_and_outside_a_repository_takes_paths_from_the_host_root(
    host: Path, manifest: dict[str, Any]
) -> None:
    """With no repository the host root ``sub`` is all there is: ``sub/spec/...`` is ``sub/sub/spec/...`` from it."""
    _nest(host)
    assert _touched(host, ["sub/spec/04_fr_list.json"], manifest, spec="sub/spec").steps == ()
    assert _touched(host, ["spec/04_fr_list.json"], manifest, spec="sub/spec").steps == ("04",)
    assert _touched(host, [str(host / "sub" / "spec" / "04_fr_list.json")], manifest, spec="sub/spec").steps == ("04",)


def test_nested_layout_without_the_git_root_in_a_repository_takes_paths_from_the_repository_top(
    host: Path, manifest: dict[str, Any]
) -> None:
    """What a pre-commit hook passes: the step file is placed, the seed at the top is reported, nothing is silent."""
    _nest(host)
    subprocess.run(["git", "init", "-q", str(host)], check=True)
    touched = _touched(host, ["sub/spec/04_fr_list.json", SEED_PATH, "spec/04_fr_list.json"], manifest, spec="sub/spec")
    assert touched.steps == ("04",)
    assert touched.outside_root == (SEED_PATH, "spec/04_fr_list.json")


def test_nested_layout_with_the_git_root_finds_the_seeds_at_the_top(host: Path, manifest: dict[str, Any]) -> None:
    _nest(host)
    graph = lambda: build_graph(str(host / "sub" / "spec"), str(ROOT))  # noqa: E731
    touched = _touched(host, [SEED_PATH], manifest, graph, spec="sub/spec", git_root=str(host))
    assert touched.steps == ("00", "02")
    assert touched.outside_root == ()


def test_paths_outside_the_host_root_are_counted_as_unmapped(host: Path, manifest: dict[str, Any]) -> None:
    _nest(host)
    seed = str(host / SEED_PATH)
    spec_file = str(host / "sub" / "spec" / "04_fr_list.json")
    touched = _touched(host, [seed, "../README.md", spec_file], manifest, spec="sub/spec")
    assert touched.steps == ("04",)
    assert touched.outside_root == (seed, "../README.md")
    note = outside_root_note(touched)
    assert note is not None and note.startswith("2 paths lie outside the host root") and "--git-root" in note


def test_outside_root_note_is_absent_without_such_paths(host: Path, manifest: dict[str, Any]) -> None:
    assert outside_root_note(_touched(host, ["spec/04_fr_list.json"], manifest)) is None


def test_spec_folder_outside_the_git_root_is_refused(host: Path, manifest: dict[str, Any], tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(GitViewError):
        _touched(host, ["spec/04_fr_list.json"], manifest, git_root=str(other))


def test_the_seed_edit_note_is_true_for_a_whitespace_only_edit() -> None:
    """A whitespace-only edit makes nothing suspect, so the note sends the reader to ``stale`` instead of saying it does."""
    assert SEED_EDIT_NOTE == "seed document edited: run specdev stale to see what became suspect"


def test_plan_file_steps_are_the_three_trinity_steps() -> None:
    assert PLAN_FILE_STEPS == ("16a", "16b", "16c")
