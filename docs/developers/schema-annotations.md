# Schema Annotations (`vc:core:graph`)

`schema/core/graph.schema.json` (`$id` `vc:core:graph`) defines the annotation language step schemas use to declare
graph nodes and links. It only defines shapes; no step schema carries an annotation yet. Every definition has an
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
