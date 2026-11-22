"""``p4_step10_rules``: the step-10 policy fields become rules (DOC "Step-10 rules" and "Step-10 content").

``p2_id_mint`` already turned each ``pr_rules`` string into a rule object with an id.  This script, from the migrated tree and
the capture (section ``governance``):

- maps a rule that is a command name to ``cli_command``: ``validate-all`` to ``spec-check``, ``matrix`` to ``coverage``, any
  other name the generated command list (``tools/cli_commands.json``) knows to itself;
- lists a rule whose name is NOT a toolkit command (``test``, ``lint``, ``build``, ``security``) as a worklist item that
  proposes the step-12 job running it (matched on the job's step commands; none: add a job);
- turns each ``review_policy.verdict_requirements`` string into a rule with ``enforcer: review``, then removes ``review_policy``
  (its other fields name no rule), ``reviewers`` and ``spec_first_policy`` (the capture holds them);
- lists every rule without ``derives_from`` as a worklist item: the upstream reason is judgement (a charter constraint, risk
  or scope item, a 02a gate or environment, or an approver-only stakeholder).  No ``derives_from`` is written.

``commit_message_rules``, ``versioning``, ``policy_ref`` and ``command_ref`` are not touched.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from specdev_tools.core.json_utils import resolve_effective_toolkit_root
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.ids import mint_slug, suggest_prefix
from specdev_tools.graph.names import REVIEW_ENFORCER, RULE
from specdev_tools.migration.maps import shape_rows
from specdev_tools.migration.registry import PHASE_CONTENT, Problem, ScriptResult, ScriptSpec
from specdev_tools.migration.scripts.v1_2_0.p1_capture import CAPTURE_REL, LEGACY
from specdev_tools.migration.scripts.v1_2_0.p2_plan_milestone_key import insert_key, step_data, step_file
from specdev_tools.migration.worklist import WorklistItem, add_items, make_item, missing_items

SCRIPT = ScriptSpec(id="p4_step10_rules", phase=PHASE_CONTENT, requires=("p2_id_mint",), touches=("10", "extras"))

GOVERNANCE_STEP = "10"
KIND_JOB = "rule-job"
KIND_REASON = "rule-reason"
RENAMED_COMMANDS = {"validate-all": "spec-check", "matrix": "coverage"}
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_COMMANDS_FILE = os.path.join("tools", "cli_commands.json")


def known_commands(ctx) -> frozenset[str]:
    """The names of the generated command list of the toolkit being migrated to (the running toolkit's list when the root has none)."""
    root = ctx.toolkit_root if os.path.isfile(os.path.join(ctx.toolkit_root, _COMMANDS_FILE)) else resolve_effective_toolkit_root(None)
    with open(os.path.join(root, _COMMANDS_FILE), encoding="utf-8") as handle:
        return frozenset(entry["path"] for entry in json.load(handle)["commands"])


def _rules(ctx) -> list[dict[str, Any]]:
    rules = step_data(ctx, GOVERNANCE_STEP).get("rules")
    return [r for r in rules if isinstance(r, dict)] if isinstance(rules, list) else []


def _captured(ctx) -> dict[str, Any]:
    return ctx.documents.load(CAPTURE_REL).data.get("governance") or {}


def _legacy_names(ctx) -> set[str]:
    return {name.strip() for name in _captured(ctx).get(LEGACY + "pr_rules") or [] if isinstance(name, str)}


def _command_of(name: str, commands: frozenset[str]) -> str | None:
    wanted = RENAMED_COMMANDS.get(name, name)
    return wanted if wanted in commands else None


def _mappable(ctx) -> list[tuple[dict[str, Any], str | None]]:
    """The legacy rules still to map: ``(rule, command or None)`` for a rule that came from ``pr_rules``, is a bare name and has no enforcer yet."""
    commands, names = known_commands(ctx), _legacy_names(ctx)
    return [
        (rule, _command_of(rule["text"].strip(), commands))
        for rule in _rules(ctx)
        if isinstance(rule.get("text"), str) and rule["text"].strip() in names and _NAME.match(rule["text"].strip())
        and "cli_command" not in rule and "enforcer" not in rule
    ]


def _jobs_running(ctx, name: str) -> list[str]:
    pattern = re.compile(rf"(?<![a-z0-9-]){re.escape(name)}(?![a-z0-9-])")
    return [
        job["job_id"]
        for job in step_data(ctx, "12").get("jobs", [])
        if isinstance(job, dict) and isinstance(job.get("job_id"), str)
        and any(isinstance(s, dict) and pattern.search(str(s.get("command", ""))) for s in job.get("steps", []))
    ]


def _review_texts(ctx) -> list[str]:
    policy = step_data(ctx, GOVERNANCE_STEP).get("review_policy")
    texts = policy.get("verdict_requirements") if isinstance(policy, dict) else None
    return [t.strip() for t in texts or [] if isinstance(t, str) and t.strip()]


def _items(ctx, extra_rules: list[dict[str, Any]]) -> list[WorklistItem]:
    items = []
    for rule, command in _mappable(ctx):
        if command is None:
            jobs = _jobs_running(ctx, rule["text"].strip())
            how = f"job {', '.join(jobs)} runs it: let that job `realises` the rule" if jobs else "no step-12 job runs it: add a job that does and `realises` the rule"
            items.append(make_item(GOVERNANCE_STEP, KIND_JOB, rule["rule_id"], audience="agent", blocking=False,
                                   evidence=f"rule {rule['rule_id']} was the pr_rules entry {rule['text']!r}, which is not a toolkit command", proposal=how))
    for rule in [*_rules(ctx), *extra_rules]:
        if "derives_from" not in rule:
            items.append(make_item(GOVERNANCE_STEP, KIND_REASON, rule["rule_id"], audience="agent", blocking=True,
                                   evidence=f"rule {rule['rule_id']} ({rule.get('text', '')!r}) has no upstream reason",
                                   proposal="derive it from a charter constraint, risk or scope item, a 02a gate or environment, or an approver-only stakeholder; if its text is only a command name, write it as one falsifiable sentence"))
    return items


def _review_rules(ctx, taken: set[str]) -> list[dict[str, Any]]:
    held = {r.get("text") for r in _rules(ctx) if r.get("enforcer") == REVIEW_ENFORCER}
    made = []
    for text in _review_texts(ctx):
        if text not in held:
            new_id = mint_slug(text, taken, prefix=suggest_prefix(RULE))
            taken.add(new_id)
            made.append({"rule_id": new_id, "text": text, "enforcer": REVIEW_ENFORCER, "scope": "in"})
    return made


def _stale_keys(ctx) -> list[str]:
    data = step_data(ctx, GOVERNANCE_STEP)
    return [key for key in (row["path"] for row in shape_rows(SCRIPT.id)) if key in data]


def _planned_reasons(ctx) -> list[dict[str, Any]]:
    """The review rules the script would add, for the reason items of a first run (ids are only for the items' keys; the rules are made again in ``apply``)."""
    return [{"rule_id": mint_slug(text, set(), prefix=suggest_prefix(RULE)), "text": text} for text in _review_texts(ctx)]


def detect(ctx) -> int:
    """Rules to map, review rules to make, policy fields to remove, and items not listed yet."""
    return sum(1 for _, command in _mappable(ctx) if command) + len(_review_texts(ctx)) + len(_stale_keys(ctx)) + len(missing_items(ctx, _items(ctx, _planned_reasons(ctx))))


def apply(ctx) -> ScriptResult:
    """Map the rules, add the review rules, remove the policy fields, list what needs a person."""
    name = step_file(ctx, GOVERNANCE_STEP)
    data = ctx.documents.load(name).data if name else {}
    mapped = _mappable(ctx)
    for rule, command in mapped:
        if command is not None:
            insert_key(rule, "cli_command", command, after="text")
    made = _review_rules(ctx, set(build_graph(ctx.spec_root, ctx.toolkit_root).by_id))
    if made:
        data.setdefault("rules", []).extend(made)
    listed = add_items(ctx, _items(ctx, []))
    stale = _stale_keys(ctx)
    for key in stale:
        del data[key]
    residue = (
        f"rules mapped to a command: {sum(1 for _, c in mapped if c)}; rules that are not toolkit commands: {sum(1 for _, c in mapped if c is None)}",
        f"review rules made from review_policy.verdict_requirements: {len(made)}",
        f"policy fields removed: {', '.join(stale) or 'none'}",
    )
    return ScriptResult(edits=sum(1 for _, c in mapped if c) + len(made) + len(stale) + listed, worklist_items=listed, residue=residue)


def verify(before, after) -> list[Problem]:
    """The three policy fields are gone, and ``commit_message_rules`` and ``versioning`` are as they were."""
    problems = []
    for rel, document in sorted(after.documents.items()):
        if rel[:2] != GOVERNANCE_STEP or not isinstance(document, dict):
            continue
        old = before.documents.get(rel) or {}
        problems += [Problem(f"{rel}: {key} is still there", rel) for key in (row["path"] for row in shape_rows(SCRIPT.id)) if key in document]
        problems += [Problem(f"{rel}: {key} changed", rel) for key in ("commit_message_rules", "versioning") if document.get(key) != old.get(key)]
    return problems
