"""``specdev align apply --auto`` and a work tree with uncommitted changes (WI-M10-01c, E880, P18).

Run as a subprocess on a ``git clone`` of the mini host, with the helpers of ``test_migration_no_git_writes.py``.  The
assertions do not depend on which scripts are registered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from integration.test_migration_no_git_writes import (
    HOST_KINDS,
    SPEC,
    Cli,
    changed_paths,
    clone_host,
    commit_all,
    git_state,
    json_of,
    make_cli,
    stamp_of,
)
from unit.migration.test_runner_core import tree_digest

CAPTURE = f"{SPEC}/extras/migration/capture.json"
DIRTY_FILE = f"{SPEC}/00_charter.json"


@pytest.fixture
def cli(tmp_path) -> Cli:
    return make_cli(tmp_path)


@pytest.fixture(params=HOST_KINDS)
def host(request, tmp_path) -> Path:
    return clone_host(tmp_path, request.param)


def make_dirty(host: Path, rel: str = DIRTY_FILE) -> bytes:
    """Append a newline to the tracked file *rel* (still valid JSON) and return the new bytes."""
    path = host / rel
    path.write_bytes(path.read_bytes() + b"\n")
    return path.read_bytes()


def test_dirty_spec_gives_e880(cli, host):
    make_dirty(host)
    before, state = tree_digest(host), git_state(host)
    done = cli.apply(host)
    assert done.returncode == 1
    assert done.stdout == ""
    assert "E880" in done.stderr
    assert f"{host / SPEC} has uncommitted changes; commit them first" in done.stderr
    assert "git checkout -- spec" in done.stderr and "or pass --allow-dirty" in done.stderr
    assert tree_digest(host) == before and git_state(host) == state
    assert not (host / CAPTURE).exists()


def test_dirty_spec_gives_e880_in_json_form(cli, host):
    make_dirty(host)
    done = cli.apply(host, "--json")
    payload = json_of(done)
    assert done.returncode == 1 and payload["status"] == "refused" and payload["dry_run"] is False
    assert [error["code"] for error in payload["errors"]] == ["E880"]
    assert "uncommitted changes" in payload["errors"][0]["message"]


def test_dirty_new_file_under_spec_is_refused_too(cli, host):
    (host / SPEC / "extras" / "scratch-note.txt").write_text("not committed\n", encoding="utf-8")
    done = cli.apply(host)
    assert done.returncode == 1 and "E880" in done.stderr
    assert not (host / CAPTURE).exists()


def test_allow_dirty_proceeds(cli, host):
    """The uncommitted edit is a VALUE (scripts rewrite this file, so its bytes change): the run keeps it."""
    path = host / DIRTY_FILE
    marker = "an uncommitted sentence"
    path.write_text(path.read_text(encoding="utf-8").replace('"problem_statement": "', f'"problem_statement": "{marker}. ', 1), encoding="utf-8")
    assert marker in path.read_text(encoding="utf-8")
    done = cli.apply(host, "--allow-dirty")
    assert done.returncode == 0, done.stderr
    assert "E880" not in done.stderr
    assert marker in path.read_text(encoding="utf-8"), "the uncommitted change was lost"
    assert stamp_of(host)["toolkit_version"] == "1.2.0"
    assert (host / CAPTURE).is_file()
    assert all(path.startswith(f"{SPEC}/") for path in changed_paths(host))


def test_dry_run_on_a_dirty_spec_is_allowed_and_writes_nothing(cli, host):
    """P18: a dry run shows what the run would do to the tree as it is."""
    make_dirty(host)
    before, state = tree_digest(host), git_state(host)
    done = cli.apply(host, "--dry-run")
    assert done.returncode == 0, done.stderr
    assert "dry run, nothing written" in done.stdout and "E880" not in done.stderr
    assert tree_digest(host) == before and git_state(host) == state
    assert not list(cli.scratch.iterdir())


def test_a_dirty_file_outside_spec_does_not_refuse(cli, host):
    (host / "README.md").write_text("an uncommitted note\n", encoding="utf-8")
    tracked = host / "schemas" / "catalog.json"
    tracked.write_bytes(tracked.read_bytes() + b"\n")
    outside = {rel: digest for rel, digest in tree_digest(host).items() if not rel.startswith(f"{SPEC}/")}
    done = cli.apply(host)
    assert done.returncode == 0, done.stderr
    assert stamp_of(host)["toolkit_version"] == "1.2.0"
    assert {rel: digest for rel, digest in tree_digest(host).items() if not rel.startswith(f"{SPEC}/")} == outside


def test_a_present_capture_file_makes_the_run_a_resume_that_ignores_dirty_changes(cli, host):
    """Resume rule: with ``capture.json`` present (a run that stopped, or one not yet committed) a dirty spec is not refused.

    The runner runs ``detect`` on every script again and applies only those with work left: the second run adds nothing.
    """
    assert cli.apply(host).returncode == 0
    assert (host / CAPTURE).is_file()
    after_first = tree_digest(host)
    dirty = make_dirty(host)
    again = cli.apply(host)
    assert again.returncode == 0, again.stderr
    assert "E880" not in again.stderr
    assert (host / DIRTY_FILE).read_bytes() == dirty
    assert {rel: d for rel, d in tree_digest(host).items() if rel != DIRTY_FILE} == {rel: d for rel, d in after_first.items() if rel != DIRTY_FILE}
    assert len(stamp_of(host)["migration_history"]) == 1


def test_an_in_progress_stamp_alone_makes_the_run_a_resume(cli, host):
    """Resume rule, second marker: ``migration_status: in_progress`` in the stamp, without a capture file, is a resume too."""
    assert cli.apply(host).returncode == 0
    assert stamp_of(host)["migration_status"] == "in_progress"
    (host / CAPTURE).unlink()
    (host / SPEC / "extras" / "migration" / "worklist.json").unlink(missing_ok=True)
    commit_all(host, "migrated, capture files removed")
    make_dirty(host)
    done = cli.apply(host)
    assert "E880" not in done.stderr, done.stderr
    assert done.returncode == 0, done.stderr


def test_after_a_refusal_committing_the_spec_lets_the_run_proceed(cli, host):
    make_dirty(host)
    assert cli.apply(host).returncode == 1
    commit_all(host, "commit the spec first")
    done = cli.apply(host)
    assert done.returncode == 0, done.stderr
    assert stamp_of(host)["toolkit_version"] == "1.2.0"
