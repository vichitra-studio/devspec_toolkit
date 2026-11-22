"""``specdev release prep``: run what the release gate will ask for and say what is left.

On a branch that is about to be released, the dev- and CI-stage bindings whose evidence is missing, failed or stale for the code tree
checked out are run (``verify.run``, at stage ``ci``) and their evidence is written under ``spec/extras/verification/``.  A binding that
already has valid evidence for this code tree (``proof.validity``) is not run again, so a second run on the same tree runs nothing.  Then
the release gate runs once (``release.gate``) and what it still finds is listed as what is left.  Nothing is committed, pushed or tagged:
the workflow job or the person commits the evidence.  Evidence under ``spec/extras/`` is outside the code tree, so writing it does not
change the tree it records.

Exit 0: every binding run passed (also when nothing needed to run); 1: a binding failed, or a refusal of the run (E520, E706, E332,
E708, E769) or of the gate is reported; 2: a usage error.  The gate's findings are listed and do not change the exit code.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from specdev_tools.graph.commands import print_json, resolve_git_root, run_on_graph
from specdev_tools.graph.model import Graph
from specdev_tools.graph.stages import CI_STAGE
from specdev_tools.proof.validity import ProofContext, evidence_for, evidence_valid
from specdev_tools.release.gate import ReleaseGateResult, run_release_gate
from specdev_tools.release.status_sections import CanonDirOf
from specdev_tools.verify.records import Evidence, all_bindings, records_folder
from specdev_tools.verify.run import run_bindings, selected_ids

EXIT_FAILED = 1


def _already_proven(graph: Graph, ctx: ProofContext) -> set[str]:
    """The ids of the bindings with evidence that proves them now (same code tree, hashes and versions; stage at least the binding's)."""
    return {
        binding.id
        for binding in all_bindings(graph)
        if any(evidence_valid(item, binding, graph, ctx).valid for item in evidence_for(binding, ctx))
    }


def _result_line(evidence: Evidence) -> str:
    if evidence.passed:
        return f"  PASS {evidence.about[0]} ({evidence.evidence_id})"
    reason = "guard not matched" if evidence.exit_code == 0 else f"exit {evidence.exit_code}"
    return f"  FAIL {evidence.about[0]} ({evidence.evidence_id}): {reason}"


def _text(proven: list[str], results: list[Evidence], gate: ReleaseGateResult) -> str:
    failed = sum(1 for item in results if not item.passed)
    lines = [f"release prep: {len(results)} binding(s) run, {len(results) - failed} passed, {failed} failed; {len(proven)} already proven for this code tree"]
    if proven:
        lines.append("already proven: " + ", ".join(proven))
    lines.extend(_result_line(item) for item in results)
    if results:
        lines.append("the evidence is written under spec/extras/verification/ and not committed: commit it through the branch")
    if gate.errors:
        lines.append(f"left for the release gate: {len(gate.errors)} error(s)")
        lines.extend(f"  {error.render()}" for error in gate.errors)
    elif results:
        lines.append("left for the release gate: nothing, once the evidence is committed (the cut refuses a tree that is not clean, E910)")
    else:
        lines.append("left for the release gate: nothing blocks the release")
    return "\n".join(lines)


def _json(proven: list[str], todo: list[str], results: list[Evidence], gate: ReleaseGateResult) -> dict[str, Any]:
    return {
        "command": "release prep",
        "stage": CI_STAGE,
        "run": todo,
        "already_proven": proven,
        "evidence": [item.evidence_id for item in results],
        "passed": [item.about[0] for item in results if item.passed],
        "failed": [{"binding": item.about[0], "evidence": item.evidence_id, "exit_code": item.exit_code, "guard_matched": item.guard_matched} for item in results if not item.passed],
        "left": [error.render() for error in gate.errors],
        "warnings": [warning.render() for warning in gate.warnings],
        "notes": [*gate.notes, *(note for item in results for note in item.notes)],
    }


def _prep(args: argparse.Namespace, graph: Graph, canon_dir_of: CanonDirOf) -> int:
    spec_root, repo_root, git_root = os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), resolve_git_root(args)
    evidence_dir = records_folder(spec_root)
    ctx = ProofContext(git_root, spec_root, evidence_dir)
    ids = selected_ids(graph, every=True, milestone=None, stage=CI_STAGE, only_stage=False)
    holding = _already_proven(graph, ctx)
    proven, todo = [i for i in ids if i in holding], [i for i in ids if i not in holding]
    results = run_bindings(todo, spec_root, evidence_dir, git_root, record=True, stage=CI_STAGE, only_stage=False, repo_root=repo_root, graph=graph) if todo else []
    canon = canon_dir_of(git_root=git_root, spec_root=spec_root, spec_dir=spec_root)
    gate = run_release_gate(repo_root, spec_root, git_root, spec_root, canon)
    if args.json_output:
        print_json(_json(proven, todo, results, gate))
    else:
        print(_text(proven, results, gate), file=sys.stdout)
    return EXIT_FAILED if any(not item.passed for item in results) else 0


def run_release_prep(args: argparse.Namespace, canon_dir_of: CanonDirOf) -> int:
    """Run ``specdev release prep`` on the parsed *args*; returns the exit code (0 nothing failed, 1 a binding failed or a refusal, 2 usage)."""
    return run_on_graph("release prep", args, lambda graph: _prep(args, graph, canon_dir_of))
