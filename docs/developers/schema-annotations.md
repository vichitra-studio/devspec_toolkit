# Schema Annotations (`vc:core:graph`)

`schema/core/graph.schema.json` (`$id` `vc:core:graph`) defines the annotation language step schemas use to declare
graph nodes and links. It only defines shapes. The seed manifest (`schema/seed_manifest.schema.json`, the top-of-graph `seed` kind) and the step schemas 00, 01, 02, 02a, 03, 04 and 05 carry annotations, as do the step schemas 06 to 12, 14 and 15, `schema/16_anchor.schema.json` and `schema/16_impl_context.schema.json`. The schemas of steps 13 and 13a carry none. Every definition has an
`$anchor` equal to its name, so reference it as `vc:core:graph#<name>`.

## `x-node` (`xNode`)

Declares that each item of an array, or each value of a map, is a graph node.

| Key | Meaning |
|---|---|
| `kind` | Required. Kebab-case node kind. |
| `id` / `map_keyed: true` | Exactly one. `id` names the id property of each item; `map_keyed` means the map key is the id. |
| `role` / `top_of_graph: true` | Exactly one. `role` is a `nodeRole`; `top_of_graph` is only for kind `seed`. |
| `contract` | Property names that make up the node's contract. Required unless `top_of_graph`. |
| `coarse` | Optional boolean. Declares a coarse obligation; the built computation that reads it comes later. |
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

## Link verbs (`linkVerb`)

A closed set of 19 field names; a field name never changes meaning between steps.

`derives_from`, `refines`, `realises`, `mitigated_by`, `assumes`, `constrains`, `provided_by`, `relies_on`,
`connects_to`, `verifies`, `verified_by`, `threatens`, `schedules`, `justified_by`, `depends_on`, `part_of`,
`replaces`, `removes`, `about`.

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

## What reads the annotations

`registry-generate` scans every schema in `tools/schema_registry.json`, lints the annotations, then writes the outputs.

| Output | Flag | Notes |
|---|---|---|
| `tools/entry_key_registry.json` | `--out` | Annotated nodes add entries marked `source: "x-node"` with `role`, `contract`, `coarse` and `links`. When an annotated shared node has the same `array_path` as a legacy heuristic entry, the legacy entry is kept. Map-keyed nodes carry no `id_field`. Glob-keyed entries (step 16 plan files) use the glob as the key. |
| `tools/extraction_paths.json` | `--extraction-paths-out` | Unchanged. |
| `tools/cli_commands.json` | `--cli-commands-out` | The CLI command list built from the argparse tree. Defaults to `tools/cli_commands.json` only when `--out` is absent; the defaults of `--out` and `--extraction-paths-out` are unchanged. |
| `tools/step_order.json` | `--step-order-out` | Generated: the order and edges derived from the annotations plus the hand-carried keys of the existing file (`version`, `steps`, `policy`, `coverage_thresholds`, `declared_edges`). Do not edit the derived keys (`downstream_consumers`, `step_metadata`) by hand. Defaults to `tools/step_order.json` only when `--out` is absent. With no annotated step, or when the annotation lint finds issues, the command fails with `registry-generate: failed:`. `step_order_gen.diff_against_hand` is library only. |
| `docs/developers/schema-change-checklist.md` | `--checklist-out` | Rendered from `tools/schema_changes.json`. Defaults to that path only when `--out` is absent. A malformed rows file makes the command fail with `registry-generate: failed:`. |

All outputs are byte-deterministic. A toolkit with no `x-node` / `x-link` annotations produces the legacy registry entries unchanged; `_format_version` is `1.1.0`.

## Lint codes (`ANNOT-NN`)

`generate_registry` raises `AnnotationError` (a `ValueError`) when the lint finds issues. The text of each issue starts with the code and names the schema file and JSON pointer. These are toolkit-author diagnostics, not `E`/`W` codes, and have no `specdev guide` entry.

| Code | Raised when |
|---|---|
| ANNOT-01 | An `x-node` or `x-link` value does not validate against `vc:core:graph`. |
| ANNOT-02 | A kind is not kebab-case, or one kind is declared at more than one site. |
| ANNOT-03 | The node's items schema is missing, the id property is missing or not a string, or a `map_keyed` node lacks `additionalProperties`. |
| ANNOT-05 | An `x-link` field name is not a link verb, is not an array whose items `$ref` is `vc:core:atoms#kebabId`, `vc:core:atoms#screamingSnakeId` or `vc:core:graph#nodeId`, or does not sit on a node item; or a `"*"` or `about` field whose items do not `$ref` `vc:core:graph#nodeId`. |
| ANNOT-07 | An `x-link` kind (or a `same_step_kinds` entry) is not a declared kind or not in `kinds`. |
| ANNOT-08 | A node item lacks `lifecycle` as `$ref vc:core:graph#lifecycle`; an obligation item lacks `scope`, `scope_reason` or the `scopeReasonRule` in its `allOf`. `top_of_graph` kinds and role `record` kinds are exempt from `lifecycle`, `scope` and `scope_reason`. |
| ANNOT-20 | The derived step graph has a cycle (raised by the step-order derivation). |
| ANNOT-21 | An `x-link` kind lives in the holder's own step and is not in `same_step_kinds` (step-order derivation). Record-role holders are checked too; only their edges are exempt from the order. |

The kind `seed` is external: links may name it without a declaring node.
