"""The command line of the id-keyed writes: ``specdev json patch|insert|delete --id`` and ``json insert --step``.

``cli.py`` hands every ``specdev json patch|insert|delete`` argument list that holds ``--id`` or ``--step`` to
``run_id_write``; the jq-path forms of the same subcommands are not touched.  The parser here is the id forms' own (the
classic ``patch`` parser has a required positional file, so ``--id`` cannot be a flag of it).  Unlike the classic forms,
the id forms need the spec folder, so they keep ``--spec-root`` and ``--git-root``.

This module is a command module of its own, not a row of the generic dispatch of ``graph/commands``: ``json`` is parsed
by ``cli.py`` with its own token handling (since 1.1.1), and moving the id forms under the generic dispatch would change
that routing, which no plan asks for.  The report text lives in ``trace.write_report``.
"""
from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from specdev_tools.core.toolkit_root import detect_toolkit_root
from specdev_tools.graph.commands import add_root_flags, print_json, resolve_git_root, run_on_graph
from specdev_tools.graph.model import Graph
from specdev_tools.lifecycle.closed_edits import edit_of_closed_node, record_migration_edit
from specdev_tools.trace.id_writes import ACTIONS, WriteRequest, execute_write
from specdev_tools.trace.write_report import render_text, result_to_dict

__all__ = ["ID_FLAGS", "build_id_write_parser", "is_id_write", "run_id_write"]

ID_FLAGS = ("--id", "--step")
ID_WRITE_DESCRIPTION = (
    "Write a node of the spec by its id instead of by its place in a file.\n\n"
    "  specdev json patch  --id <node-id> <field-path> <json-value> [--raw] [--dry-run]\n"
    "  specdev json insert --id <node-id> <field-path> <json-value> [--raw] [--dry-run]\n"
    "  specdev json insert --step NN <collection-path> <json-value> [--dry-run]\n"
    "  specdev json delete --id <node-id> [--dry-run]\n\n"
    "<field-path> is a jq path relative to the node (.statement, .derives_from); <collection-path> is a collection of "
    "the step's file (.functional_requirements). An id is looked up as an id, then as an alias; an unknown id is E706 "
    "with the nearest ids, an id defined twice is refused (E767). Items without an id get one minted from their text. "
    "The write is checked against the file's schema (a violation the edit adds refuses it), the links it writes must "
    "resolve, and the payload may not store a computed field (E768). The lock entries of the links written get the hashes "
    "their targets have now; the entries of links removed, and of a deleted node's links, are dropped.\n\n"
    "The report shows the links written with the text of their targets (cut at 300 characters, --full for all), the lock "
    "entries written and removed, the links the edit made suspect per step and, for delete, the links that now point at "
    "the deleted node. Exit 0 done, 1 refused. --dry-run reports without writing."
)


def is_id_write(tokens: Sequence[str]) -> bool:
    """True when *tokens* (the words after ``json``) are an id-keyed write: ``patch``, ``insert`` or ``delete`` with ``--id`` or ``--step``."""
    if not tokens or tokens[0] not in ACTIONS:
        return False
    return any(token.split("=", 1)[0] in ID_FLAGS for token in tokens[1:])


def build_id_write_parser() -> argparse.ArgumentParser:
    """The parser of the id-keyed write forms (no parsing, no side effects)."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true", dest="dry_run", help="Report what would be written and write nothing")
    common.add_argument("--full", action="store_true", help="Show the whole text of every target the write links to (default: first 300 characters)")
    add_root_flags(common)
    parser = argparse.ArgumentParser(prog="specdev json", description=ID_WRITE_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)

    patch = sub.add_parser("patch", parents=[common], help="Replace a field of a node, by node id")
    patch.add_argument("--id", dest="node_id", required=True, metavar="NODE_ID", help="The node to write (an id or an alias)")
    patch.add_argument("path", metavar="FIELD_PATH", help="jq path relative to the node, for example .statement")
    patch.add_argument("value", help="New value (JSON, or a plain string with --raw)")
    patch.add_argument("--raw", action="store_true", help="Treat the value as a string, not JSON")

    insert = sub.add_parser("insert", parents=[common], help="Append to an array field of a node, or add a new node to a step")
    where = insert.add_mutually_exclusive_group(required=True)
    where.add_argument("--id", dest="node_id", metavar="NODE_ID", help="The node whose array field gets the value")
    where.add_argument("--step", metavar="NN", help="Add a new node to the first-level collection of this step's file")
    insert.add_argument("path", metavar="PATH", help="With --id: jq path of an array field of the node. With --step: the collection, for example .functional_requirements")
    insert.add_argument("value", help="The item to append (JSON, or a plain string with --raw)")
    insert.add_argument("--raw", action="store_true", help="Treat the value as a string, not JSON")

    delete = sub.add_parser("delete", parents=[common], help="Delete a node, by id")
    delete.add_argument("--id", dest="node_id", required=True, metavar="NODE_ID", help="The node to delete (an id or an alias)")
    return parser


# --- running --------------------------------------------------------------------------------------------------------

def _request_of(args: argparse.Namespace) -> WriteRequest:
    return WriteRequest(
        action=args.action,
        node_id=getattr(args, "node_id", None),
        step=getattr(args, "step", None),
        path=getattr(args, "path", None),
        value=getattr(args, "value", None),
        raw=getattr(args, "raw", False),
        full=args.full,
    )


def _write(args: argparse.Namespace, graph: Graph) -> int:
    spec_root, repo_root = os.path.abspath(args.spec_root), os.path.abspath(args.repo_root)
    request = _request_of(args)
    closed = edit_of_closed_node(graph, spec_root, request.node_id, f"json {request.action} --id") if request.node_id else None
    result = execute_write(graph, spec_root, repo_root, resolve_git_root(args), request, dry_run=args.dry_run)
    if closed is not None and not args.dry_run:
        record_migration_edit(spec_root, repo_root, closed)
    if args.json_output:
        print_json(result_to_dict(result))
    else:
        print(render_text(result))
    return 0


def run_id_write(tokens: Sequence[str]) -> int:
    """Run ``specdev json patch|insert|delete`` with ``--id`` or ``--step`` on the raw *tokens* after ``json``; returns the exit code."""
    args = build_id_write_parser().parse_args(list(tokens))
    args.repo_root = detect_toolkit_root(args.repo_root)
    return run_on_graph("json", args, lambda graph: _write(args, graph))
