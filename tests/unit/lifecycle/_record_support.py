"""Builders of the hosts the record tests run on: the worked example as a git host whose plan item has addressable actions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from specdev_tools.lifecycle import anchor_store, plans
from unit.graph._synth import ROOT
from unit.lifecycle._support import MILESTONE, PLAN, closed_record
from unit.proof._support import PASSING, binding_item, host_with
from unit.verify._support import commit_all, edit_doc

ITEM = "PWRESET_CONFIRM_EXPIRED_01"
AUTHOR = {"name": "Ada Lovelace", "email": "ada@example.invalid"}
ALPHA = "ver-alpha"
STAGED = "ver-staged"
STAGED_COMMAND = "echo staged"


class Roots(NamedTuple):
    """The three roots every record function takes, as strings."""

    spec: str
    repo: str
    git: str


def roots(host: Path) -> Roots:
    """The spec root, toolkit root and host root of *host*."""
    return Roots(str(host / "spec"), str(ROOT), str(host))


@pytest.fixture
def author(monkeypatch: pytest.MonkeyPatch) -> None:
    """Git names ``AUTHOR`` as the author of whatever is recorded."""
    monkeypatch.setenv("GIT_AUTHOR_NAME", AUTHOR["name"])
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", AUTHOR["email"])


@pytest.fixture
def no_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Git has no configured identity and may not guess one from the user database."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "none"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.useConfigOnly")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "EMAIL"):
        monkeypatch.delenv(name, raising=False)


def action(action_id: str, kind: str = "file_edit", **fields: Any) -> dict[str, Any]:
    """A plan action: a ``file_edit`` of ``src/hello.txt`` unless *kind* and *fields* say otherwise."""
    body: dict[str, Any] = {"id": action_id, "type": kind, "description": f"Action {action_id}."}
    if kind in ("file_edit", "file_create"):
        body["target"] = "src/hello.txt"
    return {**body, **fields}


def plan_host(tmp_path: Path, *extra: dict[str, Any], bindings: tuple[dict[str, Any], ...] = (), keep_ids: bool = False, name: str = "host") -> Path:
    """The worked example as a git host with code and the given bindings; its plan item's first action is ``a01`` and *extra* actions follow.

    With *keep_ids* the first action has no id (a plan written before the id was required, or edited by hand: ``plan record`` still reads it).
    """
    host = host_with(tmp_path, *bindings, name=name)

    def edit(document: dict[str, Any]) -> None:
        actions = document["plan"]["spec_alignment"]["checklist"][0]["implementation"]["actions"]
        if keep_ids:
            del actions[0]["id"]
        actions.extend(extra)

    edit_doc(host, PLAN, edit)
    commit_all(host, "plan with action ids" if not keep_ids else "plan without action ids")
    return host


def plan_document(host: Path) -> dict[str, Any]:
    """The parsed plan file of the worked example's milestone in *host*."""
    return json.loads((host / "spec" / PLAN).read_text(encoding="utf-8"))


def records_in(host: Path) -> list[dict[str, Any]]:
    """The execution records of the plan of *host*, in file order."""
    return list(plan_document(host).get("execution", {}).get("records", []))


def close_milestone(host: Path) -> None:
    """Close the milestone of *host*: its anchor row is ``done`` with a close record that stores the plan hash now."""
    spec = host / "spec"
    anchor_store.write_row_state(spec, MILESTONE, "done", close=closed_record(plan_hash=plans.plan_hash(spec / PLAN)), repo_root=str(ROOT))


def alpha_binding(*, stage: str = "dev", command: str = PASSING, binding_id: str = ALPHA, proves: tuple[str, ...] | None = None) -> dict[str, Any]:
    """A binding of the fixture the plan item's criterion names in ``verified_by``."""
    return binding_item(binding_id, stage=stage, commands=(command,), **({} if proves is None else {"proves": proves}))


def lock_path_of(host: Path) -> Path:
    """The trace lock file of *host*."""
    return host / "spec" / "extras" / "trace.lock.json"


def change_lock_hash(host: Path) -> None:
    """Replace the content hash of the lock entries of the plan item, as a re-attest of a changed criterion would."""
    path = lock_path_of(host)
    document = json.loads(path.read_text(encoding="utf-8"))
    for entry in document["entries"]:
        if entry["source"] == ITEM:
            entry["content_hash"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

