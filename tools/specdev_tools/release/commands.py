"""``specdev release``: the release cut, ``release check --stage prod``, ``release rollback`` and ``release prep``.

``add_release_parsers`` registers one ``release`` parser.  ``release --tag <name>`` (no subcommand) cuts the release; ``release check``,
``release rollback`` and ``release prep`` are its subcommands.  The three path flags and ``--json`` are on the ``release`` parser with their real
defaults and again on each subcommand through one parent parser whose defaults are ``argparse.SUPPRESS``, so a value given before the
subcommand survives and a value given after it wins.  The cut flags have their own destinations (``cut_tag``, ``cut_message``; ``release check``
uses ``check_tag``), so a subparser's default can never overwrite a parent's value.

The handlers return the exit code: 0 done, 1 refused (a finding), 2 a usage error.  The project canon folder is found by a function the
caller passes (``cli._discover_project_canon_dir``): ``release`` imports nothing from ``cli``.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from specdev_tools.core.errors import SpecError
from specdev_tools.core.json_output import format_errors_json
from specdev_tools.graph.commands import add_root_flags, resolve_git_root, run_on_graph, usage_error
from specdev_tools.graph.model import Graph
from specdev_tools.graph.stages import PROD_STAGE
from specdev_tools.release.prep import run_release_prep
from specdev_tools.release.prod_gate import ProdGateResult, run_prod_gate
from specdev_tools.release.records import write_rollback
from specdev_tools.release.status_sections import CanonDirOf
from specdev_tools.release.tag_state import release_tag_pattern
from specdev_tools.release.tagging import CutResult, cut_release
from specdev_tools.verify.code_tree import declarations_of

EXIT_REFUSED = 1

RELEASE_DESCRIPTION = (
    "Cut a release: `specdev release --tag <name> [--message TEXT]` creates the annotated git tag <name> on HEAD when the release gate "
    "passes. It refuses (nothing is written) a working tree that is not clean (E910: any changed, staged or untracked file git does not "
    "ignore), a host that declares no release_tag_pattern (E911), a tag name that does not match the pattern, is not a name git accepts "
    "or exists already (E912), and a release gate with errors (listed, exit 1). It does not push the tag and commits nothing: "
    "pushing the tag starts the deploy, which is the person's or the host's step. It picks no version number. "
    "Subcommands: check (the production-deploy gate of a tag), rollback (record that a release is not verified in production). "
    "Exit 0 tagged, 1 refused, 2 usage."
)
CHECK_DESCRIPTION = (
    "The production-deploy gate: `specdev release check --stage prod --tag <name>` reads the spec as it was at the tag and the evidence "
    "from the checkout (the staging evidence reaches the repository after the tag, through the evidence pull request) and checks that "
    "every obligation of the tag has valid evidence up to staging for the tag's code tree (E347, E348, owner release-gate), every "
    "delivery obligation is built at staging (E923) and every node the release gate relieved still holds (E924); a retired staging "
    "environment is skipped (W934). The name must be a tag of this clone (E921). Nothing about the tag's signature or history is checked. "
    "Writes nothing. Exit 0 passes, 1 blocked."
)
ROLLBACK_DESCRIPTION = (
    "Record that a release is not verified in production: `specdev release rollback <tag> --reason TEXT` writes "
    "spec/extras/releases/rollback-<tag>.json, which waives the production verification of that tag for the next release check (E920). "
    "The name must be a tag of this clone and match the release tag pattern (E925), the reason is not blank (E926) and no record of the tag exists "
    "(E927). The file is written, not committed: commit it through the normal branch. Exit 0 written, 1 refused."
)

PREP_DESCRIPTION = (
    "Prepare a release on a branch: `specdev release prep` runs every dev- and CI-stage binding whose evidence is missing, failed or stale "
    "for the code tree checked out (at stage ci, through `verify run`), writes the evidence under spec/extras/verification/, and then lists "
    "what the release gate still finds. A binding with valid evidence for this code tree is not run again: a second run on the same tree "
    "runs nothing. It commits, pushes and tags nothing. Exit 0 when no binding failed, 1 when one failed or a run was refused."
)


def _path_flags_parent() -> argparse.ArgumentParser:
    """The flags of ``add_root_flags`` again, for a subcommand: a flag that is not given leaves the value of the ``release`` parser alone."""
    parent = argparse.ArgumentParser(add_help=False)
    add_root_flags(parent)
    for action in parent._actions:
        action.default = argparse.SUPPRESS
    return parent


def add_release_parsers(sub: Any, canon_dir_of: CanonDirOf) -> None:
    """Register ``release`` (and ``release check``, ``release rollback``) on the top-level sub-parsers action *sub*.

    *canon_dir_of* finds the project canon folder (``cli._discover_project_canon_dir``).
    """
    release = sub.add_parser("release", help="Cut a release tag, check a tag for production, record a rollback", description=RELEASE_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    release.add_argument("--tag", dest="cut_tag", metavar="TAG", help="The release tag to create on HEAD (must match the host's release_tag_pattern and not exist)")
    release.add_argument("--message", dest="cut_message", metavar="TEXT", help="The annotation of the tag (default: 'release <tag>')")
    add_root_flags(release)
    release.set_defaults(handler=lambda args: run_release(args, canon_dir_of))
    release_sub = release.add_subparsers(dest="release_cmd", required=False)
    parent = _path_flags_parent()
    check = release_sub.add_parser("check", parents=[parent], help="The production-deploy gate of a release tag", description=CHECK_DESCRIPTION)
    check.add_argument("--stage", required=True, choices=(PROD_STAGE,), help="The gate to run: prod (the only one)")
    check.add_argument("--tag", dest="check_tag", required=True, metavar="TAG", help="The release tag to check")
    check.set_defaults(handler=run_release_check)
    rollback = release_sub.add_parser("rollback", parents=[parent], help="Record that a release is not verified in production", description=ROLLBACK_DESCRIPTION)
    rollback.add_argument("tag", metavar="TAG", help="The release tag the record is about")
    rollback.add_argument("--reason", required=True, metavar="TEXT", help="Why the release is not verified in production")
    rollback.set_defaults(handler=run_release_rollback)
    prep = release_sub.add_parser("prep", parents=[parent], help="Run the unproven dev and CI bindings and list what the release gate still finds", description=PREP_DESCRIPTION)
    prep.set_defaults(handler=lambda args: run_release_prep(args, canon_dir_of))


def _roots(args: argparse.Namespace) -> tuple[str, str, str]:
    """The spec folder, the toolkit and the host root, absolute."""
    return os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), resolve_git_root(args)


def _report(args: argparse.Namespace, command: str, context: dict[str, Any], errors: tuple[SpecError, ...], warnings: tuple[SpecError, ...], text: list[str]) -> None:
    """Print one outcome: the JSON envelope (``status``, counts, findings, *context*) on stdout, else *text* (on stderr when there are errors)."""
    if args.json_output:
        print(format_errors_json([*errors, *warnings], context={"command": command, **context}))
    else:
        print("\n".join(text), file=sys.stderr if errors else sys.stdout)


def _finding_lines(errors: tuple[SpecError, ...], warnings: tuple[SpecError, ...], listed: tuple[SpecError, ...] = ()) -> list[str]:
    lines = [f"  {finding.render()}" for finding in (*errors, *warnings)]
    return [*lines, *(f"  {finding.render()}" for finding in listed)]


def _cut_text(result: CutResult) -> list[str]:
    gate = result.gate
    count = f"{len(gate.errors)} error(s), {len(gate.warnings)} warning(s), {len(gate.listed)} listed (not blocking)"
    if not result.tagged:
        return [f"release {result.tag}: not tagged; the release gate found {count}", *_finding_lines(gate.errors, gate.warnings), *(f"  note: {note}" for note in gate.notes)]
    return [
        f"release {result.tag}: annotated tag created on {result.commit} ({result.message})",
        f"release gate: {count}",
        *_finding_lines((), gate.warnings, gate.listed),
        f"the tag is not pushed: pushing it starts the deploy; push it yourself (`git push <remote> {result.tag}`)",
    ]


def run_release(args: argparse.Namespace, canon_dir_of: CanonDirOf) -> int:
    """Run ``specdev release --tag`` (the cut) on the parsed *args*; returns the exit code (0 tagged, 1 refused, 2 usage)."""
    def cut(_graph: Graph) -> int:
        spec_root, repo_root, git_root = _roots(args)
        canon = canon_dir_of(git_root=git_root, spec_root=spec_root, spec_dir=spec_root)
        result = cut_release(git_root, spec_root, repo_root, args.cut_tag, args.cut_message, canon)
        context = {"tag": result.tag, "commit": result.commit, "tagged": result.tagged, "listed": [finding.render() for finding in result.gate.listed], "notes": list(result.gate.notes)}
        _report(args, "release", context, result.gate.errors, result.gate.warnings, _cut_text(result))
        return 0 if result.tagged else EXIT_REFUSED

    if not args.cut_tag:
        return usage_error("release", "--tag is required to cut a release (a subcommand: check, rollback)")
    return run_on_graph("release", args, cut)


def _check_text(result: ProdGateResult) -> list[str]:
    verdict = "passes" if result.passed else f"blocked, {len(result.errors)} error(s)"
    return [f"release check --stage prod {result.tag} (commit {result.commit}, code tree {result.code_tree}): {verdict}", *_finding_lines(result.errors, result.warnings)]


def run_release_check(args: argparse.Namespace) -> int:
    """Run ``specdev release check --stage prod --tag`` on the parsed *args*; returns the exit code (0 passes, 1 blocked)."""
    def check(_graph: Graph) -> int:
        spec_root, repo_root, git_root = _roots(args)
        result = run_prod_gate(git_root, spec_root, repo_root, args.check_tag)
        context = {"stage": PROD_STAGE, "tag": result.tag, "commit": result.commit, "code_tree": result.code_tree}
        _report(args, "release check", context, result.errors, result.warnings, _check_text(result))
        return 0 if result.passed else EXIT_REFUSED

    return run_on_graph("release check", args, check)


def run_release_rollback(args: argparse.Namespace) -> int:
    """Run ``specdev release rollback`` on the parsed *args*; returns the exit code (0 written, 1 refused)."""
    def rollback(_graph: Graph) -> int:
        spec_root, _repo_root, git_root = _roots(args)
        path = write_rollback(git_root, spec_root, args.tag, args.reason, release_tag_pattern(declarations_of(spec_root)))
        text = [f"recorded the rollback of {args.tag} ({path}): its production verification is waived for the next release check", "the file is written, not committed: commit it through the normal branch"]
        _report(args, "release rollback", {"tag": args.tag, "file": path}, (), (), text)
        return 0

    return run_on_graph("release rollback", args, rollback)

