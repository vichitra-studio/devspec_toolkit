"""The graph commands of the CLI: ``specdev node`` (``show``, ``candidates``, ``status``), ``trace`` and ``diff``.

``cli.py`` only registers the parsers (``add_graph_parsers``) and calls the ``run_*`` handlers; every handler returns the
process exit code.  ``node`` is a REMAINDER group like ``json``: the top-level parser hands it the raw tokens and
``build_node_parser`` parses them here, so ``node <id>`` and ``node show <id>`` both work.  A library error carries one
finding in ``.error``; a handler prints it (text on stderr, or the ``--json`` envelope on stdout) and returns 1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, replace
from typing import Any

from specdev_tools.core.errors import FindingError, SpecError, ensure_spec_errors, make_error
from specdev_tools.core.json_output import format_errors_json
from specdev_tools.core.json_utils import JsonUtilsError
from specdev_tools.core.toolkit_root import detect_toolkit_root
from specdev_tools.graph import queries, recipes, trace
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.diff import diff_refs, diff_to_dict
from specdev_tools.graph.diff import render_text as diff_text
from specdev_tools.graph.lifecycle import NOT_APPLICABLE_GUIDANCE, set_lifecycle
from specdev_tools.graph.model import LIFECYCLES, Graph

NODE_SUBCOMMANDS = ("show", "candidates", "status")
RECIPE_ROLES = ("16a", "16b", "16c")
EXIT_FINDING = 1
EXIT_USAGE = 2


class SpecFolderMissingError(FindingError):
    """The ``--spec-root`` folder does not exist; the E520 finding (the wording of the other commands) is in ``error``."""

    def __init__(self, spec_root: str) -> None:
        super().__init__(make_error("E520", f"UNRESOLVED_INPUT missing_spec_dir {spec_root}"))


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def _add_root_flags(parser: argparse.ArgumentParser) -> None:
    """The flags every graph command takes, so the three-flag default of CLAUDE.md never fails."""
    parser.add_argument("--repo-root", default=".", help="Toolkit root (schema, registry, canon); default '.', or the toolkit submodule found below it")
    parser.add_argument("--spec-root", default="./spec", help="Spec directory of the project (default ./spec)")
    parser.add_argument("--git-root", default=".", help="Host repository root, used by the commands that read git history (default '.')")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print JSON instead of text")


# --- parsers --------------------------------------------------------------------------------------------------------

NODE_DESCRIPTION = (
    "Read nodes of the spec graph and change a node's lifecycle.\n\n"
    "Subcommands:\n"
    "  show <id> [<id> ...]   Show a node: where it is defined, its content, its links in and out (the default:\n"
    "                         'specdev node <id>' is 'specdev node show <id>'; use 'node show <id>' for an id\n"
    "                         that is also a subcommand name)\n"
    "  candidates             List the nodes a link field may point at\n"
    "  status <id> <value>    Set a node's lifecycle (writes the spec file)\n\n"
    "Flags follow the id or the subcommand, as for 'specdev json': 'specdev node <id> --json' works, "
    "'specdev node --json <id>' does not.\n"
    "Run 'specdev node <subcommand> --help' for the flags of one subcommand."
)


def build_node_parser() -> argparse.ArgumentParser:
    """Build the parser of ``specdev node`` (no parsing, no side effects); ``cli.py`` hands it the remainder tokens."""
    parser = argparse.ArgumentParser(
        prog="specdev node", description=NODE_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="node_cmd", required=True)

    show = sub.add_parser("show", help="Show one or more nodes", description="Show nodes of the spec graph by id.")
    show.add_argument("ids", nargs="+", metavar="id", help="Node id (several allowed)")
    show.add_argument("--full", action="store_true", help="Include the content of child nodes (default: child ids only)")
    _add_root_flags(show)

    cand = sub.add_parser(
        "candidates",
        help="List the valid targets of a link field",
        description="List the nodes a link field may point at, for a holder kind (--kind) or for one existing node (--for).",
    )
    holder = cand.add_mutually_exclusive_group(required=True)
    holder.add_argument("--kind", help="Kind of the node that will hold the link")
    holder.add_argument("--for", dest="for_id", metavar="ID", help="Id of the node that holds the link (also leaves out targets it already links to and, in a same-step field, targets that would close a cycle)")
    cand.add_argument("--field", required=True, help="The link field (verb), for example derives_from")
    cand.add_argument("--query", help="Keep candidates whose id or label contains this text")
    cand.add_argument("--limit", type=_positive_int, help="Show at most this many candidates")
    _add_root_flags(cand)

    status = sub.add_parser(
        "status",
        help="Set the lifecycle of a node",
        description=(
            "Set the lifecycle of a node and write it to its spec file. 'active' removes the lifecycle key.\n"
            f"Guidance: {NOT_APPLICABLE_GUIDANCE}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    status.add_argument("id", help="Node id")
    status.add_argument("value", help=f"New lifecycle: {', '.join(LIFECYCLES)}")
    _add_root_flags(status)
    return parser


def add_graph_parsers(sub: Any) -> None:
    """Register ``node``, ``trace`` and ``diff`` on the top-level sub-parsers action *sub*."""
    node = sub.add_parser(
        "node",
        help="Show a node of the spec graph, list link candidates, set a lifecycle",
        description=NODE_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    node.add_argument("args", nargs=argparse.REMAINDER, help="node subcommand and arguments")

    trace_p = sub.add_parser(
        "trace",
        help="Trace a node up (what it derives from) and down (what depends on it), or build a context pack",
        description=(
            "Trace a node through the spec graph. --up follows its links to the nodes above it, --down the nodes "
            "that point at it; without either, both. With --recipe, print the context pack of a role instead."
        ),
    )
    trace_p.add_argument("id", help="Node id to trace (with --recipe: the start node of the pack)")
    trace_p.add_argument("--up", action="store_true", help="Only what the node derives from")
    trace_p.add_argument("--down", action="store_true", help="Only what depends on the node")
    trace_p.add_argument("--depth", type=_positive_int, help="Follow at most this many edges from the node")
    trace_p.add_argument("--kinds", help="Comma-separated kinds to show (the walk still passes through other kinds)")
    trace_p.add_argument("--verbs", help="Comma-separated link fields to follow (default: all)")
    trace_p.add_argument("--no-containment", action="store_true", help="Do not follow the parent / child edge of the JSON tree")
    trace_p.add_argument(
        "--recipe", metavar="ROLE",
        help=f"Print the context pack of this role: {', '.join(RECIPE_ROLES)} (16a: task, 16b: plan item, 16c: roadmap milestone)",
    )
    trace_p.add_argument("--expand", action="store_true", help="With --recipe: add the content of every node of the pack")
    trace_p.add_argument("--since", metavar="REF", help="With --recipe: git ref the 16b dependency report compares against (default: where HEAD left the default branch)")
    _add_root_flags(trace_p)

    diff_p = sub.add_parser(
        "diff",
        help="Compare the spec graph at two git refs",
        description=(
            "Compare the spec graph at two git refs (tags, branches, commits): nodes added, removed, changed, whose "
            "lifecycle or kind changed, grouped by role and kind, with an advisory version bump."
        ),
    )
    diff_p.add_argument("ref_a", metavar="refA", help="The older ref")
    diff_p.add_argument("ref_b", metavar="refB", help="The newer ref")
    _add_root_flags(diff_p)


# --- output ---------------------------------------------------------------------------------------------------------

def _print_json(document: dict[str, Any]) -> None:
    print(json.dumps(document, indent=2))


def _with_unreadable_note(exc: FindingError, unreadable: Sequence[str]) -> SpecError:
    """The finding of *exc* with a sentence that the id may be in a file that could not be read, when *exc* is an unknown-id one."""
    if not unreadable or not exc.unknown_id:
        return exc.error
    note = f"; these files could not be read, so the node may be in one of them: {', '.join(unreadable)}"
    return replace(exc.error, message=exc.error.message + note)


def _report_finding(error: SpecError, command: str, json_output: bool) -> int:
    """Print one finding the way the other commands do (text on stderr, or the JSON envelope on stdout); the exit code."""
    if json_output:
        print(format_errors_json([error], context={"command": command}))
    else:
        print(error.render(), file=sys.stderr)
    return EXIT_FINDING


def _usage_error(command: str, message: str) -> int:
    print(f"specdev {command}: error: {message}", file=sys.stderr)
    return EXIT_USAGE


def _run_guarded(command: str, json_output: bool, action: Callable[[], int], unreadable: Sequence[str] = ()) -> int:
    """Run *action*; a library error with a finding in ``.error`` is reported and becomes exit code 1.

    *unreadable* is read when a finding is reported: the spec files the builder skipped, which an unknown-id finding names.
    """
    try:
        return action()
    except FindingError as exc:
        return _report_finding(_with_unreadable_note(exc, unreadable), command, json_output)
    except JsonUtilsError as exc:
        if json_output:
            return _report_finding(ensure_spec_errors([str(exc)])[0], command, True)
        print(f"specdev {command}: {exc}", file=sys.stderr)
        return EXIT_FINDING


def _load_graph(args: argparse.Namespace) -> Graph:
    """The graph of ``--spec-root``; raises ``SpecFolderMissingError`` when that folder does not exist."""
    spec_root = os.path.abspath(args.spec_root)
    if not os.path.isdir(spec_root):
        raise SpecFolderMissingError(spec_root)
    return build_graph(spec_root, os.path.abspath(args.repo_root))


def _run_on_graph(command: str, args: argparse.Namespace, action: Callable[[Graph], int]) -> int:
    """Load the graph of ``--spec-root`` and run *action* on it, under the one error path of ``_run_guarded``.

    When the builder skipped files, one line on stderr names them and says the answer may be incomplete.
    """
    unreadable: list[str] = []

    def run() -> int:
        graph = _load_graph(args)
        unreadable.extend(error.file for error in graph.load_errors)
        if unreadable:
            print(
                f"specdev {command}: could not read {', '.join(unreadable)}; the answer may be incomplete",
                file=sys.stderr,
            )
        return action(graph)

    return _run_guarded(command, args.json_output, run, unreadable)


# --- node -----------------------------------------------------------------------------------------------------------

def _node_show(args: argparse.Namespace, graph: Graph) -> int:
    report = queries.node_view(graph, args.ids, full=args.full)
    if args.json_output:
        _print_json(queries.node_json(report))
    else:
        print(queries.node_text(report))
    return EXIT_FINDING if report.errors else 0


def _node_candidates(args: argparse.Namespace, graph: Graph) -> int:
    result = queries.candidates(
        graph, args.field, kind=args.kind, for_id=args.for_id, query=args.query, limit=args.limit
    )
    if args.json_output:
        _print_json(queries.candidates_json(result))
    else:
        print(queries.candidates_text(result))
    return 0


def _node_status(args: argparse.Namespace, graph: Graph) -> int:
    change = set_lifecycle(graph, os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), args.id, args.value)
    if args.json_output:
        _print_json(asdict(change))
    else:
        print(f"{change.node_id}: {change.old} -> {change.new} ({change.file})")
    return 0


_NODE_HANDLERS: dict[str, Callable[[argparse.Namespace, Graph], int]] = {
    "show": _node_show,
    "candidates": _node_candidates,
    "status": _node_status,
}


def _node_tokens(tokens: Sequence[str]) -> list[str]:
    """The tokens with ``show`` put in front unless the first one is a subcommand or a help flag."""
    if tokens and tokens[0] not in (*NODE_SUBCOMMANDS, "-h", "--help"):
        return ["show", *tokens]
    return list(tokens)


def run_node(tokens: Sequence[str]) -> int:
    """Run ``specdev node`` on the raw *tokens* after ``node``; returns the exit code."""
    args = build_node_parser().parse_args(_node_tokens(tokens))
    args.repo_root = detect_toolkit_root(args.repo_root)
    handler = _NODE_HANDLERS[args.node_cmd]
    return _run_on_graph("node", args, lambda graph: handler(args, graph))


# --- trace ----------------------------------------------------------------------------------------------------------

def _csv(text: str | None) -> frozenset[str]:
    return frozenset(part for part in (text or "").split(",") if part)


def _recipe_flags_problem(args: argparse.Namespace) -> str | None:
    """Why the flag combination of ``trace`` is not accepted, or ``None``."""
    if args.recipe is None:
        stray = [flag for flag, given in (("--expand", args.expand), ("--since", args.since)) if given]
        return f"{', '.join(stray)} needs --recipe" if stray else None
    walk = [
        flag
        for flag, given in (
            ("--up", args.up), ("--down", args.down), ("--depth", args.depth), ("--kinds", args.kinds),
            ("--verbs", args.verbs), ("--no-containment", args.no_containment),
        )
        if given
    ]
    return f"--recipe cannot be combined with {', '.join(walk)}" if walk else None


def _trace_pack(args: argparse.Namespace, graph: Graph) -> int:
    git = recipes.GitContext(os.path.abspath(args.git_root), os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), args.since)
    pack = recipes.build_pack(graph, recipes.load_recipes(os.path.abspath(args.repo_root)), args.recipe, args.id, expand=args.expand, git=git)
    if args.json_output:
        _print_json(recipes.pack_to_dict(pack))
    else:
        print(recipes.render_text(pack))
    return 0


def _trace_walk(args: argparse.Namespace, graph: Graph) -> int:
    directions = trace.BOTH_DIRECTIONS if args.up == args.down else (("up",) if args.up else ("down",))
    options = trace.TraceOptions(args.depth, _csv(args.kinds), _csv(args.verbs), not args.no_containment)
    result = trace.trace_node(graph, args.id, directions, options)
    if args.json_output:
        _print_json(trace.result_to_dict(result))
    else:
        print(trace.render_text(result))
    return 0


def run_trace(args: argparse.Namespace) -> int:
    """Run ``specdev trace`` on the parsed *args*; returns the exit code."""
    problem = _recipe_flags_problem(args)
    if problem is not None:
        return _usage_error("trace", problem)
    run = _trace_pack if args.recipe is not None else _trace_walk
    return _run_on_graph("trace", args, lambda graph: run(args, graph))


# --- diff -----------------------------------------------------------------------------------------------------------

def run_diff(args: argparse.Namespace) -> int:
    """Run ``specdev diff`` on the parsed *args*; returns the exit code."""

    def action() -> int:
        result = diff_refs(
            args.ref_a, args.ref_b, os.path.abspath(args.git_root), os.path.abspath(args.spec_root), os.path.abspath(args.repo_root)
        )
        if args.json_output:
            _print_json(diff_to_dict(result))
        else:
            print(diff_text(result))
        return 0

    return _run_guarded("diff", args.json_output, action)
