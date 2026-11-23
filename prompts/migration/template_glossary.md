<!-- Migration template: step {{STEP_ID}}, {{SOURCE_VERSION}} to {{TARGET_VERSION}} -->
# Migration: Glossary (Step 03)

## Schema URI

`vc:03-glossary`

## Judgement pass

`specdev align apply spec --auto` has run and been committed. What it could not decide is a worklist item. This pass settles the items of step 03, clears the step's baseline entries and ends with the step's check. Do it after the steps above 03 have passed. `blocking` on an item is a display hint; nothing gates on it.

### Items of step 03

No script or proposer writes an item of its own for step 03; the items below and the step's check are the pass.

### Items any step can carry

| Kind | Who | What it asks | Answer with |
|---|---|---|---|
| `trace-link` | agent | A 1.1.1 `trace` entry names a node that no link field of this node takes | Pick the field that fits (`specdev node candidates --for <node-id> --field <field>` lists targets), then `specdev json insert --id <node-id> .<field> '"<target-id>"'`; or drop the entry. When the entry points to a node of a later step, the link belongs to that node's own field (`derives_from` of an FR, for example): check it there with `specdev node show <target-id>`, then resolve the item |
| `legacy-ref` | agent | An old reference names no node, or a node of another kind than its field takes | Find the node it meant (`specdev node show <id>`), then `specdev json insert --id <node-id> .<field> '"<target-id>"'`; or drop it |
| `scope-reason` | agent | A scope item with `later` or `out` has no `scope_reason` (the old list gave none) | `specdev json patch --id <node-id> .scope_reason '"<why, from the seed or the charter>"'` |
| `out-of-scope-entry` | agent | An old `out_of_scope` entry named no node | On the node it meant, the reason first (`out` needs one): `specdev json patch --id <node-id> .scope_reason '"<why>"'`, then `specdev json patch --id <node-id> .scope '"out"'` |
| `gate-text` | agent | A gate that was free text got a minted id | Name it: `specdev node rename <minted-id> <gate-id>` |
| `prose-ids` | agent | Text names ids (the evidence lists each); a field of the node may take them as links. Written by `specdev align propose spec --kind prose-ids --repo-root ./devspec_toolkit --git-root .`, not by `apply` | Link the id (`specdev json insert --id <node-id> .<field> '"<target-id>"'`) or reword the text: `specdev json patch --id <node-id> .<text-field> '"<new text>"'` |
| `seed-route-cleanup` | operator | The seed manifest routes a seed to this step (or to none) and no node of the step lists it in `derives_from` (E747, E748) | Distil the seed in a node of this step: `specdev json insert --id <node-id> .derives_from '"<seed-id>"'` (in step 03, 13 or a trinity step no node can list a seed: move the route to the step that distils it); or remove the route: `specdev json delete spec/common/seed_manifest.json '<jq path of the route>'` |
| `unresolved-link` | operator | A link the resolver refused (E700 to E702) got no lock entry | Fix or drop the link with `specdev json patch --id <node-id> .<field> '["<target-id>"]'`; `specdev attest <node-id> --yes` then writes its entry |

### Procedure

1. Once per migration, before the first step pass, run the proposers; they add the items `apply` does not write (`refines`, `prose-ids`, `legacy-binding`, `legacy-fixture`), write only the worklist, and a rerun adds none: `specdev align propose spec --kind refines --repo-root ./devspec_toolkit --git-root .`, `specdev align propose spec --kind prose-ids --repo-root ./devspec_toolkit --git-root .`, `specdev align propose spec --kind bindings --repo-root ./devspec_toolkit --git-root .`.
2. List the open items of the step: `specdev align triage spec --step 03 --repo-root ./devspec_toolkit --git-root .` (add `--audience agent` for the ones an agent settles; an operator item is decided by a person).
3. Read each item's evidence and proposal, and the node it names: `specdev node show <node-id>`. A proposal says what the script would do; it has not been applied.
4. Make the edit with the id-keyed commands of the table. Nothing is written into a file under `spec/` by hand; read through `specdev json read <file> '<jq path>'`, not the file.
5. Close the item: `specdev align triage spec --resolve <item-id> --note "<what was decided>" --repo-root ./devspec_toolkit --git-root .`.
6. Clear the step's baseline entries one node at a time. The check lists one E882 per entry: review the node's links, then `specdev attest <node-id>` previews what would be written and `specdev attest <node-id> --yes` writes it. A node of a closed milestone keeps its marker (E765).
7. Check the step: `specdev spec-check spec --step 03 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` ends `RESULT: CLEAR` when the step has no error of its own and no new error of an earlier step. Debt of an earlier step that still has E882 entries is listed and does not block. `specdev guide <code>` explains an error code.

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `glossary-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `terms`: Array of term objects (minItems: 1). Each entry requires:
  - `term_id`: kebab-case identifier (e.g., `term-billing-reconciliation`).
  - `term`: String (minLength: 2) — canonical form of the term as it appears in project documentation.
  - `definition`: String (minLength: 20) — precise definition as used in this project.
  - `term_ref`: Canonical reference object (kind: `term`) — required.
- `canonical_proposals`: Array — required at the top level (may be empty array `[]`).

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `terms[].acronym`: Uppercase string (pattern: `^[A-Z0-9]{2,}$`) — include only if the acronym appears 3+ times or is standard industry usage.
- `terms[].domain`: Lowercase alphabetic-only kebab-case string (pattern: `^[a-z]+(?:-[a-z]+)*$`) — no digits allowed.
- `terms[].units`: String (pattern: `^[A-Za-z0-9/]+$`) — unit of measurement if the term is quantifiable.
- `terms[].acronym_ref`: Canonical reference (kind: `acronym`) — only when `acronym` field is also set.
- `terms[].unit_ref`: Canonical reference (kind: `unit`) — only when `units` field is also set.

## Context

The glossary provides shared vocabulary across all spec artifacts. Terms are
referenced by canonical-lint and canonical-integrity checks. During migration,
ensure no definitions are truncated below the 20-character minimum. The top-level
`canonical_proposals` field is now required (even as an empty array). Add a
`term_ref` canonical reference to every term entry. The `domain` field pattern
prohibits digits (`^[a-z]+(?:-[a-z]+)*$`) — correct any `domain` values that
contain numbers. After migration, run `canon-accept` to promote new glossary
terms to the canonical registry.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_03_glossary.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
