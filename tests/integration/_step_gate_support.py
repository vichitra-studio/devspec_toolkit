"""Builders for the step gate tests: a git copy of the worked example with the deltas of ``tests/fixtures/step_gate`` on top.

A delta is a JSON file with ``ops`` (see ``tests/fixtures/step_gate/README.md``).  The copy, the git repository and the
command runner are the ones M5 ships (``tests/unit/trace/_lock_support.py``); nothing of the example is copied into the
fixtures folder.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from specdev_tools import cli
from specdev_tools.graph.build import build_graph
from specdev_tools.trace.lockfile import write_lock

from unit.graph._synth import git
from unit.trace._lock_support import EXAMPLE_HOST, ROOT, git_copy_of_example, lock_for, run_on_example

DELTAS = ROOT / "tests" / "fixtures" / "step_gate" / "deltas"
GRAPH_CHECK_DELTAS = ROOT / "tests" / "fixtures" / "graph_checks" / "deltas"
SPEC = "spec"
NESTED_SPEC = "sub/spec"


class DeltaError(Exception):
    """A delta names an op, a file or a path the host copy does not have."""


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _array_at(document: Any, keys: list[str | int], *, create: bool) -> list[Any]:
    """The array at the object path *keys* of *document*; with *create*, the last key is made an empty array when absent."""
    node = document
    for key in keys[:-1]:
        node = node[key]
    if isinstance(keys[-1], str) and keys[-1] not in node and create:
        node[keys[-1]] = []
    array = node[keys[-1]]
    if not isinstance(array, list):
        raise DeltaError(f"{'.'.join(map(str, keys))} is not an array")
    return array


def _apply_op(host: Path, op: dict[str, Any], spec_prefix: str) -> None:
    target = host / op["file"].replace(f"{SPEC}/", f"{spec_prefix}/", 1)
    if op["op"] == "write":
        _write(target, op["value"])
    elif op["op"] == "append":
        if not target.is_file():
            raise DeltaError(f"{op['file']}: no such file in the host copy")
        document = _read(target)
        _array_at(document, op["path"], create=op.get("create", False)).append(op["value"])
        _write(target, document)
    elif op["op"] in ("set", "remove"):
        if not target.is_file():
            raise DeltaError(f"{op['file']}: no such file in the host copy")
        document = _read(target)
        holder = _holder_of(document, op["path"])
        if op["op"] == "set":
            holder[op["path"][-1]] = op["value"]
        else:
            del holder[op["path"][-1]]
        _write(target, document)
    else:
        raise DeltaError(f"unknown op '{op['op']}'")


def _holder_of(document: Any, keys: list[str | int]) -> Any:
    """The object or array that holds the last step of *keys* (object keys are strings, array positions integers).

    Raises ``DeltaError`` when a step of the path is not in the document.
    """
    node = document
    for key in keys[:-1]:
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError) as error:
            raise DeltaError(f"no {key!r} on the path {keys}") from error
    last = keys[-1]
    if isinstance(node, list) != isinstance(last, int) or (isinstance(node, list) and not -len(node) <= last < len(node)):
        raise DeltaError(f"the path {keys} does not end at an array position or an object key of the document")
    return node


def apply_delta(host: Path, name: str, spec_prefix: str = SPEC, *, folder: Path = DELTAS) -> None:
    """Apply the delta ``<folder>/<name>.json`` (default ``tests/fixtures/step_gate/deltas``) to the host copy *host*.

    The files of a delta are named under ``spec/``; *spec_prefix* says where the spec folder is in *host* (``sub/spec``
    in a nested layout).  The graph check variants live in ``GRAPH_CHECK_DELTAS``.

    Raises ``DeltaError`` for an unknown op, a missing file or a path that is not an array.
    """
    for op in _read(folder / f"{name}.json")["ops"]:
        _apply_op(host, op, spec_prefix)


def commit_all(host: Path, message: str) -> None:
    """Commit the working tree of *host* (a baseline for the step gate's merge-base comparison)."""
    git(host, "add", "-A")
    git(host, "commit", "-q", "-m", message)


def step_gate_host(
    destination: Path, deltas: Iterable[str] = (), *, attested: bool = True, commit: bool = False
) -> Path:
    """The worked example copied to *destination* as a git repository, with *deltas* applied; returns the host folder.

    With *attested* the trace lock accepts every link as the deltas leave it, so a new link raises no E761; pass
    ``False`` for a test about a link with no lock entry.  The deltas and the lock are left uncommitted, so the copy's
    one commit is the clean baseline; with *commit* they are committed too.
    """
    host = git_copy_of_example(destination)
    for name in deltas:
        apply_delta(host, name)
    if attested:
        attest(host)
    if commit:
        commit_all(host, "deltas: " + ", ".join(deltas))
    return host


def attest(host: Path, spec_prefix: str = SPEC) -> None:
    """Rewrite the trace lock of *host* so that it accepts every link as the working tree has it."""
    spec_dir = str(host / spec_prefix)
    write_lock(spec_dir, lock_for(build_graph(spec_dir, str(ROOT)), host))


def nested_step_gate_host(destination: Path, deltas: Iterable[str] = ()) -> Path:
    """The worked example as a git repository whose spec folder is ``sub/spec`` (seed documents stay at ``docs/seed`` at the top).

    The clean example is the one commit; *deltas* are applied on top, uncommitted, and the lock is attested as in
    ``step_gate_host``.  Returns the host folder (the repository top).
    """
    shutil.copytree(EXAMPLE_HOST, destination)
    (destination / "sub").mkdir()
    shutil.move(str(destination / SPEC), str(destination / NESTED_SPEC))
    git(destination, "init", "-q", "-b", "main")
    commit_all(destination, "worked example")
    for name in deltas:
        apply_delta(destination, name, NESTED_SPEC)
    attest(destination, NESTED_SPEC)
    return destination


def run_spec_check(host: Path, *flags: str) -> tuple[int, str]:
    """Run ``specdev spec-check`` on the spec folder of *host* with the three root flags: ``(exit code, output)``."""
    return run_on_example(host, "spec-check", str(host / "spec"), *flags)


def run_split(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    """Run ``specdev <argv>`` in this process: ``(exit code, stdout, stderr)`` (``run_spec_check`` mixes the two)."""
    with patch.object(cli, "check_venv", return_value=None), patch.object(sys, "argv", ["specdev", *argv]):
        try:
            cli.main()
            code = 0
        except SystemExit as exc:
            code = int(exc.code) if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    return code, captured.out, captured.err


HOOK_TEMPLATE = ROOT / "templates" / "pre-commit-config.host.yaml"
SKILL = ROOT / ".claude" / "skills" / "specdev-context" / "SKILL.md"
HOOK_ID = "spec-check"
PATHS_FLAG = "--paths"
_TEMPLATE_PYTHON = "devspec_env/bin/python"
_TEMPLATE_TOOLKIT = "./devspec_toolkit"
_SKILL_JQ = re.compile(r"specdev upstream-backlog [^\n]*--json\s*\\\n\s*\| jq '(?P<expression>.*?)'\s*\\\n", re.DOTALL)


def hook_config(hook_id: str = HOOK_ID) -> dict[str, Any]:
    """The hook *hook_id* of ``templates/pre-commit-config.host.yaml`` as the template writes it.

    Raises ``DeltaError`` unless the template has exactly one such hook.
    """
    template = yaml.safe_load(HOOK_TEMPLATE.read_text(encoding="utf-8"))
    hooks = [hook for repo in template["repos"] for hook in repo["hooks"] if hook["id"] == hook_id]
    if len(hooks) != 1:
        raise DeltaError(f"the template has {len(hooks)} hooks with id '{hook_id}'")
    return hooks[0]


def hook_entry_argv() -> list[str]:
    """The entry command of the ``spec-check`` hook, split as a shell would, with this interpreter and the toolkit under test.

    The interpreter of the template (``devspec_env/bin/python``) becomes ``sys.executable`` and the toolkit path
    (``./devspec_toolkit``) the toolkit root; every other word stays as the template writes it.

    Raises ``DeltaError`` when the entry no longer starts with the template interpreter or names the template toolkit path.
    """
    words = shlex.split(hook_config()["entry"])
    if words[0] != _TEMPLATE_PYTHON or _TEMPLATE_TOOLKIT not in words:
        raise DeltaError(f"the entry of '{HOOK_ID}' no longer starts with {_TEMPLATE_PYTHON} or names {_TEMPLATE_TOOLKIT}")
    return [sys.executable, *(str(ROOT) if word == _TEMPLATE_TOOLKIT else word for word in words[1:])]


def run_hook(
    host: Path,
    filenames: Iterable[str],
    *,
    flags: Iterable[str] = (),
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    absolute_roots: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the ``spec-check`` hook entry of the template as pre-commit does: a new process at the repository top, *filenames* appended.

    *flags* are put before ``--paths`` (which the template keeps last, so that pre-commit's filenames follow it); *env*
    adds environment variables to the process (every ``SPECDEV_*`` variable of this process is dropped first); *cwd*
    overrides the folder the process starts in, and then *absolute_roots* must be true: the relative ``spec``,
    ``./spec`` and ``.`` of the entry are replaced by the absolute folders of *host*, as a relative entry only works from the top.

    Raises ``DeltaError`` when the entry of the template does not end with ``--paths``.
    """
    argv = hook_entry_argv()
    if argv[-1] != PATHS_FLAG:
        raise DeltaError(f"the entry of '{HOOK_ID}' must end with {PATHS_FLAG}, the filenames of pre-commit follow it")
    if absolute_roots:
        absolute = {"spec": str(host / "spec"), "./spec": str(host / "spec"), ".": str(host)}
        argv = [absolute.get(word, word) for word in argv]
    base = {key: value for key, value in os.environ.items() if not key.startswith("SPECDEV_")}
    return subprocess.run(
        [*argv[:-1], *flags, PATHS_FLAG, *filenames],
        cwd=str(cwd or host),
        env={**base, "PYTHONPATH": str(ROOT / "tools"), **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def skill_backlog_jq() -> str:
    """The jq expression that ``.claude/skills/specdev-context/SKILL.md`` pipes the backlog JSON through, read from the file.

    Raises ``DeltaError`` when the skill no longer has the ``specdev upstream-backlog ... --json | jq '...'`` block.
    """
    found = _SKILL_JQ.search(SKILL.read_text(encoding="utf-8"))
    if found is None:
        raise DeltaError(f"{SKILL.name} has no 'specdev upstream-backlog ... --json | jq' block")
    return found.group("expression")


def start_branch(host: Path, name: str = "feature") -> None:
    """Make and switch to the branch *name* at the current commit of the host copy *host* (the default branch is ``main``)."""
    git(host, "checkout", "-q", "-b", name)


def host_on_branch(destination: Path, *, on_default: Iterable[str] = (), on_branch: Iterable[str]) -> Path:
    """A host copy whose default branch holds the deltas *on_default* and whose branch ``feature`` adds *on_branch* on top.

    Both sets are committed (the trace lock is attested after each), so the merge-base with ``main`` is the default
    branch's tip.  Returns the host folder, checked out on ``feature``.
    """
    default_deltas = list(on_default)
    host = step_gate_host(destination, default_deltas, commit=bool(default_deltas))
    start_branch(host)
    for name in on_branch:
        apply_delta(host, name)
    attest(host)
    commit_all(host, "work on the branch")
    return host


def json_command(capsys: pytest.CaptureFixture[str], *argv: str) -> None:
    """Run ``specdev json <argv> --repo-root <toolkit>`` in this process and require exit 0 (an edit of a spec file through the CLI)."""
    code, out, err = run_split(capsys, "json", *argv, "--repo-root", str(ROOT))
    assert code == 0, (argv, out, err)


def insert_delta_items_with_the_cli(host: Path, capsys: pytest.CaptureFixture[str], name: str) -> None:
    """Add the items of the delta *name* the way an operator does: ``json patch`` makes an absent array, ``json insert`` adds the item.

    Only ``append`` ops are read; the delta is the one source of the item text.
    """
    for op in _read(DELTAS / f"{name}.json")["ops"]:
        assert op["op"] == "append", op
        target = str(host / op["file"])
        array = "." + ".".join(op["path"])
        if op.get("create"):
            json_command(capsys, "patch", target, array, "[]")
        json_command(capsys, "insert", target, array, json.dumps(op["value"]))
