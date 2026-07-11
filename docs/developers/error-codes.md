# Error Codes Reference

## Validation Error Codes

### E110 UNKNOWN_CANONICAL_ID

**Trigger**: A `cn:`-prefixed ID used in a spec artifact is not registered in any loaded canon directory (toolkit core canon or project canon).  Commonly fires when `--spec-root` / `--git-root` are omitted and the project-level canon is not discovered, or when the ID is genuinely absent from all canon files.

**Resolution**: Run `specdev guide E110` for the full playbook.  Quick summary:
1. Re-run the check with the correct flags so the project canon is loaded:
   ```
   specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
   ```
2. If the ID is new, declare it in `canonical_proposals` in the artifact, then promote with `specdev canon-accept`.

**See also**: E120, E211.

### E120 CANONICAL_KIND_MISMATCH

**Trigger**: A canonical reference (`{id, kind, version}`) resolves to a registered canon entry whose `kind` differs from the `kind` declared on the reference — e.g. a spec artifact references `cn:project:foo` with `kind: "api"` but the canon registry has that ID registered under `kind: "capability"`. Raised by `CanonRegistry.validate_ref` in `tools/specdev_tools/canonical/registry.py`.

**Resolution**: Fix the `kind` field on the reference to match the canon entry's registered kind, or — if the reference's kind is actually correct — correct the canon entry's `kind` at its source of truth and re-run `specdev canon-accept` to re-promote it.

**See also**: E110.

### E520 UNRESOLVED_INPUT / SCHEMA_NOT_FOUND

**Trigger**: A validator could not resolve a required input and fails closed rather than crashing. Three message families share this code:
- `UNRESOLVED_INPUT` — a required directory, file, or spec input was missing or unreadable (e.g. `missing_spec_dir`, `missing_canon_dir`, `invalid_json`), or a CLI input precondition was not met.
- `schema_not_found` — the schema registry could not load the schema for a `$schema` URI. As of 1.1.0, `specdev validate` / `spec-check` fail closed on **all** registry I/O errors (previously only `FileNotFoundError` was caught; `PermissionError` and other `OSError`s now route here instead of escaping uncaught). The step-11 validator likewise emits a structured `E520` for malformed `threats[]` / `target_ids[]` entries that previously raised an unhandled `AttributeError`.
- `checklist-proof` / `docs_impact` content validation — the step-16 checklist validator (`step_16.py`) emits `E520` when a proof-required checklist item (a non-deferred, non-`wont_do` item whose `type` is not in the docs/metadata/logging/config exemption set) has no `nfr_refs` while its FR has NFRs traced in `07_nfrs.json`, or has no `fixture_ref`; and separately when a milestone plan has code-change actions (non-doc `file_create`/`file_edit` targets) but `plan.docs_impact` is missing, its `status` is not `"required"`, `docs_touched` is empty, or a `docs_touched` entry does not match a `doc_paths` pattern from `seed_manifest.json`.

**Resolution**: Supply the missing input (pass the correct `--spec-root` / `--git-root`, create the expected `spec_dir`, or fix the malformed JSON). For `schema_not_found`, confirm the `$schema` URI is registered in `tools/schema_registry.json` and that the target schema file exists and is readable. For `checklist-proof` failures, add the missing `nfr_refs` / `fixture_ref` to the checklist item (or mark it `deferred`/`wont_do` if genuinely out of scope). For `docs_impact` failures, set `plan.docs_impact.status` to `"required"` and list the touched doc paths in `docs_touched`, matching a pattern in `seed_manifest.json`'s `doc_paths`.

### E530 INVENTED_ENUM_OR_ID

**Trigger**: A value in a spec artifact does not match any allowed enum member, canonical ID, or registered entry.  The most common variant is a leading verb in a `command` field that is not in the toolkit or project allowlist.

**Resolution**: Run `specdev guide E530-INVENTED_ENUM_OR_ID` for the full playbook.  Quick summary: extend `spec/canon/command_prefixes.json` with the allowed verb, or register the verb as a canonical command entry and attach a sibling `command_ref`.

**See also**: E530-LINKED_TEST_FILE_NOT_FOUND, E110.

### E530 LINKED_TEST_FILE_NOT_FOUND

**Trigger**: A `linked_test_expectation` field contains a path-shaped token (containing a slash or a recognised extension: `.py`, `.ts`, `.js`, `.go`, `.java`, `.rb`, `.sh`, `.json`) that does not exist on disk.  `bash -c "..."` / `sh -c '...'` wrappers are unwrapped before the check.  Compound commands (`&&`, `||`, `;`) are skipped.

**Resolution**: Run `specdev guide E530-LINKED_TEST_FILE_NOT_FOUND` for the full playbook.  Quick summary: correct the path in the artifact with `specdev json patch`, or create the missing test file at the referenced path.

**See also**: E530-INVENTED_ENUM_OR_ID.

### E125 ALIAS_SUNSET_EXPIRED

**Trigger**: A canonical alias with a past `sunset_date` is used in a spec artifact.

**Resolution**: Replace the alias with the canonical term specified in the `replaced_by` field of the alias lifecycle block.

### E211 PARTIAL_DRIFT

**Trigger**: The same term maps to different canonical IDs across different spec artifacts (N-1 updated, 1 stale).

**Resolution**: Update the stale artifact(s) to use the current canonical ID. The error message includes per-artifact paths showing which file uses which canonical ID.

### E511 PLACEHOLDER_SCAN_MISMATCH

**Removed prior to 1.0.0**. E511 (`PLACEHOLDER_SCAN_MISMATCH`) was redundant with E510 independent placeholder scan. The associated sub-field has been removed.

### E535 CONTRADICTORY_OUT_OF_SCOPE_FR

**Trigger**: A functional requirement appears in both `apis.out_of_scope[]` in step 05 (declaring it has no HTTP API surface) and in an API's `trace[]` in the same step 05 file (declaring it is covered by an API endpoint). The two claims are mutually exclusive.

**Resolution**: Remove the FR from `out_of_scope[]` if an API does cover it, or remove the trace reference from the API if the FR genuinely has no API surface.

**Note**: `out_of_scope[]` entries suppress W564 (UNCOVERED_FR_API). Without this check, a contradicted `out_of_scope[]` entry would silently mask a real API trace from coverage reporting.

### E536 CONTRADICTORY_OUT_OF_SCOPE_FR_FIXTURE

**Trigger**: A functional requirement appears in both `fixtures.out_of_scope[]` in step 08 (declaring it needs no fixture) and in a fixture's `targets[]` in the same step 08 file (declaring it is covered by a fixture). The two claims are mutually exclusive. Independent of E535 — Step 05's "no API surface" and Step 08's "no fixture" are separate scoping decisions (see `step08_oos_fr_ids` in `traceability_closure.py`).

**Resolution**: Remove the FR from `out_of_scope[]` if a fixture does cover it, or remove the target reference from the fixture if the FR genuinely needs no fixture.

**Note**: `out_of_scope[]` entries suppress W565 (UNCOVERED_FR_FIXTURE). Without this check, a contradicted `out_of_scope[]` entry would silently mask a real fixture target from coverage reporting.

### E541 UNBOUND_CANONICAL_TERM

**Trigger**: A free-text field (e.g. a `description`, `rationale`, or `intent`) mentions a canonical term registered in `canon/` without a sibling binding reference (a `*_ref` slot) that pins the term to its canonical ID. The mention reads as an unbound, hallucination-prone reference.

**Resolution**: Add the appropriate `*_ref` (e.g. `fr_ref`, `capability_ref`, `term_ref`) alongside the free-text field to bind the canonical term to its ID, or reword the field so it no longer names the canonical term.

**Note**: E541 is suppressed through four independent mechanisms; a free-text field is checked only if none of them apply:

1. **Structural suppression** (as of 1.1.0) — fields whose enclosing object is *structurally unbindable*: the object's schema sets `additionalProperties: false` and declares no `*_ref`/`*_refs` slot, so it physically cannot carry a binding reference.

2. **Namespace-aware slot-kind suppression** (as of 1.1.0, round 4) — an object whose schema sets `additionalProperties: false` and declares only *purpose-specific* ref slots (e.g. `fr_refs`, `capability_refs`, `metric_ref`) that cannot accept a `term`/`acronym` canonical ID is also suppressed. The check extracts the kind labels from each `*_ref`/`*_refs` slot name (e.g. `fr_refs` → kind `fr`; `capability_refs` → kind `capability`) and suppresses E541 for a given term when the term's canonical kind (e.g. `term`) is absent from the slot-kind set. Example: `14_roadmap` milestones have `fr_refs`/`capability_refs` (slot kinds `{"fr", "capability"}`); a `term`-kind canonical ID has no namespace overlap → E541 is suppressed. Objects that DO have a matching slot (e.g. `03_glossary.json` `terms[]` items with `term_ref`) are NOT suppressed by this mechanism — they fall through to mechanism 3 (runtime binding check).

3. **Term-specific runtime suppression** (the `bound_refs` path) — when a sibling `*_ref`/`*_refs` key is present at the same object level, it suppresses E541 only for the specific term(s) it binds: suppression applies when one of the ref's *values* is one of the mentioned term's canonical IDs. An unrelated reference (binding a different ID) does **not** suppress, so a genuinely unbound term in the same object still fires. (Prior to this release the check was object-level — any ref present suppressed every free-text field — which over-suppressed legitimate unbound mentions.)

4. **Key-name skip fallback** (the `_E541_SKIP_KEYS` / `_E541_SKIP_KEYS_BY_FILE` path) — certain keys are always exempt regardless of schema, because their subtrees are vocabulary definitions or free-form runner output rather than spec content that should bind refs. The complete set of exempted keys, sourced from `hallucination_lint.py` lines 774–838:

   **Global skips (`_E541_SKIP_KEYS`):**

   *Category A — canonical vocabulary subtrees:*
   - **`canonical_proposals`**, **`canonical_refs_used`**, **`canonical_conflicts`** — canonical metadata; not spec content that should bind refs
   - **`tech_stack`**, **`user_segments`**, **`seeds`** — structured enumerations whose values are not canonical term-binding sites

   *Category B — Step 16 implementation/narrative subtrees (belt-and-suspenders for `impl_context/` artifacts with variable filenames where `$schema` lookup is unreliable):*
   - **`actions`**, **`coding_examples`** — Step 16a/16b implementation subtrees
   - **`emergent_ambiguities`**, **`ambiguities`**, **`docs_impact`** — Step 16 narrative subtrees
   - **`review_requirements`** — Step 16 operational verification instructions (test commands, NFR measurement methods); these are not canonical term-binding sites. Note: structural suppression cannot reliably cover these because `test_commands[]` uses `oneOf` and `nfr_measurement_methods` uses `patternProperties`, both of which can cause `slot_kinds` to resolve as `None` under certain schema-navigation paths.

   *Category C — free-form runner output:*
   - **`execution`** — `execution.final_status.test_results` items have `additionalProperties` unset (intentionally free-form test-runner output). The structural rule requires `additionalProperties: false` and will NOT suppress items with unset `additionalProperties`, so a key-name skip is necessary. Example subtree that triggers this: a `16_impl_context.json` artifact's `execution.final_status.test_results[]` items describing test-runner output such as `{"name": "test_send_newsletter", "status": "passed", "duration": 1.2}`.

   **File-scoped skips (`_E541_SKIP_KEYS_BY_FILE`):**
   - **`edge_cases` in `11_redteam.json`** — unbindable narrative subtree; the red-team schema sets `additionalProperties: false` with no `*_ref` field on `edge_cases` items. Scoped to that file to avoid silently exempting a future `edge_cases` key in another artifact.
   - **`definition` in `03_glossary.json`** — glossary definitions are vocabulary prose; requiring `term_ref` bindings for every cross-term mention in the definition text is semantically incorrect. This skip applies only when the file's basename is `03_glossary.json`; a `definition` field in any other file is still checked normally. Note: the glossary `terms[]` object DOES have `term_ref`/`acronym_ref` slots (used to pin the entry's own canonical ID), so the namespace-aware structural rule does NOT suppress it — this explicit skip is required.

   For artifacts with no resolvable `$schema` (where structural suppression and namespace-aware slot-kind suppression are inactive), two mechanisms remain active: the key-name skip (mechanism 4) and the term-specific runtime `bound_ref_ids` suppression (mechanism 3). Mechanism 3 — the `bound_ref_ids` collection at `hallucination_lint.py` lines 898–904 — is unconditional and has no guard on `schema_node`; the check `if cids & bound_ref_ids: continue` (line 959) fires regardless of whether `$schema` resolved. A sibling `*_ref` binding the mentioned term therefore suppresses E541 for that specific term even in a schema-free artifact.

### E560 TRACEABILITY_GAP

**Trigger**: Fired by the traceability-closure check (`check_traceability_closure()`) for two Charter → Capabilities gaps: (1) `charter_goal_without_capability` — a Step 00 charter `goals[].goal_id` is not referenced by any Step 01 capability's `trace[]` (a trace entry of the charter-goal type); or (2) `charter_success_metric_without_capability` — a Step 00 charter `success_metrics[].metric_id` is not referenced by any capability's `success_metric_refs[]`. Only fires when both `00_charter.json` and `01_capabilities.json` are present. Note: E560 previously covered a `capability_without_fr` check (a capability with no tracing FR); that check was superseded by W568/E568 UNCOVERED_CAPABILITY, and E560 now covers only the two charter-level gaps described above.

**Resolution**: For `charter_goal_without_capability`, add a capability in `01_capabilities.json` with a `trace[]` entry referencing the uncovered `goal_id`. For `charter_success_metric_without_capability`, add the `metric_id` to the appropriate capability's `success_metric_refs[]`.

**Promotable**: `PROMOTABLE_PAIRS` registers `W560 → E560`, but the emission direction is inverted in practice: `check_traceability_closure()` only ever emits `E560` directly (never `W560`). The forward-replay check (`forward_replay_check.py`) re-runs traceability closure during PR-scoped analysis and downgrades any `E560` finding it sees to `W560` (code substitution), so a Charter→Capability gap is advisory during incremental replay. Outside forward-replay, E560 fires as a full error.

**See also**: E568 (capability → FR coverage — the check E560 formerly performed).

### E561 / W561 UNCOVERED_FR

**Trigger**: A functional requirement defined in step 04 is not assigned to any milestone in step 14 (`fr_refs`).

**Resolution**: Add the FR ID to the appropriate milestone's `fr_refs` array in `14_roadmap.json`. If the FR has no implementation surface (e.g. an infra or ops constraint), add it to `out_of_scope[]` in `05_interface_contracts.json` with a non-empty rationale — that exempts it from W561, W564, and W566.

### E562 / W562 ORPHAN_MILESTONE

**Trigger**: A milestone in step 14 is not referenced by any checklist item in step 16a.

**Resolution**: Either add FR references to the milestone or add checklist items that reference the milestone's tasks.

### E563 / W563 CHECKLIST_ROADMAP_MISMATCH

**Trigger**: A roadmap task exists in step 14 but has no corresponding checklist item in step 16a.

**Resolution**: Create a checklist item with `spec_ref.id` matching the roadmap `task_id`, or mark the task as deferred.

### E564 / W564 UNCOVERED_FR_API

**Trigger**: A functional requirement defined in step 04 has no API trace reference — no API in step 05 has a trace link with type "fr" pointing to this FR.

**Resolution**: Add a trace link of type "fr" in the appropriate API contract in `05_interface_contracts.json`. If the FR genuinely has no HTTP API surface (infra, ops, external constraint), add it to `out_of_scope[]` in `05_interface_contracts.json` with a non-empty rationale — that suppresses W564, W561, and W566 for that FR. See also E535 for the contradiction check.

**Promotable**: W564 → E564.

### E565 / W565 UNCOVERED_FR_FIXTURE

**Trigger**: A functional requirement defined in step 04 has no fixture coverage — no fixture in step 08 has a target with type "fr" pointing to this FR.

**Resolution**: Add a fixture in `08_fixtures.json` with a target referencing the FR, or add it to `out_of_scope[]` in `08_fixtures.json` with a non-empty rationale — that suppresses W565 for that FR. This is a separate exemption list from `05_interface_contracts.json`'s `out_of_scope[]`: an FR with no API surface can still need a fixture (e.g. a background job), so the two are not interchangeable — populate whichever step's `out_of_scope[]` actually applies to the FR.

**Promotable**: W565 → E565.

### E566 / W566 UNCOVERED_FR_MILESTONE

**Trigger**: A functional requirement defined in step 04 is not referenced in any step 14 milestone `fr_refs`.

**Resolution**: Add the FR ID to the appropriate milestone's `fr_refs` array in `14_roadmap.json`. If the FR has no implementation surface, use `out_of_scope[]` in `05_interface_contracts.json` with a non-empty rationale — that exempts it from W566, W564, and W561.

**Promotable**: W566 → E566.

### E567 / W567 INCOMPLETE_MILESTONE_DECOMPOSITION

**Trigger**: A milestone in step 14 has no tasks, or the milestone's `fr_refs` are not covered by any task's `fr_refs`.

**Resolution**: Add tasks to the milestone, or ensure task `fr_refs` collectively cover the milestone's `fr_refs`.

**Promotable**: W567 → E567.

### E568 / W568 UNCOVERED_CAPABILITY

**Trigger**: A capability defined in step 01 has no functional requirement tracing to it. This replaces the former E560 `capability_without_fr` check.

**Resolution**: Add an FR in `04_fr_list.json` that traces to the uncovered capability, or remove the capability if it is no longer relevant.

**Promotable**: W568 → E568.

### E569 / W569 GOVERNANCE_PR_RULE_UNCOVERED

**Trigger**: Fired by the traceability-closure check when a Step 10 governance `pr_rules[]` entry (a rule-name string) is not a substring of any CI job step's `command` field across all jobs in `12_ci_gates.json`. Only fires when both `10_governance.json` and `12_ci_gates.json` are present.

**Resolution**: Add or update a CI job step in `12_ci_gates.json` whose `command` references the uncovered rule name, so the governance rule is demonstrably enforced in CI.

**Promotable**: W569 → E569.

### E575 / W575 IMPL_PLAN_DELIVERABLE_UNCOVERED

**Trigger**: Fired by the traceability-closure check for Step 09 impl-plan deliverable → Step 14 roadmap pairwise completeness. For each Step 09 milestone `deliverables[].id`, the ID must be referenced by at least one Step 14 task's `fr_refs[]` or appear in any Step 14 milestone's `deliverables[].id`. Only fires when both `09_impl_plan.json` and `14_roadmap.json` are present.

**Resolution**: Reference the Step 09 deliverable ID from a Step 14 task's `fr_refs[]`, or add a matching `deliverables[]` entry to the covering Step 14 milestone.

**Promotable**: W575 → E575.

### E576 / W576 TASK_EXECUTION_MISSING

**Trigger**: Fired by the traceability-closure check for Step 14 task → Step 16b execution pairwise completeness. For each Step 14 task with `status` not in (`done`, `deferred`, `wont_do`), verify the task_id appears in the executed-task set derived from `execution.critical_evidence.satisfied_checklist_ids` on each Trinity Anchor milestone plan, resolved through that plan's checklist `spec_ref.id`. A task is also exempt if every checklist item covering it already has `checklist_status` `deferred` or `wont_do` (a transitional-pause allowance mirroring E304). Only fires when execution data was loaded from at least one milestone plan and `14_roadmap.json` is present.

**Resolution**: Record execution evidence for the task — add its checklist item's `id` to `execution.critical_evidence.satisfied_checklist_ids` in the covering milestone plan, or mark the task `deferred`/`wont_do` in `14_roadmap.json` if it is legitimately paused or cancelled.

**Promotable**: W576 → E576.

### E582 / W582 UNCOVERED_FR_REVIEW_COVERAGE

**Trigger** (E582): Fired in step 16 under two conditions: (1) a checklist item's `milestone_ref` names a milestone that does not exist in the step 14 roadmap; or (2) a non-deferred checklist item's `milestone_ref` does not match the milestone that owns its `spec_ref.id` task in the step 14 roadmap.

**Trigger** (W582): Fired in step 16c when a review artifact with `verdict: verified` has FRs declared in the corresponding step 14 roadmap milestone(s) that are not present in `semantic_review.fr_coverage`. If no milestone is scoped, the check runs against all milestones in the roadmap.

**Resolution**: For E582 — correct the checklist item's `milestone_ref` to match an existing step 14 milestone that owns the referenced task. For W582 — add the missing FR IDs to `semantic_review.fr_coverage` in the step 16c artifact, or verify that the FR is intentionally excluded.

**Promotable**: W582 → E582.

### W584 REMEDIATION_TASK_LINK_UNKNOWN

**Trigger**: Fired in step 16a when a `review` section is present on the same Trinity-loop artifact (post-split model: 16a plan / 16b code / 16c review share one `spec/impl_context/{milestone_id}.json` file) and a `review.findings[].remediation_task.checklist_ids` entry does not resolve to any `id` in the artifact's `plan.spec_alignment.checklist[]`. Indicates the planner accepted a reviewer's remediation task without representing it as a plan checklist item.

**Resolution**: Add a checklist item to `plan.spec_alignment.checklist[]` whose `id` matches each referenced `checklist_ids` entry, or correct the `remediation_task.checklist_ids` value to reference an existing checklist item.

### E410 CANONICAL_ALIAS_COLLISION

**Trigger**: Fired in two distinct contexts:
- **Canon manifest** (`canonical/lint.py`): a canonical registry manifest contains a duplicate entry `id`, a duplicate `(kind, normalized)` alias pair, or a single alias that resolves to more than one target `id`.
- **Seed manifest** (`seed_lint.py`): `spec/common/seed_manifest.json` declares two or more `seeds[]` entries sharing the same `seed_id` value.

**Resolution**: For canon-manifest collisions, remove or rename the duplicate entry or alias in the relevant `canon/` manifest file. For seed-manifest collisions, ensure each entry in `seed_manifest.json` `seeds[]` has a unique `seed_id`; deduplicate or rename the conflicting entries.

### E150 / W150 SEED_MANIFEST_NOT_PROVIDED

**Trigger**: A step listed in `seed_manifest.json`'s `step_requirements` has no corresponding seed documents available.

**Resolution**: Ensure the step's required seeds (as declared in `spec/common/seed_manifest.json` → `step_requirements`) are present and accessible.

**Promotable**: W150 → E150.

### W140 SEED_CONTENT_OVERLAP_LOW

**Trigger**: A spec artifact for a seed-consuming step shares fewer than 3 content tokens with the seed documents required by `seed_manifest.json` for that step. Applies to any pipeline step (00–16c) for which `step_requirements` declares seeds.

**Resolution**: Either incorporate content from the required seed documents into the artifact or review whether the step truly depends on those seeds.

### W551 UNDECLARED_SEED

**Trigger**: An on-disk seed file (under a directory declared in the manifest's `seeds[].path` entries) is not declared in the `seeds[]` array of `spec/common/seed_manifest.json`.

**Resolution**: Either add the file to the `seeds[]` array in `seed_manifest.json` with an appropriate `seed_id` and `path`, or remove the undeclared file from the seed directory.

### W553 SEED_STEP_UNKNOWN

**Trigger**: A key in `seed_manifest.json` `step_requirements` is not a recognized pipeline step in `step_order.json` (e.g. a typo such as `"9"` instead of `"09"`, a non-existent step `"02b"`, or an out-of-range value `"17"`). Real pipeline steps including `"16"`, `"16a"`, `"16b"`, and `"16c"` do not trigger this warning.

**Resolution**: Fix the typo in the `step_requirements` key to match a real step ID, or remove the phantom entry.

**Note**: W553 was previously named `SEED_STEP_OUT_OF_RANGE` (fired for any step outside 00–02a). It was repurposed in DEVSPEC-43 to fire only on genuinely unknown steps, enabling seed routing to all pipeline steps.

### W554 HARDCODED_SEED_REFERENCE

**Trigger**: A prompt file contains a literal `seed_*.md` filename (matched by the pattern `seed_\w+\.md`). `spec/common/seed_manifest.json` is the authoritative source for seed names; hardcoding seed filenames in prompts duplicates that authority and drifts silently when seed names change.

**Resolution**: Remove the literal seed filename from the prompt. Reference seed documents through the manifest's `step_requirements` routing, not by name in prompt prose. Run `specdev hardcoded-seed-check` to identify all occurrences.

**Warning-only and non-promotable**: W554 has no E-counterpart (E554 is `CANON_ENUM_DRIFT`) and is excluded from `PROMOTABLE_PAIRS`, so neither `SPECDEV_WARNINGS_AS_ERRORS` nor `SPECDEV_PROMOTE_CODES` can escalate it to an error.

### W555 STEP00_SEED_OUT_OF_SCOPE_THIN

**Trigger**: Seeds routed to step `"00"` in `seed_manifest.json` `step_requirements` supply fewer than 3 substantive out-of-scope items in aggregate. The Step 00 charter schema requires `out_of_scope minItems:3`, so thin seeds cause authors to hit a gate failure or to hallucinate content at authoring time. "Substantive" means a markdown bullet item under an out-of-scope / non-goals heading that is NOT a bracket-only placeholder (e.g. `[Non-goal 1]`), NOT a template scaffold label (e.g. `- **Expectation**:`), and NOT content inside a fenced code block (delimited by ` ``` ` or `~~~`). Fence tracking matches the opening delimiter, so a `~~~` line inside a ` ``` `-opened fence (or vice-versa) is treated as fenced content, not a closing delimiter. Items are counted across ALL seeds routed to step 00 combined; W555 fires at most once per `lint_seeds()` invocation.

**Resolution**: Add at least 3 real, project-specific out-of-scope items to the seed(s) routed to step 00. The heading must match one of the accepted variants (case-insensitive): `Out-of-Scope`, `Non-Goals`, or `Non-Goal`. A good out-of-scope item describes a concrete capability that is deliberately excluded from scope — for example "Multi-tenant support is deferred to Phase 2" or "Offline mode is not in scope for MVP".

**Warning-only and non-promotable**: E555 already exists as `SEMANTIC_COVERAGE_REGRESSION` (a structurally different code with different semantics) and W555 is intentionally excluded from `PROMOTABLE_PAIRS`, so neither `SPECDEV_WARNINGS_AS_ERRORS` nor `SPECDEV_PROMOTE_CODES` can escalate W555 to an error.

### E581 / W581 MILESTONE_REF_MISSING

**Trigger**: A non-deferred checklist item in step 16 lacks a `milestone_ref` field binding it to a step 14 milestone.

**Resolution**: Add a `milestone_ref` field to the checklist item with the `milestone_id` from step 14 that owns the referenced task.

**Promotable**: W581 → E581.

### W583 API_UNCOVERED_BY_THREAT

**Trigger**: Fired by the Step 11 (red-team) validator when Step 05 interfaces are present and a public API ID is not named by the `target_ids` (entries with `type: api`) of any threat in the artifact. Each public API should be targeted by at least one threat. The check only runs when Step 05 is present (`api_ids` is not None).

**Exemption**: An API is skipped if it has at least one FR trace and every FR it traces to carries `priority: "wont-have"` in step 04 — such an API will never be built, so demanding threat coverage for it is moot. An API with zero FR traces (e.g. only a capability trace) is not exempted. This mirrors the equivalent `wont-have` exclusion in `matrix.py`/`traceability_closure.py` (DEVSPEC-122 follow-up).

**Resolution**: Add a threat in Step 11 whose `target_ids` includes the uncovered API (`{"type": "api", "id": "<api-id>"}`), or confirm the API is intentionally outside threat scope.

**Warning-only and non-promotable**: W583 has no E-counterpart and is excluded from `PROMOTABLE_PAIRS`, so neither `SPECDEV_WARNINGS_AS_ERRORS` nor `SPECDEV_PROMOTE_CODES` can escalate it to an error.

### E604 / W604 TRACE_MATRIX_STALE

**Trigger** (W604): Fired by the Step 14 validator when `extras/trace_matrix.json` is missing, or when its modification time is older than `14_roadmap.json` — an mtime-based freshness heuristic indicating the trace matrix may not reflect the current roadmap. Only W604 is emitted; E604 is registered as the nominal error form but is not currently produced by any code path.

**Resolution**: Regenerate `extras/trace_matrix.json` so it post-dates `14_roadmap.json`, or confirm the staleness is benign (e.g. a checkout reordered file modification times).

**Warning-only and non-promotable**: W604 is excluded from `PROMOTABLE_PAIRS` because matrix staleness is advisory rather than a hard correctness failure; `SPECDEV_WARNINGS_AS_ERRORS` and `SPECDEV_PROMOTE_CODES` therefore do not escalate it. E604 exists in the registry as the same-named error form but is not wired to promotion.

### E210 CROSS_ARTIFACT_DRIFT

**Trigger**: Fired by the canonical-integrity check when an artifact's `canonical_refs_used[]` array drifts from the canonical references actually present in the document body. Three subcodes: `canonical_refs_used_missing` (a canonical ID is referenced in the body but absent from `canonical_refs_used[]`), `canonical_refs_used_extra` (an ID is listed in `canonical_refs_used[]` but not used in the body), and `unresolved_canonical_semantic` (a semantic field carries a value with no resolved canonical ref).

**Resolution**: For the `canonical_refs_used_*` subcodes, run `./tools/run_specdev.sh canonical-autofix <file> --write` to sync `canonical_refs_used[]` with the body. For `unresolved_canonical_semantic`, supply the missing canonical reference (declare it in `canonical_proposals` and run `canon-accept`, or correct the semantic value).

**Promotable**: No — error-only; there is no `W210` counterpart.

---

## R9 Error Codes — Validator & CI Enforcement

### Canon/Schema Alignment (55x)

### E551 SCHEMA_ENUM_EXTRA

**Trigger**: A JSON Schema enum contains values that are not present in the paired canonical kind.

**Resolution**: Remove the extra values from the schema enum, or register them in the canonical kind via `canon/manifest.json`.

**Promotable**: No (error only).

### E552 MISSING_PAIRED_SCHEMA

**Trigger**: A schema file referenced in the canon/schema pairing configuration does not exist on disk.

**Resolution**: Verify the schema path in the pairing config and ensure the schema file exists at the expected location.

**Promotable**: No (error only).

### E553 MISSING_ENUM_PATH

**Trigger**: A JSON path referenced in the canon/schema pairing configuration does not exist in the target schema.

**Resolution**: Fix the JSON path in the pairing config to match the actual schema structure, or add the missing enum field to the schema.

**Promotable**: No (error only).

### W552 POTENTIAL_UNREGISTERED_PAIRING

**Trigger**: An unregistered schema enum has high overlap (>=80%) with a canonical kind, suggesting a pairing should be declared.

**Resolution**: Add an explicit pairing entry in the canon/schema alignment configuration, or document why the overlap is coincidental.

**Promotable**: No (warning only — advisory for canon maintenance).

### E554 CANON_ENUM_DRIFT

**Trigger**: A JSON Schema enum does not include all values defined in the canonical registry for that kind.

**Resolution**: Add the missing canonical values to the schema enum, or register the missing values in `canon/manifest.json`.

**Promotable**: No (error only).

### E555 SEMANTIC_COVERAGE_REGRESSION

**Trigger**: IDs present in the old version of an upstream artifact are absent from the new version, indicating dropped coverage.

**Resolution**: Restore the dropped IDs or update all downstream artifacts that reference them.

**Promotable**: No (error only).

### Cross-Step Validation (59x)

### E590 / W590 CROSS_STEP_ID_NOT_FOUND / CROSS_STEP_UPSTREAM_MISSING

**Trigger (E590)**: A spec artifact references an ID (FR, API, INV, NFR, capability, governance label) that does not exist in the upstream artifact.

**Trigger (W590)**: The upstream artifact file is missing entirely; cross-step validation is skipped for that upstream.

**Resolution (E590)**: Fix the broken ID reference to match an ID that exists in the upstream artifact.

**Resolution (W590)**: Generate the missing upstream artifact first, then re-validate.

**Promotable**: No. W590 (CROSS_STEP_UPSTREAM_MISSING — upstream file absent) and E590 (CROSS_STEP_ID_NOT_FOUND — ID absent from a present file) describe different defects with different resolutions. Promoting W590 to E590 would mislabel a missing-file condition as a broken ID reference, so W590 stays a warning; a fatal "upstream missing" would require a dedicated E-code.

### E591 / W591 EXTRACTION_INTENT_EMPTY

**Trigger**: A prompt has a `### Extraction Intent` section header but no parseable artifact entries beneath it.

**Resolution**: Add extraction intent entries listing each upstream artifact and what to extract from it.

**Promotable**: W591 → E591.

### E592 / W592 COVERAGE_THRESHOLD_BREACH / COVERAGE_THRESHOLD_WARN

**Trigger**: The traceability matrix FR coverage percentage falls below the configured threshold in `tools/step_order.json` → `coverage_thresholds.fr_coverage` (default: 80%).

**Resolution**: Increase FR coverage by adding API contracts, fixtures, or NFR bindings for uncovered FRs.

**Promotable**: W592 → E592. Mode controlled by `coverage_thresholds.mode` in step_order.json (`"warn"` or `"error"`).

### E593 / W593 VAGUE_LANGUAGE_FREE_TEXT

**Trigger**: A free-text field (description, statement, rationale, justification, notes, narrative, postconditions, preconditions, risks, spikes, migration_plan, definition) contains vague quantifiers (few, some, many, several, various, appropriate, adequate, sufficient, reasonable, significant, typical, generally, usually, fast, reliable, easy, hard, quick).

**Resolution**: Replace vague language with specific, measurable terms.

**Promotable**: W593 → E593. Note: W571 is emitted for vague language in `assumptions` fields specifically.

### E594 / W594 CONTENT_DERIVATION_LOW_OVERLAP

**Trigger**: A downstream artifact's free-text content shares fewer than the configured threshold (default: 5) of distinct tokens with its declared upstream artifacts.

**Resolution**: Ensure downstream content is derived from upstream artifacts. Review extraction intent and incorporate upstream terminology.

**Promotable**: W594 → E594. W594 is advisory by default — content derivation is heuristic with inherent false-positive risk.

### E595 / W595 CONTENT_STALENESS

**Trigger**: An upstream artifact has been modified with new content tokens, but none of those new tokens appear in downstream artifacts that consume it.

**Resolution**: Review the upstream changes and update downstream artifacts to reflect the new content.

**Promotable**: W595 → E595.

**Sub-reasons** (emitted by `specdev context freshness`):
- `CONTENT_STALENESS` — a seed's on-disk hash differs from its hash in `seed_requirements.json` (seed edited since last index). Re-index with `/specdev-step`.
- `SEED_UNTRACKED` — a seed listed in `seed_manifest.json` (with a path) is **absent** from `seed_requirements.json`, so edits to it trip no drift signal. `build_seed_index` hashes every manifest seed, so an untracked seed means the index is stale-by-omission — re-index with `/specdev-step` to bring it under drift detection.

### E596 DAG_DEAD_END_PRODUCER

**Trigger**: A non-terminal step has zero entries in `downstream_consumers` in step_order.json.

**Resolution**: Add the consuming steps to the step's `downstream_consumers` array in `tools/step_order.json`.

**Promotable**: No. E596 is error-only (emitted by dag-lint).

### W596 UNDECLARED_UPSTREAM_REF

**Trigger**: A prompt's extraction intent references an artifact from a step that is not in the computed allowed upstream steps (all steps preceding the current step in `tools/step_order.json`).

**Resolution**: Either adjust the step ordering in `steps` so the referenced step precedes the current step, or remove the reference from the prompt's extraction intent.

**Promotable**: No. W596 has different semantics from E596 (undeclared ref vs dead-end producer).

### E597 / W597 EXTRACTION_INTENT_UPSTREAM_GAP / EXTRACTION_INTENT_VAGUE

**Trigger (E597)**: A step has an allowed upstream step (computed at runtime from the `steps` order in step_order.json), but the prompt's extraction intent has no entry for that upstream artifact.

**Trigger (W597)**: An extraction intent entry has vague text (fewer than 10 words or contains "relevant", "as needed", "as appropriate", "various", "TBD", "TODO").

**Resolution (E597)**: Add an extraction intent entry for the missing upstream artifact.

**Resolution (W597)**: Expand the vague intent text with specific field names and extraction purposes.

**Promotable**: No. W597 (EXTRACTION_INTENT_VAGUE) and E597 (EXTRACTION_INTENT_UPSTREAM_GAP) have different semantics — vague text in a present entry vs. a missing entry for a required upstream artifact. W597 has no fatal counterpart and is not promoted; promoting it would mislabel a vague entry as an upstream gap.

### E598 EXTRACTION_INTENT_INVALID_REF

**Trigger**: An extraction intent entry references a step that does not exist in step_order.json's `steps` list.

**Resolution**: Fix the artifact reference to point to a valid step number.

**Promotable**: No (error only).

### E599 DAG_CONSUMER_INCONSISTENCY

**Trigger**: A step is listed in another step's `downstream_consumers`, but the consumer step does not appear after the producer in the `steps` ordering (i.e., the consumer precedes or equals the producer in the `steps` list).

**Resolution**: Ensure `downstream_consumers` entries are consistent with the positional ordering of steps in `tools/step_order.json`. Every declared consumer must appear after its producer in the `steps` list.

**Promotable**: No (error only).

### E585 DAG_CIRCULAR_DEPENDENCY

**Trigger**: The computed upstream dependency graph (derived from `steps` positional order) contains a cycle.

**Resolution**: Remove the circular dependency from the `steps` ordering in `tools/step_order.json`.

**Promotable**: No (error only).

### Vague Language & Quality (57x)

### E571 / W571 ASSUMPTION_VAGUE_QUANTIFIER

**Trigger**: An assumption in the `assumptions` array contains vague quantifiers.

**Resolution**: Replace vague language with specific, measurable terms.

**Promotable**: W571 → E571.

### E572 / W572 ASSUMPTION_COUNT_HIGH

**Trigger**: The number of assumptions exceeds the configured threshold.

**Resolution**: Review assumptions and remove or consolidate redundant entries.

**Promotable**: W572 → E572.

### E573 / W573 ASSUMPTION_UNBOUND_ID

**Trigger**: An assumption references an ID that cannot be resolved to any known artifact.

**Resolution**: Bind the assumption to a valid spec artifact ID or remove the reference.

**Promotable**: W573 → E573.

### W570 GRACEFUL_SKIP

**Trigger**: A validator cannot resolve an optional upstream input needed for a cross-reference check, so it skips that check rather than emitting a false unresolved-reference error. W570 is a general graceful-skip signal emitted from several validators (`hallucination_lint`, `traceability_closure`, `seed_lint`, `canonical/autofix`, and the step-16 validator) whenever a dependency they would cross-check is absent. The representative case is the NFR-ref check in `hallucination_lint`: when `spec/07_nfrs.json` is absent, `nfr_refs` in downstream artifacts (e.g. `13_impl.json`) cannot be validated, so the linter records `W570 GRACEFUL_SKIP nfr_refs 07_nfrs.json_absent` and proceeds without flagging any `nfr-*` reference as unresolved. Each emitter's message payload names the specific check and the missing input.

**Resolution**: None required — the skip is intentional and informational. To make the skipped check actually run, provide the missing upstream artifact named in the message (e.g. `spec/07_nfrs.json` via the step-07 NFR prompt) and re-run the validator.

**Promotable**: No. W570 has no `E570` counterpart — a graceful skip is the *absence* of a checkable condition, not a defect, so there is nothing to promote to an error.

### Substep & Milestone Drift (58x)

### E580 / W580 SUBSTEP_DRIFT

**Trigger**: A substep reference in a checklist does not match the expected step structure.

**Resolution**: Update the substep reference to match the current step definition.

**Promotable**: W580 → E580.

### E608 TOOLKIT_VERSION_MISMATCH

**Trigger**: Fires in any of three cases: (1) `spec/specdev_version` is absent or is present but malformed / missing the `toolkit_version` key; (2) the active toolkit version cannot be read from `tools/pyproject.toml` (file missing or unparseable); (3) the `toolkit_version` recorded in `spec/specdev_version` differs from the active toolkit version.

**Resolution**: Run `specdev update <spec_dir>` to sync your project to the current toolkit version. When there are no schema changes, `update` re-stamps `spec/specdev_version` instantly. When schema changes are required, it directs you through the `specdev align` flow (`apply --auto`, optionally `prompts`, then `validate`), finalizing with `specdev align validate <spec_dir>` — which runs full post-migration validation and stamps the new version with a migration-history entry.

**Promotable**: No (error only).

### W615 / E615 INVARIANT_UNEXERCISED_BY_THREAT

**Trigger**: A step-06 invariant has a non-empty `risk_category_ref` field (marking it as security-relevant) but no step-11 threat has a mitigation of type `inv` referencing its `inv_id`. This indicates that a security-relevant invariant is not exercised by any threat in the red-team assessment, creating a gap between invariant definitions and threat coverage.

Only fires when step 06 is present (absent step-06 file → check skipped silently). Invariants without a `risk_category_ref` are not flagged — only those explicitly marked as belonging to a risk category are expected to have a corresponding threat.

**Exemption**: An invariant is skipped if it has at least one FR trace and every FR it traces to carries `priority: "wont-have"` in step 04 — such an invariant guards behavior that will never be built, so demanding threat coverage for it is moot. An invariant with zero FR traces (e.g. only a capability trace) is not exempted. This mirrors the equivalent `wont-have` exclusion in `matrix.py`/`traceability_closure.py` (DEVSPEC-122 follow-up).

**Resolution**: Either add a threat in `11_redteam.json` with a mitigation of type `inv` referencing the flagged `inv_id`, or remove `risk_category_ref` from the invariant if it is not genuinely security-relevant.

**Promotable**: W615 → E615 (via `SPECDEV_WARNINGS_AS_ERRORS=1` or `SPECDEV_PROMOTE_CODES=W615`).

### W616 PAUSED_OR_CANCELLED_ITEM_MARKED_VERIFIED

**Trigger**: A Step 16 checklist item has `checklist_status == "deferred"` or `"wont_do"` while its `implementation.status` still says `"verified"`. This combination is a stale contradiction: work was verified, then the item was marked paused or permanently cancelled, without ever clearing or annotating the implementation record. (This check does not itself validate evidence quality — that's E301/W600/W601's job — it only compares these two status fields.)

**Resolution**: Reconcile which state is accurate. If the item is genuinely paused/cancelled, reset `implementation.status` to something other than `verified` (e.g. `deferred`) or note in `deferred_reason`/`wont_do_reason` why verified work is being shelved. If the work is actually done, set `checklist_status` back to `active`.

**Promotable**: No. This is a human-reconcile nudge, not a correctness failure with a single unambiguous fix direction — there is no `E616` counterpart.

### Trinity Evidence & Proof Closure (30x / 599–603)

### E301 MISSING_PROOF_CLOSURE

**Trigger**: Fired by `step_16.py` in any of three shapes: (1) a checklist item's `implementation.status` is `"verified"` but it has no `actions`; (2) a `"verified"` item has actions but none of them carry an `evidence` field (`EVIDENCE_CONTENT_INVALID`/no-evidence variant); or (3) an action's `evidence.content` is present but lacks a recognized success-marker keyword (e.g. `PASS`, `OK`, `passed`, `success`, `0 failures`) and the evidence has no `stdout`/`stderr` field to fall back on. A fourth, plan-level shape (`MISSING_PROOF_CLOSURE`) fires when `plan.status == "active"` and a `review_requirements.test_commands` entry is not found among `execution.execution_results` with `status` in (`passed`, `blocked`) — an unacknowledged test command on an active plan.

**Resolution**: Add `actions` documenting the work for verified items, ensure at least one action carries an `evidence` field, and make evidence content include a success marker (or structured `stdout`/`stderr`) so proof can be machine-verified. For the plan-level shape, run the declared test command and record its result in `execution.execution_results`, or mark it `blocked` with a reason.

**Promotable**: No (error only; no `W301` counterpart).

### E302 UNPROVEN_VERIFIED_REVIEW

**Trigger**: `review.verdict == "verified"` but the proof chain backing that verdict is incomplete, in any of four ways: (1) no `execution` section exists at all; (2) `execution.execution_results` is empty; (3) one or more `review_requirements.test_commands` entries have no matching `status == "passed"` entry in `execution_results`; or (4) `execution.critical_evidence.passed_test_commands` does not list every declared test command. Unlike E301's `acknowledged` set (which also accepts `blocked`), E302 requires an explicit `passed` status — a `blocked` acknowledgment satisfies E301 but not E302.

**Resolution**: Do not set `review.verdict` to `"verified"` until every `review_requirements.test_commands` entry has a corresponding `status: "passed"` entry in `execution.execution_results`, and until `execution.critical_evidence.passed_test_commands` lists each of them.

**Promotable**: No (error only; no `W302` counterpart).

### E303 CI_GATE_VIOLATION

**Trigger**: `review.verdict == "verified"` but `review.fixture_status.ci_status` is absent or is not exactly `"green"` (Task 7-04 / AUDIT-032 strengthened this to reject any non-`"green"` value, not just an explicit failure status).

**Resolution**: Set `review.fixture_status.ci_status` to `"green"` once CI has genuinely passed, or revert `review.verdict` until it has. (E303 is also the code used for governance commit-message mismatches — see `validation/governance.py` — a distinct emitter sharing the same code for a different artifact class.)

**Promotable**: No (error only; no `W303` counterpart).

### E304 ROADMAP_TASK_UNCOVERED

**Trigger**: Fired on 16a milestone plans (not on the Trinity Anchor) when a `14_roadmap.json` task — scoped to the milestones referenced by the plan's checklist `milestone_ref`s, or to all non-`done`/non-`deferred` milestones when no scoping signal exists — has no checklist item whose `spec_ref.id` matches the task's `task_id`. A task itself marked `deferred`/`wont_do` in the roadmap is exempt (already an authored acknowledgment). Also covers two structural sub-conditions under the same code: `ROADMAP_PARSE_ERROR` (14_roadmap.json fails to load) and `ROADMAP_STRUCTURE_ERROR` (unexpected roadmap shape).

**Resolution**: Add a checklist item with `spec_ref.id` matching the uncovered roadmap `task_id`, or mark the roadmap task `deferred`/`wont_do` with a `status_reason` if it is genuinely paused or cancelled. For the structural variants, fix the malformed or misshapen `14_roadmap.json`.

**Promotable**: No (error only; no `W304` counterpart).

### E305 PLANNED_UNEXECUTED

**Trigger**: `execution.final_status.ci_status == "green"` but a checklist item that is active (`checklist_status` not in the paused/cancelled set) is not present in `execution.critical_evidence.satisfied_checklist_ids`. A green final CI status implies every planned item should have been executed and recorded as satisfied.

**Resolution**: Add the item's `id` to `execution.critical_evidence.satisfied_checklist_ids` once its work is genuinely done, or set `checklist_status` to `deferred`/`wont_do` if it was intentionally skipped for this milestone pass.

**Promotable**: No (error only; no `W305` counterpart).

### E306 SEMANTIC_REVIEW_FR_MISMATCH

**Trigger**: `review.semantic_review.fr_coverage[].fr_id` references an `fr_id` that does not exist in the corresponding `04_fr_list.json` (resolved one directory up when the artifact lives under `impl_context/`). Skipped silently if `04_fr_list.json` is missing or unreadable.

**Resolution**: Correct the `fr_id` to reference an FR that actually exists in `04_fr_list.json`, or remove the stale `fr_coverage` entry.

**Promotable**: No (error only; no `W306` counterpart).

### E307 BEHAVIOR_VALIDATION_PAIRING

**Trigger**: For every behavioral `spec_ref` (types other than `doc`, `code`, `task` — i.e. `fr`, `api`, `inv`, `nfr`) referenced by at least one checklist item, the full set of checklist items sharing that `spec_ref.id` must include at least one item of `type: "behavior"` and one of `type: "validation"`. Deferred items still count toward pairing (a paused validation item still satisfies the pairing requirement); only its own proof-of-work fields are exempted elsewhere.

**Resolution**: Add the missing `behavior` and/or `validation` checklist item(s) for the flagged `spec_ref.id`.

**Promotable**: No (error only; no `W307` counterpart).

### E308 ANCHOR_SCOPE_DRIFT

**Trigger**: Fired by `step_16_anchor.py` (the Trinity Anchor's cross-milestone drift check) in two shapes: (1) `[ownership]` — the same FR/API `ref_id` appears in `fr_refs` of two non-done `milestone_index` entries, i.e. two active milestones both claim the same requirement; (2) `[scope]` — a milestone's `plan.summary.scope_in` item (case-insensitive) appears in the anchor's own `plan.summary.scope_out`, or a milestone's `scope_out` item appears in the anchor's `scope_in` — a bidirectional scope contradiction. The `[scope]` shape only runs when `spec_path` is provided and at least one milestone context file survives the W588/W589 filtering (see W611); the `[ownership]` shape runs purely in-memory off `milestone_index` regardless of `spec_path`.

**Resolution**: For `[ownership]` conflicts, ensure at most one non-done milestone claims a given FR/API in its `fr_refs` (mark the stale milestone `done` or remove the duplicate ref). For `[scope]` conflicts, reconcile the milestone's `scope_in`/`scope_out` against the anchor's `plan.summary.scope_in`/`scope_out` so the same category is not declared in-scope by one and out-of-scope by the other.

**Promotable**: No (error only; no `W308` counterpart).

### W599 EVIDENCE_TOO_SHORT

**Trigger**: A verified action's `evidence.content` is a string shorter than 50 characters — too short to plausibly contain a meaningful proof of work.

**Resolution**: Expand the evidence content to include the actual command output, or reference `stdout`/`stderr` fields instead of a short freeform string.

**Promotable**: No (warning only; no `E599` counterpart — `E599` is `DAG_CONSUMER_INCONSISTENCY`, an unrelated Step-04→Step-05 DAG check).

### W600 VERIFIED_ACTION_NO_EVIDENCE

**Trigger**: Two shapes share this code: (1) `VERIFIED_ACTION_NO_EVIDENCE` — a verified action has no `evidence` field at all; (2) `EVIDENCE_NO_CONTENT` — the action's `evidence` is a dict but has none of `content`, `stdout`, or `stderr`.

**Resolution**: Add an `evidence` field to the action (a `content` string or structured `stdout`/`stderr` fields) documenting what was actually verified.

**Promotable**: No (warning only; no `E600` counterpart).

### W601 EVIDENCE_NO_ARTIFACT_REF

**Trigger**: A verified action's evidence (`content`, `stdout`, and/or `stderr` combined) does not contain any recognizable spec artifact ID pattern (`fr-*`, `api-*`, `nfr-*`, `inv-*`) — the evidence cannot be tied back to the spec artifact it is meant to prove.

**Resolution**: Include the relevant artifact ID (e.g. the `fr-*` or `api-*` being verified) in the evidence content, stdout, or stderr text.

**Promotable**: No (warning only; no `E601` counterpart).

### W603 FILES_OUTSIDE_TASK_SCOPE

**Trigger**: A file listed in `execution.files_touched` (Task 7-09 / AUDIT-087) is not declared in any checklist item's `implementation.files_touched`, nor in `plan.summary.milestone_supporting_files` — the file was touched during execution but isn't tracked as belonging to any specific task's scope.

**Resolution**: Add the file to the owning checklist item's `implementation.files_touched`, or to `plan.summary.milestone_supporting_files` if it is milestone-wide supporting infrastructure rather than task-specific.

**Promotable**: No (warning only; no `E603` counterpart).

### Step-16 Anchor Validation (W587 / W611 / W612)

### W587 ANCHOR_DRIFT_CHECKS_STALE

**Trigger**: Fired by `step_16_anchor.py` (the Trinity Anchor validator) when `plan.milestone_index` has one or more entries but `plan.drift.checks` is empty — the anchor is tracking milestones without recording any drift-check evidence for a Trinity cycle. Fires purely in-memory off the anchor's own `plan` data, regardless of whether `spec_path` is provided or `impl_context/` exists on disk.

**Resolution**: Record at least one entry in `plan.drift.checks` per Trinity cycle documenting a drift observation (even a "no drift found" entry satisfies the check).

**Promotable**: No. W587 has no `E587` counterpart — stale drift-check bookkeeping is advisory, not a hard defect.

#### W588 ANCHOR_MILESTONE_UNREADABLE

**Trigger**: A milestone-plan JSON file the Trinity Anchor either declares (via `plan.milestone_index[].context_path` in `16_impl_context.json`) or that is discovered by globbing `impl_context/*.json` exists on disk but cannot be parsed as JSON or cannot be read. Two independent emitters share this code: `traceability_closure.py` (registry-driven discovery, feeding the coverage checks above) and `step_16_anchor.py` (directory-glob discovery, feeding E308/E309 cross-milestone drift detection) — the same underlying condition surfaces through whichever path finds it first. A declared `context_path` that is simply missing from disk (rather than present-but-unreadable) is a separate condition owned by W607 ANCHOR_CONTEXT_PATH_MISSING, not W588.

**Resolution**: Fix the malformed JSON in the named milestone-plan file, or restore its file-read permissions. Until fixed, the file is excluded from traceability coverage checks and from E308/E309 drift detection — see W611 below if this causes every milestone plan to be filtered out.

**Promotable**: No. W588 has no `E588` counterpart — an unreadable file is a data-integrity problem to fix directly, not a severity to escalate.

#### W611 ANCHOR_DRIFT_SUPPRESSED

**Trigger**: The Trinity Anchor's `impl_context/` directory contains one or more JSON files, but none of them declare `$schema='vc:16-impl-context'`, so every per-milestone plan was filtered out (typically because each tripped W588/W589). With zero surviving milestone contexts, the cross-milestone E308 (scope drift) and E309 (checklist drift) checks are completely suppressed — the anchor looks clean while contributing nothing to drift detection. Does not fire when `impl_context/` is genuinely empty (`files_seen == 0`), which is a valid state for a fresh anchor.

**Resolution**: Fix the W588/W589 warnings reported above the W611 line so the per-milestone plans are recognized (correct each plan's `$schema` to `vc:16-impl-context`). Once at least one plan survives filtering, E308/E309 drift detection is restored.

**Promotable**: No. W611 flags a suppressed-coverage condition, not a concrete drift defect; it has no `E611` counterpart.

#### W612 ANCHOR_PHANTOM_MILESTONE

**Trigger**: A `milestone_index` entry in the Trinity Anchor names a `milestone_id` that does not match any `milestone_id` in `14_roadmap.json`. Phantom milestones bypass ownership, prefix, and scope-drift detection, so the mismatch is surfaced as a warning. Only checked when `14_roadmap.json` is present and readable.

**Resolution**: Verify the `milestone_id` is not a typo. Either correct it to reference an existing roadmap milestone, or add the milestone to `14_roadmap.json` if it is legitimately new (replaying the step-14 roadmap step).

**Promotable**: No. W612 has no `E612` counterpart — a phantom-milestone reference is advisory because the roadmap may legitimately lag a freshly-scaffolded anchor.

## Canonical Integrity Extensions (1xx / 4xx)

### E130 CANONICAL_VERSION_MISMATCH

**Trigger**: A canonical reference (`{id, kind, version}`) names a `version` that does not match the registered entry's version, via `CanonicalRegistry.validate_ref` in `tools/specdev_tools/canonical/registry.py`.

**Resolution**: Update the reference's `version` field to match the canon entry's current version, or bump the canon entry if the reference is intentionally targeting a newer version.

**See also**: E110, E120, W130.

### E140 AMBIGUOUS_ALIAS

**Trigger**: A canonical reference supplies an `alias_used` value that, for the given `kind`, resolves to more than one candidate canonical ID (`CanonicalRegistry.validate_ref`).

**Resolution**: Replace the ambiguous alias with the specific canonical `id` it should resolve to, or deduplicate the conflicting alias registrations in the canon manifest.

### W110 DEPRECATED_CANONICAL_USED

**Trigger**: A canonical reference resolves to an entry whose `status` is `"deprecated"` (`CanonicalRegistry.validate_ref`).

**Resolution**: Migrate the reference to the entry's replacement canonical ID (see the entry's lifecycle `replaced_by`), or confirm continued use of the deprecated entry is intentional.

**Promotable**: No. W110 has no `E110`-shared promotion path — `E110` is `UNKNOWN_CANONICAL_ID`, a different condition (missing vs. deprecated-but-present).

### W120 ALIAS_DEPRECATED

**Trigger**: A canonical reference's `alias_used` resolves via an alias whose lifecycle marks it deprecated (but not yet sunset — see E125 for the sunset-expired case), via `CanonicalRegistry.validate_ref`.

**Resolution**: Replace the deprecated alias with the `replaced_by` alias or the canonical `id` directly.

**See also**: E125 ALIAS_SUNSET_EXPIRED (the fatal counterpart once the alias's `sunset_date` has passed).

### W130 CANONICAL_REF_VERSION_OMITTED

**Trigger**: A canonical reference omits the `version` field entirely (`CanonicalRegistry.validate_ref`).

**Resolution**: Add an explicit `version` field to the reference pinning it to the canon entry's current version.

**Promotable**: No dedicated pairing in `PROMOTABLE_PAIRS` under this name; `E130` (`CANONICAL_VERSION_MISMATCH`) is a structurally different condition (version present but wrong, not omitted).

### E420 INVALID_DEPRECATION_LIFECYCLE

**Trigger**: Fired by `lint_canon_dir()` in `tools/specdev_tools/canonical/lint.py` for two distinct shapes: (1) a canon manifest entry (`_validate_lifecycle`) whose `lifecycle` block is missing `introduced_at` (always required), or is missing `deprecated_since` when `status` is `"deprecated"`/`"sunset"`, or is missing `sunset_after` when `status` is `"sunset"`, or is missing `retired_at` when `status` is `"retired"`; (2) a manifest alias with `status: "deprecated"` that has no `deprecated_since` on the alias itself or on its nested `lifecycle` block.

**Resolution**: Add the missing lifecycle field(s) to the canon entry (or alias) matching its current `status` — `introduced_at` is always required, and `deprecated_since` / `sunset_after` / `retired_at` become required once the entry transitions to the corresponding `status` value. See the canon manifest schema for the expected `lifecycle` shape.

**Promotable**: No (error only; no `W420` counterpart).

### W421 CANON_ID_COLLISION_PROJECT_WINS

**Trigger**: During two-tier canon loading (`CanonicalRegistry.load`), a project-canon entry `id` collides with a core-canon entry `id`. The project entry silently overrides the core entry; W421 surfaces that override so it isn't invisible.

**Resolution**: Rename the project-canon entry's `id` if the collision is accidental, or leave it if the override is intentional (the warning is informational once acknowledged).

**Promotable**: No (warning only).

### E422 CORE_ENTRY_IN_PROJECT_CANON

**Trigger**: `specdev canon-accept` is invoked with a `--namespace` under `cn:core:` while writing to project canon (`canonical/accept.py`). Project canon may not declare entries in the `cn:core:` namespace — that namespace is toolkit-owned.

**Resolution**: Use a `cn:project:`-prefixed (or other non-core) namespace for `canon-accept`, or promote the entry through the toolkit's own core-canon process if it genuinely belongs in `cn:core:`.

**Promotable**: No (error only).

### E141 TASK_DEPENDENCY_CYCLE / Circular job-requires dependency

**Trigger**: Two independent emitters share this code: (1) `step_12.py` — a CI job's `requires[]` graph in `12_ci_gates.json` contains a cycle; (2) `step_14.py` — a step 14 roadmap task's dependency graph (task-to-task, via `dfs`) contains a cycle involving a named milestone.

**Resolution**: Break the cycle by removing or reordering the offending `requires`/task-dependency edge so the graph is acyclic.

**Promotable**: No (error only).

### E142 TECH_STACK_MISMATCH

**Trigger**: Fired by `step_14.py` when a `tech_stack` entry used in `14_roadmap.json` is not present in the corresponding Step 09 (`09_impl_plan.json`) `tech_stack`.

**Resolution**: Add the technology to Step 09's `tech_stack`, or remove it from the roadmap's `tech_stack` if it is not actually part of the approved stack.

**See also**: W602 / W605 (the equivalent Step 02 ↔ Step 14 tech-stack consistency checks).

## Prompt / Schema / Dependency-Order Drift (31x / 54x)

### E310 PROMPT_SCHEMA_DRIFT

**Trigger**: Fired by `prompt_schema_sync.py` when a `prompt_NN_*.md` file's documented output contract drifts from its paired JSON Schema — missing/extra required fields, a missing schema-reference section, a missing or malformed schema URI/file reference, a missing property, or a property-level mismatch (type/description drift) between the prompt's documented fields and the schema.

**Resolution**: Update the prompt's output-contract section to match the paired schema (or vice versa, if the schema is stale) — align required fields, the `$schema` URI reference, and per-property descriptions.

**Promotable**: No (error only).

### E311 MISSING_ENUM_PROVENANCE

**Trigger**: Fired by `step_05.py` when an API entry in `05_interface_contracts.json` declares enum values (in request/response fields) but has no `enum_provenance` field recording where those enum values originated, for reproducibility tracking.

**Resolution**: Add an `enum_provenance` field to the API entry documenting the source of the enum values (e.g. a canonical registry entry or an upstream spec artifact).

**Promotable**: No (error only).

### E320 STEP13_EXTENSION_ERROR

**Trigger**: Fired by `step_13.py` for a malformed extension entry in `13_impl.json`: either a `required_schema_sections[]` item that is not a valid identifier (must start alphanumeric; only alphanumeric/underscore/hyphen allowed), or a missing/empty `justification` field on the extension.

**Resolution**: Fix the malformed `required_schema_sections[]` entry to a valid identifier, or supply a non-empty `justification` for the extension.

**Promotable**: No (error only).

### E540 SELF_OR_FORWARD_DEPENDENCY

**Trigger**: Fired by `dependency_order_lint.py` when a prompt file references (via a `spec/NN_*` path mention) either itself (self-dependency) or a step that comes later in the waterfall (forward dependency) — both violate the forward-only ordering.

**Resolution**: Remove the self-reference, or move the referenced content to a step that precedes the current one in `tools/step_order.json`'s `steps` ordering.

**Promotable**: No (error only).

### E543 STEP_METADATA_INCONSISTENT

**Trigger**: Fired by `dependency_order_lint.py` (M4 check) in three shapes, all comparing `tools/step_order.json`'s `step_metadata[].required_spec_inputs` against the `downstream_consumers`-derived inverse graph: (1) a `step_metadata` key references a step not declared in the top-level `steps` array (phantom key); (2) a step's `required_spec_inputs` is missing an entry implied by another step's `downstream_consumers`; (3) a step's `required_spec_inputs` has an extra entry not implied by any `downstream_consumers`.

**Resolution**: Remove the phantom `step_metadata` key, or reconcile `required_spec_inputs` with the corresponding `downstream_consumers` entries so the two stay consistent.

**Promotable**: No (error only).

## Spec Quality Extras (51x / 52x / 57x)

### E510 PLACEHOLDER_VALUE_FOUND

**Trigger**: Fired by `spec_quality_lint.py`'s independent placeholder scan when any string value in a spec artifact matches the placeholder pattern (e.g. bracket-wrapped tokens like `[TBD]`, `[FIXME]`).

**Resolution**: Replace the placeholder text with real, project-specific content.

**See also**: E511 (removed — was redundant with this independent scan).

### E512 ASSUMPTION_HAS_PLACEHOLDER

**Trigger**: Fired by `spec_quality_lint.py` when a value inside an `assumptions[]` entry matches the placeholder pattern.

**Resolution**: Replace the placeholder text in the assumption with a concrete, project-specific statement.

**See also**: E571/W571 ASSUMPTION_VAGUE_QUANTIFIER, W573 ASSUMPTION_UNBOUND_ID (the other assumption-content checks).

### E521 VALIDATOR_RUNTIME

**Trigger**: A validator's own execution fails unexpectedly and is caught rather than propagating an unhandled exception — emitted from several sites (`canonical/lint.py` schema-validation runtime errors, `validation/validate.py` deep-validation critical errors, `glossary_drift_lint.py` runtime errors). Also used as the fallback code in `ensure_spec_errors()` when a raw string error cannot be parsed into a structured `SpecError`.

**Resolution**: Inspect the embedded exception type/message in the error text to diagnose the underlying failure (malformed input, missing file, bad schema); fix the root cause and re-run.

**Promotable**: No (error only).

### W574 TECH_STACK_COHERENCE_MISMATCH

**Trigger**: Fired by `spec_quality_lint.py` when `09_impl_plan.json`'s `tech_stack` and `14_roadmap.json`'s `tech_stack` are both present but not identical.

**Resolution**: Reconcile the two `tech_stack` objects so Step 09 and Step 14 declare the same technology choices.

**Promotable**: No (warning only).

## Step 02 ↔ Step 14 Tech Stack Consistency (60x)

### W602 / W605 TECH_STACK_02_MISMATCH / TECH_STACK_02_MISSING

**Trigger (W602)**: `step_14.py` (AUDIT-034) fires when a `tech_stack` entry used in `14_roadmap.json` is not found in Step 02's (`02_system_sketch.json`) `tech_stack`.

**Trigger (W605)**: Fires when a technology declared in Step 02's `tech_stack` is absent from `14_roadmap.json`'s `tech_stack` — the roadmap dropped a technology the system sketch declared.

**Resolution**: Add the missing technology to whichever artifact is missing it (Step 02 system sketch or Step 14 roadmap) so the two `tech_stack` sets agree.

**Promotable**: No (warning only). This is a separate check from E142 (which compares Step 09 vs. Step 14 tech stacks).

## Forward Replay & ID Stability (55x / 59x)

### E550 / W550 FORWARD_REPLAY_MISSING / SEMANTIC_COVERAGE_SKIP

**Trigger (E550)**: Fired by `forward_replay_check.py` in three shapes: (1) `SPECDEV_REPLAY_DIFF_ERROR_MODE` is set to an invalid value (must be `error` or `ignore`); (2) the diff against the base ref could not be computed at all; (3) a changed step's downstream consumers (per `tools/step_order.json`) were not also replayed.

**Trigger (W550)**: Fired when semantic coverage checking could not read the base-ref version of an artifact (e.g. the file didn't exist at the base ref), so the coverage-regression check for that artifact is skipped rather than failing closed.

**Resolution (E550)**: Fix the `SPECDEV_REPLAY_DIFF_ERROR_MODE` value, ensure the base ref is reachable and diffable, or replay the missing downstream artifacts.

**Resolution (W550)**: Confirm the base ref genuinely predates the artifact (expected for newly-added files); no action needed if so.

**Promotable**: `PROMOTABLE_PAIRS` registers `W550 → E550`, though the two are emitted by structurally different conditions (skip vs. hard failure) — promotion escalates the skip to a hard failure under `SPECDEV_WARNINGS_AS_ERRORS`/`SPECDEV_PROMOTE_CODES=W550`.

### W598 ID_STABILITY_REMOVAL

**Trigger**: Fired by `forward_replay_check.py` alongside an E555 `SEMANTIC_COVERAGE_REGRESSION` finding — for each individual ID that was present in the base-ref version of an artifact and is now absent, W598 fires once per removed ID (in addition to the aggregate E555), to surface likely ID renames early.

**Resolution**: If the ID was renamed, update all downstream references to the new ID. If it was genuinely removed, confirm no downstream artifact still depends on it.

**Promotable**: No (warning only; co-fires with E555 rather than promoting to it).

## Glossary Parity (60x)

### E606 GLOSSARY_PROPOSAL_DRIFT

**Trigger**: Fired by `glossary_drift_lint.py` when a `03_glossary.json` `terms[]` entry's `definition` differs from the `definition` on its matching `canonical_proposals` entry (matched by `term-{temp_id}`, `kind == "term"` proposals only — acronym proposals are excluded since acronyms have no `terms[]` counterpart).

**Resolution**: Reconcile the term's `definition` in `terms[]` with the corresponding `canonical_proposals` entry so both describe the same definition.

### E607 GLOSSARY_CANON_DRIFT

**Trigger**: Fired by `glossary_drift_lint.py` when a `03_glossary.json` term's `definition` differs from the `definition` of the already-accepted `cn:project:` canon entry it's bound to via `term_ref`.

**Resolution**: Update the glossary term's `definition` to match the canon entry (the source of truth once accepted), or re-run `canon-accept` if the glossary's definition is the intended update.

### W606 GLOSSARY_CANON_ORPHAN

**Trigger**: Fired by `glossary_drift_lint.py` when a `cn:project:` canon entry whose lifecycle records `accepted_from: 03_glossary.json` is neither referenced in `canonical_refs_used[]` nor still present as a `canonical_proposals` entry — it was accepted from the glossary but the glossary no longer names it anywhere.

**Resolution**: Either re-add a reference to the canon ID in the glossary (if it's still a valid term), or leave the canon entry in place as an intentionally-retained but currently-unused registration.

**Promotable**: No (warning only).

## Step-16 Anchor Validation Extras (E309 / W585–W610)

### E309 ANCHOR_CHECKLIST_DRIFT

**Trigger**: Fired by `step_16_anchor.py` in two shapes: (1) `[prefix]` — two `milestone_index` entries declare the same `checklist_id_prefix`, so two milestones would allocate checklist IDs from the same namespace; (2) `[mapping]` — the same checklist item `id` appears in two different milestone plan files but maps to a different `spec_ref.id` in each, i.e. the same ID is bound to two different requirements.

**Resolution**: For `[prefix]`, give each milestone a unique `checklist_id_prefix`. For `[mapping]`, rename the colliding checklist `id` in one of the milestone plans so each ID maps to exactly one `spec_ref.id`.

**Promotable**: No (error only; no `W309` counterpart).

### W585 ANCHOR_DRIFT_SKIP

**Trigger**: Fired by `step_16_anchor.py` when `spec_path` is not provided to `validate_step_16_anchor`, so all filesystem-dependent drift checks (W607, the `[scope]` shape of E308, the `[mapping]` shape of E309, W610) are skipped — only the in-memory `milestone_index` checks still run.

**Resolution**: Pass `spec_path` when invoking the anchor validator so the filesystem-dependent checks can run.

**Promotable**: No (warning only).

### W586 ANCHOR_VALIDATOR_WRONG_ARTIFACT

**Trigger**: `validate_step_16_anchor` is called on an artifact that is neither field-marked (`artifact_role == "anchor"`) nor path-marked (`spec/16_impl_context.json` outside `impl_context/`) — indicating a routing bug in `validate.py`'s dispatch, or a mis-authored artifact that should not have reached the anchor validator.

**Resolution**: Fix the routing logic in `validate.py`, or correct the artifact's `artifact_role`/file location so it is unambiguously an anchor or a milestone plan.

**Promotable**: No (warning only).

### W589 ANCHOR_MILESTONE_MISSCHEMAED

**Trigger**: A JSON file under `impl_context/` parses successfully but declares a `$schema` other than `vc:16-impl-context` — it isn't recognized as a milestone plan, so it's excluded from every cross-milestone drift check (E308/E309).

**Resolution**: Correct the file's `$schema` to `vc:16-impl-context`, or move the file out of `impl_context/` if it isn't meant to be a milestone plan.

**See also**: W611 ANCHOR_DRIFT_SUPPRESSED (fires when W589/W588 filter out every milestone plan, suppressing drift detection entirely).

### W607 ANCHOR_CONTEXT_PATH_MISSING

**Trigger**: A `milestone_index[]` entry declares a `context_path` pointing to a milestone plan file, but no file exists at the resolved path — drift detection silently skips that milestone until the plan is authored.

**Resolution**: Author the missing milestone plan file at the declared `context_path`, or correct the `context_path` to point to the existing plan file.

**See also**: W588 ANCHOR_MILESTONE_UNREADABLE (the file exists but can't be parsed — a distinct condition from W607's file-absent case).

### W608 ANCHOR_LEGACY_SCHEMA

**Trigger**: The artifact at the anchor path (`spec/16_impl_context.json`) declares `$schema='vc:16-impl-context'` — the pre-Trinity-split, per-milestone schema — instead of the anchor's own `vc:16-anchor` schema. Schema validation against `vc:16-impl-context` still passes, but the file is contributing nothing to cross-milestone drift detection.

**Resolution**: Migrate: move per-milestone checklist content to `spec/impl_context/<milestone>_plan.json`, rewrite the anchor file against `vc:16-anchor` (with `plan.summary`, `plan.ambiguities`, `plan.drift`, `plan.milestone_index`), and set `artifact_role='anchor'`. See `prompts/prompt_16_impl_context.md`.

**Promotable**: No (warning only).

### W609 ANCHOR_MISFILED

**Trigger**: A file with `artifact_role='anchor'` lives inside `spec/impl_context/` instead of at `spec/16_impl_context.json`. The routing logic demotes the dispatch, so every drift check resolves `impl_context_dir` to a nonexistent nested path and silently no-ops.

**Resolution**: Move the file to `spec/16_impl_context.json` (one level up from `impl_context/`) so cross-milestone drift checks can resolve the `impl_context/` sibling directory correctly.

### W610 ANCHOR_PREFIX_VIOLATION

**Trigger**: A checklist item `id` in a milestone plan does not start with the `checklist_id_prefix` declared for that milestone in the anchor's `milestone_index`.

**Resolution**: Rename the checklist item `id` to start with the declared prefix (`{prefix}_`), or correct the `checklist_id_prefix` in `milestone_index` if the item's ID is actually correct.

**See also**: E309 `[prefix]` shape (a prefix collision between two milestones, vs. W610's single-milestone prefix mismatch).

## Upstream Backlog (61x)

### W613 UPSTREAM_BACKLOG_UNCLASSIFIED

**Trigger**: Fired by `specdev upstream-backlog` (`analysis/upstream_backlog.py`) when an ambiguity record's `impact[]` matches none of the three classifier rules used to bucket ambiguities by upstream step, falling through to the `unclassified` bucket. Applies equally to `plan.ambiguities[]` (16a) and `execution.emergent_ambiguities[]` (16b/16c) records.

**Resolution**: Informational only — review the flagged ambiguity's `impact[]` text and, if appropriate, extend the classifier rules in `upstream_backlog.py` to recognize the pattern; no per-artifact fix is required.

**Promotable**: No. Deliberately excluded from `PROMOTABLE_PAIRS` — informational only, never promoted.

### W617 UPSTREAM_BACKLOG_STATUS_FILTERED

**Trigger**: Fired by `specdev upstream-backlog` whenever its `--status` filter (default `open`) excludes at least one record that otherwise satisfies the `--severity` threshold. DEVSPEC-123: a bare invocation against a milestone plan where most ambiguities had already been resolved looked like the tool was scanning nothing, when in fact `execution.emergent_ambiguities[]` was being scanned correctly — the resolved records were just silently outside the default view.

**Resolution**: Informational only — re-run with `--status all` (or `--status resolved`) to see the hidden records. The JSON payload also carries this count as `summary.hidden_by_status_count`, which is always present (0 when nothing is hidden) for programmatic consumers.

**Promotable**: No. Deliberately excluded from `PROMOTABLE_PAIRS` — informational only, never promoted.

## Registry Checks (62x)

### E620 REGISTRY_MISSING_STEP

**Trigger**: Historical/registered code for "a step in `tools/step_order.json` is not registered in `entry_key_registry.json`" (R001). As of the registry-generator hardening (W3), this check moved to the toolkit's own unit test suite (`tests/unit/toolkit_invariants/test_step_registry_coverage.py`, `T-step-registry-coverage`) since the generator now enforces step coverage as an internal contract, making a host-runtime check redundant. E620 is retained in `ERROR_CODES` for historical reference and backward compatibility with external tooling that parses it, but `specdev registry-check` no longer emits it.

**Resolution**: Not applicable at host-runtime (the check no longer fires there). If a step is missing from the registry, run `specdev registry-generate` and confirm `pytest tests/unit/toolkit_invariants/test_step_registry_coverage.py` passes.

**Promotable**: No (error only).

### E621 REGISTRY_PHANTOM_BASENAME

**Trigger**: R002 — `specdev registry-check`'s `_check_phantom_basenames` finds a basename registered in `tools/entry_key_registry.json` that does not appear in `tools/extraction_paths.json`.

**Resolution**: Remove or rename the orphaned entry in `entry_key_registry.json`, or add the corresponding entry to `extraction_paths.json`. Run `specdev registry-generate` to regenerate both files consistently.

**Promotable**: No (error only).

### E622 REGISTRY_DRIFT

**Trigger**: R003 — `specdev registry-check` finds that a registered `(array_path, id_field)` pair no longer matches the live spec file's structure: is not an array, or its entries lack the registered `id_field`. A missing array path is drift only at the top level; a missing *nested* array path (e.g. a task's `acceptance_criteria`) is not flagged here, since nested arrays may be legitimately optional per schema — a present-but-wrong-shape nested array still fires E622.

**Resolution**: Run `specdev registry-generate` to regenerate `entry_key_registry.json`/`extraction_paths.json` from the current schemas, or fix the schema/spec structure if the drift indicates an unintended shape change.

**Promotable**: No (error only).

### W614 UNREGISTERED_ARRAY

**Trigger**: R004 — a host spec file has an array of dict items bearing an `*_id` (or `id`) field that is not declared in the registry as a known `(basename, array_path)` pair — a novel array the generator doesn't yet know about.

**Resolution**: If the array should be tracked (e.g. for cross-step ID validation), add it to the registry source and run `specdev registry-generate`. If it's intentionally untracked free-form data, no action is required — R004 is advisory (WARNING, not ERROR) precisely because the generator may not yet cover every new array shape.

**Promotable**: No (warning only).

## Exception Classes

### SubmoduleDetectionError

**Module**: `specdev_tools.core.errors`

**Raised when**: The toolkit cannot detect the git root in a submodule deployment.

**Common triggers**:
- Running from a detached HEAD state in the submodule
- `--repo-root` pointing to the wrong directory

**Resolution**: Pass `--git-root` pointing to the host repo's git root, and `--spec-root` pointing to the spec directory.

### SchemaRegistryError

**Module**: `specdev_tools.core.errors`

**Raised when**: A schema URI cannot be resolved from `tools/schema_registry.json`.

**Common triggers**:
- Missing entry in `tools/schema_registry.json`
- `--repo-root` not pointing to the toolkit directory
- Schema file referenced in the registry doesn't exist on disk

**Resolution**: Check `tools/schema_registry.json` for the expected URI mapping and verify `--repo-root` points to the devspec_toolkit directory.
