"""Builders the tests of ``specdev release`` share: hosts for the cut and for the production gate, the identity git needs for a tag, and a snapshot of what a command may change.

``staged_host`` is a release-ready example (``unit.release._support.release_host``) in which one threat stays in scope and is
mitigated by a fixture bound at ``staging``: at the release gate the threat is relieved (its proof waits for staging), at the
production gate it needs staging evidence for the code tree of the tag.  ``at_deploy_host`` is a release-ready example whose closed
milestone has an action to be done at deploy for ``staging`` and ``prod``: a release after it owes those records.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from specdev_tools.core import changelog_parser
from unit.graph._synth import ROOT, git
from unit.lifecycle._record_support import action, closed_row
from unit.lifecycle._support import PLAN
from specdev_tools.verify.records import records_folder, write_binding
from unit.proof._support import GUARD, PASSING, binding_item, run
from unit.release._support import release_host, stamp
from unit.verify._support import commit_all, edit_doc, write

THREAT = "threat-reset-token-replay"
FIXTURE = "fix-password-reset-expired-token"
BINDING = "ver-password-reset-expired-token"
SECOND_FIXTURE = "fix-password-reset-reused-token"
SECOND_BINDING = "ver-password-reset-reused-token"
DEPLOY_ITEM = "PWRESET_CONFIRM_EXPIRED_01"
DEPLOY_ACTION = "a03"
IDENTITY = {"GIT_AUTHOR_NAME": "Release Person", "GIT_AUTHOR_EMAIL": "person@example.invalid", "GIT_COMMITTER_NAME": "Release Person", "GIT_COMMITTER_EMAIL": "person@example.invalid"}


@pytest.fixture
def identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Git has the identity a tag needs (the hosts of the tests carry no git configuration of their own)."""
    for name, value in IDENTITY.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def toolkit_1_2_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """The active toolkit reads as 1.2.0 (it is 1.1.1 until the release), so a host stamped 1.2.0 raises no E608."""
    monkeypatch.setattr(changelog_parser, "get_toolkit_version", lambda *_args, **_kwargs: "1.2.0")


def _stage_the_binding(host: Path) -> None:
    """Bind the two fixtures that mitigate the threat at ``staging``, with commands that pass."""
    path = host / "spec" / "extras" / "verification" / f"{BINDING}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["records"][0].update(stage="staging", commands=[PASSING], output_guard=GUARD)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    write_binding(records_folder(str(host / "spec")), str(ROOT), binding_item(SECOND_BINDING, verifier=SECOND_FIXTURE, proves=(), stage="staging"))
    write(host / "src" / "hello.txt", "hello\n")


def staged_host(tmp_path: Path, *leave: str, name: str = "host") -> Path:
    """A release-ready example in which ``THREAT`` (and the obligations named in *leave*) stay in scope and the mitigating fixture is bound at ``staging``; committed, no evidence yet."""
    host = release_host(tmp_path, THREAT, *leave, name=name)
    _stage_the_binding(host)
    commit_all(host, "staging binding")
    return host


def run_staging(host: Path) -> None:
    """Run the staging binding on *host* as it is now and commit the evidence (a commit that changes only the spec folder, so the code tree stays)."""
    run(host, [BINDING, SECOND_BINDING], stage="staging")
    commit_all(host, "staging evidence")


def at_deploy_host(tmp_path: Path, name: str = "host") -> Path:
    """A release-ready example, stamped 1.2.0, whose closed milestone has an at-deploy action for staging and prod (no deploy record yet); committed."""
    host = release_host(tmp_path, name=name)
    edit_doc(host, PLAN, lambda document: document["plan"]["spec_alignment"]["checklist"][0]["implementation"]["actions"].append(action(DEPLOY_ACTION, at_deploy=["staging", "prod"])))
    closed_row(host)
    stamp(host, "1.2.0")
    commit_all(host, "closed milestone with an at-deploy action")
    return host


def snapshot(host: Path) -> dict[str, object]:
    """Everything a refused command must leave as it was: every file outside ``.git`` (bytes), every ref, HEAD."""
    files = {str(path.relative_to(host)): path.read_bytes() for path in sorted(host.rglob("*")) if path.is_file() and ".git" not in path.relative_to(host).parts}
    return {"files": files, "refs": git(host, "for-each-ref"), "head": git(host, "rev-parse", "HEAD")}
