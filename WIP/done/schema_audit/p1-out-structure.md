# P1-E: Structure & Registry -- Findings

## Summary
- Total findings: 14
- Critical: 1 | High: 3 | Medium: 5 | Low: 3 | Info: 2

---

## Findings

### FINDING-001: seed_manifest.schema.json missing `$schema` property definition
- **Severity**: CRITICAL
- **Category**: STRUCTURE
- **Location**: `schema/seed_manifest.schema.json` (entire file -- `properties` object, line 7)
- **Description**: The schema sets `"additionalProperties": false` (line 6) but does not define `"$schema"` as a property. The data file `spec/common/seed_manifest.json` includes `"$schema": "https://specdev.local/schema/seed_manifest.schema.json"` (line 2). Strict schema validation rejects this as an unexpected additional property. The validator at `tools/specdev_tools/validation/validate.py:144` strips `$schema` from the payload before validation, masking the error at runtime.
- **Evidence**: Running `jsonschema.validate(manifest, schema)` directly without the strip yields: `Additional properties are not allowed ('$schema' was unexpected)`. The canon schemas (`canon/kind.schema.json:8-11`, `canon/aliases.schema.json:8-11`, `schema/core/canon.schema.json`) correctly define `$schema` as a property.
- **Recommendation**: Add `"$schema": { "type": "string", "format": "uri" }` to the `properties` object of `seed_manifest.schema.json`. Apply the same fix to all 19 step schemas (00 through 16) since spec data files may include `$schema`. This makes the schema self-consistent without relying on the validator's strip workaround.

---

### FINDING-002: No step schema defines `$schema` as a property
- **Severity**: HIGH
- **Category**: STRUCTURE
- **Location**: All 19 step schemas in `schema/` (00_charter through 16_impl_context) -- none include `$schema` in their `properties` object
- **Description**: All step schemas set `"additionalProperties": false` but none define `$schema` as a property. At least 2 spec data files (`spec/05_interface_contracts.json:2`, `spec/common/seed_manifest.json:2`) and 68+ test fixtures include `$schema` URIs. The validator (`validate.py:144`) strips `$schema` before validation, masking the incompatibility. By contrast, the 3 canon schemas (`kind.schema.json`, `aliases.schema.json`, `core/canon.schema.json`) correctly define `$schema` as a property.
- **Evidence**: `for f in schema/*.schema.json; python3 -c "import json; print('\$schema' in json.load(open('$f')).get('properties', {}))"` returns `False` for all 20 files.
- **Recommendation**: Add `"$schema": { "type": "string", "format": "uri" }` to all step schemas' `properties` objects, following the pattern already established in the canon schemas.

---

### FINDING-003: URI naming inconsistency between core/canon schemas and step schemas
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Location**: `tools/schema_registry.json` -- all 29 entries
- **Description**: Two different URI patterns coexist in the registry:
  - **Versioned path pattern** (6 entries): `core/atoms/1`, `core/canon/1`, `core/collections/1`, `core/errors/1`, `canon/aliases/1`, `canon/kind/1` -- uses `/1` version suffix, no file extension
  - **Filename pattern** (23 entries): `00_charter.schema.json`, `seed_manifest.schema.json` -- uses `.schema.json` extension, no version

  The `$id` values in schema files match their registry URIs exactly, so this inconsistency is baked into the `$id` declarations themselves.
- **Evidence**:
  - `schema/core/atoms.schema.json:$id = "https://specdev.local/schema/core/atoms/1"`
  - `schema/00_charter.schema.json:$id = "https://specdev.local/schema/00_charter.schema.json"`
- **Recommendation**: Standardize on one URI pattern. Recommended: versioned path style (`schema/00_charter/1`) for all schemas -- it supports future versioning, is cleaner, and aligns with the core/ convention. This would require updating `$id` in all 20 step schemas, all `$ref` URIs that reference them (if any exist), all `$schema` properties in data/fixture files, and the registry itself.

---

### FINDING-004: 16a/16b/16c share a single schema despite distinct pipeline phases
- **Severity**: HIGH
- **Category**: STRUCTURE
- **Location**: `tools/schema_registry.json:25-27` (16a, 16b, 16c entries all point to `schema/16_impl_context.schema.json`)
- **Description**: Steps 16a (plan), 16b (code), and 16c (review) are distinct pipeline phases with different data expectations:
  - 16a produces `plan` (required)
  - 16b produces `execution` (currently optional in schema)
  - 16c produces `review` (currently optional in schema)

  The single schema marks only `plan` as required, with `execution` and `review` optional. This means a step-16a artifact passes validation even if `execution` and `review` are empty, but a step-16c artifact also passes with empty `execution` and `review` -- no schema enforcement that 16c must include review data.

  `step_order.json` treats 16a/16b/16c as fully distinct steps with different upstream dependencies (lines 250-315) and different downstream consumers (lines 340-343). Each step has its own prompt (`prompts/prompt_16a_*.md`, etc.).
- **Evidence**:
  - Schema `$id`: only `https://specdev.local/schema/16_impl_context.schema.json` -- single identity
  - Registry aliases: `16a_impl_context.schema.json`, `16b_impl_context.schema.json`, `16c_impl_context.schema.json` all resolve to same file
  - Required fields: `["id", "owner", "created_at", ..., "plan"]` -- only `plan` is step-specific required
- **Recommendation**: Create distinct schemas or use `if/then` conditional validation:
  - **Option A (preferred)**: Add `allOf` conditions based on an `id` pattern or a `phase` discriminator field to require `execution` for 16b and `review` for 16c
  - **Option B**: Create `16a_plan.schema.json`, `16b_code.schema.json`, `16c_review.schema.json` as wrappers that `$ref` the shared 16 `$defs` but enforce phase-specific required fields

---

### FINDING-005: Test fixture references non-existent schema `13b_database_schema`
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Location**: `tests/fixtures/step_13/valid_extension.json:$schema`
- **Description**: The test fixture file references `https://specdev.local/schema/13b_database_schema.schema.json`, but no such schema file exists anywhere in the repository. The URI is not in `schema_registry.json`. No file matching `*13b*` exists in the codebase.
- **Evidence**: `find devspec_toolkit -name "*13b*"` returns empty. `schema_registry.json` has no entry for `13b_database_schema`.
- **Recommendation**: Either create the `13b_database_schema.schema.json` schema (if this extension type is planned) or update the test fixture's `$schema` to reference `13_extension_generator.schema.json`.

---

### FINDING-006: Test fixture uses stale relative `$schema` path
- **Severity**: LOW
- **Category**: STRUCTURE
- **Location**: `tests/fixtures/step_00/00_charter.json:$schema`
- **Description**: This test fixture uses a relative file path `../../schema/00_charter.schema.json` instead of the canonical URI `https://specdev.local/schema/00_charter.schema.json`. All other test fixtures use the `specdev.local` URI scheme.
- **Evidence**: `"$schema": "../../schema/00_charter.schema.json"` -- the only file in the entire test suite using a relative path.
- **Recommendation**: Update to `"$schema": "https://specdev.local/schema/00_charter.schema.json"` for consistency.

---

### FINDING-007: Test fixture uses GitHub raw URL instead of local URI
- **Severity**: LOW
- **Category**: STRUCTURE
- **Location**: `tests/fixtures/14_roadmap.json:$schema`
- **Description**: This test fixture references `https://raw.githubusercontent.com/Vichitra-Collective/devspec/main/schema/14_roadmap.schema.json` -- a remote GitHub raw URL instead of the local `specdev.local` URI.
- **Evidence**: This is the only file in the test suite using a GitHub URL for `$schema`. All others use `https://specdev.local/schema/...`.
- **Recommendation**: Update to `"$schema": "https://specdev.local/schema/14_roadmap.schema.json"`.

---

### FINDING-008: 22 of 25 canon/kinds/ data files missing `$schema` property
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Location**: `canon/kinds/` -- 22 files lack `$schema`
- **Description**: Only 3 of 25 kind registry files (`nfr_category.json`, `owner.json`, `trace_type.json`) include `"$schema": "https://specdev.local/schema/canon/kind/1"`. The remaining 22 files have no `$schema` at all. This means the validation pipeline cannot automatically determine which schema governs these data files.
- **Evidence**: Missing `$schema` in: `acronym.json`, `action.json`, `capability.json`, `command.json`, `completeness_dimension.json`, `dependency.json`, `entity.json`, `environment.json`, `event.json`, `governance_label.json`, `id_pattern.json`, `interface.json`, `metric.json`, `policy.json`, `risk_category.json`, `role.json`, `stage.json`, `status.json`, `tag.json`, `tech_stack.json`, `term.json`, `unit.json`.
- **Recommendation**: Add `"$schema": "https://specdev.local/schema/canon/kind/1"` to all 22 files for consistency and to enable schema-based validation.

---

### FINDING-009: Canon schemas live outside `schema/` directory
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Location**: `canon/kind.schema.json` (32 LOC), `canon/aliases.schema.json` (27 LOC)
- **Description**: Two schema files live in `canon/` alongside their data files (`canon/manifest.json`, `canon/aliases.json`, `canon/kinds/`), while all other schemas live in `schema/`. The registry maps them with a different URI path (`canon/aliases/1`, `canon/kind/1`) vs the core schemas (`core/atoms/1`). The co-location of schemas with data was likely intentional (canon schemas validate canon data), but it creates a split where schema files must be looked up in two separate directory trees.
- **Evidence**:
  - Schema files: 24 in `schema/` + 2 in `canon/` = 26 total
  - Registry entries for canon schemas use `canon/` prefix in URI, matching their physical location
  - The `SchemaRegistry` class (`tools/specdev_tools/core/registry.py:30-35`) resolves paths relative to repo root, so moving files would require updating registry entries
- **Recommendation**: Two viable options:
  - **Option A (move)**: Move to `schema/canon/kind.schema.json` and `schema/canon/aliases.schema.json`. Update registry paths. Keep URI unchanged. Pro: single schema directory tree. Con: breaks co-location with canon data.
  - **Option B (keep)**: Accept the split as intentional design -- canon schemas govern canon data and belong near it. Document the convention. Pro: preserves domain locality. Con: developers must look in two places for schemas.

---

### FINDING-010: `schema_registry.json` location in `tools/` is non-obvious
- **Severity**: LOW
- **Category**: STRUCTURE
- **Location**: `tools/schema_registry.json`
- **Description**: The schema registry lives in `tools/` rather than `schema/`. The `SchemaRegistry` class (`tools/specdev_tools/core/registry.py:9-12`) looks for it first at `tools/schema_registry.json`, with a fallback to `schema_registry.json` at repo root. Since the registry is a metadata index of schema files, it could logically live in `schema/` alongside the schemas it indexes.
- **Evidence**:
  - Primary lookup: `os.path.join(self.repo_root, "tools", "schema_registry.json")` (line 9)
  - Fallback: `os.path.join(self.repo_root, "schema_registry.json")` (line 12)
  - Multiple tool modules reference `tools/schema_registry.json` hardcoded (canonical/lint.py:43-44, cli.py:95, prompt_schema_sync.py:336)
- **Recommendation**: Keep in `tools/` for now. Moving it would require updating 6+ tool source files, the registry loader, and documentation. The fallback mechanism already supports alternative locations. If a future restructuring moves all tool config files (step_order.json, schema_registry.json) to a dedicated config location, include it in that batch.

---

### FINDING-011: `step_order.json` lacks a JSON schema for self-validation
- **Severity**: MEDIUM
- **Category**: STRUCTURE
- **Location**: `tools/step_order.json` (no corresponding schema file exists)
- **Description**: `step_order.json` is a critical configuration file consumed by 5+ tool modules (`dependency_order_lint.py`, `dag_lint.py`, `extraction_intent_check.py`, `hallucination_lint.py`, `cli.py`). It defines policy, step ordering, dependency DAGs, coverage thresholds, and downstream consumers. Despite its complexity (344 lines) and criticality, there is no JSON schema to validate its structure. Any typo in a step ID, missing required field, or structural error would only be caught at runtime.
- **Evidence**: `find devspec_toolkit -name "step_order*schema*"` returns empty. No schema file or registry entry exists for step_order.json.
- **Recommendation**: Create `schema/step_order.schema.json` with validation for: version string, policy object structure, steps array (unique kebab IDs), allowed_upstream_dependencies (all referenced steps must exist in `steps` array), downstream_consumers (same constraint), coverage_thresholds structure. Register it in `schema_registry.json`. This is especially important if seed_manifest fields are absorbed into step_order.json (as considered by P1-C).

---

### FINDING-012: Flat schema directory structure adequate for current size
- **Severity**: INFO
- **Category**: STRUCTURE
- **Location**: `schema/` directory (20 flat files + `core/` subdirectory)
- **Description**: The plan asks whether schemas should be grouped into subfolders by phase (e.g., `schema/discovery/`, `schema/impl/`). With 20 step/manifest schemas, the current flat layout is navigable. The natural grouping would be:
  - `schema/discovery/` (00-12, 13 files): charter, capabilities, system_sketch, delivery_baseline, glossary, fr_list, interface_contracts, invariants, nfrs, fixtures, impl_plan, governance, redteam, ci_gates
  - `schema/impl/` (13-16, 6 files): extension_generator, completeness_assessment, roadmap, scaffold, impl_context
  - `schema/manifest/` (1 file): seed_manifest
  - `schema/core/` (4 files): unchanged

  However, this would require updating all `$id` URIs, all `$ref` references, all registry entries, all `$schema` properties in data files (68+ test fixtures, 2+ spec files, 28+ canon data files), and documentation references. The cost far exceeds the benefit at current scale.
- **Evidence**: 20 files in a flat directory with numeric prefixes that provide natural ordering (00-16). The `core/` subdirectory already handles shared definitions.
- **Recommendation**: Do not restructure into subfolders at this time. The numeric prefix naming convention provides sufficient organization. Revisit if schema count exceeds ~40 files.

---

### FINDING-013: Registry is complete -- all schema files registered, no orphan entries
- **Severity**: INFO
- **Category**: STRUCTURE
- **Location**: `tools/schema_registry.json` (29 entries mapping to 26 unique files)
- **Description**: Verification confirms:
  - **All 26 schema files are registered**: 20 step/manifest schemas + 4 core schemas + 2 canon schemas. Every `.schema.json` file has at least one registry entry.
  - **No orphan entries**: All 29 URI-to-path mappings resolve to existing files on disk.
  - **3 alias entries**: 16a, 16b, 16c each map to `schema/16_impl_context.schema.json` (3 aliases + 1 primary = 4 entries for 1 file, accounting for 29 entries vs 26 files).
  - **No unregistered schemas**: No `.schema.json` file in `schema/` or `canon/` lacks a registry entry.
- **Evidence**: Automated check of all 29 entries: `OK` for every entry. Cross-check of all `.schema.json` files on disk: every file's `$id` matches a registry key.
- **Recommendation**: No action needed. Registry is complete and internally consistent.

---

### FINDING-014: URI change impact assessment -- 93+ files would need updating
- **Severity**: HIGH
- **Category**: STRUCTURE
- **Location**: All files containing `$schema` properties or `$ref` URIs referencing `specdev.local`
- **Description**: If schema URIs are changed (per ALIGN-2 in the research roadmap, or per FINDING-003 URI normalization), the following files would need updating:
  - **Schema files** (26): Update `$id` declarations and all `$ref` URIs
  - **Schema registry** (1): `tools/schema_registry.json` -- all 29 entries
  - **Spec data files** (2): `spec/05_interface_contracts.json`, `spec/common/seed_manifest.json`
  - **Canon data files** (4): `canon/manifest.json`, `canon/aliases.json`, plus 3 kind files with `$schema`
  - **Test fixture files** (60+): All files under `tests/fixtures/` with `$schema` properties
  - **Tool source code** (6+): Any hardcoded URI references in Python modules

  Total estimated: 93+ files across 5 file categories.
- **Evidence**:
  - 23 unique `$schema` URI values found across data files
  - 448 `$ref` URIs across schema files referencing `specdev.local`
  - 68+ test fixtures with `$schema` properties
- **Recommendation**: Any URI scheme change must be done as a single atomic batch with a migration script. Create a `migrate_uris.py` script that:
  1. Reads old-to-new URI mapping
  2. Updates `$id` in all schema files
  3. Updates `$ref` in all schema files
  4. Updates `$schema` in all data/fixture files
  5. Updates `schema_registry.json`
  6. Runs `pytest tests/ -x` as a gate

  Do NOT attempt manual URI changes across 93+ files.
