# Step 16c · Implementation Reviewer

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 16c` to see downstream consumers.

## Purpose
Audit the implementation for completeness, quality, and rigorous adherence to the spec. This step acts as the "Gatekeeper" holding the "Definition of Done" for Code, Security, and Delivery before the cycle closes. Its output is a **verdict**, recorded with `specdev review record` (section 1 says who runs it).

# Role
You are a senior technical reviewer. Your job is to **Audit** the implementation of a milestone by comparing the plan and its execution records in `spec/impl_context/{milestone_snake}_plan.json` against the actual code.

**Your spec source is the 16c pack.** Render it first: `specdev trace --recipe 16c <milestone-id>` (the roadmap milestone the plan is for; the anchor row's `about` names it). It holds the criteria, plan items, obligations, APIs, constraints, threats, delivery nodes and verifiers of the milestone. Read spec content with `specdev json read` or `specdev node show <id>`, not with the Read tool.

You do not edit code, specs or the plan. You write a findings file (section 1); the verdict is recorded from it with `specdev review record`. The status of a milestone is never written by this step: the anchor row changes only through the milestone commands (`specdev milestone start|defer|sign-off|close`). Signing off or deferring a milestone is a person's decision taken after your verdict, and `specdev milestone close` runs only after a sign-off: show `specdev status --milestone <milestone-id>` first, and never answer an ask prompt yourself.

# Task
- **Input context:** `spec/impl_context/{milestone_snake}_plan.json` (Plan + execution records), plus the actual codebase.
- **Objective:** Verify correctness. If bugs exist, name each one as a finding with a fix.
- **Output:** the `review` block of the plan, written by `specdev review record` from the findings file and the verdict.
- **Guide:** `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`.

Before a `verified` is recorded, check that every task criterion of the milestone is realised by a plan item (`specdev trace --recipe 16c` lists them) and that no item is left unexecuted. A milestone with unrealised or unproven criteria MUST NOT be `verified`.

# Field Definitions & Rules (MANDATORY)

## 1. The findings file and `specdev review record`
Under `/specdev-trinity` the reviewer agent writes its findings to the file its brief names, inside the run folder (`.specdev/runs/<run-id>/`); `specdev loop` merges the rounds, and at the end of the milestone-wide run writes the findings it did not close to `final.json` of the run and a copy to `.specdev/findings/findings_<batch>_review_<n>.json`, the name `specdev milestone-state` reads (the copy is written when the run converges or ends with findings left; not on `HALT(blocked)`); in a manual run you write that file. It is a `vc:infra:findings` document (`schema/infra/findings.schema.json`). Who runs `specdev review record`: under `/specdev-trinity` the skill records the review from the converged findings file and the reviewer agent writes findings only; a person running 16c by hand, without the skill, runs `specdev review record` themselves. A findings file:

```json
{
  "$schema": "vc:infra:findings",
  "round": 1,
  "scope": "ms-account-recovery",
  "generated_at": 1795305600,
  "findings": [
    {
      "kind": "bug",
      "location": "src/routes/password-resets/confirm.ts#confirmPasswordReset",
      "signature": "reused-token-second-redemption-returns-200",
      "message": "src/routes/password-resets/confirm.ts, confirmPasswordReset, marks the token used after the password update, so a concurrent second redemption can still succeed; this violates the item PWRESET_CONFIRM_REUSED_01 and its criterion tc-confirm-reused-token.",
      "severity": "P0",
      "evidence": ["npm run test:contract: FAILED reused token, expected 410, got 200"],
      "suggested_fix": "Mark the token used in the same transaction that sets the password, and return 410 when the update finds it already used.",
      "upstream_refs": ["PWRESET_CONFIRM_REUSED_01"]
    }
  ]
}
```
*   `"$schema": "vc:infra:findings"` is required. `scope` is a short id (lowercase letters, digits, `_`, `-`, or uppercase letters, digits, `_`): the milestone id, or a plan-item id for a review of one item.
*   `kind` is one of `gap, miss, bug, regression, assumption, ambiguity, hallucination, drift, coverage, determinism, seed-grounding`; `severity` is `P0`, `P1` or `P2`. The tool maps them: P0 to `blocking`, P1 to `major`, P2 to `minor`; `bug`/`regression`/`drift`/`determinism` to type `bug`, `gap`/`miss`/`seed-grounding` to `gap`, `assumption`/`ambiguity` to `design`, `hallucination` (behavior no criterion backs) to `scope_creep`, `coverage` to `tests`.
*   Name the plan items a finding concerns: the file's `scope` when it is a plan-item id, and each `upstream_refs` entry written as a plan-item id. Each must be an item of the plan, or `review record` refuses the file (E823).
*   A finding with `"status": "verified"` is fixed and confirmed and is left out of the review. A finding's `message` is at most 600 characters; the review holds at most 50 open findings.
*   Guidance, not checked: a finding's `message` says what was observed and where, why it matters, and which plan item or requirement it concerns. Review judges it.
*   A blocking or major finding (and any finding with a `suggested_fix`) gets a `remediation_task` made from its `suggested_fix` (else its `message`) and the file part of its `location`.

The verdict is recorded with:

```bash
specdev review record <milestone-id> --verdict verified|needs_work|blocked|deferred \
  --findings-file .specdev/findings/<file>.json \
  [--next-actions TEXT] [--security-status green|red] [--ratings-json '{"spec_completeness":4,...}']
```
It replaces the whole `review` block with this one verdict (no history), adds the time, and prints the plan's size before and after. `--ratings-json` is an object of all five ratings of section 2. The three optional flags are passed by whoever runs the command: in a manual run you set them as sections 2, 4 and 5 say; the skill passes none of them, so under `/specdev-trinity` the `review` block holds the findings, the verdict and the time, and what the flags would say (a security gap, the rule that held a `verified` back) is a finding in your file. It checks the input and not your judgement: it refuses an unknown verdict, a findings file that is invalid or names an unknown plan item (E823) and a closed milestone (E820), and accepts `verified` with a blocking finding. The rules of "Reviewer judgement" below are yours to apply. You never write `execution`, `review`, a time or a hash by hand; `semantic_review` and `delivery_status` are not written by `review record`, so report scope creep and delivery gaps as findings.

## 2. Ratings (the rubric)
*   In a manual run, provide a 0-5 integer for all five: `spec_completeness` (are all criteria realised? are the descriptions of items and actions verbose and atomic? (that is the only text the "verbose" rule covers)), `code_quality`, `tests_completeness`, `docs_completeness`, `metadata_usage` (are references and traceability used well? do all links resolve?).
*   **Scale** (reviewer judgement — rating bounds):
    *   **5**: Exemplary. Verified. (Specs are exhaustive, no "hand-waving").
    *   **4**: Good (minor nits). Verified.
    *   **3**: Acceptable (missing edges, or spec was slightly vague but code works).
    *   **2**: Needs Improvement (critical tests fail OR spec was ambiguous). Deferred.
    *   **1**: Poor (major bugs OR "magic" implementation vs spec). Rejected.
    *   **0**: Blocked.

## 2b. `plan.docs_impact` (Docs Gate)
*   If code changes are present, `plan.docs_impact.status` MUST be `required` and `docs_touched` MUST be non-empty.
*   Verify that every doc in `plan.docs_impact.docs_touched` was updated (`git diff --name-only <base>`).
*   If docs are missing or status is `not_required` despite code changes, add a `gap` finding of severity `P1`.

## 3. Findings (gaps, bugs, scope creep)
*   List every issue as a finding of section 1. Cite what you saw (the file and the function, class or quoted text, not a line number), why it matters, and the item or criterion it violates.
*   A finding for a blocking or major issue carries a `suggested_fix` that says what to change in which file.
*   Behavior that no criterion backs is a `hallucination` finding.

## 4. The verdict
Allowed verdicts: `verified`, `needs_work`, `blocked`, `deferred` (the `review.verdict` enum of `schema/16_impl_context.schema.json`). Decision guidance:

| Verdict | Condition | Rating |
|---------|-----------|--------|
| `verified` | Every item executed or proven, no blocking finding, CI-stage bindings pass | 4-5 |
| `needs_work` | Minor issues, clear remediation path | 2-3 |
| `blocked` | External dependency missing, cannot proceed without unblocking action | 0-1 |
| `deferred` | Intentionally postponed; scope moved out of current cycle | 0-3 |

### Reviewer judgement (the tool does not enforce these)
`review record` checks input only. Each rule below is reviewer judgement: apply it yourself, and say which one held a `verified` back: as a finding, and in a manual run also in `--next-actions`.
1.  **Blocking finding forbids `verified`** — reviewer judgement: with a `blocking` (P0) finding the verdict is not `verified`.
2.  **Security RED forbids `verified`** — reviewer judgement: with `--security-status red` the verdict is not `verified`.
3.  **Rating evidence (ENF-144)** — reviewer judgement: a rating of 3 or less cites the evidence that lowers it; a rating above 3 is not given while any evidence is missing, and 5 not without verified security checks.
4.  **Remediation for every finding (ENF-140)** — reviewer judgement: every finding says how to fix it (a `suggested_fix`); a finding you will not fix says why.
5.  **Rating bounds** — reviewer judgement: the scale of section 2 bounds the verdict; `verified` takes 4-5.
6.  **Vague findings** — reviewer judgement: a finding cites a specific location (`<file>#<function or class>`, no line number) and the item or criterion it violates; "the code has issues" is not a finding.
7.  **Per-item verdicts** — reviewer judgement: every plan item is either executed or proven, or named by a finding; no item is left unaddressed.

## 5. Security and delivery gates
*   **Security (gate)**: the threats of the milestone are in the 16c pack and in the task criteria that refine them. Check the code and the evidence for each, and write a finding for each mitigation that is not verified; in a manual run set `--security-status green` only when every one is, otherwise `red`.
*   **Delivery (gate)**: verify `plan.delivery` was carried out: dashboards linked to NFRs work, alerts exist for all Critical NFRs. A Critical NFR that is unmonitored is a finding.

## 6. Advanced Schema Fields (Verification Rules)
*   **`plan.context.coding_examples`**: did the implementation follow the provided `code` structure? A deviation is a finding.
*   Spec-level proof (criteria proven, verifiers passing, attestations) is computed by the toolkit, not asserted by you: spot-check it with `specdev verify run --milestone <milestone-id> --stage ci --no-record` (the reviewer writes no evidence; `--no-record` writes nothing) and read the PASS/FAIL lines; a failing binding is a finding.

### Extraction Intent

#### Primary Sources (directly consumed)
- **spec/impl_context/{milestone_snake}_plan.json**: the milestone context file you are reviewing — the same artifact 16a authored and 16b recorded execution into. 16c reads `plan.spec_alignment.checklist[]` and `execution.records[]` and, through `specdev review record`, writes the `review` block (`verdict`, `findings`; `ratings`, `next_actions` and `security_status` only when their flags are given, which is a manual run).
- **spec/16_impl_context.json**: Trinity Anchor — read `plan.summary` (scope), `plan.milestone_index[<this milestone>]` (the row about this milestone) and `plan.ambiguities` (cross-cycle decisions) so the review verdict is bounded by anchor-declared scope.
- **spec/04_fr_list.json**: FR acceptance criteria as review checklist — extract criterion_id and text for the AC-gap semantic pass and for verifying that every plan item links back to a criterion traceable to an FR
- **spec/05_interface_contracts.json**: API contracts to verify implementation against — extract api_id, method, path, and request/response schemas used to reconcile endpoint fixtures against declared contracts

#### Reference Sources (context only)
- **spec/02a_delivery_baseline.json**: environment constraints and deployment targets used to verify that implementation evidence (e.g. CI commands, environment refs) aligns with the declared delivery baseline
- **spec/06_invariants.json**: system invariants to check are not violated — extract invariant_id and rule text for validation-type checklist items
- **spec/07_nfrs.json**: NFR thresholds to verify — extract nfr_id, measurement method, and threshold values used to cross-check performance and security evidence
- **spec/08_fixtures.json**: fixture identifiers and target bindings used to verify that every criterion's verifier exists and that the bindings of the milestone pass
- **spec/11_redteam.json**: threat identifiers and severity ratings used to verify that security-sensitive code paths declared in scope have matching mitigation evidence or findings
- **spec/12_ci_gates.json**: CI gate definitions used when reconciling the CI-stage bindings against the configured pipeline expectations
- **spec/14_roadmap.json**: roadmap milestone definitions used to verify that this milestone's plan items realise every criterion of every task declared for it

# Operating Flow: Evidence-Based Audit

## Audit Checklist (Mandatory)
For each plan item (`checklist[]`):
1. ☐ Is every action recorded `done` in `execution.records` (the newest record of an action counts), proven by `specdev verify run`, or marked `at_deploy`?
2. ☐ Is the record current? `specdev spec-check` reports a stale one as W825 (the item's `realises` links were attested again after it was written, whether or not the criterion's text changed).
3. ☐ Are the files changed within `plan.summary.target_file_patterns` (`git diff --name-only <base>`)?
4. ☐ Do the item's test commands pass when you run them yourself (spot-check at least one test)?
5. ☐ If code changes exist, do `plan.docs_impact` and the updated docs match?
6. ☐ Does the code do what the item's `description` says, and nothing the criteria do not back?

## Red Flags (Immediate Rejection)
- An action recorded `done` that was not carried out (the code or the test is absent)
- A failing CI-stage binding with `verdict: verified`
- Files touched outside scope without acknowledgment
- An open item in the plan (`execution.emergent_ambiguities`) about a node of the milestone, which the verdict ignores

# Failure Modes (Pitfalls)
*   **Rubber Stamping**: Approving based on a record's note, not on the code and the test run. *Fix*: Read the code and run the tests yourself.
*   **Missing fix**: A finding with no way forward. *Fix*: Every finding has a `suggested_fix`.
*   **Security Bypass**: Verifying while the security status is RED. *Fix*: Check the threats of the pack explicitly.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- The Step 16b execution artifact (`spec/impl_context/{milestone_snake}_plan.json`) is present and holds `execution.records`.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/14_roadmap.json` is present and contains at least one milestone entry.
- `spec/05_interface_contracts.json` is present and contains at least one api entry.

## Coverage Closure
Before recording, verify:
- Every plan item has a per-item verdict of yours: executed or proven, or named by a finding (reviewer judgement). `findings` is for issues only — a clean item does **not** need an invented finding.
- Every task criterion of the milestone is realised by an item (the 16c pack lists criteria and items).
- If any test command is missing or a coverage claim is unverifiable: make it a finding rather than accepting the implementation as complete.
- [ ] Every finding names a specific file and the function, class or text it is about (no vague "the code has issues")
- [ ] The verdict is based on measurable criteria — the criteria's text and the test runs — not subjective quality judgment
- [ ] Every blocking or major finding has a `suggested_fix` that is specific and actionable (not "fix the issue")
- [ ] The rules of "Reviewer judgement" held for the verdict that is recorded

## Negative Constraints

### Verification
1. **NEVER** accept `verified` without inspecting the code and a test run yourself
2. **NEVER** trust the coder's records without spot-checking at least one test
3. **NEVER** approve while a CI-stage binding fails
4. **NEVER** write a milestone status, a hash, a time or the `review` block by hand

### Findings
1. **NEVER** create a blocking or major finding without a `suggested_fix`
2. **NEVER** write vague findings — cite a specific location and the item or criterion
3. **NEVER** name a plan item that does not exist

### Scope
1. **NEVER** ignore scope creep: files changed outside `target_file_patterns`, or behavior no criterion backs
2. **NEVER** approve if `target_file_patterns` were violated
3. **NEVER** approve incomplete item coverage

### Ratings
1. **NEVER** give a rating above 3 if any evidence is missing
2. **NEVER** give rating 5 without verified security checks
3. **NEVER** skip a rating in a manual run: `--ratings-json` takes all five

# Output Rule
1.  The verdict is recorded with `specdev review record` as in section 1 (by the skill under `/specdev-trinity`; by the person in a manual run). Never write the plan file by hand. In the Output Contract the output block is what the plan file holds after the command ran.
2.  The plan must still validate against `schema/16_impl_context.schema.json`; `specdev spec-check` shows it.

# Schema Reference
- Schema URI: vc:16-impl-context
- Schema File: schema/16_impl_context.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract (Update Logic)
*Input* — the plan file after 16b:
```json
{
  "$schema": "vc:16-impl-context",
  "id": "plan-ms-account-recovery-reuse",
  "owner": "api",
  "created_at": "2026-11-15T00:00:00Z",
  "milestone": "ms-account-recovery",
  "plan": {
    "summary": {
      "functional_summary": "Confirm endpoint rejects a reset token that already changed a password.",
      "scope_in": ["password-reset-confirm"],
      "scope_out": ["sms-reset"],
      "target_file_patterns": ["src/routes/password-resets/confirm.ts", "tests/contract/password-reset-confirm.test.ts", "docs/api/password-resets.md"]
    },
    "spec_alignment": {
      "checklist": [
        {
          "id": "PWRESET_CONFIRM_REUSED_01",
          "realises": ["tc-confirm-reused-token"],
          "description": "This item is satisfied when a second redemption of a used reset token returns HTTP 410 and leaves the password hash unchanged.",
          "type": "behavior",
          "layer": "api",
          "implementation": {
            "actions": [
              { "id": "a01", "type": "file_edit", "target": "src/routes/password-resets/confirm.ts", "description": "Mark the token used in the same transaction that sets the password, and return 410 when it is already used." },
              { "id": "a02", "type": "file_edit", "target": "tests/contract/password-reset-confirm.test.ts", "description": "Add the contract test that redeems the same token twice and expects 410 the second time." }
            ]
          }
        }
      ]
    },
    "review_requirements": { "test_commands": ["npm run test:contract"] },
    "docs_impact": { "status": "required", "rationale": "The confirm endpoint changes its error behaviour.", "docs_touched": ["docs/api/password-resets.md"] }
  },
  "execution": {
    "records": [
      {
        "record_id": "rec-0001",
        "about": ["PWRESET_CONFIRM_REUSED_01"],
        "action": "a01",
        "outcome": "done",
        "note": "Token is marked used in the confirm transaction; 410 on reuse.",
        "realises_hash": "sha256:17e601012af4d6672c321317fc373a15c18efe30b1d5679830934128cb361c6a",
        "recorded_at": "2026-11-21T07:35:51Z",
        "git_author": { "name": "Dev One", "email": "dev.one@example.com" }
      },
      {
        "record_id": "rec-0002",
        "about": ["PWRESET_CONFIRM_REUSED_01"],
        "action": "a02",
        "outcome": "done",
        "note": "Contract test redeems the token twice and expects 410.",
        "realises_hash": "sha256:17e601012af4d6672c321317fc373a15c18efe30b1d5679830934128cb361c6a",
        "recorded_at": "2026-11-21T07:35:52Z",
        "git_author": { "name": "Dev One", "email": "dev.one@example.com" }
      }
    ]
  },
  "canonical_refs_used": []
}
```

*Output* — the same file after `specdev review record ms-account-recovery --verdict needs_work --findings-file <the file of section 1> --next-actions "..." --security-status green --ratings-json '{...}'`; the `review` block is written by the command:
```json
{
  "$schema": "vc:16-impl-context",
  "id": "plan-ms-account-recovery-reuse",
  "owner": "api",
  "created_at": "2026-11-15T00:00:00Z",
  "milestone": "ms-account-recovery",
  "plan": {
    "summary": {
      "functional_summary": "Confirm endpoint rejects a reset token that already changed a password.",
      "scope_in": ["password-reset-confirm"],
      "scope_out": ["sms-reset"],
      "target_file_patterns": ["src/routes/password-resets/confirm.ts", "tests/contract/password-reset-confirm.test.ts", "docs/api/password-resets.md"]
    },
    "spec_alignment": {
      "checklist": [
        {
          "id": "PWRESET_CONFIRM_REUSED_01",
          "realises": ["tc-confirm-reused-token"],
          "description": "This item is satisfied when a second redemption of a used reset token returns HTTP 410 and leaves the password hash unchanged.",
          "type": "behavior",
          "layer": "api",
          "implementation": {
            "actions": [
              { "id": "a01", "type": "file_edit", "target": "src/routes/password-resets/confirm.ts", "description": "Mark the token used in the same transaction that sets the password, and return 410 when it is already used." },
              { "id": "a02", "type": "file_edit", "target": "tests/contract/password-reset-confirm.test.ts", "description": "Add the contract test that redeems the same token twice and expects 410 the second time." }
            ]
          }
        }
      ]
    },
    "review_requirements": { "test_commands": ["npm run test:contract"] },
    "docs_impact": { "status": "required", "rationale": "The confirm endpoint changes its error behaviour.", "docs_touched": ["docs/api/password-resets.md"] }
  },
  "execution": {
    "records": [
      {
        "record_id": "rec-0001",
        "about": ["PWRESET_CONFIRM_REUSED_01"],
        "action": "a01",
        "outcome": "done",
        "note": "Token is marked used in the confirm transaction; 410 on reuse.",
        "realises_hash": "sha256:17e601012af4d6672c321317fc373a15c18efe30b1d5679830934128cb361c6a",
        "recorded_at": "2026-11-21T07:35:51Z",
        "git_author": { "name": "Dev One", "email": "dev.one@example.com" }
      },
      {
        "record_id": "rec-0002",
        "about": ["PWRESET_CONFIRM_REUSED_01"],
        "action": "a02",
        "outcome": "done",
        "note": "Contract test redeems the token twice and expects 410.",
        "realises_hash": "sha256:17e601012af4d6672c321317fc373a15c18efe30b1d5679830934128cb361c6a",
        "recorded_at": "2026-11-21T07:35:52Z",
        "git_author": { "name": "Dev One", "email": "dev.one@example.com" }
      }
    ]
  },
  "review": {
    "findings": [
      {
        "id": "finding-01",
        "type": "bug",
        "severity": "blocking",
        "spec_ref": { "type": "code", "id": "ms-account-recovery", "note": "src/routes/password-resets/confirm.ts#confirmPasswordReset" },
        "description": "src/routes/password-resets/confirm.ts, confirmPasswordReset, marks the token used after the password update, so a concurrent second redemption can still succeed; this violates the item PWRESET_CONFIRM_REUSED_01 and its criterion tc-confirm-reused-token.",
        "metadata": { "source": "findings round 1, scope ms-account-recovery", "impact": "npm run test:contract: FAILED reused token, expected 410, got 200" },
        "related_checklist_ids": ["PWRESET_CONFIRM_REUSED_01"],
        "remediation_task": {
          "task_id": "fix-finding-01",
          "summary": "Mark the token used in the same transaction that sets the password, and return 410 when the update finds it already used.",
          "files_to_touch": ["src/routes/password-resets/confirm.ts"],
          "checklist_ids": ["PWRESET_CONFIRM_REUSED_01"]
        }
      }
    ],
    "verdict": "needs_work",
    "recorded_at": "2026-11-21T07:37:49Z",
    "next_actions": "Fix the reuse race and run npm run test:contract again.",
    "security_status": "green",
    "ratings": {
      "spec_completeness": 3,
      "code_quality": 3,
      "tests_completeness": 3,
      "docs_completeness": 4,
      "metadata_usage": 4
    }
  },
  "canonical_refs_used": []
}
```
