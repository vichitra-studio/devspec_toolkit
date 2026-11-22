"""``specdev align triage`` and ``specdev align validate`` (WI-M10-12 items 1 and 2), and the one writer of the stamp.

The cases of the commands run in process through ``cli.main`` on a git copy of the mini host.  ``spec-check --merge`` is
stubbed (``stub_merge_check``) wherever a case is about what validate does with its answer; the end-to-end class runs
it for real on a temp toolkit root at 1.2.0 (the live toolkit says 1.1.1 until the release commit, P1).
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from specdev_tools import cli
from specdev_tools.core.errors import make_error
from specdev_tools.generation.schema_differ import KEEP_STATUS, stamp_specdev_version
from specdev_tools.migration import runner, triage
from specdev_tools.migration.registry import PHASE_IDS
from specdev_tools.migration.worklist import WORKLIST_FILE, make_item
from specdev_tools.core.changelog_parser import get_toolkit_version

from .test_runner_core import MINI_HOST, REAL_ROOT, git, make_host, make_script, make_toolkit

SPEC = "spec"
CAPTURE = "extras/migration/capture.json"
WORKLIST = "extras/migration/worklist.json"
LIVE_VERSION = get_toolkit_version(REAL_ROOT) or ""  # the version the live toolkit says


def specdev(*argv: str) -> tuple[int, str, str]:
    """Run ``specdev align ...`` in process; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with (
        patch("specdev_tools.cli.check_venv", return_value=None),
        patch.object(sys, "argv", ["specdev", "align", *argv]),
        redirect_stdout(out),
        redirect_stderr(err),
    ):
        try:
            cli.main()
        except SystemExit as exit_:
            code = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
    return code, out.getvalue(), err.getvalue()


def digest(host: Path) -> dict[str, str]:
    return {
        str(p.relative_to(host)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(host.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(host).parts
    }


def stamp_of(host: Path) -> dict:
    return yaml.safe_load((host / SPEC / "specdev_version").read_text(encoding="utf-8"))


def write_worklist(host: Path, *items) -> None:
    path = host / SPEC / WORKLIST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"$schema": "vc:infra:migration-worklist", "items": [i.to_json() for i in items]}, indent=4) + "\n", encoding="utf-8")


def in_progress_stamp(host: Path, **extra) -> None:
    data = stamp_of(host)
    data.update(migration_status="in_progress", **extra)
    (host / SPEC / "specdev_version").write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def commit(host: Path, message: str = "state") -> None:
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", message)


def item(step: str, kind: str, about: str, *, audience="agent", blocking=True):
    return make_item(step, kind, about, audience=audience, blocking=blocking, evidence=f"evidence of {about}", proposal=f"proposal for {about}")


@pytest.fixture
def host(tmp_path):
    """The mini host at the live toolkit's version, in a migration (``in_progress``), with an empty worklist file, committed."""
    root = make_host(tmp_path, version=LIVE_VERSION)
    in_progress_stamp(root)
    write_worklist(root)
    commit(root)
    return root


def stub_merge_check(errors=()):
    """Replace the whole ``spec-check --merge`` run of validate by an answer; the returned patch records the calls."""
    return patch.object(triage, "run_spec_check", return_value=list(errors))


# ---------------------------------------------------------------------------
# align triage
# ---------------------------------------------------------------------------


MIXED = (
    item("16a", "spec-ref-realises", "B-ITEM", audience="agent", blocking=True),
    item("04", "scope-reason", "a-node", audience="agent", blocking=False),
    item("09", "schedules", "milestone-x", audience="agent", blocking=True),
    item("00", "scope-reason", "scope-y", audience="agent", blocking=True),
    item("12", "host-declaration", "setup_command", audience="operator", blocking=False),
    item("16", "duplicate-promoted-item", "amb-z", audience="operator", blocking=True),
)


def test_triage_lists_the_worklist_items_sorted_by_step(host):
    write_worklist(host, *MIXED)
    code, out, err = specdev("triage", str(host / SPEC))
    assert code == 0, err
    ids = [line.split()[-1] for line in out.splitlines() if line.strip().startswith(("BLOCKING", "optional"))]
    # operator first; blocking before optional; within one group by step, then kind, then id
    assert ids == [
        "wl-16-duplicate-promoted-item-amb-z",
        "wl-12-host-declaration-setup-command",
        "wl-00-scope-reason-scope-y",
        "wl-09-schedules-milestone-x",
        "wl-16a-spec-ref-realises-b-item",
        "wl-04-scope-reason-a-node",
    ]
    assert "6 open item(s), 4 blocking; 0 resolved" in out
    assert "operator (2 open):" in out and "agent (4 open):" in out
    assert "evidence: evidence of scope-y" in out and "proposal: proposal for scope-y" in out
    assert "--resolve <id> --note" in out


def test_triage_filters_by_step_and_audience(host):
    write_worklist(host, *MIXED)
    code, out, _ = specdev("triage", str(host / SPEC), "--step", "4")
    assert code == 0 and "wl-04-scope-reason-a-node" in out and "wl-09" not in out and "[step 4]" in out
    code, out, _ = specdev("triage", str(host / SPEC), "--step", "16")
    assert "wl-16-duplicate" in out and "wl-16a" not in out
    code, out, _ = specdev("triage", str(host / SPEC), "--audience", "operator")
    assert "operator (2 open)" in out and "agent (" not in out
    code, out, _ = specdev("triage", str(host / SPEC), "--audience", "operator", "--step", "12")
    assert "wl-12-host-declaration-setup-command" in out and "wl-16-" not in out
    code, _, err = specdev("triage", str(host / SPEC), "--audience", "nobody")
    assert code == 2 and "invalid choice" in err


def test_triage_json_is_the_worklist_items(host):
    write_worklist(host, *MIXED)
    code, out, _ = specdev("triage", str(host / SPEC), "--json")
    assert code == 0
    data = json.loads(out)
    assert data["command"] == "align" and data["action"] == "triage" and data["status"] == "PASS"
    assert (data["open"], data["blocking_open"]) == (6, 4)
    assert data["items"] == [i.to_json() for i in MIXED]  # the items as the file holds them (it keeps its own order), resolved ones too
    code, out, _ = specdev("triage", str(host / SPEC), "--json", "--audience", "operator")
    assert [i["id"] for i in json.loads(out)["items"]] == ["wl-12-host-declaration-setup-command", "wl-16-duplicate-promoted-item-amb-z"]


def test_triage_legacy_prints_the_old_values_by_git_show_and_writes_nothing(host):
    old = (host / SPEC / "04_fr_list.json").read_text(encoding="utf-8")
    head = git(host, "rev-parse", "HEAD").strip()
    capture = {"source": {"commit": head, "spec_dir": SPEC, "show_form": f"git show {head}:{SPEC}/<file>",
                          "file_hashes": {"00_charter.json": "x", "04_fr_list.json": "x", "13a_completeness_assessment.json": "x"}}}
    (host / SPEC / CAPTURE).write_text(json.dumps(capture), encoding="utf-8")
    (host / SPEC / "04_fr_list.json").write_text('{"migrated": true}\n', encoding="utf-8")
    (host / SPEC / "13a_completeness_assessment.json").unlink()
    commit(host, "migrated")
    before_files, before_status = digest(host), git(host, "status", "--porcelain")
    code, out, err = specdev("triage", str(host / SPEC), "--legacy", "4")
    assert code == 0, err
    assert f"=== 04_fr_list.json at {head[:12]}" in out and old.strip() in out and "migrated" not in out
    assert "00_charter" not in out
    code, out, err = specdev("triage", str(host / SPEC), "--legacy", "13a")  # a file the migration deleted is still shown
    assert code == 0 and "13a_completeness_assessment.json" in out
    code, out, err = specdev("triage", str(host / SPEC), "--legacy", "07")
    assert code == 1 and "lists no file of step 07" in err
    assert digest(host) == before_files and git(host, "status", "--porcelain") == before_status


def test_triage_legacy_without_a_capture_says_what_writes_it(host):
    code, out, err = specdev("triage", str(host / SPEC), "--legacy", "4")
    assert code == 1 and "there is no capture" in err and "align apply --auto" in err


def test_triage_resolve_sets_resolved_true_with_the_note_and_edits_only_worklist_json(host):
    first, second = item("00", "scope-reason", "scope-y"), item("09", "schedules", "milestone-x")
    write_worklist(host, first, second)
    commit(host)
    before = digest(host)
    code, out, err = specdev("triage", str(host / SPEC), "--resolve", first.id, "--note", "out of scope until the charter says otherwise")
    assert code == 0, err
    assert f"{first.id}: resolved" in out
    changed = {rel for rel, value in digest(host).items() if before.get(rel) != value}
    assert changed == {f"{SPEC}/{WORKLIST}"}
    items = json.loads((host / SPEC / WORKLIST).read_text(encoding="utf-8"))["items"]
    closed = next(i for i in items if i["id"] == first.id)
    assert closed["resolved"] is True and closed["note"] == "out of scope until the charter says otherwise"
    assert next(i for i in items if i["id"] == second.id) == second.to_json()
    assert git(host, "diff", "--numstat").split() == ["2", "2", f"{SPEC}/{WORKLIST}"]  # the file's own style is kept: two lines
    code, out, _ = specdev("triage", str(host / SPEC), "--resolve", first.id, "--note", "again")  # a closed item keeps its note
    assert code == 0 and "already resolved" in out
    assert json.loads((host / SPEC / WORKLIST).read_text(encoding="utf-8"))["items"][0]["note"] == "out of scope until the charter says otherwise"


def test_triage_resolve_refuses_an_unknown_id_and_usage_mistakes(host):
    write_worklist(host, item("00", "scope-reason", "scope-y"))
    before = digest(host)
    code, _, err = specdev("triage", str(host / SPEC), "--resolve", "wl-nothing", "--note", "x")
    assert code == 1 and "no worklist item has the id 'wl-nothing'" in err and "wl-00-scope-reason-scope-y" in err
    assert specdev("triage", str(host / SPEC), "--resolve", "wl-00-scope-reason-scope-y")[0] == 2  # no --note
    assert specdev("triage", str(host / SPEC), "--note", "x")[0] == 2  # no --resolve
    assert specdev("triage", str(host / SPEC), "--resolve", "wl-x", "--note", "x", "--step", "00")[0] == 2
    code, _, err = specdev("triage", str(host / SPEC), "--resolve", "wl-00-scope-reason-scope-y", "--note", "  ")
    assert code == 1 and "pass --note with text" in err
    assert digest(host) == before


def test_triage_has_no_only_and_no_report_flag():
    for flag in ("--only", "--report"):
        assert specdev("triage", "spec", flag, "x")[0] == 2


# ---------------------------------------------------------------------------
# align validate
# ---------------------------------------------------------------------------


def test_validate_runs_merge_mode_and_fails_on_a_merge_mode_error(host):
    write_worklist(host, item("04", "scope-reason", "a-node", blocking=False))
    commit(host)
    before = digest(host)
    finding = make_error("E631", "open item amb-x in a plan")
    with stub_merge_check([finding]) as stub:
        code, out, err = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT), "--base-ref", "HEAD")
    assert code == 1
    kwargs = stub.call_args.kwargs
    assert kwargs["merge"] is True and kwargs["base_ref"] == "HEAD"
    assert kwargs["git_root"] == str(host) and kwargs["spec_root"] == str(host / SPEC)
    assert "E631 open item amb-x in a plan" in err and "reports 1 error(s); the migration is not finished and nothing was changed" in err
    assert digest(host) == before and stamp_of(host)["migration_status"] == "in_progress"


def test_validate_a_warning_alone_does_not_fail(host):
    with stub_merge_check([make_error("W633", "a warning")]):
        code, out, err = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT))
    assert code == 0, err
    assert "spec-check --merge: no error (1 warning(s))" in out


def test_validate_an_open_blocking_item_is_information_not_a_failure(host):
    write_worklist(host, *MIXED)
    commit(host)
    with stub_merge_check() as stub:
        code, out, err = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT))
    assert code == 0, err
    assert stub.called  # merge mode is the gate: it ran although 4 blocking items are open
    assert "worklist: 6 item(s) not resolved, 4 of them marked blocking (information, not a failure)." in out
    assert (host / SPEC / WORKLIST).is_file() and "migration_status" not in stamp_of(host)


def test_validate_keeps_the_worklist_and_prints_the_unresolved_count_while_an_item_remains(host):
    write_worklist(host, item("04", "scope-reason", "a-node", blocking=False), item("12", "host-declaration", "setup_command", audience="operator", blocking=False))
    (host / SPEC / CAPTURE).write_text("{}\n", encoding="utf-8")
    commit(host)
    with stub_merge_check():
        code, out, err = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT))
    assert code == 0, err
    assert "worklist: 2 item(s) not resolved, 0 of them marked blocking" in out
    assert "2 file(s) of spec/extras/migration/ kept: 2 item(s) are not resolved" in out
    assert (host / SPEC / WORKLIST).is_file() and (host / SPEC / CAPTURE).is_file()
    assert "migration_status" not in stamp_of(host)  # the stamp is finished: only merge mode and blocking items fail


def test_validate_deletes_the_worklist_after_the_last_resolve(host):
    only = item("04", "scope-reason", "a-node")
    write_worklist(host, only)
    (host / SPEC / CAPTURE).write_text("{}\n", encoding="utf-8")
    commit(host)
    with stub_merge_check():
        code, out, _ = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT), "--keep-worklist")
        assert code == 0 and "1 item(s) not resolved" in out  # open: kept (the stamp is cleared; the test restores it below)
        in_progress_stamp(host)
        assert specdev("triage", str(host / SPEC), "--resolve", only.id, "--note", "done")[0] == 0
        code, out, err = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT))
    assert code == 0, err
    assert "worklist: every item is resolved." in out
    assert "deleted: spec/extras/migration/capture.json, spec/extras/migration/worklist.json" in out
    assert not (host / SPEC / "extras" / "migration").exists()  # the folder goes with its files
    assert "migration_status" not in stamp_of(host)


def test_validate_keep_worklist_keeps_it_regardless(host):
    (host / SPEC / CAPTURE).write_text("{}\n", encoding="utf-8")
    commit(host)
    with stub_merge_check():
        code, out, err = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT), "--keep-worklist")
    assert code == 0, err
    assert "spec/extras/migration/ kept (--keep-worklist)" in out
    assert (host / SPEC / WORKLIST).is_file() and (host / SPEC / CAPTURE).is_file()
    assert "migration_status" not in stamp_of(host)


def test_validate_clears_migration_status(host):
    in_progress_stamp(host, x_note_of_a_person="kept", last_migration="2026-01-01T00:00:00.000000Z", migration_history=[{"from": "1.0.0", "to": LIVE_VERSION, "date": "d", "notes": "n"}])
    commit(host)
    before = stamp_of(host)
    with stub_merge_check():
        code, out, err = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT))
    assert code == 0, err
    assert "stamp: migration_status cleared, last_migration refreshed" in out and "Migration finished" in out
    after = stamp_of(host)
    assert "migration_status" not in after
    assert after["last_migration"] != before["last_migration"]
    assert after["x_note_of_a_person"] == "kept" and after["created_at"] == before["created_at"] and after["toolkit_version"] == before["toolkit_version"]
    assert after["migration_history"] == before["migration_history"]  # validate appends no history entry
    with stub_merge_check():  # a second validate has no status to clear and leaves the stamp alone
        digest_before = digest(host)
        code, out, _ = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT))
    assert code == 0 and "was not rewritten" in out and digest(host) == digest_before


def test_validate_refuses_a_spec_that_was_not_migrated(tmp_path):
    root = make_host(tmp_path, version="1.0.0")
    before = digest(root)
    with stub_merge_check() as stub:
        code, out, err = specdev("validate", str(root / SPEC), "--repo-root", str(REAL_ROOT))
    assert code == 1 and not stub.called
    assert f"the spec records toolkit v1.0.0 and this toolkit is v{LIVE_VERSION}: the migration has not been run" in err
    assert digest(root) == before


def test_validate_refuses_when_no_base_resolves_and_says_so(host):
    from specdev_tools.core.errors import FindingError

    with patch.object(triage, "run_spec_check", side_effect=FindingError(make_error("E900", "no base"))):
        code, out, err = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT))
    assert code == 1 and "align validate: refused: E900 no base" in err and stamp_of(host)["migration_status"] == "in_progress"


def test_validate_json_envelope(host):
    write_worklist(host, item("04", "scope-reason", "a-node"))
    commit(host)
    with stub_merge_check([make_error("E631", "x")]):
        code, out, _ = specdev("validate", str(host / SPEC), "--repo-root", str(REAL_ROOT), "--json")
    data = json.loads(out)
    assert code == 1 and data["status"] == "FAIL" and data["blocking"] == 1 and data["unresolved"] == 1


# ---------------------------------------------------------------------------
# History across run, resume and validate; the one writer of the stamp
# ---------------------------------------------------------------------------


def test_validate_leaves_exactly_one_1_1_1_to_1_2_0_history_entry_after_run_resume_and_validate(tmp_path):
    toolkit = make_toolkit(tmp_path, "1.2.0")
    root = make_host(tmp_path, version="1.1.1")
    mark = make_script("p2_mark", PHASE_IDS, touches=("extras",))
    argv = [str(root / SPEC), "--auto", "--repo-root", str(toolkit)]

    def apply() -> int:
        with patch.object(runner, "discover_scripts", return_value=[mark]):
            return specdev("apply", *argv)[0]

    assert apply() == 0
    entries = stamp_of(root)["migration_history"]
    assert [(e["from"], e["to"]) for e in entries] == [("1.1.1", "1.2.0")] and stamp_of(root)["migration_status"] == "in_progress"
    assert apply() == 0  # the resume: the stamp says in_progress, detect finds nothing, nothing is written
    assert len(stamp_of(root)["migration_history"]) == 1
    with stub_merge_check():
        code, out, err = specdev("validate", str(root / SPEC), "--repo-root", str(toolkit))
    assert code == 0, err
    after = stamp_of(root)
    assert [(e["from"], e["to"]) for e in after["migration_history"]] == [("1.1.1", "1.2.0")]
    assert "migration_status" not in after and after["toolkit_version"] == "1.2.0"


def test_stamp_writer_keeps_unknown_keys_and_changes_only_the_keys_it_is_told_to(tmp_path):
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "specdev_version").write_text(
        yaml.dump({"toolkit_version": "1.1.1", "created_at": "c", "last_migration": "l", "migration_history": [], "x_key": {"a": 1}, "migration_status": "in_progress"}),
        encoding="utf-8",
    )
    assert stamp_specdev_version(spec, "1.1.1", is_migration=False) is None  # a plain bump keeps even migration_status
    data = yaml.safe_load((spec / "specdev_version").read_text(encoding="utf-8"))
    assert data["x_key"] == {"a": 1} and data["migration_status"] == "in_progress" and data["last_migration"] == "l"
    assert stamp_specdev_version(spec, "1.1.1", is_migration=True, migration_status=None, now=lambda: "T") is None
    data = yaml.safe_load((spec / "specdev_version").read_text(encoding="utf-8"))
    assert "migration_status" not in data and data["x_key"] == {"a": 1} and data["last_migration"] == "T" and data["migration_history"] == []
    assert KEEP_STATUS is not None


def test_the_runner_and_update_and_validate_all_write_the_stamp_through_the_one_writer(tmp_path):
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "specdev_version").write_text(yaml.dump({"toolkit_version": "1.1.1", "created_at": "c", "x_key": 7}), encoding="utf-8")
    calls = []
    real = stamp_specdev_version

    def spy(*args, **kwargs):
        calls.append((args[1], args[2] if len(args) > 2 else kwargs.get("is_migration"), kwargs.get("migration_status", KEEP_STATUS)))
        return real(*args, **kwargs)

    with patch.object(runner, "stamp_specdev_version", spy), patch.object(triage, "stamp_specdev_version", spy):
        assert runner.stamp_migrated(str(spec), "1.2.0", ["p1_a", "p2_b"], lambda: "NOW") is True
        assert runner.stamp_migrated(str(spec), "1.2.0", ["p1_a"], lambda: "LATER") is False  # already at the target: no write, no entry
        triage._finish(str(spec), "1.2.0", yaml.safe_load((spec / "specdev_version").read_text(encoding="utf-8")), triage.ValidateReport(), False)
    assert calls == [("1.2.0", True, "in_progress"), ("1.2.0", True, None)]
    data = yaml.safe_load((spec / "specdev_version").read_text(encoding="utf-8"))
    assert data["x_key"] == 7 and "migration_status" not in data
    assert data["migration_history"] == [{"from": "1.1.1", "to": "1.2.0", "date": "NOW", "notes": "mechanical migration (runner); scripts: p1_a, p2_b"}]


# ---------------------------------------------------------------------------
# The whole procedure on the mini host, through the commands
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def toolkit_1_2_0(tmp_path_factory):
    """A copy of the toolkit's tools, schemas, canon and changelog that says 1.2.0 (so ``spec-check`` runs for real)."""
    root = tmp_path_factory.mktemp("toolkit_1_2_0")
    for name in ("tools", "schema", "canon", "changelog"):
        shutil.copytree(REAL_ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))
    pyproject = root / "tools" / "pyproject.toml"
    pyproject.write_text(pyproject.read_text(encoding="utf-8").replace(f'version = "{LIVE_VERSION}"', 'version = "1.2.0"', 1), encoding="utf-8")
    (root / "changelog" / "v1.2.0.yaml").write_text("version: 1.2.0\nbreaking: true\nchanges: []\n", encoding="utf-8")
    return root


class TestMiniHostEndToEnd:
    """update -> align apply --auto -> align triage -> align validate (refuses) -> resolve the blocking items -> align validate."""

    @pytest.fixture
    def migrated(self, tmp_path, toolkit_1_2_0):
        root = make_host(tmp_path, version="1.1.1")
        code, out, err = specdev("apply", str(root / SPEC), "--auto", "--repo-root", str(toolkit_1_2_0))
        assert code == 0, err
        commit(root, "migrate")
        return root

    def blocking_ids(self, root: Path, toolkit: Path) -> list[str]:
        data = json.loads(specdev("triage", str(root / SPEC), "--repo-root", str(toolkit), "--json")[1])
        return [i["id"] for i in data["items"] if i["blocking"] and not i["resolved"]]

    def test_the_mechanical_pass_leaves_an_in_progress_stamp_and_a_worklist_that_triage_lists(self, migrated, toolkit_1_2_0):
        assert stamp_of(migrated)["migration_status"] == "in_progress"
        code, out, err = specdev("triage", str(migrated / SPEC), "--repo-root", str(toolkit_1_2_0))
        assert code == 0, err
        assert out.startswith("Worklist: ") and "open item(s)" in out and "BLOCKING  wl-" in out
        assert self.blocking_ids(migrated, toolkit_1_2_0)

    def test_validate_goes_straight_to_merge_mode_and_with_the_checks_stubbed_finishes_the_stamp(self, migrated, toolkit_1_2_0):
        ids = self.blocking_ids(migrated, toolkit_1_2_0)
        assert ids  # open blocking items do not stop validate
        # the scripts that exist so far leave the tree with errors that later scripts clear: the checks are stubbed
        # here and the state they leave is pinned in the last test; the passing end is in test_migration_then_merge_mode.py
        with stub_merge_check():
            code, out, err = specdev("validate", str(migrated / SPEC), "--repo-root", str(toolkit_1_2_0))
        assert code == 0, err
        stamp = stamp_of(migrated)
        assert "migration_status" not in stamp and [(e["from"], e["to"]) for e in stamp["migration_history"]] == [("1.1.1", "1.2.0")]
        assert (migrated / SPEC / WORKLIST).is_file()  # items are open: kept, and the counts printed
        assert f"{len(ids)} of them marked blocking" in out

    def test_validate_with_the_checks_unstubbed_refuses_a_host_whose_judgement_pass_is_not_done(self, migrated, toolkit_1_2_0):
        """The control of the passing end: the passing end (the same host after the scripted judgement pass, ``validate`` exit 0, the
        worklist and the capture gone, the stamp finished) is ``tests/integration/test_migration_then_merge_mode.py``, which runs the
        pass once per session.  Here the mechanical stage alone leaves errors only a person can clear, so validate says what is left
        and changes nothing."""
        before = digest(migrated)
        code, out, err = specdev("validate", str(migrated / SPEC), "--repo-root", str(toolkit_1_2_0))
        assert code == 1
        assert "spec-check --merge reports" in err and "the migration is not finished and nothing was changed" in err
        assert digest(migrated) == before and stamp_of(migrated)["migration_status"] == "in_progress"
