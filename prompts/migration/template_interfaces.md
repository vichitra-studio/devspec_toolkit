<!-- Migration template: step {{STEP_ID}}, {{SOURCE_VERSION}} to {{TARGET_VERSION}} -->
# Migration: Interface Contracts (Step 05)

## Schema URI

`vc:05-interface-contracts`

## Judgement pass

`specdev align apply spec --auto` has run and been committed. What it could not decide is a worklist item. This pass settles the items of step 05, clears the step's baseline entries and ends with the step's check. Do it after the steps above 05 have passed. `blocking` on an item is a display hint; nothing gates on it.

### Items of step 05

| Kind | Who | What it asks | Answer with |
|---|---|---|---|
| `milestone-order` | agent | A step-09 milestone came after another one (`depends_on`, now removed), and no API `depends_on` connects what they schedule | Add the missing link: `specdev json insert --id <later-api-id> .depends_on '"<earlier-api-id>"'`; or drop the pair |
| `api-relies-on` | agent | An API names a technology in its name or version that is now a third-party node | `specdev json insert --id <api-id> .relies_on '"<third-party-id>"'` (the version is the pin the API was specified against); or drop it |

### Items any step can carry

| Kind | Who | What it asks | Answer with |
|---|---|---|---|
| `trace-link` | agent | A 1.1.1 `trace` entry names a node that no link field of this node takes | Pick the field that fits (`specdev node candidates --for <node-id> --field <field>` lists targets), then `specdev json insert --id <node-id> .<field> '"<target-id>"'`; or drop the entry. When the entry points to a node of a later step, the link belongs to that node's own field (`derives_from` of an FR, for example): check it there with `specdev node show <target-id>`, then resolve the item |
| `legacy-ref` | agent | An old reference names no node, or a node of another kind than its field takes | Find the node it meant (`specdev node show <id>`), then `specdev json insert --id <node-id> .<field> '"<target-id>"'`; or drop it |
| `scope-reason` | agent | A scope item with `later` or `out` has no `scope_reason` (the old list gave none) | `specdev json patch --id <node-id> .scope_reason '"<why, from the seed or the charter>"'` |
| `out-of-scope-entry` | agent | An old `out_of_scope` entry named no node | On the node it meant, the reason first (`out` needs one): `specdev json patch --id <node-id> .scope_reason '"<why>"'`, then `specdev json patch --id <node-id> .scope '"out"'` |
| `gate-text` | agent | A gate that was free text got a minted id | Name it: `specdev node rename <minted-id> <gate-id>` |
| `prose-ids` | agent | Text names ids (the evidence lists each); a field of the node may take them as links. Written by `specdev align propose spec --kind prose-ids --repo-root ./devspec_toolkit --git-root .`, not by `apply` | Link the id (`specdev json insert --id <node-id> .<field> '"<target-id>"'`) or reword the text: `specdev json patch --id <node-id> .<text-field> '"<new text>"'` |
| `seed-route-cleanup` | operator | The seed manifest routes a seed to this step (or to none) and no node of the step lists it in `derives_from` (E747, E748) | Distil the seed: `specdev json insert --id <node-id> .derives_from '"<seed-id>"'`; or remove the route: `specdev json delete spec/common/seed_manifest.json '<jq path of the route>'` |
| `unresolved-link` | operator | A link the resolver refused (E700 to E702) got no lock entry | Fix or drop the link with `specdev json patch --id <node-id> .<field> '["<target-id>"]'`; `specdev attest <node-id> --yes` then writes its entry |

An error with no item: an `E520 ... '<field>' is a required property` for a link the node must now have (`derives_from`, `threatens`, `mitigated_by`) has no worklist item. The error names the file and a path with an index (`00_charter.json:risks/0`): read the node there with `specdev json read <file> '.<collection>[<index>]'`, list what the field accepts with `specdev node candidates --for <node-id> --field <field> --repo-root ./devspec_toolkit --git-root .`, and write the link with `specdev json patch --id <node-id> .<field> '["<target-id>"]'`. The host guide, step 6, "An error that has no worklist item", shows the three commands run.

### Procedure

1. Once per migration, before the first step pass, run the proposers; they add the items `apply` does not write (`refines`, `prose-ids`, `legacy-binding`, `legacy-fixture`), write only the worklist, and a rerun adds none: `specdev align propose spec --kind refines --repo-root ./devspec_toolkit --git-root .`, `specdev align propose spec --kind prose-ids --repo-root ./devspec_toolkit --git-root .`, `specdev align propose spec --kind bindings --repo-root ./devspec_toolkit --git-root .`.
2. List the open items of the step: `specdev align triage spec --step 05 --repo-root ./devspec_toolkit --git-root .` (add `--audience agent` for the ones an agent settles; an operator item is decided by a person).
3. Read each item's evidence and proposal, and the node it names: `specdev node show <node-id>`. A proposal says what the script would do; it has not been applied.
4. Make the edit with the id-keyed commands of the table. Nothing is written into a file under `spec/` by hand; read through `specdev json read <file> '<jq path>'`, not the file.
5. Close the item: `specdev align triage spec --resolve <item-id> --note "<what was decided>" --repo-root ./devspec_toolkit --git-root .`.
6. Clear the step's baseline entries one node at a time. The check lists one E882 per entry: review the node's links, then `specdev attest <node-id>` previews what would be written and `specdev attest <node-id> --yes` writes it. A node of a closed milestone keeps its marker (E765).
7. Check the step: `specdev spec-check spec --step 05 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` ends `RESULT: CLEAR` when the step has no error of its own and no new error of an earlier step. Debt of an earlier step that still has E882 entries is listed and does not block. `specdev guide <code>` explains an error code.

## Required Changes

**Step-base fields (required in every artifact):**

- `id`: String — unique kebab-case identifier for this artifact instance (e.g., `interface-contracts-v1`). Convention: `{step-noun}-v{N}`.
- `owner`: String enum — must be one of `api | ui | system | ops | data | product | business | engineering`.
- `created_at`: String — ISO 8601 UTC timestamp (e.g., `2025-10-16T22:06:04.202593Z`).
- `canonical_refs_used`: Array of canonical reference objects — required even when empty (`[]`).

**Step-specific fields:**

- `$schema`: Must reference the URI above for the target toolkit version.
- `apis`: Array of API contract objects (minItems: 1). Each entry requires:
  - `api_id`: kebab-case identifier; `api-` prefix recommended (e.g., `api-user-auth`, `api-session-create`).
  - `name`: Human-readable endpoint name (e.g., `Create User Session`).
  - `version`: String matching pattern `^v\d+(?:\.\d+)*$` (e.g., `v1`, `v2.1`).
  - `protocol`: Must be one of `http | grpc | ws | mqtt`.
  - `owner`: Canonical owner enum (`api | ui | system | ops | data | product | business | engineering`).
  - `interface_ref`: Canonical reference object (kind: `interface`) — required.
  - `scope`: Must be one of `in | later | out`; `later` and `out` also require `scope_reason`.
  - `derives_from`: Array of functional requirement ids (minItems: 1) that this API implements.

## Output Contract

The migrated artifact MUST include:

- `$schema`: Set to the canonical URI above.
- `canonical_refs_used`: Array of canonical reference objects.

## Optional Fields

- `_migration_notes`: Array of strings — migration annotations written exclusively by specdev tooling (canonical-autofix, align apply). Do NOT populate manually.
- `apis[].path`: URL path string (omit for non-HTTP protocols).
- `apis[].method`: HTTP method — one of `GET | POST | PUT | PATCH | DELETE` (omit for non-HTTP).
- `apis[].security`: Auth mechanism — one of `none | jwt | oauth2 | api-key | mTLS`.
- `apis[].input_schema_ref`: Relative path to request body JSON Schema file (use `-tbd` as placeholder).
- `apis[].output_schema_ref`: Relative path to response body JSON Schema file (use `-tbd` as placeholder).
- `apis[].errors`: Array of error objects, each requiring `error_id` (kebab-case), `code` (kebab-case), `message`, `scope` (`in | later | out`) and `derives_from` (ids of acceptance criteria, minItems: 1); `severity` (`info | warn | error | fatal`) is optional, and `scope_reason` is required when `scope` is `later` or `out`.
- `apis[].parameters`: Array of parameter objects, each requiring `name`, `in` (`query | path | header`), and `required` (boolean).
- `apis[].provided_by`: Array of component ids that provide this API.
- `apis[].relies_on`: Array of third-party ids this API relies on.
- `apis[].event_ref`: Canonical reference (kind: `event`) for events emitted or consumed.
- `apis[].entity_ref`: Canonical reference (kind: `entity`) for the primary domain entity.
- `apis[].policy_ref`: Canonical reference (kind: `policy`) for access control policy.
- `apis[].enum_provenance`: Object required whenever a parameter declares `enum`; needs `source_url`, `source_date`, and `resolved_at`.

## Context

Interface contracts define the API surface. The top-level array field is `apis`
(not `interfaces`) — rename accordingly. Each entry requires `interface_ref` as
a canonical object (not a bare string). The `method` field accepts only
`GET | POST | PUT | PATCH | DELETE` (not OPTIONS or HEAD — those are scaffold-only);
ensure no lowercase or non-standard HTTP verbs remain. Each API must list at least one FR in
`derives_from`. Step 08 fixtures reference the API from the fixture side, so
there is no fixture list to maintain on the API.


## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_05_interface_contracts.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
