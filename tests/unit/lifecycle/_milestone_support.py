"""Builders the milestone-command tests share: the worked example as a git host that is ready to close, and the commands run on it."""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from specdev_tools import cli
from specdev_tools.lifecycle.commands import gate_providers
from specdev_tools.lifecycle.plan_records import Address, record_action
from specdev_tools.lifecycle.signoff import sign_off
from specdev_tools.trace.lockfile import Lock, read_lock, write_lock
from unit.graph._synth import ROOT
from unit.lifecycle._record_support import ITEM, alpha_binding, plan_host, roots
from unit.lifecycle._support import ANCHOR, MILESTONE, PLAN
from unit.proof._support import INVARIANT, OTHER_FIXTURE, REUSED_BINDING, binding_item, run
from unit.verify._support import commit_all, edit_doc, write

SECOND_ITEM = "PWRESET_CONFIRM_REUSED_01"
SECOND_CRITERION = "tc-confirm-reused-token"
SCAFFOLD_FILE = "src/routes/password-resets/confirm.ts"
REVIEW = {"verdict": "verified", "recorded_at": "2026-11-21T10:00:00Z"}


def providers_of(host: Path) -> Any:
    """The close-gate providers the command layer builds, for the roots of *host*."""
    spec, repo, git = roots(host)
    return gate_providers(spec, repo, git)


def set_row(host: Path, status: str, **fields: Any) -> None:
    """Give the anchor row of *host* this status and these extra fields (``deferral_reason``, ``close``)."""
    def edit(document: dict[str, Any]) -> None:
        row = document["plan"]["milestone_index"][0]
        row.pop("deferral_reason", None), row.pop("close", None)
        row.update(status=status, **fields)

    edit_doc(host, ANCHOR, edit)


def ready_host(tmp_path: Path, *, signed: bool = False, name: str = "host") -> Path:
    """The worked example with both criteria realised, bound, run and proven, the item executed, a verified review and a tracked scaffold file; with *signed* it holds a sign-off record too."""
    bindings = (alpha_binding(), binding_item(REUSED_BINDING, verifier=OTHER_FIXTURE, proves=(INVARIANT,)))
    host = plan_host(tmp_path, bindings=bindings, name=name)

    def edit_plan(document: dict[str, Any]) -> None:
        document["plan"]["spec_alignment"]["checklist"].append({
            "id": SECOND_ITEM, "realises": [SECOND_CRITERION], "description": "A second redemption of a token is refused.", "type": "behavior", "layer": "api",
            "implementation": {"actions": []},
        })
        document["review"] = dict(REVIEW)

    edit_doc(host, PLAN, edit_plan)
    write(host / SCAFFOLD_FILE, "export {};\n")
    commit_all(host, "ready")
    spec, repo, git = roots(host)
    record_action(spec, repo, git, Address(ITEM, "a01"), "done")
    run(host, [binding["verification_id"] for binding in bindings if binding["stage"] == "dev"])
    if signed:
        sign_off(spec, repo, git, MILESTONE, providers_of(host))
    return host


def change_stamp(host: Path, holder: str, target: str) -> None:
    """Make the lock entry of the link *holder* to *target* carry a chain stamp the target no longer has: the link is suspect."""
    lock = read_lock(str(host / "spec"))
    stamped = [entry.__class__(**{**entry.__dict__, "chain_stamp": "sha256:" + "0" * 64}) if (entry.source, entry.target) == (holder, target) else entry for entry in lock.entries]
    write_lock(str(host / "spec"), Lock(tuple(stamped)))


def cli_run(host: Path, *argv: str) -> tuple[int, str, str]:
    """Run ``specdev <argv>`` on *host* with the three root flags; returns the exit code, stdout and stderr."""
    flags = ["--repo-root", str(ROOT), "--spec-root", str(host / "spec"), "--git-root", str(host)]
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), patch("specdev_tools.cli.check_venv", return_value=None), patch.object(sys, "argv", ["specdev-tools", *argv, *flags]):
        try:
            code = cli.main()
        except SystemExit as exit_:
            code = int(exit_.code or 0)
    return (code or 0), out.getvalue(), err.getvalue()
