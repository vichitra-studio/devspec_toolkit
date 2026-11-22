"""Library cases of ``diff`` over a real git history (WI-M4-10): a temporary repository with tags the test creates."""
from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph import gitview
from specdev_tools.graph.diff import ADDED, CHANGED, MINOR, NO_BUMP, PATCH, REMOVED, RENAMED, diff_refs, diff_to_dict, render_text
from specdev_tools.graph.gitview import GitViewError, archive_ref, load_graph_at, load_snapshot_at, spec_path_in_repo
from unit.graph._synth import EXAMPLE_SPEC, ROOT, load_doc, run_cli, run_specdev, write_json, write_spec
from unit.graph._synth import git as _git

_FR_FILE = "04_fr_list.json"
_SEED_MANIFEST = "common/seed_manifest.json"
_SEED_FILE = "docs/seed/notes.md"


def _commit(repo: Path, tag: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", tag)
    _git(repo, "tag", tag)


@pytest.fixture
def host(tmp_path: Path) -> Path:
    repo = tmp_path / "host"
    repo.mkdir()
    _git(repo, "init", "-q")
    return repo


def _fr_doc(statement: str, *criteria: str) -> dict[str, Any]:
    requirement: dict[str, Any] = {
        "fr_id": "fr-a",
        "statement": statement,
        "acceptance_criteria": [{"criterion_id": f"ac-{i}", "text": text} for i, text in enumerate(criteria, 1)],
    }
    return {"functional_requirements": [requirement]}


def _seed_manifest() -> dict[str, Any]:
    return {"seeds": [{"seed_id": "seed-notes", "path": _SEED_FILE}]}


def _two_tag_host(host: Path) -> Path:
    spec = host / "spec"
    write_spec(spec, {_FR_FILE: _fr_doc("The system shall do a.", "It works.")})
    _commit(host, "v1")
    write_spec(spec, {_FR_FILE: _fr_doc("The system shall do a, quickly.", "It works.", "It is fast.")})
    _commit(host, "v2")
    return spec


def test_two_tags_give_node_diff_and_bump_suggestion(host: Path) -> None:
    spec = _two_tag_host(host)
    diff = diff_refs("v1", "v2", str(host), str(spec), str(ROOT))
    assert {change.id: change.changes for change in diff.changes} == {"fr-a": (CHANGED,), "ac-2": (ADDED,)}
    assert (diff.bump, diff.old_ref, diff.new_ref) == (MINOR, "v1", "v2")


def test_diff_of_a_ref_with_itself_is_empty(host: Path) -> None:
    spec = _two_tag_host(host)
    diff = diff_refs("v2", "v2", str(host), str(spec), str(ROOT))
    assert (diff.changes, diff.bump) == ((), NO_BUMP)


def test_diff_reads_history_not_the_working_tree(host: Path) -> None:
    spec = _two_tag_host(host)
    write_spec(spec, {_FR_FILE: _fr_doc("Uncommitted edit.")})
    assert diff_refs("v2", "v2", str(host), str(spec), str(ROOT)).changes == ()


def test_load_graph_at_builds_the_graph_of_the_tag(host: Path) -> None:
    _two_tag_host(host)
    graph = load_graph_at("v1", str(host), "spec", str(ROOT))
    assert sorted(graph.by_id) == ["ac-1", "fr-a"]


def test_diff_seed_whitespace_only_is_unchanged(host: Path) -> None:
    spec = host / "spec"
    write_json(spec, _SEED_MANIFEST, _seed_manifest())
    (host / _SEED_FILE).parent.mkdir(parents=True)
    (host / _SEED_FILE).write_text("Users sign in.\nThey can reset a password.\n", encoding="utf-8")
    write_spec(spec, {_FR_FILE: _fr_doc("The system shall do a.")})
    _commit(host, "v1")
    (host / _SEED_FILE).write_text("Users   sign in.\n\n\nThey can reset a   password.", encoding="utf-8")
    _commit(host, "v2")
    assert diff_refs("v1", "v2", str(host), str(spec), str(ROOT)).changes == ()
    (host / _SEED_FILE).write_text("Users sign in. They can reset a password by email.", encoding="utf-8")
    _commit(host, "v3")
    changes = diff_refs("v2", "v3", str(host), str(spec), str(ROOT)).changes
    assert [(change.id, change.changes) for change in changes] == [("seed-notes", (CHANGED,))]


def test_diff_seed_file_absent_at_a_tag_counts_as_removed(host: Path) -> None:
    spec = host / "spec"
    write_json(spec, _SEED_MANIFEST, _seed_manifest())
    write_spec(spec, {_FR_FILE: _fr_doc("The system shall do a.")})
    _commit(host, "v1")
    (host / _SEED_FILE).parent.mkdir(parents=True)
    (host / _SEED_FILE).write_text("Now it exists.", encoding="utf-8")
    _commit(host, "v2")
    changes = diff_refs("v1", "v2", str(host), str(spec), str(ROOT)).changes
    assert [(change.id, change.changes) for change in changes] == [("seed-notes", (ADDED,))]


_EXAMPLE_SEED = "docs/seed/seed_accounts.md"
_EXAMPLE_SEED_ID = "seed-accounts"


@pytest.fixture
def example_host(host: Path) -> Path:
    """The worked example on the standard layout (``docs/seed/`` beside ``spec/``), committed as tag ``v1``."""
    shutil.copytree(EXAMPLE_SPEC.parent, host, dirs_exist_ok=True)
    _commit(host, "v1")
    return host


def _seed_changes(host: Path, old: str, new: str) -> list[tuple[str, tuple[str, ...]]]:
    changes = diff_refs(old, new, str(host), str(host / "spec"), str(ROOT)).changes
    return [(change.id, change.changes) for change in changes]


def test_diff_standard_layout_seed_edit_is_changed(example_host: Path) -> None:
    with (example_host / _EXAMPLE_SEED).open("a", encoding="utf-8") as seed:
        seed.write("A link also expires after a day.\n")
    _commit(example_host, "v2")
    assert _seed_changes(example_host, "v1", "v2") == [(_EXAMPLE_SEED_ID, (CHANGED,))]


def test_diff_standard_layout_seed_whitespace_only_is_unchanged(example_host: Path) -> None:
    seed = example_host / _EXAMPLE_SEED
    seed.write_text("\n\n".join(seed.read_text(encoding="utf-8").split("\n")) + "\n\n", encoding="utf-8")
    _commit(example_host, "v2")
    assert _seed_changes(example_host, "v1", "v2") == []


def test_diff_reads_seed_from_archive_root_at_each_ref(example_host: Path) -> None:
    (example_host / _EXAMPLE_SEED).write_text("Only the second text.", encoding="utf-8")
    _commit(example_host, "v2")
    texts = {ref: load_snapshot_at(ref, str(example_host), "spec", str(ROOT)).seeds[_EXAMPLE_SEED_ID] for ref in ("v1", "v2")}
    assert texts["v2"] == "Only the second text."
    assert texts["v1"] != texts["v2"]
    assert texts["v1"] == " ".join(_git(example_host, "show", f"v1:{_EXAMPLE_SEED}").split())


def test_snapshot_omits_a_seed_file_missing_at_the_ref(example_host: Path) -> None:
    (example_host / _EXAMPLE_SEED).unlink()
    _commit(example_host, "v2")
    snapshot = load_snapshot_at("v2", str(example_host), "spec", str(ROOT))
    assert _EXAMPLE_SEED_ID in snapshot.graph.by_id
    assert _EXAMPLE_SEED_ID not in snapshot.seeds
    assert _seed_changes(example_host, "v1", "v2") == [(_EXAMPLE_SEED_ID, (REMOVED,))]


def test_diff_spec_dir_absent_at_tag_e708(host: Path) -> None:
    (host / "README.md").write_text("no spec yet\n", encoding="utf-8")
    _commit(host, "v0")
    spec = write_spec(host / "spec", {_FR_FILE: _fr_doc("The system shall do a.")})
    _commit(host, "v1")
    with pytest.raises(GitViewError) as raised:
        diff_refs("v0", "v1", str(host), str(spec), str(ROOT))
    assert raised.value.error.code == "E708"
    assert "spec" in raised.value.error.message and "'v0'" in raised.value.error.message


def test_ref_unresolved_e708(host: Path) -> None:
    spec = _two_tag_host(host)
    with pytest.raises(GitViewError) as raised:
        diff_refs("v1", "v9", str(host), str(spec), str(ROOT))
    assert raised.value.error.code == "E708" and "'v9'" in raised.value.error.message


def test_a_ref_that_looks_like_an_option_is_e708(host: Path) -> None:
    _two_tag_host(host)
    with pytest.raises(GitViewError) as raised:
        gitview.resolve_ref("--output=x", str(host))
    assert raised.value.error.code == "E708" and "is not a git ref" in raised.value.error.message


def test_a_git_root_that_is_not_a_folder_is_e708_with_its_own_message(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-folder"
    with pytest.raises(GitViewError) as raised:
        gitview.resolve_ref("HEAD", str(missing))
    assert raised.value.error.code == "E708"
    assert raised.value.error.message == f"the git root {missing} is not a directory"
    file = tmp_path / "a-file"
    file.write_text("x", encoding="utf-8")
    with pytest.raises(GitViewError) as raised:
        gitview.resolve_ref("HEAD", str(file))
    assert "is not a directory" in raised.value.error.message


def test_diff_with_a_missing_git_root_names_the_git_root(tmp_path: Path) -> None:
    result = run_specdev("diff", "HEAD", "HEAD", "--repo-root", str(ROOT), "--spec-root", str(tmp_path / "nowhere" / "spec"), "--git-root", str(tmp_path / "nowhere"))
    assert result.returncode == 1 and result.stderr.startswith("E708") and "git root" in result.stderr and "not a directory" in result.stderr


def test_a_folder_that_is_not_a_repository_is_e708(tmp_path: Path) -> None:
    folder = tmp_path / "plain"
    folder.mkdir()
    with pytest.raises(GitViewError) as raised:
        gitview.resolve_ref("v1", str(folder))
    assert raised.value.error.code == "E708" and "not a git repository" in raised.value.error.message


def test_missing_git_is_e708(host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_git(*_args: Any, **_kwargs: Any) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitview.subprocess, "run", no_git)
    with pytest.raises(GitViewError) as raised:
        gitview.resolve_ref("v1", str(host))
    assert raised.value.error.code == "E708" and "git" in raised.value.error.message


def test_git_that_times_out_is_e708(host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def slow_git(*args: Any, **_kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(gitview.subprocess, "run", slow_git)
    with pytest.raises(GitViewError) as raised:
        gitview.resolve_ref("v1", str(host))
    assert raised.value.error.code == "E708" and "did not finish" in raised.value.error.message


def test_ref_predates_model_e709(host: Path) -> None:
    spec = host / "spec"
    legacy = {"functional_requirements": [{"statement": "Legacy requirement with no id."}]}
    write_spec(spec, {_FR_FILE: legacy})
    (spec / "specdev_version").write_text("toolkit_version: 1.1.0\n", encoding="utf-8")
    _commit(host, "v1")
    with pytest.raises(GitViewError) as raised:
        diff_refs("v1", "v1", str(host), str(spec), str(ROOT))
    assert raised.value.error.code == "E709" and "1.1.0" in raised.value.error.message


def test_ref_predates_model_e709_when_the_stamp_is_absent(host: Path) -> None:
    write_spec(host / "spec", {_FR_FILE: {"functional_requirements": []}})
    _commit(host, "v1")
    with pytest.raises(GitViewError) as raised:
        load_graph_at("v1", str(host), "spec", str(ROOT))
    assert raised.value.error.code == "E709" and "no toolkit stamp" in raised.value.error.message


def test_ref_with_only_seeds_is_e709(host: Path) -> None:
    spec = host / "spec"
    write_spec(spec, {_SEED_MANIFEST: _seed_manifest()})
    (host / _SEED_FILE).parent.mkdir(parents=True)
    (host / _SEED_FILE).write_text("notes\n", encoding="utf-8")
    _commit(host, "seeds-only")
    with pytest.raises(GitViewError) as raised:
        load_graph_at("seeds-only", str(host), "spec", str(ROOT))
    assert raised.value.error.code == "E709"


def test_ref_with_a_node_beside_its_seeds_is_not_refused(host: Path) -> None:
    spec = host / "spec"
    write_spec(spec, {_SEED_MANIFEST: _seed_manifest(), _FR_FILE: _fr_doc("The system shall do a.")})
    (host / _SEED_FILE).parent.mkdir(parents=True)
    (host / _SEED_FILE).write_text("notes\n", encoding="utf-8")
    _commit(host, "seeds-and-fr")
    assert "fr-a" in load_graph_at("seeds-and-fr", str(host), "spec", str(ROOT)).by_id


@pytest.mark.parametrize("failure", [tarfile.ReadError("truncated"), OSError("disk full")], ids=["tar error", "os error"])
def test_an_archive_that_cannot_be_unpacked_is_e708(host: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    _two_tag_host(host)

    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise failure

    monkeypatch.setattr(gitview.tarfile, "open", broken)
    with pytest.raises(GitViewError) as raised:
        archive_ref("v1", str(host), ["spec"])
    assert raised.value.error.code == "E708" and "cannot be unpacked" in raised.value.error.message


def test_a_1_1_1_tree_that_has_ids_is_compared_not_refused(host: Path) -> None:
    spec = host / "spec"
    spec.mkdir()
    for source in (ROOT / "tests" / "fixtures" / "spec_corpus").iterdir():
        (spec / source.name).write_bytes(source.read_bytes())
    _commit(host, "corpus")
    for stale in spec.iterdir():
        stale.unlink()
    for source in (ROOT / "tests" / "fixtures" / "graph_example" / "spec").rglob("*"):
        if source.is_file():
            target = spec / source.relative_to(ROOT / "tests" / "fixtures" / "graph_example" / "spec")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    _commit(host, "example")
    result = run_specdev(
        "diff", "HEAD~1", "HEAD", "--repo-root", str(ROOT), "--spec-root", str(spec), "--git-root", str(host)
    )
    assert result.returncode == 0, result.stderr
    assert "E709" not in result.stdout + result.stderr
    assert "FR-CORPUS-001: removed" in result.stdout and "fr-password-reset: added" in result.stdout


def test_a_git_root_that_is_not_a_folder_is_named_before_the_spec_folder_is_checked(host: Path) -> None:
    spec = _two_tag_host(host)
    missing = host / "no-such-folder"
    with pytest.raises(GitViewError) as raised:
        diff_refs("v1", "v2", str(missing), str(spec), str(ROOT))
    assert raised.value.error.code == "E708" and "is not a directory" in raised.value.error.message
    result = run_specdev(
        "diff", "v1", "v2", "--repo-root", str(ROOT), "--spec-root", str(spec), "--git-root", str(missing)
    )
    assert result.returncode == 1 and result.stderr.startswith("E708") and "is not a directory" in result.stderr


def test_spec_path_is_relative_to_the_git_root(host: Path) -> None:
    nested = host / "services" / "api" / "spec"
    nested.mkdir(parents=True)
    assert spec_path_in_repo(str(nested), str(host)) == "services/api/spec"
    assert spec_path_in_repo(str(host / "spec"), str(host / "spec" / "..")) == "spec"


def test_diff_of_a_spec_folder_below_the_repository_root(host: Path) -> None:
    spec = write_spec(host / "services" / "spec", {_FR_FILE: _fr_doc("The system shall do a.")})
    _commit(host, "v1")
    write_spec(spec, {_FR_FILE: _fr_doc("The system shall do a, quickly.")})
    _commit(host, "v2")
    diff = diff_refs("v1", "v2", str(host), str(spec), str(ROOT))
    assert [(change.id, change.changes) for change in diff.changes] == [("fr-a", (CHANGED,))]


def test_spec_root_outside_git_root_is_e708(host: Path, tmp_path: Path) -> None:
    with pytest.raises(GitViewError) as raised:
        spec_path_in_repo(str(tmp_path / "elsewhere"), str(host))
    assert raised.value.error.code == "E708" and "not inside the git root" in raised.value.error.message


def test_archive_ref_extracts_the_paths_at_the_ref(host: Path) -> None:
    spec = _two_tag_host(host)
    with archive_ref("v1", str(host), ["spec"]) as archived:
        text = (Path(archived) / "spec" / _FR_FILE).read_text(encoding="utf-8")
    assert "It is fast." not in text and "It works." in text
    assert "It is fast." in (spec / _FR_FILE).read_text(encoding="utf-8")
    assert not Path(archived).exists()


# --- a rename is one renamed node, not a removal and an addition --------------------------------------------------------

_CRITERION = "ac-password-reset-3"
_FR = "fr-password-reset"


def _rename_and_tag(host: Path, old: str, new: str, tag: str) -> None:
    code, out = run_cli("node", "rename", old, new, "--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host))
    assert code == 0, out
    _commit(host, tag)


def _changes(host: Path, old: str, new: str) -> list[tuple[str, tuple[str, ...], str | None]]:
    diff = diff_refs(old, new, str(host), str(host / "spec"), str(ROOT))
    return [(change.id, change.changes, change.old_id) for change in diff.changes]


def test_a_rename_between_two_refs_is_one_renamed_node_and_no_holder_is_changed(example_host: Path) -> None:
    _rename_and_tag(example_host, _CRITERION, "ac-password-reset-3b", "v2")
    assert _changes(example_host, "v1", "v2") == [("ac-password-reset-3b", (RENAMED,), _CRITERION)]
    diff = diff_refs("v1", "v2", str(example_host), str(example_host / "spec"), str(ROOT))
    assert diff.bump == PATCH
    assert "ac-password-reset-3b: renamed from ac-password-reset-3" in render_text(diff)
    nodes = [node for group in diff_to_dict(diff)["groups"] for node in group["nodes"]]
    assert nodes == [{"id": "ac-password-reset-3b", "changes": ["renamed"], "old_id": _CRITERION}]


def test_a_second_rename_is_found_from_the_first_name_and_from_the_middle_name(example_host: Path) -> None:
    _rename_and_tag(example_host, _FR, "fr-password-reset-v2", "v2")
    _rename_and_tag(example_host, "fr-password-reset-v2", "fr-password-reset-v3", "v3")
    assert _changes(example_host, "v1", "v3") == [("fr-password-reset-v3", (RENAMED,), _FR)]
    assert _changes(example_host, "v2", "v3") == [("fr-password-reset-v3", (RENAMED,), "fr-password-reset-v2")]


def test_a_rename_with_an_edit_is_renamed_and_changed(example_host: Path) -> None:
    _rename_and_tag(example_host, _CRITERION, "ac-password-reset-3b", "v2")
    document = load_doc(example_host / "spec", _FR_FILE)
    criterion = document["functional_requirements"][0]["acceptance_criteria"][2]
    criterion["text"] += " Also reject a token issued for another account."
    write_json(example_host / "spec", _FR_FILE, document)
    _commit(example_host, "v3")
    assert _changes(example_host, "v1", "v3")[0] == ("ac-password-reset-3b", (RENAMED, CHANGED), _CRITERION)
    assert diff_refs("v1", "v3", str(example_host), str(example_host / "spec"), str(ROOT)).bump == MINOR


def test_an_alias_of_an_id_that_still_exists_is_not_a_rename(example_host: Path) -> None:
    document = load_doc(example_host / "spec", _FR_FILE)
    document["functional_requirements"].append({"fr_id": "fr-brand-new", "statement": "The system shall exist.", "aliases": [_FR]})
    write_json(example_host / "spec", _FR_FILE, document)
    _commit(example_host, "v2")
    assert _changes(example_host, "v1", "v2") == [("fr-brand-new", (ADDED,), None)]


# --- the command ---------------------------------------------------------------------------------------------------

def _diff_cli(host: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run_specdev("diff", *args, "--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host))


def test_cli_diff_prints_the_changes_and_the_bump(host: Path) -> None:
    _two_tag_host(host)
    result = _diff_cli(host, "v1", "v2")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == "diff v1 -> v2: 2 node(s) changed"
    assert lines[-1] == "suggested bump: minor"


def test_cli_diff_json_has_the_groups_and_the_bump(host: Path) -> None:
    _two_tag_host(host)
    document = json.loads(_diff_cli(host, "v1", "v2", "--json").stdout)
    assert {"from", "to", "bump", "groups", "new_removes"} == set(document) and document["bump"] == "minor"


def test_cli_diff_of_equal_refs_is_empty(host: Path) -> None:
    _two_tag_host(host)
    result = _diff_cli(host, "v2", "v2")
    assert result.returncode == 0 and result.stdout.splitlines()[0] == "diff v2 -> v2: 0 node(s) changed"


def test_cli_diff_unresolvable_ref_is_e708_on_stderr(host: Path) -> None:
    _two_tag_host(host)
    result = _diff_cli(host, "v1", "v9")
    assert result.returncode == 1 and result.stderr.startswith("E708") and "v9" in result.stderr


def test_cli_diff_unresolvable_ref_as_json_envelope(host: Path) -> None:
    _two_tag_host(host)
    document = json.loads(_diff_cli(host, "v1", "v9", "--json").stdout)
    assert (document["command"], document["status"], document["errors"][0]["code"]) == ("diff", "FAIL", "E708")


def test_diff_submodule_flags(host: Path) -> None:
    """``diff --repo-root <toolkit> --spec-root <absolute spec> --git-root <host>`` reads the spec folder at its path relative to the git root."""
    nested = _two_tag_host(host)
    assert nested == host / "spec" and nested.is_absolute()
    result = run_specdev("diff", "v1", "v2", "--repo-root", str(ROOT), "--spec-root", str(nested), "--git-root", str(host))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == "diff v1 -> v2: 2 node(s) changed"
    assert spec_path_in_repo(str(nested), str(host)) == "spec"


def _stamped_host_with_nodes(host: Path, stamp: str | None) -> None:
    """A tree that has a node (so it LOOKS like a 1.2.0 spec), stamped *stamp* (no stamp file when ``None``), committed as tag ``t``."""
    spec = host / "spec"
    write_spec(spec, {_FR_FILE: _fr_doc("The system shall do a.", "It works.")})
    if stamp is not None:
        (spec / "specdev_version").write_text(f"toolkit_version: {stamp}\n", encoding="utf-8")
    _commit(host, "t")


def test_a_ref_stamped_below_1_2_0_is_e709_even_when_it_has_nodes(host: Path) -> None:
    _stamped_host_with_nodes(host, "1.1.1")
    with pytest.raises(GitViewError) as raised:
        load_graph_at("t", str(host), "spec", str(ROOT))
    assert raised.value.error.code == "E709"
    assert "stamped toolkit 1.1.1" in raised.value.error.message and "below 1.2.0" in raised.value.error.message
    result = run_specdev("diff", "t", "t", "--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host))
    assert result.returncode == 1 and "E709" in result.stderr


def test_a_ref_with_no_stamp_is_judged_by_structure_as_before(host: Path) -> None:
    _stamped_host_with_nodes(host, None)
    assert "fr-a" in load_graph_at("t", str(host), "spec", str(ROOT)).by_id
    write_spec(host / "spec", {_FR_FILE: {"functional_requirements": []}})
    _commit(host, "empty")
    with pytest.raises(GitViewError) as raised:
        load_graph_at("empty", str(host), "spec", str(ROOT))
    assert raised.value.error.code == "E709" and "no toolkit stamp" in raised.value.error.message


def test_a_ref_stamped_1_2_0_or_later_is_read(host: Path) -> None:
    _stamped_host_with_nodes(host, "1.2.0")
    assert "fr-a" in load_graph_at("t", str(host), "spec", str(ROOT)).by_id
    write_spec(host / "spec", {_FR_FILE: {"functional_requirements": []}})
    (host / "spec" / "specdev_version").write_text("toolkit_version: 1.3.0\n", encoding="utf-8")
    _commit(host, "later")
    with pytest.raises(GitViewError) as raised:  # a 1.3.0 stamp does not excuse a tree with no node
        load_graph_at("later", str(host), "spec", str(ROOT))
    assert raised.value.error.code == "E709" and "stamped toolkit 1.3.0" in raised.value.error.message
