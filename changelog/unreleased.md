## [unreleased]

### Breaking Changes

- `schema/14_roadmap.schema.json` roadmap task `status` enum now accepts `deferred`
  and `wont_do` alongside `pending`/`in_progress`/`done`, each requiring a new
  task-level `status_reason` field (DEVSPEC-122 follow-up). Previously a task had
  no way to express "paused" or "permanently cancelled" — the only escape hatch
  was deleting the task outright, which is what forced a real production incident
  (a payment-wallet routing task had to be deleted rather than deferred because
  deferring its checklist item tripped E304 `ROADMAP_TASK_UNCOVERED`). Existing
  artifacts with a task missing `status_reason` where required will now fail
  `spec-check`/`validate`. Remediation: for each roadmap task that should be
  paused or permanently cancelled instead of deleted, set `status` to `deferred`
  or `wont_do` and author a `status_reason` naming the blocker/decision and, for
  `deferred`, the condition required to resume.

- `schema/16_impl_context.schema.json` checklist items now require their own
  `deferred_reason` when `checklist_status == "deferred"` (DEVSPEC-122). Previously
  a single checklist item could be marked `deferred` with zero documentation — the
  only enforced `deferred_reason` requirement was at the whole-plan level
  (`plan.status == "deferred"`), which does not apply when the rest of the milestone
  is still active. Existing artifacts with a `deferred` checklist item and no
  `deferred_reason` will now fail `spec-check`/`validate`. Remediation: populate
  `deferred_reason` on each deferred checklist item, naming the blocker and the
  condition required to undefer — this is independent of `plan.deferred_reason` and
  does not require deferring the whole plan.

### Added

- Added W555 `STEP00_SEED_OUT_OF_SCOPE_THIN` to `seed_lint.py`: fires when seeds routed
  to step "00" supply fewer than 3 substantive out-of-scope items combined. The Step 00
  charter schema requires `out_of_scope minItems:3`; without this warning, thin seeds
  cause authors to hit a gate failure or hallucinate content at authoring time. W555 is
  warn-only and non-promotable (E555 is the distinct `SEMANTIC_COVERAGE_REGRESSION` code).

### Changed

- Relaxed the `vc:core:canon` JSON Schema `entries.minItems` constraint from 1 to 0.
  `init_project.py` bootstraps `spec/canon/manifest.json` with `entries: []` before any
  `specdev canon-accept` has run (Step 03), so the prior `minItems: 1` caused `spec-check`
  and `canonical-integrity` to emit E520 `schema_invalid` on every new project until the
  canon was populated. New projects legitimately start with an empty project-canon registry.

- Extended the changelog format schema (`changelog/format.yaml`) `optional_fields` with
  `source_of_truth` and `render_target`, declaring the authoritative YAML source file and
  its rendered Markdown target. These keys are declared in `changelog/format.yaml`'s
  `optional_fields`, so the `ChangelogFormat` parser accepts them as optional top-level
  keys in versioned changelog files without consuming their values. YAML-to-Markdown
  parity between the two paths is a manual
  convention, not tool-enforced.

### Added

- Added W616 `PAUSED_OR_CANCELLED_ITEM_MARKED_VERIFIED` to `step_16.py`: fires
  when a checklist item has `checklist_status == "deferred"` or `"wont_do"`
  while its `implementation.status` still says `"verified"`
  (DEVSPEC-122 follow-up, found by adversarial testing). The
  `wont_do` case was added during this same review pass for parity with every
  other deferred-only guard extended to `wont_do`. Advisory only,
  non-promotable (no `E616` counterpart) — a human-reconcile nudge, not a hard
  correctness failure.

### Added

- Added `"wont_do"` `checklist_status` to `schema/16_impl_context.schema.json`,
  alongside a required `wont_do_reason` field (enforced pattern, matching
  `deferred_reason`) (DEVSPEC-122 follow-up). `"wont_do"` means permanently
  cancelled, distinct from `"deferred"` (paused, resumable later). `wont_do`
  items get the same treatment as `deferred` items throughout the pipeline —
  coverage, proof-of-work exemptions, milestone_ref, planned-vs-executed diff,
  spec_ref.id requirement, and milestone phase-position roll-up (kept as a
  distinct state literal in `milestone_state.py` so callers can tell "paused"
  from "cancelled"). This closes the exact trap that forced a real production
  incident: a task had to be deleted rather than marked permanently cancelled
  because no such status existed. Existing artifacts are unaffected (purely
  additive enum value); the only Breaking surface is that a new checklist item
  using checklist_status "wont_do"
  without wont_do_reason will fail validation.

### Fixed

- Fixed E304 `ROADMAP_TASK_UNCOVERED` excluding deferred checklist items from
  counting as coverage for their roadmap task (DEVSPEC-122 follow-up). A checklist
  item with `checklist_status == "deferred"` whose `spec_ref.id` matches a roadmap
  `task_id` previously did not count, making the task look abandoned and forcing
  deletion (rather than deferral) to pass validation — the exact incident that
  triggered this follow-up investigation. Also fixed E304's milestone-status
  fallback branch to skip `"deferred"` milestones alongside `"done"`/`"completed"`.
  Also fixed (found in post-rollout review): E304's task-collection loop
  ignored the new roadmap task-level `status` field entirely, so a task marked
  `status:"deferred"`/`"wont_do"` (with its own `status_reason`, no checklist
  item required) still demanded a checklist item to avoid E304 — defeating the
  point of adding task-level status. Now skips tasks whose own status is
  deferred/wont_do. Purely relaxing: no previously-passing spec is affected.

- Fixed E307 `BEHAVIOR_VALIDATION_PAIRING` excluding deferred checklist items
  when grouping items by `spec_ref.id` to check for a behavior+validation pair
  (DEVSPEC-122 follow-up). A deferred `"validation"` item previously did not
  count toward its spec_ref's pairing requirement, falsely demanding it be
  re-added as active. Purely relaxing: no previously-passing spec is affected.

- Fixed W576 `TASK_EXECUTION_MISSING` never recognizing a roadmap task as
  paused or cancelled (DEVSPEC-122 follow-up). Now skips tasks with status
  `"deferred"`/`"wont_do"` (primary fix), plus a defense-in-depth check for the
  transitional case where the task's own status hasn't been updated yet but
  every checklist item covering it has already been marked deferred/wont_do.
  A task with a mix of deferred and still-active covering items still requires
  execution evidence. Purely relaxing: no previously-passing spec is affected.

- Fixed W568 `UNCOVERED_CAPABILITY` never being exempted by capability-level
  `scope:"out"` (DEVSPEC-122 follow-up) — the capability-level analog of FR
  `priority:"wont-have"`. A permanently excluded capability by design has no FR
  tracing to it; the existing wont-have FR exclusion didn't help since it only
  applies when a wont-have FR exists and traces to the capability. Extended in
  post-rollout review: `scope:"future"` capabilities (acknowledged, deferred to
  a later release) are exempt too, for the same "parked by design" reasoning as
  every other deferred/wont-have/wont-do entity in this rollout. Purely
  relaxing: no previously-passing spec is affected; some previously-failing
  `scope:"future"` artifacts now pass.

- Fixed `matrix.py`'s `fr_coverage` threshold check (`SPECDEV_MATRIX_STRICT=1`)
  having zero exclusion logic for FRs that will never be built (DEVSPEC-122
  follow-up). `priority:"wont-have"` FRs and Step-05 `out_of_scope[]` FRs are
  now excluded from both `fr_total` and the `fr_with_*` numerators, mirroring
  the equivalent exclusions in `traceability_closure.py`. Purely relaxing: no
  previously-passing spec is affected. Refined further in a second fresh-review
  round: `fr_with_fixture` was still sharing `fr_total`/`excluded_fr_ids` with
  the other `fr_with_*` numerators, which never accounted for Step-08's
  independent fixture `out_of_scope[]` set -- silently understating fixture
  coverage for Step-08-exempted FRs. `fr_with_fixture` now has its own
  exclusion set and denominator (`fr_total_fixture`), matching the
  Step-05-vs-Step-08 split already applied in `cli.py` and
  `traceability_closure.py`.

- Fixed `step_11.py`'s W583 `API_UNCOVERED_BY_THREAT` and W615
  `INVARIANT_UNEXERCISED_BY_THREAT` falsely demanding threat coverage for an
  API/invariant whose only tracing FR is `priority:"wont-have"` (DEVSPEC-122
  follow-up). Each API's/invariant's `trace[]` is now walked back to its FR(s);
  exempt only when every traced FR is wont-have. Purely relaxing: no
  previously-passing spec is affected.

- Fixed `cli.py`'s `completeness-check` command computing its own `total_frs`
  and `total_caps` denominators without excluding parked entities (DEVSPEC-122
  follow-up). Refined further in post-rollout review: a single shared
  `total_frs` desynced from the actual uncovered-sets it's divided into, since
  W564/W566 exempt Step-05 `out_of_scope[]` FRs while W565 exempts the
  independent Step-08 `out_of_scope[]` set — `total_frs` now splits into two
  denominators (api/milestone vs. fixture) matching each check's real
  exemption set, on top of the existing `priority:"wont-have"` exclusion
  shared by both. `total_caps` continues to exclude both `scope:"out"` and
  `scope:"future"` capabilities, now consistent by construction: W568
  `UNCOVERED_CAPABILITY` itself was extended in this same review round to
  exempt `scope:"future"` too (see the W568 fix above), so `total_caps`'
  exclusion set matches exactly what W568 actually treats as parked. Purely
  relaxing: no previously-passing spec is affected.

- Fixed `linked_test_expectation` being unconditionally required on every Step 16
  checklist item, including `deferred` ones (DEVSPEC-122). A deferred item's eventual
  test contract isn't always known before work starts, so it is now required only when
  `checklist_status` is `active` (matching the existing exemption pattern for
  `implementation` and `fixture_ref`). Purely relaxing: no previously-passing spec is
  affected; some previously-failing deferred-item artifacts now pass.

- Fixed W565 `UNCOVERED_FR_FIXTURE` never being exempted by any out-of-scope
  declaration, unlike its sibling checks W561/W564/W566 (DEVSPEC-122). Added a new
  `out_of_scope[]` array to `schema/08_fixtures.schema.json` (same shape as
  `05_interface_contracts.json`'s: `fr_id` + `rationale`), and `traceability_closure.py`
  now subtracts FRs listed there from W565's FR set. This is deliberately a separate
  exemption list from Step 05's out_of_scope[] — "no API surface" and "no fixture" are
  independent scoping decisions (e.g. a background job can lack an API but still need a
  fixture), so Step 05's out_of_scope[] does not exempt W565 and vice versa. Purely
  additive: no previously-passing spec is affected.

- Fixed the generated pre-commit hook configuration for macOS and submodule deployments.
  All hook entry points are now invoked via `devspec_env/bin/python` instead of the ambient
  `python`, ensuring the managed venv is always used. The `validate-all` hook has been renamed
  to `spec-check` (matching the current CLI command) and updated to pass `--spec-root ./spec`
  and `--git-root .` so project-canon resolution works correctly. The `seed-lint`,
  `canonical-integrity`, and `prompt-sync` hooks likewise receive `--spec-root`/`--git-root`
  where applicable.

- The generated `devspec-governance` commit-msg hook now sets `pass_filenames: true` (was
  `false`) so pre-commit passes the commit-message file path to `governance-check --message`,
  which previously received no message file.

- The generated host CI workflow (`init_project.py` `_render_ci_workflow`) now runs
  `spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` instead of
  `validate-all`, so project-canon resolves and new host repos no longer emit false E110s in
  CI (matching the pre-commit hook fix).

- Corrected submodule-deployment documentation and prompt-contract examples to pass the
  project-canon flags (`--spec-root ./spec --git-root .`) on spec-validating commands, and
  switched the CI-gates and scaffold prompt examples to `spec-check`. Bare invocations
  previously emitted false E110s when followed in a host repo.

### Changed (documentation)

- Documented the E308 FR-release workflow in `prompt_16_impl_context.md`
  (DEVSPEC-122 follow-up). E308's ownership check correctly treats a deferred
  milestone as still owning every FR/API in its `fr_refs` — but no workflow
  previously existed for how to free an FR from a deferred milestone for
  reassignment. Documented: remove the ID from the deferred milestone's
  `fr_refs` explicitly; there is no automatic release on deferral. Doc-only, no
  code or schema change.

- Documented the `checklist_status` enum (`active`/`deferred`/`wont_do`), the
  mandatory per-item `deferred_reason`/`wont_do_reason` rules, and the roadmap
  task-skip rule (a Step 14 task already marked `deferred`/`wont_do` with its
  own `status_reason` needs no checklist item to satisfy roadmap coverage) in
  `prompt_16a_impl_planner.md` (DEVSPEC-122 follow-up). These contract clauses
  mirror the schema/`step_16.py`/`step_16a.py` guards added earlier in the same
  rollout; the prompt previously gave planners no guidance on when reasons are
  mandatory or when a roadmap task can be skipped. Doc-only, no schema or code
  change.

- Documented that `checklist_status: "wont_do"` is an accepted terminal state in
  `prompt_16b_impl_coder.md` (DEVSPEC-122 follow-up), alongside `deferred` and
  `verified`: a coder discovering mid-implementation that a checklist item is
  permanently unnecessary (not just blocked or postponed) sets
  `checklist_status: "wont_do"` and populates the mandatory `wont_do_reason`
  (mirroring the existing `deferred_reason` requirement for `deferred` items).
  The prompt now explicitly states the no-delete rule: do NOT delete the
  checklist item to work around coverage validation, since deletion loses the
  record that the work was considered and explicitly cancelled. Doc-only, no
  schema or code change.

- Corrected stale E520 message text in `step_16.py` (found in a second
  fresh-review round): the guard already exempted both `deferred` and
  `wont_do` checklist items from the `nfr_refs`/`fixture_ref` proof
  requirement, but the two error messages still said "is not deferred"
  without mentioning `wont_do`. No behavior change — the messages only ever
  fire for genuinely active items either way.

### Removed

- Removed the `/specdev-trinity-plan` skill; its plan-phase functionality is now invoked via
  `/specdev-trinity --phase plan`. Host repos that vendor the toolkit as a git submodule must
  re-run project init (`init_project.py`) after bumping to this version to refresh the now-stale
  `specdev-trinity-plan` skill symlink. No spec-artifact migration is required.

### Added

- Added a new script `.claude/skills/devspec_pr_audit/scripts/p6_verify.py`, which reads
  a `fix_plan.json` and executes each task's `acceptance_command` in topological order,
  reporting PASS/FAIL per task as the post-fix verification gate. Also extended
  `SKILL.md` and `protocol.md` with the `--post-fix` scoped-audit contract
  (DEVSPEC-121). `validate_agent_outputs.py`'s scope is unchanged by this work; it
  continues to validate only the standard P0-P5 pipeline artifacts (`findings.json`,
  `fix_plan.json`, p2/p3 fragments, `manifest.json`).

### Changed

- Added an "Agentified flow note" to `prompts/prompt_16c_impl_reviewer.md` clarifying
  that when the Trinity loop is invoked via `/specdev-trinity --phase review`, the
  anchor/roadmap sync is performed by `.claude/skills/specdev-trinity/SKILL.md`'s
  post-convergence Step C3 (operator gate) -- not by this prompt directly -- whereas
  the standalone (non-agentified) invocation path continues to perform anchor/roadmap
  sync inline per the prompt's own Crucial Side Effect section.

### Internal

- Rewrote 11 `.claude/agents/*.md` agent-contract files across the DEVSPEC-100 fix arc:
  Phase 1 (WI-1..WI-8: `pr-audit-discovery-mechanical`, `pr-audit-discovery-semantic` via
  Wave B1, `specdev-reviewer`, `specdev-scope`, and initial passes on `specdev-impl`,
  `specdev-trinity-reviewer`), Phase 2 (IU-11 `pr-audit-context-author` bin-packing,
  IU-12 `pr-audit-fix-apply` post-fix automation, Wave B1 `pr-audit-context-verifier`),
  Phase 3 (IU-17 `specdev-trinity-impl` `errors_remaining`, IU-18 `pr-audit-cross-boundary`
  p2/-absent meta-finding, IU-20 `specdev-impl` author-extend mode), and follow-up F-1b
  (`specdev-trinity-reviewer` FR-coverage gate fix). Added corresponding test coverage:
  `tests/integration/pr_audit/test_p5_finalize.py`, `test_tier0_checks.py`,
  `test_validate_agent_outputs.py`, and `tests/unit/test_wi8_green_derivation.py`.
- Consolidated the four `checklist_status not in/in ("deferred", "wont_do")` literal-tuple
  checks in `step_16.py` and `step_16a.py` into one shared constant,
  `PAUSED_OR_CANCELLED_CHECKLIST_STATUSES` (DEVSPEC-122 follow-up review pass). No behavior
  change -- full suite green before and after. Found while auditing the `wont_do` rollout
  for DRY: the repeated literal is exactly the kind of site a future third status value
  could silently miss (per the enum-value-rollout-sweep lesson from this same
  investigation).
