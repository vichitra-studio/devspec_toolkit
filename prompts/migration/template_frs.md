<!-- Migration template for {{project_name}} — specdev v{{spec_version}} — step {{step_id}} -->
# Migration: Functional Requirements (Step 04)

## Schema URI

`vc:04-fr-list`

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `fr-list-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `functional_requirements`: Array of FR objects (minItems: 2). Each entry requires:
  - `fr_id`: kebab-case identifier with `fr-` prefix (e.g., `fr-user-login`).
  - `statement`: String (minLength: 20) — falsifiable statement of a single system behavior.
  - `acceptance_criteria`: Array of criterion objects (minItems: 2). Each requires `criterion_id` (kebab-case) and `text` (string, minLength: 15).
  - `trace`: Array of trace reference objects (minItems: 1) — each requires `type` and `id`; at least one must use `type: implements` pointing to a `cap-*` ID.
  - `capability_ref`: Canonical reference object (kind: `capability`) — required on every FR.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `functional_requirements[].rationale`: String explaining the business or technical justification.
- `functional_requirements[].priority`: MoSCoW enum — `must-have | should-have | could-have | wont-have`.
- `functional_requirements[].preconditions`: Array of strings — state conditions before execution.
- `functional_requirements[].postconditions`: Array of strings — state conditions after execution.
- `functional_requirements[].action_ref`: Canonical reference (kind: `action`) for the primary verb.
- `functional_requirements[].entity_ref`: Canonical reference (kind: `entity`) for the primary domain entity.

## Validation

After migration, run:

```bash
./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
```

## Context

Functional requirements are the primary traceability anchor. FR IDs appear in
interface contracts (Step 05), fixtures (Step 08), the trace matrix, and roadmap
tasks (Step 14). Never rename an `fr_id` without updating all downstream
references. The field is `functional_requirements` (not `requirements`) — rename
accordingly. Each FR requires a `capability_ref` canonical object and a `trace`
array; FRs without these will fail canonical-integrity checks. The
`acceptance_criteria` field requires structured objects (`criterion_id` + `text`),
not plain strings — convert any string-format criteria. The trace matrix must
be regenerated after migration.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_04_functional_requirements.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
