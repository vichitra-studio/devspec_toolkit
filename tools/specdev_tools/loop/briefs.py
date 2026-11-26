"""Briefs: the one file an agent is given. The tool writes each from the run's state, so
every dispatch of a role carries the same sections, and an agent is told nothing else."""

from __future__ import annotations

import json
from typing import Any

BUDGETS = {"reviewer": (60, 60_000), "fixer": (120, 20_000), "author": (150, 20_000), "executor": (200, 20_000)}
"""Tool calls and bytes of output a brief allows a role (agent text, not a check)."""

REVIEW_SHAPE = {
    "$schema": "vc:infra:findings",
    "round": "<the round, a number>",
    "scope": "<scope>",
    "coverage": {"assigned": ["<every id and path of 'Read'>"], "read": ["<what you read>"], "not_run": []},
    "judgements": [{"key": "<key from 'To judge'>", "verdict": "resolved | not_resolved | decline_right | finding_right", "quote": "<the text that shows it>"}],
    "findings": [
        {
            "kind": "gap | miss | bug | regression | assumption | ambiguity | hallucination | drift | coverage | determinism | seed-grounding",
            "location": "<node-id>[#field] | <artifact file>[#/pointer without index]",
            "message": "<what is wrong and why it matters, at most 600 characters>",
            "severity": "P0 | P1 | P2",
            "evidence_quotes": [{"source": "<node id or file path>", "text": "<exact text that occurs there>"}],
            "evidence": ["<optional: what else you cite, in your own words>"],
            "origin": "<optional: introduced-on-branch | pre-existing-on-main | stale-after-fix>",
            "suggested_fix": "<optional>",
        }
    ],
}

FIX_SHAPE = {
    "outcomes": [
        {
            "key": "<key from 'Findings'>",
            "outcome": "fixed | accepted | declined | recorded | upstream",
            "changed": ["<node ids or files you edited, for fixed>"],
            "basis": {"source": "<contract, upstream node or seed>", "text": "<quote that settles a choice you made>"},
            "quote": {"source": "<node or file>", "text": "<for declined: the text that refutes the finding; for accepted: the target's new text>"},
            "reason": "<one sentence>",
            "item_id": "<for recorded: the id of the open item you wrote>",
            "named": {"kind": "<kind>", "location": "<for upstream: the node that is wrong>"},
        }
    ],
    "noticed": ["<a contradiction you saw in a node you edited and did not fix>"],
}

AUTHOR_SHAPE = {
    "result": "written | nothing_to_add",
    "written": ["<node ids or files you wrote>"],
    "reason": "<for nothing_to_add: why the intent adds nothing to this step>",
    "open_items": ["<ids of the open items you recorded>"],
    "refusal": "<only when you cannot start: a prerequisite is missing, the artifact already exists>",
}

EXEC_SHAPE = {
    "result": "executed",
    "recorded": ["<action ids you carried out and recorded with `specdev plan record`>"],
    "awaiting_confirmation": ["<manual-verification action ids only a person can carry out>"],
    "skipped_at_deploy": ["<action ids that run at deploy>"],
    "held_by_open_item": ["<action ids you left unrecorded because an open item holds their item>"],
    "open_items": ["<ids of the open items you wrote into the plan>"],
    "refusal": "<only when you cannot start>",
}

HOW_TO_READ = {
    "step": "Use `specdev node show <id> --full --json`; never open a spec file directly.",
    "plan": "Use `specdev node show <id> --full --json` for a plan item and `specdev json read <plan file> <jq path>` for "
            "the rest of the plan; never open a spec file directly.",
    "code-group": "Read each code file with Read (a file that does not exist yet is a finding if its action was "
                  "recorded as done). Read the plan item with `specdev node show <item id> --full --json` and its "
                  "records with `specdev json read <plan file> .execution.records`.",
    "common": "Read the file's entries with `specdev json read <file> <jq path>`, and run `specdev seed-lint` and "
              "`specdev spec-check` on the spec with the roots; a failure of either is a finding.",
    "code-milestone": "Read each code file with Read, and the plan with `specdev json read <plan file> <jq path>`.",
}

SEVERITY = """A finding is P0 or P1 when it is a defect, however small: it affects consistency, completeness or drift, or leaves an
assumption, an ambiguity or a hallucination, in the spec or in what would be built from it. It is also P0 or P1 when
the artifact breaks a rule of its own contract and you quote that rule from the step's prompt or schema. It is P2 when
it is wording or preference: the spec would say the same thing and the build would be the same without the change.
The finding's kind does not set the severity. Between the two: P0 when someone who builds from the text as written
builds the wrong thing or cannot build, P1 when the text leaves the builder or a later step to guess. Both are fixed
before the run converges. The `message` of a P0 or P1 says the impact in one sentence: what goes wrong if it stays."""

NO_QUESTIONS = """You ask nobody. If the contract or an upstream node settles a choice, make it and quote that source as `basis`. If
nothing settles it, record an open item in this step's artifact (`about` names the upstream node or seed that is
silent or unclear, `proposed_assumption` your best answer if you have one), write nothing that depends on the answer,
and go on. List the ids an item may be about with `specdev node candidates --kind ambiguity-item --field about`."""


def _fence(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=2) + "\n```"


def roots_text(roots: dict[str, str]) -> str:
    return f"--repo-root {roots['repo']} --spec-root {roots['spec']} --git-root {roots['git']}"


def _head(role: str, meta: dict[str, Any], extra: str = "") -> list[str]:
    calls, size = BUDGETS[role]
    return [
        f"# Brief: {role}, run `{meta['run_id']}`{extra}",
        "",
        "Follow this brief and nothing else. Where a finding or a habit disagrees with the contract, the contract wins.",
        "",
        "## Contract (read first, in full)",
        *[f"- `{p}`" for p in meta.get("contract", [])],
        "",
        "## Roots",
        f"Every `specdev` command takes: `{roots_text(meta['roots'])}`",
        f"Run every command from `{meta['roots']['git']}`: a file argument such as `spec/<file>` is read from there. "
        "Where your agent file writes `<toolkit>`, `<spec>` or `<root>` (or `./devspec_toolkit`, `./spec`, `.`), use these roots.",
        "",
        "## Limits",
        f"At most {calls} tool calls. Your output file: at most {size} bytes.",
        "",
        *([f"Base ref for `git diff` (often empty: uncommitted work is read from the files): `{meta['base_ref']}`", ""]
          if meta.get("base_ref") and meta["kind"].startswith("code") else []),
    ]


def _output(expect: str, shape: Any) -> list[str]:
    return [
        "## Output",
        f"Write one file: `{expect}`. Write it under the name `{expect}.tmp` first, then rename it.",
        "Its shape:",
        _fence(shape),
        "Return one line: the path of the file.",
        "",
    ]


def reviewer(meta: dict[str, Any], *, round_no: int, nodes: list[str], context: list[str], judge: list[dict[str, Any]],
             known: dict[str, list[Any]], expect: str, retry_reason: str = "") -> str:
    lines = _head("reviewer", meta, f", round {round_no}")
    if retry_reason:
        lines += ["## Your first file was refused", retry_reason, ""]
    lines += [
        "## Read",
        "Review each of these, against the contract and against the nodes it links to. "
        + (HOW_TO_READ["common"] if (meta.get("scope") or {}).get("file") else HOW_TO_READ[meta["kind"]])
        + " You edit nothing.",
        *[f"- `{n}`" for n in nodes],
        "",
        "Context, not to be reviewed again: " + (", ".join(f"`{c}`" for c in context) or "none"),
        "",
        "## Severity",
        SEVERITY,
        "",
        "## To judge",
    ]
    if not judge:
        lines += ["Nothing.", ""]
    for j in judge:
        lines += [f"- key `{j['key']}` ({j['status']}): {j['message']}", f"  - the fixer: {j['fixer']}"]
    lines += [
        "",
        "For an `awaiting` finding say `resolved` or `not_resolved`; for an accepted link, whether the acceptance was right. "
        "For a `contested` finding say `decline_right` or `finding_right`. Quote the text that shows it.",
        "",
        "## Already known (raise again only if the text changed)",
    ]
    for title, values in known.items():
        lines += [f"- {title}: " + ("; ".join(str(v) for v in values) or "none")]
    lines += [
        "",
        "## Evidence",
        "Every finding needs at least one `evidence_quotes` entry whose text occurs in its source, character for "
        "character apart from whitespace. For something missing, quote the contract, seed or upstream node that requires it. "
        "A finding about a node of another step is still a finding: name that node as the location. "
        "No line numbers and no array indexes in a location.",
        "",
        "`coverage.read` must list every id above and every contract path. `scope` is "
        f"`{meta['scope_label']}` and `round` is {round_no}.",
        "",
    ]
    return "\n".join(lines + _output(expect, REVIEW_SHAPE))


def fixer(meta: dict[str, Any], *, findings: list[dict[str, Any]], expect: str, diffs_path: str | None) -> str:
    lines = _head("fixer", meta)
    code = meta["kind"] in ("code-group", "code-milestone")
    lines += ["## Findings", "One outcome per key."]
    for f in findings:
        lines += [f"- key `{f['key']}` [{f['source']}] at `{f['location']}`: {f['message']}"]
        for q in f.get("quotes", []):
            lines += [f"  - quote from `{q.get('source')}`: {q.get('text')}"]
        if f.get("instruction"):
            lines += [f"  - instruction (this finding cannot be declined): {f['instruction']}"]
    if code:
        lines += [
            "",
            "## Outcomes",
            "- `fixed`: you edited code inside the plan's `target_file_patterns` (or a listed supporting file), or carried "
            "out an action and recorded it with `specdev plan record <item>/<action> --outcome done`. Name the files you "
            "changed; for a record alone, name the plan file.",
            "- `declined`: the finding is wrong. Quote the text that refutes it.",
            "- `recorded`: the fix is outside what you may edit (another file, or the spec), or needs an answer nothing "
            "gives you. You wrote an open item into the plan; name its id.",
            "",
            "## Rules",
            "You ask nobody. Edit only what the findings name. Never edit a spec file other than through "
            "`specdev plan record` and the open-item commands of your agent file.",
            "",
        ]
        return "\n".join(lines + _output(expect, FIX_SHAPE))
    lines += [
        "",
        "## Outcomes",
        "- `fixed`: you edited, by node id (`specdev json patch|insert|delete --id`). Name what you changed.",
        "- `accepted` (link findings only): the holder still follows from its changed target; you ran "
        "`specdev attest <holder> --field <F> --target <T> --yes`. If the holder had to change, edit it first, then "
        "accept the link the same way and answer `fixed`. Take link findings upward first, in the order given.",
        "- `declined`: the finding is wrong, or demands content the contract excludes. Quote the text that refutes it.",
        "- `recorded`: the fix needs an answer nothing gives you. You recorded an open item; name its id.",
        "- `upstream`: the node here is right and the node it links to is wrong. Name that node.",
        "",
        "## Rules",
        NO_QUESTIONS,
        "Edit only the targets of the listed findings. Remove or shorten before adding. Provenance and citations go in "
        "this outcome file, never into spec text. After deleting a node or a link run `specdev attest --prune`. After "
        "your edits run `specdev spec-check spec --step <NN>` with the roots; after a glossary edit run `canon-accept` "
        "with `--update`.",
        "",
    ]
    if diffs_path:
        lines += [f"What changed above each suspect link: `{diffs_path}`", ""]
    return "\n".join(lines + _output(expect, FIX_SHAPE))


def author(meta: dict[str, Any], *, expect: str) -> str:
    mode, arg = meta["mode"], meta.get("mode_arg") or {}
    lines = _head("author", meta)
    step = meta["steps"][0] if meta["steps"] else "16a"
    if meta["kind"] == "plan":
        ms, batch = meta["scope"]["milestone"], meta["scope"].get("batch", "<batch_id>")
        lines += [
            "## Task",
            f"Author the plan of milestone `{ms}` as the contract (prompt 16a) says.",
            f"1. `specdev trace {ms} --down --kinds task --json` lists the milestone's tasks; "
            "`specdev trace --recipe 16a <task-id>` renders the pack of one. Render each.",
            f"2. Write the plan as a draft outside `spec/`: `.specdev/drafts/plan_{batch}.json`. Its file-level "
            f"`milestone` is `{ms}`.",
            f"3. Create the plan file: `specdev step create 16a {batch} --from .specdev/drafts/plan_{batch}.json` "
            "(`--dry-run` prints the report and writes nothing). Never write a file under `spec/` yourself.",
            "Answer with a refusal, and write nothing, if the milestone has no row in `spec/16_impl_context.json` or the "
            "command refuses (a second plan file for a milestone is E767).",
            "",
        ]
    elif mode == "author":
        lines += ["## Task", f"Author step {step}: write the draft and create the artifact with `specdev step create {step} --from <draft>`.", ""]
    else:
        lines += [
            "## Task",
            f"Extend the existing artifact of step {step} with content for this intent, by `specdev json insert` "
            "(by step or by node id). If the intent adds nothing to this step, answer `nothing_to_add` with the reason.",
            "",
            f"Intent: {arg.get('extend', '')}",
            *( [f"Seed: `{arg['seed']}`. Quote from it no more than the contract allows; no file-and-line reference in spec text."] if arg.get("seed") else [] ),
            "",
        ]
    lines += ["## Rules", NO_QUESTIONS, ""]
    return "\n".join(lines + _output(expect, AUTHOR_SHAPE))


def executor(meta: dict[str, Any], *, expect: str, actions: list[dict[str, Any]], files: list[str], plan_file: str) -> str:
    scope = meta["scope"]
    lines = _head("executor", meta)
    lines += [
        "## Task",
        f"Carry out the actions of plan item `{scope['group']}` of milestone `{scope['milestone']}` (plan file "
        f"`{plan_file}`), in order, and record each with `specdev plan record {scope['group']}/<action id> --outcome done`.",
        "",
        "Actions:",
        *[f"- `{a.get('id')}` ({a.get('type')}) {a.get('target', '')}: {a.get('description', '')}" for a in actions],
        "",
        "Files of this item: " + (", ".join(f"`{f}`" for f in files) or "none named"),
        "",
        "## Rules",
        "You ask nobody. When the item is ambiguous, write an open item into the plan and stop on that item; list the "
        "actions you left unrecorded under `held_by_open_item`. A manual-verification action only a person can carry "
        "out goes under `awaiting_confirmation`, unrecorded.",
        "",
    ]
    return "\n".join(lines + _output(expect, EXEC_SHAPE))
