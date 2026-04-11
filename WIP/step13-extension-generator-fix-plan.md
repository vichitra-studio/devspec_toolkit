# Step 13 Extension Generator — Hardening Plan (Expanded: Full Toolkit Drift Sweep)

**Status**: Re-planned 2026-04-09. Reviewed + simplified 2026-04-10. Scope expanded from "step 13 hardening" to "eliminate all discovered drift / tech debt in the toolkit while fixing step 13." Execution pending.
**Branch**: `codex/canonical-drift-review-plan`. Commit tag for this phase: `[phase-1-seed-spec]`.
**Scope owner**: Shantanu (VC website host repo).
**Scope mandate**: eliminate tech debt; keep toolkit coherent and consistent; introduce no regressions; introduce no new drift; strengthen the toolkit. Pre-existing rot surfaced during execution is in scope.

**Finding set** — 21 findings after 2026-04-10 verification pass (prior F2/F11/F12/F13/F14/F22/F23/F24 collapsed into a single driver-table finding **FC — Canonical Ref Prose→Const Sweep**; F28 added from V22 resolution):

- **F1, F3–F10**: original step 13 hardening (schema, prompt, canon, fixtures, validator, docs)
- **FC**: canonical-ref prose→const sweep across every drift site (replaces F2/F11–F14/F22–F24)
- **F15**: bridge test rot repair (steps 03–10, 15 → strict `{0}`)
- **F16 + F25**: `canon-schema-alignment` detector enhancement — prose/const drift (E553/E554/W555) + example ID/kind shelf mismatch (E556) + narrowing-enum recognition (F19)
- **F17**: `context structure` split `canon_kinds_needed` → required + optional
- **F18**: `schema_differ.py` stale comment cleanup
- **F19**: W552 unregistered enum pairings (4 real, 1 false positive resolved via detector enhancement)
- **F20**: W597 vague extraction intent on `prompt_11`
- **F21**: schema audit false-PASS process fix
- **F26**: replace fake `tests/integration/test_step_13.py` with real-validator wrapper
- **F27**: rewrite stale `canonicalRef.kind` description in `schema/core/collections.schema.json`
- **F28**: refactor `step_13.py:_load_governance_labels()` to accept `spec_dir` override (SoC fix; unblocks F8 Part C)

**Prerequisite reads for executing agent**:
- `/Users/vichitracollective/vc-code/vc_wesbite/CLAUDE.md` (branch strategy, commit format)
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/CLAUDE.md` (CLI usage, `--repo-root`)
- `devspec_toolkit/docs/prompts/shared_expectations.md`
- `devspec_toolkit/prompts/prompt_13_extension_generator.md`
- `devspec_toolkit/docs/developers/extension_schemas.md`

---

## 1. Origin of This Work

Started from a concrete product question:

> "Do we need any Step 13 extensions for the VC website (MVP localhost Ghost blog)?"

Answering that honestly required `/specdev-context 13` and scanning every candidate extension domain. The conclusion — **no extensions are warranted** — could not be emitted under the current schema (`minItems: 1`), because a chain of coordinated defects in step 13's schema/prompt/canon/validator/fixtures makes "none-required" an unexpressible state. The fix was scoped to the toolkit, not worked around per-project.

### 1.1 Why "None Required" for VC Website

| Domain | Evidence | Decision |
|---|---|---|
| Data | SQLite owned by Ghost; zero custom schemas | Reject |
| Security | `spec/07_nfrs.json` has 0 NFRs in `security`/`compliance` (17 NFRs total, all latency/usability/availability/durability/maintainability/portability/throughput) | Reject |
| AI/ML | Not in charter, capabilities, or tech stack | Reject |
| Infrastructure | Phase 2 deferred per charter | Reject |
| Integration | Zoho SMTP, YouTube oEmbed, GitHub SCM — all trivial | Reject |

None qualify per the prompt's "≥3 dedicated schema sections" filter. That single honest answer exposed the step 13 defect chain.

---

## 2. Investigation Methodology

All findings verified read-only before committing to fixes. Commands run from `/Users/vichitracollective/vc-code/vc_wesbite` with `--repo-root ./devspec_toolkit`:

```bash
./tools/run_specdev.sh context structure spec --step 13
./tools/run_specdev.sh context canon --step 13 --spec-root ./spec
./tools/run_specdev.sh canon-schema-alignment
./tools/run_specdev.sh extraction-intent-check
./tools/run_specdev.sh canonical-integrity spec --spec-root ./spec --git-root .
./tools/run_specdev.sh validate devspec_toolkit/tests/fixtures/step_13/valid_manifest.json
```

Raw output is in **Appendix A — Evidence**.

---

## 3. Confirmed Findings

### F1 — Schema `minItems` contradicts prompt "return empty array"

**File**: `devspec_toolkit/schema/13_extension_generator.schema.json`

**Bug**: `extensions` has `minItems: 1`, but the prompt's Negative Constraints says *"If no complex domains are found, return empty array."* Both "author never thought about extensions" and "author actively concluded none needed" currently fail identically.

**Fix**:
1. Change `extensions.minItems` from `1` to `0`.
2. Add required sibling `extension_decision` (name locked):
   ```json
   "extension_decision": {
     "type": "object",
     "additionalProperties": false,
     "required": ["status", "rationale"],
     "properties": {
       "status": { "type": "string", "enum": ["extensions-required", "none-required"] },
       "rationale": {
         "type": "string",
         "minLength": 40,
         "description": "For 'none-required', must cite component_ids from 02_system_sketch.json AND NFR categories from 07_nfrs.json evaluated and ruled out."
       }
     }
   }
   ```
3. Add an `allOf` conditional. **Defensive form** (ensures `if` cannot pass vacuously when status is absent):
   ```json
   "allOf": [
     {
       "if": {
         "required": ["extension_decision"],
         "properties": {
           "extension_decision": {
             "required": ["status"],
             "properties": { "status": { "const": "none-required" } }
           }
         }
       },
       "then": { "properties": { "extensions": { "maxItems": 0 } } }
     },
     {
       "if": {
         "required": ["extension_decision"],
         "properties": {
           "extension_decision": {
             "required": ["status"],
             "properties": { "status": { "const": "extensions-required" } }
           }
         }
       },
       "then": { "properties": { "extensions": { "minItems": 1 } } }
     }
   ]
   ```
4. Keep `extensions` in top-level `required[]`; add `extension_decision` to `required[]`.

---

### F3 — Prompt Output Contract example is minimal and misleading

**File**: `devspec_toolkit/prompts/prompt_13_extension_generator.md`

**Bugs**:
1. Output Contract example shows only 6 of 11 schema fields (missing `justification`, `schema_design_guidelines`, `verification_rules`, `tag_ref`, `policy_ref`, `id_pattern_ref`). An author who copies verbatim produces output the validator rejects.
2. Example references non-existent `cn:core:governance_label:mandatory`.
3. Prompt does not document the dual-check architecture (canon + step 10 `canonical_refs_used`).
4. Prompt Negative Constraint contradicts schema (*"return empty array"* vs `minItems: 1`).

**Fix**:
1. Rewrite Output Contract with **two** complete examples:
   - **Example A — populated**: every field present, realistic values, valid canonical IDs (use `cn:core:governance_label:mandatory` once F4 lands).
   - **Example B — none-required**: `extensions: []`, `extension_decision: { status: "none-required", rationale: "..." }` citing ≥2 component_ids and ≥1 NFR category.
2. Rewrite first Negative Constraints bullet to reference `extension_decision.status = 'none-required'`.
3. Add subsection **"Governance Label Resolution"** (dual-check):
   > *"`governance_label_ref` is dual-checked. The referenced canonical ID must exist in BOTH (a) `devspec_toolkit/canon/manifest.json` (verified by `canonical-integrity`, error code per validator — executing agent verifies actual code before pasting); AND (b) `spec/10_governance.json.canonical_refs_used` (verified by `step_13.py`)."*
   
   **Verification step**: before shipping prose with hardcoded error codes, confirm the actual codes emitted by running `validate` against a deliberate-miss fixture. Appendix A §4 confirms E110. The step 10 cross-step code is enforced by `step_13.py` — read the file and verify the code string.
4. Update §Cross-Step Synthesis Notes to reference the new `cn:core:governance_label:{mandatory,recommended,optional}`.

---

### F4 — Register `mandatory`, `recommended`, `optional` governance labels in core canon

**File**: `devspec_toolkit/canon/manifest.json`

**Design decision**: Tier labels belong in core canon (MoSCoW-style generic vocabulary). Do NOT add `security_review_required`.

**Fix**: Add three entries alongside the existing `cn:core:governance_label:security`. Use V4-confirmed shape. **Timestamp instruction**: use execution date in ISO-8601 Z format (e.g., `2026-04-10T00:00:00Z`), not `<timestamp of commit>` placeholder.

```json
{
  "id": "cn:core:governance_label:mandatory",
  "kind": "governance_label",
  "preferred_label": "mandatory",
  "definition": "Governance label for extensions or controls that must be implemented before the artifact is shippable. Blocks release if absent. Equivalent to 'Must Have' in MoSCoW.",
  "version": "1.0.0",
  "status": "active",
  "owners": ["spec-platform"],
  "aliases": ["must-have", "required", "p0", "critical"],
  "lifecycle": { "introduced_at": "2026-04-10T00:00:00Z" }
}
```

Plus analogous entries for `recommended` (aliases: should-have, p1) and `optional` (aliases: nice-to-have, could-have, p2).

**Post-edit verification**:
```bash
./tools/run_specdev.sh canonical-lint canon
./tools/run_specdev.sh json read devspec_toolkit/canon/manifest.json '.entries[] | select(.kind == "governance_label") | .id'
# Expected: four entries — security, mandatory, recommended, optional
```

---

### F5 — Add test fixtures for `extension_decision` states

**Directory**: `devspec_toolkit/tests/fixtures/step_13/`

**New fixtures**:
1. **`valid_none_required.json`** — `extensions: []` + valid `extension_decision` with rationale citing real components + NFR categories. Expected: validate passes.
2. **`invalid_empty_no_decision.json`** — `extensions: []`, no `extension_decision`. Expected: fails (missing required).
3. **`invalid_status_mismatch.json`** — `status: extensions-required` + `extensions: []`. Expected: fails on `allOf` (minItems).
4. **`invalid_status_mismatch_2.json`** — `status: none-required` + populated `extensions`. Expected: fails on `allOf` (maxItems).

**Wire into `test_step_scripts_bridge.py`**: add rows pinning the new fixtures to expected exit codes (`{0}` for valid, `{1}` for invalid). This is the integration-level regression guard for F1; F8 Part F provides the unit-level guard.

---

### F6 — Downstream prompt touch-ups (13a, 14)

**Files**: `devspec_toolkit/prompts/prompt_13a_completeness_assessment.md`, `prompt_14_roadmap.md`

**Bugs**:
1. Neither prompt mentions `extension_decision.status == none-required` as a valid terminal state — LLMs may incorrectly flag it as a coverage gap.
2. `extraction-intent-check` reports W597 EXTRACTION_INTENT_VAGUE on `prompt_13a` step-09 intent (7 words).

**Fix**:
1. `prompt_13a`, §Extraction Intent, update `13_extension_manifest.json` bullet: *"If `extension_decision.status == 'none-required'`, treat empty `extensions` as valid terminal state. Otherwise, verify every listed extension file exists under `spec/ext_NN_*.json`."*
2. `prompt_13a`, fix W597 vague step-09 extraction intent — list actual fields extracted from `09_impl_plan.json` and why.
3. `prompt_14`, §Extraction Intent, update `13_extension_generator.json` bullet similarly.
4. `prompt_14`, update the existing "Ignoring Extensions" pitfall (or equivalent — **executing agent must grep the file for the exact section name before editing**) to clarify that skipping extensions when `status == 'none-required'` is correct behavior.

---

### F7 — File F-findings in host review report

**File**: `docs/ops/rfc_devspec_toolkit_review_report.md` (host repo)

**Fix**: Add one-line F-finding entries summarizing F1, F3–F10, FC, F15–F27 to Part A and corresponding tasks to Part B. Host-repo bookkeeping, no toolkit code impact. Full text of entries is the executing agent's judgment call — follow the existing entry style in Part A.

---

### F8 — Repair broken fixture + wire integration test to run full validation

**Files**:
- `tests/fixtures/step_13/valid_manifest.json` — fails validation with 7 errors (Appendix A §4).
- `tests/fixtures/step_13/valid_extension.json` — stale `$schema: vc:13b-database-schema`.
- `tests/integration/test_step_scripts_bridge.py:55` — pins `valid_manifest.json` to exit 0 while fixture fails.
- Companion step 10 fixture required for cross-step checks.

**Part A — Delete `valid_extension.json`**: orphan from abandoned `13b_*` naming. No test references it (confirmed). Delete outright.

**Part B — Repair `valid_manifest.json`**: re-author to match new schema. Requirements:
1. `governance_label_ref.kind = "governance_label"`, id = `cn:core:governance_label:mandatory` (after F4).
2. Non-empty `justification` for every entry.
3. `schema_design_guidelines` containing a verification keyword.
4. Label listed in top-level `canonical_refs_used`.
5. Include `extension_decision: { status: "extensions-required", rationale: "..." }`.

**Part C — Create companion step 10 fixture + validator refactor (depends on F28)**:

**Resolution (V22, 2026-04-10)**: `_load_governance_labels(toolkit_root)` at `step_13.py:79–113` hard-codes `spec_dir = os.path.join(toolkit_root, "spec")` and globs `10_*.json` there. Placing a fixture at `tests/fixtures/step_13/10_governance.json` **will not work** — the validator will never look there.

**Clean-code fix (F28)**: refactor `_load_governance_labels()` and `validate_step_13()` to accept `spec_root: Optional[str] = None`, and update the `validate.py` dispatcher lambda to forward `ctx.get("spec_root")`. Mirrors the existing `step_13a` pattern exactly — see F28 for full detail.

**Fixture placement** (after F28 lands): `tests/fixtures/step_13/10_governance.json`. Minimal content: a valid step 10 artifact whose `canonical_refs_used` contains `cn:core:governance_label:mandatory` with `kind: "governance_label"`. The unit tests in F8 Part F call `validate_step_13(..., spec_root=<fixture_parent>)` to exercise the E590 path.

**Part D — Superseded by F26**: previously "fix bridge pin to run real validation." F26 deletes the fake bridge script and replaces it with a real-CLI wrapper.

**Part E — Folded into F15**: the "audit other bridge rows" step previously lived here but overlaps entirely with F15's classification pass. Removed to avoid duplicate work. F15 Phase 9 handles classification + repair for all non-13 rows.

**Part F — Unit test coverage**: create `tests/unit/validation/validators/test_step_13_deep.py` (currently missing). Tests must import and call `validate_step_13` directly (to pass `spec_root` per F28) and run the shipped `jsonschema` validator against the shipped schema — **no hand-rolled schema checks, no mocking**. Subprocess-based CLI invocation is forbidden here because it cannot inject the `spec_root` override the F28 refactor introduces; F26's integration wrapper covers the CLI path.

Validator-layer tests (call `validate_step_13(instance, toolkit_root, spec_root=<fixture_parent>)` directly):
- Missing `justification` → E320.
- Cross-step: `governance_label_ref.id` not in fixture `10_governance.json.canonical_refs_used` → E590.
- Cross-step: `spec_root` points at a dir with no `10_*.json` → W590.

Schema-layer tests (load the shipped schema via `core.registry`, run `jsonschema.validate` against fixture dicts):
- **F9 keyword guard**: `schema_design_guidelines` lacking any of `verif|test|check|validat|assert` → schema `pattern` violation. (Post-F9 this is a schema-level check, not a validator E320.)
- `schema_design_guidelines` with at least one keyword passes the pattern.
- Missing `governance_label_ref` fails required-property check.
- **F9 regression guard**: writing `verification_rules` fails `unevaluatedProperties: false`.
- **F1 regression guards**: `status: none-required` + `extensions: []` passes; `extensions: []` without `extension_decision` fails required; `status: none-required` + populated `extensions` fails the `allOf` `maxItems: 0` branch; `status: extensions-required` + `extensions: []` fails the `allOf` `minItems: 1` branch.

Both layers test what ships: real shipped validator, real shipped schema, real fixture files. No mocking.

---

### F9 — Align schema `required[]` with validator enforcement

**File**: `devspec_toolkit/schema/13_extension_generator.schema.json` + `tools/specdev_tools/validation/validators/step_13.py`

**Bug**: `step_13.py` enforces `justification` non-empty and `verification_rules` OR `schema_design_guidelines` keyword presence. Neither field is in schema `required[]`. Schema-valid output the validator rejects.

**Dead code**: schema has no `verification_rules` field, and top-level `unevaluatedProperties: false` means writing it fails schema validation. The validator's `verification_rules` branch is **dead code**.

**Fix (decisive)**:
1. Add `justification` and `schema_design_guidelines` to `extensions[].items.required[]`.
2. **Delete** the `verification_rules` branch from `step_13.py`. Only the `schema_design_guidelines` keyword path is viable.
3. Add schema-level `pattern` on `schema_design_guidelines` (char class for case-insensitivity; ECMA-262 compatible):
   ```json
   "schema_design_guidelines": {
     "type": "string",
     "minLength": 40,
     "pattern": "([Vv]erif|[Tt]est|[Cc]heck|[Vv]alidat|[Aa]ssert)",
     "description": "Must contain at least one verification keyword."
   }
   ```
4. **Decision on validator keyword check**: since the schema `pattern` now enforces the keyword requirement, the validator's keyword check is redundant. **Delete it** — single source of truth is the schema. This eliminates the risk of schema/validator drift on keyword semantics. The validator retains only the non-empty `justification` check and the cross-step governance label check (unique to the validator layer).

---

### F10 — Drop `file_name` field, derive from `extension_id`

**File**: `devspec_toolkit/schema/13_extension_generator.schema.json` + 13 dependent active files (V5; historical `WIP/done/*` excluded).

**Bug**: Schema description says *"file_name must be the extension_id with hyphens replaced by underscores"* but the two fields have independent regex patterns. No machine check. **Decision (host-confirmed)**: drop `file_name` entirely.

**Fix**:
1. Remove `file_name` from schema properties and `required[]`.
2. Update all call sites in the 13 active files (V5 + V23 re-verified 2026-04-10; 44 occurrences total):
   - `schema/13_extension_generator.schema.json` (4 hits — field itself)
   - `tools/specdev_tools/generation/schema_differ.py` (3 hits — audit, likely update)
   - `prompts/prompt_13_extension_generator.md` (1 hit — F3 rewrite covers)
   - `prompts/migration/template_extension_generator.md` (2 hits)
   - `tests/unit/generation/test_schema_contracts.py` (3 hits), `test_prompt_contracts.py` (14 hits)
   - `docs/developers/extension_schemas.md` (1 hit)
   - `tests/fixtures/step_13/valid_manifest.json` (2), `invalid_missing_ref.json` (2), `invalid_naming.json` (1), `ext_01_database_schema.json` (1), `ext_02_session_management.json` (1)
   - `tests/integration/test_step_13.py` (9 hits — entire file deleted by F26, so these resolve trivially)
   - Historical `WIP/done/...` and this plan doc — leave alone
3. Document derivation in the prompt: `file_name = extension_id.replace('-', '_') + '.json'`.
4. Pre-commit grep:
   ```bash
   rg 'extensions\[.*\].*file_name|manifest.*file_name' devspec_toolkit/
   ```

---

### FC — Canonical Ref Prose→Const Sweep (consolidates prior F2/F11–F14/F22–F24)

**Pattern**: every affected schema field currently uses prose (`"Kind must be '<wrong>'"`) + hallucinated example IDs on a shelf with no backing data. The fix is identical across all sites:

1. Rewrite the field as `allOf: [{ "$ref": "vc:core:collections#canonicalRef" }, { "properties": { "kind": { "const": "<correct_kind>" } } }]`.
2. Rewrite the field's example to a real canonical ID from the driver table.
3. Rewrite any prompt or migration template example that carries the wrong kind.
4. Rewrite any live fixture drift (listed in the "Live drift sites" column).

**Invariant verified (V8)**: canon already holds the dedicated kinds. No canon edits required. No alias additions. No data migration — the wrong-kind example IDs are hallucinated (no fixture or spec references them).

**Driver table** — every known drift site (verified 2026-04-09, V1 + V7–V19):

| Field | Schemas (line) | Correct kind | Example ID | Live drift sites (must rewrite) | Prior finding |
|---|---|---|---|---|---|
| Step 13 refs | `13_extension_generator.schema.json` (57, 61, +2) | `tag`, `policy`, `id_pattern`, `governance_label` | per-field, see F8 | fixture drift handled by F8 | F2 |
| `tag_ref` | `08_fixtures.schema.json:60` | `tag` | `cn:core:tag:critical-path` | `tests/fixtures/step_08/invalid/invalid_targets_format.json:14`; `tests/fixtures/step_08/valid/valid_generic.json:21-24`; `tests/fixtures/step_08/valid/valid_http.json:30-33` | F11 |
| `metric_ref` | `14_roadmap.schema.json:153` | `metric` | `cn:core:metric:error-rate` | none | F11 |
| `tech_stack_ref` | `09_impl_plan.schema.json:30`; `14_roadmap.schema.json:28`; `core/collections.schema.json:330` (generic canonicalRef atom — harden with const) | `tech_stack` | `cn:core:tech_stack:python` | none | F12 |
| `status_ref` | `04_fr_list`, `06_invariants`, `09_impl_plan:84`, `14_roadmap:145,219`, `16_impl_context` (16 sites: lines 239, 511, 680, 930, 972, 1000, 1051, 1078, 1154, 1181, 1255, 1350, 1522, 1642, 1918, 1995 — V23) | `status` | `cn:core:status:pending` | none | F13 |
| `unit_ref` | `00_charter:187`, `03_glossary:62`, `07_nfrs:96` | `unit` | `cn:core:unit:ms` | `prompts/prompt_07_nfrs.md:129` (drift in example). Fixtures under `tests/fixtures/step_00/` and `tests/fixtures/step_07/` verified clean (V23, 2026-04-10). | F14 |
| `role_ref` | `00_charter:79`, `01_capabilities:118`, `12_ci_gates:80` | `role` | `cn:core:role:reviewer` | none | F22 |
| `command_ref` | `02a_delivery_baseline:63`, `15_scaffold:69` | `command` | `cn:core:command:pytest` | none | F23 |
| `policy_ref` | `02a_delivery_baseline:67`, `16_impl_context:2124` | `policy` | `cn:core:policy:spec-first` | `prompts/prompt_06_invariants.md:144`; `tests/fixtures/step_06/invalid_owner.json:22`; `invalid_missing_trace.json:22`; `valid_full.json:32-35, 58-61` | F24 |

**Shared-atom note**: `tech_stack_ref` has a verified shared atom to harden (`core/collections.schema.json:330`). **`core/step_base.schema.json` has NO `status_ref` or `unit_ref` atoms** (V20, 2026-04-10, resolved inline): the only atoms defined in step_base are `id`, `owner`, `created_at`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`, `_migration_notes`. The `canonical_refs_used` description text mentions `status_ref`/`unit_ref` as aggregation examples only — this is documentation prose, not a schema atom. The cascade claim inherited from the original F13/F14 was a phantom. FC scope is the listed step schemas only.

**`dependency_ref` atom (line 404)**: out of scope for FC. V11 confirmed it is a generic canonicalRef with no `const`, but `14_roadmap.dependency_ref` already has correct prose and there is no live drift. Hardening the atom is a "nice to have" and belongs in a future strengthening pass — do not touch in this plan.

**Pre-execution grep (required before each row)** — confirms no live data uses the current wrong kind beyond what's listed:
```bash
rg '"kind"\s*:\s*"<current_wrong_kind>"' devspec_toolkit/tests/fixtures/step_<NN>/
rg 'cn:[^"]+:<current_wrong_kind>:' devspec_toolkit/spec/ devspec_toolkit/prompts/
```

**Migration templates**: after each FC row's schema edit, also grep `devspec_toolkit/prompts/migration/` for example blocks carrying the row's wrong kind or example ID. Rewrite any hits to match the new `const` + canonical ID. Do not maintain a per-row template list — the grep is the authoritative scope.
```bash
rg '"kind"\s*:\s*"<current_wrong_kind>"' devspec_toolkit/prompts/migration/
```

**Fixture rewrite rule (host-confirmed)**: rewrite drift fixtures to point at existing `cn:core:*` canon entries. Do not propose new project-tier canon entries for fixture realism. If a fixture rewrite breaks a test that asserts specific IDs, **stop and report** — do not rewrite the test to match.

**Do NOT touch** legitimate kind usage (V9):
- Step 11 `risk_category_ref` → `risk_category` (correct).
- Step 03 glossary `term_ref` → `term` (correct).
- Step 01 `capability_ref` → `capability` (correct).
- `canon/examples/auth_demo.json` (demo, out of scope).
- `tests/unit/canonical/test_*.py` throwaway inline canons (test-harness internals).

**Test gate (end of sweep)**: `validate-all`, `canonical-integrity`, `canonical-lint`, `canon-schema-alignment`, `pytest tests/`, `forward-replay-check`.

---

### F15 — Bridge test rot repair

**Context**: `tests/integration/test_step_scripts_bridge.py` pins steps 03, 04, 05, 06, 07, 08, 09, 10, 15 to returncodes `{0, 1}` with `TODO(TEST-004)` comments. Unbounded regression risk — the bridge accepts failure.

**Pre-work — classify every bridge script** (required before touching any slice): for each `test_step_NN.py` referenced by the bridge, determine whether it calls the real `validate` CLI (like `test_step_03.py` per V19) or is a hand-rolled validator (like `test_step_13.py` per V3). Classification output goes in Appendix B (Decision Log).

**Per-script rule**:
- **Real-CLI wrapper**: repair in place (fix fixtures, fix script paths, fix validator expectations).
- **Hand-rolled fake**: delete + replace with the F26 thin-wrapper pattern. No asking.

**Per-step known failure modes** (from 2026-04-09 audit):

| Step | Symptom | Likely fix class |
|---|---|---|
| 03 | `valid_minimal.json` schema error | fixture repair |
| 04 | references non-existent `valid_comprehensive.json`, `invalid_bad_trace.json` | create fixtures or fix paths |
| 05 | needs diagnosis | TBD |
| 06 | `valid_full.json`, `invariants_sample.json` fail validation | fixture repair (coordinate with FC policy_ref drift) |
| 07 | `valid_full.json`, `valid_minimal.json` fail validation | fixture repair (coordinate with FC unit_ref drift) |
| 08 | script paths have doubled `devspec_toolkit/` prefix | script path fix |
| 09 | W590 + E520 on valid fixtures | create step 08 companions or update validator (coordinate with FC tech_stack drift) |
| 10 | exits 1 on invalid fixtures (expected) | restructure script to return 0 on pass/fail expectations |
| 15 | needs diagnosis | TBD |

**Per-step protocol**: read script, run it, capture output, classify, apply minimum fix, tighten pin to `{0}`, remove `TODO(TEST-004)`.

**Exit criteria**: every row pinned to `{0}`; zero `TODO(TEST-004)` comments remain.

---

### F16 + F25 — `canon-schema-alignment` detector enhancement

**Context**: the detector currently emits only W552 (enum overlaps). It cannot catch prose-based `kind` assertions (the FC class) or example ID/kind shelf mismatches (the F25 class discovered at `13a_completeness_assessment.schema.json:32`: `{"id": "cn:core:term:coverage-completeness", "kind": "completeness_dimension"}`).

**Fix**:
1. Extend the detector to parse schema field descriptions for `"Kind (must|should) be '([a-z_]+)'"`, import `INFERENCE_RULES` from `tools/specdev_tools/core/constants.py` as the authoritative field→kind map (V13), and cross-reference against (a) registered canon kinds from `canon/kinds/`, (b) any structural `const` on the same field.
2. New error codes:
   - **E553 SCHEMA_KIND_PROSE_UNREGISTERED**: prose claims a kind not in `canon/kinds/`. Fatal.
   - **E554 SCHEMA_KIND_PROSE_CONFLICTS_CONST**: prose says X, `const` says Y. Fatal.
   - **W555 SCHEMA_KIND_PROSE_NO_CONST**: prose claims a kind but field has no `const`. Warning — nudges toward structural pinning.
   - **E556 SCHEMA_EXAMPLE_SHELF_MISMATCH**: example ID's kind segment ≠ stated `kind`. Fatal.
3. Fix F25's known site (`13a_completeness_assessment.schema.json:32`) and any additional hits surfaced by the detector.
4. **Test fixture location**: add `tests/fixtures/canon_schema_alignment/prose_const_mismatch.schema.json` and `example_shelf_mismatch.schema.json` with deliberate bugs; assert new codes fire.

**Expected state after FC + detector ships**: zero E553, zero E554, zero W555, zero E556.

---

### F17 — `context structure` `canon_kinds_needed` accuracy

**Context**: `context structure` reports `canon_kinds_needed` as a superset of what the schema requires (it unions all `*_ref` fields regardless of `required[]`). For step 13 it lists all four when only `governance_label` is required.

**Fix (locked — option (c) Split)**: emit both `canon_kinds_required` (derived from fields reachable from `required[]`) and `canon_kinds_optional` (remaining `*_ref` fields). Update or extend existing `context structure` tests to assert both fields.

---

### F18 — `schema_differ.py` stale comment cleanup

**File**: `tools/specdev_tools/generation/schema_differ.py:337`

**Bug**: comment references `"project-specific extension (e.g., 13b_custom, 13c_domain)"` — a naming scheme rejected in favor of `ext_NN_*`.

**Fix**: replace with correct `ext_NN_*` naming; link to `docs/developers/extension_schemas.md`. **Audit the surrounding function**: if the code branching depends on the rejected naming pattern (not just the comment), escalate.

---

### F19 — W552 unregistered enum pairings

**Context**: `canon-schema-alignment` emits 5 W552 warnings (Appendix A §9). Four are real canonical drift; one is a detector false positive.

| Warning | Overlap | Action |
|---|---|---|
| `11_redteam.mitigations.type` vs `trace_type` | 6/7 | Audit the local-only value. Add to canon if valid; rename if typo. Then `$ref` canon. |
| `15_scaffold.build_status` vs `status` | 3/3 | Replace with `$ref` to canon `status`. |
| `16_impl_context.env` vs `environment` (and dual `env vs stage`) | 3/3 each | **Detector false positive — intentional narrowing** (V21, 2026-04-10, resolved inline). `schema/16_impl_context.schema.json:1965–1981` has `allOf: [{ $ref: environmentName }, { enum: ["dev","staging","prod"], description: "Restricts deployment environments to dev, staging, or prod (excludes ci)." }]`. The inline enum at `allOf[1]` is a **deliberate narrowing** of the base `environmentName` enum (excludes `ci`). This is correct semantic composition, not drift. **Fix**: enhance `canon-schema-alignment` to recognize the pattern `allOf: [{$ref: X}, {enum: [...]}]` as narrowing-by-intersection (valid) rather than redundant duplication (drift). Skip W552 in that case. **Do NOT edit the schema.** |
| `core/atoms.schema.json` `owner` vs `owner` | 8/8 | Replace with `$ref` to canon `owner`. Foundational cascade — run `validate-all` and `pytest` after. |

**Test gate**: `canon-schema-alignment` emits zero W552. `validate-all` passes unchanged.

---

### F20 — W597 vague extraction intent on `prompt_11`

**Fix**: rewrite `prompt_11_redteam.md` step-02 extraction intent (currently 44 words, flagged vague) to explicitly list fields extracted from `02_system_sketch.json` (component boundaries, trust zones, attack surfaces). Follow the style of non-vague intents in the same file. Re-run `extraction-intent-check` — expect zero W597.

---

### F21 — Schema audit false-PASS process fix

**Context**: `WIP/done/schema_audit/` marked FIX-048 as PASS, but the stale `vc:13b-database-schema` reference still existed (F8 Part A removes it).

**Fix**:
1. Add "Spot-Check Verification Protocol" to `WIP/done/schema_audit/` close-out doc: auditor must re-run every fix's verification grep as an independent pass, capturing verbatim output, before marking PASS.
2. Correct the FIX-048 entry to reflect that the stale reference was not removed until F8.
3. Add `F-audit-01` to the host review report (per F7).

---

### F26 — Delete fake `test_step_13.py`; replace with real-validator wrapper

**File**: `tests/integration/test_step_13.py`

**Bug (V3)**: hand-rolled validator that reimplements schema checks, hard-requires `file_name` (which F10 removes), never calls `./tools/run_specdev.sh validate`. Bridge pin `{0}` is meaningless.

**Fix**:
1. Delete the current file.
2. Replace with a thin subprocess wrapper:
   ```python
   import subprocess, sys
   from pathlib import Path

   def main():
       if len(sys.argv) != 2:
           sys.exit("Usage: test_step_13.py <fixture>")
       fixture = Path(sys.argv[1])
       toolkit_root = Path(__file__).resolve().parents[2]
       result = subprocess.run(
           [str(toolkit_root / "tools" / "run_specdev.sh"), "validate", str(fixture),
            "--repo-root", str(toolkit_root)],
           cwd=str(toolkit_root),
       )
       sys.exit(result.returncode)

   if __name__ == "__main__":
       main()
   ```
3. F8 Part B becomes a hard dependency — `valid_manifest.json` must be fully schema-valid before the bridge pin has meaning.

**Pattern**: applied by F15 to any other hand-rolled validator discovered during bridge classification.

---

### F28 — Refactor `_load_governance_labels()` for testability (SoC)

**File**: `tools/specdev_tools/validation/validators/step_13.py:79–113`

**Current state (V22 + re-verified 2026-04-10)**:
```python
# tools/specdev_tools/validation/validators/step_13.py:19
def validate_step_13(instance: dict[str, Any], toolkit_root: str) -> list[SpecError]:
    ...
    governance_labels = _load_governance_labels(toolkit_root)

# tools/specdev_tools/validation/validators/step_13.py:79
def _load_governance_labels(toolkit_root: str) -> Optional[Set[str]]:
    spec_dir = os.path.join(toolkit_root, "spec")
    ...
```
The dispatcher at `tools/specdev_tools/validation/validate.py:468` is:
```python
"13": lambda instance, root, ctx: step_13.validate_step_13(instance, root),
```
Note that `step_13a` (line 469) already reads `ctx.get("spec_root")` as prior art — step 13 just doesn't use it.

**Bug**: the loader hardcodes `{toolkit_root}/spec/`, coupling path policy to the loader. Untestable without either polluting production spec or mocking `os.listdir` (forbidden).

**Fix (mirrors `step_13a` exactly for DRY consistency)**:
1. Change loader signature to `_load_governance_labels(toolkit_root: str, spec_root: Optional[str] = None) -> Optional[Set[str]]`. At the top: `spec_dir = spec_root if spec_root is not None else os.path.join(toolkit_root, "spec")`. Use `spec_root` — not `spec_dir` — to match the existing `ctx["spec_root"]` convention used by `step_13a`.
2. Change `validate_step_13` signature to `validate_step_13(instance, toolkit_root, spec_root: Optional[str] = None)`. Forward `spec_root` into `_load_governance_labels`.
3. Update the dispatcher in `validate.py:468` to mirror the `step_13a` lambda exactly:
   ```python
   "13": lambda instance, root, ctx: step_13.validate_step_13(instance, root, ctx.get("spec_root")),
   ```
   Since `ctx.get("spec_root")` returns `None` when absent, default CLI behavior is preserved.

**SoC rationale**: path policy (where does the governance file live?) belongs at the call site, not inside the loader. Mirrors the existing `step_13a` pattern — zero new conventions.

**Backward compatibility**: existing CLI invocations without `--spec-root` yield `ctx["spec_root"] = None`, loader falls back to `{toolkit_root}/spec`. Identical behavior.

**Test gate**: `test_step_13_deep.py` (F8 Part F) calls `validate_step_13(instance, toolkit_root, spec_root=<fixture_parent>)` directly to exercise the override path against `tests/fixtures/step_13/10_governance.json`. The bridge integration test (F26 wrapper) exercises the default path via the real CLI. No mocking.

---

### F27 — `canonicalRef.kind` description rot in `core/collections.schema.json`

**Context (V11)**: `canonicalRef.kind.description` at line 119 lists a stale subset of kinds. Missing: `command, completeness_dimension, governance_label, id_pattern, interface, metric, nfr_category, owner, policy, role, status, tag, tech_stack, trace_type`. Authors reading this conclude the missing kinds aren't canonical — which is the upstream source of the FC class of drift. `canonicalProposal.kind.description` at line 164 has the same problem.

**Fix**: rewrite both descriptions to reference `canon/kinds/` as the authoritative source rather than enumerating inline:
> *"Canonical kind category. Must match a kind defined under `canon/kinds/*.json` (or the project canon). See `devspec_toolkit/canon/kinds/` for the full list. Examples from registered kinds: 'unit' (ms, percent), 'status' (pending, active), 'tech_stack' (python), 'policy' (spec-first)."*

Zero behavioral change — description-only edits. Closes the drift source upstream of FC.

---

## 4. Withdrawn Findings

### H2 — extraction intent ↔ DAG divergence for step 13
**Status**: Withdrawn. `extraction-intent-check` reported only 2 W597 warnings, neither against step 13. The linter is authoritative.

### H6 — nested `canonical_refs_used` aggregation
**Status**: Withdrawn. `validate` correctly surfaces E210 for refs nested inside `extensions[]` (Appendix A §4). Aggregation works.

### Step 13b as "missing pipeline layer"
**Status**: Withdrawn. Extension schemas are per-project (`docs/developers/extension_schemas.md`). The `vc:13b-database-schema` URI is a stale relic.

---

## 5. Pre-Execution Verifications

V1–V19 were executed during planning (2026-04-09). V20–V23 were added during the 2026-04-10 review pass to close out inherited assumptions. Findings are consolidated in §3 (FC driver table especially).

### V1 ✅ — `"Kind must be"` prose sweep
13 schemas affected. Complete classification in FC driver table.

### V2 ✅ — Project extension-schema discovery
`tools/schema_registry.json` is a flat static map. No dynamic discovery of `schema/ext_*.schema.json`. Deferred-07 stays deferred.

### V3 ✅ — `test_step_13.py` audit
Hand-rolled validator. F8 Part D replaced by F26.

### V4 ✅ — Canon entry shape
Inline entries in `canon/manifest.json`. ISO-8601 Z timestamps. See F4 for concrete shape.

### V5 ✅ — `file_name` readers
16 files reference `file_name`. Full list in F10.

### V6 ✅ — Step 13 fixture directory contents
Contains `valid_manifest.json`, `valid_extension.json`, `invalid_missing_ref.json`, `invalid_naming.json`, `ext_01_database_schema.json`, `ext_02_session_management.json`.

### V7 ✅ — Existing tech_stack WIP plan
`WIP/done/step02-tech-stack-migration-context/` addresses step ownership, not kind drift. FC `tech_stack_ref` row is independent.

### V8 ✅ — Canon inventory

| Kind | Count | IDs |
|---|---|---|
| command | 2 | pytest, governance-check |
| completeness_dimension | 4 | traceability, completeness, quality, ambiguity |
| environment | 4 | dev, ci, staging, prod |
| governance_label | 1 | security |
| id_pattern | 1 | conventional-commit |
| interface | 5 | ask, http, http-json, search, trace-retrieval |
| metric | 1 | error-rate |
| nfr_category | 11 | latency, throughput, availability, durability, cost, security, privacy, maintainability, usability, portability, energy |
| owner | 8 | api, ui, system, ops, data, product, business, engineering |
| policy | 1 | spec-first |
| role | 1 | reviewer |
| stage | 4 | ci, dev, staging, prod (pipeline phases) |
| status | 7 | active, blocked, deferred, pending, green, red, verified (work-item states) |
| tag | 1 | critical-path |
| tech_stack | 1 | python |
| trace_type | 11 | fr, api, nfr, invariant, fixture, doc, capability, component, threat, charter-goal, glossary |
| unit | 3 | percent, ms, count |

**Zero-entry kinds**: `term`, `entity`, `action`, `capability` (core), `risk_category` (core), `acronym`, `event`, `dependency`. Schema examples on these shelves are dangling hallucinations.

### V9 ✅ — Canon-ref usage scan
Live fixture/prompt drift sites consolidated into FC driver table. Legitimate refs (step 03 term, step 11 risk_category, step 01 capability) marked "do NOT touch".

### V10 ✅ — `stage` vs `status` kinds distinct
`stage` = CI/CD phases; `status` = work-item states. FC `status_ref` row replaces prose + hallucinated `cn:core:stage:pending` examples with real `cn:core:status:*`.

### V11 ✅ — `schema/core/collections.schema.json` audit
- `tech_stack_ref` atom at line 330 — generic canonicalRef with no const. FC adds const.
- `dependency_ref` atom at line 404 — generic. `14_roadmap.dependency_ref` already has correct prose. Low priority; FC may optionally harden the atom.
- `canonicalRef.kind.description` at line 119 — stale subset. **F27 fixes.**
- `stageName` and `environmentName` enums identical by design. **F19 `env` dual-overlap is detector false positive.**

### V12 ✅ — `canonical/integrity.py` audit
No hardcoded kind strings. No changes required for FC.

### V13 ✅ — `INFERENCE_RULES` in `constants.py` is the source of truth
Public constant tuple mapping field names → kinds. F16 imports it directly. Dead entries (`state_ref`, `actor_ref`, `resource_ref`) exist in the tuple but no schema fields use them — defensive, leave alone.

### V14 ✅ — step_06 `valid_full.json:32-35,58-61` drift confirmed
`policy_ref` with `{id: "cn:project:term:*-policy", kind: "term"}`. FC `policy_ref` row.

### V15 ✅ — step_08 `valid_generic.json:21-24` drift confirmed
`tag_ref` with `kind: "term"`. FC `tag_ref` row.

### V16 ✅ — step_08 `valid_http.json:30-33` drift confirmed
`tag_ref` with `kind: "term"`. FC `tag_ref` row.

### V17 ✅ — `"Kind should be"` weaker wording
2 hits: `00_charter.schema.json:79` (role_ref, FC), `:187` (unit_ref, FC).

### V18 ✅ — `canon/kinds/tag.json`, `canon/kinds/metric.json`
`cn:core:tag:critical-path` and `cn:core:metric:error-rate` exist. FC examples point at these.

### V19 ✅ — `test_step_03.py` bridge script audit
Real CLI wrapper (subprocess at lines 177–180). Not all bridge scripts are fake. F15 classifies before repair-vs-replace.

### V20 ✅ — `core/step_base.schema.json` `status_ref` / `unit_ref` presence
**Result (2026-04-10)**: step_base contains NO `status_ref` or `unit_ref` atom. The only atoms defined are `id`, `owner`, `created_at`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`, `_migration_notes`. The grep hits (lines 28, 32) are in the `canonical_refs_used` description prose, where it lists ref field names as aggregation examples — this is documentation, not a schema atom. **FC step_base cascade claims were phantoms**; dropped from both rows. No foundational-atom edit required.

### V21 ✅ — `16_impl_context.env` field shape
**Result (2026-04-10)**: `schema/16_impl_context.schema.json:1965–1981` has:
```json
"env": {
  "description": "Target deployment environment.",
  "allOf": [
    { "$ref": "vc:core:collections#environmentName" },
    { "enum": ["dev", "staging", "prod"],
      "description": "Restricts deployment environments to dev, staging, or prod (excludes ci)." }
  ]
}
```
The inline enum is **intentional narrowing** (excludes `ci`, which is present in the base `environmentName` enum). Both V11's "single $ref" claim and B1's "duplicated drift" suspicion were wrong. **F19 action locked**: enhance detector to recognize the `allOf: [{$ref}, {enum}]` narrowing pattern as valid composition, not drift. Do not edit the schema.

### V23 ✅ — Remaining FC row verifications (2026-04-10)
- **`status_ref` in `16_impl_context.schema.json`**: 16 sites at lines 239, 511, 680, 930, 972, 1000, 1051, 1078, 1154, 1181, 1255, 1350, 1522, 1642, 1918, 1995. All require FC const treatment.
- **`unit_ref` fixture sweep**: grep of `tests/fixtures/step_00/` and `tests/fixtures/step_07/` for `"kind": "term"|"stage"|"capability"|"risk_category"` returned zero matches. No live fixture drift; FC `unit_ref` row only touches schemas + `prompts/prompt_07_nfrs.md:129`.

### V22 ✅ — `step_13.py:_load_governance_labels()` path resolution
**Result (2026-04-10)**: the loader at `step_13.py:79–113` has signature `_load_governance_labels(toolkit_root: str)` and hardcodes `spec_dir = os.path.join(toolkit_root, "spec")`. The dispatcher at `validate.py:468` currently passes only `(instance, root)` even though the neighbouring `step_13a` lambda already threads `ctx.get("spec_root")`. Placing the companion fixture at `tests/fixtures/step_13/10_governance.json` will not work — the glob will never see it. **Resolution**: new finding **F28** threads `spec_root` through loader + `validate_step_13` + dispatcher to mirror the existing `step_13a` pattern exactly. No new conventions; no mocking.

---

## 6. Out of Scope — Deferred

### Deferred-07 — Per-project extension-schema discovery (STILL DEFERRED)
`docs/developers/extension_schemas.md` documents a workflow for `schema/ext_NN_*.schema.json` files. V2 confirmed `tools/schema_registry.json` is static. Missing feature, not drift. **Mitigation**: F7 adds a "workflow unsupported" note to the doc.

All previously-deferred drift-class items (Deferred-01..06, -08) are now in-scope as F15–F21 / F26.

---

## 7. Execution Order

**Important**: executed by a Claude Code agent. Read this doc in full including Appendix A first. No wall-clock estimates. Stop-report on any unexpected failure — do not guess forward.

**Rollback protocol**: since the executing agent does not commit during this pass, unrecoverable mid-phase breakage is resolved by `git reset --hard HEAD` to drop working-tree edits and re-plan the phase. Use file-level reverts for narrower recovery.

### Phase 1 — Verification (V1–V23 all complete)
All twenty-three verifications (V1–V23) were executed read-only during planning. Results are consolidated in §5. No pre-execution read-only work remains. The executing agent starts at Phase 2 after reading §3 and §5 in full.

### Phase 2 — Step 13 schema edits (lowest blast radius first)
1. **F1** — add `extension_decision`, flip `minItems`, add defensive `allOf` conditional.
2. **F9** — add `justification` and `schema_design_guidelines` to `required[]`; schema `pattern`; delete dead `verification_rules` branch AND redundant keyword check from `step_13.py`.
3. **F10** — drop `file_name` field. Update all call sites across the 13 dependent active files (see F10 list).

**Test gate**: self-validate `13_extension_generator.schema.json`; `validate-all`; unit tests.

### Phase 3 — FC slice 1: step 13 `*_ref` (four fields)
4. Apply FC pattern to step 13's `tag_ref`, `policy_ref`, `id_pattern_ref`, `governance_label_ref` (const + corrected prose/examples). Fixture drift handled by F8.

**Test gate**: `validate-all`.

### Phase 4 — Canon edits
5. **F4** — register `cn:core:governance_label:{mandatory, recommended, optional}` with concrete 2026-04-10 timestamps.

**Test gate**: `canonical-lint canon`; confirm 4 `governance_label` entries.

### Phase 5 — Prompt edits
6. **F3** — rewrite step 13 prompt (Output Contract, Negative Constraints, Governance Label Resolution, Cross-Step Synthesis). Verify actual error codes against validator before pasting.
7. **F6** — update `prompt_13a` (extension_decision + W597 fix) and `prompt_14` (extension_decision awareness, pitfall clarification — grep first for exact section name).
8. **F20** — rewrite `prompt_11_redteam.md` step-02 W597.

**Test gate**: `prompt-sync spec`, `extraction-intent-check` (expect zero W597), `dag-lint`.

### Phase 6 — Step 13 validator refactor + fixtures + real-validator wrapper
9. **F28** — thread `spec_root` through `_load_governance_labels` → `validate_step_13` → the `validate.py:468` dispatcher lambda (mirroring `step_13a`). Run existing `pytest tests/` to confirm no regression in default-path behavior.
10. **F8 Part A** — delete `valid_extension.json`.
11. **F8 Part B** — repair `valid_manifest.json` to match new schema.
12. **F8 Part C** — create `tests/fixtures/step_13/10_governance.json` companion (relies on F28).
13. **F26** — delete fake `test_step_13.py`, replace with subprocess wrapper.
14. **F8 Part F** — create `tests/unit/validation/validators/test_step_13_deep.py` with the validator-layer and schema-layer coverage listed in F8 Part F. Tests call `validate_step_13(..., spec_root=<fixture_parent>)` directly and run the shipped `jsonschema` validator against the shipped schema — no mocking, no subprocess.
15. **F5** — create four new `extension_decision` fixtures; wire into `test_step_scripts_bridge.py` with strict pins.

**Test gate**: all step 13 fixtures validate per expected status; `pytest tests/integration/test_step_scripts_bridge.py -v -k step_13` passes.

### Phase 7 — FC slice 2: all remaining canonical-ref rows
16. Execute each FC driver-table row (tag, metric, tech_stack, status, unit, role, command, policy). Per row:
    - Run pre-execution grep from FC.
    - Rewrite schema field(s) with `allOf → { const: "<kind>" }`.
    - Rewrite any live prompt/fixture drift in the row's "Live drift sites" column.
    - Update migration templates if they carry wrong-kind examples.

    **Parallelization**: rows are NOT file-disjoint. Known collisions:
    - `14_roadmap.schema.json`: `metric_ref` + `tech_stack_ref` + `status_ref`
    - `00_charter.schema.json`: `unit_ref` + `role_ref`
    - `02a_delivery_baseline.schema.json`: `command_ref` + `policy_ref`

    Group into serial batches by colliding file; within a batch, execute rows sequentially in the main thread. Non-colliding rows (e.g. `tag_ref` → step_08 only) may run as background subagents in parallel with a batch, provided their file sets do not intersect any concurrently-running row. Executing agent must build the collision map from the FC driver table before dispatching any subagent.

**Test gate (after all rows)**: `validate-all`, `canonical-integrity`, `canonical-lint`, `canon-schema-alignment`, full `pytest tests/`, `forward-replay-check`.

### Phase 8 — Detector + hardening (F27, F16+F25, F17, F19)
17. **F27**
 — rewrite stale `canonicalRef.kind` and `canonicalProposal.kind` descriptions in `core/collections.schema.json`.
18. **F16 + F25** — extend `canon-schema-alignment` with E553/E554/W555/E556; import `INFERENCE_RULES`; add test fixtures under `tests/fixtures/canon_schema_alignment/`; fix F25 site in `13a_completeness_assessment.schema.json:32` and any other surfaced hits.
19. **F17** — split `canon_kinds_needed` into `canon_kinds_required` + `canon_kinds_optional`; update `context structure` tests.
20. **F19** — close the 4 real W552 warnings per the table (11_redteam/trace_type audit, 15_scaffold/build_status $ref, core/atoms owner $ref). Detector enhancement (narrowing-enum recognition) is folded into F16 + F25 in the same detector module — so the 5th W552 (env) closes automatically once F16 ships.

**Test gate**: `canon-schema-alignment` → zero W552, zero E553/E554/W555/E556. `validate-all spec` (catches any regression from the `core/atoms.schema.json owner` foundational cascade — every schema using the owner atom must still validate). `pytest tests/`.

### Phase 9 — Bridge test rot repair (F15)
21. **Classification pass**: for each `test_step_NN.py` row in `test_step_scripts_bridge.py`, determine real-CLI vs hand-rolled. Record in Appendix B.
22. For each `{0, 1}` row (steps 03, 04, 05, 06, 07, 08, 09, 10, 15): apply per-script rule (repair or F26-pattern replace). Tighten pin to `{0}`. Remove `TODO(TEST-004)`.
23. Re-run `pytest tests/integration/test_step_scripts_bridge.py` after each row.

**Test gate**: every row pinned to `{0}`. Zero `TODO(TEST-004)` comments.

### Phase 10 — Doc + process cleanup
24. **F18** — fix stale `schema_differ.py:337` comment; audit surrounding function.
25. **F21** — add Spot-Check Verification Protocol; correct FIX-048.
26. **F7** — add one-line F-finding entries to host review report Part A + tasks to Part B.
27. Update `docs/developers/extension_schemas.md` — drop `file_name`, add `extension_decision`, add Deferred-07 note.
28. Check `devspec_toolkit/tools/step_docs.json` for step 13 documentation mapping updates.

**Test gate**: `pytest tests/`, `spec-check`, `canonical-integrity`, `canon-schema-alignment`, `extraction-intent-check`, `dependency-order-lint`, `forward-replay-check`, `prompt-sync`. Zero errors, zero warnings outside Deferred-07.

### Phase 11 — Final full sweep
29. Full pipeline validation:
    ```bash
    pytest devspec_toolkit/tests/ -v
    ./tools/run_specdev.sh spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ./tools/run_specdev.sh extraction-intent-check --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh canon-schema-alignment --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
    ./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh dependency-order-lint --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh forward-replay-check --repo-root ./devspec_toolkit --git-root .
    ./tools/run_specdev.sh prompt-sync spec --repo-root ./devspec_toolkit
    ./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit
    ```
30. Move this doc to `WIP/done/` once green.

### Phase 11b — Host-side follow-up (NOT the executing agent's responsibility)

After the toolkit fix merges, the VC website host has no `spec/13_extension_manifest.json`. Host runs `prompt_13` on the VC website spec to emit a `none-required` manifest. Listed here so it isn't forgotten; executing agent does not perform it.

### Phase 12 — Commit (only if host explicitly authorizes)
Host has not authorized commits for this pass. The executing agent does NOT commit.

If host later authorizes: use commit tag `[phase-1-seed-spec]` to match the existing branch convention. **Note** (verified 2026-04-10 against host `spec/10_governance.json:10`): the commit-message regex accepts any `phase-[0-9a-z-]+` pattern, so `[phase-1-step-13-hardening]` would also pass governance-check — the earlier claim that it would fail was incorrect. Prefer `[phase-1-seed-spec]` for consistency with existing commits on this branch, not because other tags are invalid. Co-author attribution: substitute the executing agent's actual model name — do not blindly copy examples.

---

## 8. Decisions Already Made

Original step 13 decisions:
- Field name: `extension_decision`.
- F10: drop `file_name` entirely; no validator check.
- F9: breaking schema change OK (no existing artifacts); char-class regex `([Vv]erif|...)`.
- F4: core canon, three labels (`mandatory`, `recommended`, `optional`); no `security_review_required`.
- F8: delete `valid_extension.json` outright.
- Commit authority: none.

Re-planning (2026-04-09) decisions:
- Scope: eliminate tech debt; no regressions; no new drift; pre-existing rot in scope.
- V1–V19 verified every Cat 2 "migration" collapses to prose+const fix; FC consolidates them.
- F13 resolution: `status_ref` with `const: "status"`; no rename, no migration.
- F8 Part C: companion fixture at `tests/fixtures/step_13/10_governance.json` (same directory as `valid_manifest.json`).
- Execution model: single agent, multi-phase; background subagents OK for independent parallel slices; no nested subagents.

Review simplification (2026-04-10) decisions:
- Collapsed F2/F11/F12/F13/F14/F22/F23/F24 into single FC driver-table finding.
- F17 locked to option (c) Split.
- F9: delete both `verification_rules` branch AND redundant validator keyword check.
- F8 Part F tests must exercise the real CLI / real validator modules (no hand-rolled jsonschema calls).
- F15 classification sub-phase added before per-script repair.
- Rollback protocol: `git reset --hard HEAD` (safe because no commits during execution).

Verification-pass (2026-04-10) resolutions (V20–V22 executed inline, no deferred verifications remain):
- **V20**: `core/step_base.schema.json` has NO `status_ref`/`unit_ref` atoms — the cascade claim inherited from original F13/F14 was a phantom. FC rows no longer touch step_base.
- **V21**: `16_impl_context.env` inline enum is intentional narrowing (excludes `ci`). F19 fix = detector enhancement to recognize `allOf: [{$ref}, {enum}]` narrowing. Schema is correct; do not touch.
- **V22**: `_load_governance_labels()` hardcodes `{toolkit_root}/spec/`. **F28 (new)** refactors it to accept an optional `spec_dir` override. F8 Part C then uses the override — no mocking, no production-spec pollution.
- **F28** added as a SoC clean-code finding (path policy belongs at the call site, not inside the loader).
- **Phase 12 tag claim corrected**: host `spec/10_governance.json` regex accepts any `phase-[0-9a-z-]+`; the earlier fear that `[phase-1-step-13-hardening]` would fail was wrong. Prefer `[phase-1-seed-spec]` only for consistency with existing commits.

---

## 9. Operational Decisions (All Resolved)

No decision gates remain open at execution time.

1. **F17**: option (c) Split — emit `canon_kinds_required` + `canon_kinds_optional`.
2. **F19 `env`**: detector false positive (intentional narrowing, V21); no schema edit; fix detector via F16's same module.
3. **Fixture realism**: rewrite drift fixtures to existing `cn:core:*` canon entries. Concrete targets:
   - step_06 `policy_ref` → `cn:core:policy:spec-first`
   - step_08 `tag_ref` → `cn:core:tag:critical-path`
   - step_13 `governance_label_ref` → `cn:core:governance_label:security` initially, then `cn:core:governance_label:mandatory` after F4.
   **Escalation rule**: if a fixture rewrite breaks a test that asserts specific IDs, stop and report — do not rewrite the test.
4. **F15 fake-script replacement**: auto-replace without asking, per classification.
5. **Subagents**: `run_in_background: true` allowed only when the concurrent slices touch fully disjoint file sets. Phase 7 FC rows are NOT file-disjoint — see the Phase 7 collision map. No nested subagents.
6. **Commits**: no commits during execution. Host reviews and commits after full green.

---

## Appendix A — Evidence (Raw Command Outputs)

### §1 — Step 13 context structure
```
required_inputs: [01, 02, 04, 05, 07, 08, 11]
canon_kinds_needed: [governance_label, id_pattern, policy, tag]
```
Components (from step 02): ghost-cms, vc-collective-theme, ghost-sqlite-db, zoho-mail-smtp, youtube-oembed, github-scm.

NFRs (step 07, 17 total): latency × 6, usability × 5, availability × 1, durability × 2, maintainability × 2, portability × 1, throughput × 1. **Zero in `security` or `compliance`.**

### §2 — Schema `"Kind must be"` prose bugs in step 13
```
57: "...tag_ref...Kind must be 'term'. Example: {\"id\": \"cn:project:term:payments\", \"kind\": \"term\"}"
61: "...policy_ref...Kind must be 'risk_category'. Example: {\"id\": \"cn:project:risk_category:pci-dss\", \"kind\": \"risk_category\"}"
id_pattern_ref: "Kind must be 'term' or 'action'."
governance_label_ref: "Kind must be 'capability'."
```

### §3 — `extraction-intent-check`
```
W597 EXTRACTION_INTENT_VAGUE prompt_11 intent for '02' is vague (44 words)
W597 EXTRACTION_INTENT_VAGUE prompt_13a intent for '09' is vague (7 words)
OK (warnings)
```

### §4 — `valid_manifest.json` fixture validation errors
```
E320 Extension 'ext-01-database-schema' missing or empty justification
E320 Extension 'ext-01-database-schema' has no verification_rules and schema_design_guidelines lacks verification keywords
E320 Extension 'ext-02-session-management' missing or empty justification
E320 Extension 'ext-02-session-management' has no verification_rules and schema_design_guidelines lacks verification keywords
W590 CROSS_STEP_UPSTREAM_MISSING 10_governance.json not found
E110 UNKNOWN_CANONICAL_ID cn:core:term:spec-extension extensions[0].governance_label_ref
E110 UNKNOWN_CANONICAL_ID cn:core:term:spec-extension extensions[1].governance_label_ref
E210 CROSS_ARTIFACT_DRIFT canonical_refs_used_missing ids=['cn:core:term:spec-extension']
```
(Fixture content re-readable via `./tools/run_specdev.sh json read devspec_toolkit/tests/fixtures/step_13/valid_manifest.json '.'` — not reproduced here.)

### §5 — `valid_extension.json` stale schema ref
```
E520 schema_not_found uri=vc:13b-database-schema
```

### §6 — Integration test pin
`tests/integration/test_step_scripts_bridge.py:55`:
```python
("test_step_13.py", [str(toolkit_root / "tests" / "fixtures" / "step_13" / "valid_manifest.json")], repo_root, {0}),
```

### §7 — Canon `governance_label` (before F4)
Single entry: `cn:core:governance_label:security`.

### §8 — `step_13.py` validator enforcement
- `justification` non-empty → E320.
- `verification_rules` OR `schema_design_guidelines` keyword (dead branch + redundant check per F9).
- `governance_label_ref.id` must appear in `spec/10_*.json` `canonical_refs_used` where `kind == "governance_label"` → E590. Missing file → W590.

### §9 — `canon-schema-alignment` output
```
W552 11_redteam.schema.json:.../mitigations/.../type/enum overlaps 6/7 with 'trace_type'
W552 15_scaffold.schema.json:.../build_status/enum overlaps 3/3 with 'status'
W552 16_impl_context.schema.json:.../deployments/.../env/allOf/1/enum overlaps 3/3 with 'environment'
W552 16_impl_context.schema.json:.../deployments/.../env/allOf/1/enum overlaps 3/3 with 'stage'
W552 core/atoms.schema.json:$defs/owner/enum overlaps 8/8 with 'owner'
OK (warnings)
```

### §10 — `extension_schemas.md` naming convention
```
- Manifest: 13_extension_manifest.json
- Extension Artifacts: ext_[0-9]{2}_<topic>.json
- Extension Schemas: ext_NN_<topic>.schema.json (if custom schema)
```

### §11 — Schema audit false-PASS
`WIP/done/schema_audit/p5-batch5-review.md:30` claimed no `13b` reference remained. Reality: `tests/fixtures/step_13/valid_extension.json:2` still had `"$schema": "vc:13b-database-schema"`. F-audit-01.

---

## Appendix B — Decision Log

| Decision | Date | Rationale |
|---|---|---|
| Do not force trivial extension for VC website | 2026-04-09 | Violates prompt rules |
| Fix toolkit instead of per-project workaround | 2026-04-09 | Other projects hit same bugs |
| Field name `extension_decision` | 2026-04-09 | Host choice |
| Drop `file_name` entirely | 2026-04-09 | Eliminate drift surface |
| F9 breaking change acceptable | 2026-04-09 | No existing artifacts |
| Core canon for tier labels | 2026-04-09 | Generic MoSCoW vocabulary |
| Delete `valid_extension.json` | 2026-04-09 | Orphan from rejected naming |
| Withdraw step 13b as "missing layer" | 2026-04-09 | Extension schemas per-project |
| Withdraw H2 (extraction DAG) | 2026-04-09 | Linter is authoritative |
| Consolidate F2/F11–F14/F22–F24 into FC | 2026-04-10 | DRY; same fix pattern 7× |
| F17 option (c) Split | 2026-04-09 | Strengthens output |
| F19 env = false positive | 2026-04-09 | V11 confirmed explicit $ref |
| F8 Part C location | 2026-04-10 | Same-dir glob is simplest |
| F9 delete redundant validator keyword check | 2026-04-10 | Schema pattern is single source of truth |
| V20 added | 2026-04-10 | Prevent unverified step_base cascade |
| Rollback = `git reset --hard HEAD` | 2026-04-10 | Safe because no commits during exec |

| V20 resolved: `step_base` has no ref atoms | 2026-04-10 | Read-only inspection; cascade claim was a phantom |
| V21 resolved: `env` is intentional narrowing | 2026-04-10 | `allOf[1]` enum excludes `ci` by design |
| V22 resolved: `_load_governance_labels` hardcodes spec path | 2026-04-10 | Drives F28 SoC refactor |
| F28 added (SoC refactor of governance loader) | 2026-04-10 | V22 revealed untestable coupling |
| Phase 12 tag claim corrected | 2026-04-10 | Host regex accepts any `phase-*`; fear was unfounded |

**To be appended at execution time**:
- F15 bridge-script classification table (real-CLI vs hand-rolled per step).
