# Migration: CI Gates (Step 12)

## Schema URI

`vc:12-ci-gates`

## Required Changes

- `$schema`: Must reference the URI above for the target toolkit version.
- `jobs`: Array of CI job objects; each needs `job_id`, `name`, `steps`, and `environment_ref`.
- `job_id` format: Must be kebab-case (e.g., `job-lint-and-test`).
- `jobs[].steps`: Array of step objects; each requires `id`, `name`, and `command`.
- `jobs[].environment_ref`: Required canonical reference for the deployment environment.
- `jobs[].steps[].id` format: Must be kebab-case.
- `coverage_thresholds`: If present, `lines` and `branches` must be numbers in the range 0–100.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.
- `canonical_proposals`: Array (OPTIONAL).
- `canonical_conflicts`: Array (OPTIONAL).

## Optional Fields

- `_migration_notes`: String describing what changed during migration.
- `coverage_thresholds`: Object with `lines` and/or `branches` thresholds.
- `jobs[].requires`: Array of kebab-case job IDs that must pass before this job runs.
- `jobs[].role_ref`: Canonical reference to the role responsible for this job.
- `jobs[].security`: Object containing `runner_labels`, `token_permissions`, and/or `environment_protection`.
- `jobs[].steps[].command_ref`: Canonical reference for the command.
- `trace`: Array of trace refs for top-level provenance.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/12_ci_gates.json --repo-root ./devspec_toolkit
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
