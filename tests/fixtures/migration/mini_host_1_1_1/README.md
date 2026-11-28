# mini_host_1_1_1

A small, invented host as toolkit 1.1.1 left it: "Lantern Lending", a neighbourhood tool library (catalog search,
reservations, desk checkout and return, late fees). Nothing here comes from a real host.

A test copies this folder into `tmp_path`, deletes this `README.md`, makes the copy a git repository and runs the
migration on it. It is the one fixture that WI-M10-03 to 09, 15 and 17 test on (ruling P11): later bundles only ADD
files or subfolders to it, never rewrite one of these files.

The shapes were checked against the REAL 1.1.1 toolkit (`git archive v1.1.1`): `spec-check` on a copy is clean except
the findings listed under "1.1.1 run" below. Every shape is a 1.1.1 shape that the 1.2.0 schemas removed or changed;
the deliberate ones (collisions, status conflicts) are listed there.

## Files

| File | Legacy shape it carries | Needed by (M10 work item) |
|---|---|---|
| `spec/specdev_version` | host-form YAML, `toolkit_version: 1.1.1`, `migration_history: []` | 01, 10, 12 |
| `spec/00_charter.json` | string lists `in_scope`, `out_of_scope`, `assumptions`, `risks`; stakeholders without an id (`role`, `needs[]`); `links`, `seed_refs_ingested`; one non-ASCII text | 04, 05, 06 |
| `spec/01_capabilities.json` | `goal_id`, `success_metric_refs`, `trace`; `scope: future` | 04, 05 |
| `spec/02_system_sketch.json` | `type: external` component with tag `external-dependency`; `tech_stack`; connections with `from`/`to`/`trace`, `schema_ref`, `interface_ref`; `spec_refs_ingested` | 05, 06 |
| `spec/02a_delivery_baseline.json` | `ci_gates` and `secrets` as strings; environments with host keys that have no node field (`lifecycle`, `ghost_port`, `log_level`); staging with `lifecycle: decommissioned-at-production-go-live`; `trace` | 04, 05, 08 |
| `spec/03_glossary.json` | glossary terms with `term_ref` and `canonical_proposals[].temp_id` | 04 |
| `spec/04_fr_list.json` | criteria `ac-*` (two of them minted again in 14), `trace`, a `wont-have` FR, `spec_refs_ingested`, `seed_refs_ingested` | 04, 05, 09 |
| `spec/05_interface_contracts.json` | errors without an id, `example_refs`, `trace`, `out_of_scope`, a `DELETE` method | 04, 05, 09 |
| `spec/06_invariants.json` | `rules[].scope` as `{components, apis}`, `rules[].trace` | 05 |
| `spec/07_nfrs.json` | stages `dev`, `staging`, `prod`; `trace` to FR, API and invariant; one NFR with a fixture, three without | 05, 06 |
| `spec/08_fixtures.json` | `targets` at FRs, APIs, an invariant and an NFR; `out_of_scope`; indent 2 | 05, 09, 17 |
| `spec/09_impl_plan.json` | `milestones[].status`, `deliverables`, `depends_on`; `tech_stack`, `tech_stack_ref`; typed `external` dependency, `dependency_ref`; a stray `ms-*` milestone id that 14 also defines | 04, 05, 06, 08 |
| `spec/10_governance.json` | `pr_rules` strings (`validate-all`, `matrix`, a known command, unknown names), `review_policy`, `reviewers`, `spec_first_policy`, `links`; hand-formatted (the `pr_rules` array on one line) | 05, 06 |
| `spec/11_redteam.json` | `target_ids`, `mitigations` (one by capability), `trace`; edge cases | 05 |
| `spec/12_ci_gates.json` | `requires`, job step ids, a mixed job (smoke check next to staging delete and a production migration) | 05, 06 |
| `spec/13_extension_manifest.json` | none-required decision (the 1.1.1 step-13 form) | 15 |
| `spec/13a_completeness_assessment.json` | the retired step 13a file | 05 |
| `spec/14_roadmap.json` | tasks with `fr_refs`, `invariant_refs`, `depends_on`, `status`, `status_reason`, `exit_conditions`, `assumptions`, criterion `fixture_ref`; milestone `status`, `milestone_status_reason`, `source_milestones`, `fr_refs`, `capability_refs`, `deliverables`; `tech_stack`, `dependencies`; criteria `ac-catalog-search-1` and `ac-reserve-tool-1` defined again with other text; a done task in a pending milestone, a pending task in a done milestone | 03, 04, 05, 06, 08, 09 |
| `spec/15_scaffold.json` | `interface_map[].interface_ref` and `method`, `trace`, `links`; NO trailing newline | 05, 15 |
| `spec/16_impl_context.json` | the 1.1.1 anchor: rows with `milestone_id`, `context_path`, `fr_refs`; two open items (one id also in plan B); a row that disagrees with 14; prose mention of `status_ref` | 03, 04, 06, 08 |
| `spec/impl_context/ms_catalog_plan.json` | legacy-closed plan (14 `done`, anchor `done`, verdict `verified`), batch stem differs from the milestone id, no `milestone` key; every removed plan field; `checklist_status` deferred and wont_do; backticked ids in descriptions | 03, 04, 05, 06, 08, 17 |
| `spec/impl_context/ms_reservations_plan.json` | OPEN plan: `ambiguities[]` and `emergent_ambiguities[]` in `resolved`, `tracking`, `deferred`; one id in both lists; items `pending`, `deferred`, `wont_do`; `linked_test_expectation` as command and as prose | 03, 04, 06, 08, 17 |
| `spec/impl_context/ms_late_fees_plan.json` | plan whose milestone 14 calls `done` while the anchor row says `pending` (status conflict), no verdict; emergent item shared with plan B | 04, 06, 08 |
| `spec/common/seed_manifest.json` | seed paths relative to the REPOSITORY root; a decisions seed; a seed no step routes | 05, 08 |
| `spec/canon/manifest.json` | project canon manifest with the retired kinds `interface` and `dependency`, the kind `inv`, `command` and `role` entries | 05 |
| `spec/canon/kinds/capability.json`, `command.json`, `dependency.json`, `interface.json`, `inv.json`, `role.json`, `tech_stack.json`, `term.json` | project canon kind files (`interface.json` and `dependency.json` are retired kinds, `inv.json` holds kind `inv`) | 05 |
| `spec/extras/trace_matrix.json` | the stored trace matrix that 1.2.0 retires, tracked | 05 |
| `variants/status_ref_1_0_x/04_fr_list.json` | live `status_ref` objects as 1.0.x wrote them (valid under toolkit 1.0.0, not under 1.1.1); NOT part of `spec/` | 01 |
| `variants/criterion_text_names_removed_field.json` | an edit list (M10-15a): a step-14 criterion TEXT that names the removed field `exit_conditions`; applied to a copy of the host by `tests/e2e/host_migration/test_mini_host.py`; NOT part of `spec/` | 15 |
| `variants/sentence_dependencies.json` | an edit list (M10-15a): step-09 `dependencies` written as sentences, as both real 1.1.1 hosts wrote them; NOT part of `spec/` | 15 |
| `docs/seed/seed_lending_overview.md`, `seed_hosting_plan.md`, `seed_decision_clarifications.md`, `seed_volunteer_roster.md` | seed documents of the manifest | 05, 08 |
| `schemas/lending.json`, `catalog.json`, `sms.json` | files named by connection `schema_ref` | 05 |
| `scripts/check_desk_flow.sh`, `scripts/check_fees.sh` | commands named by `linked_test_expectation` | 17 |
| `tests/catalog.spec.ts`, `tests/fee.spec.ts`, `tests/import.spec.ts` | test files named by `linked_test_expectation` | 17 |
| `.pre-commit-config.yaml` | a host hook that calls `specdev spec-check` | 11 |
| `.github/workflows/spec_validation.yml` | retired commands `validate-all` and `matrix` in a workflow | 11 |

## Shapes

One row per shape the fixture claims; `tests/unit/migration/test_mini_host_fixture.py` asserts each by id.

| Id | Shape |
|---|---|
| F01 | fields the 1.2.0 schemas removed, one instance each (the paths are listed in the test and under "Removed-field rows" below) |
| F02 | stored computed fields (the E768 names): plan-item `milestone_ref`, `nfr_refs`, `fixture_ref`; `fr_refs`, `capability_refs`, `invariant_refs`, `deliverables`, `source_milestones` on 14; anchor `fr_refs` |
| F03 | `status_ref` only as prose in the host and as live objects in `variants/status_ref_1_0_x/` |
| F04 | collision: criterion `ac-catalog-search-1` defined in 04 and again in 14 with other text |
| F05 | collision: criterion `ac-reserve-tool-1` defined in 04 and again in 14 with other text |
| F06 | collision: milestone `ms-late-fees` defined in 09 and in 14 |
| F07 | a referrer whose field fixes the kind: plan items `milestone_ref: ms-late-fees` and the anchor row `milestone_id: ms-late-fees` |
| F08 | a referrer whose field does not fix the kind: backticked `ac-catalog-search-1` and `ac-reserve-tool-1` in plan item descriptions |
| F09 | items without ids: charter lists and stakeholders, 02a `ci_gates` and `secrets`, 05 errors, 10 `pr_rules` |
| F10 | 14 tasks with `fr_refs`, `invariant_refs`, `depends_on` and a `status_reason` |
| F11 | plan B carries `ambiguities[]` and `emergent_ambiguities[]` in `resolved`, `tracking` and `deferred` |
| F12 | one id in two lists: `amb-sms-retry` (plan B, both lists), `amb-fee-rounding` (anchor and plan B), `amb-pickup-hours` (plans B and C) |
| F13 | `linked_test_expectation` as a command string, as prose and as a list |
| F14 | plan actions without ids |
| F15 | anchor with open items and a status conflict: `ms-late-fees` is `done` in 14, `pending` in the anchor and in 09; a `done` task inside the `pending` milestone `ms-reservations`; a `pending` task inside the `done` milestone `ms-catalog-basics` |
| F16 | NFR stages `dev`, `staging` and `prod` |
| F17 | third-party mentions: `external` component with tag `external-dependency`, `tech_stack` in 02, 09 and 14 (a non-semver version `Built-in`, a version that differs between 02 and 09/14), typed `external` dependency in 09 and 14 |
| F18 | assumptions in the legacy form: charter strings and 14 task `assumptions` |
| F19 | prose ids in backticks: one that resolves (`fr-catalog-search`) and one that does not (`fr-catalog-wishlist`) |
| F20 | file styles: most files indent 4, non-ASCII kept, trailing newline; `08_fixtures.json` indent 2; `10_governance.json` hand-formatted; `15_scaffold.json` without a trailing newline |
| F21 | seed manifest paths resolve from the repository root; a decisions seed; a seed that no step routes |
| F22 | `spec/specdev_version` is YAML with `toolkit_version: 1.1.1` |
| F23 | project canon with retired kind files `interface.json` and `dependency.json`, and the kind `inv` |
| F24 | retired files: `13a_completeness_assessment.json` and `extras/trace_matrix.json` |
| F25 | three plans: one open (pending), one legacy-closed by verdict, status and anchor, one closed by the 14 status alone |
| F26 | a mixed job in step 12 (a smoke check next to a staging teardown and a production migration) |
| F27 | `pr_rules` names: `validate-all`, `matrix`, a toolkit command (`fixtures-lint`, `governance-check`), names that are no toolkit command (`test`, `lint`) |
| F28 | closed-plan fields M8 and M3 removed: `execution_results` with `evidence_binding`, `critical_evidence`, `final_status`, `review.fixture_status`, `semantic_review.fr_coverage`, `security.spec_mutations`, `new_fixtures`, `extensions.review_state`, `spec_ref.line_range` and `commit_hash` |
| F29 | item dispositions `deferred` and `wont_do` with reasons, in the open plan and in a closed plan |
| F30 | 02a environment host keys with no node field, and the staging environment with `lifecycle: decommissioned-at-production-go-live` |
| F31 | a 05 API with method `DELETE` |
| F32 | host files with retired commands (a workflow) and a pre-commit hook |
| F33 | fixtures: FR targets, two fixtures that share one command (`npm test -- reservations`), a fixture no plan item names, an NFR with a fixture and NFRs without |
| F34 | 14 criteria `fixture_ref` and `exit_conditions` |
| F35 | legacy anchor rows (`milestone_id`, `context_path`) and plan file names whose stem differs from the milestone id (`ms_catalog_plan.json`), no plan carries the `milestone` key |
| F36 | threat mitigation by capability type |

### Removed-field rows (kind `remove` of `tools/schema_changes.json`)

Covered: 97 of the 147 `remove` rows (96 by key path, listed as `COVERED_PATHS` in the test, plus step 13a by the file itself). The `change` rows are covered by
F09 (string lists), F17 (`external`), F11 and F12 (ambiguity shapes), 01 `scope: future`, 04 `wont-have`; `add` rows
cannot occur in a 1.1.1 host.

## 1.1.1 run

```
cd <git copy of tk 1.1.1 from `git archive v1.1.1`>
PYTHONPATH="$PWD/tools" python -m specdev_tools.cli spec-check <copy>/spec --repo-root . --spec-root <copy>/spec --git-root <copy>
```

`spec-check: 14 checks run, 1 errors, 12 warnings`, all that remains:

| Code | Count | Why it stays |
|---|---|---|
| E520 | 1 | `UNRESOLVED_INPUT` on `connections[0].schema_ref` (`file://schemas/lending.json`): the 1.1.1 schema demands the `file://` form and the 1.1.1 lint wants a defined id; no value satisfies both. Kept to carry the removed field |
| W594 | 4 | content-derivation overlap is low in four small invented files |
| W614 | 7 | `UNREGISTERED_ARRAY` for `seed_refs_ingested`, `spec_refs_ingested` and `dependencies`: the 1.1.1 registry does not list them |
| W576 | 1 | `TASK_EXECUTION_MISSING` for `task-reserve-endpoint`: the open plan has not executed it yet |

The deliberate collisions (F04 to F06, F12) and conflicts (F15) are NOT findings in 1.1.1: no 1.1.1 check looks for them.

## Today's run (the "before")

```
specdev spec-check <git copy>/spec --repo-root <toolkit> --spec-root <copy>/spec --git-root <copy>
```

Live tree at HEAD `f62a401` plus the uncommitted files of the M10 wave: `spec-check: 27 checks run, 558 errors, 26 warnings`.

| Code | Count | | Code | Count |
|---|---|---|---|---|
| E520 | 343 | | W583 | 6 |
| E740 | 53 | | W594 | 4 |
| E743 | 25 | | W608 | 3 |
| E768 | 63 | | W611 | 1 |
| E752 | 35 | | W614 | 8 |
| E742 | 11 | | W630 | 4 |
| E566 | 6 | | | |
| E704 | 6 | | | |
| E622 | 5 | | | |
| E761 | 5 | | | |
| E748 | 4 | | | |
| E590 | 1 | | | |
| E747 | 1 | | | |

The six E704 are the three collisions (F04 to F06) and the three duplicated ambiguity ids (F12).

## Not covered

Rows of `tools/schema_changes.json` and pack shapes that the fixture does not carry, with the reason:

| What | Reason |
|---|---|
| `spec_refs_ingested` on 01, 02a, 03, 06 to 13, 15, 16; `seed_refs_ingested` on 01 to 03, 05 to 13, 15, 16 (rows SC-xx-01 and SC-xx-02 of those steps) | the same step-base field on every step; carried on 00, 02, 04 and 14 only (each carried field costs a 1.1.1 W614) |
| SC-16_impl_context-07 `plan.deferred_reason` | needs a plan whose `plan.status` is `deferred`; no plan of this host is deferred (item-level `deferred_reason` is covered) |
| SC-02a-02 `environments{}{}` | present as the host keys of F30; the row's path form is not a key path |
| stored `content_hash` and `chain_stamp` (P5/E768 names) | the 1.1.1 schemas have no property for them (`additionalProperties: false`); a 1.1.1 host cannot carry them |
| live `status_ref` inside `spec/` | rejected by the 1.1.1 schemas (E520); carried in `variants/status_ref_1_0_x/` and as prose |
| rows `SC-core-*` and `$defs.*` | definitions inside `schema/core`, not host content |
| rows of kind `add` | additions of 1.2.0; a 1.1.1 host cannot carry them |
| host declarations (pin sources, tag pattern, code-tree exclusions) and git tags | WI-11 builds them in its own test copy; this folder holds no `.git` |
| a seed routed to a trinity step (`step_requirements` key at or after 16) | the 1.1.1 manifest schema accepts it, but both real hosts have none; WI-08's test adds the key in its own copy |
| a plan with an executed item in an OPEN plan | no real host has one; plan B has none |
| `Handlebars`-style duplicate third-party slugs | the pack names them as hosts' data; a duplicate would add a 1.1.1 finding; F17 carries the version-differs and non-semver cases |
