# Migration: CI Gates (Step 12)

## Schema URI

`vc:12-ci-gates`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `jobs`: Array of CI job objects (minItems: 1). Each entry requires:
  - `job_id`: kebab-case identifier (e.g., `gate-build-unit-tests`).
  - `name`: Human-readable Title Case display name (e.g., `Unit Tests`).
  - `steps`: Array of step objects (minItems: 1). Each step requires `id` (kebab-case), `name` (string), and `command` (string).
  - `environment_ref`: Canonical reference object (kind: `environment`) — required (e.g., `{id: "cn:core:environment:ci", kind: "environment"}`).

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `coverage_thresholds`: Object with `lines` and/or `branches` thresholds.
- `jobs[].requires`: Array of kebab-case job IDs that must pass before this job runs.
- `jobs[].role_ref`: Canonical reference to the role responsible for this job.
- `jobs[].security`: Object containing `runner_labels`, `token_permissions`, and/or `environment_protection`.
- `jobs[].steps[].command_ref`: Canonical reference for the command.
- `trace`: Array of trace refs for top-level provenance.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

CI gates define the automated quality pipeline that every change must pass. The
`jobs` array encodes the DAG of CI steps; `requires` on each job establishes
execution order — validate that no cycles are introduced. The `environment_ref`
on each job must resolve to a valid entry in the canonical environments registry.
During migration, check whether `security` fields have been added to the schema
since the source version; populate `runner_labels` and `token_permissions` as
appropriate for the target environment. Coverage thresholds enforced here tie
directly to NFR targets defined in Step 07, so keep them consistent.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_12_ci_gates.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
