<!-- Migration template: step {{STEP_ID}}, {{SOURCE_VERSION}} to {{TARGET_VERSION}} -->
# Migration: Implementation Planner (Step 16a)

## Schema URI

`vc:16-impl-context`

## Judgement pass

`specdev align apply spec --auto` has run and been committed. What it could not decide is a worklist item. This pass settles the items of step 16a, clears the step's baseline entries and ends with the step's check. Do it after the steps above 16a have passed. `blocking` on an item is a display hint; nothing gates on it.

### Items of step 16a

| Kind | Who | What it asks | Answer with |
|---|---|---|---|
| `ambiguity-about` | operator | An open item of a plan does not name exactly one node of an earlier step | `specdev json patch --id <item-id> .about '["<node-id>"]'`, then remove each old field with `specdev json delete <file> '<item path>.<field>'` |
| `plan-security-item` | operator | A closed plan asked for a fixture or a spec change that was never made (the plan is not changed) | Raise it again in the right artifact (a fixture: `specdev json insert --step 08 .fixtures '{...}'`), or drop it |
| `spec-ref-realises` | agent | A plan item's `spec_ref` names a task; the item must `realises` task criteria | `specdev json insert --id <plan-item-id> .realises '"<criterion-id>"'` (the proposal names the criteria) |

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
2. List the open items of the step: `specdev align triage spec --step 16a --repo-root ./devspec_toolkit --git-root .` (add `--audience agent` for the ones an agent settles; an operator item is decided by a person).
3. Read each item's evidence and proposal, and the node it names: `specdev node show <node-id>`. A proposal says what the script would do; it has not been applied.
4. Make the edit with the id-keyed commands of the table. Nothing is written into a file under `spec/` by hand; read through `specdev json read <file> '<jq path>'`, not the file.
5. Close the item: `specdev align triage spec --resolve <item-id> --note "<what was decided>" --repo-root ./devspec_toolkit --git-root .`.
6. Clear the step's baseline entries one node at a time. The check lists one E882 per entry: review the node's links, then `specdev attest <node-id>` previews what would be written and `specdev attest <node-id> --yes` writes it. A node of a closed milestone keeps its marker (E765).
7. Check the step: `specdev spec-check spec --step 16a --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` ends `RESULT: CLEAR` when the step has no error of its own and no new error of an earlier step. Debt of an earlier step that still has E882 entries is listed and does not block. `specdev guide <code>` explains an error code.

### Context

- The old plan files are step-16a files: `specdev align triage spec --legacy 16a --repo-root ./devspec_toolkit --git-root .` prints them as 1.1.1 had them.
- A milestone with no plan file gets one with `specdev step create 16a <batch> --from <draft-file>`.

## Shape in 1.2.0

The schema is the authority (`specdev json schema <spec-file> .<field>` resolves the schema of a field); this lists its unconditional requirements as of 1.2.0. Required at the top level of every artifact: `id`, `owner`, `created_at`, `canonical_refs_used`. Links between nodes are the link fields of a node kind: `specdev node candidates --kind <kind> --field <field>` lists what a field accepts.

- `extensions` (object, optional): fields `execution_context`
- `plan` (object, required): requires `review_requirements`
- `execution` (object, optional): fields `config_validation`, `emergent_ambiguities`, `files_touched`, `records`
- `review` (object, optional): fields `delivery_status`, `findings`, `next_actions`, `ratings`, `recorded_at`, `security_status`, `semantic_review`, `verdict`
- `policy_ref` (object, optional): requires `id`, `kind`
- `risk_category_ref` (object, optional): requires `id`, `kind`
- `milestone` (string, required)

## Output Contract

The migrated artifact MUST include:

- `$schema`: `vc:16-impl-context`.
- `canonical_refs_used`: array of canonical reference objects (`[]` when there are none).

## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_16a_impl_planner.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
