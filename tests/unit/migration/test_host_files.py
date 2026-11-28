"""``p7_host_files`` (WI-M10-11): what the migration reports about a host's hooks, workflows and declarations.

The host files are INVENTED (``tests/fixtures/migration/host_files/`` overlaid on a git copy of the mini host).  The script
reads the host's files and writes worklist items under ``spec/extras/migration/``; no host file outside ``spec/`` is ever
written (ruling P4: there is no ``--rewrite-host-commands``).
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import sys
from unittest.mock import patch
from pathlib import Path

import pytest

from specdev_tools import cli
from specdev_tools.core.host_declarations import HOST_DECLARATIONS_FILE, load_host_declarations
from specdev_tools.host_install import retired_command_findings
from specdev_tools.migration import runner
from specdev_tools.migration.context import MigrationContext
from specdev_tools.migration.registry import Problem, discover_scripts
from specdev_tools.migration.report import STATUS_OK
from specdev_tools.migration.scripts.v1_2_0 import p7_host_files as script
from specdev_tools.migration.worklist import WORKLIST_FILE
from specdev_tools.migration.writer import DocumentSet

from ._support import MINI_HOST, git, make_host, make_toolkit, tree_digest

OVERLAYS = MINI_HOST.parent / "host_files"
HOOK = ".pre-commit-config.yaml"
CI = ".github/workflows/ci.yml"
MINI_CI = ".github/workflows/spec_validation.yml"
THIRD_PARTY = {"third_party_id": "tp-argon2", "name": "Argon2", "pin": "0.41.1", "derives_from": ["seed-x"]}


def _overlay(host: Path, *names: str) -> None:
    for name in names:
        shutil.copytree(OVERLAYS / name, host, dirs_exist_ok=True)


def _commit(host: Path, message: str = "host files") -> None:
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", message)


def _items(host: Path) -> list[dict]:
    path = host / "spec" / WORKLIST_FILE
    return json.loads(path.read_text(encoding="utf-8"))["items"] if path.is_file() else []


def _of_kind(host: Path, kind: str) -> list[dict]:
    return [item for item in _items(host) if item["kind"] == kind]


def _run(host: Path, toolkit: Path, **kwargs):
    chosen = [s for s in discover_scripts() if s.id == script.SCRIPT.id]
    return runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host, scripts=chosen, **kwargs)


def _context(host: Path, toolkit: Path) -> MigrationContext:
    spec = host / "spec"
    return MigrationContext(str(spec), str(host), str(host), str(toolkit), False, DocumentSet(str(spec)), "1.1.1", "1.2.0")


def _digest_outside_spec(host: Path) -> dict[str, str]:
    return {rel: digest for rel, digest in tree_digest(host).items() if not rel.startswith("spec/")}


def _with_third_party(host: Path) -> None:
    path = next((host / "spec").glob("02_*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["third_parties"] = [THIRD_PARTY]
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


@pytest.fixture
def toolkit(tmp_path) -> Path:
    return make_toolkit(tmp_path)


@pytest.fixture
def host(tmp_path) -> Path:
    """The mini host with the retired-command overlay committed: hooks and workflows with every shape the detector reads."""
    root = make_host(tmp_path)
    _overlay(root, "retired")
    _commit(root)
    return root


def test_the_report_holds_one_w932_finding_per_retired_command_line(host, toolkit):
    findings = retired_command_findings(host)
    seen = {(f.file, f.line, f.command) for f in findings}
    assert seen == {
        (HOOK, 6, "matrix"),
        (HOOK, 10, "traceability-check"),
        (CI, 12, "validate-all"),
        (CI, 13, "matrix"),
        (CI, 13, "trace_matrix.json"),
        (MINI_CI, 11, "validate-all"),
        (MINI_CI, 12, "matrix"),
    }
    report = _run(host, toolkit)
    assert report.status == STATUS_OK, report.render()
    items = _of_kind(host, script.KIND_RETIRED_COMMAND)
    assert len(items) == len(findings)
    assert {item["evidence"].split(": ", 1)[0] for item in items} == {f"{f.file}:{f.line}" for f in findings}
    assert {item["about"] for item in items} == {HOOK, CI, MINI_CI}
    printed = report.render()
    for finding in findings:
        assert f"{finding.file} ({script.KIND_RETIRED_COMMAND}): {finding.file}:{finding.line}:" in printed


def test_each_item_names_the_file_the_line_and_the_replacement_the_detector_gives(host, toolkit):
    _run(host, toolkit)
    by_evidence = {item["evidence"].split(": ", 1)[0]: item for item in _of_kind(host, script.KIND_RETIRED_COMMAND)}
    matrix = by_evidence[f"{HOOK}:6"]
    assert "./tools/run_specdev.sh matrix" in matrix["evidence"]
    assert "specdev coverage --by fr" in matrix["proposal"]
    assert "by hand" in matrix["proposal"] and matrix["audience"] == "operator"
    validate_all = by_evidence[f"{CI}:12"]
    assert "is superseded in 1.2.0 by `specdev spec-check`" in validate_all["proposal"] and "was removed" not in validate_all["proposal"]
    assert "--out spec/extras/trace_matrix.json" in by_evidence[f"{CI}:13"]["evidence"]


def test_a_hook_that_calls_a_retired_command_blocks_and_a_workflow_line_does_not(host, toolkit):
    _run(host, toolkit)
    blocking = {item["about"]: item["blocking"] for item in _of_kind(host, script.KIND_RETIRED_COMMAND)}
    assert blocking == {HOOK: True, CI: False, MINI_CI: False}


def test_a_commented_line_and_a_matrix_strategy_are_not_reported(host, toolkit):
    _run(host, toolkit)
    lines = {item["evidence"].split(": ", 1)[0] for item in _of_kind(host, script.KIND_RETIRED_COMMAND)}
    assert f"{HOOK}:12" not in lines  # a commented specdev forward-replay-check
    assert f"{CI}:6" not in lines and f"{CI}:15" not in lines  # `matrix:` strategy, a commented completeness-check


def test_the_detector_misses_a_command_after_a_backslash_and_the_report_says_so(host, toolkit):
    assert not any(f.line in (15, 16) for f in retired_command_findings(host) if f.file == HOOK)  # pinned: what the detector does today
    report = _run(host, toolkit)
    assert script.CONTINUATION_NOTE in report.render()
    assert not any(item["evidence"].startswith((f"{HOOK}:15", f"{HOOK}:16")) for item in _items(host))


def test_dag_lint_is_not_reported(host, toolkit):
    _run(host, toolkit)
    text = json.dumps(_items(host))
    assert "dag-lint" not in text
    assert not any(item["evidence"].startswith(f"{HOOK}:19") or item["evidence"].startswith(f"{CI}:14") for item in _items(host))


def test_a_default_run_changes_no_host_file(host, toolkit):
    before = _digest_outside_spec(host)
    config = (host / ".git" / "config").read_bytes()
    report = _run(host, toolkit)
    assert report.status == STATUS_OK, report.render()
    assert _digest_outside_spec(host) == before
    assert (host / ".git" / "config").read_bytes() == config
    assert set(report.changed_files) == {WORKLIST_FILE, "specdev_version"}


def test_the_write_set_excludes_claude_hooks_gitattributes_git_config_and_workflows_without_the_flag(host, toolkit):
    # P4: there is no flag; the files below are never written by the runner, whatever they hold
    (host / ".claude").mkdir()
    (host / ".claude" / "settings.local.json").write_text('{"permissions": {"ask": ["Bash(specdev align:*)"]}}\n', encoding="utf-8")
    (host / ".gitattributes").write_text("spec/specdev.lock merge=specdev-lock\n", encoding="utf-8")
    hook = host / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexec specdev matrix spec\n", encoding="utf-8")
    watched = [HOOK, CI, MINI_CI, ".claude/settings.local.json", ".gitattributes", ".git/config", ".git/hooks/pre-commit"]
    before = {rel: hashlib.sha256((host / rel).read_bytes()).hexdigest() for rel in watched}
    assert _run(host, toolkit).status == STATUS_OK
    assert {rel: hashlib.sha256((host / rel).read_bytes()).hexdigest() for rel in watched} == before


def test_dry_run_installs_nothing(host, toolkit):
    before = tree_digest(host)
    report = _run(host, toolkit, dry_run=True)
    assert report.status == STATUS_OK, report.render()
    assert tree_digest(host) == before
    assert not (host / "spec" / WORKLIST_FILE).exists()
    assert report.edits_by_script[script.SCRIPT.id] > 0 and WORKLIST_FILE in report.diff


def test_a_missing_declaration_becomes_one_operator_worklist_item(host, toolkit):
    _run(host, toolkit)
    declarations = _of_kind(host, script.KIND_DECLARATION)
    assert sorted(item["about"] for item in declarations) == ["release_tag_pattern", "setup_command"]  # toolkit outside the repository: no exclusion item
    for item in declarations:
        assert item["audience"] == "operator" and item["step"] == "12" and not item["resolved"]
        assert "spec/common/host_declarations.json" in item["proposal"]
    assert len({item["id"] for item in _items(host)}) == len(_items(host))


def _fragment(item: dict) -> dict:
    """The JSON object a declaration item proposes: the argument of the `specdev json insert` line in its proposal."""
    return json.loads(item["proposal"][item["proposal"].index("{") : item["proposal"].rindex("}") + 1])


def _commands(item: dict) -> list[list[str]]:
    """The command lines of a proposal (the text after its first ``): ``), split on ``&&``), each as an argument list."""
    words = shlex.split(item["proposal"].split("): ", 1)[1])
    lines, current = [], []
    for word in words:
        if word == "&&":
            lines.append(current)
            current = []
        else:
            current.append(word)
    return [*lines, current]


def _run_command(host: Path, toolkit: Path, line: list[str]) -> None:
    """One printed ``specdev ...`` line through the real CLI, from the host root (the paths of a proposal are relative to it)."""
    previous = os.getcwd()
    os.chdir(host)
    try:
        with patch("specdev_tools.cli.check_venv", return_value=None), patch.object(sys, "argv", [*line, "--repo-root", str(toolkit)]):
            try:
                cli.main()
            except SystemExit as exit_:
                assert exit_.code in (None, 0), line
    finally:
        os.chdir(previous)


def test_the_proposal_is_a_command_that_creates_the_declarations_file_when_it_does_not_exist(host, toolkit):
    _run(host, toolkit)
    item = next(item for item in _of_kind(host, script.KIND_DECLARATION) if item["about"] == "setup_command")
    assert not (host / "spec" / HOST_DECLARATIONS_FILE).exists()
    line = shlex.split(item["proposal"].split("): ", 1)[1])
    assert line[:5] == ["specdev", "json", "insert", "spec/common/host_declarations.json", "."] and line[-2:] == ["--create-schema", "vc:host-declarations"]
    previous = os.getcwd()
    os.chdir(host)  # the command's path is relative to the host root
    try:
        with patch("specdev_tools.cli.check_venv", return_value=None), patch.object(sys, "argv", [*line, "--repo-root", str(toolkit)]):
            try:
                cli.main()
            except SystemExit as exit_:
                assert exit_.code in (None, 0)
    finally:
        os.chdir(previous)
    written = json.loads((host / "spec" / HOST_DECLARATIONS_FILE).read_text(encoding="utf-8"))
    assert written["setup_command"] == _fragment(item)["setup_command"] and written["$schema"] == "vc:host-declarations"
    assert load_host_declarations(str(host / "spec")).setup_command == written["setup_command"]


def test_the_toolkit_folder_inside_the_repository_is_proposed_as_an_exclusion(host, tmp_path):
    inside = make_toolkit(host, "1.2.0")  # host/toolkit
    _commit(host, "toolkit inside")
    _run(host, inside)
    item = next(item for item in _of_kind(host, script.KIND_DECLARATION) if item["about"] == "code_tree_exclusions")
    assert _fragment(item) == {"code_tree_exclusions": ["toolkit"]}


def test_a_declared_item_gets_no_item_and_a_complete_file_gets_none(host, toolkit):
    declarations = {
        "$schema": "vc:host-declarations",
        "release_tag_pattern": "^v[0-9]+[.][0-9]+[.][0-9]+$",
        "setup_command": "npm ci",
        "code_tree_exclusions": ["toolkit"],
        "pin_sources": {},
    }
    target = host / "spec" / HOST_DECLARATIONS_FILE
    target.write_text(json.dumps(declarations), encoding="utf-8")
    _commit(host, "declarations")
    _run(host, toolkit)
    assert _of_kind(host, script.KIND_DECLARATION) == [] and _of_kind(host, script.KIND_PIN_SOURCE) == []
    assert json.loads(target.read_text(encoding="utf-8")) == declarations


def test_an_unreadable_declarations_file_is_one_item_and_the_other_declaration_items_wait(host, toolkit):
    (host / "spec" / HOST_DECLARATIONS_FILE).write_text('{"setup_command": 7}', encoding="utf-8")
    _commit(host, "bad declarations")
    _run(host, toolkit)
    assert _of_kind(host, script.KIND_DECLARATION) == []
    invalid = _of_kind(host, script.KIND_DECLARATIONS_INVALID)
    assert len(invalid) == 1 and invalid[0]["about"] == f"spec/{HOST_DECLARATIONS_FILE}"


def test_proposed_declaration_values_are_evidence_only_and_never_written_to_host_declarations_json(host, toolkit):
    _overlay(host, "pins")
    _with_third_party(host)
    _commit(host, "pins")
    for tag in ("v1.0.0", "v1.0.1", "v1.0.1-stage"):
        git(host, "tag", tag)
    _run(host, toolkit)
    assert not (host / "spec" / HOST_DECLARATIONS_FILE).exists()
    fragments = [_fragment(item) for item in _items(host) if item["kind"] == script.KIND_DECLARATION]
    merged: dict = {"$schema": "vc:host-declarations", "pin_sources": {}}
    for fragment in fragments:
        merged.update(fragment)
    for item in _of_kind(host, script.KIND_PIN_SOURCE):
        *_, patch_line = _commands(item)
        merged["pin_sources"][item["about"]] = json.loads(patch_line[-1])
    assert merged["release_tag_pattern"] == script.TAG_PATTERN_EXAMPLE
    assert merged["setup_command"] == "npm ci --ignore-scripts"  # the toolkit's own install line is left out
    assert merged["pin_sources"] == {"tp-argon2": [{"type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version"}]}
    scratch = host.parent / "scratch_host"
    (scratch / "common").mkdir(parents=True)
    (scratch / HOST_DECLARATIONS_FILE).write_text(json.dumps(merged), encoding="utf-8")
    accepted = load_host_declarations(scratch)  # the real reader accepts what the items propose
    assert accepted.setup_command == "npm ci --ignore-scripts" and "tp-argon2" in accepted.pin_sources
    tag_item = next(item for item in _items(host) if item["about"] == "release_tag_pattern")
    assert "2 match" in tag_item["evidence"] and "1 do not" in tag_item["evidence"]
    pin_item = next(item for item in _items(host) if item["kind"] == script.KIND_PIN_SOURCE)
    assert pin_item["step"] == "02" and "0.41.1" in pin_item["evidence"]


def test_a_pin_without_a_derivable_source_prints_the_command_with_the_shape_of_a_source(host, toolkit):
    _with_third_party(host)
    _commit(host, "third party without a lock file")
    _run(host, toolkit)
    item = _of_kind(host, script.KIND_PIN_SOURCE)[0]
    assert item["about"] == "tp-argon2" and "no lock or requirement file is tracked" in item["evidence"]
    assert "by hand" not in item["evidence"] and "by hand" not in item["proposal"]
    insert, patch_line = _commands(item)
    assert patch_line[:5] == ["specdev", "json", "patch", "spec/common/host_declarations.json", '.pin_sources["tp-argon2"]']
    assert json.loads(patch_line[5]) == [{"type": "json-pointer", "file": "<file>", "pointer": "<JSON pointer to the version>"}]
    assert '"regex"' in item["evidence"]


def test_every_pin_proposal_is_safe_in_any_order_whether_or_not_the_declarations_file_exists(tmp_path):
    """Four cases through the real CLI: file absent or present, first or second third party; each id ends up declared and nothing else is lost."""
    second = {"third_party_id": "tp-hasher", "name": "Hasher", "pin": "2.0.0", "derives_from": ["seed-x"]}
    lock = {"lockfileVersion": 3, "packages": {"node_modules/argon2": {"version": "0.41.1"}, "node_modules/hasher": {"version": "2.0.0"}}}
    for order in ((0, 1), (1, 0)):
        for present in (False, True):
            root = tmp_path / f"case-{order[0]}-{int(present)}"
            root.mkdir()
            host, toolkit = make_host(root), make_toolkit(root)
            _overlay(host, "pins")
            (host / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
            path = next((host / "spec").glob("02_*.json"))
            data = json.loads(path.read_text(encoding="utf-8"))
            data["third_parties"] = [THIRD_PARTY, second]
            path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
            target = host / "spec" / HOST_DECLARATIONS_FILE
            if present:
                target.write_text(json.dumps({"$schema": "vc:host-declarations", "release_tag_pattern": "^v$", "pin_sources": {"tp-old": [{"type": "regex", "file": "a.txt", "pattern": "(1)"}]}}), encoding="utf-8")
            _commit(host, "case")
            _run(host, toolkit)
            pins = {item["about"]: item for item in _of_kind(host, script.KIND_PIN_SOURCE)}
            assert sorted(pins) == ["tp-argon2", "tp-hasher"]
            ids = ["tp-argon2", "tp-hasher"]
            for index in order:
                for line in _commands(pins[ids[index]]):
                    _run_command(host, toolkit, line)
            held = json.loads(target.read_text(encoding="utf-8"))
            assert {"tp-argon2", "tp-hasher"} <= set(held["pin_sources"]) and held["$schema"] == "vc:host-declarations"
            assert held["pin_sources"]["tp-argon2"][0]["pointer"] == "/packages/node_modules~1argon2/version"
            assert ("tp-old" in held["pin_sources"] and held["release_tag_pattern"] == "^v$") == present
            assert load_host_declarations(str(host / "spec")).pin_sources.keys() == held["pin_sources"].keys()


def test_a_rerun_adds_nothing_and_a_resolved_item_stays_resolved(host, toolkit):
    context = _context(host, toolkit)
    found = script.detect(context)
    assert found > 0
    assert script.apply(context).worklist_items == found
    context.documents.write()
    assert script.detect(_context(host, toolkit)) == 0
    path = host / "spec" / WORKLIST_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    data["items"][0].update(resolved=True, note="fixed by hand")
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    before = path.read_bytes()
    again = _context(host, toolkit)
    assert script.detect(again) == 0 and script.apply(again).edits == 0
    again.documents.write()
    assert path.read_bytes() == before


def test_a_line_a_person_fixed_is_not_found_again(host, toolkit):
    _run(host, toolkit)
    hook = host / HOOK
    hook.write_text(hook.read_text(encoding="utf-8").replace("specdev traceability-check spec", "specdev spec-check spec"), encoding="utf-8")
    assert not any(f.command == "traceability-check" for f in retired_command_findings(host))
    assert script.detect(_context(host, toolkit)) == 0  # the item stays listed until a person closes it


def test_the_script_declares_extras_only_and_phase_seven():
    assert script.SCRIPT.touches == ("extras",) and script.SCRIPT.phase == 7


def test_verify_accepts_the_worklist_and_refuses_any_other_changed_file():
    class Snap:
        def __init__(self, files):
            self.files = files

    before = Snap({"a.json": "1", WORKLIST_FILE: "x"})
    assert script.verify(before, Snap({"a.json": "1", WORKLIST_FILE: "y"})) == []
    assert script.verify(before, Snap({"a.json": "2", WORKLIST_FILE: "y", f"common/{Path(HOST_DECLARATIONS_FILE).name}": "z"})) == [
        Problem("changed a.json; this script adds worklist items only", "a.json"),
        Problem("changed common/host_declarations.json; this script adds worklist items only", "common/host_declarations.json"),
    ]
