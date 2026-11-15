## [unreleased]

### Added

- `schema/core/graph.schema.json` (`vc:core:graph`): the `x-node` / `x-link` annotation language for declaring graph nodes and links in step schemas. See `docs/developers/schema-annotations.md`. Only `schema/seed_manifest.schema.json` is annotated in this release.
- Annotation reader and lint with `ANNOT-NN` toolkit-author codes, and a step-order derivation (`ANNOT-20` cycle, `ANNOT-21` same-step link). `registry-generate` folds annotated nodes into `entry_key_registry.json`; without annotations the entries are unchanged and `_format_version` is `1.1.0`.
- `tools/cli_commands.json` (generated; `schema/cli_commands.schema.json`) and the `registry-generate` flags `--cli-commands-out` and `--step-order-out`. Toolkit-internal: no host action.

### Changed

- `schema/entry_key_registry.schema.json` accepts annotation-derived entries (map-keyed entries without `id_field`, glob keys).
- `spec-check` and the canonical checks share one schema registry and cache validators (speed only).

### Fixed

- `schema_nav.effective_schema` keeps keywords that sit beside a `$ref` instead of dropping them; validation results are unchanged.
- Step 13 `governance_label_ref` is no longer checked by E590/W590 against step 10; the label resolves through canon (E110 when unknown) and E210 remains. Hosts with no declared extensions see no change.
