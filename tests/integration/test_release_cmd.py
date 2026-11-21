"""``specdev release`` through ``main([...])``: the cut and its refusals, the next-release check on a second cut, and ``release rollback``.

Every test works on a git copy of the worked example made release-ready (``unit.release._support``): 0 errors at the gate, 28 obligations
listed as parked.  A refused cut leaves every file and every ref as it was.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from specdev_tools.graph import gitview
from unit.graph._synth import git, run_cli
from unit.lifecycle._milestone_support import cli_run
from unit.lifecycle._record_support import no_identity  # noqa: F401  (the fixture ``no_identity``)
from unit.release._support import advance, commit, release_host, tag
from unit.verify._support import commit_all, write
from integration._release_support import DEPLOY_ACTION, DEPLOY_ITEM, IDENTITY, at_deploy_host, identity, snapshot, toolkit_1_2_0  # noqa: F401

pytestmark = pytest.mark.usefixtures("identity")
LEFT_IN_SCOPE = "inv-reset-token-single-use"


def _tags(host: Path) -> list[str]:
    return git(host, "tag").split()


def _refused(host: Path, code: str, *argv: str) -> str:
    """Run a command that must exit 1 naming *code*, with the tree and the refs as they were; returns the output."""
    before = snapshot(host)
    exit_code, out, err = cli_run(host, *argv)
    assert exit_code == 1 and code in out + err, f"{argv}: exit {exit_code}\n{out}{err}"
    assert snapshot(host) == before, "a refused command wrote something"
    return out + err


# --- the cut ----------------------------------------------------------------------------------------------------------


def test_release_creates_annotated_tag_on_head_when_gate_passes(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    head, before = git(host, "rev-parse", "HEAD"), snapshot(host)
    code, out, err = cli_run(host, "release", "--tag", "v1.0.0", "--message", "the first release")
    assert code == 0, out + err
    assert git(host, "cat-file", "-t", "v1.0.0") == "tag"
    assert git(host, "rev-parse", "v1.0.0^{commit}") == head
    assert git(host, "tag", "-n1", "-l", "v1.0.0").split(None, 1)[1] == "the first release"
    assert "annotated tag created" in out and "not pushed" in out and "28 listed" in out
    after = snapshot(host)
    assert after["files"] == before["files"] and after["head"] == head, "the cut writes the tag and nothing else"
    assert git(host, "status", "--porcelain") == ""


def test_release_without_message_annotates_with_the_tag_name(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    assert cli_run(host, "release", "--tag", "v1.0.0")[0] == 0
    assert git(host, "tag", "-n1", "-l", "v1.0.0").split(None, 1)[1] == "release v1.0.0"


def test_release_json_reports_the_tag_and_the_gate(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    code, out, _ = cli_run(host, "release", "--tag", "v1.0.0", "--json")
    document = json.loads(out)
    assert code == 0 and document["command"] == "release" and document["tagged"] is True and document["tag"] == "v1.0.0"
    assert document["status"] == "WARN" and document["error_count"] == 0 and len(document["listed"]) == 28
    assert document["commit"] == git(host, "rev-parse", "HEAD")


def test_release_path_flags_before_the_tag_flag_are_the_same_command(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    code, out = run_cli("release", "--repo-root", str(Path(__file__).parents[2]), "--spec-root", str(host / "spec"), "--git-root", str(host), "--tag", "v1.0.0")
    assert code == 0 and _tags(host) == ["v1.0.0"], out


def test_release_without_a_tag_is_a_usage_error(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    before = snapshot(host)
    code, out, err = cli_run(host, "release")
    assert code == 2 and "--tag is required" in out + err and snapshot(host) == before
    assert cli_run(host, "release", "--message", "m")[0] == 2


@pytest.mark.parametrize("dirty", ["modified", "staged", "untracked"])
def test_release_refuses_dirty_tree_E910(tmp_path: Path, dirty: str) -> None:
    host = release_host(tmp_path)
    if dirty == "untracked":
        write(host / "notes.txt", "not committed\n")
    else:
        write(host / "src" / "routes" / "password-resets" / "confirm.ts", "export const changed = 1;\n")
        if dirty == "staged":
            git(host, "add", "-A")
    out = _refused(host, "E910", "release", "--tag", "v1.0.0")
    assert "not clean" in out and _tags(host) == []


def test_release_ignores_a_file_git_ignores(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    write(host / ".gitignore", "scratch/\n")
    commit_all(host, "ignore scratch")
    write(host / "scratch" / "a.txt", "ignored\n")
    assert cli_run(host, "release", "--tag", "v1.0.0")[0] == 0


def test_release_refuses_when_pattern_undeclared_E911(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    (host / "spec" / "common" / "host_declarations.json").unlink()
    commit_all(host, "no declarations")
    out = _refused(host, "E911", "release", "--tag", "v1.0.0")
    assert "release_tag_pattern" in out and _tags(host) == []


@pytest.mark.parametrize("name", ["banana", "v1.0", "release-1.0.0", "-v1.0.0"])
def test_release_refuses_tag_not_matching_pattern_or_existing_E912(tmp_path: Path, name: str) -> None:
    host = release_host(tmp_path)
    out = _refused(host, "E912", "release", f"--tag={name}")
    assert "does not match the release tag pattern" in out and _tags(host) == []


def test_release_refuses_a_tag_that_exists_E912(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    tag(host, "v1.0.0")
    advance(host)
    out = _refused(host, "E912", "release", "--tag", "v1.0.0")
    assert "exists already" in out and _tags(host) == ["v1.0.0"]


def test_release_does_not_tag_when_gate_fails(tmp_path: Path) -> None:
    host = release_host(tmp_path, LEFT_IN_SCOPE)
    out = _refused(host, "E914", "release", "--tag", "v1.0.0")
    assert "not tagged" in out and LEFT_IN_SCOPE in out and _tags(host) == []


def test_release_json_of_a_failed_gate_lists_the_errors_and_exits_1(tmp_path: Path) -> None:
    host = release_host(tmp_path, LEFT_IN_SCOPE)
    code, out, _ = cli_run(host, "release", "--tag", "v1.0.0", "--json")
    document = json.loads(out)
    assert code == 1 and document["tagged"] is False and document["status"] == "FAIL"
    assert "E914" in {error["code"] for error in document["errors"]} and _tags(host) == []


def test_release_does_not_push(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(host, "remote", "add", "origin", str(remote))
    git(host, "push", "-q", "origin", "main")
    sent: list[list[str]] = []
    real = gitview.run_git
    with patch.object(gitview, "run_git", side_effect=lambda root, args, **kw: (sent.append(list(args)), real(root, args, **kw))[1]):
        assert cli_run(host, "release", "--tag", "v1.0.0")[0] == 0
    assert _tags(host) == ["v1.0.0"] and git(host, "ls-remote", "--tags", "origin") == ""
    assert not [args for args in sent if args[0] in {"push", "commit", "fetch"}]


def test_release_without_a_git_identity_is_refused_and_writes_nothing(tmp_path: Path, no_identity: None, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in IDENTITY:
        monkeypatch.delenv(name, raising=False)
    host = release_host(tmp_path)
    before = snapshot(host)
    code, out, err = cli_run(host, "release", "--tag", "v1.0.0")
    assert code == 1 and "E708" in out + err and _tags(host) == [] and snapshot(host) == before


# --- the next-release check on a second cut ---------------------------------------------------------------------------------


def test_second_release_waits_for_the_first_to_be_verified_or_waived(tmp_path: Path, toolkit_1_2_0: None) -> None:
    host = at_deploy_host(tmp_path)
    assert cli_run(host, "release", "--tag", "v1.0.0")[0] == 0
    advance(host)
    out = _refused(host, "E920", "release", "--tag", "v1.1.0")
    assert f"{DEPLOY_ITEM}/{DEPLOY_ACTION} has no done record for staging" in out and "specdev release rollback v1.0.0" in out
    for env in ("staging", "prod"):
        assert cli_run(host, "plan", "record", "--at-deploy", f"{DEPLOY_ITEM}/{DEPLOY_ACTION}", "--env", env, "--tag", "v1.0.0")[0] == 0
    _refused(host, "E910", "release", "--tag", "v1.1.0")  # the deploy records are not committed yet
    commit(host, "deploy records")
    assert cli_run(host, "release", "--tag", "v1.1.0")[0] == 0 and _tags(host) == ["v1.0.0", "v1.1.0"]


def test_second_release_goes_through_after_a_rollback_record(tmp_path: Path, toolkit_1_2_0: None) -> None:
    host = at_deploy_host(tmp_path)
    assert cli_run(host, "release", "--tag", "v1.0.0")[0] == 0
    advance(host)
    _refused(host, "E920", "release", "--tag", "v1.1.0")
    assert cli_run(host, "release", "rollback", "v1.0.0", "--reason", "v1.0.0 never reached production")[0] == 0
    commit(host, "rollback record")
    assert cli_run(host, "release", "--tag", "v1.1.0")[0] == 0 and _tags(host) == ["v1.0.0", "v1.1.0"]


# --- release rollback -------------------------------------------------------------------------------------------------------


def test_rollback_writes_the_record_and_nothing_else(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    tag(host, "v1.0.0")
    before = snapshot(host)
    code, out, _ = cli_run(host, "release", "rollback", "v1.0.0", "--reason", "rolled back before production")
    record = host / "spec" / "extras" / "releases" / "rollback-v1.0.0.json"
    assert code == 0 and "not committed" in out and json.loads(record.read_text())["reason"] == "rolled back before production"
    after = snapshot(host)
    assert {key for key in after["files"] if key not in before["files"]} == {"spec/extras/releases/rollback-v1.0.0.json"}
    assert after["refs"] == before["refs"] and after["head"] == before["head"]


@pytest.mark.parametrize(("argv", "code"), [
    (["rollback", "v9.9.9", "--reason", "x"], "E925"),
    (["rollback", "v1.0.0", "--reason", "  "], "E926"),
])
def test_rollback_refusals_write_nothing(tmp_path: Path, argv: list[str], code: str) -> None:
    host = release_host(tmp_path)
    tag(host, "v1.0.0")
    _refused(host, code, "release", *argv)


def test_rollback_twice_is_E927_and_json_names_the_file(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    tag(host, "v1.0.0")
    code, out, _ = cli_run(host, "release", "rollback", "v1.0.0", "--reason", "first", "--json")
    assert code == 0 and json.loads(out)["file"].endswith("rollback-v1.0.0.json")
    _refused(host, "E927", "release", "rollback", "v1.0.0", "--reason", "second")


def test_rollback_needs_a_reason(tmp_path: Path) -> None:
    host = release_host(tmp_path)
    tag(host, "v1.0.0")
    assert cli_run(host, "release", "rollback", "v1.0.0")[0] == 2
