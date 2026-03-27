# Batch 5 Review (FIX-046 through FIX-052)

**Reviewer**: Claude Opus 4.6
**Date**: 2026-03-19
**Test suite**: 1271 passed, 0 failed (41.73s)

---

## FIX-046: $schema property in seed_manifest.schema.json

**Status**: PASS

- `$schema` property added at line 8 of `schema/seed_manifest.schema.json`
- Type: `string`, format: `uri`, with description
- Schema has `additionalProperties: false` at line 6, AND `$schema` is listed inside `properties` -- so it will NOT be rejected
- `$schema` is correctly NOT in the `required` array (optional, as expected)

## FIX-047: $schema in canon/kinds/*.json files

**Status**: PASS

- All 25 canon/kinds files have `$schema` property:
  acronym, action, capability, command, completeness_dimension, dependency, entity, environment, event, governance_label, id_pattern, interface, metric, nfr_category, owner, policy, risk_category, role, stage, status, tag, tech_stack, term, trace_type, unit
- 25/25 covered, 0 missing

## FIX-048: Stale 13b $schema reference in test fixture

**Status**: PASS

- No `13b` reference remains in any JSON file under `tests/` or anywhere in the repo
- Only mention is in the WIP fix-plan document (describing the fix itself)
- All step_13 fixtures now reference `13_extension_generator.schema.json`

## FIX-049: Relative $schema path in test fixture

**Status**: PASS

- Searched all JSON files for relative `$schema` patterns (`../schema`, `./schema`)
- Zero matches found -- all `$schema` URIs use canonical `https://specdev.local/schema/` prefix

## FIX-050: GitHub raw URL $schema in test fixture

**Status**: PASS

- Searched all JSON files for `raw.githubusercontent` patterns
- Zero matches found -- no GitHub raw URLs remain

## FIX-051: schema/step_order.schema.json

**Status**: PASS (with one advisory note)

### Structural validation
- Every field in `tools/step_order.json` has a corresponding schema property: `version`, `_notes`, `policy`, `steps`, `allowed_upstream_dependencies`, `coverage_thresholds`, `downstream_consumers` (7/7)
- No fields in data missing from schema, no fields in schema missing from data
- `allowed_upstream_dependencies` is correctly NOT in `required` array (optional, per spec)
- All 7 properties have descriptions
- `policy` sub-properties all have descriptions and correct types
- `steps` items pattern `^[0-9]{2}[a-c]?$` correctly matches all step IDs including suffixed ones
- `coverage_thresholds` has `required: ["fr_coverage", "mode"]` with proper constraints

### Runtime validation
- `python -c "from jsonschema import validate; validate(data, schema)"` -- **OK**, no errors

### Advisory: Draft version mismatch
- `step_order.schema.json` uses `draft-07/schema#` while all other schemas in the repo use `draft/2020-12/schema`
- This is functionally correct (draft-07 is sufficient for the constructs used) but is an inconsistency
- Recommend aligning to `draft/2020-12/schema` in a future cleanup pass for uniformity

## FIX-052: 16a/16b/16c phase discrimination in Step 16 schema

**Status**: PASS

### Structure
- Two `if/then` blocks added at the end of the top-level `allOf` array (lines 2036-2063)
- Block 1 (16b): if `id` matches `^16b-`, then `required: ["execution"]`
- Block 2 (16c): if `id` matches `^16c-`, then `required: ["execution", "review"]`
- Both `execution` (line 1342) and `review` (line 1575) are defined as top-level properties in the schema

### Phase logic correctness
- **16a** (plan only): No additional if/then -- only base `required` applies (`plan` is in base required). Correct.
- **16b** (code): Requires `execution` in addition to base. Correct -- code phase must provide execution evidence.
- **16c** (review): Requires both `execution` AND `review`. Correct -- review phase must show both execution and review evidence.

### Integration safety
- The if/then blocks are appended to the existing `allOf` array, which already contains the `$ref` to `step_base` and the main properties object
- They do not interfere with existing structure -- they only add conditional requirements
- The `unevaluatedProperties: false` at line 2065 is compatible with the if/then pattern in draft 2020-12

## FIX: Missed items check

**Status**: PASS

- No stale `13b` $schema references remain anywhere
- No relative `$schema` paths in any JSON file
- No `raw.githubusercontent` URLs in any JSON file
- All test fixture `$schema` URIs use canonical `https://specdev.local/schema/` format

---

## Summary

| FIX | Description | Verdict |
|-----|-------------|---------|
| 046 | $schema in seed_manifest schema | PASS |
| 047 | $schema in 25 canon/kinds files | PASS |
| 048 | Stale 13b $schema in fixture | PASS |
| 049 | Relative $schema in fixture | PASS |
| 050 | GitHub raw URL $schema in fixture | PASS |
| 051 | step_order.schema.json | PASS (advisory: draft-07 vs 2020-12 mismatch) |
| 052 | 16a/16b/16c phase discrimination | PASS |

**Overall**: All 7 fixes verified correct. 1271 tests passing. One advisory note on draft version consistency for FIX-051.
