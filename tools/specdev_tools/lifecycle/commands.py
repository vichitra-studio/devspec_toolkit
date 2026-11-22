"""The lifecycle commands of the CLI: ``specdev plan record``, ``review record``, ``milestone start|defer|sign-off|close`` and ``status``.

``cli.py`` registers them with one call, ``add_lifecycle_parsers``; each parser names its handler with ``set_defaults``.  A
handler returns the process exit code: 0 done, 1 refused, 2 a usage error.  Another command of the group is added by a
private ``_add_<group>_parser`` function that ``add_lifecycle_parsers`` calls.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from typing import Any

from ..core.errors import SpecError
from ..core.json_output import format_errors_json
from ..graph.commands import add_root_flags, print_json, roots, run_on_graph, usage_error
from ..graph.model import Graph
from ..graph.ownership import CLOSE_OWNER
from ..graph.stages import DEPLOY_ENVIRONMENTS
from ..trace.lockfile import Lock
from .close_gate import OpenItemsProvider, ScaffoldProvider
from .executed import lock_if_present
from .milestone import CloseResult, MilestoneRefusal, ProviderFactory, close_milestone, defer_milestone, milestone_id_of, start_milestone
from .plan_records import Address, DeployResult, PruneResult, RecordResult, parse_address, prune_records, record_action, record_at_deploy
from .review_record import VERDICTS, ReviewRequest, ReviewResult, record_review
from .signoff import sign_off
from .status import build_status, milestone_view, status_context, status_dict, status_text, view_dict, view_text

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
OUTCOMES = ("done", "failed", "blocked")
NOTE_MAX = 200


def add_lifecycle_parsers(sub: Any) -> None:
    """Register the lifecycle groups (``plan``, ``review``, ``milestone``) and ``status`` on the top-level sub-parsers action *sub*."""
    _add_plan_parser(sub)
    _add_review_parser(sub)
    _add_milestone_parser(sub)
    _add_status_parser(sub)


def _add_plan_parser(sub: Any) -> None:
    plan = sub.add_parser("plan", help="Record the execution of a plan's actions", description=PLAN_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    plan_sub = plan.add_subparsers(dest="plan_cmd", required=True)
    record = plan_sub.add_parser("record", help="Record an action as done, failed or blocked", description=PLAN_RECORD_DESCRIPTION)
    record.add_argument("address", nargs="?", metavar="ITEM/ACTION", help="A plan item id and an action id of that item, as one word: PWRESET_CONFIRM_EXPIRED_01/a01")
    record.add_argument("--outcome", choices=OUTCOMES, help="done, failed or blocked (required; for --at-deploy only done or failed, default done)")
    record.add_argument("--note", metavar="TEXT", help=f"A short note, at most {NOTE_MAX} characters: what was done, or why it failed or is blocked")
    record.add_argument("--at-deploy", action="store_true", dest="at_deploy", help="Write the deploy record of an action marked at_deploy (needs --env)")
    record.add_argument("--env", choices=DEPLOY_ENVIRONMENTS, help="With --at-deploy: the environment the deploy job ran for")
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


def _plan_record(args: argparse.Namespace, address: Address | None, graph: Graph) -> None:
    spec_root, repo_root, git_root = roots(args)
    if address is None:
        pruned = prune_records(spec_root, repo_root, milestone_id_of(graph, spec_root, args.prune))
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

    def run(graph: Graph) -> int:
        _plan_record(args, address, graph)
        return 0

    return run_on_graph("plan record", args, run)


def _review_text(result: ReviewResult) -> str:
    block = result.block
    count = len(block.get("findings", ()))
    findings = f", {count} finding(s)" if "findings" in block else ""
    return f"recorded the review of {result.plan}: verdict {block['verdict']}{findings}\n{_sizes(result.bytes_before, result.bytes_after)}"


def run_review_record(args: argparse.Namespace) -> int:
    """Run ``specdev review record`` on the parsed *args*; returns the exit code (0 written, 1 refused)."""
    def run(graph: Graph) -> int:
        spec_root = os.path.abspath(args.spec_root)
        request = ReviewRequest(milestone_id_of(graph, spec_root, args.milestone), args.verdict, args.findings_file, args.next_actions, args.security_status, args.ratings_json)
        result = record_review(spec_root, os.path.abspath(args.repo_root), request)
        document = {"command": "review record", "milestone": request.milestone, "plan": result.plan, "review": result.block, "bytes_before": result.bytes_before, "bytes_after": result.bytes_after}
        _emit(args, document, _review_text(result))
        return 0

    return run_on_graph("review record", args, run)


# --- milestone and status -----------------------------------------------------------------------------------------------

MILESTONE_DESCRIPTION = (
    "The life of a milestone: its anchor row in spec/16_impl_context.json and its sign-off record.\n\n"
    "Subcommands:\n"
    "  start <milestone-id>              Make a pending or deferred milestone in_progress (a resume clears the deferral reason)\n"
    "  defer <milestone-id> --reason T   Put a pending or in_progress milestone aside, with the reason\n"
    "  sign-off <milestone-id>           Record that a person signed the milestone off against the code tree now\n"
    "  close <milestone-id> [--check]    Run the close gate and, when it passes, close the milestone\n\n"
    "The id is a roadmap milestone (ms-...), never a batch id: `specdev milestone-state --batch-id <batch>` prints the milestone "
    "of a plan under `milestone`. Exit 0 done, 1 refused, 2 usage."
)
START_DESCRIPTION = (
    "Start the milestone, or resume it. Writes status in_progress on its anchor row and nothing else; a milestone that is "
    "in_progress already is left as it is (exit 0). Refused with E800: ANCHOR_ROW_MISSING (no anchor row about the id), "
    "STATUS_NOT_STARTABLE (the milestone is done), PENDING_REPLAY_ON_CHAIN (a suspect link is on the milestone's chain: its "
    "plan items, their criteria and everything those reach upward; suspect links elsewhere do not stop it, and each one is "
    "listed with its owner). With no trace lock file the suspect check is skipped and the command says so. E803: no plan "
    "names the milestone, or the id is a batch id. Exit 0 started, 1 refused."
)
DEFER_DESCRIPTION = (
    "Put the whole milestone aside: status deferred and the reason on its anchor row, from pending or in_progress. Tasks, plan "
    "items and open items are not touched; one task is deferred by its disposition in step 14. --reason is required and has at "
    "most 300 characters (E802). Refused with E801 when the milestone is deferred or done. `milestone start` resumes it. "
    "Exit 0 deferred, 1 refused."
)
SIGNOFF_DESCRIPTION = (
    "Record the sign-off of an in_progress milestone: extras/signoff/so-<milestone>-<NNNN>.json holds the code tree now, the git "
    "author, the time and what was listed (manual fixtures and how many are attested, deferred and won't-do tasks, plan items "
    "not executed, proof owed at staging or prod). The same view as `specdev status --milestone <id>` is printed. A second "
    "sign-off gets the next number. Nothing checks who runs it, whether the review said verified, or whether the tree is the "
    "current one at close. Refused: E801 (the milestone is not in_progress), E803, E800 (no anchor row). Exit 0 recorded, 1 refused."
)
CLOSE_DESCRIPTION = (
    "Close an in_progress milestone. The close gate checks, and reports every finding at once: E810 a task criterion no plan item "
    "realises, E811 a criterion not proven (at the dev stage; a ci binding counts as dev; staging and production bindings do "
    "not hold the close up), E812 a plan item not executed, E813 the review of the plan is not verified, E632 an open item in the "
    "plan, E763 a suspect link on the milestone's chain, E761 a link of a plan item that has no lock entry, E746 a scaffold row that is not a tracked file, E814 no sign-off record. "
    "With errors nothing is written and the command exits 1, the errors listed by owner. With none, ONE write sets status done and "
    "the close record (signed_off_by the git author email of the latest sign-off, signoff its id, tree, plan_hash, closed_at, "
    "migrations); the plan is frozen from then on (a record write is refused with E820, spec-check frozen-plans reports a "
    "change, E827). --check runs the gate and writes nothing. The sign-off tree is printed next to the tree the close is made "
    "at, as information. Refused: E801 (the milestone is not in_progress), E803, E800. Exit 0 closed or passes, 1 refused."
)
STATUS_DESCRIPTION = (
    "Where the work stands, in sections: pending replay by step, open items by owner, milestones awaiting sign-off, outdated and "
    "removed realisations, the next step that may start, the gate-owned errors of the milestones in progress (the close gate as a "
    "dry run, and the W350 warning for a submodule with uncommitted content), the merge-check and release-gate errors (the release "
    "gate run on the checkout, by owner) and the production verification of the previous release (verified in production, rollback "
    "recorded, not verified, none (previous tag predates 1.2.0; this tag predates 1.2.0 for the release at HEAD) or none). Reads and writes nothing; "
    "exit 0 whatever it lists (1 only when it cannot read what it needs). --milestone <id> prints the view `milestone sign-off` "
    "shows: the code tree, the proof of each criterion, the manual share, deferred and won't-do tasks, open items and the close "
    "gate as a dry run. --json prints the same data with stable keys."
)


def _add_milestone_parser(sub: Any) -> None:
    group = sub.add_parser("milestone", help="Start, defer, sign off and close a milestone", description=MILESTONE_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    group_sub = group.add_subparsers(dest="milestone_cmd", required=True)
    for name, short, text, handler in (
        ("start", "Start or resume a milestone", START_DESCRIPTION, run_milestone_start),
        ("defer", "Put a milestone aside with a reason", DEFER_DESCRIPTION, run_milestone_defer),
        ("sign-off", "Record the sign-off of a milestone", SIGNOFF_DESCRIPTION, run_milestone_signoff),
        ("close", "Run the close gate and close the milestone", CLOSE_DESCRIPTION, run_milestone_close),
    ):
        command = group_sub.add_parser(name, help=short, description=text)
        command.add_argument("milestone", metavar="milestone-id", help="The roadmap milestone (ms-...), not a batch id")
        if name == "defer":
            command.add_argument("--reason", metavar="TEXT", help="Why the milestone waits (required; at most 300 characters)")
        if name == "close":
            command.add_argument("--check", action="store_true", help="Run the close gate and stop: nothing is written")
        add_root_flags(command)
        command.set_defaults(handler=handler)


def _add_status_parser(sub: Any) -> None:
    status = sub.add_parser("status", help="Where the work stands: replay, open items, sign-offs, gate-owned errors", description=STATUS_DESCRIPTION)
    status.add_argument("--milestone", metavar="milestone-id", help="Show the sign-off and close view of this milestone")
    add_root_flags(status)
    status.set_defaults(handler=run_status)


def gate_providers(spec_root: str, repo_root: str, git_root: str) -> ProviderFactory:
    """The two checks of the close gate that live in ``validation`` (this package may not import it at the top), built for one run."""
    def build(graph: Graph, lock: Lock | None) -> tuple[OpenItemsProvider, ScaffoldProvider]:
        from ..validation.graph_checks.context import GraphCheckContext
        from ..validation.graph_checks.scaffold import scaffold_scan
        from ..validation.open_items import check_open_items
        scan_context = GraphCheckContext.from_graph(graph, lock, repo_root, git_root=git_root, spec_root=spec_root)
        return (lambda plan: check_open_items(spec_root, gate="close", plan_path=plan), lambda apis: scaffold_scan(scan_context, apis, "close"))
    return build


def _refused(args: argparse.Namespace, command: str, error: SpecError, details: tuple[SpecError, ...] = ()) -> int:
    """Print a refusal (text on stderr: the finding, then the findings behind it; JSON on stdout) and return exit code 1."""
    if args.json_output:
        print(format_errors_json([error, *details], context={"command": command}))
    else:
        print(error.render(), file=sys.stderr)
        for detail in details:
            print(f"  [{detail.owner or 'no owner'}] {detail.render()}", file=sys.stderr)
    return EXIT_ERROR


def _guarded(command: str, args: argparse.Namespace, body: Callable[[], int]) -> int:
    def run(_graph: object) -> int:
        try:
            return body()
        except MilestoneRefusal as refusal:
            return _refused(args, command, refusal.error, refusal.details)

    return run_on_graph(command, args, run)


def run_milestone_start(args: argparse.Namespace) -> int:
    """Run ``specdev milestone start`` on the parsed *args*; returns the exit code (0 started, 1 refused)."""
    def body() -> int:
        result = start_milestone(*roots(args), args.milestone)
        what = "already in progress, nothing written" if result.noop else f"{'resumed' if result.resumed else 'started'} ({result.previous} -> in_progress)" + ("; the deferral reason is cleared" if result.resumed else "")
        _emit(args, {"command": "milestone start", "milestone": result.milestone, "previous": result.previous, "noop": result.noop, "resumed": result.resumed, "notes": list(result.notes)}, "\n".join([f"milestone {result.milestone}: {what}", *result.notes]))
        return 0

    return _guarded("milestone start", args, body)


def run_milestone_defer(args: argparse.Namespace) -> int:
    """Run ``specdev milestone defer`` on the parsed *args*; returns the exit code (0 deferred, 1 refused)."""
    def body() -> int:
        spec_root, repo_root, _ = roots(args)
        result = defer_milestone(spec_root, repo_root, args.milestone, args.reason)
        _emit(args, {"command": "milestone defer", "milestone": result.milestone, "previous": result.previous, "reason": result.reason}, f"milestone {result.milestone}: deferred ({result.previous} -> deferred): {result.reason}")
        return 0

    return _guarded("milestone defer", args, body)


def _gate_lines(result: CloseResult) -> list[str]:
    report = result.report
    lines = [f"  deferred or won't-do task {task.task_id} ({task.disposition}): {task.reason or 'no reason'}" for task in report.paused]
    lines.extend(f"  {warning.render()}" for warning in report.warnings)
    lines.extend(f"  note: {note}" for note in report.notes)
    return lines


def _close_refused_text(result: CloseResult) -> str:
    by_owner: dict[str, list[SpecError]] = {}
    for error in result.report.errors:
        by_owner.setdefault(error.owner or CLOSE_OWNER, []).append(error)
    lines = [f"milestone {result.milestone} cannot be closed: {len(result.report.errors)} error(s)"]
    for owner, errors in by_owner.items():
        lines.append(f"{owner} ({len(errors)}):")
        lines.extend(f"  {error.render()}" for error in errors)
    return "\n".join([*lines, *_gate_lines(result)])


def _close_json(result: CloseResult) -> dict[str, Any]:
    report = result.report
    return {
        "command": "milestone close", "milestone": result.milestone, "closed": result.closed, "check": result.check_only, "passes": report.passed,
        "errors": [{"code": e.code, "owner": e.owner, "message": e.message, "node": e.node_id} for e in report.errors],
        "warnings": [{"code": w.code, "message": w.message, "node": w.node_id} for w in report.warnings],
        "notes": list(report.notes), "close": result.record, "signoff_tree": result.signoff_tree, "tree": result.tree,
    }


def _closed_text(result: CloseResult) -> str:
    record = result.record or {}
    lines = [f"milestone {result.milestone}: closed", f"  signed off by {record.get('signed_off_by')} ({record.get('signoff')}, tree {result.signoff_tree})", f"  closed at tree {result.tree}"]
    if result.signoff_tree != result.tree:
        lines.append("  note: the tree of the sign-off is not the tree the milestone is closed at")
    lines.append(f"  plan hash {record.get('plan_hash')}; the plan is frozen")
    return "\n".join([*lines, *_gate_lines(result)])


def run_milestone_close(args: argparse.Namespace) -> int:
    """Run ``specdev milestone close`` on the parsed *args*; returns the exit code (0 closed, or the gate passes with --check; 1 refused)."""
    def body() -> int:
        spec_root, repo_root, git_root = roots(args)
        result = close_milestone(spec_root, repo_root, git_root, args.milestone, gate_providers(spec_root, repo_root, git_root), check_only=args.check)
        if not result.report.passed:
            if args.json_output:
                print_json(_close_json(result))
            else:
                print(_close_refused_text(result), file=sys.stderr)
            return EXIT_ERROR
        text = _closed_text(result) if result.closed else "\n".join([f"milestone {result.milestone}: the close gate passes; nothing written", *_gate_lines(result)])
        _emit(args, _close_json(result), text)
        return 0

    return _guarded("milestone close", args, body)


def run_milestone_signoff(args: argparse.Namespace) -> int:
    """Run ``specdev milestone sign-off`` on the parsed *args*; returns the exit code (0 recorded, 1 refused)."""
    def body() -> int:
        spec_root, repo_root, git_root = roots(args)
        result = sign_off(spec_root, repo_root, git_root, args.milestone, gate_providers(spec_root, repo_root, git_root))
        document = {**view_dict(result.view), "command": "milestone sign-off", "record": result.record, "file": result.file}
        _emit(args, document, f"{view_text(result.view)}\n\nrecorded {result.record['signoff_id']} ({result.file}): tree {result.record['tree']}, signed by {result.record['git_author']['name']} <{result.record['git_author']['email']}>")
        return 0

    return _guarded("milestone sign-off", args, body)


def run_status(args: argparse.Namespace) -> int:
    """Run ``specdev status`` on the parsed *args*; returns the exit code (0 whatever it lists; 1 when it cannot read what it needs)."""
    def run(graph: Graph) -> int:
        spec_root, repo_root, git_root = roots(args)
        context = status_context(spec_root, repo_root, git_root, lock_if_present(spec_root), graph, gate_providers(spec_root, repo_root, git_root))
        if args.milestone:
            view = milestone_view(context, milestone_id_of(graph, spec_root, args.milestone))
            _emit(args, view_dict(view), view_text(view))
        else:
            sections = build_status(context)
            _emit(args, status_dict(sections), status_text(sections))
        return 0

    return run_on_graph("status", args, run)
