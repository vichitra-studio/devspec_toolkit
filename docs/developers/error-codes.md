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

**Trigger**: A validator could not resolve a required input and fails closed rather than crashing. Five message families share this code:
- `UNRESOLVED_INPUT` — a required directory, file, or spec input was missing or unreadable (e.g. `missing_spec_dir`, `missing_canon_dir`, `invalid_json`), or a CLI input precondition was not met.
- `schema_not_found` — the schema registry could not load the schema for a `$schema` URI. As of 1.1.0, `specdev validate` / `spec-check` fail closed on **all** registry I/O errors (previously only `FileNotFoundError` was caught; `PermissionError` and other `OSError`s now route here instead of escaping uncaught). The step-11 validator likewise emits a structured `E520` for a `threats[]` entry that is not an object.
- `docs_impact` content validation — the step-16 validator (`step_16.py`) emits `E520` when a milestone plan has code-change actions (non-doc `file_create`/`file_edit` targets) but `plan.docs_impact` is missing, its `status` is not `"required"`, `docs_touched` is empty, or a `docs_touched` entry does not match a `doc_paths` pattern from `seed_manifest.json`.
- A write that plans from the graph (`specdev json patch|insert|delete --id`, `json insert --step`, `step create`, `node rename`, `node rename --label`, `attest --prune`, `attest --yes`, and `step ready`; a `--dry-run` of the writers is refused as well, an `attest` preview is not) refused because a spec file cannot be read, so the links it holds are not in the graph: `E520 json patch --id refused: 04_fr_list.json cannot be read, so the links it holds are not in the graph and the lock cannot be checked against them; repair the file, then run the command again` (the command is named at the start, with its flags for `attest`: `E520 attest --yes --dry-run refused: ...`, `E520 attest --prune --dry-run refused: ...`; exit 1, nothing written; it follows the line `specdev json: could not read 04_fr_list.json; the answer may be incomplete` on stderr). `step ready` prints `E520 step ready refused: 04_fr_list.json cannot be read, ...` in the same form. `stale`, `coverage`, `node` and an `attest` preview (no `--yes`, bare or with `--dry-run`, exit 0) print the same kind of warning and then an answer that may be incomplete. `specdev lock merge` reports E520 for a version file it cannot read (`E520 cannot read the base version nope.json of p: [Errno 2] No such file or directory: 'nope.json'`).
- `spec-check --step` and `spec-check --paths` refuse with one finding and exit 1 (on stderr in text mode, as JSON on stdout with `--json`) when the spec folder does not exist (`E520 UNRESOLVED_INPUT missing_spec_dir <dir>`), when the toolkit's `tools/error_ownership.json` is missing or unreadable (`E520 UNRESOLVED_INPUT ownership_table <path>: unreadable or not a JSON object`), or when its `tools/step_order.json` is unreadable (`E520 <path> step order is unreadable: No such file or directory`; for a file that is not JSON the reason is the parser's, such as `Expecting property name enclosed in double quotes: line 1 column 2 (char 1)`). A schema E520 that the gate reports is owned by the step of the file (`step:04`) and carries `file` and `jq_path` in `--json`: `04_fr_list.json` and `.functional_requirements[0].scope`, or `.` for an error of the whole file.
- A write that puts a hash into the trace lock (`specdev json patch|insert|delete --id`, `json insert --step`, `step create`, each with or without `--dry-run`, `attest <node-id> --yes` and `attest --step NN --yes`, each with or without `--dry-run`) refused because a seed document that the spec names is not found under the host root: the hash would be the hash of a missing file. The root is `--git-root`, or the folder that holds the spec folder. Nothing is written; exit 1. Example, on a copy whose spec folder is `h/sub/spec` and whose seed documents are at `h/docs/seed`, run from `h` with no `--git-root`: `E520 seed document docs/seed/seed_accounts.md (seed-accounts) was not found under <h>/sub; if the repository root is another folder pass --git-root`; several seeds read `seed documents A (id), B (id) were not found under ...`. With `--git-root .` the same commands ran. `node rename`, `node rename --label`, `node status` and `attest --prune` were run in that layout and were not refused. The reads that report on the lock (`stale`, `coverage`, `step ready`, an `attest` preview, `attest --prune`) print one line on stderr and then their answer: `note: seed documents not found under <h>/sub: docs/seed/seed_accounts.md (seed-accounts); their links count as suspect; if the repository root is another folder pass --git-root`; `spec-check`, `validate-all` and `forward-replay-check` print the same line on stderr and report the links as E763.
- `changelog_parser.py` structural validation — `validate_changelog()` in `tools/specdev_tools/core/changelog_parser.py` emits `E520` for unloadable/malformed YAML (missing file, parse error, empty or non-mapping content), plus four raw-dict structural checks run before the changelog is parsed into a dataclass: **Check 1** — `breaking` is present but not a `bool`; **Check 2** — a top-level key is not in the format's `required_fields`/`optional_fields`; **Check 3** — `version` is not valid semver or does not match the filename's version, except that a `version: "unreleased"` value in `unreleased.yaml` is exempted via an explicit unreleased-sentinel bypass; **Check 4** — a declared `source_of_truth`/`render_target` path is not a non-empty string, does not exist on disk, exists but points to a non-file path (e.g. a directory), or exists but is empty. It also emits `E520` for invalid `change.type` / `change.migration.action` values found after parsing.

**Resolution**: Supply the missing input (pass the correct `--spec-root` / `--git-root`, create the expected `spec_dir`, or fix the malformed JSON). For `schema_not_found`, confirm the `$schema` URI is registered in `tools/schema_registry.json` and that the target schema file exists and is readable. For `docs_impact` failures, set `plan.docs_impact.status` to `"required"` and list the touched doc paths in `docs_touched`, matching a pattern in `seed_manifest.json`'s `doc_paths`. For `changelog_parser.py` failures, fix the offending YAML field per the check that fired (correct `breaking`'s type, remove/rename the unknown key, fix `version` to match the filename or use the `unreleased` sentinel only in `unreleased.yaml`, or fix the `source_of_truth`/`render_target` path).

### E530 INVENTED_ENUM_OR_ID

**Trigger**: A value in a spec artifact does not match any allowed enum member, canonical ID, or registered entry.  The most common variant is a leading verb in a `command` field that is not in the toolkit or project allowlist.

**Resolution**: Run `specdev guide E530-INVENTED_ENUM_OR_ID` for the full playbook.  Quick summary: extend `spec/canon/command_prefixes.json` with the allowed verb, or register the verb as a canonical command entry and attach a sibling `command_ref`.

**See also**: E110.

### E125 ALIAS_SUNSET_EXPIRED

**Trigger**: A canonical alias with a past `sunset_date` is used in a spec artifact.

**Resolution**: Replace the alias with the canonical term specified in the `replaced_by` field of the alias lifecycle block.

### E211 PARTIAL_DRIFT

**Trigger**: The same term maps to different canonical IDs across different spec artifacts (N-1 updated, 1 stale).

**Resolution**: Update the stale artifact(s) to use the current canonical ID. The error message includes per-artifact paths showing which file uses which canonical ID.

### E511 PLACEHOLDER_SCAN_MISMATCH

**Removed prior to 1.0.0**. E511 (`PLACEHOLDER_SCAN_MISMATCH`) was redundant with E510 independent placeholder scan. The associated sub-field has been removed.

### E535 CONTRADICTORY_OUT_OF_SCOPE_FR

**Trigger**: A functional requirement appears in both `apis.out_of_scope[]` in step 05 (declaring it has no HTTP API surface) and in an API's `trace[]` in the same step 05 file (declaring it is covered by an API endpoint). The two claims are mutually exclusive. The check reads the 1.1.1 `trace` field and runs only when the file it reads carries it (see E564).

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

2. **Namespace-aware slot-kind suppression** (as of 1.1.0, round 4) — an object whose schema sets `additionalProperties: false` and declares only *purpose-specific* ref slots (e.g. `fr_refs`, `capability_refs`, `metric_ref`) that cannot accept a `term`/`acronym` canonical ID is also suppressed. The check extracts the kind labels from each `*_ref`/`*_refs` slot name (e.g. `fr_refs` → kind `fr`; `capability_refs` → kind `capability`) and suppresses E541 for a given term when the term's canonical kind (e.g. `term`) is absent from the slot-kind set. Example: an object that declares only `fr_refs` and `capability_refs` has slot kinds `{"fr", "capability"}`; a `term`-kind canonical ID has no namespace overlap → E541 is suppressed. Objects that DO have a matching slot (e.g. `03_glossary.json` `terms[]` items with `term_ref`) are NOT suppressed by this mechanism — they fall through to mechanism 3 (runtime binding check).

3. **Term-specific runtime suppression** (the `bound_refs` path) — when a sibling `*_ref`/`*_refs` key is present at the same object level, it suppresses E541 only for the specific term(s) it binds: suppression applies when one of the ref's *values* is one of the mentioned term's canonical IDs. An unrelated reference (binding a different ID) does **not** suppress, so a genuinely unbound term in the same object still fires. (Prior to this release the check was object-level — any ref present suppressed every free-text field — which over-suppressed legitimate unbound mentions.)

4. **Key-name skip fallback** (the `_E541_SKIP_KEYS` / `_E541_SKIP_KEYS_BY_FILE` path) — certain keys are always exempt regardless of schema, because their subtrees are vocabulary definitions or free-form runner output rather than spec content that should bind refs. The complete set of exempted keys, sourced from `_E541_SKIP_KEYS` and `_E541_SKIP_KEYS_BY_FILE` in `hallucination_lint.py`:

   **Global skips (`_E541_SKIP_KEYS`):**

   *Category A — canonical vocabulary subtrees:*
   - **`canonical_proposals`**, **`canonical_refs_used`**, **`canonical_conflicts`** — canonical metadata; not spec content that should bind refs
   - **`tech_stack`**, **`user_segments`**, **`seeds`** — structured enumerations whose values are not canonical term-binding sites

   *Category B — Step 16 implementation/narrative subtrees (belt-and-suspenders for `impl_context/` artifacts with variable filenames where `$schema` lookup is unreliable):*
   - **`actions`**, **`coding_examples`** — Step 16a/16b implementation subtrees
   - **`emergent_ambiguities`**, **`docs_impact`** — Step 16 narrative subtrees; **`ambiguities`** — the open-ambiguity list, a top-level array in steps 00 to 15 and `plan.ambiguities` in the step 16 anchor and plans
   - **`review_requirements`** — Step 16 operational verification instructions (test commands, NFR measurement methods); these are not canonical term-binding sites. Note: structural suppression cannot reliably cover these because `test_commands[]` uses `oneOf` and `nfr_measurement_methods` uses `patternProperties`, both of which can cause `slot_kinds` to resolve as `None` under certain schema-navigation paths.

   *Category C — free-form runner output:*
   - **`execution`** — `execution.final_status.test_results` items have `additionalProperties` unset (intentionally free-form test-runner output). The structural rule requires `additionalProperties: false` and will NOT suppress items with unset `additionalProperties`, so a key-name skip is necessary. Example subtree that triggers this: a `16_impl_context.json` artifact's `execution.final_status.test_results[]` items describing test-runner output such as `{"name": "test_send_newsletter", "status": "passed", "duration": 1.2}`.

   **File-scoped skips (`_E541_SKIP_KEYS_BY_FILE`):**
   - **`edge_cases` in `11_redteam.json`** — unbindable narrative subtree; the red-team schema sets `additionalProperties: false` with no `*_ref` field on `edge_cases` items. Scoped to that file to avoid silently exempting a future `edge_cases` key in another artifact.
   - **`definition` in `03_glossary.json`** — glossary definitions are vocabulary prose; requiring `term_ref` bindings for every cross-term mention in the definition text is semantically incorrect. This skip applies only when the file's basename is `03_glossary.json`; a `definition` field in any other file is still checked normally. Note: the glossary `terms[]` object DOES have `term_ref`/`acronym_ref` slots (used to pin the entry's own canonical ID), so the namespace-aware structural rule does NOT suppress it — this explicit skip is required.

   For artifacts with no resolvable `$schema` (where structural suppression and namespace-aware slot-kind suppression are inactive), two mechanisms remain active: the key-name skip (mechanism 4) and the term-specific runtime `bound_ref_ids` suppression (mechanism 3). Mechanism 3 — the `bound_ref_ids` collection in `_check_free_text_terms` of `hallucination_lint.py` — is unconditional and has no guard on `schema_node`; the check `if cids & bound_ref_ids: continue` fires regardless of whether `$schema` resolved. A sibling `*_ref` binding the mentioned term therefore suppresses E541 for that specific term even in a schema-free artifact.

**Note on the closure codes** (E535, E536, E560, W561, W562, W563, W564, W565, W566, W567, W568, W569, W575, W576): their Trigger and Resolution texts below describe the 1.1.1 shape. Each reads fields that 1.2.0 removed (`trace`, `targets`, `out_of_scope`, `fr_refs`, `spec_ref`, `deliverables`, `critical_evidence`, `pr_rules`) and runs only when the files it reads carry those fields, or hold no entries to read. A 1.2.0-shaped spec gets none of them until a later 1.2.0 change replaces them with graph coverage; the one live part is the empty-milestone half of W567 (a milestone with no tasks), which fires only on a file the schema already rejects, since `tasks` must not be empty. A new-shape anchor has no `plan.milestone_index[].context_path`, so the closure checks load no milestone plans from it. Where a text below says to add a removed field to a 1.1.1 file, a 1.2.0 spec marks a node that needs no API or fixture with `scope: out` and `scope_reason`.

### E560 TRACEABILITY_GAP

**Trigger**: Fired by the traceability-closure check (`check_traceability_closure()`) for two Charter → Capabilities gaps: (1) `charter_goal_without_capability` — a Step 00 charter `goals[].goal_id` is not referenced by any Step 01 capability's `trace[]` (a trace entry of the charter-goal type); or (2) `charter_success_metric_without_capability` — a Step 00 charter `success_metrics[].metric_id` is not referenced by any capability's `success_metric_refs[]`. Only fires when both `00_charter.json` and `01_capabilities.json` are present and carry the 1.1.1 fields this check reads (`goal_id`, `success_metric_refs`, `trace`). A spec whose steps 00 to 05 have the new shape gets no E560, whatever shape its later steps have, until graph coverage later in this release. Note: E560 previously covered a `capability_without_fr` check (a capability with no tracing FR); that check was superseded by W568/E568 UNCOVERED_CAPABILITY, and E560 now covers only the two charter-level gaps described above.

**Resolution**: For a pre-1.2.0 spec, for `charter_goal_without_capability`, add a capability in `01_capabilities.json` with a `trace[]` entry referencing the uncovered `goal_id`. For `charter_success_metric_without_capability`, add the `metric_id` to the appropriate capability's `success_metric_refs[]`.

**Promotable**: No (error only).

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

**Trigger**: A functional requirement defined in step 04 has no API trace reference — no API in step 05 has a trace link with type "fr" pointing to this FR. The check reads only the 1.1.1 `trace` field of step 05 APIs and runs only when the files it reads carry that field. A spec whose steps 00 to 05 have the new shape gets no E564 / W564 / E535 and no FR-to-API coverage warning from the matrix, whatever shape its later steps have, until graph coverage later in this release.

**Resolution**: In a pre-1.2.0 spec, add a trace link of type "fr" in the appropriate API contract in `05_interface_contracts.json`. If the FR genuinely has no HTTP API surface (infra, ops, external constraint), add it to `out_of_scope[]` in `05_interface_contracts.json` with a non-empty rationale — that suppresses W564, W561, and W566 for that FR. See also E535 for the contradiction check.

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

**Trigger**: A capability defined in step 01 has no functional requirement tracing to it. This replaces the former E560 `capability_without_fr` check. The check reads 1.1.1 fields and runs only when the files it reads carry them; a spec whose steps 00 to 05 have the new shape gets no W568 / E568 until graph coverage later in this release.

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

### W553 SEED_STEP_UNKNOWN

**Trigger**: A key in `seed_manifest.json` `step_requirements` is not a recognized pipeline step in `step_order.json` (e.g. a typo such as `"9"` instead of `"09"`, a non-existent step `"02b"`, or an out-of-range value `"17"`). Real pipeline steps including `"16"`, `"16a"`, `"16b"`, and `"16c"` do not trigger this warning.

**Resolution**: Fix the typo in the `step_requirements` key to match a real step ID, or remove the phantom entry.

**Note**: W553 was previously named `SEED_STEP_OUT_OF_RANGE` (fired for any step outside 00–02a). It was repurposed in DEVSPEC-43 to fire only on genuinely unknown steps, enabling seed routing to all pipeline steps.

### W554 HARDCODED_SEED_REFERENCE

**Trigger**: A prompt file contains a literal `seed_*.md` filename (matched by the pattern `seed_\w+\.md`). `spec/common/seed_manifest.json` is the authoritative source for seed names; hardcoding seed filenames in prompts duplicates that authority and drifts silently when seed names change.

**Resolution**: Remove the literal seed filename from the prompt. Reference seed documents through the manifest's `step_requirements` routing, not by name in prompt prose. Run `specdev hardcoded-seed-check` to identify all occurrences.

**Warning-only and non-promotable**: W554 has no E-counterpart (E554 is `CANON_ENUM_DRIFT`) and is excluded from `PROMOTABLE_PAIRS`, so neither `SPECDEV_WARNINGS_AS_ERRORS` nor `SPECDEV_PROMOTE_CODES` can escalate it to an error.

### W555 STEP00_SEED_OUT_OF_SCOPE_THIN

**Trigger**: Seeds routed to step `"00"` in `seed_manifest.json` `step_requirements` supply fewer than 3 substantive out-of-scope items in aggregate. The threshold is a seed-quality heuristic stated in `seed_lint.py`, not a mirror of the Step 00 charter schema (which has no per-class floor on `scope_items`): thin seeds leave authors with too little to derive out-of-scope items from, so they hallucinate content at authoring time. "Substantive" means a markdown bullet item under an out-of-scope / non-goals heading that is NOT a bracket-only placeholder (e.g. `[Non-goal 1]`), NOT a template scaffold label (e.g. `- **Expectation**:`), and NOT content inside a fenced code block (delimited by ` ``` ` or `~~~`). Fence tracking matches the opening delimiter, so a `~~~` line inside a ` ``` `-opened fence (or vice-versa) is treated as fenced content, not a closing delimiter. Items are counted across ALL seeds routed to step 00 combined; W555 fires at most once per `lint_seeds()` invocation.

**Resolution**: Add at least 3 real, project-specific out-of-scope items to the seed(s) routed to step 00. The heading must match one of the accepted variants (case-insensitive): `Out-of-Scope`, `Non-Goals`, or `Non-Goal`. A good out-of-scope item describes a concrete capability that is deliberately excluded from scope — for example "Multi-tenant support is deferred to Phase 2" or "Offline mode is not in scope for MVP".

**Warning-only and non-promotable**: W555 is intentionally excluded from `PROMOTABLE_PAIRS`, so neither `SPECDEV_WARNINGS_AS_ERRORS` nor `SPECDEV_PROMOTE_CODES` can escalate W555 to an error.

### W583 API_UNCOVERED_BY_THREAT

**Trigger**: Fired by the Step 11 (red-team) validator when Step 05 interfaces are present and an API id of step 05 is not named in the `threatens` of any threat in the artifact (`threatens` accepts api, component, connection and third-party ids). Each API should be threatened by at least one threat. The check only runs when Step 05 is present.

**Exemption**: An API is skipped if its `derives_from` is non-empty and every id in it is a parked FR of step 04 (`scope` `later` or `out`; a 1.1.1 FR also parks with `priority: "wont-have"`) — such an API will never be built, so demanding threat coverage for it is moot. An API whose `derives_from` is empty or holds an id that is not a parked FR (e.g. a capability id) is not exempted. This mirrors the equivalent parked-FR exclusion in `matrix.py`/`traceability_closure.py` (DEVSPEC-122 follow-up).

**Resolution**: Add a threat in Step 11 whose `threatens` includes the uncovered API id, or confirm the API is intentionally outside threat scope.

**Warning-only and non-promotable**: W583 has no E-counterpart and is excluded from `PROMOTABLE_PAIRS`, so neither `SPECDEV_WARNINGS_AS_ERRORS` nor `SPECDEV_PROMOTE_CODES` can escalate it to an error.

### E604 / W604 TRACE_MATRIX_STALE

**Trigger** (W604): Fired by the Step 14 validator when `extras/trace_matrix.json` is missing, or when its modification time is older than `14_roadmap.json` — an mtime-based freshness heuristic indicating the trace matrix may not reflect the current roadmap. The check runs only when `14_roadmap.json` carries a 1.1.1 `fr_refs` or `source_milestones` field (the matrix is built from them), so it is skipped on a 1.2.0-shaped roadmap. Only W604 is emitted; E604 is registered as the nominal error form but is not currently produced by any code path.

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

### Cross-Step Validation (59x)

### E590 / W590 CROSS_STEP_ID_NOT_FOUND / CROSS_STEP_UPSTREAM_MISSING

**Trigger (E590)**: A spec artifact references an ID (FR, API, INV, NFR, capability) that does not exist in the upstream artifact.

**Trigger (E590, step 02)**: "Missing capability coverage" (`validators/step_02.py` `check_capability_coverage`): a capability in the Step 01 artifact is not named in any component's `derives_from`. A parked capability (`scope` `later` or `out`) is exempt. The check is skipped when the Step 01 artifact is not found.

**Note (links)**: No step validator of steps 06 to 16 checks that the id in a link field (a field the schema marks `x-link`) exists; the `graph` check of `spec-check` does (E700). A plan's file-level `milestone` is not a link field: E304 reports one that names no roadmap milestone.

**Trigger (W590)**: The upstream artifact file is missing entirely; cross-step validation is skipped for that upstream.

**Resolution (E590)**: Fix the broken ID reference to match an ID that exists in the upstream artifact.

**Resolution (W590)**: Generate the missing upstream artifact first, then re-validate.

**Promotable**: No. W590 (CROSS_STEP_UPSTREAM_MISSING — upstream file absent) and E590 (CROSS_STEP_ID_NOT_FOUND — ID absent from a present file) describe different defects with different resolutions. Promoting W590 to E590 would mislabel a missing-file condition as a broken ID reference, so W590 stays a warning; a fatal "upstream missing" would require a dedicated E-code.

### E591 / W591 EXTRACTION_INTENT_EMPTY

**Trigger**: A prompt has a `### Extraction Intent` section header but no parseable artifact entries beneath it.

**Resolution**: Add extraction intent entries listing each upstream artifact and what to extract from it.

**Promotable**: W591 → E591.

### E592 / W592 COVERAGE_THRESHOLD_BREACH / COVERAGE_THRESHOLD_WARN

**Trigger**: The traceability matrix FR coverage percentage falls below the configured threshold in `tools/step_order.json` → `coverage_thresholds.fr_coverage` (default: 80%). The percentage is FR-to-API coverage, read from the 1.1.1 `trace` field of step 05 APIs. When a step 05 file is loaded and its APIs carry no `trace` (a spec whose steps 00 to 05 have the new shape), that coverage is not computed and neither W592 nor E592 is emitted, in either mode, until graph coverage later in this release.

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

**Trigger**: Reported by `specdev context freshness` and by the seed indexer for the two seed sub-reasons below. File-level forward replay, which reported W595 when an upstream artifact gained content tokens that no downstream artifact shows, is retired: `specdev forward-replay-check` and `validate-all` no longer report W595 for that reason, and `SPECDEV_STALENESS_THRESHOLD` has no effect. The suspect links of the trace lock ([E763](#e763-suspect_link)) replace that check.

**Resolution**: For the seed sub-reasons, re-index the seeds (below). For a change in a spec artifact, run `specdev stale` and read the pending replay.

**Promotable**: W595 → E595.

**Sub-reasons** (emitted by `specdev context freshness`):
- `CONTENT_STALENESS` — a seed's on-disk hash differs from its hash in `seed_requirements.json` (seed edited since last index). Re-index with `/specdev-step`.
- `SEED_UNTRACKED` — a seed listed in `seed_manifest.json` (with a path) is **absent** from `seed_requirements.json`, so edits to it trip no drift signal. `build_seed_index` hashes every manifest seed, so an untracked seed means the index is stale-by-omission — re-index with `/specdev-step` to bring it under drift detection.

### E596 DAG_DEAD_END_PRODUCER

**Trigger**: A non-terminal step has zero entries in `downstream_consumers` in step_order.json. Steps 03 and 16c are exempt: 16c ends the pipeline, and the glossary (03) is read by label, which no stored link carries, so the generated order lists no consumer for it.

**Resolution**: `downstream_consumers` is generated: run `specdev registry-generate --repo-root ./devspec_toolkit` and do not edit `tools/step_order.json` by hand. A consumer appears when a step's schema carries an `x-link` to this step's kinds; add that link to the consuming schema, or add a `[producer, consumer]` pair to `declared_edges` (a hand key of `tools/step_order.json`) for a context read no stored link carries.

**Promotable**: No. E596 is error-only (emitted by dag-lint).

### W596 UNDECLARED_UPSTREAM_REF

**Trigger**: A prompt's extraction intent references an artifact from a step that is not in the computed allowed upstream steps (all steps preceding the current step in `tools/step_order.json`).

**Resolution**: Either adjust the step ordering in `steps` so the referenced step precedes the current step, or remove the reference from the prompt's extraction intent.

**Promotable**: No. W596 has different semantics from E596 (undeclared ref vs dead-end producer).

### E597 / W597 EXTRACTION_INTENT_UPSTREAM_GAP / EXTRACTION_INTENT_VAGUE

**Trigger (E597)**: A step reads an upstream step (its `step_metadata.required_spec_inputs` in step_order.json; every preceding step of the `steps` order when a step has no such list), but the prompt's extraction intent has no entry for that upstream artifact.

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

**Resolution**: Ensure `downstream_consumers` entries are consistent with the positional ordering of steps in `tools/step_order.json`. Every declared consumer must appear after its producer in the `steps` list. `downstream_consumers` is generated by `registry-generate`; the `steps` order and `declared_edges` are the hand-carried keys.

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

**Trigger**: A step-06 invariant (`rules[]`) has a non-empty `risk_category_ref` field (marking it as security-relevant) but no step-11 threat names its `inv_id` in `mitigated_by`. This indicates that a security-relevant invariant is not exercised by any threat in the red-team assessment, creating a gap between invariant definitions and threat coverage.

Only fires when step 06 is present (absent step-06 file → check skipped silently). Invariants without a `risk_category_ref` are not flagged — only those explicitly marked as belonging to a risk category are expected to have a corresponding threat.

**Exemption**: An invariant is skipped if its `constrains` is non-empty and every id in it is a parked FR of step 04 (`scope` `later` or `out`; a 1.1.1 FR also parks with `priority: "wont-have"`) — such an invariant guards behavior that will never be built, so demanding threat coverage for it is moot. An invariant whose `constrains` is empty, or holds an id that is not a parked FR (an API, component or connection id), is not exempted. This mirrors the equivalent parked-FR exclusion in `matrix.py`/`traceability_closure.py` (DEVSPEC-122 follow-up).

**Resolution**: Either add the flagged `inv_id` to the `mitigated_by` of a threat in `11_redteam.json`, or remove `risk_category_ref` from the invariant if it is not genuinely security-relevant.

**Promotable**: W615 → E615 (via `SPECDEV_WARNINGS_AS_ERRORS=1` or `SPECDEV_PROMOTE_CODES=W615`).

### Trinity Evidence & Proof Closure (30x / 599–603)

**Note on the plan-item checks**: E301 shapes (1) to (3), W599, W600, W601 and E305 read `implementation.status` of a plan item, and E307 reads an object `spec_ref`. A 1.2.0 plan item stores neither field, so these checks report nothing on it until a later 1.2.0 change replaces them. The text below describes the 1.1.1 reading. E301's plan-level shape, E302, E303, E304 and E306 run on 1.2.0 plans.

### E301 MISSING_PROOF_CLOSURE

**Trigger**: Fired by `step_16.py` in any of three shapes, each only for a plan item that carries `implementation.status`: (1) a checklist item's `implementation.status` is `"verified"` but it has no `actions`; (2) a `"verified"` item has actions but none of them carry an `evidence` field (`EVIDENCE_CONTENT_INVALID`/no-evidence variant); or (3) an action's `evidence.content` is present but lacks a recognized success-marker keyword (e.g. `PASS`, `OK`, `passed`, `success`, `0 failures`) and the evidence has no `stdout`/`stderr` field to fall back on. A fourth, plan-level shape (`MISSING_PROOF_CLOSURE`) runs on every plan: it fires when the plan is active (`plan.status` is `active` or absent, as in every 1.2.0 plan), `execution.execution_results` is non-empty, and a `review_requirements.test_commands` entry is not found among `execution.execution_results` with `status` in (`passed`, `blocked`) — an unacknowledged test command on an active plan.

**Resolution**: Add `actions` documenting the work for verified items, ensure at least one action carries an `evidence` field, and make evidence content include a success marker (or structured `stdout`/`stderr`) so proof can be machine-verified. For the plan-level shape, run the declared test command and record its result in `execution.execution_results`, or mark it `blocked` with a reason.

**Promotable**: No (error only; no `W301` counterpart).

### E302 UNPROVEN_VERIFIED_REVIEW

**Trigger**: `review.verdict == "verified"` but the proof chain backing that verdict is incomplete, in any of three ways: (1) no `execution` section exists at all; (2) `execution.execution_results` is empty; or (3) one or more `review_requirements.test_commands` entries have no matching `status == "passed"` entry in `execution_results`. Unlike E301's `acknowledged` set (which also accepts `blocked`), E302 requires an explicit `passed` status — a `blocked` acknowledgment satisfies E301 but not E302.

**Resolution**: Do not set `review.verdict` to `"verified"` until every `review_requirements.test_commands` entry has a corresponding `status: "passed"` entry in `execution.execution_results`.

**Promotable**: No (error only; no `W302` counterpart).

### E303 CI_GATE_VIOLATION

**Trigger**: `review.verdict == "verified"` but `review.fixture_status.ci_status` is absent or is not exactly `"green"` (Task 7-04 / AUDIT-032 strengthened this to reject any non-`"green"` value, not just an explicit failure status).

**Resolution**: Set `review.fixture_status.ci_status` to `"green"` once CI has genuinely passed, or revert `review.verdict` until it has. (E303 is also the code used for governance commit-message mismatches — see `validation/governance.py` — a distinct emitter sharing the same code for a different artifact class.)

**Promotable**: No (error only; no `W303` counterpart).

### E304 ROADMAP_TASK_UNCOVERED

**Trigger**: Fired on 16a milestone plans (not on the Trinity Anchor) in three shapes, named in the message. `ROADMAP_MILESTONE_UNKNOWN`: the plan's file-level `milestone` is not a `milestone_id` of `14_roadmap.json`. `ROADMAP_TASK_UNCOVERED`: a task of that milestone has no plan item whose `realises` names one of the task's `acceptance_criteria[].criterion_id`; a task with no acceptance criterion is reported too, because a plan item can only realise a criterion; a task whose `disposition.value` is `deferred` or `wont_do` is exempt (already an authored acknowledgment). `ROADMAP_PARSE_ERROR`: `14_roadmap.json` is present and is not a UTF-8 JSON object. A plan with no `milestone` key checks nothing here (the schema reports the missing key); a missing `14_roadmap.json` is skipped.

**Resolution**: Add a plan item whose `realises` names one of the uncovered task's criteria (for a task that has none, add an acceptance criterion to the task first), or give the roadmap task a `disposition` (`deferred` or `wont_do`, with a `reason`) if it is genuinely paused or cancelled. Correct the plan's `milestone` for `ROADMAP_MILESTONE_UNKNOWN`. For `ROADMAP_PARSE_ERROR`, fix `14_roadmap.json`.

**Promotable**: No (error only; no `W304` counterpart).

### E305 PLANNED_UNEXECUTED

**Trigger**: Only for a plan whose items carry `implementation.status`. `execution.final_status.ci_status == "green"` but a checklist item that is active (`checklist_status` not in the paused/cancelled set) is not present in `execution.critical_evidence.satisfied_checklist_ids`. A green final CI status implies every planned item should have been executed and recorded as satisfied. Both fields are 1.1.1 fields; a 1.2.0 plan has neither, so E305 reports nothing on it.

**Resolution**: Add the item's `id` to `execution.critical_evidence.satisfied_checklist_ids` once its work is genuinely done, or set `checklist_status` to `deferred`/`wont_do` if it was intentionally skipped for this milestone pass.

**Promotable**: No (error only; no `W305` counterpart).

### E306 SEMANTIC_REVIEW_FR_MISMATCH

**Trigger**: `review.semantic_review.fr_coverage[].fr_id` references an `fr_id` that does not exist in the corresponding `04_fr_list.json` (resolved one directory up when the artifact lives under `impl_context/`). Skipped silently if `04_fr_list.json` is missing or unreadable.

**Resolution**: Correct the `fr_id` to reference an FR that actually exists in `04_fr_list.json`, or remove the stale `fr_coverage` entry.

**Promotable**: No (error only; no `W306` counterpart).

### E307 BEHAVIOR_VALIDATION_PAIRING

**Trigger**: Only for plan items that carry an object `spec_ref` (a 1.1.1 field; a 1.2.0 plan item has none, so E307 reports nothing on it). For every behavioral `spec_ref` (types other than `doc`, `code`, `task` — i.e. `fr`, `api`, `inv`, `nfr`) referenced by at least one checklist item, the full set of checklist items sharing that `spec_ref.id` must include at least one item of `type: "behavior"` and one of `type: "validation"`. Deferred items still count toward pairing (a paused validation item still satisfies the pairing requirement); only its own proof-of-work fields are exempted elsewhere.

**Resolution**: Add the missing `behavior` and/or `validation` checklist item(s) for the flagged `spec_ref.id`.

**Promotable**: No (error only; no `W307` counterpart).

### E308 ANCHOR_SCOPE_DRIFT

**Trigger**: Fired by `step_16_anchor.py` (the Trinity Anchor's cross-milestone drift check) in two shapes: (1) `[ownership]` — the same FR/API `ref_id` appears in `fr_refs` of two non-done `milestone_index` entries, i.e. two active milestones both claim the same requirement; a 1.2.0 anchor row has no `fr_refs`, so this shape finds nothing on it; (2) `[scope]` — a milestone plan's `plan.summary.scope_in` item (case-insensitive) appears in the anchor's own `plan.summary.scope_out`, or a plan's `scope_out` item appears in the anchor's `scope_in` — a bidirectional scope contradiction. The `[scope]` shape only runs when `spec_path` is provided and at least one plan file takes part in drift detection (see W611); the `[ownership]` shape runs purely in-memory off `milestone_index` regardless of `spec_path`.

**Resolution**: For `[ownership]` conflicts (1.1.1 anchors only), ensure at most one non-done milestone claims a given FR/API in its `fr_refs` (mark the stale milestone `done` or remove the duplicate ref). For `[scope]` conflicts, reconcile the milestone's `scope_in`/`scope_out` against the anchor's `plan.summary.scope_in`/`scope_out` so the same category is not declared in-scope by one and out-of-scope by the other.

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

### Step-16 Anchor Validation (W587 / W588 / W611)

### W587 ANCHOR_DRIFT_CHECKS_STALE

**Trigger**: Fired by `step_16_anchor.py` (the Trinity Anchor validator) when `plan.milestone_index` has one or more entries but `plan.drift.checks` is empty — the anchor is tracking milestones without recording any drift-check evidence for a Trinity cycle. Fires purely in-memory off the anchor's own `plan` data, regardless of whether `spec_path` is provided or `impl_context/` exists on disk.

**Resolution**: Record at least one entry in `plan.drift.checks` per Trinity cycle documenting a drift observation (even a "no drift found" entry satisfies the check).

**Promotable**: No. W587 has no `E587` counterpart — stale drift-check bookkeeping is advisory, not a hard defect.

#### W588 ANCHOR_MILESTONE_UNREADABLE

**Trigger**: A milestone-plan JSON file in `impl_context/*.json` exists on disk but cannot be read or parsed as JSON. Two independent emitters share this code: `traceability_closure.py` (which finds plans through the `plan.milestone_index[].context_path` of a 1.1.1 anchor, feeding the coverage checks above) and `step_16_anchor.py` (directory-glob discovery, feeding E308/E309 cross-milestone drift detection) — the same underlying condition surfaces through whichever path finds it first. A declared `context_path` that is missing from disk reports nothing.

**Resolution**: Fix the malformed JSON in the named milestone-plan file, or restore its file-read permissions. Until fixed, the file is excluded from traceability coverage checks and from E308/E309 drift detection — see W611 below if this causes every milestone plan to be filtered out.

**Promotable**: No. W588 has no `E588` counterpart — an unreadable file is a data-integrity problem to fix directly, not a severity to escalate.

#### W611 ANCHOR_DRIFT_SUPPRESSED

**Trigger**: The Trinity Anchor's `impl_context/` directory contains one or more JSON files, and either none of them takes part in drift detection or some plan file names a milestone that no anchor row is about. A file takes part when it declares `$schema='vc:16-impl-context'` and its file-level `milestone` names a milestone that some anchor row is `about`. With zero participating plans, the cross-milestone E308 (scope drift) and E309 (checklist drift) checks are completely suppressed — the anchor looks clean while contributing nothing to drift detection. Does not fire when `impl_context/` is genuinely empty (no JSON files), which is a valid state for a fresh anchor.

**Resolution**: Fix the W588/W589/W608 warnings reported above the W611 line, or add the anchor row a plan file's `milestone` names, so the per-milestone plans take part. Once at least one plan takes part, E308/E309 drift detection is restored.

**Promotable**: No. W611 flags a suppressed-coverage condition, not a concrete drift defect; it has no `E611` counterpart.

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

### E141 TASK_DEPENDENCY_CYCLE (removed)

Removed in 1.2.0, see E703: a job or task `depends_on` cycle is now reported by the link check (`spec-check`, check `graph`) as E703.

## Prompt / Schema / Dependency-Order Drift (31x / 54x)

### E310 PROMPT_SCHEMA_DRIFT

**Trigger**: Fired by `prompt_schema_sync.py` when a `prompt_NN_*.md` file's documented output contract drifts from its paired JSON Schema — missing/extra required fields, a missing schema-reference section, a missing or malformed schema URI/file reference, a missing property, or a property-level mismatch (type/description drift) between the prompt's documented fields and the schema.

**Resolution**: Update the prompt's output-contract section to match the paired schema (or vice versa, if the schema is stale) — align required fields, the `$schema` URI reference, and per-property descriptions.

**Promotable**: No (error only).

### E311 MISSING_ENUM_PROVENANCE

**Trigger**: Fired by `step_05.py` when an API entry in `05_interface_contracts.json` declares at least one `parameters[].enum` but has no `enum_provenance` field recording where the value set originated, for reproducibility tracking. Listing `errors` or `error_codes` does not fire it.

**Resolution**: Add an `enum_provenance` field to the API entry documenting the source of the enum values (e.g. an external standard such as ISO 4217 or IANA language tags, a canonical registry entry, or an upstream spec artifact). An internal enum is asked for provenance too, because structure cannot tell internal from external value sets.

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

**Resolution**: `step_metadata` and `downstream_consumers` are generated: correct the hand-kept keys of `tools/step_order.json` (`steps`, `declared_edges`) if the fault comes from them, then run `specdev registry-generate --repo-root <toolkit>`. Do not edit the two generated keys by hand.

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

**Trigger**: Fired by `step_16_anchor.py` in two shapes: (1) `[prefix]` — two `milestone_index` entries declare the same `checklist_id_prefix`, so two milestones would allocate checklist IDs from the same namespace; (2) `[mapping]` — the same checklist item `id` appears in two different milestone plan files but maps to a different `spec_ref.id` in each, i.e. the same ID is bound to two different requirements. The `[mapping]` shape reads an object `spec_ref`, which a 1.2.0 plan item no longer has, so it finds nothing on a 1.2.0 plan.

**Resolution**: For `[prefix]`, give each milestone a unique `checklist_id_prefix`. For `[mapping]`, rename the colliding checklist `id` in one of the milestone plans so each ID maps to exactly one `spec_ref.id`.

**Promotable**: No (error only; no `W309` counterpart).

### W585 ANCHOR_DRIFT_SKIP

**Trigger**: Fired by `step_16_anchor.py` when `spec_path` is not provided to `validate_step_16_anchor`, so all filesystem-dependent drift checks (W588, W589, W608 for plan files, W611, the `[scope]` shape of E308, the `[mapping]` shape of E309, W610) are skipped — only the in-memory `milestone_index` checks still run.

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

### W608 ANCHOR_LEGACY_SCHEMA

**Trigger**: Two cases. (1) The artifact at the anchor path (`spec/16_impl_context.json`) declares `$schema='vc:16-impl-context'` — the pre-Trinity-split, per-milestone schema — instead of the anchor's own `vc:16-anchor` schema. Schema validation against `vc:16-impl-context` still passes, but the file is contributing nothing to cross-milestone drift detection. (2) A plan file in `impl_context/` declares `vc:16-impl-context` but has no file-level `milestone` key (the pre-1.2.0 plan shape); the file is skipped by the drift checks until it names its milestone.

**Resolution**: For case (1), migrate: move per-milestone checklist content to `spec/impl_context/<milestone>_plan.json`, rewrite the anchor file against `vc:16-anchor` (with `plan.summary`, `plan.ambiguities`, `plan.drift`, `plan.milestone_index`), and set `artifact_role='anchor'`. For case (2), add the roadmap milestone id as the plan file's file-level `milestone`. See `prompts/prompt_16_impl_context.md`.

**Promotable**: No (warning only).

### W609 ANCHOR_MISFILED

**Trigger**: A file with `artifact_role='anchor'` lives inside `spec/impl_context/` instead of at `spec/16_impl_context.json`. The routing logic demotes the dispatch, so every drift check resolves `impl_context_dir` to a nonexistent nested path and silently no-ops.

**Resolution**: Move the file to `spec/16_impl_context.json` (one level up from `impl_context/`) so cross-milestone drift checks can resolve the `impl_context/` sibling directory correctly.

### W610 ANCHOR_PREFIX_VIOLATION

**Trigger**: A checklist item `id` in a milestone plan does not start with `<checklist_id_prefix>_` (the prefix and an underscore), the `checklist_id_prefix` being the one declared for that milestone in the anchor's `milestone_index` (the row whose `about` equals the plan's file-level `milestone`; a plan that no row is about is skipped, see W611).

**Resolution**: Rename the checklist item `id` to start with the declared prefix (`{prefix}_`), or correct the `checklist_id_prefix` in `milestone_index` if the item's ID is actually correct.

**See also**: E309 `[prefix]` shape (a prefix collision between two milestones, vs. W610's single-milestone prefix mismatch).

## Upstream Backlog (61x)

### W613 UPSTREAM_BACKLOG_UNCLASSIFIED

**Trigger**: Fired by `specdev upstream-backlog` (`analysis/upstream_backlog.py`) for each item it lists under the group `unplaced`: an item none of whose `about` ids names a node of the spec (the message names `<artifact>:<item id>`), or an item of the 1.1.1 shape (no `about`) whose `impact[]` names no step. An item with at least one `about` id that names a node is placed under the step of that node and never fires W613. Applies to the open items of the step files, the anchor and the milestone plans (`plan.ambiguities[]`, `execution.emergent_ambiguities[]`).

**Resolution**: Informational only. For an item with `about`, correct the id (it may be misspelled, or the node was renamed or deleted). For an item of the 1.1.1 shape, name a spec file in its `impact[]` as `spec/NN_name.json` (optionally `spec/NN_name.json:<id>`; `06_invariants.json` without `spec/` places nothing and the item stays under `unplaced`) or give it `about`. No per-artifact fix is required.

**Promotable**: No. Deliberately excluded from `PROMOTABLE_PAIRS` — informational only, never promoted.

### W617 UPSTREAM_BACKLOG_STATUS_FILTERED

**Trigger**: Fired by `specdev upstream-backlog` whenever its `--status` filter (default `open`) excludes at least one record that otherwise satisfies the `--severity` threshold. DEVSPEC-123: a bare invocation against a milestone plan where most ambiguities had already been resolved looked like the tool was scanning nothing, when in fact `execution.emergent_ambiguities[]` was being scanned correctly — the resolved records were just silently outside the default view. The filters apply to items of the 1.1.1 shape only: an item with `about` is always listed and is never counted in this warning.

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

**Trigger**: R003 — `specdev registry-check` finds that a registered `(array_path, id_field)` pair no longer matches the live spec file's structure: the declared array path is not an array, or its entries lack the registered `id_field`. An absent collection, root or nested (e.g. an optional root `constraints` or a task's `acceptance_criteria`), is not drift: collections may be legitimately optional per schema, and required presence is owned by schema validation in `spec-check`. A present-but-wrong-shape collection (including a key present with `null`), one whose first entry lacks the `id_field`, and a file whose top level is not an object still fire E622.

**Resolution**: Run `specdev registry-generate` to regenerate `entry_key_registry.json`/`extraction_paths.json` from the current schemas, or fix the schema/spec structure if the drift indicates an unintended shape change.

**Promotable**: No (error only).

### W614 UNREGISTERED_ARRAY

**Trigger**: R004 — a host spec file has an array of dict items bearing an `*_id` (or `id`) field that is not declared in the registry as a known `(basename, array_path)` pair — a novel array the generator doesn't yet know about.

**Resolution**: If the array should be tracked (e.g. for cross-step ID validation), add it to the registry source and run `specdev registry-generate`. If it's intentionally untracked free-form data, no action is required — R004 is advisory (WARNING, not ERROR) precisely because the generator may not yet cover every new array shape.

**Promotable**: No (warning only).

## Open Items (63x)

An open item is an entry of an `ambiguities` array (the step files 00 to 15, the anchor's `plan.ambiguities`, a milestone plan's `plan.ambiguities` and `execution.emergent_ambiguities`) that has not been answered and deleted: a question the spec cannot answer yet. An item of the 1.2.0 shape has `about` (the ids of the nodes it is about, or a node kind with `missing_kind`) and, once the operator has answered, a non-empty `decision`. An item of the 1.1.1 shape has `severity` and `status` and is open until `status` is `resolved`. The check is `open-items` (`validation/open_items.py`), at one of three gates.

Today one command reports these codes. `spec-check` reports W630 (check `open-items`): in plain `spec-check` and in `spec-check --step` and `--paths`. No command runs the merge gate or the close gate yet, so no command reports E631, E632 or W633.

### W630 OPEN_ITEM

**Trigger**: An open item exists. The step gate reports one W630 for each item of the 1.2.0 shape, for example `open item amb-reset-seed in 05_interface_contracts.json: about seed-accounts; answer known: apply in the batch pass` (the item has a `decision`) or `... answer needed from the operator` (it has none). For items of the 1.1.1 shape (the message calls them legacy) it reports one summary for each artifact and step, for example ``3 legacy open items in 05_interface_contracts.json (ambiguities); see `upstream-backlog` ``. The parenthesis names the array that holds them, and the owner is the step of that array: a step file `00` to `15` gives `(ambiguities)` and `step:<step of the file>`; the anchor `16_impl_context.json` gives `(plan.ambiguities)` and `step:16`; a milestone plan gives `(plan.ambiguities)` with `step:16a` and `(execution.emergent_ambiguities)` with `step:16b`, so a plan with legacy items in both arrays gets two summaries. For one item the finding carries its `node_id`. An item with no id is named `(no id)`: `open item (no id) in <file>: ...`. An item of a frozen milestone plan is skipped; today no plan is frozen. A spec file that cannot be read (no permission, or a folder named like a step file) ends the check with one E520, `cannot read <path>: <reason>`, owned by the step of that file (`step:04` for `04_fr_list.json` in `spec-check --json`); the other checks of the run go on.

**Resolution**: Warning only; it never blocks. `specdev upstream-backlog` lists the items by the step they are about. Apply a known answer in the batch pass and delete the item; ask the operator for an answer that is needed.

**Promotable**: No. Not in `PROMOTABLE_PAIRS`: `SPECDEV_WARNINGS_AS_ERRORS=1` leaves it a warning, and `SPECDEV_PROMOTE_CODES=W630` is ignored with a warning on stderr.

### E631 OPEN_ITEM_AT_MERGE

**Trigger**: The merge gate finds an open item that is not in a frozen plan, one E631 for each item, owner `merge-check`, for example `open item amb-reset-seed in 05_interface_contracts.json: about seed-accounts; apply the answer (known: apply in the batch pass), then delete the item`. No command runs the merge gate yet.

**Resolution**: Apply the answer to the spec, then delete the item.

**Promotable**: No (error only).

### E632 OPEN_ITEM_IN_PLAN

**Trigger**: The close gate finds an open item in the milestone plan that is closing, one E632 for each item, owner `close-gate`, for example `open item amb-plan-confirm-status in impl_context/ms_account_recovery_plan.json: about api-password-reset-confirm; answer it and delete the item before the milestone closes`. It looks at the plan named by `plan_path` only. No command runs the close gate yet.

**Resolution**: Answer the item and delete it before the milestone closes.

**Promotable**: No (error only).

### W633 OPEN_ITEM_LEGACY_TRIAGE

**Trigger**: The merge gate finds an open item in a frozen milestone plan, one W633 for each item, owner `merge-check`, for example `open item amb-plan-confirm-status in impl_context/ms_account_recovery_plan.json: about api-password-reset-confirm; in a frozen plan: listed for triage, does not fail the merge`. No command runs the merge gate yet, and no plan is frozen yet (`default_frozen` answers no for every plan), so nothing reports W633.

**Resolution**: Informational only. Decide for each item whether it still matters; a frozen plan is not edited.

**Promotable**: No. Not in `PROMOTABLE_PAIRS`.

## Spec Graph (70x / 72x)

A finding about the spec carries an `owner` (`step:<id>`, `merge-check`, `close-gate` or `release-gate`) and, when a node is involved, a `node_id`. `spec-check --json` prints both, and every finding in it has an `owner`: the one the finding carries, else the row of `tools/error_ownership.json` for its code, else the default owner of its check (`merge-check` for most checks). The codes of the spec graph that do this are E700 to E704, W720, E740 to E749, E752, E761 to E763, E768, E771, E772, E774, E778 and E882 (E760 carries an owner and no node id), and the open-item codes W630, E631, E632 and W633 (owners `step:<id>`, `merge-check`, `close-gate` and `merge-check`). The rows of `tools/error_ownership.json` give the owner of some of them (the others set it when they are raised): the owner of a link finding is the step of the node that holds the link, and E762 and E763 are for the merge check. The codes that refuse a command (E705 to E709, E764, E765, E767, E769, E770, E773) carry no owner.

### E700 LINK_TARGET_NOT_FOUND

**Trigger**: A link field names an id that no node has. Reported by `spec-check` (check `graph`). When no file of any step that holds a kind the field accepts exists in the spec, the message says that no file of those steps exists, instead of "no node has that id"; when such a file exists but could not be read (for example, it is not valid JSON, or its top level is not an object), the message says that the file could not be read, so the target cannot be checked. This replaces the step 12 E590 check of a job's `depends_on`.

**Resolution**: Owner `step:<holder step>`. Fix the id, or define the node it names.

**Promotable**: No (error only).

### E701 LINK_TARGET_WRONG_KIND

**Trigger**: A link field names a node whose kind is not one of the kinds the field allows.

**Resolution**: Owner `step:<holder step>`. Point the field at a node of an allowed kind.

**Promotable**: No (error only).

### E702 LINK_POINTS_DOWNSTREAM

**Trigger**: A link field names a node of a later step (or of the same step, where that is not a declared same-step link).

**Resolution**: Owner `step:<holder step>`. Link only to a node of an earlier step.

**Promotable**: No (error only).

### E703 LINK_CYCLE_SAME_STEP

**Trigger**: Links among nodes of one step form a cycle (a node that links to itself counts). One finding per cycle, naming its members. Reported by `spec-check` (check `graph`); a job `depends_on` cycle or a task `depends_on` cycle is E703, which replaces E141. The tasks of the whole roadmap are checked together, so a cycle that runs through the tasks of two milestones is reported too (1.1.1 did not check it). A single-file `validate` does not report a cycle.

**Resolution**: Owner `step:<step>`. Break the cycle.

**Promotable**: No (error only).

### E704 DUPLICATE_NODE_ID

**Trigger**: An id is defined by more than one node, in one file or in several, whatever the lifecycle of each. Reported by `spec-check` (check `graph`) for the whole spec, and by `validate` on one file for an id repeated inside that file. The message names both definitions and a free numeric-suffixed id. The row of `tools/error_ownership.json` does not list E704: its owner is set when it is raised.

**Resolution**: Owner `step:<step of the later definition>`. Rename one definition.

**Promotable**: No (error only).

### E705 LIFECYCLE_CHANGE_REFUSED

**Trigger**: A `node status` change was refused: an unknown or ambiguous id, a value that is not `active`, `deprecated` or `not_applicable`, a node of role `record` or `seed`, or a write the JSON tools refuse (for example an edit that would introduce a schema violation; the file is left as it was). When a spec file could not be read, the message of an unknown id adds that the node may be in one of the files named, and the command prints `specdev node: could not read <files>; the answer may be incomplete` on stderr first, where `<files>` are the unreadable files joined by ", ".

**Resolution**: Command usage error: no owner, no node id. Correct the command arguments.

**Promotable**: No (error only).

### E706 GRAPH_COMMAND_TARGET_UNKNOWN

**Trigger**: A command was given an id, step, field, kind or role the graph does not know, for example an unknown `--kinds` or `--verbs` name of `trace`, a `--recipe` role that is not `16a`, `16b` or `16c`, or, from the graph and trace commands, an unknown node id, step or link. An unknown step prints `E706 no step '99'; known steps: 00, 01, ...` (`spec-check --step`, `stale --step`, `attest --step`, `step ready`, `json insert --step`, `step create`). `spec-check --step` takes the step as in the file name: `--step 5` and `--step 13A` print `E706 no step '5'; known steps: 00, 01, 02, 02a, ... 16c` and exit 1. An unknown node id prints `E706 no node with the id 'fr-nope'; nearest: fr-password-reset, prod, term-reset-token` from `node`, `node show`, `node candidates --for`, `node rename`, `attest <id>` and `json patch|insert|delete --id`; `trace` prints `E706 no node has the id 'fr-nope'` and names no nearest ids; `node status` prints `E705 no node has the id 'fr-nope'`. `attest <id> --field F` and `--target T` name only the flags given, for a node that holds no such link: `E706 'api-password-reset-confirm' holds no link with target nope`, `E706 'api-password-reset-confirm' holds no link with field nope`, `E706 'api-password-reset-confirm' holds no link with field derives_from and target nope`. When a spec file could not be read, the message of an unknown id adds that the node may be in one of the files named, and the command prints a line on stderr first, for example `specdev trace: could not read <files>; the answer may be incomplete`, where `<files>` are the unreadable files joined by ", ".

**Resolution**: Command usage error: no owner, no node id. Correct the command arguments.

**Promotable**: No (error only).

### E707 RECIPE_START_KIND_INVALID

**Trigger**: The start node of a recipe is not of the kind the role starts from.

**Resolution**: Command usage error: no owner, no node id. Start from a node of the right kind.

**Promotable**: No (error only).

### E708 DIFF_REF_UNRESOLVED

**Trigger**: A ref given to `diff` does not resolve, or the spec folder cannot be read at it: for example a `--git-root` that is not a folder or not a git repository, a spec folder that is absent at the ref or outside the git root, or git failing. `spec-check --paths` gives it too for a spec folder outside `--git-root`: `E708 the spec folder <dir> is not inside the git root <root>, so it cannot be found in the repository` (exit 1). `spec-check --step` is not refused in that layout: the report says `base: unavailable` and stderr has a `note:` with the same words.

**Resolution**: Command usage error: no owner, no node id. Give a ref that exists.

**Promotable**: No (error only).

### E709 DIFF_REF_PREDATES_GRAPH_MODEL

**Trigger**: The tree at a ref given to `diff` has no graph node (seeds do not count), which is what a tree from before the 1.2.0 node model can look like. The message says the tree may predate the model and names the toolkit version its spec is stamped with, or says it carries no stamp (it says so also when the stamp file cannot be read). A tree from before 1.2.0 that has ids the registry reads is not refused: it is compared as it is, and the result is not meaningful.

**Resolution**: Command usage error: no owner, no node id. Give a ref whose spec folder has graph nodes.

**Promotable**: No (error only).

### W720 LINK_TO_DEPRECATED_NODE

**Trigger**: A link names a node whose lifecycle is `deprecated` and the trace lock has no entry for that link yet, so the link is new. Reported by `spec-check` (check `graph`), together with the missing entry (E761), and by `validate-all`. A link that already has a lock entry raises nothing. Example, after `specdev node status fr-password-reset-request deprecated` and a hand edit that makes `api-password-reset-confirm` link to it: `W720 api-password-reset-confirm, field derives_from, target 'fr-password-reset-request': 'fr-password-reset-request' is deprecated; point the link at the node that replaces it`.

**Resolution**: Owner `step:<holder step>`. Point the link at the node that replaces the deprecated one. Not promotable (no E counterpart).

## Graph Role Checks (74x)

Eight checks of `spec-check` read the nodes of the spec by role: `no-dangling` (E740), `term-use` (E741), `verifier-rules` (E742, E743), `cross-cutting` (E744), `refinement` (E745), `scaffold-paths` (E746), `seed-routes` (E747, E748, E749) and `prose-ids` (E752). They run on every spec, whatever shape its files have: a check is not skipped because a spec looks like 1.1.1. Each finding has an `owner` and a `node_id` (for E747 and E748 the node is the seed); plain `spec-check` prints the message only, `spec-check --json` prints the owner. The step gate (`spec-check --step N`) lists a finding that a later step owns under PENDING (owned by a later step) and does not block on it; it blocks on a finding of step N itself. A **verifier** is what a task criterion's `verified_by` may name: a fixture (step 08), a job (step 12) or a rule (step 10). A fixture or a job proves the nodes its `verifies` names (a job also the nodes its `realises` names); a rule proves itself.

E740, E742 and E743 are **coverage gaps**: a node, or a missing node, that the spec should have linked. `specdev stale` counts them under the step that owns them (`step 08: 0 suspect nodes, 0 suspect links, N coverage gaps`), `specdev coverage` prints them under `Role findings`, and `specdev step ready` counts them as blockers of the steps that link to that step. The other codes of this section are not coverage gaps; only `spec-check` reports them. This is not the same as **pending replay** (what `specdev stale` lists and what E773 refuses on: a suspect link, or a coverage gap, that a step above still holds) and not the same as the step gate's PENDING (a finding that a later step owns).

The messages below are copied from runs on copies of the worked example (`tests/fixtures/graph_example`), with the code as it is now. The worked example is a partial spec: `spec-check` reports 17 E740, 5 E743 and 1 E744 on it, and none of the other codes of this section, and `specdev step ready 14` reports 6 blockers (the five E743 of step 08 and the missing file of step 13a). These counts are written here and nowhere else in the documentation: the other places, and the quotes below, write `N` or say that the partial example reports role findings, because the counts move when the example changes.

**The attest step.** Most fixes below add, change or remove a link, and the trace lock (see [Trace Lock (76x)](#trace-lock-76x)) has to follow before `spec-check` is clean. Until it does, `spec-check` shows E761 for a link that is new (the lock has no entry for it), E763 for a link whose target, or something above its target, was edited (editing a node makes suspect the links that point at it and those below it), and E762 for a link that was removed (the lock still has its entry). So a fix that touches a link ends with the attest step: run `specdev attest <node> --yes` for each node an E761 or E763 names, run `spec-check` again, and repeat while one of them shows (a node that links to another suspect node is refused with E764: attest the node it links to first, or run `specdev attest --step NN --yes`, which goes upward first); after a link was removed, run `specdev attest --prune`. A Resolution below says it **clears** a finding when, after the attest step, the finding was gone and `spec-check` showed no finding that the run had not started with. Each fix that the Resolutions describe was run on a copy of the worked example, and each ended with that step; without it the runs showed E761, E762 or E763 in place of the finding.

### E740 NODE_DANGLING

**Trigger**: A node of a requirement, delivery or context kind (for example a criterion, an API error, an NFR, a rule, a threat, an environment, a secret or a metric) is used by no other node, and none of the nodes it contains is used. A node is used when a node that is not out of scope links to it with one of the verbs the message lists, or when a node it contains is used (an FR is used when one of its criteria is). Reported by `spec-check` (check `no-dangling`). A node is not checked when its lifecycle is `not_applicable` or its scope is `later` or `out`. A child keeps its own `scope`: parking an FR does not park its criteria, which are still checked until they are parked too. Example, from the worked example: `E740 edge-case ec-token-at-expiry-second is not used by any node; a node of this kind is used by task-criterion refines (step 14): link it, or set scope later or out with a scope_reason`. The message lists at most five ways to use the kind and then says how many more there are (`... and 4 more`). It ends with the ways out that exist for the kind. `link it` is always there. `schedule it` is there only for a kind that a step 09 milestone's `schedules` is one of the ways to use: a criterion, an FR and an NFR in the worked example (`E740 criterion ac-password-reset-1 is not used by any node; a node of this kind is used by api-error derives_from (step 05), design-milestone schedules (step 09), edge-case mitigated_by (step 11), threat mitigated_by (step 11), task-criterion refines (step 14): link it, schedule it, or set scope later or out with a scope_reason`), and, by the use table of the check, an API, an invariant and a risk (not run). `set scope later or out with a scope_reason` is there only for a kind whose schema has a `scope` field. So the message of an environment, a secret, a rule, a threat, an edge case or an API error ends `link it, or set scope later or out with a scope_reason`: the `schedules` field refuses a secret, a rule, a threat, an edge case and an API error (E701), and accepts an environment but does not count that as a use. A charter metric has no `scope` field either, so its message ends after the ways to link it: `E740 metric metric-reset-completion-rate is not used by any node; a node of this kind is used by capability derives_from (step 01), nfr derives_from (step 07): link it`.

**Resolution**: Owner `step:<the latest step whose nodes can use this kind>`: `step:07` for a metric (a capability or an NFR can use it), `step:12` for an environment or a secret (a job), `step:14` for a criterion or an edge case (a task criterion). A coverage gap: the step gate shows it under PENDING until that step is gated. Fix it one of three ways, the ones the message names for the kind, and finish with the attest step.

- **Link it** from a node that can use it (the message names the kinds and verbs). Run for each kind of the worked example: a metric, when an NFR lists it in `derives_from`; an environment, a secret or a rule, when a job lists it in `realises`; a criterion, an API error or an NFR, when an edge case lists it in `mitigated_by`; an FR, when another FR lists it in `depends_on` (the FR that holds the new link is edited, so the attest step attested it and the 13 nodes below it); an edge case or a threat, when a task criterion `refines` it and lists in `verified_by` a verifier that proves it through its mitigations (`fix-password-reset-expired-token`; a verifier that proves something else starts E745). For a kind the worked example does not have (a capability, an invariant, an API, a component, a connection, a third party, a risk, a constraint) the message lists the ways to use it; use one of them. These were not run.
- **Schedule it**, where the message says so: add the node to `schedules` of a step 09 milestone. Run for a criterion, an FR and an NFR, each added to `schedules` of `milestone-account-recovery`; the attest step attested that milestone. The message does not say it for an environment, because scheduling `dev` left its E740 in place, and not for a metric, because that gave E701.
- **Park it**, where the message says so: set `scope` to `later` or `out` and give a `scope_reason` (without the reason the schema gives E520: `04_fr_list.json:functional_requirements/0/acceptance_criteria/0: 'scope_reason' is a required property`). Run for an environment, a secret, a criterion, an FR, an API error, an NFR, a rule, an edge case and a threat. Parking the criterion edits a node that links point at, so the attest step was needed (12 nodes below it); no other run needed it. Parking a criterion also cleared its E743, and parking the NFR cleared its E743 and the E744 it had caused. A child keeps its own scope: `scope: later` on `fr-password-reset-request` cleared the E740 of the FR and left the E740 and E743 of its two criteria, which went when the criteria were parked too. A charter metric has no `scope` field (the schema refuses it: `00_charter.json:success_metrics/1: Additional properties are not allowed ('scope' was unexpected)`), so only a link clears a metric: an NFR that lists it in `derives_from` cleared `metric-reset-completion-rate`.

**Promotable**: No (error only).

### E741 TERM_NOT_USED_BY_LABEL

**Trigger**: A glossary term whose current label no node uses. A term stores no link, so it is used when its label appears in the text of a node of steps 04 to 15 (a requirement, contract, invariant, task or other node that is not a record). The match ignores case, reads `-`, `_` and `/` as a space, needs whole words and allows `s` or `es` after the last word: with the label `recovery code`, `A Recovery-Code is single use.` and `Recovery codes expire.` match, `The recovery codex is long.` and `Recoverycode is one word.` do not. Only the current label matches. A term is not checked when its lifecycle is `not_applicable`. Reported by `spec-check` (check `term-use`). Example, after the label of `term-reset-token` was changed to `recovery code` and no text was changed: `E741 term 'term-reset-token' ('recovery code') is not used: no node of steps 04 to 15 mentions its label; use it in the text of a requirement, contract, invariant, task or other non-record node, or mark the term not_applicable`.

**Resolution**: Owner `step:14`. Use the label in the text of a node of steps 04 to 15, or mark the term `not_applicable`. Using the label edits a node, so the attest step follows (the run added the words to the `statement` of `fr-password-reset` and attested the 13 nodes below it). `specdev node status term-reset-token not_applicable` cleared it with no attest step. Not a coverage gap: `stale` does not count it.

**Promotable**: No (error only).

### E742 UNUSED_VERIFIER

**Trigger**: A verifier that nothing uses. A fixture is unused when no task criterion lists it in `verified_by`, even if it verifies something. A job is unused when no task criterion lists it and it realises and verifies nothing; a job that `verifies` a node is used even if no criterion lists it. A task criterion of a closed milestone counts: a fixture that only such a criterion lists is used. Reported by `spec-check` (check `verifier-rules`). The unchanged worked example has none. Examples, after a second fixture was added and no criterion listed it: `E742 fixture fix-password-reset-spare is not used: no task criterion lists it in verified_by; list it in a criterion's verified_by, or remove it and run specdev attest --prune`; for a job with an empty `realises`: `E742 job job-idle is not used: no task criterion lists it in verified_by, and it neither realises nor verifies a node; list it in a criterion's verified_by, or remove it and run specdev attest --prune`.

**Resolution**: Owner `step:14`. A coverage gap. Two ways. List the verifier in the `verified_by` of a task criterion that refines what it verifies; this adds a link, so the attest step follows (the run listed a spare fixture in `tc-confirm-expired-token` and attested that criterion and `PWRESET_CONFIRM_EXPIRED_01`). Or remove it and run `specdev attest --prune`: a removed fixture left E762 (`trace lock entry ... has no link any more`) until the prune; a job that nothing links has no lock entry, and the prune reported `no orphan entries`. Listing a fixture in one criterion and not in another can make the other fixture unused: after `verified_by` of `tc-confirm-expired-token` was changed from `fix-password-reset-expired-token` to `fix-password-reset-reused-token`, the first fixture got this error and the criterion got E745.

**Promotable**: No (error only).

### E743 MISSING_VERIFIER

**Trigger**: A node that a verifier should prove has none. The kinds a fixture's `verifies` may name are checked: an acceptance criterion, an API, an invariant and an NFR. An API error is not checked (it is proven with its API), and neither are a threat, an edge case or a rule. A node is not checked when its lifecycle is `not_applicable` or its scope is `later` or `out`: `scope: later` with a `scope_reason` on `ac-password-reset-2` cleared its E743. A node that a task criterion of a closed milestone lists in `removes` is not checked either (a milestone is closed when its row in `plan.milestone_index` of `16_impl_context.json` is `done`): with the milestone open the E743 stayed, with it closed it went, and the E740 of the node stayed in both cases. Reported by `spec-check` (check `verifier-rules`). Examples, from the worked example: `E743 criterion ac-password-reset-1 has no verifier: add a fixture at step 08 that verifies it and that a task criterion lists in verified_by`; `E743 nfr nfr-latency-reset-email has no verifier: add a fixture at step 08 that verifies it and that a task criterion lists in verified_by, or a job at step 12 that verifies it`.

**Resolution**: Owner `step:08`, the step that writes the fixtures. A coverage gap: the step gate shows it under PENDING until step 08 is gated (at `--step 07` the E743 findings of the worked example are in the PENDING count, `08: N`). Add a fixture whose `verifies` names the node, and list the fixture in `verified_by` of a task criterion, as the message says. A fixture alone clears the E743 and starts E742 for the new fixture (run: `fix-ac1`). With both, and the attest step (the fixture, `tc-confirm-expired-token` and `PWRESET_CONFIRM_EXPIRED_01`), the E743 of a criterion and of the NFR went and nothing else came. An NFR can be proven the other way, with a job whose `verifies` names it (step 12; a job's `realises` does not accept an NFR, E701); the job needs no criterion to list it, and the attest step attested the job. A new job also needs the canonical proposal of each command it runs (E210 names the command): that is the step 12 rule, not part of this advice.

**Promotable**: No (error only).

### E744 CROSS_CUTTING_NOT_REFINED

**Trigger**: An invariant or an NFR that constrains something applies to a task, and no criterion of the task refines it. The invariant or NFR applies to a task when the task refines something that leads to the same capability or component that the invariant or NFR constrains. The tasks of a closed milestone are not checked: with the milestone of the worked example marked done, `cross-cutting` passes. Reported by `spec-check` (check `cross-cutting`). Example, from the worked example: `E744 task task-implement-password-reset-confirm falls under nfr-latency-reset-email through cap-account-recovery but no criterion of the task refines it; add a task criterion that refines nfr-latency-reset-email and lists in verified_by a verifier that verifies it`.

**Resolution**: Owner `step:14`. Add a criterion to the task whose `refines` names the invariant or NFR, and list in its `verified_by` a verifier that verifies the same node (a fixture or a job whose `verifies` names it), then the attest step (the criterion and the verifier). A criterion that refined `nfr-latency-reset-email` with a new fixture or a new job that verifies the NFR cleared E744, the E740 of the NFR and its E743, and nothing came. The criterion alone cleared E744 and started E745 (`(none listed)`).

**Promotable**: No (error only).

### E745 VERIFIER_DOES_NOT_VERIFY_REFINED

**Trigger**: A criterion of a task refines a node, and no verifier in its `verified_by` proves that node. A verifier proves it when its `verifies` names the node, a node that contains it or a node it contains; when it is a job that `realises` the node; or when it is the rule that is the refined node (a rule listed in its own criterion). A threat or an edge case is proven through its mitigations: a verifier proves it when it is one of the nodes in its `mitigated_by` (a fixture the threat names) or proves one of them (a fixture that verifies a mitigating invariant). A criterion that lists no verifier gets the finding too, with `(none listed)` in the place of the verifiers. The criteria of a closed milestone are not checked: with the milestone of the worked example marked done, `refinement` passes. Reported by `spec-check` (check `refinement`). Example, after `verified_by` of `tc-confirm-expired-token` (which refines `ac-password-reset-3`) was changed to `fix-password-reset-reused-token`: `E745 task criterion tc-confirm-expired-token refines ac-password-reset-3 but none of its verifiers (fix-password-reset-reused-token) verifies ac-password-reset-3, a node that contains it or a node it contains (for a threat or an edge case: one of its mitigations or a verifier of one); add a verifier that does`. For a criterion that refined `threat-reset-token-replay` and listed a fixture that verifies only `ac-password-reset-request-1`, the same message names the threat and that fixture. The unchanged worked example has none.

**Resolution**: Owner `step:14`. List a verifier that proves the refined node in `verified_by`, or change what the criterion refines; then the attest step. Runs: adding `fix-password-reset-expired-token` to `verified_by` of `tc-confirm-expired-token` cleared it (and the E742 that the change had left on that fixture); for a criterion that refined `threat-reset-token-replay` and listed a fixture that verifies something else, adding the fixture `fix-password-reset-expired-token`, which the threat names in `mitigated_by`, cleared it, and so did listing a fixture that verifies the mitigating invariant `inv-reset-token-single-use`; a criterion with no verifier was cleared by a new fixture that verifies the node it refines, listed in `verified_by`. Not a coverage gap.

**Promotable**: No (error only).

### E746 SCAFFOLD_PATH_NOT_TRACKED

**Trigger**: A scaffold row (step 15) names a file that git does not track, for an API that is built. An API is built when a task criterion of a closed milestone refines it and the link is attested at the content the API has now (the run added a criterion that refines `api-password-reset-confirm`, attested it, and set the row of the milestone in `plan.milestone_index` of `16_impl_context.json` to `done`, with `close.signed_off_by`). A criterion that was not attested gave E761 and no E746; an API edited after the attest was not built, so it gave no E746. `spec-check` checks a row only once an API it realises is built (a row of two APIs is checked when either is built; a row of an API that is not built is not); with no API built, as on the unchanged worked example, it reports nothing. A file that exists but was never added to git is not tracked; one that is added to the index is. A row whose path lies under a submodule that is not checked out cannot be judged: `spec-check` writes a note on stderr (`note: scaffold row scaffold-password-reset-confirm path theme/routes/confirm.ts is under submodule theme, which is not checked out: not checked`) and checks the other rows. Outside a git repository the check is skipped and the summary says why: `[SKIP] scaffold-paths (git ls-files failed: fatal: not a git repository (or any of the parent directories): .git)`. It is skipped too when every row to check lies under a submodule that is not checked out, as in a clone that has not run `git submodule update`: `[SKIP] scaffold-paths (every scaffold row to check is under a submodule that is not checked out (theme))`; `--json` gives the same text as the `reason`. Reported by `spec-check` (check `scaffold-paths`). Example, after a done milestone made `api-password-reset-confirm` built: `E746 scaffold row scaffold-password-reset-confirm names src/routes/password-resets/confirm.ts, which is not a tracked file (merge mode); add and commit the file, or correct the row's path`. The words `merge mode` name the mode in which `spec-check` runs this check: it reads only the rows of built APIs. The modes `close` and `release`, which read every row, belong to the milestone close and release gates, which no command runs yet.

**Resolution**: Owner `step:15`. Add the file to git, or correct the `path` of the row. Both were run: creating the file and `git add` cleared it (the check reads the index, so `git add` is enough for `spec-check` although the message says commit), and so did setting the `path` to a tracked file. No attest step was needed.

**Promotable**: No (error only).

### E747 SEED_NOT_ROUTED

**Trigger**: A seed in `seeds[]` of the seed manifest that no `step_requirements` entry names. The finding points at the manifest. A seed that no entry routes gets this finding only, even when a node links it: E749 is for a seed that is routed somewhere, but not to the step of the node that links it. Reported by `spec-check` (check `seed-routes`). Example, after `seed-extra` was added to `seeds[]` with no route: `E747 seed seed-extra is listed in the seed manifest but no step_requirements entry routes it to a step; route it to the step that distils it and list it in derives_from of a node of that step, or remove the seed (its seeds[] entry and its document)`. When a node already links the seed the message names the step: `... route it to step 02 (where a node lists it in derives_from), or remove the seed (its seeds[] entry and its document) and the derives_from links to it, then run specdev attest --prune` (`steps 00, 02` for several).

**Resolution**: Owner `step:00`. Two cases, as the message says. No node links the seed: route it to the step that distils it (add it to `step_requirements`) and list it in `derives_from` of a node of that step, then the attest step (the run routed `seed-extra` to `02` and listed it in `tp-argon2`; routing alone gave E748). Or remove the seed: its entry in `seeds[]` and its document (removing the entry alone leaves the document on disk, which seed-lint does not report). A node links the seed: route it to the step of that node (the run routed to `02`: clean, no attest step). Or remove the seed, its document and the `derives_from` links to it, then the attest step and `specdev attest --prune` (without the prune E762 stayed).

**Promotable**: No (error only).

### E748 SEED_ROUTE_UNUSED

**Trigger**: The manifest routes a seed to a step, and no node of that step links the seed with `derives_from`. A step whose node kinds cannot link a seed at all is named in the message. Reported by `spec-check` (check `seed-routes`); the finding points at the step's key in `step_requirements`. Examples: a route of `seed-accounts` to step `02a` where no node links it: `E748 the seed manifest routes seed-accounts to step 02a but no node of step 02a lists seed-accounts in derives_from; distil the seed in that step (a node of step 02a lists seed-accounts in derives_from), or remove the route`; a route to step `05`: `E748 the seed manifest routes seed-accounts to step 05 but no node kind of step 05 can link a seed (only the kinds of steps 00, 02, 02a can); move the route to a step whose nodes can link a seed (00, 02, 02a) and list seed-accounts in derives_from of a node there, or remove the route`; a route to step `16`: `E748 the seed manifest routes seed-accounts to step 16 but the trinity key 16 cannot be used: no node of the trinity steps links a seed; move the route to a step whose nodes can link a seed (00, 02, 02a) and list seed-accounts in derives_from of a node there, or remove the route`. These three seeds had other routes. When the route is the only route of the seed, the end of the message is `or remove the seed from the manifest (its seeds[] entry, this route and its document), as this is its only route and a seed with no route is E747`.

**Resolution**: Owner `step:<the step of the route>`. Three ways, by the message. In a step whose nodes can link a seed: use the seed in a node of that step (add its id to the node's `derives_from`, then the attest step; this cleared a route of `seed-extra` to step `02`, with `tp-argon2`). If the seed has other routes, remove the route from `step_requirements` (run for routes to `02`, `02a`, `05` and `16`: clean, no attest step). If it is the seed's only route, removing the route alone gives E747: remove the seed with it, its `seeds[]` entry and its document (run for routes to `02`, `05` and `16`: clean). In step `05` or in a trinity key (`16`), no node can link a seed, so move the route to step `00`, `02` or `02a` and list the seed in `derives_from` of a node there (run: the route moved to `02` and `tp-argon2` listed the seed, then the attest step), or remove the route or the seed as above. The runs did not use a node of step `00` or `02a` as the place to list the seed.

**Promotable**: No (error only).

### E749 SEED_LINK_NOT_ROUTED

**Trigger**: A node links a seed with `derives_from`, and the manifest does not route that seed to the node's step. Reported by `spec-check` (check `seed-routes`). Example, after the route of `seed-accounts` to step `02` was removed: `E749 tp-argon2 derives from seed seed-accounts, which the seed manifest does not route to step 02; add seed-accounts to step_requirements["02"], or remove the link and run specdev attest --prune (a derives_from that would be left empty needs another entry)`. One finding for each link: a node that links two seeds the manifest does not route to its step gets two. A seed that no entry routes at all is E747 only.

**Resolution**: Owner `step:<the step of the node that holds the link>`. Add the seed to `step_requirements` for that step (this cleared both findings, with no attest step), or remove the link, then the attest step and `specdev attest --prune`. A `derives_from` that the removal would leave empty is not allowed (`02_system_sketch.json:third_parties/0/derives_from: [] should be non-empty`): give the node another entry first. The run replaced the seed with `con-staged-delivery` in `tp-argon2` and ran the attest step and the prune: clean.

**Promotable**: No (error only).

### E752 NODE_ID_IN_PROSE

**Trigger**: The text of a node names the id of another node, an old id of a renamed node, or a seed id. A node's own id in its own text is not reported (there is no link to write). A mention in text is not a link: the graph never sees it, so the trace lock, the suspect check and the use rules miss the relation it states. The check reads the string fields of every node whose lifecycle is not `not_applicable`: a node parked with `scope: later` or `out` is read too (a criterion with `scope: later` that mentioned `cap-account-recovery` gave the finding), and a node that is `not_applicable` is not. It does not read the id and link fields, or a field whose schema fixes the value: an enum, a constant, a format, or a pattern that rejects ordinary sentences (an id written in the `domain` of a glossary term, which has the pattern `^[a-z]+(?:-[a-z]+)*$`, gave no finding; one written in the `target_date` of a milestone, which has the format `date`, gave E520 and no E752). A pattern that some ordinary sentence satisfies fixes nothing, such as one that only asks for a non-space character, for two words, for lower-case letters and spaces, or for a capital first letter (the check tries a lower-case pair of words and a capitalised sentence with a comma and a full stop; no pattern of the schemas of the toolkit is of that kind, so this was not run on a spec): an id in the `description` of a task, in the `definition` of a glossary term or in the `statement` of an FR gave the finding. It matches whole ids that contain a `-`; a single-word id such as `dev` is an ordinary word and is not matched, and a token that looks like an id but names nothing is not reported. Reported by `spec-check` (check `prose-ids`). Example, after the `statement` of `fr-password-reset` was given the sentence `The system shall serve cap-account-recovery, as agreed.`: `E752 fr fr-password-reset mentions the id cap-account-recovery in its text at statement: a prose mention is not a link and the resolver never sees it; turn a mention that states a relation into the link, or reword it`. A retired name is reported with it (`mentions the id fr-password-reset-request (a retired name of fr-pw-request)`). On a spec of the 1.1.1 shape that has not been migrated, the old link fields (`trace`, `targets`) are such text and give E752.

**Resolution**: Owner `step:<the step of the node that holds the text>`. Two ways. Reword the text so that it holds no id (replacing the id with plain words cleared it; the node is edited, so the attest step follows). Or, if the mention states a relation, write the relation as a link and take the id out of the text: adding the link alone left the finding, as the message says, and the link with the id still in the text kept E752; the id removed and the link added (`depends_on` on `fr-password-reset`) cleared it and also the E740 of the node it named, after the attest step.

**Promotable**: No (error only).

## Trace Lock (76x)

The trace lock is `spec/extras/trace.lock.json`: one entry per link, holding the content hash and the chain stamp of the target as the holder last accepted them. Its format is `schema/extras/trace_lock.schema.json`. A link whose target now has another chain stamp is a suspect link. The messages below are copied from runs on a copy of the worked example (`tests/fixtures/graph_example`); the host path is left out of one of them.

### E760 TRACE_LOCK_MALFORMED

**Trigger**: The trace lock cannot be read. The file is not valid JSON, is not an object of the lock format (a missing or unknown key, a `version` other than 1, a hash that is not `sha256:` and 64 lower-case hex digits, a `baseline` that is not `true`), names the same (source, field, target) triple twice, or holds git merge conflict markers (`<<<<<<<`). The marker case is checked before the JSON is parsed, and the message names the repair. Reported, in runs on a worked-example copy whose lock held `{"version": 2}`, by `spec-check` (check `trace-lock`), `validate-all`, `forward-replay-check`, `stale`, `coverage`, `attest` (a preview, `--yes` and `--prune`), `step ready`, `json patch --id` and `node rename` (the commands that read the lock before they write refuse with exit 1 and write nothing); `node status`, `node <id>` and `trace <id>` were run on the same copy and printed their answer, exit 0. `specdev lock merge` reports it for an input version that is not a valid lock. Examples: `specdev lock merge bad.json bad.json bad.json bad.json` on a lock cut off after 14 bytes: `E760 trace lock bad.json: not valid JSON (Unterminated string starting at: line 1 column 13 (char 12))`; a file that holds `{"version": 2}`: `E760 trace lock <host>/spec/extras/trace.lock.json: $schema must be vc:extras:trace-lock`; a lock path that is a folder: `E760 trace lock <host>/spec/extras/trace.lock.json: cannot be read (Is a directory)`; conflict markers: `E760 trace lock <host>/spec/extras/trace.lock.json: holds git merge conflict markers (<<<<<<<). Repair, from the repository root, with three commands in this order: `specdev lock install-driver --driver-command "<path to specdev> lock merge" --spec-root <host>/spec` (routes the lock to the merge driver and sets the driver; safe to run again), `git checkout -m -- <host>/spec/extras/trace.lock.json` (merges again with the driver and writes the merged file, but git still lists the path as unmerged), `git add <host>/spec/extras/trace.lock.json``.

**Resolution**: Owner `merge-check`, no node id. For conflict markers, run the three commands the message prints, in that order: `specdev lock install-driver --driver-command '<path to specdev> lock merge'` (it sets the driver and adds the `merge=specdev-trace-lock` line to `.git/info/attributes`), `git checkout -m -- spec/extras/trace.lock.json` (it re-runs the driver and writes the merged file, but git still lists the path as unmerged), then `git add spec/extras/trace.lock.json`. For any other cause, restore the file from git or fix the entry the message names.

**Promotable**: No (error only).

### E761 LINK_LOCK_ENTRY_MISSING

**Trigger**: A link that the resolver accepts has no entry in the trace lock. Reported by `spec-check` (check `graph`), by `validate-all` and by `forward-replay-check`, once per link, in the same resolver run as E700-E703; `stale` does not list it. Links of a record and `replaces` links need no entry. Links of historical nodes (a milestone whose anchor row is `done`) still need one. Example (a hand edit through `specdev json patch <file> <path> <value>` added the link): `E761 api-password-reset-confirm, field derives_from, target 'fr-password-reset-request': the trace lock has no entry for this link; once the target is checked, `specdev attest api-password-reset-confirm` shows what would be written, `specdev attest api-password-reset-confirm --yes` writes it`.

**Resolution**: Owner `step:<holder step>`. Check the target, then run `specdev attest <holder id> --yes`; for a link with no entry it creates the entry. A link written through `specdev json patch|insert|delete --id`, `specdev json insert --step` or `specdev step create` gets its entry at once; `specdev node rename` re-keys the entries it touches. The path form of `specdev json` (`json patch <file> <path> <value>`) writes no entry, which is what the example shows.

**Promotable**: No (error only).

### E762 LOCK_ENTRY_ORPHAN

**Trigger**: A trace lock entry names a holder, field and target that no node declares any more (the link was removed or the holder was deleted). Reported by `spec-check` (check `trace-lock`). Example, after the `constrains` list of an invariant was shortened by a hand edit: `E762 trace lock entry (inv-reset-token-single-use, field constrains, target 'identity-service') has no link any more; remove it with `specdev attest --prune``. The same finding follows a merge in which one branch renamed a holder (`specdev node rename api-password-reset-confirm api-pw-confirm`) and the other branch attested one of the holder's links (`specdev attest --step 05 --yes`): after the merge the lock holds the entry the other branch wrote under the old holder id, `stale` lists the link under the new id as suspect, and `spec-check` reports the entry under the old id as E762 with the line above. Pruning removes that entry, and with it the attestation: run `specdev attest api-pw-confirm --yes` again.

**Resolution**: Owner `merge-check`. Remove the entry with `specdev attest --prune` (it writes at once; `--dry-run` lists what it would remove).

**Promotable**: No (error only).

### E763 SUSPECT_LINK

**Trigger**: The target of a link has changed since the holder accepted it: the chain stamp stored in the lock differs from the one the target has now. The message gives the cause (the target itself was edited, or something above it changed) and up to three nearest changed nodes above it. Reported by `spec-check` (check `trace-lock`), by `validate-all` and by `forward-replay-check` for links held by nodes that are not historical and not `not_applicable`. When the seed documents are not under the folder that holds the spec folder (spec at `h/sub/spec`, seeds at `h/docs/seed`), `spec-check`, `validate-all` and `forward-replay-check` run from `h` with no `--git-root` report the links to a seed as suspect (64 E763 on the worked example in that layout) and print one line on stderr that names the folder searched: `note: seed documents not found under <h>/sub: docs/seed/seed_accounts.md (seed-accounts); their links count as suspect; if the repository root is another folder pass --git-root`; with `--git-root .` they print neither. Example, after the text of a criterion was edited: `E763 api-password-reset-confirm, field derives_from, target 'fr-password-reset': suspect link, the target itself was edited; changed above: ac-password-reset-3. Review the change, then edit api-password-reset-confirm or accept it: `specdev attest api-password-reset-confirm` shows what would be written, `specdev attest api-password-reset-confirm --yes` writes it`.

**Resolution**: Owner `merge-check`. `specdev stale` lists the suspect links by step, and `specdev stale --diff` shows the change; `step ready` reports a step with suspect links above it as not ready. Read the change, then edit the holder or run `specdev attest <holder id> --yes`. Replay works upward first: `specdev attest --step NN --yes` does it for a step.

**Promotable**: No (error only).

### E764 ATTEST_REFUSED_TARGET_SUSPECT

**Trigger**: `specdev attest` refused a node because one of its own targets is itself a suspect node: a node that holds a suspect link. The message names the node and the links that block it. With `--step`, the blocked nodes are named in one E764. The exit code is 1. Example: `E764 attest refused: 'inv-reset-token-single-use' links to suspect nodes (constrains -> api-password-reset-confirm); attest those nodes first`.

**Resolution**: Command refusal: no owner, no node id. Attest the blocking node first (`specdev attest <blocking id> --yes`), then this one; `specdev attest --step NN --yes` does this upward first for a whole step.

**Promotable**: No (error only).

### E765 ATTEST_REFUSED_HISTORICAL

**Trigger**: `specdev attest` refused a node of a closed milestone (a historical node). Its lock entries stay as they were. Example: `E765 'tc-confirm-expired-token' is historical (it belongs to a closed milestone), so its links are not re-attested; its lock entries stay as they were`.

**Resolution**: Command refusal: no owner, no node id. Links of a closed milestone are not re-attested.

**Promotable**: No (error only).

### E767 WRITE_REFUSED

**Trigger**: A command that writes a spec file or the lock refused the write. Raised by `specdev json patch|insert|delete --id <node-id>`, `specdev json insert --step NN` and `specdev step create NN --from DRAFT`. The reasons include: the node is a seed; the field path names the node's id; the edit adds a schema violation; the edit would leave a link that does not resolve (for example E700) or an alias collision (E771); for `insert --id`, a field the node does not have when its schema does not declare that field as an array (a field it does declare as an array is created with the one item), or a field the node has that holds a string, an object, a number or a boolean instead of an array (a field that already holds an array takes the insert); for `insert --step`, a path that is not a node collection of the step, or one that is a map keyed by id; for `step create`, a step that already has its file, step 13a or 16 to 16c, a draft that cannot be read, or a draft whose `$schema` is not the step's own. An unknown id or step is E706, a payload that stores a computed field is E768. Nothing is written. Examples: `E767 .fr_id is the id of 'fr-password-reset'; an id is changed with `specdev node rename``; `E767 'seed-accounts' is a seed; a seed is edited as a file, not by id`; `E767 step 07 already has a spec file (07_nfrs.json); edit it with `specdev json patch|insert|delete --id``; `E767 .environments is a map keyed by id, and `specdev json insert --step` does not add to a map` (`json insert --step 02a .environments '{...}'`); `E767 step 02a has no node collection .nope; its collections: .ambiguities (ambiguity-item), .ci_gates (gate), .environments (environment, map: not added by this command), .secrets (secret)` (`json insert --step 02a .nope '{}'`); `E767 'fr-password-reset' has no nope and its schema does not declare .nope as an array, so there is nothing to insert into; set the field with `specdev json patch --id`` (`json insert --id fr-password-reset .nope '"x"'`); `E767 .statement of 'fr-password-reset' is a string, not an array, so nothing can be inserted into it; set it with `specdev json patch --id fr-password-reset .statement <value>`` (`json insert --id fr-password-reset .statement '"x"'`); `E767 .interface_ref of 'api-password-reset-confirm' is an object, not an array, so nothing can be inserted into it; set it with `specdev json patch --id api-password-reset-confirm .interface_ref <value>`` (`json insert --id api-password-reset-confirm .interface_ref '"x"'`); `E767 step 13a has no spec file that step create writes; it creates steps 00, 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15`.

**Resolution**: Command refusal: no owner. With `--json` the error names the node in `node_id`. The message names the reason.

**Promotable**: No (error only).

### E768 STORED_COMPUTED_FIELD

**Trigger**: A spec node stores a field that the toolkit computes (for example `fr_refs` on a roadmap task, `milestone_ref` on a plan item, `content_hash` on any node). Raised by the `computed-fields` check of `spec-check`, and by `specdev json patch --id` when the payload stores one (E768 is the code of the refusal, exit 1); the message names the node id, the view and where the value comes from. Examples: from `spec-check`, `E768 fr-password-reset (fr) stores 'content_hash', which is computed (content hash and chain stamp). Remove it; the content hash and the chain stamp are computed from the node's text and are kept in the trace lock, not in a spec file`; from `specdev json patch --id fr-password-reset .content_hash '"sha256:aa"'`, `E768 the write to fr-password-reset stores 'content_hash': it is computed (content hash and chain stamp); remove it; the content hash and the chain stamp are computed from the node's text and are kept in the trace lock, not in a spec file`.

**Resolution**: Owner `step:<node step>` (from `spec-check`). Remove the stored field.

**Promotable**: No (error only).

### E769 LOCK_WRITE_CONFLICT

**Trigger**: A command that writes the lock found another specdev write running: the exclusive lock on the spec folder is held by another process (no folder is created for it). Example, with a process that held the lock on `<host>/spec` while `attest --prune` and `node status` ran: `E769 another specdev write is running (the lock on <host>/spec is held); wait for it to finish, then run the command again`.

**Resolution**: Command refusal: no owner, no node id. Wait for the other command to finish and run this one again.

**Promotable**: No (error only).

### E770 RENAME_REFUSED

**Trigger**: `specdev node rename` (or `node rename --label`) refused a rename and wrote nothing: the node is a seed or a record (for example), the old and the new id are the same, the new id is the id or an alias of a node, the new id is not an id (`Bad Id`), or, with `--label`, the id is not a glossary term. An unknown id is E706, not E770. Exit 1. Example: `E770 'fr-password-reset' is an alias of 'fr-reset-password'; choose an id no node or alias has`.

**Resolution**: Command refusal: no owner, no node id. The message names the reason.

**Promotable**: No (error only).

### E771 ALIAS_COLLISION

**Trigger**: An alias equals a live node id or an alias another node lists. Aliases share the id space of the nodes, whatever a node's lifecycle. Reported by `spec-check` (check `graph`); an id write that would create the collision is refused (E767 naming E771). Example: `E771 fr-reset-password: alias 'fr-password-reset-request' is the id of a fr; give the node a different alias`.

**Resolution**: Owner `step:<node step>`. Give the node a different alias.

**Promotable**: No (error only).

### E772 REPLACES_NAMES_LIVE_NODE

**Trigger**: A `replaces` link names a node that is still in the spec (by its id or one of its aliases). Reported by `spec-check` (check `graph`). Example: `E772 fr-password-reset-request, field replaces, target 'fr-password-reset': 'fr-password-reset' is still in the spec; delete it or drop the link`.

**Resolution**: Owner `step:<node step>`. Deprecate or remove the replaced node, or drop the link.

**Promotable**: No (error only).

### E773 STEP_NOT_READY

**Trigger**: `specdev step ready NN` found that step NN may not start: a step above it has no spec file, or holds pending replay (a suspect link, or a coverage gap: E740, E742 or E743, as counted by `specdev stale`). The steps checked are the steps NN's nodes link to, plus (for the presence check only) the `required_spec_inputs` of NN in `tools/step_order.json`; the file of NN itself is not required (`step ready 07` with no 07 file reports `step 07: ready` on the worked example). Exit 1; the report lists each blocker (node, link, roots) and ends with what to do first, by the blockers of the first step: `write step NN first` when it has no file, `replay step NN first` when it holds suspect links, `fix the coverage gaps of step NN first` when it holds only coverage gaps, and `replay step NN first and fix its coverage gaps` when it holds both. Examples: after the text of `ac-password-reset-3` was edited, `E773 step 06 is not ready: step 05 (2 blockers); replay step 05 first`; with the file of step 05 missing, `E773 step 07 is not ready: step 05 (1 blocker); write step 05 first`; with suspect links and coverage gaps at step 08, `E773 step 14 is not ready: step 08 (N blockers); step 13a (1 blocker); replay step 08 first and fix its coverage gaps`. On the worked example `step ready 14` reports `E773 step 14 is not ready: step 08 (N blockers); step 13a (1 blocker); fix the coverage gaps of step 08 first` (N is the number of E743 findings, which moves with the example) and lists the blockers: `step 08: coverage gap E743: ac-password-reset-1` (and the other E743) and `step 13a: no spec file yet`. The step 08 blockers are the missing verifiers of the partial example (E743, owner step 08); step 13a is a blocker because `tools/step_order.json` still lists 13a as an input of 14 and the example has no 13a file, which lasts until a later 1.2.0 change retires step 13a.

**Resolution**: Command refusal: no owner, no node id. Do what the last words say, earliest step first. `write step NN first`: write the step. `replay step NN first`: `specdev stale`, then `specdev attest` (`attest --step NN --yes` cleared the suspect links of step 05 and `step ready 06` printed `step 06: ready`). `fix the coverage gaps of step NN first`: fix the findings the report names (E740, E742, E743, as in this section); `attest` clears only suspect links and said `attest: nothing to attest` for a step with only gaps. In the run, one fixture that verified the four criteria, listed in `verified_by`, and a job that verified the NFR, then the attest step, took step 08 out of the blockers; only `write step 13a first` was left.

**Promotable**: No (error only).

### E774 RECORD_INVALID

**Trigger**: A record file under `spec/extras/verification/` (`ver-<id>.json` for a verification record, `evd-<id>.json` for an evidence record) is not valid. Reported by `spec-check` (check `records`) for a file that is not a JSON object, violates the schema its `$schema` names (for example a second record in the file, an id with the wrong prefix, no `output_guard`, an unknown `stage`, a malformed `output_hash`), holds no record of the kind its name prefix declares, or has a file name that is not its record id. A `verifies` or `about` id that no node has is E700 from the `graph` check, not E774. Examples: `E774 extras/verification/ver-bad.json: unreadable or not a JSON object`; `E774 extras/verification/ver-other-name.json: the file name 'ver-other-name' is not the record id 'ver-password-reset-expired-token'`; a second record in the file: `E774 extras/verification/ver-password-reset-expired-token.json: records: has more items than the schema allows`; a schema violation inside the record: `E774 extras/verification/ver-x.json: records/0/verification_id: 'bad-x' does not match '^ver-[a-z0-9]+(?:-[a-z0-9]+)*$'`.

**Resolution**: Owner `merge-check`. Fix the record the message names; the file name has to be the record id.

**Promotable**: No (error only).

### E778 STALE_ALIAS_USE

**Trigger**: A live node's link names an alias of a node instead of the node's current id. Reported by `spec-check` (check `graph`), `validate-all` and `forward-replay-check`; a link of a historical node (a closed milestone) or of a record keeps the old id and is not reported. `specdev node rename` rewrites the links of live nodes itself, so this appears after a hand edit. Example: `E778 api-password-reset-confirm, field derives_from, target 'fr-password-reset': 'fr-password-reset' is an old id of 'fr-reset-password'; use the current id 'fr-reset-password'`.

**Resolution**: Owner `step:<holder step>`. Rewrite the link to the current id.

**Promotable**: No (error only).

### E882 MIGRATION_BASELINE_NOT_REATTESTED

**Trigger**: A trace lock entry still carries the `baseline` marker that a migration stamps, and its holder is not a historical node. Reported by `spec-check` (check `trace-lock`). Entries of historical holders keep the marker without error. Example: `E882 trace lock entry (PWRESET_CONFIRM_EXPIRED_01, field realises, target 'tc-confirm-expired-token') still carries the migration baseline marker; check the link, then clear it: `specdev attest PWRESET_CONFIRM_EXPIRED_01` shows what would be written, `specdev attest PWRESET_CONFIRM_EXPIRED_01 --yes` writes it`.

**Resolution**: Owner `step:<holder step>`. Check the link, then run `specdev attest <holder id> --yes`: it writes the current stored hashes and clears the marker.

**Promotable**: No (error only).

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
