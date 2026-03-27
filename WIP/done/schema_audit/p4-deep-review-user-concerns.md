# P4 Deep Review: User Concerns Q3-Q6

**Date**: 2026-03-19
**Reviewer**: Independent architectural review
**Method**: Read all source files, consumers, spec files, test fixtures, and prompts. Formed assessment from actual code, not from audit summaries.

---

## Q3: generation_quality -- Does This Solve Anything?

### What the Audit Concluded (and Why It Is Insufficient)

The audit (FINDING-C03, MEDIUM) concluded: "Keep `generation_quality` as required -- it is actively consumed by 2 modules, is a drift-sensitive field, and prompt contracts depend on it." The audit treated "is consumed" as sufficient justification. It did not examine whether the field carries actual signal.

### Independent Assessment

**What is it?** An object with one property: `{"assumptions": []}`. Defined in `schema/core/collections.schema.json` (lines 380-392) as `generationQuality` with `additionalProperties: false` and `required: ["assumptions"]` where `assumptions` is a `stringArray`.

**What do the consumers actually do?**

1. `spec_quality_lint.py:180` -- Checks that the key `generation_quality` EXISTS in the top-level object. Does not read or validate its contents. It just checks `if key not in data` and emits E520 if missing. This is a pure presence check.

2. `prompt_schema_sync.py:27` -- Lists `generation_quality` in `DRIFT_SENSITIVE_FIELDS`. This means prompt-schema sync verifies the JSON Schema definition of `generation_quality` in prompt files matches the schema definition. It validates structure consistency, not value.

Neither consumer reads `generation_quality.assumptions` or does anything with the string values inside. The actual assumptions checking logic in `spec_quality_lint.py` (lines 114-146, the `_check_assumptions` function) operates on a *different* field -- top-level `assumptions` arrays found anywhere in the JSON tree, not `generation_quality.assumptions`.

**What does real data look like?**

- `spec/05_interface_contracts.json`: `"generation_quality": {"assumptions": []}`
- Every single test fixture (40+ files examined): `"assumptions": []`
- Every prompt contract instructs the AI to populate it, but the toolkit's own spec files and all test fixtures show empty arrays.
- A migration script `strip_generation_quality.py` already stripped it down from something larger, confirming even its prior incarnation was deemed excess.

**The core problem**: `generation_quality` is a wrapper object containing a single array that is always empty. The schema requires this wrapper in all 19 step schemas, adding boilerplate to every spec file, every test fixture, and every prompt contract. The two consumers only check structural presence -- they never extract value from it.

**Could it be removed?** Yes. The actual cost:
- Remove from `DRIFT_SENSITIVE_FIELDS` in `prompt_schema_sync.py` (1 line)
- Remove from `_check_required_top_level` in `spec_quality_lint.py` (1 line)
- Remove from `required` array in 19 step schemas
- Remove property definition from 19 step schemas
- Update 24+ prompt files to remove the field from output contracts
- Update 40+ test fixtures to remove the field
- `generationQuality` definition can stay in `core/collections.schema.json` (no harm)

**Could it be simplified instead?** If you want to keep the concept, promote `assumptions` to a top-level array: `"generation_assumptions": []`. But this still does nothing -- no consumer reads the values.

### Recommendation: REMOVE

**Verdict**: NO/REMOVE

`generation_quality` is architectural theater. It mandates a wrapper object in every spec file, but nothing in the toolchain extracts meaning from it. The `_check_assumptions` function that actually validates assumption text (vague language, unbound IDs, placeholder detection) operates on a completely different `assumptions` field -- the step-specific one (e.g., `00_charter.schema.json`'s top-level `assumptions` array). The `generation_quality.assumptions` array is a dead-end.

**Specific actions:**
1. Remove `"generation_quality"` from `DRIFT_SENSITIVE_FIELDS` in `prompt_schema_sync.py`
2. Remove `"generation_quality"` from the checked keys in `spec_quality_lint.py:175-183`
3. Remove `generation_quality` from `required` arrays and `properties` in all 19 step schemas
4. Update prompt output contracts (24+ files) to remove the field
5. Update test fixtures (40+ files) to remove the field
6. Leave `generationQuality` definition in `core/collections.schema.json` (dormant, no harm)

**Impact**: Zero functional impact. No validator reads assumption values from this field. No downstream tool breaks.

**Effort**: ~2 hours mechanical work (sed/script across files). Low risk.

---

## Q4: seed_manifest.json -- Is This Required At All?

### What the Audit Concluded (and Why It Is Insufficient)

The audit (FINDING-C11, MEDIUM) concluded: "Keep them separate. seed_manifest lives in spec/common/ (project data) while step_order.json lives in tools/ (toolkit config). Different lifecycles." The audit also marked docs_policy as WONTFIX (AUDIT-044). This answered "should they merge?" but not "is seed_manifest over-engineered?"

### Independent Assessment

**What does seed_manifest.json actually contain?** (83 lines total)

1. **Metadata** (lines 2-6): `$schema`, `seed_manifest_id`, `version`, `created_at`, `last_updated` -- Standard envelope. Minimal overhead.

2. **global_seed_order** (lines 7-10): Array of 2 seed IDs. Consumed by `seed_lint.py:259-261` for referential integrity and by `_collect_required_seeds` to union with step-specific seeds.

3. **nested_order** (lines 11-20): Single "foundation" layer with the same 2 seeds. Consumed by `seed_lint.py:263-266` for referential integrity only. Currently adds zero value beyond `global_seed_order`. The audit (FINDING-C06) acknowledged this.

4. **seeds** (lines 21-36): Registry of 2 seed documents with `seed_id`, `path`, `description`, `required`, `source_type`. Consumed by `seed_lint.py` for path validation, existence checks, duplicate detection, and content overlap analysis. **This is the core value of seed_manifest.**

5. **step_requirements** (lines 37-57): Maps steps to their required seeds (e.g., step 00 requires both seeds, step 01 requires only seed-overview). Consumed by `seed_lint.py:48-63` via `_collect_required_seeds()` to validate that spec files reference the correct seeds. **This is real, non-derivable data.**

6. **docs_policy** (lines 58-82): README requirements, scope, exclusions, doc_paths. Consumed by `docs_lint.py:46-52` and `step_16.py:180`. **Semantically misplaced** -- this is documentation governance config, not seed metadata.

**Is step_requirements duplicating step_order.json?** No. `step_order.json` defines pipeline ordering and dependency structure. `step_requirements` maps steps to *which seeds they need*. This is orthogonal data -- you cannot derive "step 04 needs seed-overview but not seed-tech-stack" from pipeline ordering.

**Is allowed_upstream_dependencies derivable from step order?** I examined the actual data. Every step's `allowed_upstream_dependencies` is exactly the list of all preceding steps in the `steps` array. Step 00 has `[]`, step 01 has `["00"]`, step 02 has `["00", "01"]`, etc. This is a strict prefix of the steps array.

**This means `allowed_upstream_dependencies` IS 100% derivable** from `steps` + the `strict_waterfall` policy. For 22 steps, that is 253 entries that could be computed at runtime. However, 5 consumers load it, and making it explicit allows for future deviation from strict waterfall (e.g., a step that should NOT see certain predecessors). The data is currently redundant but serves as a declaration of intent.

**Is docs_policy over-engineered?** Looking at what `docs_lint.py` does with it:
- `readme_required: true` -- could be convention (always require READMEs)
- `root_readme_required: true` -- could be convention
- `readme_depth_default: 0` -- configurable depth; convention would work (default 0 or 1)
- `readme_depth_by_scope: {}` -- empty, unused
- `scope: ["devspec_toolkit/"]` -- this IS project-specific, hard to convention-ify
- `exclusions: [...]` -- 8 exclusion paths; definitely project-specific

So `scope` and `exclusions` justify having a config object. `readme_required` and `readme_depth_default` could be conventions with overrides, but the current approach is cleaner.

**Is coverage_thresholds worth a dedicated section?** It has `{"fr_coverage": 80, "mode": "warn"}` -- 2 fields consumed by `matrix.py:301-357`. The `mode` field (warn vs. error) is genuinely useful for CI configuration. A single threshold does not justify a dedicated config section on its own, but `mode` makes it more than "1 threshold."

**Should seed_manifest + step_order merge?** No. The audit's lifecycle argument is correct. `seed_manifest.json` lives in `spec/common/` and varies per project. `step_order.json` lives in `tools/` and is toolkit infrastructure. Merging them conflates user data with toolkit config.

### Recommendation: SIMPLIFY (3 specific actions)

**Verdict**: SIMPLIFY

seed_manifest.json is architecturally justified as a separate file. But it carries unnecessary weight:

**Action 1: Remove `nested_order` from required, make optional.**
- Currently identical to `global_seed_order` for this project
- `seed_lint.py:263-266` does a simple referential integrity check that adds nothing beyond what `global_seed_order` already gets (lines 259-261)
- Make it optional in `seed_manifest.schema.json`; keep the property definition
- Effort: 5 minutes. Impact: Zero -- single consumer gracefully handles missing via `.get("nested_order", [])`

**Action 2: Move `docs_policy` out of seed_manifest.** (Deferred -- WONTFIX is reasonable for now)
- Semantically it does not belong in seed metadata
- But 2 consumers work correctly, and migration cost exceeds benefit
- Revisit when/if a `project_config.json` concept is introduced

**Action 3: Consider computing `allowed_upstream_dependencies` at runtime.**
- Every entry is a strict prefix of the `steps` array -- it is 100% derivable
- Could add a `compute_allowed_upstream(steps, step_id)` utility function
- 5 consumers would call this instead of loading the JSON
- Saves 250+ lines of pure redundancy in `step_order.json`
- Risk: If the policy ever deviates from strict waterfall, you need the explicit data back. Mitigation: keep `policy.mode: "strict_waterfall"` as the signal to compute, with optional explicit overrides.
- Effort: Medium (~1 day). Impact: 5 consumer updates + step_order.json cleanup.

**Impact of Action 1**: Remove `nested_order` from `required` in schema. Zero consumer impact.
**Impact of Action 3**: 5 files updated to call a utility function. step_order.json shrinks from 345 lines to ~80 lines.

---

## Q5: seed_refs, spec_refs_ingested -- Needed in Schema?

### What the Audit Concluded (and Why It Is Insufficient)

The audit confirmed `spec_refs_ingested` is dead (FINDING-C01, HIGH -- zero consumers). For `seed_refs`, it was implicitly kept because `seed_lint.py` consumes it. The audit did not question whether `seed_refs` provides proportional value.

### Independent Assessment

**spec_refs_ingested: Confirmed dead.** Zero consumers in `tools/specdev_tools/`. Not in `DRIFT_SENSITIVE_FIELDS`. Not checked by `spec_quality_lint.py`. Every instance is `[]`. The audit was right -- remove it.

**seed_refs: What does it actually do?**

`seed_refs` is an array of `seedRef` objects in each spec file, declaring which seed documents informed that step's generation. Here is what `seed_lint.py` does with it (lines 277-312):

1. Reads `seed_refs` from each spec JSON
2. Validates that referenced `seed_id` values exist in the manifest (`seed_id_set`)
3. Checks that ALL required seeds for that step are present (via `_collect_required_seeds`)
4. Runs content overlap analysis (`_check_seed_content_overlap`) -- tokenizes the spec and seed, warns if shared tokens < 3

**What does seed_refs look like in practice?**

- `spec/05_interface_contracts.json`: `"seed_refs": []` -- Empty despite being step 05 (which likely should reference seeds)
- `tests/fixtures/step_00/00_charter.json`: Has `seed_refs` with 2 entries, seed_id only -- no hash, no path, no section, no note
- `tests/fixtures/step_04/valid_comprehensive.json`: Has `seed_refs` with 2 entries, seed_id only

The `seedRef` schema supports rich metadata (`seed_id`, `path`, `section`, `note`, `hash`, `version`) but in practice only `seed_id` is populated. The hash verification feature (SHA-256 of seed at ingestion time) is never used in any real data.

**Is seed_lint validation providing real value?**

Yes, partially. The step_requirements cross-check (ensuring step 00 references both required seeds) catches real errors where an AI generates a spec without reading required inputs. The content overlap check is a lightweight hallucination detection signal. These are genuine guardrails.

However, the mechanism of embedding `seed_refs` in every spec file is ceremony-heavy for the validation payoff. The alternative: `seed_lint` could check whether the step's prompt references the correct seeds (it already does this in `_lint_prompt_manifest_refs`) and skip the per-artifact embedding entirely.

**Could seed traceability work without embedding refs in every spec?**

Partially. The prompt-level check (`_lint_prompt_manifest_refs`) already validates that prompts reference `seed_manifest.json` and include "Seed Order & Mandatory Sources" sections. This ensures the AI *receives* the right seeds. The per-artifact `seed_refs` is supposed to confirm the AI *used* them, but in practice the AI just emits `[{"seed_id": "seed-overview"}, {"seed_id": "seed-tech-stack"}]` because the prompt tells it to -- it is not genuine attestation.

The content overlap check (`_check_seed_content_overlap`, lines 129-170) does add value -- it verifies the spec output actually contains tokens from the referenced seeds. But this check only needs the `seed_id` from `seed_refs`, not the full `seedRef` object schema with hash/path/section/note/version.

### Recommendation: SIMPLIFY

**Verdict**: SIMPLIFY (two-part)

**Part A: Remove `spec_refs_ingested`** -- Confirmed dead. Remove from all 19 schemas, all fixtures, all prompts.
- Effort: ~1 hour (scripted removal)
- Impact: Zero. No consumer exists.

**Part B: Simplify `seed_refs` to a string array** -- Instead of `seedRef` objects with 6 optional fields (only `seed_id` ever populated), make `seed_refs` a simple `string[]` of seed IDs:
```json
"seed_refs": ["seed-overview", "seed-tech-stack"]
```
instead of:
```json
"seed_refs": [{"seed_id": "seed-overview"}, {"seed_id": "seed-tech-stack"}]
```

This preserves all current validation (seed_lint reads only `seed_id`) while eliminating the unused `hash`, `path`, `section`, `note`, `version` fields from the schema.

**What breaks:**
- `seed_lint.py:300`: Currently reads `ref.get("seed_id")` -- needs to handle strings directly
- `seed_lint.py:154-158`: Content overlap reads `ref.get("seed_id")` -- same change
- `core/collections.schema.json`: `seedRef` and `seedRefArray` definitions need updating
- 19 step schemas: No change needed (they reference `seedRefArray`)
- Test fixtures: Update `seed_refs` format in ~20 files
- Prompt files: Update output contract examples in ~24 files

**Effort**: ~3 hours. Medium risk (schema change + consumer updates).

**Alternative (lower effort)**: Keep `seed_refs` as-is but remove `hash`, `path`, `section`, `note`, `version` from the `seedRef` schema definition since they are never populated. Make `seedRef` just `{"seed_id": "<kebabId>"}` with `additionalProperties: false`. This is a smaller change that still eliminates dead schema surface.

---

## Q6: Do We Need So Much Canonical Machinery in Every Schema?

### What the Audit Concluded (and Why It Is Insufficient)

The audit (FINDING-C10, MEDIUM) concluded: "The canonical triad is NOT bloat -- it is well-consumed by 5 modules." The audit treated consumer count as a proxy for value. It did not examine whether the data is ever populated or whether mandatory status is justified.

### Independent Assessment

**The canonical triad**: Every step schema requires three arrays:
1. `canonical_refs_used` -- Array of `canonicalRef` objects listing all `cn:` IDs used in the spec
2. `canonical_proposals` -- Array of `canonicalProposal` objects for new terms needing canonical registration
3. `canonical_conflicts` -- Array of `canonicalConflict` objects for ambiguous term resolutions

**What does real data look like?**

I searched all JSON files in the entire repository:

- `canonical_refs_used`: Populated with real data in `spec/05_interface_contracts.json` (3 refs) and `tests/fixtures/step_00/00_charter.json` (2 refs). Empty `[]` in all other fixtures.
- **`canonical_proposals`: NEVER non-empty.** Zero files in the entire repo contain a non-empty `canonical_proposals` array. I searched for `"canonical_proposals": [{` across all JSON files -- zero matches.
- **`canonical_conflicts`: NEVER non-empty.** Same result -- zero files contain actual conflict data.

This is the critical finding: `canonical_proposals` and `canonical_conflicts` are schema infrastructure that has never been exercised with real data.

**What do the 5 consumer modules actually do with these fields?**

1. `canonical/integrity.py:299-300` -- Builds a `_proposal_index` and `_conflict_index` from these fields. These indexes are used to suppress E210 "unresolved_canonical_semantic" errors. If a field lacks a `*_ref` companion but has a matching proposal or conflict entry, the error is suppressed. Since proposals and conflicts are always empty, this suppression logic has never fired on real data.

2. `canonical/integrity.py:182-186` -- Validates `canonical_refs_used` completeness. Compares declared refs against actually-used `cn:` IDs in the document. This IS exercised and catches real drift (missing or extra canonical refs).

3. `canonical/autofix.py:60,331-355` -- Reads and modifies `canonical_refs_used` to auto-sync it with actual `cn:` IDs found in the document. Does NOT touch proposals or conflicts.

4. `spec_quality_lint.py:181-183` -- Checks presence of all three fields. Pure existence check.

5. `prompt_schema_sync.py:28-30` -- All three in `DRIFT_SENSITIVE_FIELDS`. Structural sync check.

6. `step_13.py:101` -- Reads `canonical_refs_used` for extension ref validation.

**Summary of actual utility:**

| Field | Consumer Count | Non-empty in Real Data | Provides Value |
|---|---|---|---|
| `canonical_refs_used` | 4 (integrity, autofix, step_13, quality) | Yes (2 files) | YES -- catches ref drift |
| `canonical_proposals` | 1 (integrity, for suppression) | Never | NO -- suppression logic never fires |
| `canonical_conflicts` | 1 (integrity, for suppression) | Never | NO -- suppression logic never fires |

**Boilerplate cost**: Every spec file must include:
```json
"canonical_refs_used": [],
"canonical_proposals": [],
"canonical_conflicts": []
```
That is 3 required arrays x 19 schemas x every test fixture and prompt. The proposals and conflicts arrays add ~20 lines of boilerplate per spec file (the empty arrays plus the schema definitions that mandate their structure).

**Could canonical_proposals and canonical_conflicts be made optional?**

Yes. The consumers already handle them gracefully:
- `_proposal_index()` returns empty set if value is not a list
- `_conflict_index()` returns empty set if value is not a list
- `spec_quality_lint.py` would need the key removed from its check list
- `prompt_schema_sync.py` would need them removed from `DRIFT_SENSITIVE_FIELDS`

**What would break?**

If a future spec *does* have a canonical conflict, the `canonical/integrity.py` suppression logic would still work if the field is present -- it just would not be required. The only risk is that an AI-generated spec might omit the field even when it has conflicts, causing false-positive E210 errors. This is acceptable: the AI can be instructed to include these fields when relevant, without mandating empty arrays everywhere.

### Recommendation: SIMPLIFY

**Verdict**: SIMPLIFY (keep `canonical_refs_used` required, make `canonical_proposals` and `canonical_conflicts` optional)

**Specific actions:**

1. **Keep `canonical_refs_used` as required.** It is actively consumed by 4 modules, populated with real data, and catches genuine drift. Justified.

2. **Remove `canonical_proposals` from `required` in all 19 step schemas.** Keep as optional property.
   - Remove from `spec_quality_lint.py:182` checked keys
   - Remove from `DRIFT_SENSITIVE_FIELDS` in `prompt_schema_sync.py`
   - Keep property definition in schemas (optional, not required)
   - Keep `canonicalProposal` and `canonicalProposalArray` in `core/collections.schema.json`
   - Update prompts: "Include `canonical_proposals` only if you encounter terms needing canonical registration"

3. **Remove `canonical_conflicts` from `required` in all 19 step schemas.** Same treatment as proposals.
   - Remove from `spec_quality_lint.py:183` checked keys
   - Remove from `DRIFT_SENSITIVE_FIELDS`
   - Keep property definition in schemas (optional, not required)

4. **Update test fixtures**: Remove `"canonical_proposals": []` and `"canonical_conflicts": []` from all fixtures that have empty arrays. ~40 files.

5. **Update prompt output contracts**: Remove empty arrays from output contract JSON blocks. ~24 files.

**What breaks:**
- `canonical/integrity.py` -- No code change needed. `_proposal_index` and `_conflict_index` already handle missing fields gracefully (return empty sets).
- `canonical/autofix.py` -- No code change needed. Does not touch proposals/conflicts.
- `spec_quality_lint.py` -- Remove 2 keys from the check list (2 lines).
- `prompt_schema_sync.py` -- Remove 2 entries from `DRIFT_SENSITIVE_FIELDS` (2 lines).
- 19 step schemas -- Remove from `required` array only (keep in `properties`).
- Test fixtures -- Remove empty arrays (~40 files, scriptable).
- Prompts -- Update output contracts (~24 files, scriptable).

**Effort**: ~3 hours (mostly scripted file updates). Low risk.

**Net result**: Every spec file loses 2 lines of mandatory boilerplate. The canonical system retains its full capability (proposals and conflicts work when present) but stops mandating ceremony when there is nothing to declare.

---

## Summary Table

| Question | Audit Verdict | Independent Verdict | Recommendation | Effort |
|---|---|---|---|---|
| Q3: generation_quality | KEEP (2 consumers) | REMOVE (consumers check presence only; value always empty) | Remove from all schemas, prompts, fixtures | ~2 hours |
| Q4: seed_manifest.json | KEEP separate (correct) | SIMPLIFY (make `nested_order` optional; consider computing `allowed_upstream_deps`) | 2 actions: optional nested_order + upstream deps computation | 5 min + 1 day |
| Q5: seed_refs / spec_refs_ingested | spec_refs dead; seed_refs keep | REMOVE spec_refs; SIMPLIFY seed_refs to string array or strip unused fields | Remove dead field; simplify schema | 1h + 3h |
| Q6: canonical triad | KEEP all 3 required | SIMPLIFY (keep canonical_refs_used required; make proposals+conflicts optional) | Remove 2 fields from required in 19 schemas | ~3 hours |

**Total estimated savings:**
- Schema surface: ~200 lines removed from required arrays across 19 schemas
- Test fixture boilerplate: ~300 lines removed across 40+ files
- Prompt boilerplate: ~150 lines removed across 24+ files
- step_order.json: ~250 lines removable if upstream deps are computed
- Zero functional regressions (all consumers handle missing optional fields gracefully)
