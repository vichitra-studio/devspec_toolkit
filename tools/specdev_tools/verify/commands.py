"""The verify commands of the CLI: ``specdev verify bind`` and ``specdev verify run``.

``cli.py`` registers them with one call, ``add_verify_parsers``; each parser names its handler with ``set_defaults``.  A
handler returns the process exit code: 0 done, 1 refused or a binding failed, 2 a usage error (argparse's, and a run
that names no binding).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from typing import Any

from specdev_tools.graph.commands import add_root_flags, print_json, resolve_git_root, run_on_graph, usage_error
from specdev_tools.graph.model import Graph
from specdev_tools.proof.stages import STAGES
from specdev_tools.trace.writing import locked_graph
from specdev_tools.verify.bind import BindRequest, BindResult, apply_bind
from specdev_tools.verify.code_tree import submodule_warnings
from specdev_tools.trace.records import RECORDS_DIR
from specdev_tools.verify.records import Evidence, records_folder
from specdev_tools.verify.run import run_bindings, selected_ids

VERIFY_DESCRIPTION = (
    "Bind verifiers to commands and run them.\n\n"
    "Subcommands:\n"
    "  bind <verifier-id> --command CMD --guard REGEX   Write the verification record of a fixture, a job or a rule\n"
    "  run [<binding-id> ...] [--all | --milestone ID]  Run bindings and write their evidence"
)

BIND_DESCRIPTION = (
    "Bind a verifier (an 08 fixture, a 12 job or a step-10 rule) to the commands that prove it and the output guard they must "
    "print: writes spec/extras/verification/<binding-id>.json, never a spec file. One binding covers one verifier; --proves "
    "lists the nodes of that verifier the binding proves (default: all of them) and the binding's stage is the highest stage "
    "those nodes need (a --stage that differs is E330). A verifier whose nodes need different stages needs one binding per "
    "stage: pass --proves for each. --guard is required (E332 when missing or not a regular expression); a guard that matches "
    "empty output is accepted with a note. Binding the same verifier and nodes again replaces the record; another binding "
    "that proves one of the nodes is E333. A manual fixture is not bound (it is attested). Exit 0 written, 1 refused."
)

RUN_DESCRIPTION = (
    "Run the commands of bindings and write one evidence record per binding and stage (extras/verification/evd-<binding>-<stage>.json; "
    "each run overwrites the last). A binding passes when its commands exit 0 and the output matches its guard; the exit code "
    "is 1 when any binding fails. Name bindings, or take --all, or --milestone ID (the bindings of the verifiers its task "
    "criteria name in verified_by). --stage (default dev) is the stage the run executes in: bindings of that stage or below "
    "run, and a named binding above it is refused; --only-stage keeps the bindings of exactly that stage. Bindings with the "
    "same commands and guard run once. The commands run in a shell in the host root; --timeout SEC kills a command that runs "
    "longer (recorded as exit 124). --no-record writes nothing and the run is the proof. A run that changes the code tree "
    "warns (W351); a submodule with uncommitted content warns (W350). --installed TP=VERSION records the version a deploy "
    "installed instead of the one the working tree declares."
)


def add_verify_parsers(sub: Any) -> None:
    """Register the ``verify`` group (``bind``, ``run``) on the top-level sub-parsers action *sub*."""
    verify = sub.add_parser("verify", help="Bind verifiers to commands; run the bindings", description=VERIFY_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    verify_sub = verify.add_subparsers(dest="verify_cmd", required=True)

    bind = verify_sub.add_parser("bind", help="Write the binding of a fixture, job or rule", description=BIND_DESCRIPTION)
    bind.add_argument("verifier_id", metavar="verifier-id", help="The fixture, job or rule to bind (an id or an alias)")
    bind.add_argument("--command", action="append", required=True, dest="commands", metavar="CMD", help="A shell command to run; repeat for more, they run in order")
    bind.add_argument("--guard", help="Regular expression the output of the commands must match (required)")
    bind.add_argument("--proves", action="extend", nargs="+", metavar="node-id", help="The nodes this binding proves (default: all the verifier's)")
    bind.add_argument("--stage", choices=STAGES, help="The stage of the binding; must be the stage its nodes need (default: that stage)")
    bind.add_argument("--id", dest="record_id", metavar="ver-ID", help="The id of the record (default: made from the verifier's id)")
    add_root_flags(bind)
    bind.set_defaults(handler=run_verify_bind)

    run = verify_sub.add_parser("run", help="Run bindings and write their evidence", description=RUN_DESCRIPTION)
    run.add_argument("binding_ids", nargs="*", metavar="ver-ID", help="The bindings to run")
    run.add_argument("--all", action="store_true", dest="every", help="Run every binding")
    run.add_argument("--milestone", metavar="ms-ID", help="Run the bindings of the verifiers this milestone's task criteria name in verified_by")
    run.add_argument("--stage", choices=STAGES, default=STAGES[0], help="The stage this run executes in (default dev)")
    run.add_argument("--only-stage", action="store_true", dest="only_stage", help="Run only the bindings whose stage is exactly --stage")
    run.add_argument("--no-record", action="store_true", dest="no_record", help="Write no evidence; the run is the proof")
    run.add_argument("--installed", action="extend", nargs="+", metavar="TP=VERSION", help="The version of a third party as installed, instead of the declared one")
    run.add_argument("--timeout", type=float, metavar="SEC", help="Kill a command that runs longer than this, per command")
    add_root_flags(run)
    run.set_defaults(handler=run_verify_run)


def _bind_text(result: BindResult) -> str:
    plan = result.plan
    verb = "replaced" if plan.replaced else "written"
    lines = [f"{plan.verifier}: binding {plan.record_id} {verb} (stage {plan.stage}, {RECORDS_DIR}/{result.file})"]
    lines.append(f"  proves: {', '.join(plan.proves)}" if plan.proves else "  proves: nothing")
    needs = ", ".join(f"{node_id} needs {stage}" for node_id, stage in plan.reasoning)
    lines.append(f"  stage {plan.stage} is the highest stage the proved nodes need ({needs})" if needs else f"  stage {plan.stage}: no proved node needs a later stage")
    lines.extend(f"  note: {note}" for note in plan.notes)
    return "\n".join(lines)


def _bind_json(result: BindResult) -> dict[str, Any]:
    plan = result.plan
    return {
        "command": "verify bind",
        "record_id": plan.record_id,
        "file": f"{RECORDS_DIR}/{result.file}",
        "verifier": plan.verifier,
        "stage": plan.stage,
        "proves": list(plan.proves),
        "reasoning": [{"node": node_id, "stage": stage} for node_id, stage in plan.reasoning],
        "replaced": plan.replaced,
        "notes": list(plan.notes),
    }


def _bind(args: argparse.Namespace) -> int:
    request = BindRequest(args.verifier_id, tuple(args.commands), args.guard, tuple(args.proves or ()), args.stage, args.record_id)
    spec_root = os.path.abspath(args.spec_root)
    repo_root = os.path.abspath(args.repo_root)
    with locked_graph(spec_root, repo_root, "verify bind") as graph:
        result = apply_bind(graph, spec_root, repo_root, request)
    if args.json_output:
        print_json(_bind_json(result))
    else:
        print(_bind_text(result))
    return 0


def run_verify_bind(args: argparse.Namespace) -> int:
    """Run ``specdev verify bind`` on the parsed *args*; returns the exit code (0 written, 1 refused)."""
    return run_on_graph("verify bind", args, lambda _graph: _bind(args))


def _installed_overrides(pairs: Sequence[str]) -> dict[str, str] | None:
    """``{third party: version}`` from ``TP=VERSION`` items; ``None`` when one is not of that form."""
    overrides: dict[str, str] = {}
    for pair in pairs:
        name, separator, version = pair.partition("=")
        if not separator or not name or not version:
            return None
        overrides[name] = version
    return overrides


def _evidence_line(evidence: Evidence) -> str:
    verdict = "PASS" if evidence.passed else "FAIL"
    reason = "" if evidence.passed else f" ({'guard not matched' if evidence.exit_code == 0 else f'exit {evidence.exit_code}'})"
    return f"{verdict} {evidence.about[0]} at {evidence.stage}{reason}"


def _run_text(results: Sequence[Evidence], *, recorded: bool) -> str:
    failed = sum(1 for evidence in results if not evidence.passed)
    lines = [_evidence_line(evidence) for evidence in results]
    lines.append(f"{len(results)} run, {len(results) - failed} passed, {failed} failed" + ("" if recorded else " (nothing recorded)"))
    return "\n".join(lines)


def _run_json(results: Sequence[Evidence], stage: str, warnings: Sequence[str], *, recorded: bool) -> dict[str, Any]:
    return {
        "command": "verify run",
        "stage": stage,
        "recorded": recorded,
        "passed": sum(1 for evidence in results if evidence.passed),
        "failed": sum(1 for evidence in results if not evidence.passed),
        "results": [{**evidence.to_item(), "passed": evidence.passed} for evidence in results],
        "warnings": [*warnings, *(note for evidence in results for note in evidence.notes)],
    }


def _binding_ids(args: argparse.Namespace, graph: Graph) -> list[str] | None:
    """The bindings the run takes, or ``None`` when the arguments name no selection, or more than one."""
    chosen = [bool(args.binding_ids), args.every, args.milestone is not None]
    if chosen.count(True) != 1:
        return None
    if args.binding_ids:
        return list(args.binding_ids)
    return selected_ids(graph, every=args.every, milestone=args.milestone, stage=args.stage, only_stage=args.only_stage)


def _run(args: argparse.Namespace, graph: Graph) -> int:
    ids = _binding_ids(args, graph)
    overrides = _installed_overrides(args.installed or ())
    if ids is None:
        return usage_error("verify run", "name bindings, or give exactly one of --all and --milestone")
    if overrides is None:
        return usage_error("verify run", "--installed takes TP=VERSION")
    spec_root, git_root = os.path.abspath(args.spec_root), resolve_git_root(args)
    warnings = [error.render() for error in submodule_warnings(git_root)]
    record = not args.no_record
    results = run_bindings(
        ids, spec_root, records_folder(spec_root), git_root, record, args.stage, args.only_stage,
        timeout=args.timeout, installed=overrides, repo_root=os.path.abspath(args.repo_root), graph=graph,
    )
    if args.json_output:
        print_json(_run_json(results, args.stage, warnings, recorded=record))
    else:
        print(_run_text(results, recorded=record))
        for line in (*warnings, *(note for evidence in results for note in evidence.notes)):
            print(line, file=sys.stderr)
    return 1 if any(not evidence.passed for evidence in results) else 0


def run_verify_run(args: argparse.Namespace) -> int:
    """Run ``specdev verify run`` on the parsed *args*; returns the exit code (0 all passed, 1 a binding failed or a refusal, 2 usage)."""
    return run_on_graph("verify run", args, lambda graph: _run(args, graph))
