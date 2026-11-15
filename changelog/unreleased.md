## [unreleased]

### Breaking

- Steps 00 to 05 move to the spec-graph shape; existing host specs do not validate until migrated (the migration passes land later in this release). Step 00: `in_scope` / `out_of_scope` merge into `scope_items` (`scope` `in` | `later` | `out`, `scope_reason`), assumptions, risks, stakeholders and needs get ids, new `constraints`, `links` removed. Step 01: `goal_id`, `success_metric_refs` and `trace` removed, `derives_from` added, `scope` `future` becomes `later`. Step 02: `trace` removed; connections use `connection_id`, `derives_from`, `connects_to` (no `from`, `to`, `schema_ref`, `interface_ref`); new `third_parties` (`tech_stack` deprecated). Step 02a: `trace` removed; `ci_gates` and `secrets` become objects; environment host keys move under `config`. Step 03: terms gain `aliases`, `lifecycle`, `replaces`. Step 04: `trace` replaced by `derives_from` and `depends_on`. Step 05: `trace` and `example_refs` removed; `derives_from`, `provided_by`, `relies_on`, `depends_on` added; errors become objects. `specdev align status` / `diff` / `plan` do not see item-level changes until the migration passes.
- Link-existence checks are removed from the step validators of 01, 02, 02a, 04 and 05 and are not replaced until the graph resolver later in this release: a step 00 to 05 spec gets no link-existence or cycle error in the meantime.
- FR-to-API coverage (matrix, E564 / W564 / E535) and the E560 closure checks read only the pre-1.2.0 `trace`, `goal_id` and `success_metric_refs` fields, so they are silent for new-shape specs until graph coverage later in this release.

### Added

- `schema/core/graph.schema.json` (`vc:core:graph`): the `x-node` / `x-link` annotation language for declaring graph nodes and links in step schemas. See `docs/developers/schema-annotations.md`. Only `schema/seed_manifest.schema.json` is annotated in this release.
- Annotation reader and lint with `ANNOT-NN` toolkit-author codes, and a step-order derivation (`ANNOT-20` cycle, `ANNOT-21` same-step link). `registry-generate` folds annotated nodes into `entry_key_registry.json`; without annotations the entries are unchanged and `_format_version` is `1.1.0`.
- `tools/cli_commands.json` (generated; `schema/cli_commands.schema.json`) and the `registry-generate` flags `--cli-commands-out` and `--step-order-out`. Toolkit-internal: no host action.

### Changed

- E311 is narrowed to an API that declares a `parameters[].enum` without `enum_provenance`; `parameters[].enum` is added to the step 05 schema.
- `registry-check` no longer reports E622 for a registered root collection absent from a spec file; wrong-shape collections and a missing `id_field` still do.
- The W555 message and docs no longer cite a charter `minItems:3` bound. `scripts/generate_fixtures_02a.py` is removed (toolkit-internal).
- `schema/entry_key_registry.schema.json` accepts annotation-derived entries (map-keyed entries without `id_field`, glob keys) and the step `extras` for record-host entries.
- `spec-check` and the canonical checks share one schema registry and cache validators (speed only).

### Fixed

- `schema_nav.effective_schema` keeps keywords that sit beside a `$ref` instead of dropping them; validation results are unchanged.
- Step 13 `governance_label_ref` is no longer checked by E590/W590 against step 10; the label resolves through canon (E110 when unknown) and E210 remains. Hosts with no declared extensions see no change.
