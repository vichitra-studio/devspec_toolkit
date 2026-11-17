"""The trace commands of the CLI: ``specdev stale`` (the replay), ``attest`` and ``lock``, and the commands later work items add here.

``cli.py`` registers every command of this module with one call, ``add_trace_parsers``, and runs the handler a parser
names with ``set_defaults(handler=...)``.  To add a command: write its ``run_<name>(args) -> int`` handler here (follow
``graph/commands.py``: a library error carries a finding in ``.error``, the handler prints it and returns 1; exit code 2
is argparse's alone), add its parser in ``add_trace_parsers`` and end that with ``set_defaults(handler=run_<name>)``.
"""
from __future__ import annotations

import argparse
import os
import sys
from contextlib import nullcontext
from typing import Any

from specdev_tools.core.errors import FindingError, make_error
from specdev_tools.core.json_output import format_errors_json
from specdev_tools.graph.commands import add_root_flags, print_json, run_on_graph, usage_error
from specdev_tools.graph.gitview import read_seed_texts, spec_path_in_repo
from specdev_tools.graph.kinds import SEED_STEP
from specdev_tools.graph.model import Graph
from specdev_tools.trace import attest, replay
from specdev_tools.trace.history import OldTextResolver
from specdev_tools.trace.lockfile import Lock, read_lock, with_write_lock, write_lock
from specdev_tools.trace.merge_driver import install_driver, merge_files

STALE_DESCRIPTION = (
    "Show what is still to be re-read after an upstream change: the suspect links (links whose target changed after "
    "the holder accepted them), grouped by owning step in waterfall order, nodes upward first, with the cause and the "
    "nodes the change started from (roots), and the coverage gaps. Links of closed milestones are not listed. "
    "Informational: exit 0 whatever it finds (the gate is spec-check).\n\n"
    "--diff adds, per root, the unified diff of its contract text against the text it had when the link was accepted. "
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
    "listed. A node of a closed milestone is refused (E765). An unknown id is E706, a duplicate id E704, exit 1."
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


def add_trace_parsers(sub: Any) -> None:
    """Register the trace commands (``stale``, ``lock``) on the top-level sub-parsers action *sub*."""
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


def _require_known_step(graph: Graph, step: str) -> None:
    """Raise E706 unless *step* is a step of ``tools/step_order.json``; the message names the known steps."""
    known = sorted((name for name in graph.shape.step_ranks if name != SEED_STEP), key=graph.shape.step_ranks.__getitem__)
    if step not in known:
        raise FindingError(make_error("E706", f"no step {step!r}; known steps: {', '.join(known)}"))


def _stale(args: argparse.Namespace, graph: Graph) -> int:
    spec_root, git_root = os.path.abspath(args.spec_root), os.path.abspath(args.git_root)
    if args.step is not None:
        _require_known_step(graph, args.step)
    lock = read_lock(spec_root)
    seed_texts = read_seed_texts(graph, git_root)
    plan = replay.compute_replay(graph, lock, seed_texts)
    if args.step is not None:
        plan = replay.ReplayPlan(replay.pending_replay(plan, [args.step]))
    diffs = None
    if args.diff:
        resolver = OldTextResolver(graph, git_root=git_root, spec_root=spec_root, repo_root=os.path.abspath(args.repo_root))
        diffs = replay.root_diffs(graph, lock, plan, seed_texts, resolver)
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


def _attest_prune(args: argparse.Namespace, graph: Graph, spec_root: str) -> int:
    write = not args.dry_run
    with with_write_lock(spec_root) if write else nullcontext():
        lock, dropped = attest.prune_orphans(graph, read_lock(spec_root))
        if write and dropped:
            write_lock(spec_root, lock)
    if args.json_output:
        print_json(attest.prune_to_dict(dropped, written=write and bool(dropped)))
    else:
        print(attest.prune_text(dropped, written=write))
    return 0


def _attest_preview_diffs(args: argparse.Namespace, graph: Graph, spec_root: str, git_root: str, plan: attest.AttestPlan) -> list[replay.RootDiff]:
    """What changed above the suspect links of *plan*, read from git history."""
    resolver = OldTextResolver(graph, git_root=git_root, spec_root=spec_root, repo_root=os.path.abspath(args.repo_root))
    return replay.root_diffs(graph, read_lock(spec_root), attest.suspect_view(plan), read_seed_texts(graph, git_root), resolver)


def _attest_links(args: argparse.Namespace, graph: Graph, spec_root: str, git_root: str) -> int:
    seed_texts = read_seed_texts(graph, git_root)
    write = args.yes and not args.dry_run

    def plan_for(lock: Lock) -> attest.AttestPlan:
        if args.step is not None:
            return attest.plan_step_attest(graph, lock, seed_texts, args.step)
        return attest.plan_node_attest(graph, lock, seed_texts, args.node_id, field=args.field, target=args.target)

    with with_write_lock(spec_root) if write else nullcontext():
        lock = read_lock(spec_root)
        plan = plan_for(lock)
        if write and plan.links:
            write_lock(spec_root, attest.apply_attest(lock, plan))
    diffs = None if write else _attest_preview_diffs(args, graph, spec_root, git_root, plan)
    if args.json_output:
        print_json(attest.plan_to_dict(plan, written=write and bool(plan.links), diffs=diffs))
    elif plan.links or not plan.blocked:
        print(attest.render_text(plan, written=write, diffs=diffs))
    if plan.blocked and not args.json_output:
        print(attest.blocked_error(plan).render(), file=sys.stderr)
    return 1 if plan.blocked else 0


def _attest(args: argparse.Namespace, graph: Graph) -> int:
    problem = _attest_flags_problem(args)
    if problem is not None:
        return usage_error("attest", problem)
    spec_root, git_root = os.path.abspath(args.spec_root), os.path.abspath(args.git_root)
    if args.prune:
        return _attest_prune(args, graph, spec_root)
    if args.step is not None:
        _require_known_step(graph, args.step)
    return _attest_links(args, graph, spec_root, git_root)


def run_attest(args: argparse.Namespace) -> int:
    """Run ``specdev attest`` on the parsed *args*; returns the exit code."""
    return run_on_graph("attest", args, lambda graph: _attest(args, graph))


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
