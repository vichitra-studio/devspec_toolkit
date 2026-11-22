<!-- Migration template: step {{STEP_ID}}, {{SOURCE_VERSION}} to {{TARGET_VERSION}} -->
# Migration: System Sketch (Step 02)

## Schema URI

`vc:02-system-sketch`

## Judgement pass

`specdev align apply spec --auto` has run and been committed. What it could not decide is a worklist item. This pass settles the items of step 02, clears the step's baseline entries and ends with the step's check. Do it after the steps above 02 have passed. `blocking` on an item is a display hint; nothing gates on it.

### Items of step 02

| Kind | Who | What it asks | Answer with |
|---|---|---|---|
| `third-party-proposal` | agent | A `tech_stack` entry of steps 02, 09 or 14 that may be a third party; the item shows a name, a pin and a rationale to judge | Add it: `specdev json insert --step 02 .third_parties '{"third_party_id":"<id>","name":"<name>","pin":"<exact version>","derives_from":["<seed-or-constraint-id>"]}'`; link each user: `specdev json insert --id <node-id> .relies_on '"<third-party-id>"'`; or drop the entry |
| `external-component` | agent | An external component became a `third_parties` entry with no pin and no `derives_from` (E520 until filled); what used it may now lack a component (E590) | `specdev third-party pin <third-party-id> <exact version>`, `specdev json patch --id <third-party-id> .derives_from '["<seed-or-constraint-id>"]'`; point its users at it (`connects_to`, `relies_on`); name a component for the capability |
| `external-dependency` | agent | A step-09 dependency named an external party; the entry was copied nowhere | Relate it to the third-party node: `specdev json insert --id <api-id> .relies_on '"<third-party-id>"'` or `specdev json insert --id <connection-id> .connects_to '"<third-party-id>"'`; or drop it |
| `connection-external` | agent | A connection pointed at an external component; the third-party node replaces it | Once the node exists: `specdev json insert --id <connection-id> .connects_to '"<third-party-id>"'` |
| `host-pin-source` | operator | No tracked file states the version of a third party, so no pin source could be derived | Add where the repository states it under `pin_sources` of `spec/common/host_declarations.json` (the item prints the shape; `docs/developers/host_declarations.md`): `specdev json patch spec/common/host_declarations.json '.pin_sources["<third-party-id>"]' '[<source>]'` |

### Items any step can carry

| Kind | Who | What it asks | Answer with |
|---|---|---|---|
| `trace-link` | agent | A 1.1.1 `trace` entry names a node that no link field of this node takes | Pick the field that fits (`specdev node candidates --for <node-id> --field <field>` lists targets), then `specdev json insert --id <node-id> .<field> '"<target-id>"'`; or drop the entry |
| `legacy-ref` | agent | An old reference names no node, or a node of another kind than its field takes | Find the node it meant (`specdev node show <id>`), then `specdev json insert --id <node-id> .<field> '"<target-id>"'`; or drop it |
| `scope-reason` | agent | A scope item with `later` or `out` has no `scope_reason` (the old list gave none) | `specdev json patch --id <node-id> .scope_reason '"<why, from the seed or the charter>"'` |
| `out-of-scope-entry` | agent | An old `out_of_scope` entry named no node | On the node it meant, the reason first (`out` needs one): `specdev json patch --id <node-id> .scope_reason '"<why>"'`, then `specdev json patch --id <node-id> .scope '"out"'` |
| `gate-text` | agent | A gate that was free text got a minted id | Name it: `specdev node rename <minted-id> <gate-id>` |
| `prose-ids` | agent | Text names ids (the evidence lists each); a field of the node may take them as links. Written by `specdev align propose spec --kind prose-ids --repo-root ./devspec_toolkit --git-root .`, not by `apply` | Link the id (`specdev json insert --id <node-id> .<field> '"<target-id>"'`) or reword the text: `specdev json patch --id <node-id> .<text-field> '"<new text>"'` |
| `seed-route-cleanup` | operator | The seed manifest routes a seed to this step (or to none) and no node of the step lists it in `derives_from` (E747, E748) | Distil the seed: `specdev json insert --id <node-id> .derives_from '"<seed-id>"'`; or remove the route: `specdev json delete spec/common/seed_manifest.json '<jq path of the route>'` |
| `unresolved-link` | operator | A link the resolver refused (E700 to E702) got no lock entry | Fix or drop the link with `specdev json patch --id <node-id> .<field> '["<target-id>"]'`; `specdev attest <node-id> --yes` then writes its entry |

### Procedure

1. Once per migration, before the first step pass, run the proposers; they add the items `apply` does not write (`refines`, `prose-ids`, `legacy-binding`, `legacy-fixture`), write only the worklist, and a rerun adds none: `specdev align propose spec --kind refines --repo-root ./devspec_toolkit --git-root .`, `specdev align propose spec --kind prose-ids --repo-root ./devspec_toolkit --git-root .`, `specdev align propose spec --kind bindings --repo-root ./devspec_toolkit --git-root .`.
2. List the open items of the step: `specdev align triage spec --step 02 --repo-root ./devspec_toolkit --git-root .` (add `--audience agent` for the ones an agent settles; an operator item is decided by a person).
3. Read each item's evidence and proposal, and the node it names: `specdev node show <node-id>`. A proposal says what the script would do; it has not been applied.
4. Make the edit with the id-keyed commands of the table. Nothing is written into a file under `spec/` by hand; read through `specdev json read <file> '<jq path>'`, not the file.
5. Close the item: `specdev align triage spec --resolve <item-id> --note "<what was decided>" --repo-root ./devspec_toolkit --git-root .`.
6. Clear the step's baseline entries one node at a time. The check lists one E882 per entry: review the node's links, then `specdev attest <node-id>` previews what would be written and `specdev attest <node-id> --yes` writes it. A node of a closed milestone keeps its marker (E765).
7. Check the step: `specdev spec-check spec --step 02 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` ends `RESULT: CLEAR` when the step has no error of its own and no new error of an earlier step. Debt of an earlier step that still has E882 entries is listed and does not block. `specdev guide <code>` explains an error code.

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `system-sketch-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `components`: Array of component objects (minItems: 1). Each entry requires:
  - `component_id`: kebab-case identifier (e.g., `api-gateway`, `user-service`).
  - `type`: Must be one of `service | db | queue | cache | job | ui | lib`.
  - `responsibilities`: Array of strings (minItems: 3, maxItems: 6) — present-tense action phrases.
  - `owner`: Canonical owner enum (`api | ui | system | ops | data | product | business | engineering`).
  - `derives_from`: Array of capability or constraint ids (minItems: 1).
- `connections`: Required when 2 or more components exist (minItems: 1). Each entry requires:
  - `connection_id`: kebab-case identifier of the connection.
  - `derives_from`: Array of component ids (minItems: 1) naming the source component.
  - `connects_to`: Array of component or third-party ids (minItems: 1) naming the destination.
  - `protocol`: Must be one of `http | grpc | event | rpc | db | file`.
  - `trust_boundary`: Must be one of `internal | partner | public`.
  - When `trust_boundary` is `partner` or `public`: `auth` and `rate_limit` are also required.
  - When `protocol` is `event`: `reliability` is also required.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `components[].tags`: Array of enum strings from the approved tag vocabulary (e.g., `critical-path`, `stateful`, `pii`).
- `components[].entity_ref`: Canonical reference (kind: `entity`) for the primary domain entity this component owns.
- `third_parties`: Array of third-party objects. Each requires `third_party_id` (kebab-case), `name`, `pin` (the pinned version) and `derives_from`; `rationale` is optional. Replaces `tech_stack`, which is deprecated.
- `connections[].rate_limit`: **Conditionally required** — must be present when `trust_boundary` is `partner` or `public` (enforced by schema `if/then`). Object with `rps` (integer, 1–100000) and `scope` (`ip | client | token | global`) required; `burst` and `window_s` optional. Omit only for `internal` trust boundary connections where back-pressure is not needed.
- `connections[].reliability`: Must be one of `best-effort | at-least-once | exactly-once` (required for event connections).
- `connections[].event_ref`: Canonical reference (kind: `event`) for the event type (used when `protocol` is `event`).

## Context

The system sketch defines the architectural topology. Component IDs
(`component_id`) are referenced by interface contracts (Step 05), invariants
(Step 06), and the implementation plan (Step 09). Rename any legacy `id` field
to `component_id`. The schema has no `name` property on components (it is rejected) —
human-readable labels come from `responsibilities`. Connections between 2+
components are required; if no `connections` array exists, add at least one.
An external service is not a component: record it as a
`third_parties` entry and point the `connects_to` of the connection that reaches it
at its `third_party_id`, with `trust_boundary` set to `partner` or `public`.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_02_system_sketch.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
