# Migration: Implementation Reviewer (Step 16c)

## Schema URI

`vc:16-impl-context`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `review.ratings`: Object with integer scores (0–5) for `spec_completeness`, `code_quality`, `tests_completeness`, `docs_completeness`, and `metadata_usage`.
- `review.findings`: Array of structured finding objects; each requires `id`, `type` (one of `bug`, `gap`, `scope_creep`, `style`, `design`, `tests`, `docs`), `severity` (one of `blocking`, `major`, `minor`, `nit`), `spec_ref`, `description` (≥40 chars naming file:line, impact, and violated requirement), and `metadata` (with `source` and `impact`). When `severity` is `blocking` or `major`, `remediation_task` is also required.
- `review.verdict`: One of `verified`, `needs_work`, `blocked`, or `deferred`.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to `vc:16-impl-context`.
- `id`: Kebab-case identifier for this artifact.
- `owner`: One of the allowed owner enum values.
- `created_at`: ISO 8601 timestamp.
- `canonical_refs_used`: Array of canonical reference objects (e.g. `[{ "id": "cn:core:unit:ms", "kind": "unit" }]`).
- `plan`: Object with at minimum `status` populated.
- `review`: Populated object with at minimum `findings`, `ratings`, and `verdict`.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `review.fixture_status`: Required by the schema when `review.verdict == "verified"`. Object with `implemented_interfaces`, `test_results` (each entry requires `fixture_ref` and `status`), and `ci_status` (`green` or `red`). When `verdict == "verified"`, `ci_status` must be `"green"`.
- `review.semantic_review`: Required by the schema when `review.verdict == "verified"`. Object with `fr_coverage` (array — each entry requires `fr_id`, `satisfied`, `evidence_summary`, and `checklist_ids`) and `hallucinated_features` (array — use `[]` to assert none). Include `scope_delta` when unplanned features are detected.
- `review.security_status`: Security gate result (`green` or `red`).
- `review.delivery_status`: Deployment status with `deployments` array.
- `review.next_actions`: Concrete follow-up actions (name the responsible party and prerequisite condition).
- `extensions`: Structured data that does not fit in core schema fields.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

Step 16c is the Review phase of the Trinity Loop. It audits the implementation against the plan
and spec, closing the cycle or spawning remediation tasks. During migration, ensure `review.verdict`
reflects the actual evidence state: `verified` is forbidden if any `blocking` finding exists or
any active checklist item lacks evidence. When `verdict == "verified"`, the schema additionally
requires `review.fixture_status` (with `ci_status == "green"`) and `review.semantic_review`
(with `fr_coverage` and `hallucinated_features`). The `fr_coverage` array must include an entry
for every FR referenced in the active milestone's `fr_refs` — no FR may be silently omitted.
If the previous artifact approved implementation without concrete evidence content, downgrade
the verdict and add findings. When `verdict` is `verified`, also update `spec/14_roadmap.json`
and `spec/09_impl_plan.json` to set the corresponding milestone status to `done`.

## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_16c_impl_reviewer.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
