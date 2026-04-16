# Migration: Implementation Context (Step 16, post-split)

## Schema URIs

The pre-split `spec/16_impl_context.json` (single artifact using
`vc:16-impl-context`) has been split into **two** distinct artifact types. A
host repo upgrading from an earlier version must produce BOTH:

1. **Trinity Anchor** — `spec/16_impl_context.json` — `vc:16-anchor`
2. **Milestone Plans** — `spec/impl_context/<milestone>_plan.json` — `vc:16-impl-context`

## Required Changes

**Step-base fields (required in every artifact — both anchor and milestone plans)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: One of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: Array of canonical reference objects.
- `$schema`: `vc:16-anchor` for the anchor; `vc:16-impl-context` for milestone plans.

### Trinity Anchor (`vc:16-anchor`) — `spec/16_impl_context.json`

Required fields beyond step-base:

- `artifact_role`: **Must be the literal string `"anchor"`** (JSON Schema `const`).
- `plan.summary`: Object with `functional_summary`, `scope_in`, `scope_out`, `target_file_patterns`.
- `plan.ambiguities`: Array of unresolved decisions carried across Trinity cycles. Each item requires `id`, `description`, `severity` (`low | medium | high | critical` — the anchor uses `severityLevel`, not the milestone-plan `blocking | non_blocking`). Empty array is valid.
- `plan.drift.checks`: Array of cross-cycle drift-check strings.
- `plan.milestone_index`: Array registering each active/pending/done/deferred milestone. Each entry requires `milestone_id`, `context_path` (pointing at the 16a plan file under `spec/impl_context/`), `status`, `fr_refs`, `checklist_id_prefix`, `summary`.

The anchor schema **forbids** `execution`, `review`, top-level `milestone_ref`, and `plan.spec_alignment.checklist` via `unevaluatedProperties: false`. All per-milestone detail lives in the corresponding milestone plan file.

### Milestone Plans (`vc:16-impl-context`) — `spec/impl_context/<milestone>_plan.json`

One file per milestone (shared across 16a plan / 16b execution / 16c review). Required beyond step-base:

- `plan.status`: `active | deferred`.
- `plan.summary`: Same structure as the anchor but scoped to this milestone.
- `plan.spec_alignment.checklist`: Array of checklist items. Each item id **MUST be prefixed with the `checklist_id_prefix` declared for this milestone in the anchor's `milestone_index[]`** (e.g. prefix `AUTH` → `AUTH_LOGIN_01`). Two milestones sharing a prefix trigger E309 ANCHOR_CHECKLIST_DRIFT.
- Non-deferred checklist items also require `implementation` (with `status` and `actions`), `nfr_refs`, and `fixture_ref` for behavioural types.
- `plan.review_requirements.test_commands`: Array with `minItems: 1` when `status == "active"`.

Optional sections (populated as the Trinity Loop progresses):

- `execution`: Files touched, execution results, critical evidence (written by 16b).
- `review`: Findings, ratings, verdict, next actions (written by 16c).
- `plan.ambiguities`: Planning-phase ambiguities, `severity` uses `blocking | non_blocking` (distinct from the anchor's `severityLevel` enum).

## Migration Steps

Applying the split to an existing host repo:

1. **Preserve the legacy artifact**: copy `spec/16_impl_context.json` to `spec/impl_context/<milestone_id>_plan.json` (for whichever milestone the original content belonged to). Leave `$schema` as `vc:16-impl-context`. Drop `artifact_role` if present.
2. **Rewrite `spec/16_impl_context.json` against the anchor contract**: see `prompts/prompt_16_impl_context.md` and `schema/16_anchor.schema.json`. The new file carries only `artifact_role: "anchor"`, `plan.summary`, `plan.ambiguities`, `plan.drift.checks`, and `plan.milestone_index`.
3. **Use the shared milestone status enum**: `milestone_index[].status` is one of `pending | in_progress | done | deferred` (from `vc:core:atoms#milestoneStatus`). Earlier drafts used `active | planned` — those values are now schema-rejected.
4. **Derive `checklist_id_prefix` per milestone**: allocate a unique SCREAMING_SNAKE prefix (e.g. `AUTH`, `PAYMENT`). Ensure it does not collide with other milestones' prefixes. Update each 16a plan's checklist ids to use this prefix.
5. **Validate**:

   ```bash
   ./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
   ./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit
   ```

   `spec-check` surfaces any new E308 (scope/FR-ownership conflict), E309 (checklist ID drift), W587 (stale drift checks), W588 (unreadable milestone), and W589 (mis-schemaed milestone) signals introduced by the split.

## Optional Fields (milestone plan only)

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `plan.solution.architecture_sketch`: Free-form description of the solution approach.
- `plan.context.existing_structures` / `plan.context.coding_examples`: Grounding references into the current codebase.
- `plan.review_requirements.guidelines`, `plan.review_requirements.nfr_measurement_methods`, `plan.review_requirements.timeout_constants`.
- `plan.security`, `plan.docs`, `plan.delivery`: each either `{status: not_applicable, reason}` or `{status: planned, …}`.
- `plan.coverage_status`: Integer counts of `total`, `verified`, `deferred`, `pending` checklist items.
- `extensions.review_state` / `extensions.execution_context`.

## Context

Before the split, `spec/16_impl_context.json` tried to serve two purposes: a scope/ownership declaration spanning all milestones AND the per-milestone implementation contract for the active Trinity cycle. Validating both through one schema meant the anchor paid the milestone-plan validation cost (forced per-task behavior+validation pairs, hollow stub items, ~130 item bloat on a real host repo). The split gives each artifact its own contract, its own validator, and its own authoring prompt.

New error/warning codes introduced by the split:

- **E308** ANCHOR_SCOPE_DRIFT — scope contradiction (bidirectional) or FR/API ownership conflict between in-flight milestones.
- **E309** ANCHOR_CHECKLIST_DRIFT — cross-milestone checklist ID collision or duplicate `checklist_id_prefix`.
- **W585** ANCHOR_DRIFT_SKIP — drift check skipped (usually routing-related).
- **W586** ANCHOR_VALIDATOR_WRONG_ARTIFACT — anchor validator invoked on a non-anchor artifact.
- **W587** ANCHOR_DRIFT_CHECKS_STALE — `milestone_index` non-empty but `drift.checks` empty.
- **W588** ANCHOR_MILESTONE_UNREADABLE — a milestone plan file could not be parsed.
- **W589** ANCHOR_MILESTONE_MISSCHEMAED — file under `impl_context/` declares the wrong `$schema`.

## Full Generation Reference

To generate these artifacts from scratch (rather than migrate an existing one), use the canonical step prompts:

- **Anchor**: `prompts/prompt_16_impl_context.md`
- **Milestone plan (16a)**: `prompts/prompt_16a_impl_planner.md`
- **Milestone execution (16b)**: `prompts/prompt_16b_impl_coder.md`
- **Milestone review (16c)**: `prompts/prompt_16c_impl_reviewer.md`

Each generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
