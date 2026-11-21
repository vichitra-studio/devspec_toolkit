"""The lifecycle commands of the CLI: ``specdev plan record`` and ``specdev review record``.

``cli.py`` registers them with one call, ``add_lifecycle_parsers``; each parser names its handler with ``set_defaults``.  A
handler returns the process exit code: 0 done, 1 refused, 2 a usage error.  Another command of the group is added by a
private ``_add_<group>_parser`` function that ``add_lifecycle_parsers`` calls.
"""
from __future__ import annotations

import argparse
import os
from typing import Any

from ..graph.commands import add_root_flags, print_json, resolve_git_root, run_on_graph, usage_error
from .plan_records import Address, DeployResult, PruneResult, RecordResult, parse_address, prune_records, record_action, record_at_deploy
from .review_record import VERDICTS, ReviewRequest, ReviewResult, record_review

PLAN_DESCRIPTION = (
    "Execution records of a milestone's plan.\n\n"
    "Subcommands:\n"
    "  record <item>/<action> --outcome done|failed|blocked   Record that an action of a plan item was carried out, failed or is blocked\n"
    "  record --at-deploy <item>/<action> --env ENV           Record that a deploy job carried out an at_deploy action\n"
    "  record --prune <milestone-id>                          Remove the records of items or actions the plan no longer has"
)
PLAN_RECORD_DESCRIPTION = (
    "Write an execution record. <item>/<action> is a plan item id and the id of one of its actions, written as one word "
    "(PWRESET_CONFIRM_EXPIRED_01/a01). The record is appended to execution.records of the plan that holds the item, with the git "
    "author, the time and the hash of what the item realises, and the plan size in bytes is printed before and after. Refused: "
    "E821 an unknown item or action (an action with no id cannot be addressed), E820 a plan of a closed milestone, E822 an action "
    "that names a verifier (its command is a command of a binding): its proof is the evidence of 'specdev verify run', not a "
    "record. Whether an item counts as executed is computed from the records and the evidence; recording again adds a newer "
    "record, and the latest one counts.\n\n"
    "--at-deploy writes the record of an action marked at_deploy for --env as a file of its own, extras/verification/dep-<NNNN>.json "
    "(--outcome done or failed, default done; --tag names the release). It does not touch the plan, so it works for a closed "
    "milestone, and with no git identity the author is 'ci'.\n\n"
    "--prune <milestone-id> removes the records of that milestone's plan whose item or action is gone (after a re-plan); it is not "
    "'specdev attest --prune', which removes orphan lock entries.\n\n"
    "Exit 0 written, 1 refused, 2 usage."
)
REVIEW_DESCRIPTION = (
    "The review verdict of a milestone's plan.\n\n"
    "Subcommands:\n"
    "  record <milestone-id> --verdict V   Replace the review block of the plan with the verdict and its findings"
)
REVIEW_RECORD_DESCRIPTION = (
    "Replace the whole review block of the plan of <milestone-id> with one verdict (no history is kept) and the time it was "
    "recorded; the plan size in bytes is printed before and after. --verdict is verified, needs_work, blocked or deferred. "
    "--findings-file takes the converged findings file of the reviewer: a JSON document with \"$schema\": \"vc:infra:findings\" "
    "that is valid against schema/infra/findings.schema.json; each finding that is not already verified becomes one entry of "
    "review.findings (an empty findings list records none). A finding names plan items through the file's scope or its "
    "upstream_refs written as a plan-item id; each must be an item of the plan. --ratings-json is a JSON object of the five "
    "ratings. The tool checks the input, not the judgement: verified is accepted with a blocking finding or a red "
    "security status. Refused: E823 for an unknown verdict, a findings file that is not valid (the message names what is "
    "missing), a finding that names an unknown item or a block that breaks the plan schema; E820 for a closed milestone; "
    "E803 when no plan names the milestone. Exit 0 written, 1 refused."
)
EXIT_ERROR = 1
ENVIRONMENTS = ("staging", "prod")
OUTCOMES = ("done", "failed", "blocked")
DEPLOY_OUTCOMES = ("done", "failed")
NOTE_MAX = 200


def add_lifecycle_parsers(sub: Any) -> None:
    """Register the lifecycle groups (``plan``, ``review``) on the top-level sub-parsers action *sub*."""
    _add_plan_parser(sub)
    _add_review_parser(sub)


def _add_plan_parser(sub: Any) -> None:
    plan = sub.add_parser("plan", help="Record the execution of a plan's actions", description=PLAN_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    plan_sub = plan.add_subparsers(dest="plan_cmd", required=True)
    record = plan_sub.add_parser("record", help="Record an action as done, failed or blocked", description=PLAN_RECORD_DESCRIPTION)
    record.add_argument("address", nargs="?", metavar="ITEM/ACTION", help="A plan item id and an action id of that item, as one word: PWRESET_CONFIRM_EXPIRED_01/a01")
    record.add_argument("--outcome", choices=OUTCOMES, help="done, failed or blocked (required; for --at-deploy only done or failed, default done)")
    record.add_argument("--note", metavar="TEXT", help=f"A short note, at most {NOTE_MAX} characters: what was done, or why it failed or is blocked")
    record.add_argument("--at-deploy", action="store_true", dest="at_deploy", help="Write the deploy record of an action marked at_deploy (needs --env)")
    record.add_argument("--env", choices=ENVIRONMENTS, help="With --at-deploy: the environment the deploy job ran for")
    record.add_argument("--tag", metavar="TAG", help="With --at-deploy: the release tag that was deployed")
    record.add_argument("--prune", metavar="MILESTONE", help="Remove the records of this milestone's plan whose item or action no longer exists")
    add_root_flags(record)
    record.set_defaults(handler=run_plan_record)


def _add_review_parser(sub: Any) -> None:
    review = sub.add_parser("review", help="Record the review verdict of a plan", description=REVIEW_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    review_sub = review.add_subparsers(dest="review_cmd", required=True)
    record = review_sub.add_parser("record", help="Replace the review block of a plan", description=REVIEW_RECORD_DESCRIPTION)
    record.add_argument("milestone", metavar="milestone-id", help="The roadmap milestone whose plan is reviewed")
    record.add_argument("--verdict", required=True, metavar="VERDICT", help=f"{', '.join(VERDICTS)}")
    record.add_argument("--findings-file", metavar="PATH", dest="findings_file", help="The converged findings file of the reviewer (vc:infra:findings)")
    record.add_argument("--next-actions", metavar="TEXT", dest="next_actions", help="What happens next, and who does it")
    record.add_argument("--security-status", metavar="green|red", dest="security_status", help="green (no issues) or red")
    record.add_argument("--ratings-json", metavar="JSON", dest="ratings_json", help="A JSON object with the five ratings, each 0 to 5")
    add_root_flags(record)
    record.set_defaults(handler=run_review_record)


def _sizes(before: int, after: int) -> str:
    return f"  plan file: {before} bytes before, {after} bytes after"


def _record_text(result: RecordResult) -> str:
    record = result.record
    lines = [f"recorded {record['record_id']}: {record['about'][0]}/{record['action']} {record['outcome']} ({result.plan})", _sizes(result.bytes_before, result.bytes_after)]
    return "\n".join([*lines, *(f"  {note}" for note in result.notes)])


def _record_json(result: RecordResult) -> dict[str, Any]:
    return {"command": "plan record", "record": result.record, "plan": result.plan, "bytes_before": result.bytes_before, "bytes_after": result.bytes_after, "notes": list(result.notes)}


def _deploy_text(result: DeployResult) -> str:
    record = result.record
    return f"recorded {record['deploy_id']}: {record['about'][0]}/{record['action']} {record['outcome']} at {record['env']} ({result.file})"


def _prune_text(result: PruneResult) -> str:
    what = f"removed {len(result.removed)} orphan record(s) from {result.plan}: {', '.join(result.removed)}" if result.removed else f"no orphan records in {result.plan}"
    return f"{what}\n{_sizes(result.bytes_before, result.bytes_after)}"


def _prune_json(result: PruneResult) -> dict[str, Any]:
    return {"command": "plan record --prune", "plan": result.plan, "removed": list(result.removed), "bytes_before": result.bytes_before, "bytes_after": result.bytes_after}


def _usage_problem(args: argparse.Namespace) -> str | None:
    """What is wrong with the combination of arguments of ``plan record``, or ``None``."""
    if args.prune is not None:
        extras = [name for name, given in (("an action", args.address), ("--outcome", args.outcome), ("--note", args.note), ("--at-deploy", args.at_deploy), ("--env", args.env), ("--tag", args.tag)) if given]
        return f"--prune takes a milestone id and nothing else (also given: {', '.join(extras)})" if extras else None
    if args.address is None:
        return "give <plan item id>/<action id> (PWRESET_CONFIRM_EXPIRED_01/a01), or --prune <milestone-id>"
    if parse_address(args.address) is None:
        return f"{args.address!r} is not <plan item id>/<action id>, for example PWRESET_CONFIRM_EXPIRED_01/a01"
    if args.at_deploy:
        return _at_deploy_problem(args)
    if args.env or args.tag:
        return "--env and --tag go with --at-deploy"
    if args.outcome is None:
        return "--outcome is required: done, failed or blocked"
    return f"--note is {len(args.note)} characters; at most {NOTE_MAX}" if args.note and len(args.note) > NOTE_MAX else None


def _at_deploy_problem(args: argparse.Namespace) -> str | None:
    if args.env is None:
        return "--at-deploy needs --env staging or --env prod"
    if args.note:
        return "--note is for a plain record; an at-deploy record has no note"
    return "an at-deploy record is done or failed, not blocked" if args.outcome == "blocked" else None


def _emit(args: argparse.Namespace, document: dict[str, Any], text: str) -> None:
    """Print *document* as JSON when ``--json`` was given, else *text*."""
    if args.json_output:
        print_json(document)
    else:
        print(text)


def _plan_record(args: argparse.Namespace, address: Address | None) -> None:
    spec_root, repo_root, git_root = os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), resolve_git_root(args)
    if address is None:
        pruned = prune_records(spec_root, repo_root, args.prune)
        _emit(args, _prune_json(pruned), _prune_text(pruned))
    elif args.at_deploy:
        deployed = record_at_deploy(spec_root, repo_root, git_root, address, args.env, args.outcome or "done", args.tag)
        _emit(args, {"command": "plan record --at-deploy", "record": deployed.record, "file": deployed.file}, _deploy_text(deployed))
    else:
        recorded = record_action(spec_root, repo_root, git_root, address, args.outcome, args.note)
        _emit(args, _record_json(recorded), _record_text(recorded))


def run_plan_record(args: argparse.Namespace) -> int:
    """Run ``specdev plan record`` on the parsed *args*; returns the exit code (0 written, 1 refused, 2 usage)."""
    problem = _usage_problem(args)
    if problem is not None:
        return usage_error("plan record", problem)
    address = parse_address(args.address) if args.address else None

    def run(_graph: object) -> int:
        _plan_record(args, address)
        return 0

    return run_on_graph("plan record", args, run)


def _review_text(result: ReviewResult) -> str:
    block = result.block
    count = len(block.get("findings", ()))
    findings = f", {count} finding(s)" if "findings" in block else ""
    return f"recorded the review of {result.plan}: verdict {block['verdict']}{findings}\n{_sizes(result.bytes_before, result.bytes_after)}"


def run_review_record(args: argparse.Namespace) -> int:
    """Run ``specdev review record`` on the parsed *args*; returns the exit code (0 written, 1 refused)."""
    def run(_graph: object) -> int:
        request = ReviewRequest(args.milestone, args.verdict, args.findings_file, args.next_actions, args.security_status, args.ratings_json)
        result = record_review(os.path.abspath(args.spec_root), os.path.abspath(args.repo_root), request)
        document = {"command": "review record", "milestone": args.milestone, "plan": result.plan, "review": result.block, "bytes_before": result.bytes_before, "bytes_after": result.bytes_after}
        _emit(args, document, _review_text(result))
        return 0

    return run_on_graph("review record", args, run)
