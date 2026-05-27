# Migration: Roadmap (Step 14)

## Schema URI

`vc:14-roadmap`

## Required Changes

**Step-base fields (required in every artifact)**

- `id`: Unique kebab-case identifier for this artifact instance (`$ref: vc:core:atoms#kebabId`).
- `owner`: Owner of this spec artifact. Must be one of: `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: ISO 8601 timestamp of when this artifact was generated or last regenerated (`$ref: vc:core:atoms#timestamp`).
- `canonical_refs_used`: array of canonical reference objects used in this artifact

- `$schema`: Must reference the URI above for the target toolkit version.
- `tech_stack`: Object with required keys `languages` and `frameworks` (arrays of strings). Additional optional keys: `databases`, `queues`, `caches`, `infra`, `tools`.
- `milestones`: Array of roadmap milestone objects. Each entry requires:
  - `milestone_id`: kebab-case identifier (e.g., `ms-auth-mvp`).
  - `name`: String — Title Case, 3–6 words describing the deliverable theme.
  - `target_date`: ISO 8601 date string (YYYY-MM-DD).
  - `user_story`: String following `As a <role>, I want <goal>, so that <benefit>` format.
  - `source_milestones`: Array of Step 09 `milestone_id` strings this roadmap milestone maps to.
  - `tasks`: Array of task objects (minItems: 1). Each task requires `task_id` (kebab-case) and `description` (string, ≥2 words).
  - `deliverables`: Array of trace reference objects (minItems: 1) — typed `traceRef` objects, not bare strings.
  - `fr_refs`: Array of `fr-*` ID strings referencing functional requirements this milestone delivers.
  - `capability_refs`: Array of `cap-*` ID strings from Step 01 this milestone implements.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `tech_stack_ref`: Canonical reference (kind: `capability`) for the tech stack registry entry.
- `milestones[].status`: Must be one of `pending | in_progress | done | deferred`.
- `milestones[].risk_status`: Must be one of `low | medium | high | critical`.
- `milestones[].tasks[].acceptance_criteria`: Array of criterion objects (minItems: 1), each requiring `criterion_id` and `text` (minLength: 15).
- `milestones[].tasks[].status`: Must be one of `pending | in_progress | done`.
- `milestones[].tasks[].depends_on`: Array of `task_id` strings within the same milestone.
- `milestones[].tasks[].fr_refs`: Array of `fr-*` ID strings this task addresses.
- `milestones[].risks`: Array of named risk strings.
- `milestones[].spikes`: Array of time-boxed investigation strings.
- `milestones[].status_ref`: Canonical reference (kind: `stage`) for milestone status.
- `migration_plan`: String (minLength: 1) describing migration strategy.
- `dependencies`: Array of structured dependency objects.
- `dependency_ref`: Canonical reference (kind: `dependency`) for the primary external dependency.
- `trace`: Array of trace reference objects at the document level.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh validate spec/14_roadmap.json --repo-root ./devspec_toolkit
```

## Context

The roadmap now requires `tech_stack` (with `languages` and `frameworks` required)
at the top level. The `milestone_id` field (not `id`) must be used. Each milestone
now requires `user_story`, `source_milestones`, `tasks`, `deliverables`, `fr_refs`,
and `capability_refs` — populate these from the existing milestone descriptions.
The `status` default for new milestones should be `pending`. Tasks within each
milestone require `task_id` and `description`; convert any free-text task lists
into structured objects. Deliverables must be typed `traceRef` objects — convert
any bare string deliverables. Verify all `fr_refs` and `capability_refs` still
point to valid IDs from Steps 04 and 01 respectively.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_14_roadmap.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
