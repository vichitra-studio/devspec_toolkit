"""The trace commands of the CLI: ``specdev stale`` (the replay), and the commands later work items add here.

``cli.py`` registers every command of this module with one call, ``add_trace_parsers``, and runs the handler a parser
names with ``set_defaults(handler=...)``.  To add a command: write its ``run_<name>(args) -> int`` handler here (follow
``graph/commands.py``: a library error carries a finding in ``.error``, the handler prints it and returns 1; exit code 2
is argparse's alone), add its parser in ``add_trace_parsers`` and end that with ``set_defaults(handler=run_<name>)``.
"""
from __future__ import annotations

import argparse
import os
from typing import Any

from specdev_tools.graph.commands import add_root_flags, print_json, run_on_graph
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.graph.model import Graph
from specdev_tools.trace import replay
from specdev_tools.trace.history import OldTextResolver
from specdev_tools.trace.lockfile import read_lock

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


def add_trace_parsers(sub: Any) -> None:
    """Register the trace commands (``stale``) on the top-level sub-parsers action *sub*."""
    stale = sub.add_parser("stale", help="List the pending replay by step: suspect links and coverage gaps", description=STALE_DESCRIPTION)
    stale.add_argument("--step", metavar="NN", help="Only the replay of this step: the suspect links its nodes hold (what changed above them)")
    stale.add_argument("--diff", action="store_true", help="Add, per root, the diff of its contract text against the text the link was accepted with (reads git history)")
    add_root_flags(stale)
    stale.set_defaults(handler=run_stale)


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
