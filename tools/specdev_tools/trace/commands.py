"""The trace commands of the CLI: ``specdev stale`` (the replay), and the commands later work items add here.

``cli.py`` registers every command of this module with one call, ``add_trace_parsers``, and runs the handler a parser
names with ``set_defaults(handler=...)``.  To add a command: write its ``run_<name>(args) -> int`` handler here (follow
``graph/commands.py``: a library error carries a finding in ``.error``, the handler prints it and returns 1; exit code 2
is argparse's alone), add its parser in ``add_trace_parsers`` and end that with ``set_defaults(handler=run_<name>)``.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from specdev_tools.core.errors import FindingError
from specdev_tools.core.json_output import format_errors_json
from specdev_tools.graph.commands import add_root_flags, print_json, run_on_graph
from specdev_tools.graph.gitview import read_seed_texts, spec_path_in_repo
from specdev_tools.graph.model import Graph
from specdev_tools.trace import replay
from specdev_tools.trace.history import OldTextResolver
from specdev_tools.trace.lockfile import read_lock
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


def _stale(args: argparse.Namespace, graph: Graph) -> int:
    spec_root, git_root = os.path.abspath(args.spec_root), os.path.abspath(args.git_root)
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
