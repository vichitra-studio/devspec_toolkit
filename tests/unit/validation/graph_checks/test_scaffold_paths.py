"""The scaffold row path check (E746, WI-M6b-08): tracked files, submodules, the git-less host, the merge filter, lifecycle and order."""
from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from specdev_tools.validation.graph_checks import scaffold
from specdev_tools.validation.graph_checks.context import GraphCheckContext, Mode
from specdev_tools.validation.graph_checks.scaffold import scaffold_scan, check_scaffold_paths, run_scaffold_paths, scaffold_rows_untracked
from unit.graph._synth import HASH_SEEDS

from ._order_support import seeded
from ._git_support import SUBMODULE, clone_without_submodules, git, make_host_with_submodule, make_repo
from ._scaffold_support import SCAFFOLD_FILE
from ._scaffold_support import scaffold_context as _context


def _paths(context: GraphCheckContext, mode: Mode = "close", api_ids: Sequence[str] | None = None) -> list[str | None]:
    return [error.node_id for error in scaffold_rows_untracked(context, api_ids, mode)]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "host", {"src/a.ts": "a", "src/b.ts": "b"})


def test_tracked_path_gives_no_e746(repo: Path) -> None:
    assert _paths(_context({"row-a": ("src/a.ts", ["api-1"])}, repo)) == []
    assert _paths(_context({"row-a": ("./src/../src/a.ts", ["api-1"])}, repo)) == []


def test_untracked_path_gives_e746(repo: Path) -> None:
    (repo / "src" / "c.ts").write_text("c", encoding="utf-8")
    rows = {"row-a": ("src/a.ts", ["api-1"]), "row-c": ("src/c.ts", ["api-1"]), "row-missing": ("src/none.ts", ["api-1"])}
    assert _paths(_context(rows, repo)) == ["row-c", "row-missing"]


def test_submodule_tracked_path_gives_no_e746(tmp_path: Path) -> None:
    host = make_host_with_submodule(tmp_path, {"h.txt": "h"}, {"a.txt": "a"})
    (host / SUBMODULE / "loose.txt").write_text("untracked", encoding="utf-8")
    context = _context({"row-in": (f"{SUBMODULE}/a.txt", ["api-1"]), "row-loose": (f"{SUBMODULE}/loose.txt", ["api-1"])}, host)
    assert _paths(context) == ["row-loose"]


def test_plain_ls_files_would_report_submodule_rows_so_recurse_is_used(tmp_path: Path) -> None:
    host = make_host_with_submodule(tmp_path, {"h.txt": "h"}, {"a.txt": "a"})
    assert f"{SUBMODULE}/a.txt" not in git(host, "ls-files").split()
    assert _paths(_context({"row-in": (f"{SUBMODULE}/a.txt", ["api-1"])}, host)) == []


def test_a_folder_that_only_shares_the_prefix_of_an_unchecked_submodule_is_checked(tmp_path: Path) -> None:
    host = make_host_with_submodule(tmp_path, {"h.txt": "h"}, {"a.txt": "a"})
    clone = clone_without_submodules(host, tmp_path / "clone")
    rows = {"row-in": (f"{SUBMODULE}/a.txt", ["api-1"]), "row-near": (f"{SUBMODULE}s/none.ts", ["api-1"])}
    scan = scaffold_scan(_context(rows, clone), None, "close")
    assert [error.node_id for error in scan.findings] == ["row-near"]
    assert len(scan.notes) == 1 and "row-in" in scan.notes[0]


def test_uninitialised_submodule_rows_skip_not_e746(tmp_path: Path) -> None:
    host = make_host_with_submodule(tmp_path, {"h.txt": "h"}, {"a.txt": "a"})
    clone = clone_without_submodules(host, tmp_path / "clone")
    scan = scaffold_scan(_context({"row-in": (f"{SUBMODULE}/a.txt", ["api-1"]), "row-gone": ("src/none.ts", ["api-1"])}, clone), None, "close")
    assert [error.node_id for error in scan.findings] == ["row-gone"]
    assert len(scan.notes) == 1 and "row-in" in scan.notes[0] and SUBMODULE in scan.notes[0]


def test_every_row_under_an_unchecked_submodule_skips_the_whole_check(tmp_path: Path) -> None:
    """Nothing was judged: the registered check reports SKIP with the reason (the summary and ``--json`` show it); with one row elsewhere it runs and only notes the others."""
    host = make_host_with_submodule(tmp_path, {"h.txt": "h"}, {"a.txt": "a", "b.txt": "b"})
    clone = clone_without_submodules(host, tmp_path / "clone")
    everything = _context({"row-a": (f"{SUBMODULE}/a.txt", ["api-1"]), "row-b": (f"{SUBMODULE}/b.txt", ["api-1"])}, clone, built=["api-1"])
    scan = scaffold_scan(everything, None, "merge")
    assert scan.findings == [] and len(scan.notes) == 2
    assert scan.skip_reason is not None and SUBMODULE in scan.skip_reason and "every scaffold row" in scan.skip_reason
    with patch.object(GraphCheckContext, "from_registry", return_value=everything):
        result = run_scaffold_paths(object())  # type: ignore[arg-type]
    assert result["status"] == "SKIP" and result["reason"] == scan.skip_reason

    some = _context({"row-a": (f"{SUBMODULE}/a.txt", ["api-1"]), "row-h": ("h.txt", ["api-1"])}, clone, built=["api-1"])
    scan = scaffold_scan(some, None, "merge")
    assert scan.skip_reason is None and len(scan.notes) == 1
    with patch.object(GraphCheckContext, "from_registry", return_value=some):
        assert run_scaffold_paths(object())["status"] == "PASS"  # type: ignore[arg-type]


def test_the_note_of_rows_under_an_unchecked_submodule_is_left_out_of_a_quiet_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    host = make_host_with_submodule(tmp_path, {"h.txt": "h"}, {"a.txt": "a"})
    clone = clone_without_submodules(host, tmp_path / "clone")
    rows = {"row-a": (f"{SUBMODULE}/a.txt", ["api-1"]), "row-h": ("h.txt", ["api-1"])}
    for quiet, noted in ((False, True), (True, False)):
        context = replace(_context(rows, clone, built=["api-1"]), quiet=quiet)
        with patch.object(GraphCheckContext, "from_registry", return_value=context):
            assert run_scaffold_paths(object())["status"] == "PASS"  # type: ignore[arg-type]
        assert ("is under submodule" in capsys.readouterr().err) is noted


def test_the_scan_tells_clean_from_could_not_check(repo: Path) -> None:
    """A gate that reads only the findings cannot: no host root gives no findings and a skip reason, a clean repository gives no findings and none."""
    rows = {"row-a": ("src/a.ts", ["api-1"])}
    unreadable = scaffold_scan(_context(rows, None), None, "close")
    assert unreadable.findings == [] and unreadable.skip_reason is not None
    clean = scaffold_scan(_context(rows, repo), None, "close")
    assert clean.findings == [] and clean.skip_reason is None


def test_non_git_host_skips(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    for root in (plain, None):
        scan = scaffold_scan(_context({"row-a": ("src/a.ts", ["api-1"])}, root), None, "close")
        assert scan.findings == [] and scan.skip_reason


def test_merge_mode_skips_rows_of_unbuilt_api(repo: Path) -> None:
    rows = {"row-built": ("src/gone-1.ts", ["api-1"]), "row-unbuilt": ("src/gone-2.ts", ["api-2"])}
    assert _paths(_context(rows, repo, built=["api-1"]), "merge") == ["row-built"]


def test_merge_mode_checks_a_row_with_two_apis_once_one_is_built(repo: Path) -> None:
    rows = {"row-two": ("src/gone.ts", ["api-1", "api-2"])}
    assert _paths(_context(rows, repo, built=["api-2"]), "merge") == ["row-two"]
    assert _paths(_context(rows, repo), "merge") == []


def test_close_mode_checks_every_row(repo: Path) -> None:
    rows = {"row-1": ("src/gone-1.ts", ["api-1"]), "row-2": ("src/gone-2.ts", ["api-2"])}
    context = _context(rows, repo)
    assert _paths(context, "close") == _paths(context, "release") == ["row-1", "row-2"]
    assert _paths(context, "merge") == []


def test_api_ids_limit_the_rows_read(repo: Path) -> None:
    rows = {"row-1": ("src/gone-1.ts", ["api-1"]), "row-2": ("src/gone-2.ts", ["api-2"])}
    assert _paths(_context(rows, repo), "close", ["api-2"]) == ["row-2"]


def test_e746_owner_is_step_15_and_names_row_path_and_mode(repo: Path) -> None:
    (error,) = scaffold_rows_untracked(_context({"row-a": ("src/gone.ts", ["api-1"])}, repo), None, "release")
    assert (error.code, error.owner, error.node_id) == ("E746", "step:15", "row-a")
    assert "row-a" in error.message and "src/gone.ts" in error.message and "release" in error.message
    assert (error.file, error.jq_path) == (SCAFFOLD_FILE, ".rows[0]")


def test_git_ls_files_runs_once_per_run(repo: Path) -> None:
    calls: list[list[str]] = []
    real = scaffold.run_git

    def counting(git_root: str, args: Sequence[str]):
        calls.append(list(args))
        return real(git_root, args)

    rows = {f"row-{index}": (f"src/gone-{index}.ts", ["api-1"]) for index in range(3)}
    with patch.object(scaffold, "run_git", counting):
        assert len(check_scaffold_paths(_context(rows, repo, built=["api-1"]), "merge")) == 3
    assert [args[0] for args in calls] == ["ls-files"]


def test_scaffold_paths_do_not_read_a_not_applicable_node(repo: Path) -> None:
    rows = {"row-a": ("src/gone.ts", ["api-1"])}
    assert _paths(_context(rows, repo, lifecycle="not_applicable")) == []
    assert _paths(_context(rows, repo, lifecycle="deprecated")) == ["row-a"]


def _scenario(reverse: bool) -> list[str | None]:
    with tempfile.TemporaryDirectory() as folder:
        host = make_repo(Path(folder) / "host", {"src/a.ts": "a"})
        rows = {f"row-{name}": (f"src/none-{name}.ts", ["api-1"]) for name in ("m", "z", "a", "k")}
        ordered = dict(reversed(list(rows.items()))) if reverse else rows
        return _paths(_context(ordered, host))


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_scaffold_paths_report_in_the_same_order_whatever_the_hash_seed(seed: int) -> None:
    expected = _scenario(False)
    assert expected == ["row-a", "row-k", "row-m", "row-z"] == seeded(seed, __name__, "_scenario", True)
