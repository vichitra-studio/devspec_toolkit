"""``specdev align apply --auto --dry-run`` prints what the real run does, the same every time (WI-M10-01c).

Run as a subprocess on a ``git clone`` of the mini host, with the helpers of ``test_migration_no_git_writes.py``.  The one
clock value of the run, the dates of the stamp hunk, is printed masked (``<timestamp>``) by the runner; ``masked`` here
masks the real ``git diff`` the same way, with the runner's own function.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from integration.test_migration_no_git_writes import (
    HOST_KINDS,
    SPEC,
    STAMP,
    Cli,
    clone_host,
    commit_all,
    json_of,
    make_cli,
)
from specdev_tools.migration.report import mask_stamp_timestamps
from unit.migration.test_runner_core import git, tree_digest

ISO_DATE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d")
SCRIPT_LINE = re.compile(r"^  p(\d+) (\S+): (?:nothing to do|(\d+) edit\(s\), (\d+) worklist item\(s\))$")
TOTAL_LINE = re.compile(r"^total: (\d+) edit\(s\), (\d+) worklist item\(s\), (\d+) file\(s\) changed$")


@pytest.fixture
def cli(tmp_path) -> Cli:
    return make_cli(tmp_path)


@pytest.fixture(params=HOST_KINDS)
def host(request, tmp_path) -> Path:
    return clone_host(tmp_path, request.param)


def hunks_by_file(diff: str, strip: str = "") -> dict[str, list[str]]:
    """``{path: [the @@ and the +, - and context lines of its diff]}`` of a unified diff (trailing blank lines dropped); *strip* is cut off the paths."""
    files: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].removeprefix("b/").removeprefix(strip)
            current = files.setdefault(path, [])
        elif line.startswith(("--- ", "diff --git", "index ", "new file mode", "deleted file mode", "similarity", "rename ")):
            continue
        elif current is not None:
            current.append(line)
    return {path: "\n".join(body).rstrip("\n").split("\n") for path, body in files.items()}


def script_lines(text: str) -> list[tuple[str, int, int]]:
    """``[(script id, edits, worklist items)]`` of the ``  pN <id>: ...`` lines of the text form, in order."""
    out = []
    for line in text.splitlines():
        found = SCRIPT_LINE.match(line)
        if found:
            out.append((found.group(2), int(found.group(3) or 0), int(found.group(4) or 0)))
    return out


def test_dry_run_output_identical_on_repeat(cli, host):
    first, second = cli.apply(host, "--dry-run"), cli.apply(host, "--dry-run")
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout and first.stderr == second.stderr
    assert first.stdout.strip(), "a dry run prints its diff"
    stamp_hunk = hunks_by_file(first.stdout)[STAMP]
    assert any("<timestamp>" in line for line in stamp_hunk), stamp_hunk
    assert not ISO_DATE.search(first.stdout.split("+++ b/specdev_version", 1)[1].split("\n--- ", 1)[0])


def test_dry_run_json_is_identical_on_repeat(cli, host):
    first, second = cli.apply(host, "--dry-run", "--json"), cli.apply(host, "--dry-run", "--json")
    assert first.stdout == second.stdout and json_of(first)["dry_run"] is True


def test_dry_run_then_real_run_gives_the_same_diff(cli, host):
    dry = cli.apply(host, "--dry-run")
    assert dry.returncode == 0, dry.stderr
    promised = hunks_by_file(dry.stdout)
    assert promised, "the dry run promised no change: the test would prove nothing"
    real = cli.apply(host)
    assert real.returncode == 0, real.stderr
    git(host, "add", "-A")  # the test's own index: puts the new files into `git diff`
    done = mask_stamp_timestamps(git(host, "diff", "--cached", "--no-color"))
    assert hunks_by_file(done, strip=f"{SPEC}/") == promised
    assert sorted(promised) == sorted(real_changed_files(host))


def real_changed_files(host: Path) -> list[str]:
    return [line.removeprefix(f"{SPEC}/") for line in git(host, "diff", "--cached", "--name-only").splitlines()]


def test_dry_run_then_real_run_then_dry_run_says_no_change(cli, host):
    assert cli.apply(host, "--dry-run").returncode == 0
    assert cli.apply(host).returncode == 0
    again = cli.apply(host, "--dry-run")
    assert again.returncode == 0 and again.stdout.rstrip().endswith("no change")


def test_second_real_run_after_commit_is_a_noop_that_says_so(cli, host):
    first = cli.apply(host)
    assert first.returncode == 0, first.stderr
    assert "review: git diff --stat spec" in first.stdout
    commit_all(host, "migrated")
    tree = tree_digest(host)
    second = cli.apply(host)
    assert second.returncode == 0, second.stderr
    lines = second.stdout.splitlines()
    scripts = [line for line in lines if SCRIPT_LINE.match(line)]
    assert scripts and all(line.endswith("nothing to do") for line in scripts), second.stdout
    assert any(TOTAL_LINE.match(line) and line.startswith("total: 0 edit(s), 0 worklist item(s), 0 file(s) changed") for line in lines)
    assert not any(line.startswith(("review:", "undo:")) for line in lines)
    assert tree_digest(host) == tree
    assert git(host, "status", "--porcelain") == ""
    payload = json_of(cli.apply(host, "--json"))
    assert payload["status"] == "ok" and set(payload["edits_by_script"].values()) == {0} and payload["worklist_items"] == 0


@pytest.mark.parametrize("flags", [("--dry-run",), ()], ids=["dry run", "real run"])
@pytest.mark.parametrize("kind", HOST_KINDS)
def test_json_form_names_the_same_scripts_and_counts_as_the_text_form(cli, tmp_path, kind, flags):
    """Two clones of the same host: one run prints the text form, the other the JSON form."""
    text_host, json_host = clone_host(tmp_path, kind), clone_host(tmp_path, kind)
    text, as_json = cli.apply(text_host, *flags), json_of(cli.apply(json_host, *flags, "--json"))
    assert text.returncode == 0, text.stderr
    assert as_json["status"] == "ok" and as_json["dry_run"] is bool(flags) and as_json["errors"] == []
    from_text = script_lines(text.stdout)
    assert [name for name, *_ in from_text] == list(as_json["edits_by_script"])
    assert {name: edits for name, edits, _ in from_text} == as_json["edits_by_script"]
    assert sum(worklist for *_, worklist in from_text) == as_json["worklist_items"]
    total = next(TOTAL_LINE.match(line) for line in text.stdout.splitlines() if TOTAL_LINE.match(line))
    assert (int(total.group(1)), int(total.group(2))) == (sum(as_json["edits_by_script"].values()), as_json["worklist_items"])
