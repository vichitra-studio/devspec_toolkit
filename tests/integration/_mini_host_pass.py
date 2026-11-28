"""The scripted judgement pass of the mini host as a callable (WI-M10-15b): ``run_scripted_pass(host, toolkit)``.

``host`` is a tmp git copy of the mini host already past ``align apply --auto`` and committed; ``toolkit`` is a toolkit root that
says 1.2.0 (the live checkout: the ``toolkit_1_2_0`` fixture).  The answers are ``tests/fixtures/migration/mini_host_pass/``.  The function runs every
step, closes the worklist items, commits ("Judgement pass") and leaves the copy ready for ``spec-check --merge`` and ``align validate``.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

from specdev_tools import cli
from specdev_tools.graph.build import build_graph
from unit.migration._support import REAL_ROOT, git

PASS_DIR = REAL_ROOT / "tests" / "fixtures" / "migration" / "mini_host_pass"
SPEC = "spec"
WORKLIST = f"{SPEC}/extras/migration/worklist.json"


# ---------------------------------------------------------------------------


@dataclass
class Host:
    """The git copy and the toolkit root, and the one way commands run on them."""

    root: Path
    toolkit: Path

    @property
    def spec(self) -> Path:
        return self.root / SPEC

    def specdev(self, *argv: str) -> tuple[int, str, str]:
        """``specdev <argv>`` in process with the flags a submodule deployment passes; returns (exit code, stdout, stderr)."""
        flags = ["--repo-root", str(self.toolkit), "--git-root", str(self.root)]
        if argv[0] != "align":
            flags += ["--spec-root", str(self.spec)]
        out, err, code = io.StringIO(), io.StringIO(), 0
        with (
            patch("specdev_tools.cli.check_venv", return_value=None),
            patch.object(sys, "argv", ["specdev", *argv, *flags]),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            try:
                cli.main()
            except SystemExit as exit_:
                code = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
        return code, out.getvalue(), err.getvalue()

    def commit(self, message: str) -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--no-verify", "-m", message)

    def spec_check(self, *flags: str) -> tuple[int, dict]:
        code, out, _err = self.specdev("spec-check", str(self.spec), *flags, "--json")
        return code, json.loads(out)

    def node_ids(self) -> frozenset[str]:
        return frozenset(build_graph(str(self.spec), str(self.toolkit)).by_id)


def error_codes(report: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for error in report["errors"]:
        if error.get("severity", "error") == "error":
            counts[error["code"]] = counts.get(error["code"], 0) + 1
    return counts


def digest(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}




@dataclass
class PassLog:
    """What the pass saw."""

    worklist_ids: list[str]
    failed_commands: list[tuple[str, list]] = field(default_factory=list)
    step_gates: dict[str, int] = field(default_factory=dict)
    later_gates: dict[str, dict[str, int]] = field(default_factory=dict)
    resolved: list[str] = field(default_factory=list)
    commands_run: int = 0


def run_file_operation(host: Host, operation: dict) -> None:
    """An operation on a file of the host outside ``spec/``: write a file, replace a line, commit."""
    if "write_file" in operation:
        target = host.root / operation["write_file"]["path"]
        assert SPEC not in target.relative_to(host.root).parts[:1], "a file operation never writes under spec/"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(operation["write_file"]["text"], encoding="utf-8")
    elif "replace" in operation:
        target = host.root / operation["replace"]["path"]
        text = target.read_text(encoding="utf-8")
        assert operation["replace"]["old"] in text
        target.write_text(text.replace(operation["replace"]["old"], operation["replace"]["new"]), encoding="utf-8")
    elif "commit" in operation:
        host.commit(operation["commit"])
    else:  # pragma: no cover - a typo in the fixture
        raise AssertionError(f"unknown operation {operation}")




def run_scripted_pass(host: Path | Host, toolkit: Path | None = None) -> PassLog:
    """Run the whole judgement pass on the migrated, committed copy *host*; see the module docstring."""
    if not isinstance(host, Host):
        host = Host(Path(host), Path(toolkit))
    answers = json.loads((PASS_DIR / "pass.json").read_text(encoding="utf-8"))["steps"]
    notes = json.loads((PASS_DIR / "resolutions.json").read_text(encoding="utf-8"))
    worklist = json.loads((host.root / WORKLIST).read_text(encoding="utf-8"))["items"]
    log = PassLog(worklist_ids=[item["id"] for item in worklist])
    pending = list(worklist)

    def resolve(item: dict) -> None:
        code, _out, err = host.specdev("align", "triage", str(host.spec), "--resolve", item["id"], "--note", notes[item["id"]])
        if code:
            log.failed_commands.append((item["id"], [err.strip()]))
        log.resolved.append(item["id"])
        pending.remove(item)

    finished: list[str] = []
    for step in answers:
        number = step["step"]
        for command in step["commands"]:
            log.commands_run += 1
            if isinstance(command, dict):
                run_file_operation(host, command)
                continue
            code, out, err = host.specdev(*[part.replace("{spec}", str(host.spec)) for part in command])
            if code:
                log.failed_commands.append((number, [*command[:5], (out + err).strip()[-400:]]))
        for item in [i for i in pending if i["step"] == number]:
            resolve(item)
        log.step_gates[number] = host.specdev("spec-check", str(host.spec), "--step", number)[0]
        finished.append(number)
        log.later_gates[number] = {later: host.specdev("spec-check", str(host.spec), "--step", later)[0] for later in ("14", "16a") if later not in finished}
    for item in list(pending):  # the items of steps that have no answers of their own (16b)
        resolve(item)
    host.commit("Judgement pass")
    return log
