# Step 14 · Roadmap

> **REQUIRED**: Before starting, read `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md` in full. All directives in that document apply to this step unless explicitly overridden below. Do not proceed without reading it.

Run `specdev prompt-context 14` to see downstream consumers.

## Role
You are a **senior technical program manager and roadmap strategist**. Your job is to emit a single JSON artifact for **Step 14 · Roadmap** that translates the implementation plan into an execution-ready milestone sequence with FR-level task decomposition. You do not write examples, tutorials, or comments. You only output the canonical JSON that matches the schema.

## Purpose
Synthesize the foundational strategy (Step 09: Implementation Plan), the detailed core specifications (Steps 00–12), and any discovered domain extensions (Step 13) into a cohesive **Execution Roadmap**. This artifact drives the "Just-In-Time" implementation loop by breaking the scope down into sequential, verifiable milestones, where **Each Milestone** corresponds to exactly **One User Story** decomposed into atomic sub-tasks.

## Extraction Intent

### Primary Sources (directly consumed)
- **09_impl_plan.json**: Design-level milestones as the starting structure; derive execution milestones from these. Each design milestone's `schedules` names the nodes it delivers; the task criteria of this step must refine them. Which design milestones a roadmap milestone covers is computed from its criteria: this step writes no field for it
- **04_fr_list.json**: FR ids and their acceptance criteria and `scope`; every FR in scope must be reached by ≥1 task criterion, and a task criterion is written against the acceptance criterion it makes testable
- **01_capabilities.json**: Capabilities and their `scope`; the work of a capability is reached through the FRs derived from it, and an invariant or NFR that constrains a capability applies to the tasks that refine what leads to it

### Reference Sources (context only)
- **00_charter.json**: Project scope, timeline constraints, and success criteria used to bound roadmap milestones and validate that no out-of-scope work is scheduled
- **02_system_sketch.json**: Component architecture, subsystem dependencies, and `third_parties` (technology choices and pins; Step 02 is the authoritative source) used to determine milestone sequencing so infrastructure precedes dependent application layers
- **02a_delivery_baseline.json**: Deployment environment specifications, gates and release cadence constraints incorporated into milestone target dates and infrastructure task planning
- **03_glossary.json**: Canonical domain terminology used to ensure consistent naming of milestones and tasks across the roadmap artifact
- **05_interface_contracts.json**: API endpoint definitions and API errors used to sequence API implementation tasks; a task criterion refines the API or API error it makes testable
- **06_invariants.json**: System invariant rules incorporated as task criteria so milestone completion preserves data integrity guarantees
- **07_nfrs.json**: Performance thresholds, security requirements, and compliance constraints incorporated as milestone risks and as task criteria for non-functional validation
- **08_fixtures.json**: Test fixture definitions; a task criterion lists in `verified_by` the fixtures that prove what it refines
- **10_governance.json**: Rules that tasks must satisfy; a rule is refined by a task criterion and is its own verifier
- **11_redteam.json**: Threats and edge cases (with their `mitigated_by`) used to populate milestone risks, inform task prioritization for security-critical sequences, and to be refined by task criteria
- **12_ci_gates.json**: Jobs (what they realise and verify); a job that realises or verifies a node is a verifier a criterion lists in `verified_by`
- **13_extension_manifest.json**: Extension manifest entries and `extension_decision` used to schedule extension implementation work as dedicated milestones; if `extension_decision.status == 'none-required'`, skip extension milestones entirely — this is correct behavior, not a gap

## Operating Flow: Ingest → Synthesize → Sequence → Decompose → Emit
- **Ingest**: Scan all `spec/` artifacts (Steps 00-13) to understand the complete scope.
- **Synthesize**: Identify every distinct feature, capability, and dependency across all specs.
- **Sequence**: Arrange milestones in logical order based on dependencies and critical path.
- **Decompose**: Break down Step 09 technical milestones into atomic user stories for Step 14.
- **Emit**: Generate a roadmap that groups these items into logical milestones using the JIT (Just-In-Time) philosophy—plan details iteratively while still providing required fields.

### Task Criteria Refine Upstream Obligations
Task `acceptance_criteria` in Step 14 REFINE the obligations of the steps above them (FR acceptance criteria, APIs, invariants, NFRs, threats and the rest): they break a high-level obligation into an implementation-verifiable check. The relation is the `refines` link of a criterion. Rules:
- **Every in-scope obligation is refined.** A criterion states how the obligation is observed or verified. The threshold or case it checks is one that an upstream node states (refine that node); a threshold or case that no upstream node states is not written here (see "Refinement Decision Rules"). A criterion that only repeats the obligation adds nothing.
- **One criterion per rule.** When several nodes state the same rule (an FR criterion and the API that carries it), the criterion `refines` the most downstream system or delivery node, not each of them.
- **Cross-cutting obligations are refined in every task they bind.** An invariant or NFR that constrains something a task builds gets a refining criterion in that task (`E744` otherwise).
- **A refinement carries its verifier.** `verified_by` lists a fixture, job or rule that proves what the criterion refines (`E745` otherwise). A criterion that refines a threat or an edge case is verified through that node's `mitigated_by`: a fixture listed there, or a fixture that verifies an obligation listed there (a fixture's `verifies` can never name a threat).
- **A child keeps its own `scope`.** Parking an FR with `scope` `later` or `out` does not park its acceptance criteria. Setting `scope` to `later` or `out` needs a `scope_reason` and leaves the links that point at the node suspect until attested.
- Task acceptance criteria MUST NOT contradict the criteria they refine.
- Task acceptance criteria SHOULD be more specific and implementation-testable (e.g., "unit test passes for UserService.deactivate()" refines "user account is deactivated and sessions invalidated").
- Every task criterion should be verifiable by a specific CI check, unit test, or manual procedure.

### Refinement Decision Rules
- **Stricter threshold** = invention, not a refinement: FR says "within 500ms", task says "within 200ms" — do not write 200ms; raise an open item about the FR criterion so that Step 04 decides, unless an upstream node (an NFR, an invariant) already states 200ms: then refine that node.
- **Weaker threshold** = contradiction: FR says "within 500ms", task says "within 1000ms" — FORBIDDEN.
- **Added edge case** = refinement only when an upstream node states it: FR says "user can login", the API error `err-login-invalid-credential` states "invalid credential returns an error response", the task criterion refines that API error; when no node states it, raise an open item about the FR criterion.
- **Removed condition** = contradiction: FR says "authentication required", task says "authentication optional" — FORBIDDEN.
- **More specific artifact** = refinement: FR says "page renders", task says "read operation for resource returns success with expected component" — OK.

**Step Authority**: Step 14 is the authoritative source for execution-level `migration_plan` entries and task-level `depends_on`. Step 09 provides the design-level implementation plan and stores no order between its milestones. This roadmap must reach everything a Step 09 milestone schedules (`E567` otherwise); a change of scope is made at Step 09 first, never here.

## Heuristics For Completeness
- **Unified View**: The roadmap must include items from BOTH the Core specs and any found Extensions.
- **Ordering**: Core dependencies (e.g., Auth, Base API) must precede dependent Extensions.

## Self-Audit Gate
> Per shared_expectations: if ANY item below cannot be satisfied, enter Clarify mode.
- `spec/09_impl_plan.json` is present and contains at least one milestone entry.
- `spec/04_fr_list.json` is present and contains at least one functional_requirements entry.
- `spec/01_capabilities.json` is present and contains at least one capability entry.

## Negative Constraints
- **NO Hallucinations**: Do not name technologies that are not `third_parties` of Step 02 or part of Step 13.
- **NO Computed Facts**: Do not add a field the schema does not define. Which design milestones a roadmap milestone covers, and whether an FR is delivered, are computed from the task criteria; milestone status lives on the Step 16 anchor row.
- **NO Vague Tasks**: Tasks must be atomic and specific.
- **NO Orphan Milestones**: Every milestone must map to a user story.
- **NO Backward Planning**: Dates must proceed logically from earliest to latest, and the milestones are listed in ascending `target_date` order (`E520` otherwise); the order states no dependency.
- **NEVER create a `depends_on` cycle**: Task A depending on B which depends on A is forbidden and is reported as `E703`.
- **NEVER refine or verify with an id that is not in the spec**: `refines`, `verified_by` and `depends_on` name existing nodes, of the kinds the schema accepts for the field (`E700` when no node has the id, `E701` for a node of another kind).
- **NEVER weaken an upstream AC, and never add a bar it does not state**: A task AC that relaxes a threshold, removes a condition, or contradicts a constraint of the originating FR acceptance criterion is a regression, not a refinement. A task AC that sets a stricter threshold or a new condition that no upstream node states is an invention: raise an open item about the FR criterion, so that Step 04 decides.
- **NO Ambiguous Task Scope**: Task `description` must name the specific deliverable artifact (endpoint, template, table, config, module) being created or modified. "Configure dependencies" is too vague — "Configure OAuth2 client credentials in session middleware settings" is specific.
- If `risk_status` is 'high' or 'critical', the `risks` array MUST contain >=1 entry naming the specific blocker.
- A task that is deliberately not built now carries a `disposition` (`value` `deferred` or `wont_do`, with a `reason`: for `deferred`, the blocker and the condition to resume). Do not delete the task to dodge a coverage finding. The milestone, tasks and task criteria of a closed milestone are not edited by id (`json patch|insert|delete --id` is E767): `specdev node status <id> not_applicable` parks one whose built target was deleted, and a change of the work is a new task or milestone.

## Coverage Closure
Before emitting, verify:
- Every in-scope obligation from ingested context is refined by ≥1 task criterion, OR parked in its own step with `scope` `later` or `out` and a `scope_reason`.
- No upstream capability, FR, or milestone is silently dropped.
- Every id in `refines`, `verified_by` and `depends_on` resolves to a node of the right kind.
- No node ids in prose: a mention that states a relation is a link field; any other mention is reworded; contract values (paths, error codes, field names) stay.
- If any upstream obligation cannot be refined: add a gap question (Clarify mode) rather than omitting it.
- [ ] Every upstream node this step must cover is used by a node of this step (`spec-check` reports an unused one, E740 to E745; `specdev coverage` lists them)
- [ ] No placeholder tokens remain (TBD, TODO, FIXME, XXX)
- [ ] All required fields populated from actual upstream data (not hallucinated)
- [ ] Every Step 09 milestone's scheduled node that a task criterion can refine is refined by a criterion of this roadmap, itself or through a node it contains. `spec-check` reports one that is not as `E567` on the Step 09 milestone: `fr <id> is scheduled by <milestone> but no task criterion refines it: add a task criterion that refines it or a node it contains, or remove it from the schedules of <milestone>`. A scheduled risk, component or environment is never reported
- [ ] Every FR in scope is reached by ≥1 task criterion: one that refines the FR, one of its acceptance criteria, or a node derived from them (an API that lists the FR in `derives_from`). `spec-check` reports one that is not as `E566`: `fr <id> is in scope but no task criterion reaches it: add a task criterion that refines it, one of its acceptance criteria or a node derived from it, or set its scope to later or out with a scope_reason`
- [ ] Task acceptance criteria refine (not contradict) the originating FR acceptance criteria
- [ ] Every criterion lists in `verified_by` a verifier of what it refines (`E745`); every fixture of Step 08 is listed by ≥1 criterion, and so is every job of Step 12 that realises and verifies nothing (`E742` otherwise)
- [ ] Every invariant and NFR that constrains something a task builds is refined by a criterion of that task (`E744`: `task <id> falls under <node> through <node> but no criterion of the task refines it`)
- [ ] Every threat, edge case, rule and API error in scope is used: refined by a criterion (`E740` otherwise); a criterion that refines a threat or edge case is verified through its `mitigated_by`
- [ ] Task acceptance criteria referencing interface contracts use the same method/operation and identifier pattern as defined in Step 05 interface contracts
- [ ] All required fields for downstream consumers (Step 15 scaffold, Step 16 trinity loop) are populated: `milestones[].tasks[].task_id`, `milestones[].tasks[].description` and `milestones[].tasks[].acceptance_criteria`

**Extraction Mandate**:
- Every FR in scope from `04_fr_list.json` must be reached by ≥1 task criterion. List any FR not reached (`E566` names it).

## Best Practices
- **One Milestone = One User Story**: Every milestone must map individually to a specific user story. Do not bundle multiple stories into one vague milestone.
- **Atomic Decomposition**: Each User Story must be broken down into specific, unambiguous, atomic sub-tasks.
- **Technology**: Names and pins belong to the `third_parties` of Step 02; do not restate them here. Add a task for a tool only when Step 13 extensions introduced it.
- **Sequence Dependencies**: Ensure "Infrastructure" or "Base API" milestones precede "UI" or "Complex Logic" milestones.
- **JIT Granularity**: Plan the immediate next 1-2 milestones in high detail (dates, criteria). Later milestones MUST use tentative target dates and MUST include at minimum a `task_id` and a `description` (>=2 words, imperative verb) for each task, but MAY omit `depends_on`. An in-scope FR still needs a refining criterion somewhere (`E566`), so give a later task at least the one criterion that reaches it, or park the FR in Step 04.
- **Deferral Notes**: Use the `milestones[].risks` field to note *why* a complex extension was deferred or split.
- **Atomicity Test**: If a task description contains 'and' connecting two independent work items, split it into two tasks. If a task cannot be merged or demoed independently, split it further. Target: each task completable in 1-3 days by one developer.
- **Gate**: After emitting the roadmap artifact, run `specdev spec-check spec --step 14 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` and read its `E566` and `E567` lines, and the `E740`, `E742` to `E745` lines it owns for Step 14. Fix each by adding or correcting a criterion, then follow the forward pass of `shared_expectations.md` section 9.1: a link written by path or by hand (E761), or an edit to a node that other nodes link to (E763), needs `specdev attest <node-id> --yes` for the node that holds the link; `specdev step create` and the id forms of `json patch|insert|delete` write the lock entry of a link themselves (`attest` then says `nothing to attest`). The paragraph "The attest step" under "Graph Role Checks" in `docs/developers/error-codes.md` explains it.

## Common Pitfalls
- **Ignoring Extensions**: When `extension_decision.status == 'extensions-required'`, failing to schedule the work defined in extension files (e.g. `ext_01_database.json`). When `status == 'none-required'`, skipping extension milestones is correct behavior — do not flag it as a gap.
- **Redoing Step 09**: Spending time debating "Python vs Go" (which was settled in Step 09) instead of planning "Sprint 1 vs Sprint 2".
- **Skipping Coverage**: Creating a roadmap for a spec full of holes; the step gate (`E566`, `E567`) is the final quality check before coding.
- **Echo Criteria**: A criterion that repeats the obligation it refines instead of stating what the obligation leaves open.
- **Wrong Link**: Listing a fixture in `refines` (it belongs in `verified_by`), or an obligation in `verified_by`.

## Cross-Step Synthesis Notes

### milestones[].target_date
- Use `YYYY-MM-DD` format.
- Ensure milestones are listed in chronological order.

### milestones[].risk_status
- Use only the enum values from the schema.
- Omit if you want the default (`low`).

### milestones[].tasks
- Use objects with `task_id` and `description` (optional `depends_on`, `disposition`).
- `task_id` must be kebab-case and unique across the whole spec, not only within its milestone: the same `task_id` in two milestones is reported as E704. The schema suggests the prefix `task-`.
- `description` must be atomic and specific (at least two words).
- Use imperative verb form in `description` (e.g., "Implement authentication module").
- Use `acceptance_criteria` for every task that delivers an obligation; include `criterion_id` (unique across the whole spec, like `task_id`, and not reusing a Step 04 criterion id; a duplicate is reported as E704 by `spec-check`; the schema suggests the prefix `tc-`), a `text` meeting the schema's minimum length, `refines` (what the criterion makes testable; required unless it carries `removes`) and `verified_by` (the fixtures, jobs or rules that prove it).

### tasks[].depends_on
- List `task_id` values of this roadmap that this task depends on.
- Do not create circular dependencies (A → B → A is forbidden).
- Omit or use `[]` when the task has no dependencies.

### milestones[].risks
- List only risks that are directly related to the milestone.
- Use clear, actionable language (e.g., "Dependency on external API" rather than "Technical risk").

### milestones[].spikes
- Document only technical investigations that are necessary to resolve uncertainty.
- Keep spikes brief and focused on a single question or hypothesis.
- Guidance, not checked: write each spike as one string that names the question, the time budget and the expected output. Review judges it.

### migration_plan
- Use a short string giving the migration sequence and how it is reversed, or `"none"` if not applicable.
- What is replaced is stated by links (`replaces` on the node that takes the place of a deleted one, a criterion's `removes`), and what confirms the migration is a task criterion with a verifier in `verified_by`: a criterion refines an upstream node, and when none states the bar, raise an open item instead. Neither goes in this string: no tool reads a link out of it.
- Keep it to one or two sentences; avoid rehashing Step 09.
- If not `"none"`, use at least three words and keep it under 40 words.
- Guidance, not checked (no tool measures the length).

### Invariant-Fixture Cross-Check
- An invariant from Step 06 is proven by a fixture of Step 08 whose `verifies` names it (`E743` reports an invariant with none). The criterion that refines the invariant lists that fixture in `verified_by`. A missing fixture is a gap question for Step 08, not a reason to leave the invariant unrefined.

### Governance and CI Gate Binding
- If Step 10 defines commit or PR rules that require spec ids, they apply to commits and pull requests. A task `description` or criterion `text` names no node id (`E752`): the relation is the criterion's `refines`.
- If Step 02a defines gates that gate milestone completion, the final task of the milestone gets a criterion that refines the gate and lists in `verified_by` the Step 12 job that realises it.

# Note on `$schema`
The `$schema` field is required in the output and is stripped before validation during prompt-schema sync checks.

# Schema Reference
- Schema URI: vc:14-roadmap
- Schema File: schema/14_roadmap.schema.json
- Schema Registry: tools/schema_registry.json

# Output Contract
```json
{
  "$schema": "vc:14-roadmap",
  "id": "roadmap-v1",
  "owner": "system",
  "created_at": "2025-01-01T00:00:00Z",
  "migration_plan": "none",
  "milestones": [
    {
      "milestone_id": "ms-core-foundation",
      "name": "Core Foundation",
      "user_story": "As a developer, I want a stable base API so that I can build authentication features.",
      "tasks": [
        {
          "task_id": "task-init-fastapi-project",
          "description": "Initialize FastAPI project structure",
          "acceptance_criteria": [
            {
              "criterion_id": "tc-project-structure-ready",
              "text": "Project boots with FastAPI app and expected folder layout.",
              "refines": ["ac-project-boots-1"],
              "verified_by": ["fix-project-boots"]
            }
          ]
        }
      ],
      "target_date": "2025-02-01"
    }
  ],
  "canonical_refs_used": []
}
```

