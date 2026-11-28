# Schema Annotations (`vc:core:graph`)

`schema/core/graph.schema.json` (`$id` `vc:core:graph`) defines the annotation language step schemas use to declare
graph nodes and links. It only defines shapes. The seed manifest (`schema/seed_manifest.schema.json`, the top-of-graph `seed` kind) and the step schemas 00, 01, 02, 02a, 03, 04 and 05 carry annotations, as do the step schemas 06 to 12, 14 and 15, `schema/16_anchor.schema.json` and `schema/16_impl_context.schema.json`. The schema of step 13 declares the `extension` kind (role `plan`, with the required link `justified_by`) and gets the shared `ambiguity-item` node through the core `ambiguityList`. A host declares kinds of its own with the same annotations in the extension schemas of its spec folder (see "An extension schema"). Every definition has an
`$anchor` equal to its name, so reference it as `vc:core:graph#<name>`.

## `x-node` (`xNode`)

Declares that each item of an array, or each value of a map, is a graph node.

| Key | Meaning |
|---|---|
| `kind` | Required. Kebab-case node kind. |
| `id` / `map_keyed: true` | Exactly one. `id` names the id property of each item; `map_keyed` means the map key is the id. |
| `role` / `top_of_graph: true` | Exactly one. `role` is a `nodeRole`; `top_of_graph` is only for kind `seed`. |
| `contract` | Property names that make up the node's contract. Required unless `top_of_graph`. |
| `coarse` | Optional boolean. Declares a coarse obligation. `registry-generate` copies it into the registry entry; the built computation decides coarseness by kind (`scope-item`, `risk`, `capability`) and does not read it. |
| `step` | Optional step id. Default: the numeric prefix of the schema file name. |
| `files` | Optional relative globs. Default: the step's spec file. Step 16 plan files must set `files: ["impl_context/ms_*_plan.json"]` explicitly. |

**Which schemas are hosts.** `registry-generate` registers nodes from step schemas (`schema/NN_*.schema.json`), the seed manifest, and any other schema registered in `tools/schema_registry.json` whose own file declares an `x-node` with `files`; such entries go under the `files` glob key and always register under step `extras`; `x-node.step` is not read for these hosts. A node declared in a non-step schema without `files` is not registered.

`nodeRole` values: `obligation-system`, `obligation-delivery`, `verifier`, `plan`, `context`, `record`. `seed` is not a role.

## `x-link` (`xLink`)

| Key | Meaning |
|---|---|
| `kinds` | Required. Non-empty array of kind names, or the literal `"*"`. `"*"` is meant only for `replaces`, `removes` and `about`; the lint does not check which verb uses it. A field whose `kinds` is `"*"`, or whose verb is `about`, must reference `vc:core:graph#nodeId`. |
| `required` | Required boolean. |
| `built` | Optional boolean, default false. |
| `same_step_kinds` | Optional array, a subset of `kinds` that may be held in the same step. |
| `additional_kinds` | Optional array, a subset of `kinds` that the field accepts in addition to the others. When the link is required, a value that holds only targets of these kinds does not satisfy it (E701). A target that cannot be found is looked for in the steps of the other kinds (the two special forms of E700). Used for a seed listed beside a node's upstream link. |
| `roles` | Optional array of roles. The field accepts, in addition to `kinds`, every kind of these roles that a host declares in its extension schemas (step 13). A kind of the toolkit is never added by role: the toolkit lists its own kinds in `kinds`. Used by `refines` of a task criterion (`["obligation-system"]`), which is how a criterion refines an obligation of an extension. |

## Link verbs (`linkVerb`)

A closed set of 20 field names; a field name never changes meaning between steps.

`derives_from`, `refines`, `realises`, `mitigated_by`, `assumes`, `constrains`, `provided_by`, `relies_on`,
`connects_to`, `verifies`, `verified_by`, `threatens`, `schedules`, `justified_by`, `depends_on`, `part_of`,
`replaces`, `removes`, `about`, `expects`.

## Shared fields and attachment rule

`nodeId` (kebab or SCREAMING_SNAKE id), `lifecycle` (`active` default, `deprecated`, `not_applicable`), `scope`
(`in`, `later`, `out`), `scopeReason` (non-empty string, field name `scope_reason`).

Item schemas are closed (`additionalProperties: false`), so attach these as direct properties, never through `allOf`:

```json
"lifecycle": {"$ref": "vc:core:graph#lifecycle"},
"scope": {"$ref": "vc:core:graph#scope"},
"scope_reason": {"$ref": "vc:core:graph#scopeReason"}
```

Attach the reason rule in the item's `allOf`; it makes `scope_reason` required when `scope` is `later` or `out`:

```json
"allOf": [{"$ref": "vc:core:graph#scopeReasonRule"}]
```

## An extension schema

A host declares kinds and links in the schema file of an extension, `spec/extensions/ext_NN_<topic>.schema.json`
(the guide: [extension_schemas.md](extension_schemas.md); the model:
`tests/fixtures/extension_example/spec/extensions/ext_01_database.schema.json`). The annotations are the ones above,
within these bounds:

| An extension schema | Rule |
|---|---|
| `x-node` keys | `kind`, `role`, `id`, `contract`. `step`, `files` and `top_of_graph` are refused: the step is 13 and the nodes are the items of the extension's data file |
| `role` | `context` or `obligation-system`; no other role |
| `kind` | A name that no toolkit kind and no other extension schema declares (ANNOT-02) |
| `id` | The id property is in `required` of the item |
| `contract` | Properties of the item; never the id property and never a link field |
| Nesting | A kind may be nested in another kind, not in itself |
| `x-link` keys | `kinds`, `required`, `built`, `same_step_kinds`, `additional_kinds`, on a field named with a link verb |
| Link targets | Kinds of earlier steps, and kinds of step 13 that the link lists in `same_step_kinds`. `seed` in the `kinds` of a `derives_from`, for a seed the manifest routes to step 13 |
| Proof of an obligation | The obligation kind declares `verified_by` to `fixture` and `job`; a task criterion that refines an item lists a verifier the item names (E745) |
| `$ref` | The core schemas (`vc:core:*`) and another extension schema of the folder. The `x-node` of a toolkit step schema may not be reached by `$ref`; the core `ambiguityList` may |
| Item fields | `lifecycle` on every item; `scope`, `scope_reason` and the `scopeReasonRule` on an obligation item (ANNOT-08); `aliases` (an array of `vc:core:atoms#kebabId`) on an item that `specdev node rename` is to rename |

The lint below runs on an extension schema too. An extension schema that breaks a rule is reported by the step gate of step 13
in one E520 that lists every line, each with the schema file and the JSON pointer; no kind of any extension is
loaded until all are corrected. The lines, copied from runs on copies of the example:

- `/properties/tables: an extension kind may not take the role 'verifier'; the roles of an extension kind are context and obligation-system`
- `/properties/tables: an extension kind may not set 'step': its step is 13 and its nodes are in the data file of the extension`
- `/properties/datastores: the id property 'datastore_id' of the extension kind 'datastore' is not in `required` of its item; an item with no 'datastore_id' would be no node and no check would say so: add it to `required``
- `/properties/tables: the contract of the extension kind 'table' names its id property 'table_id'; the id is not part of the text of a node`
- `/properties/tables: the contract of the extension kind 'table' names 'scope', which is no property of its item; an edit of a node is seen through its contract fields`
- `.fixtures: reaches by $ref the x-node of the toolkit kind 'fixture' (schema/08_fixtures.schema.json /properties/fixtures); the nodes of kind fixture live in the file of step 08, and an extension file holds the kinds an extension schema declares: declare a kind of the extension for these items, or name the nodes of the toolkit by id in a link field`
- `ANNOT-02 kind 'rule' is declared at more than one site: schema/10_governance.schema.json /allOf/1/properties/rules, extensions/ext_01_database.schema.json /properties/datastores`
- `ANNOT-07 extensions/ext_01_database.schema.json /properties/tables/items/properties/verified_by: x-link kind 'nosuch' is not a declared kind`
- `ANNOT-08 extensions/ext_01_database.schema.json /properties/datastores: item of 'datastore' must declare lifecycle as $ref vc:core:graph#lifecycle`

Nothing of an extension schema enters the registry files of the toolkit: `registry-generate` does not read it.

## What reads the annotations

`registry-generate` scans every schema in `tools/schema_registry.json`, lints the annotations, then writes the outputs.

| Output | Flag | Notes |
|---|---|---|
| `tools/entry_key_registry.json` | `--out` | Annotated nodes add entries marked `source: "x-node"` with each of `role`, `contract` and `coarse` that the node declares, and `links` when it has any. Map-keyed nodes carry no `id_field`. Glob-keyed entries (step 16 plan files) use the glob as the key. |
| `tools/extraction_paths.json` | `--extraction-paths-out` | Lists, beside each top-level array path, the full path of every nested and map-keyed entry (for example `.milestones[].tasks[].acceptance_criteria`). |
| `tools/cli_commands.json` | `--cli-commands-out` | The CLI command list built from the argparse tree. Defaults to `tools/cli_commands.json` only when `--out` is absent; the defaults of `--out` and `--extraction-paths-out` are unchanged. |
| `tools/step_order.json` | `--step-order-out` | Generated: the order and edges derived from the annotations plus the hand-carried keys of the existing file (`version`, `steps`, `policy`, `declared_edges`). Do not edit the derived keys (`downstream_consumers`, `step_metadata`) by hand. Defaults to `tools/step_order.json` only when `--out` is absent. With no annotated step, when the annotation lint finds issues, or when a hand-carried key of the existing file cannot be used (wrong type, a declared edge naming an unlisted step), the command fails with `registry-generate: failed:` and writes no file. On every run, with or without this flag, `steps` must list each step that declares an `x-node` kind. |
| `docs/developers/schema-change-checklist.md` | `--checklist-out` | Rendered from `tools/schema_changes.json`. Defaults to that path only when `--out` is absent. A malformed rows file makes the command fail with `registry-generate: failed:`. |

All outputs are byte-deterministic. A toolkit with no `x-node` / `x-link` annotations produces the legacy registry entries unchanged; `_format_version` is `1.1.0`.

## Lint codes (`ANNOT-NN`)

`generate_registry` raises `AnnotationError` (a `ValueError`) when the lint finds issues. The text of each issue starts with the code and names the schema file and JSON pointer. These are toolkit-author diagnostics, not `E`/`W` codes, and have no `specdev guide` entry. For an extension schema the same texts are lines of the E520 of step 13 (see "An extension schema").

| Code | Raised when |
|---|---|
| ANNOT-01 | An `x-node` or `x-link` value does not validate against `vc:core:graph`. |
| ANNOT-02 | A kind is not kebab-case, or one kind is declared at more than one site. |
| ANNOT-03 | The node's items schema is missing, the id property is missing or not a string, or a `map_keyed` node lacks `additionalProperties`. |
| ANNOT-05 | An `x-link` field name is not a link verb, is not an array whose items `$ref` is `vc:core:atoms#kebabId`, `vc:core:atoms#screamingSnakeId` or `vc:core:graph#nodeId`, or does not sit on a node item; or a `"*"` or `about` field whose items do not `$ref` `vc:core:graph#nodeId`. |
| ANNOT-07 | An `x-link` kind (or a `same_step_kinds` or `additional_kinds` entry) is not a declared kind or not in `kinds`. |
| ANNOT-08 | A node item lacks `lifecycle` as `$ref vc:core:graph#lifecycle`; an obligation item lacks `scope`, `scope_reason` or the `scopeReasonRule` in its `allOf`. `top_of_graph` kinds and role `record` kinds are exempt from `lifecycle`, `scope` and `scope_reason`. |
| ANNOT-20 | The derived step graph has a cycle (raised by the step-order derivation). |
| ANNOT-21 | An `x-link` kind lives in the holder's own step and is not in `same_step_kinds` (step-order derivation). Record-role holders are checked too; only their edges are exempt from the order. |

The kind `seed` is external: links may name it without a declaring node.
