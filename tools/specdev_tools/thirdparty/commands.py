"""The third-party commands of the CLI: ``specdev third-party pin`` and ``specdev third-party check``.

``cli.py`` registers them with one call, ``add_thirdparty_parsers``; each parser names its handler with ``set_defaults``.  A
handler returns the process exit code: 0 done, 1 a finding or a refusal, 2 a usage error.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from typing import Any

from specdev_tools.core.errors import SpecError
from specdev_tools.core.json_output import format_errors_json
from specdev_tools.graph.commands import add_root_flags, print_json, resolve_git_root, run_on_graph, usage_error
from specdev_tools.graph.model import Graph
from specdev_tools.thirdparty.check import check_installed, check_pins, write_install_checks
from specdev_tools.thirdparty.pin import pin_third_party
from specdev_tools.trace.records import RECORDS_DIR
from specdev_tools.trace.write_report import render_text, result_to_dict
from specdev_tools.verify.code_tree import declarations_of
from specdev_tools.verify.commands import installed_overrides

CHANGE_REMINDER = (
    "The code change for this pin is made in this branch, through a change milestone whose task criteria refine "
    "the obligations that rely on the third party."
)

THIRD_PARTY_DESCRIPTION = (
    "Pin third parties and check the pins.\n\n"
    "Subcommands:\n"
    "  pin <tp-id> <version>   Write the exact version a third party is pinned to (writes the step-02 file)\n"
    "  check                   Compare every pin with the version sources the host declares, or with what a deploy installed"
)

PIN_DESCRIPTION = (
    "Write <version> as the pin of the third-party node <tp-id> (an id or an alias). The version must be exact: a version, "
    "a commit or a contract id; latest, *, x-wildcards and ranges are E336. The edit goes through the id-keyed write path, "
    "so the node's content hash changes, the links into it go suspect (listed by `specdev stale`) and the command prints "
    "how many, by step. The code change itself is made in this branch through a change milestone. Exit 0 written, 1 refused."
)

CHECK_DESCRIPTION = (
    "With no flags, compare the pin of every third party that declares pin_sources (spec/common/host_declarations.json) with "
    "the version each source reads from the working tree: E336 for a pin that is not exact, E337 for a different version, "
    "E338 for a source that gives none; exit 1 on any finding. With --installed TP=VERSION (repeat for more) and --env, "
    "compare what a deploy installed with the pins: a different version is E339 and exit 1, which stops the deploy; when "
    "all match, one install-check evidence record per third party is written to spec/extras/verification/ "
    "(evd-install-<tp>-<env>.json, with --tag when given)."
)


def add_thirdparty_parsers(sub: Any) -> None:
    """Register the ``third-party`` group (``pin``, ``check``) on the top-level sub-parsers action *sub*."""
    group = sub.add_parser("third-party", help="Pin third parties; check the pins", description=THIRD_PARTY_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    group_sub = group.add_subparsers(dest="third_party_cmd", required=True)

    pin = group_sub.add_parser("pin", help="Write the exact version of a third party", description=PIN_DESCRIPTION)
    pin.add_argument("third_party_id", metavar="tp-id", help="The third-party node (an id or an alias)")
    pin.add_argument("version", help="The exact version, commit or contract id to pin")
    add_root_flags(pin)
    pin.set_defaults(handler=run_third_party_pin)

    check = group_sub.add_parser("check", help="Compare pins with the repository, or with a deploy", description=CHECK_DESCRIPTION)
    check.add_argument("--installed", action="extend", nargs="+", metavar="TP=VERSION", help="Deploy mode: the version of a third party the deploy installed")
    check.add_argument("--env", help="Deploy mode: the environment deployed to (required with --installed)")
    check.add_argument("--tag", help="Deploy mode: the release tag deployed")
    add_root_flags(check)
    check.set_defaults(handler=run_third_party_check)


def _pin(args: argparse.Namespace, graph: Graph) -> int:
    result = pin_third_party(
        graph, os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), resolve_git_root(args), args.third_party_id, args.version
    )
    if args.json_output:
        print_json({**result_to_dict(result), "command": "third-party pin", "reminder": CHANGE_REMINDER})
    else:
        print(render_text(result))
        print(CHANGE_REMINDER)
    return 0


def run_third_party_pin(args: argparse.Namespace) -> int:
    """Run ``specdev third-party pin`` on the parsed *args*; returns the exit code (0 written, 1 refused)."""
    return run_on_graph("third-party pin", args, lambda graph: _pin(args, graph))


def _report_findings(findings: Sequence[SpecError], json_output: bool) -> int:
    """Print *findings* the way the other commands do (text on stderr, or the JSON envelope on stdout); the exit code 1."""
    if json_output:
        print(format_errors_json(list(findings), context={"command": "third-party check"}))
    else:
        for finding in findings:
            print(finding.render(), file=sys.stderr)
    return 1


def _check_sources(args: argparse.Namespace, graph: Graph) -> int:
    declarations = declarations_of(os.path.abspath(args.spec_root))
    findings = check_pins(graph, declarations, resolve_git_root(args))
    if findings:
        return _report_findings(findings, args.json_output)
    checked = bool(declarations.pin_sources)
    if args.json_output:
        print_json({"command": "third-party check", "mode": "sources", "checked": checked, "errors": []})
    else:
        print("every pin matches its declared sources" if checked else "no pin sources are declared; nothing checked")
    return 0


def _check_deploy(args: argparse.Namespace, graph: Graph, installed: dict[str, str]) -> int:
    resolved, findings = check_installed(graph, installed)
    if findings:
        return _report_findings(findings, args.json_output)
    files = write_install_checks(os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), resolve_git_root(args), resolved, args.env, args.tag)
    records = [f"{RECORDS_DIR}/{name}" for name in files]
    if args.json_output:
        print_json({"command": "third-party check", "mode": "installed", "env": args.env, "tag": args.tag, "installed": resolved, "records": records, "errors": []})
    else:
        for (node_id, version), record in zip(resolved.items(), records):
            print(f"{node_id}: installed {version} is the pin; recorded {record}")
    return 0


def run_third_party_check(args: argparse.Namespace) -> int:
    """Run ``specdev third-party check`` on the parsed *args*; returns the exit code (0 all agree, 1 a finding or a refusal, 2 usage)."""
    if args.installed is None:
        if args.env is not None or args.tag is not None:
            return usage_error("third-party check", "--env and --tag go with --installed")
        return run_on_graph("third-party check", args, lambda graph: _check_sources(args, graph))
    installed = installed_overrides(args.installed)
    if installed is None:
        return usage_error("third-party check", "--installed takes TP=VERSION")
    if not args.env:
        return usage_error("third-party check", "--installed needs --env, the environment deployed to")
    return run_on_graph("third-party check", args, lambda graph: _check_deploy(args, graph, installed))
