"""Builders the release tests share: a git host whose release gate is clear, tags, stamps and the gate run on a host.

The worked example is not release-ready (spec-check reports its own 24 errors).  ``release_host`` makes a copy that is: every
obligation is parked (scope ``later``, W933 listed), the two nodes parking leaves unused (a metric, a job) are ``not_applicable``,
the scaffold file is tracked, the spec is stamped with the active toolkit version and the host declares a release tag pattern.
``leave`` names obligations that stay in scope.
"""
from __future__ import annotations

import atexit
import shutil
import tempfile
from functools import cache
from pathlib import Path

from specdev_tools.core.changelog_parser import get_toolkit_version
from specdev_tools.core.json_utils import patch_text
from specdev_tools.graph.names import OBLIGATION_ROLES
from specdev_tools.release.gate import ReleaseGateResult, run_release_gate
from specdev_tools.trace.lockfile import write_lock
from unit.graph._synth import ROOT, git
from unit.trace._lock_support import git_copy_of_example, lock_for
from unit.verify._support import commit_all, graph_of, write, write_json

PATTERN = r"^v[0-9]+\.[0-9]+\.[0-9]+$"
SCAFFOLD = "src/routes/password-resets/confirm.ts"
UNUSED = ("metric-reset-completion-rate", "job-contract-tests")
"""The metric and the job that nothing uses once every obligation is parked."""


def stamp(host: Path, version: str | None = None) -> None:
    """Write ``spec/specdev_version`` with *version* (the active toolkit's when ``None``)."""
    write(host / "spec" / "specdev_version", f"toolkit_version: {version or get_toolkit_version(ROOT)}\n")


def declare(host: Path) -> None:
    """Declare the release tag pattern."""
    write_json(host / "spec" / "common" / "host_declarations.json", {"$schema": "vc:host-declarations", "release_tag_pattern": PATTERN})


def _patch(host: Path, node_id: str, **fields: str) -> None:
    node = graph_of(host).by_id[node_id]
    path = host / "spec" / node.file
    text = path.read_text(encoding="utf-8")
    for key, value in fields.items():
        text = patch_text(text, f"{node.jq_path}.{key}", f'"{value}"')
    path.write_text(text, encoding="utf-8")


def set_scope(host: Path, node_id: str, scope: str) -> None:
    """Give *node_id* this scope (with a reason) and rebuild the lock, as a person's ``attest`` would; not committed."""
    _patch(host, node_id, scope=scope, scope_reason="set by the release test")
    write_lock(str(host / "spec"), lock_for(graph_of(host), host))


def _build(destination: Path, leave: tuple[str, ...]) -> None:
    host = git_copy_of_example(destination)
    stamp(host)
    declare(host)
    write(host / SCAFFOLD, "export {};\n")
    parked = [node.id for node in graph_of(host).nodes if node.role in OBLIGATION_ROLES and node.scope in (None, "in") and node.id not in leave]
    for node_id in parked:
        _patch(host, node_id, scope="later", scope_reason="parked for the release test")
    for node_id in UNUSED:
        _patch(host, node_id, lifecycle="not_applicable")
    write_lock(str(host / "spec"), lock_for(graph_of(host), host))
    commit_all(host, "release-ready example")


@cache
def _template(leave: tuple[str, ...]) -> Path:
    folder = Path(tempfile.mkdtemp(prefix="release-template-"))
    atexit.register(shutil.rmtree, folder, ignore_errors=True)
    _build(folder / "host", leave)
    return folder / "host"


def release_host(tmp_path: Path, *leave: str, name: str = "host") -> Path:
    """A copy of the release-ready example in *tmp_path* (one git commit); the obligations named in *leave* stay in scope."""
    destination = tmp_path / name
    shutil.copytree(_template(tuple(sorted(leave))), destination, symlinks=True)
    return destination


def gate(host: Path) -> ReleaseGateResult:
    """The release gate on *host*."""
    return run_release_gate(str(ROOT), str(host / "spec"), str(host), str(host / "spec"), str(host / "spec" / "canon"))


def codes(result: ReleaseGateResult) -> list[str]:
    """The codes of the errors of *result*, in order."""
    return [error.code for error in result.errors]


def nodes_of(result: ReleaseGateResult, code: str) -> set[str | None]:
    """The node ids of the errors of *result* with *code*."""
    return {error.node_id for error in result.errors if error.code == code}


def tag(host: Path, name: str, *, annotated: bool = False, ref: str = "HEAD") -> None:
    """Tag *ref* of *host* (a lightweight tag, or an annotated one)."""
    git(host, "tag", *(["-a", "-m", f"release {name}"] if annotated else []), name, ref)


def commit(host: Path, message: str = "change") -> None:
    """Stage everything and commit it, also when nothing changed (a release point on an unchanged tree)."""
    git(host, "add", "-A")
    git(host, "commit", "-q", "--allow-empty", "-m", message)


def advance(host: Path, text: str = "next\n") -> str:
    """Commit a change of code on *host* and return the new commit."""
    write(host / "src" / "next.txt", text)
    commit(host, "next")
    return git(host, "rev-parse", "HEAD")


def latency_host(tmp_path: Path, *, run_it: bool, name: str = "host") -> Path:
    """A closed example in which the NFR waits for staging proof (a fixture bound at ``staging`` verifies it), declared and stamped 1.2.0; with *run_it* the binding has run."""
    from specdev_tools.verify.records import records_folder, write_binding
    from unit.proof._closed import add_milestone, closed_example, criterion
    from unit.proof._support import EXAMPLE_BINDING, NFR, add_fixture, binding_item, run

    host = closed_example(tmp_path, name)
    (host / "spec" / "extras" / "verification" / f"{EXAMPLE_BINDING}.json").unlink()
    write(host / "src" / "hello.txt", "hello\n")
    write_binding(records_folder(str(host / "spec")), str(ROOT), binding_item(LATENCY_BINDING, verifier=LATENCY_FIXTURE, proves=(NFR,), stage="staging"))
    add_fixture(host, fixture_id=LATENCY_FIXTURE, verifies=[NFR])
    add_milestone(host, "ms-latency", [criterion("tc-latency-check", refines=[NFR])], done=True)
    declare(host)
    stamp(host, "1.2.0")
    commit_all(host, "latency host")
    if run_it:
        run(host, [LATENCY_BINDING], stage="staging")
        commit_all(host, "staging evidence")
    return host


LATENCY_FIXTURE, LATENCY_BINDING = "fix-latency", "ver-latency"
