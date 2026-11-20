"""Builders of the hosts the proof tests run on: the worked example with code, bindings, runs and edits, and the proof of a node on it."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from specdev_tools.proof.proof import ProofResult, proof
from specdev_tools.proof.validity import ProofContext
from specdev_tools.verify.records import Binding, Evidence, binding_of, records_folder, write_binding, write_evidence
from specdev_tools.verify.run import run_bindings
from unit.graph._synth import ROOT
from unit.verify._support import commit_all, edit_doc, example_host, graph_of, write

FIXTURE = "fix-password-reset-expired-token"
OTHER_FIXTURE = "fix-password-reset-reused-token"
CRITERION, API, INVARIANT = "ac-password-reset-3", "api-password-reset-confirm", "inv-reset-token-single-use"
TP = "tp-argon2"
NFR = "nfr-latency-reset-email"
EXAMPLE_BINDING = "ver-password-reset-expired-token"
PASSING = "echo expected line"
GUARD = "expected line"
SPEC_FILES = {"fixtures": "08_fixtures.json"}
TAG_REF = {"id": "cn:core:tag:critical-path", "kind": "tag", "version": "1.0.0"}
REUSED_BINDING = "ver-reused"


def binding_item(binding_id: str, *, verifier: str = FIXTURE, proves: tuple[str, ...] = (CRITERION, API), stage: str = "dev",
                 commands: tuple[str, ...] = (PASSING,), guard: str = GUARD) -> dict[str, Any]:
    """A verification record for *verifier* (the keys of the record schema)."""
    item: dict[str, Any] = {"verification_id": binding_id, "verifies": [verifier], "stage": stage, "commands": list(commands), "output_guard": guard}
    return {**item, "proves": list(proves)} if proves else item


def add_fixture(host: Path, **fixture: Any) -> None:
    """Add a fixture (mode ``contract`` unless given) to ``08_fixtures.json`` of *host*."""
    shell = {"mode": "contract", "input": {"method": "GET", "path": "/v1/ping"}, "expected": {"status": 200}, "tag_ref": dict(TAG_REF)}
    edit_doc(host, SPEC_FILES["fixtures"], lambda doc: doc["fixtures"].append({**shell, **fixture}))


def host_with(tmp_path: Path, *bindings: dict[str, Any], keep_example_binding: bool = False, name: str = "host") -> Path:
    """The worked example with code under ``src/`` and the given bindings, committed; the example's own record is dropped unless *keep_example_binding*."""
    host = example_host(tmp_path, name)
    if not keep_example_binding:
        (host / "spec" / "extras" / "verification" / f"{EXAMPLE_BINDING}.json").unlink()
    write(host / "src" / "hello.txt", "hello\n")
    for item in bindings:
        write_binding(records_folder(str(host / "spec")), str(ROOT), item)
    commit_all(host)
    return host


def context(host: Path) -> ProofContext:
    """A fresh proof context on *host* (the code tree and hashes are read when first asked)."""
    spec = str(host / "spec")
    return ProofContext(git_root=str(host), spec_dir=spec, evidence_dir=records_folder(spec))


def run(host: Path, ids: list[str], **given: Any) -> list[Evidence]:
    """Run the bindings *ids* of *host* (``run_bindings``)."""
    spec = str(host / "spec")
    return run_bindings(ids, spec, records_folder(spec), str(host), repo_root=str(ROOT), **given)


def prove(host: Path, obligation: str, cap: str = "dev", **given: Any) -> ProofResult:
    """The proof of *obligation* on *host* as it is now (a new graph and a new context)."""
    return proof(graph_of(host), context(host), obligation, cap, **given)


def binding(host: Path, binding_id: str) -> Binding:
    """The binding *binding_id* of *host*."""
    return binding_of(graph_of(host).by_id[binding_id], graph_of(host))


def attest(host: Path, node_id: str, *, stage: str = "dev", evidence_id: str = "evd-attest-one") -> None:
    """Write an attestation of *node_id* as it is on *host* now: the code tree and the node's content hash of now."""
    ctx = context(host)
    item = {
        "evidence_id": evidence_id, "about": [node_id], "type": "attestation", "stage": stage, "tested_tree": ctx.code_tree,
        "recorded_hashes": {node_id: ctx.content_hashes(graph_of(host))[node_id]}, "git_author": {"name": "Reviewer", "email": "reviewer@example.invalid"},
    }
    write_evidence(records_folder(str(host / "spec")), str(ROOT), item)


def edit_code(host: Path, text: str = "changed\n") -> None:
    """Change the code of *host* (not committed: the code tree sees the working tree)."""
    write(host / "src" / "hello.txt", text)


__all__ = [
    "API", "CRITERION", "REUSED_BINDING", "EXAMPLE_BINDING", "FIXTURE", "GUARD", "INVARIANT", "NFR", "OTHER_FIXTURE", "PASSING", "TP", "add_fixture", "binding",
    "attest", "binding_item", "commit_all", "context", "edit_code", "edit_doc", "graph_of", "host_with", "prove", "run",
]
