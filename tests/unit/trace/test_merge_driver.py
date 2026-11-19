"""The lock merge driver (WI-M5-07): the three-way table, the S-010 choice, the integrity refusals, the installer."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specdev_tools.core.constants import TRACE_LOCK_FILENAME
from specdev_tools.core.errors import FindingError
from specdev_tools.trace.lockfile import Lock, LockEntry, LockError, serialise_lock
from specdev_tools.trace.merge_driver import (
    DRIVER_NAME,
    LockMergeError,
    attribute_line,
    install_driver,
    merge_entry,
    merge_files,
    merge_locks,
)

BASE = LockEntry("fr-a", "api_refs", "api-x", "sha256:" + "1" * 64, "sha256:" + "2" * 64)
CHANGED = LockEntry("fr-a", "api_refs", "api-x", "sha256:" + "3" * 64, "sha256:" + "4" * 64)
OTHER = LockEntry("fr-a", "api_refs", "api-x", "sha256:" + "5" * 64, "sha256:" + "6" * 64)
SMALL = LockEntry("fr-a", "api_refs", "api-x", "sha256:" + "9" * 64, "sha256:" + "0" * 64)
LARGE = LockEntry("fr-a", "api_refs", "api-x", "sha256:" + "0" * 64, "sha256:" + "f" * 64)
SPEC = "spec"
Z_ENTRY = LockEntry("z", "f", "t", OTHER.content_hash, OTHER.chain_stamp)


@pytest.mark.parametrize(
    ("base", "ours", "theirs", "expected"),
    [
        pytest.param(BASE, BASE, BASE, BASE, id="unchanged"),
        pytest.param(BASE, CHANGED, CHANGED, CHANGED, id="both-made-the-same-change"),
        pytest.param(BASE, None, None, None, id="both-deleted"),
        pytest.param(None, BASE, BASE, BASE, id="both-added-the-same"),
        pytest.param(BASE, BASE, CHANGED, CHANGED, id="only-theirs-changed"),
        pytest.param(BASE, CHANGED, BASE, CHANGED, id="only-ours-changed"),
        pytest.param(BASE, BASE, None, None, id="theirs-deleted-ours-untouched"),
        pytest.param(BASE, None, BASE, None, id="ours-deleted-theirs-untouched"),
        pytest.param(None, None, CHANGED, CHANGED, id="theirs-added"),
        pytest.param(None, CHANGED, None, CHANGED, id="ours-added"),
        pytest.param(BASE, None, CHANGED, CHANGED, id="ours-deleted-theirs-modified"),
        pytest.param(BASE, CHANGED, None, CHANGED, id="theirs-deleted-ours-modified"),
        pytest.param(BASE, CHANGED, OTHER, BASE, id="both-modified-keeps-the-base"),
        pytest.param(None, CHANGED, OTHER, CHANGED, id="both-added-smaller-chain-stamp"),
    ],
)
def test_three_way_table_every_case(base, ours, theirs, expected) -> None:
    assert merge_entry(base, ours, theirs) == expected


def test_s010_base_entry_kept_when_both_modified() -> None:
    merged = merge_locks(Lock((BASE,)), Lock((CHANGED,)), Lock((OTHER,)))
    assert merged.entries == (BASE,)


def test_s010_no_base_smaller_chain_stamp_wins() -> None:
    assert merge_locks(Lock(), Lock((LARGE,)), Lock((SMALL,))).entries == (SMALL,)
    assert merge_entry(None, CHANGED, OTHER) == CHANGED


def test_s010_equal_chain_stamps_fall_back_to_content_hash_and_baseline() -> None:
    low = LockEntry("a", "f", "t", "sha256:" + "1" * 64, "sha256:" + "2" * 64)
    high = LockEntry("a", "f", "t", "sha256:" + "3" * 64, "sha256:" + "2" * 64)
    flagged = LockEntry("a", "f", "t", "sha256:" + "1" * 64, "sha256:" + "2" * 64, True)
    assert merge_entry(None, high, low) == low
    assert merge_entry(None, flagged, low) == low


def _lock(*entries: LockEntry) -> Lock:
    return Lock(entries)


def test_keys_merge_independently() -> None:
    kept = LockEntry("fr-b", "api_refs", "api-y", "sha256:" + "7" * 64, "sha256:" + "8" * 64)
    added_ours = LockEntry("fr-c", "api_refs", "api-z", "sha256:" + "a" * 64, "sha256:" + "b" * 64)
    added_theirs = LockEntry("fr-d", "api_refs", "api-z", "sha256:" + "c" * 64, "sha256:" + "d" * 64)
    merged = merge_locks(_lock(BASE, kept), _lock(BASE, kept, added_ours), _lock(CHANGED, kept, added_theirs))
    assert merged.entries == (CHANGED, kept, added_ours, added_theirs)


@pytest.mark.parametrize(
    ("base", "ours", "theirs"),
    [
        (Lock((BASE,)), Lock((CHANGED,)), Lock((OTHER,))),
        (Lock(), Lock((LARGE,)), Lock((SMALL,))),
        (Lock((BASE,)), Lock(), Lock((CHANGED,))),
        (Lock((BASE,)), Lock((CHANGED,)), Lock((BASE, Z_ENTRY))),
    ],
)
def test_output_is_symmetric_in_both_directions(base: Lock, ours: Lock, theirs: Lock) -> None:
    assert serialise_lock(merge_locks(base, ours, theirs)) == serialise_lock(merge_locks(base, theirs, ours))


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def _merge_on_disk(tmp_path: Path, base: str, ours: str, theirs: str) -> Path:
    paths = [_write(tmp_path / name, text) for name, text in (("base", base), ("ours", ours), ("theirs", theirs))]
    merge_files(*paths, "spec/extras/trace.lock.json")
    return tmp_path / "ours"


def test_merge_files_writes_the_result_over_ours(tmp_path: Path) -> None:
    result = _merge_on_disk(tmp_path, serialise_lock(_lock(BASE)), serialise_lock(_lock(BASE, Z_ENTRY)), serialise_lock(_lock(CHANGED)))
    assert [(e["source"], e["target"]) for e in json.loads(result.read_text())["entries"]] == [("fr-a", "api-x"), ("z", "t")]


def test_merge_files_takes_an_empty_base_as_an_empty_lock(tmp_path: Path) -> None:
    result = _merge_on_disk(tmp_path, "", serialise_lock(_lock(LARGE)), serialise_lock(_lock(SMALL)))
    assert result.read_text() == serialise_lock(_lock(SMALL))


_BAD_VERSION = serialise_lock(_lock(BASE)).replace('"version": 1', '"version": 2')
_BAD_ENTRY = serialise_lock(_lock(BASE)).replace("sha256:" + "1" * 64, "sha256:short")
_MARKERS = "<<<<<<< ours\n" + serialise_lock(_lock(BASE)) + "=======\n>>>>>>> theirs\n"


@pytest.mark.parametrize("bad", [_BAD_VERSION, _BAD_ENTRY, "not json", _MARKERS], ids=["version", "entry", "json", "markers"])
@pytest.mark.parametrize("side", ["base", "ours", "theirs"])
def test_malformed_entry_or_version_mismatch_exits_1(tmp_path: Path, side: str, bad: str) -> None:
    texts = {"base": serialise_lock(_lock(BASE)), "ours": serialise_lock(_lock(CHANGED)), "theirs": serialise_lock(_lock(OTHER))}
    texts[side] = bad
    ours_before = texts["ours"]
    with pytest.raises(LockError) as caught:
        _merge_on_disk(tmp_path, texts["base"], texts["ours"], texts["theirs"])
    assert caught.value.error.code == "E760"
    assert (tmp_path / "ours").read_text() == ours_before


def test_an_unreadable_version_is_e520(tmp_path: Path) -> None:
    ours = _write(tmp_path / "ours", serialise_lock(_lock(BASE)))
    with pytest.raises(LockMergeError) as caught:
        merge_files(str(tmp_path / "missing"), ours, ours, "p")
    assert isinstance(caught.value, FindingError) and caught.value.error.code == "E520"


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)


def _attributes(repo: Path) -> Path:
    return repo / ".git" / "info" / "attributes"


def _config(repo: Path, key: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "config", "--local", "--get", key], capture_output=True, text=True, check=True).stdout.strip()


def test_install_driver_idempotent(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    first = install_driver(str(tmp_path), SPEC, "/venv/bin/specdev lock merge")
    second = install_driver(str(tmp_path), SPEC, "/venv/bin/specdev lock merge")
    assert first == second
    line = f"spec/extras/{TRACE_LOCK_FILENAME} merge={DRIVER_NAME}"
    assert _attributes(tmp_path).read_text().splitlines().count(line) == 1
    assert _config(tmp_path, f"merge.{DRIVER_NAME}.driver") == "/venv/bin/specdev lock merge %O %A %B %P"
    assert _config(tmp_path, f"merge.{DRIVER_NAME}.name")
    assert not (tmp_path / ".gitattributes").exists()


def test_install_driver_keeps_existing_attributes_and_adds_a_missing_newline(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _attributes(tmp_path).write_text("*.bin binary", encoding="utf-8")
    install_driver(str(tmp_path), "docs/spec", "specdev lock merge")
    assert _attributes(tmp_path).read_text().splitlines() == ["*.bin binary", f"docs/spec/extras/{TRACE_LOCK_FILENAME} merge={DRIVER_NAME}"]


def test_install_driver_replaces_a_changed_driver_command(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    install_driver(str(tmp_path), SPEC, "old lock merge")
    install_driver(str(tmp_path), SPEC, "new lock merge")
    assert _config(tmp_path, f"merge.{DRIVER_NAME}.driver") == "new lock merge %O %A %B %P"


def test_install_driver_outside_a_repository_is_e520(tmp_path: Path) -> None:
    with pytest.raises(LockMergeError) as caught:
        install_driver(str(tmp_path / "nowhere"), SPEC, "specdev lock merge")
    assert caught.value.error.code == "E520"


@pytest.mark.parametrize(("spec", "expected"), [("spec", "spec/extras"), (".", "extras"), ("a/b/", "a/b/extras")])
def test_attribute_line_names_the_lock_path_from_the_git_root(spec: str, expected: str) -> None:
    assert attribute_line(spec) == f"{expected}/{TRACE_LOCK_FILENAME} merge={DRIVER_NAME}"


def test_a_git_failure_reaches_the_caller_as_the_e520_of_the_driver(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``_git`` re-wraps the ``GitViewError`` of ``run_git`` (a missing git, a timeout) so the driver reports E520, as the module promises."""
    from specdev_tools.core.errors import make_error
    from specdev_tools.graph.gitview import GitViewError
    from specdev_tools.trace import merge_driver

    def failing(git_root: str, args: object) -> object:
        raise GitViewError(make_error("E708", "git did not answer within 30 seconds"))

    monkeypatch.setattr(merge_driver, "run_git", failing)
    with pytest.raises(LockMergeError) as caught:
        merge_driver._git(str(tmp_path), ["rev-parse", "--git-dir"])
    assert not isinstance(caught.value, GitViewError)
    assert caught.value.error.code == "E520" and "git did not answer within 30 seconds" in caught.value.error.message
