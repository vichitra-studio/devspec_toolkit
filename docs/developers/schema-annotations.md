# Schema Annotations (`vc:core:graph`)

`schema/core/graph.schema.json` (`$id` `vc:core:graph`) defines the annotation language step schemas use to declare
graph nodes and links. It only defines shapes. Only `schema/seed_manifest.schema.json` carries an annotation today (the top-of-graph `seed` kind); step schemas are annotated in later milestones. Every definition has an
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
| `files` | Optional relative globs. Default: the step's spec file (step 16 plan files use `impl_context/ms_*_plan.json`). |

`nodeRole` values: `obligation-system`, `obligation-delivery`, `verifier`, `plan`, `context`, `record`. `seed` is not a role.

## `x-link` (`xLink`)

| Key | Meaning |
|---|---|
| `kinds` | Required. Non-empty array of kind names, or the literal `"*"` (only for `replaces`, `removes`, `about`). |
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
| `tools/cli_commands.json` | `--cli-commands-out` | The CLI command list built from the argparse tree. Defaults to `tools/cli_commands.json` only when `--out` is absent. |
| derived step order | `--step-order-out` | Written only when a path is given. `tools/step_order.json` stays the hand file; the derived order is compared against it, never written into it. |

All outputs are byte-deterministic. A toolkit with no `x-node` / `x-link` annotations produces the legacy registry unchanged.

## Lint codes (`ANNOT-NN`)

`generate_registry` raises `AnnotationError` (a `ValueError`) when the lint finds issues. The text of each issue starts with the code and names the schema file and JSON pointer. These are toolkit-author diagnostics, not `E`/`W` codes, and have no `specdev guide` entry.

| Code | Raised when |
|---|---|
| ANNOT-01 | An `x-node` or `x-link` value does not validate against `vc:core:graph`. |
| ANNOT-02 | A kind is not kebab-case, or one kind is declared at more than one site. |
| ANNOT-03 | The node's items schema is missing, the id property is missing or not a string, or a `map_keyed` node lacks `additionalProperties`. |
| ANNOT-05 | An `x-link` field name is not a link verb, is not an array of `$ref` items, or does not sit on a node item. |
| ANNOT-07 | An `x-link` kind (or a `same_step_kinds` entry) is not a declared kind or not in `kinds`. |
| ANNOT-08 | A node item lacks `lifecycle` as `$ref vc:core:graph#lifecycle`; an obligation item lacks `scope`, `scope_reason` or the `scopeReasonRule` in its `allOf`. |
| ANNOT-20 | The derived step graph has a cycle (raised by the step-order derivation). |
| ANNOT-21 | An `x-link` kind lives in the holder's own step and is not in `same_step_kinds` (step-order derivation). |

The kind `seed` is external: links may name it without a declaring node.
