"""The trace commands of the CLI: ``specdev stale`` (the replay), ``attest``, ``lock`` and ``step``, and the commands later work items add here.

``cli.py`` registers every command of this module with one call, ``add_trace_parsers``, and runs the handler a parser
names with ``set_defaults(handler=...)``.  To add a command: write its ``run_<name>(args) -> int`` handler here (follow
``graph/commands.py``: a library error carries a finding in ``.error``, the handler prints it and returns 1; exit code 2
is argparse's alone), add its parser in ``add_trace_parsers`` and end that with ``set_defaults(handler=run_<name>)``.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.errors import FindingError
from specdev_tools.core.json_output import format_errors_json
from specdev_tools.graph.commands import add_root_flags, print_json, run_on_graph, usage_error
from specdev_tools.graph.gitview import read_seed_texts, spec_path_in_repo
from specdev_tools.graph.model import Graph
from specdev_tools.graph.queries import require_known_step
from specdev_tools.trace import attest, coverage, replay, step_ready
from specdev_tools.trace.history import OldTextResolver
from specdev_tools.trace.id_write_commands import render_text as render_write, result_to_dict as write_to_dict
from specdev_tools.trace.lockfile import Lock, locked_graph, read_lock, refuse_unreadable, write_lock
from specdev_tools.trace.merge_driver import install_driver, merge_files
from specdev_tools.trace.step_create import StepCreateRequest, create_step

STALE_DESCRIPTION = (
    "Show what is still to be re-read after an upstream change: the suspect links (links whose target changed after "
    "the holder accepted them), grouped by owning step in waterfall order, nodes upward first, with the cause and the "
    "nodes the change started from (roots), and the coverage gaps. Links of closed milestones are not listed. "
    "Informational: exit 0 whatever it finds (the gate is spec-check).\n\n"
    "--diff adds, per root, the unified diff of its contract text against the text it had when the link was accepted "
    "(one diff per accepted version, with the holders named, when holders accepted different ones; a line says so when "
    "the change above was already accepted by the links that point at it). "
    "That text is recovered from git: the commits that touched the root's file are walked newest first (at most 50) "
    "and the first whose content hash equals the one in the lock is used. The hash is recomputed with the current "
    "contract fields, so after a change of those fields, or for a history from before the node model, no commit matches "
    "and the diff says 'no earlier version found'; a link stamped by migration says so, and a folder that is not a git "
    "repository, or a shallow clone without the commits, says 'history unavailable'. Without --diff history is not read."
)

ATTEST_DESCRIPTION = (
    "Accept the links of a node as they are now: write each link's lock entry with the state its target has today, so "
    "the link stops being suspect. The command takes no stamp from the user; it always writes the current one.\n\n"
    "  attest <node-id>      the suspect links the node holds, and its links that have no lock entry yet (the entry is\n"
    "                        created) or still carry the migration baseline marker; --field and --target narrow it\n"
    "  attest --step NN      every node of step NN that holds a suspect link, upward first in one run\n"
    "  attest --prune        remove the lock entries whose link no longer exists\n\n"
    "Without --yes the command only prints what it would write (and, per suspect link, what changed above it) and exits "
    "0; --yes writes; --dry-run never writes, with or without --yes. --prune writes at once, without --yes.\n\n"
    "A node can be attested only when none of the nodes it links to is itself a suspect node: attest those first. "
    "Otherwise the node is refused (E764), exit 1; with --step the nodes that can be attested are, and the rest are "
    "listed. A node of a closed milestone is refused (E765). An unknown id is E706, a duplicate id E704, exit 1. While a spec "
    "file cannot be read, --yes, --dry-run and --prune are refused (E520), exit 1, and nothing is written."
)

LOCK_DESCRIPTION = (
    "Work with the trace lock file (<spec>/extras/trace.lock.json).\n\n"
    "Subcommands:\n"
    "  merge BASE OURS THEIRS PATH   The git merge driver: merge the three versions entry by entry and write the result\n"
    "                                to OURS; exit 0 merged, 1 left as a conflict (a version is not a valid lock). When\n"
    "                                both sides changed one entry the older chain stamp wins, so the link stays suspect.\n"
    "  install-driver                Set the driver up in this clone: one line in .git/info/attributes and two\n"
    "                                'git config merge.specdev-trace-lock.*' keys; safe to run again. Git config is\n"
    "                                per clone, so run it once in each fresh clone."
)

STEP_DESCRIPTION = (
    "Create the artifact of a step and ask whether a step may start.\n\n"
    "Subcommands:\n"
    "  create NN --from DRAFT   Write spec/<NN file> from the draft artifact (the whole JSON document; ids of\n"
    "                           sub-items may be left out and are minted). The draft is checked against the step's\n"
    "                           schema, every link must resolve, and the lock gets an entry for every link. Prints each\n"
    "                           link target with its contract text. Refused (E767, exit 1) when the step already has a\n"
    "                           file (edit it with `specdev json patch|insert|delete --id`) or is 13a or 16. Writes\n"
    "                           nothing with --dry-run.\n"
    "  ready NN                 Exit 0 when step NN may start; exit 1 (E773) when a step above it is missing or has\n"
    "                           pending replay (a suspect link or a coverage gap), listing each blocker and the step to\n"
    "                           replay first. An unknown step is E706, exit 1."
)


COVERAGE_DESCRIPTION = (
    "Show how the obligations of the graph are linked, read from the reverse index. Information only: exit 0 whatever "
    "it finds (no rule requires an FR to have an API or a capability to have an FR; the role-rule findings are the "
    "gate of spec-check).\n\n"
    "Default view: the FRs with an API, the FRs with a fixture (a fixture that verifies one of the FR's criteria) and "
    "the capabilities with an FR, each as linked/total/ratio with the ids that are not linked; the criteria that have "
    "a current refinement (a step-14 task criterion that refines it, whose lock entry still holds the criterion's "
    "present content hash); the exempt nodes (lifecycle not_applicable, scope later or out), which are left out of every "
    "count; and the role findings of the coverage-gap seam, grouped by owning step.\n\n"
    "--by fr prints the matrix instead: per in-scope FR, the nodes that link the FR or one of its criteria directly, "
    "grouped by kind, each with 'current' (the lock entry's content hash equals the target's now), 'suspect' and "
    "'historical'; and per criterion 'refined': current, stale (refinements exist, none current) or none. Direct "
    "links only, nothing through an API."
)


def add_trace_parsers(sub: Any) -> None:
    """Register the trace commands (``stale``, ``attest``, ``lock``, ``step``, ``coverage``) on the top-level sub-parsers action *sub*."""
    stale = sub.add_parser("stale", help="List the pending replay by step: suspect links and coverage gaps", description=STALE_DESCRIPTION)
    stale.add_argument("--step", metavar="NN", help="Only the replay of this step: the suspect links its nodes hold (what changed above them)")
    stale.add_argument("--diff", action="store_true", help="Add, per root, the diff of its contract text against the text the link was accepted with (reads git history)")
    add_root_flags(stale)
    stale.set_defaults(handler=run_stale)

    attest_p = sub.add_parser(
        "attest", help="Accept the suspect links of a node, or prune lock entries without a link", description=ATTEST_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    what = attest_p.add_mutually_exclusive_group(required=True)
    what.add_argument("node_id", nargs="?", metavar="node-id", help="Node whose links are attested (an id or an alias)")
    what.add_argument("--step", metavar="NN", help="Attest every node of this step that holds a suspect link, upward first")
    what.add_argument("--prune", action="store_true", help="Remove the lock entries that have no link any more (writes at once)")
    attest_p.add_argument("--field", help="Only the links of this field")
    attest_p.add_argument("--target", help="Only the links to this target (id or alias)")
    attest_p.add_argument("--yes", action="store_true", help="Write the lock; without it the command only prints")
    attest_p.add_argument("--dry-run", action="store_true", dest="dry_run", help="Print what would be written and write nothing, also with --yes and --prune")
    add_root_flags(attest_p)
    attest_p.set_defaults(handler=run_attest)

    lock = sub.add_parser("lock", help="Merge and set up the trace lock file", description=LOCK_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    lock_sub = lock.add_subparsers(dest="lock_cmd", required=True)
    merge = lock_sub.add_parser("merge", help="Git merge driver of the lock file", description="Merge the lock versions BASE, OURS and THEIRS entry by entry; the result replaces OURS.")
    merge.add_argument("base", metavar="BASE", help="Common ancestor version (git's %%O)")
    merge.add_argument("ours", metavar="OURS", help="Current version, overwritten with the result (git's %%A)")
    merge.add_argument("theirs", metavar="THEIRS", help="Other branch's version (git's %%B)")
    merge.add_argument("pathname", metavar="PATH", help="Repository path of the lock file, used in messages (git's %%P)")
    merge.set_defaults(handler=run_lock_merge)
    install = lock_sub.add_parser("install-driver", help="Install the merge driver in this clone", description="Install the lock merge driver in the clone at --git-root (idempotent).")
    install.add_argument("--driver-command", required=True, help="Command git runs, before the four file arguments, for example '<venv>/bin/specdev lock merge'; quote what a shell needs quoted")
    add_root_flags(install)
    install.set_defaults(handler=run_lock_install_driver)

    step = sub.add_parser("step", help="Create the artifact of a step; check that a step may start", description=STEP_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    step_sub = step.add_subparsers(dest="step_cmd", required=True)
    create = step_sub.add_parser("create", help="Write the artifact of a step from a draft", description="Write the artifact of step NN from the draft file given with --from.")
    create.add_argument("step", metavar="NN", help="The step to create, for example 04 or 02a")
    create.add_argument("--from", required=True, dest="draft", metavar="DRAFT", help="JSON file holding the whole artifact; ids of sub-items may be left out")
    create.add_argument("--dry-run", action="store_true", dest="dry_run", help="Print the same report and write nothing")
    add_root_flags(create)
    create.set_defaults(handler=run_step_create)
    ready = step_sub.add_parser("ready", help="Check that nothing above a step is still to be replayed", description="Exit 0 when step NN may start, 1 (E773) when a step above it is missing or has pending replay.")
    ready.add_argument("step", metavar="NN", help="The step to check, for example 06")
    add_root_flags(ready)
    ready.set_defaults(handler=run_step_ready)

    coverage_p = sub.add_parser(
        "coverage", help="Show link counts and the FR matrix over the reverse index (information only)", description=COVERAGE_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    coverage_p.add_argument("--by", choices=["fr"], help="Print the matrix of the FRs: their criteria and the nodes that link them directly")
    add_root_flags(coverage_p)
    coverage_p.set_defaults(handler=run_coverage)


@dataclass(frozen=True)
class _View:
    """What a trace command reads, once: the graph, the folders, the lock and the seed texts of the graph."""

    graph: Graph
    spec_root: str
    git_root: str
    repo_root: str
    lock: Lock
    seed_texts: dict[str, str]

    def resolver(self) -> OldTextResolver:
        """The resolver of old texts for ``--diff`` and the attest preview."""
        return OldTextResolver(self.graph, git_root=self.git_root, spec_root=self.spec_root, repo_root=self.repo_root)


def _view(args: argparse.Namespace, graph: Graph) -> _View:
    spec_root, git_root = os.path.abspath(args.spec_root), os.path.abspath(args.git_root)
    return _View(graph, spec_root, git_root, os.path.abspath(args.repo_root), read_lock(spec_root), read_seed_texts(graph, git_root))


@contextmanager
def _locked_view(args: argparse.Namespace, what: str) -> Iterator[_View]:
    """The view of a command *what* that writes: the write lock is held and the graph is built under it (``locked_graph``)."""
    with locked_graph(os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), what) as graph:
        yield _view(args, graph)


def _stale(args: argparse.Namespace, graph: Graph) -> int:
    if args.step is not None:
        require_known_step(graph, args.step)
    view = _view(args, graph)
    plan = replay.compute_replay(graph, view.lock, view.seed_texts)
    if args.step is not None:
        plan = replay.ReplayPlan(replay.pending_replay(plan, [args.step]))
    diffs = replay.root_diffs(graph, view.lock, plan, view.seed_texts, view.resolver()) if args.diff else None
    if args.json_output:
        print_json(replay.plan_to_dict(plan, diffs))
    else:
        print(replay.render_text(plan, diffs))
    return 0


def run_stale(args: argparse.Namespace) -> int:
    """Run ``specdev stale`` on the parsed *args*; returns the exit code."""
    return run_on_graph("stale", args, lambda graph: _stale(args, graph))


def _attest_flags_problem(args: argparse.Namespace) -> str | None:
    """The sentence that says which flags of ``attest`` do not go with the chosen mode, or ``None``."""
    narrowing = [flag for flag, given in (("--field", args.field), ("--target", args.target)) if given]
    if args.prune:
        extra = [*narrowing, *(["--yes"] if args.yes else [])]
        return f"--prune cannot be combined with {', '.join(extra)}" if extra else None
    if args.step is not None and narrowing:
        return f"--step cannot be combined with {', '.join(narrowing)}"
    return None


def _attest_prune(args: argparse.Namespace, graph: Graph) -> int:
    write = not args.dry_run
    with _locked_view(args, "attest --prune") if write else nullcontext(_view(args, graph)) as view:
        refuse_unreadable(view.graph, "attest --prune")
        lock, dropped = attest.prune_orphans(view.graph, view.lock)
        if write and dropped:
            write_lock(view.spec_root, lock)
    if args.json_output:
        print_json(attest.prune_to_dict(dropped, written=write and bool(dropped)))
    else:
        print(attest.prune_text(dropped, written=write))
    return 0


def _attest_links(args: argparse.Namespace, graph: Graph) -> int:
    write = args.yes and not args.dry_run
    with _locked_view(args, "attest --yes") if write else nullcontext(_view(args, graph)) as view:
        if args.dry_run:
            refuse_unreadable(view.graph, "attest --dry-run")
        if args.step is not None:
            plan = attest.plan_step_attest(view.graph, view.lock, view.seed_texts, args.step)
        else:
            plan = attest.plan_node_attest(view.graph, view.lock, view.seed_texts, args.node_id, field=args.field, target=args.target)
        if write and plan.links:
            write_lock(view.spec_root, attest.apply_attest(view.lock, plan))
    diffs = None if write else replay.root_diffs(view.graph, view.lock, attest.suspect_view(plan), view.seed_texts, view.resolver())
    if args.json_output:
        print_json(attest.plan_to_dict(plan, written=write and bool(plan.links), diffs=diffs))
    elif plan.links or not plan.blocked:
        print(attest.render_text(plan, written=write, diffs=diffs, dry_run=args.dry_run))
    if plan.blocked and not args.json_output:
        print(attest.blocked_error(plan).render(), file=sys.stderr)
    return 1 if plan.blocked else 0


def _attest(args: argparse.Namespace, graph: Graph) -> int:
    problem = _attest_flags_problem(args)
    if problem is not None:
        return usage_error("attest", problem)
    if args.prune:
        return _attest_prune(args, graph)
    if args.step is not None:
        require_known_step(graph, args.step)
    return _attest_links(args, graph)


def run_attest(args: argparse.Namespace) -> int:
    """Run ``specdev attest`` on the parsed *args*; returns the exit code."""
    return run_on_graph("attest", args, lambda graph: _attest(args, graph))


def _step_create(args: argparse.Namespace, graph: Graph) -> int:
    require_known_step(graph, args.step)
    result = create_step(
        graph,
        os.path.abspath(args.spec_root),
        os.path.abspath(args.repo_root),
        os.path.abspath(args.git_root),
        StepCreateRequest(args.step, args.draft),
        dry_run=args.dry_run,
    )
    if args.json_output:
        print_json(write_to_dict(result))
    else:
        print(render_write(result))
    return 0


def run_step_create(args: argparse.Namespace) -> int:
    """Run ``specdev step create`` on the parsed *args*; returns the exit code (0 written, 1 refused)."""
    return run_on_graph("step create", args, lambda graph: _step_create(args, graph))


def _step_ready(args: argparse.Namespace, graph: Graph) -> int:
    require_known_step(graph, args.step)
    view = _view(args, graph)
    plan = replay.compute_replay(graph, view.lock, view.seed_texts)
    required = step_ready.required_spec_inputs(view.repo_root, args.step)
    readiness = step_ready.check_ready(graph, plan, args.step, required, step_ready.present_steps(graph, view.spec_root))
    errors = [] if readiness.ready else [step_ready.not_ready_error(readiness)]
    if args.json_output:
        print(format_errors_json(errors, context={"command": "step ready", **step_ready.to_dict(readiness)}))
    else:
        print(step_ready.render_text(readiness))
        for error in errors:
            print(error.render(), file=sys.stderr)
    return 0 if readiness.ready else 1


def run_step_ready(args: argparse.Namespace) -> int:
    """Run ``specdev step ready`` on the parsed *args*; returns the exit code (0 ready, 1 not ready: E773)."""
    return run_on_graph("step ready", args, lambda graph: _step_ready(args, graph))


def _coverage(args: argparse.Namespace, graph: Graph) -> int:
    view = _view(args, graph)
    if args.by == "fr":
        matrix, exempt = coverage.build_fr_matrix(graph, view.lock, view.seed_texts), tuple(coverage.exempt_nodes(graph))
        if args.json_output:
            print_json(coverage.matrix_to_dict(matrix, exempt))
        else:
            print(coverage.render_matrix(matrix, exempt))
        return 0
    report = coverage.build_report(graph, view.lock, view.seed_texts)
    if args.json_output:
        print_json(coverage.report_to_dict(report))
    else:
        print(coverage.render_report(report))
    return 0


def run_coverage(args: argparse.Namespace) -> int:
    """Run ``specdev coverage`` on the parsed *args*; returns the exit code (0: it only informs)."""
    return run_on_graph("coverage", args, lambda graph: _coverage(args, graph))


def _report_finding(error: FindingError, command: str, json_output: bool) -> int:
    """Print the finding of a refused command (text on stderr, JSON envelope on stdout); the exit code 1."""
    if json_output:
        print(format_errors_json([error.error], context={"command": command}))
    else:
        print(error.error.render(), file=sys.stderr)
    return 1


def run_lock_merge(args: argparse.Namespace) -> int:
    """Run ``specdev lock merge`` on the parsed *args*: 0 when the merged lock is in OURS, 1 when git keeps the conflict."""
    try:
        merge_files(args.base, args.ours, args.theirs, args.pathname)
    except FindingError as exc:
        return _report_finding(exc, "lock merge", False)
    return 0


def run_lock_install_driver(args: argparse.Namespace) -> int:
    """Run ``specdev lock install-driver`` on the parsed *args*; returns the exit code."""
    try:
        git_root = os.path.abspath(args.git_root)
        result = install_driver(git_root, spec_path_in_repo(os.path.abspath(args.spec_root), git_root), args.driver_command)
    except FindingError as exc:
        return _report_finding(exc, "lock install-driver", args.json_output)
    if args.json_output:
        print_json({"attributes_file": result.attributes_file, "attribute_line": result.attribute_line, "driver": result.driver_config})
    else:
        print(f"lock merge driver installed: {result.attribute_line} in {result.attributes_file}; driver: {result.driver_config}")
    return 0
