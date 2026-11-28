<!-- Migration template: step {{STEP_ID}}, {{SOURCE_VERSION}} to {{TARGET_VERSION}} -->
# Migration: Extension Manifest (Step 13)

## Schema URI

`vc:13-extension-manifest`

## Judgement pass

`specdev align apply spec --auto` has run and been committed. What it could not decide is a worklist item. This pass settles the items of step 13, clears the step's baseline entries and ends with the step's check. Do it after the steps above 13 have passed. `blocking` on an item is a display hint; nothing gates on it.

### Items of step 13

No script or proposer writes an item of its own for step 13; the items below and the step's check are the pass. A manifest whose `extension_decision.status` is `none-required` needs nothing more.

A manifest that declares extensions is left as it was by `apply`, and the step's check (step 7 of the procedure) reports each entry until three things are done. The steps a person follows are in `docs/developers/workflows/workflow_migrate_1_2_0.md` ("Step 13: the files and the links of an extension"):

| The check prints | What it asks | Answer with |
|---|---|---|
| E520 `'justified_by' is a required property` | The entry lists no node that makes the extension necessary | `specdev json patch --id <extension-id> .justified_by '["<node-id>"]'` (a component, third party, capability, FR or NFR; `specdev node candidates --kind extension --field justified_by` lists them). The `prose-ids` item of the entry lists the ids its `justification` names |
| E752 on the `justification` of the entry | The text names a node id | Once the id is in `justified_by`, reword the text to name no id: `specdev json patch --id <extension-id> .justification '"<new text>"'` |
| E520 `Extension '<extension-id>' has no schema`, `has no file` | An entry has two files in `spec/extensions/`: its schema file and its data file | A data file of the 1.1.1 place (`spec/ext_NN_<topic>.json`) is moved to `spec/extensions/` by the operator. The schema file is written as `prompts/prompt_13_extension_manifest.md` says (The Files Of An Extension); a data file that does not exist yet is created with `specdev step create 13 <extension-id> --from <draft> --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` |
| W630 for a data file | An open item of the data file is now counted (E631 at the merge check) | Apply its answer, then `specdev json delete --id <item-id>` |

### Items any step can carry

| Kind | Who | What it asks | Answer with |
|---|---|---|---|
| `trace-link` | agent | A 1.1.1 `trace` entry names a node that no link field of this node takes | Pick the field that fits (`specdev node candidates --for <node-id> --field <field>` lists targets), then `specdev json insert --id <node-id> .<field> '"<target-id>"'`; or drop the entry. When the entry points to a node of a later step, the link belongs to that node's own field (`derives_from` of an FR, for example): check it there with `specdev node show <target-id>`, then resolve the item |
| `legacy-ref` | agent | An old reference names no node, or a node of another kind than its field takes | Find the node it meant (`specdev node show <id>`), then `specdev json insert --id <node-id> .<field> '"<target-id>"'`; or drop it |
| `scope-reason` | agent | A scope item with `later` or `out` has no `scope_reason` (the old list gave none) | `specdev json patch --id <node-id> .scope_reason '"<why, from the seed or the charter>"'` |
| `out-of-scope-entry` | agent | An old `out_of_scope` entry named no node | On the node it meant, the reason first (`out` needs one): `specdev json patch --id <node-id> .scope_reason '"<why>"'`, then `specdev json patch --id <node-id> .scope '"out"'` |
| `gate-text` | agent | A gate that was free text got a minted id | Name it: `specdev node rename <minted-id> <gate-id>` |
| `prose-ids` | agent | Text names ids (the evidence lists each); a field of the node may take them as links. Written by `specdev align propose spec --kind prose-ids --repo-root ./devspec_toolkit --git-root .`, not by `apply` | Link the id (`specdev json insert --id <node-id> .<field> '"<target-id>"'`) or reword the text: `specdev json patch --id <node-id> .<text-field> '"<new text>"'` |
| `seed-route-cleanup` | operator | The seed manifest routes a seed to this step (or to none) and no node of the step lists it in `derives_from` (E747, E748) | Distil the seed in a node of this step: `specdev json insert --id <node-id> .derives_from '"<seed-id>"'` (in a trinity step no node can list a seed, and in step 13 only a node of an extension whose schema declares `derives_from` to a seed can: otherwise move the route to the step that distils it); or remove the route: `specdev json delete spec/common/seed_manifest.json '<jq path of the route>'` |
| `unresolved-link` | operator | A link the resolver refused (E700 to E702) got no lock entry | Fix or drop the link with `specdev json patch --id <node-id> .<field> '["<target-id>"]'`; `specdev attest <node-id> --yes` then writes its entry |

### Procedure

1. Once per migration, before the first step pass, run the proposers; they add the items `apply` does not write (`refines`, `prose-ids`, `legacy-binding`, `legacy-fixture`), write only the worklist, and a rerun adds none: `specdev align propose spec --kind refines --repo-root ./devspec_toolkit --git-root .`, `specdev align propose spec --kind prose-ids --repo-root ./devspec_toolkit --git-root .`, `specdev align propose spec --kind bindings --repo-root ./devspec_toolkit --git-root .`.
2. List the open items of the step: `specdev align triage spec --step 13 --repo-root ./devspec_toolkit --git-root .` (add `--audience agent` for the ones an agent settles; an operator item is decided by a person).
3. Read each item's evidence and proposal, and the node it names: `specdev node show <node-id>`. A proposal says what the script would do; it has not been applied.
4. Make the edit with the id-keyed commands of the table. Nothing is written into a file under `spec/` by hand; read through `specdev json read <file> '<jq path>'`, not the file.
5. Close the item: `specdev align triage spec --resolve <item-id> --note "<what was decided>" --repo-root ./devspec_toolkit --git-root .`.
6. Clear the step's baseline entries one node at a time. The check lists one E882 per entry: review the node's links, then `specdev attest <node-id>` previews what would be written and `specdev attest <node-id> --yes` writes it. A node of a closed milestone keeps its marker (E765).
7. Check the step: `specdev spec-check spec --step 13 --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` ends `RESULT: CLEAR` when the step has no error of its own and no new error of an earlier step. Debt of an earlier step that still has E882 entries is listed and does not block. `specdev guide <code>` explains an error code.

### Context

- Step 13a no longer exists: its file was deleted by the migration. For the link counts and the ids that are not linked use `specdev coverage`; for what is still to re-read upstream use `specdev stale`.

## Shape in 1.2.0

The schema is the authority (`specdev json schema <spec-file> .<field>` resolves the schema of a field); this lists its unconditional requirements as of 1.2.0. Required at the top level of every artifact: `id`, `owner`, `created_at`, `canonical_refs_used`. Links between nodes are the link fields of a node kind: `specdev node candidates --kind <kind> --field <field>` lists what a field accepts.

- `extension_decision` (object, required): requires `rationale`, `status`
- `extensions` (array, required): each item requires `area_of_concern`, `extension_id`, `governance_label_ref`, `justification`, `justified_by`, `required_schema_sections`, `schema_design_guidelines`, `title`

## Output Contract

The migrated artifact MUST include:

- `$schema`: `vc:13-extension-manifest`.
- `canonical_refs_used`: array of canonical reference objects (`[]` when there are none).

## Full Generation Reference

To generate this artifact from scratch (rather than migrate an existing one), use the canonical step prompt:

- `prompts/prompt_13_extension_manifest.md`

The generation prompt contains the complete Output Contract, Self-Audit Gate, and schema authority reference needed to produce a valid artifact.
