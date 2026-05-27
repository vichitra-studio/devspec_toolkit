# Migration: Implementation Coder (Step 16b)

## Schema URI

`vc:16-impl-context`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `execution.execution_results`: Array — one entry per command run. Each entry requires `status` (one of `passed`, `failed`, `blocked`, `partial`), `outcome_description`, `reasoning`, `command`, and `evidence` (string, minLength: 20). When `status == "passed"`, `evidence_ref` and `evidence_binding` are also required.
- `plan.spec_alignment.checklist[].implementation.status`: Updated to `in_progress` or `verified` per item.
- `plan.spec_alignment.checklist[].implementation.actions[].evidence`: Structured `{ type, content }` evidence object for every action on a `verified` checklist item.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to `vc:16-impl-context`.
- `id`: Kebab-case identifier for this artifact.
- `owner`: One of the allowed owner enum values.
- `created_at`: ISO 8601 timestamp.
- `canonical_refs_used`: Array of canonical reference objects (e.g. `[{ "id": "cn:core:unit:ms", "kind": "unit" }]`).
- `plan`: Object with at minimum `status` populated.
- `execution`: Populated object — include at minimum `execution_results`.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `execution.files_touched`: Every file modified; should be a subset of `plan.summary.target_file_patterns`.
- `execution.critical_evidence.satisfied_checklist_ids`: Checklist IDs fully implemented and verified.
- `execution.critical_evidence.passed_test_commands`: Specific test commands that passed.
- `execution.emergent_ambiguities`: Blockers or spec issues discovered during execution; each requires `id`, `description`, and `severity`.
- `execution.config_validation`: Validation results for delivery, drift, or security configs.
- `execution.final_status`: Final CI status and test result summary.
- `extensions`: Structured data that does not fit in core schema fields.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/16_impl_context.json --repo-root ./devspec_toolkit
```

## Context

Step 16b is the Coding phase of the Trinity Loop. It executes the plan defined in Step 16a and
records evidence for every action. During migration, verify that `execution.files_touched` is a
strict subset of `plan.summary.target_file_patterns` — any file outside that set should be flagged
as an `emergent_ambiguity` rather than silently included. Every `execution_results` entry must
contain concrete `evidence` content with at least 20 characters describing the actual outcome.
If the previous artifact used paraphrased test output or missing evidence, replace with captured
output describing the observable result. When `execution_results[].status == "passed"`, the schema
also requires `evidence_ref` and `evidence_binding` (`timestamp`, `sha256`, `exit_code`).
The `plan` section must not be modified outside `plan.spec_alignment.checklist[].implementation`
evidence and status updates. Documentation impact guidance belongs in `plan.docs_impact`
(`status` and `rationale` required; `docs_touched` with minItems:1 required when `status == "required"`).

## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_16b_impl_coder.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
