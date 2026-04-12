# Step 14 Roadmap — Hardening Plan (Toolkit-Wide)

**Status**: Planned 2026-04-12. Execution pending.
**Branch**: `codex/canonical-drift-review-plan`. Commit tag for this phase: `[phase-2-roadmap-hardening]`.
**Scope owner**: Shantanu (VC website host repo).
**Scope mandate**: Harden Step 14's prompt, schema, and supporting tooling so that future roadmap artifact generation produces complete, drift-free, fully-traced output. Fix the matrix deduplication bug. All changes must be generic (not project-specific). Introduce no regressions.

**Finding set** — 24 findings across 4 categories after 2026-04-12 review pass:

- **F1–F6**: prompt Coverage Closure gaps (critical — enforcement blind spots)
- **F7–F8**: prompt Negative Constraints gaps (high — allows contradictory/vague output)
- **F9–F12**: schema structural gaps (high — missing fields, weak validation)
- **F13–F17**: cross-step synthesis gaps (medium — incomplete integration guidance)
- **F18–F19**: shared_expectations.md gaps (medium — namespace/fixture rules)
- **F20**: matrix.py deduplication bug (high — produces wrong FR count)
- **F21**: canonical-lint CLI ergonomics (low — UX improvement: confusing error on bad positional arg)
- **F22–F23**: prompt usability gaps (low — atomicity rules, trace matrix guidance)
- **F24**: prompt Extraction Mandate references wrong filename (high — hallucinated path)

**Prerequisite reads for executing agent**:
- `$PRODUCT_ROOT/CLAUDE.md` (branch strategy, commit format)
- `$TOOLKIT_ROOT/CLAUDE.md` (CLI usage, `--repo-root`)
- `$TOOLKIT_ROOT/docs/prompts/shared_expectations.md`
- `$TOOLKIT_ROOT/prompts/prompt_14_roadmap.md`
- `$TOOLKIT_ROOT/schema/14_roadmap.schema.json`
- `$TOOLKIT_ROOT/tools/specdev_tools/validation/matrix.py`
- `$TOOLKIT_ROOT/tools/specdev_tools/canonical/lint.py`

> Path variables follow `shared_expectations.md` §1: `$PRODUCT_ROOT` = host repo root, `$TOOLKIT_ROOT` = `devspec_toolkit/` submodule root.

---

## 1. Origin of This Work

Started from a comprehensive review of `spec/14_roadmap.json` against all upstream specs (00-13) for the VC website project. The roadmap artifact passed `specdev spec-check` (0 errors) but manual cross-referencing exposed systemic gaps:

| Gap Category | Count | Root Cause |
|---|---|---|
| 39 fixtures unreferenced by any task AC | 39 | Prompt doesn't enforce fixture coverage; schema makes `fixture_ref` optional with no closure check |
| 0/60 invariants individually traced | 60 | No `invariant_refs` field in schema; prompt says "incorporated as constraints" but never mandates tracing |
| 3/3 `cn:core` canon refs dangling | 3 | No pipeline step creates `cn:core` entries; namespace guidance absent from shared_expectations |
| HTTP method mismatch (PUT vs POST) | 1 | No cross-step API method validation; prompt doesn't enforce Step 05 contract alignment |
| Trace matrix duplicate FR entry | 1 | matrix.py collects from all arrays without deduplication |

All issues are generic toolkit deficiencies, not project-specific. The fixes below keep the toolkit domain-agnostic.

---

## 2. Investigation Methodology

All findings verified read-only. Commands run from `$PRODUCT_ROOT`:

```bash
source dev_env/bin/activate
specdev spec-check spec/ --spec-root spec/ --git-root .
specdev canonical-lint canon --repo-root ./devspec_toolkit --spec-root ./spec
specdev matrix spec/ --repo-root ./devspec_toolkit --spec-root ./spec --out spec/extras/trace_matrix.json
# Manual cross-checks: grep all fr_refs, capability_refs, fixture_refs, invariant IDs, threat IDs
# across spec/{01,04,05,06,07,08,11,14}_*.json
```

---

## 3. Confirmed Findings

### Category A — Prompt Coverage Closure Gaps (Critical)

> **DRY implementation note**: F1–F4 and F6 add items to the Coverage Closure checklist section. F5 adds guidance to the Cross-Step Synthesis section (different concern: *how* to populate trace vs *verifying* trace completeness). Implement the closure items (F1–F4, F6) as a single coherent "Upstream Artifact Coverage Matrix" block; keep F5's trace population guidance in Cross-Step Synthesis where it belongs. This maintains SoC between population guidance and verification checklists.

#### F1 — No fixture coverage enforcement in Coverage Closure

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, lines 73-86

**Bug**: Coverage Closure checklist verifies FR, capability, and milestone coverage but never checks that Step 08 fixtures are referenced by task acceptance criteria `fixture_ref` fields. Result: 39 of 78 fixtures were orphaned in the VC website roadmap.

**Evidence**: The prompt says fixtures are "used to bind milestone acceptance criteria to concrete fixture references" (line 28) but the closure checklist has no item enforcing this.

**Fix**: Add closure item:
```markdown
- [ ] Every fixture from Step 08 with category `contract` or `e2e` is referenced by >=1 task acceptance criterion `fixture_ref`, OR is documented in a deferred milestone with preservation rationale
```

#### F2 — No invariant tracing enforcement in Coverage Closure

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, lines 73-86

**Bug**: Step 06 invariants are ingested (line 26) as "task constraints and acceptance criteria" but Coverage Closure never verifies individual invariant IDs appear in the `trace` array. Result: all 60 invariants were compressed into a single abstract "invariants-catalog" entry.

**Fix**: Add closure item:
```markdown
- [ ] Every invariant from Step 06 appears in the `trace` array with type='invariant', an `id` matching the invariant's own ID, and a `note` naming the validating task
```

#### F3 — No threat mitigation coverage in Coverage Closure

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, lines 73-86

**Bug**: Step 11 threats are mentioned as inputs for "milestone risks and task prioritization" (line 30) but Coverage Closure doesn't verify that every threat has a trace entry. The VC website roadmap happened to cover all 20 threats, but nothing enforces this.

**Fix**: Add closure item:
```markdown
- [ ] Every threat from Step 11 appears in the `trace` array with type='threat', an `id` matching the threat's own ID, and a `note` documenting the mitigation task or risk acceptance rationale
```

#### F4 — No API contract alignment check in Coverage Closure

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, lines 73-86

**Bug**: Task acceptance criteria can reference API endpoints with methods/paths that contradict Step 05 interface contracts. The VC website roadmap had `PUT /themes/upload/` when Step 05 correctly defined `POST`.

**Fix**: Add closure item:
```markdown
- [ ] Task acceptance criteria referencing interface contracts use the same method/operation and identifier pattern as defined in Step 05 interface contracts
```

> **Generic mandate**: This rule is protocol-agnostic — it applies to HTTP methods, RPC operations, event names, CLI commands, or any interface contract type defined in Step 05.

#### F5 — No trace matrix population guidance

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`

**Bug**: The prompt never mentions the trace matrix or instructs the AI to populate the `trace` array systematically across all upstream artifact types (FR, capability, NFR, invariant, threat, governance, doc).

**Fix**: Add to Cross-Step Synthesis section:
```markdown
### trace
- Populate the `trace` array with one entry per upstream artifact that shapes this roadmap.
- Include trace entries for every upstream artifact type listed in Extraction Intent (both Primary Sources and Reference Sources). Valid trace types are defined in `$TOOLKIT_ROOT/canon/kinds/trace_type.json` — consult this file for the authoritative list. Typical roadmap trace types: fr, capability, nfr, invariant, threat, fixture, api, charter-goal. Additional types (doc, glossary, component) are valid but less common for roadmaps — include only when a specific upstream artifact of that type directly shaped a task.
- Each entry must have `type`, `id` (matching the upstream artifact's own ID), and `note` (naming the validating task or acceptance rationale).
- Coverage goal: every artifact ID consumed from upstream steps should appear as a trace entry. Orphaned upstream IDs indicate incomplete synthesis.
```

#### F6 — No NFR coverage enforcement in Coverage Closure

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, lines 73-86

**Bug**: NFR coverage happened to be complete in the VC website roadmap (17/17), but nothing in Coverage Closure enforces it. The same blind spot that missed fixtures and invariants also applies to NFRs.

**Fix**: Add closure item:
```markdown
- [ ] Every NFR from Step 07 appears in the `trace` array with type='nfr' and a note linking to the validating task and acceptance criterion
```

---

### Category B — Prompt Negative Constraints Gaps (High)

#### F7 — No guard against contradictory acceptance criteria

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, lines 61-71

**Bug**: The prompt states task ACs "REFINE" FR ACs (lines 43-46) but Negative Constraints don't forbid ACs that are less strict. No guidance on what constitutes refinement vs. contradiction.

**Fix**: Add to Negative Constraints:
```markdown
- **NEVER weaken an upstream AC**: Task acceptance criteria must be equal to or STRICTER than the originating FR acceptance criteria. A task AC that relaxes a threshold, removes a condition, or contradicts a constraint is a regression, not a refinement.
```

#### F8 — No guard against ambiguous task scope

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, lines 61-71

**Bug**: Schema enforces `description` pattern `^\S+\s+\S+.*$` (at least 2 words). Tasks like "Configure dependencies" pass validation but communicate no atomic scope.

**Fix**: Add to Negative Constraints:
```markdown
- **NO Ambiguous Task Scope**: Task `description` must name the specific deliverable artifact (endpoint, template, table, config, module) being created or modified. "Configure dependencies" is too vague — "Configure OAuth2 client credentials in session middleware settings" is specific.
```

---

### Category C — Schema Structural Gaps (High)

#### F9 — No `invariant_refs` field on tasks

**File**: `devspec_toolkit/schema/14_roadmap.schema.json`, task properties (lines 96-208)

**Bug**: Tasks have `fr_refs` (line 193-202) but no `invariant_refs` field. The prompt states invariants are "incorporated as task constraints" but the schema provides no structural way to declare which invariants a task enforces.

**Fix**: Add optional field to task properties:
```json
"invariant_refs": {
  "type": "array",
  "items": { "$ref": "vc:core:atoms#kebabId" },
  "uniqueItems": true,
  "description": "Invariant IDs from Step 06 that this task enforces or tests. Enables traceability from roadmap tasks back to system invariant guarantees. Add all invariants this task validates, even partially."
}
```

> **JSON Schema note**: `description` is placed on the parent `invariant_refs` object, not on `items` alongside `$ref`. In JSON Schema Draft 2020-12, sibling keywords next to `$ref` are ignored by compliant validators. The existing `fr_refs` field (lines 193-202) places `description` on `items` alongside `type`+`pattern` (no `$ref`), so there is no pre-existing inconsistency to replicate.
>
> **Generic note**: Uses `kebabId` atom instead of hardcoding an `inv-*` pattern. Invariant ID prefixes are project-specific — the schema should not assume a particular naming convention.
>
> **Consistency note**: This differs from `fr_refs` (which hardcodes `^fr-[a-z0-9]+(?:-[a-z0-9]+)*$`). The inconsistency is intentional — FR IDs have a universal `fr-` prefix convention, but invariant IDs do not. If a project adopts a consistent `inv-` prefix, a project-level lint rule in `specdev_tools/validation/` can enforce the pattern without baking it into the generic schema.
>
> **Placement note**: The task object uses `additionalProperties: false` (line 97). The new `invariant_refs` field MUST be added inside the existing `properties` block (lines 98-208), not as a sibling outside it. Misplacement will cause all existing roadmap artifacts to fail validation.

#### F10 — `fixture_ref` lacks conditional requirement guidance

**File**: `devspec_toolkit/schema/14_roadmap.schema.json`, AC properties (lines 125-128)

**Bug**: `fixture_ref` description says "Omit this field if no fixture has been defined for this criterion yet" which is accurate but insufficient. It doesn't guide the author to CHECK Step 08 before omitting.

**Fix**: Update description:
```json
"description": "Kebab-case ID of the fixture from spec/08_fixtures.json that validates this acceptance criterion. Before omitting, verify that no matching fixture exists in Step 08 — missing fixture_ref values create coverage gaps detectable by specdev matrix. If no fixture exists yet and one should, note it as a gap in milestone risks."
```

#### F11 — Conditional schema requirements not enforced

**File**: `devspec_toolkit/schema/14_roadmap.schema.json`

**Bug**: Several fields should be conditionally required but aren't:
- If `risk_status` is `high` or `critical`, `risks` should have `minItems: 1`
- If `status` is `done`, `acceptance_criteria` should have `minItems: 1`

**Fix**: Enforce via **prompt-level rules** (not JSON Schema `if/then` conditionals). Add to Negative Constraints:
```markdown
- If `risk_status` is 'high' or 'critical', the `risks` array MUST contain >=1 entry naming the specific blocker.
- If task `status` is 'done', the task MUST have >=1 acceptance criterion documenting what was verified.
```

> **Decision**: Prompt-level enforcement chosen over schema `if/then` conditionals. JSON Schema conditional composition adds dialect complexity that the toolkit's validation infrastructure doesn't need for two rules.
>
> **Validation gap**: Prompt-level rules only apply when an AI runner follows the prompt. Existing artifacts and manually-authored roadmaps won't be checked. A dedicated lint rule in `specdev_tools/validation/` (e.g., `roadmap_lint.py`) should enforce these two conditions programmatically. This is tracked as a follow-up, not blocked on this plan — the prompt rules provide immediate coverage for new artifact generation.

#### F12 — Trace array lacks Step 14-specific type guidance

**File**: `devspec_toolkit/schema/14_roadmap.schema.json`, trace property (lines 267-274)

**Bug**: The `trace` array description says "Traceability links connecting this roadmap to upstream FRs and capabilities" but doesn't enumerate the valid trace types for Step 14 or what IDs are expected per type.

**Fix**: Update description:
```json
"description": "Traceability links connecting this roadmap to all upstream artifacts. Step 14 should include trace entries for each upstream artifact type consumed in Extraction Intent (e.g., FRs from Step 04, NFRs from Step 07, invariants from Step 06, threats from Step 11, capabilities from Step 01, governance/CI references from Steps 10/12). The specific trace types must be valid entries from the canon trace_type registry. Each entry must have type, id (matching the upstream ID), and note (naming the validating task)."
```

> **Generic note**: Does not hardcode a fixed list of required trace types — references the canon trace_type registry and the step's own Extraction Intent section, which vary per project.

---

### Category D — Cross-Step Synthesis Gaps (Medium)

#### F13 — No capability-to-milestone completeness closure

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, lines 73-86

**Bug**: Prompt line 18 says "every capability is scheduled for delivery in at least one milestone" but Coverage Closure has no checkbox item enforcing this.

**Fix**: Add closure item:
```markdown
- [ ] Every capability_id from `spec/01_capabilities.json` appears in >=1 milestone's `capability_refs`
```

#### F14 — No invariant-to-fixture cross-check guidance

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`

**Bug**: The prompt mentions invariants (Step 06) and fixtures (Step 08) independently but never instructs the author to verify that high-severity invariants have negative-case fixtures testing violation scenarios.

**Fix**: Add to Cross-Step Synthesis:
```markdown
### Invariant-Fixture Cross-Check
- For each invariant from Step 06 with severity `error`, verify that Step 08 contains >=1 fixture with a target referencing that invariant ID. If missing, note it as a coverage gap in milestone risks rather than silently omitting the invariant from the trace.
```

#### F15 — No AC refinement decision rules

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, lines 42-47

**Bug**: The prompt says task ACs "REFINE" FR ACs but provides no decision rule for distinguishing refinement from contradiction or duplication.

**Fix**: Expand lines 42-47:
```markdown
### Refinement Decision Rules
- **Stricter threshold** = refinement: FR says "within 500ms", task says "within 200ms" — OK.
- **Weaker threshold** = contradiction: FR says "within 500ms", task says "within 1000ms" — FORBIDDEN.
- **Added edge case** = refinement: FR says "user can login", task adds "invalid credential returns error response" — OK.
- **Removed condition** = contradiction: FR says "authentication required", task says "authentication optional" — FORBIDDEN.
- **More specific artifact** = refinement: FR says "page renders", task says "read operation for resource returns success with expected component" — OK.
```

#### F16 — Governance/CI gates not bound to tasks

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, line 29

**Bug**: Steps 10 (governance) and 12 (CI gates) are referenced as context but the prompt doesn't guide binding governance rules or CI gates to specific milestone tasks.

**Fix**: Add to Cross-Step Synthesis:
```markdown
### Governance and CI Gate Binding
- If Step 10 defines PR labeling rules (e.g., `[fr-*]` tags), task descriptions implementing FRs should reference the FR ID to enable governance compliance.
- If Step 12 defines CI gates gating milestone completion, note them as exit_conditions on the relevant milestone's final task.
```

#### F17 — No downstream consumer validation

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`

**Bug**: Step 14's downstream consumers (Steps 15, 16, 16a, 16b, 16c per step_order.json) expect specific fields populated. The prompt never verifies the output satisfies downstream input requirements.

**Fix**: Add to Coverage Closure:
```markdown
- [ ] All required fields for downstream consumers (Step 15 scaffold, Step 16 trinity loop) are populated: `milestones[].tasks[].task_id`, `milestones[].tasks[].description`, `milestones[].tasks[].acceptance_criteria`, and `milestones[].tasks[].fr_refs`
```

---

### Category E — Shared Expectations Gaps (Medium)

#### F18 — No `cn:core` vs `cn:project` namespace guidance

**File**: `devspec_toolkit/docs/prompts/shared_expectations.md`

**Bug**: Canonical Registry Protocol (section 3) defines binding rules but doesn't distinguish when to use `cn:core:*` (universal toolkit vocabulary) vs `cn:project:*` (project-specific terms). Step 14 schema examples use `cn:core:status:pending` but this namespace may or may not exist in the project's canon manifest.

**Fix**: Add section:
```markdown
### Namespace Resolution
- `cn:core:*` — reserved for universal, toolkit-wide vocabulary: status (pending, in_progress, done, deferred), environment (dev, staging, prod), severity levels. These are defined in the toolkit's own `canon/manifest.json` or must be created in the project's `spec/canon/kinds/` if not present.
- `cn:project:*` — project-specific canonical entries: custom capabilities, roles, domain terms, dependencies. Created via `specdev canon-accept --from spec/03_glossary.json --repo-root ./devspec_toolkit` from Step 03 glossary (see CLAUDE.md § Canon management).
- Before emitting a `*_ref` field with a `cn:core:*` ID, verify the entry exists in either the toolkit's `canon/manifest.json` or the project's `spec/canon/manifest.json`. If missing, create it in the project's `spec/canon/kinds/{kind}.json` and manifest.
- For submodule deployments: add `--namespace cn:project: --owner product` to `canon-accept` to scope entries to project canon. Use `--git-root .` when running from the host repo.
```

#### F19 — No fixture completeness rule in shared expectations

**File**: `devspec_toolkit/docs/prompts/shared_expectations.md`

**Bug**: Steps whose schemas include `fixture_ref` fields (04, 14, 16) each have independent guidance on fixture binding. No shared rule ensures consistent fixture coverage expectations across steps.

**Fix**: Add section:
```markdown
### Fixture Traceability
- If this step's schema includes `fixture_ref` fields, every automatable acceptance criterion should have a fixture reference.
- Before omitting `fixture_ref`, check `spec/08_fixtures.json` for a matching fixture by target or category. Missing fixtures are coverage gaps, not permission to omit.
```

---

### Category F — Tooling Bugs (High)

#### F20 — matrix.py produces duplicate FR entries

**File**: `devspec_toolkit/tools/specdev_tools/validation/matrix.py`, lines 186-200

**Bug**: `build_trace_matrix()` collects FR entities by scanning ALL arrays in ALL spec files for objects with `*_id` fields. When an FR ID appears in both `functional_requirements[]` (Step 04) and `out_of_scope[]` (Step 05), both are added to the entity index, producing a duplicate row and inflated `fr_total`.

**Evidence**: `fr-collaborative-authoring` appears in:
- `spec/04_fr_list.json` → `functional_requirements[].fr_id` (canonical definition)
- `spec/05_interface_contracts.json` → `out_of_scope[].fr_id` (metadata reference)

Result: `fr_total: 25` instead of correct `24`; duplicate row in matrix output.

**Fix (Inline dedup during collection)**:
Deduplicate at the point of collection (lines 186-200) where the `field` name and `item[field]` value are already in hand. This avoids a post-hoc pass and eliminates the need for a separate `_extract_entity_id` helper or additional imports:
```python
# Replace lines 183-200 with:
entity_index = collections.defaultdict(list)  # normalized_trace_type -> [entity_objects]
seen_entities: set[tuple[str, str]] = set()   # (normalized_trace_type, id_value)

for data in artifacts.values():
    for key, value in data.items():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            for field in item:
                if not field.endswith("_id") or not isinstance(item[field], str):
                    continue
                prefix = field[:-3]  # strip "_id"
                normalized = normalize_trace_type(prefix)
                if is_valid_trace_type(normalized):
                    entity_key = (normalized, item[field])
                    if entity_key not in seen_entities:
                        entity_index[normalized].append(item)
                        seen_entities.add(entity_key)
                    break  # one entity type per object
```

> **Why inline, not post-hoc?** During collection the code already holds the raw `field` name and `item[field]` value — the exact ID that matters. A post-hoc dedup would need to re-discover which `*_id` field is the primary one, requiring alias resolution against `CANONICAL_TRACE_TYPE`. Inline dedup sidesteps that entirely: no new helper function, no new import, 3 added lines.
>
> **Why not a context whitelist?** A whitelist of array names (`functional_requirements`, `apis`, etc.) would address the root cause but requires maintenance as new step schemas add arrays. The dedup approach is defensive, handles unknown schemas, and doesn't couple matrix.py to specific step structures.

**Tests** (add to `tests/unit/validation/linters/test_matrix_rules.py`):

1. **Test — duplicate FR dedup**: Create temp-dir spec files with realistic structure: a `04_fr_list.json` containing `functional_requirements` with full FR objects (fr_id, statement, acceptance_criteria, priority), and a `05_interface_contracts.json` containing `out_of_scope` with the same `fr_id`. Call `build_trace_matrix()`. Assert `fr_total` counts the FR once, not twice. Assert the matrix array has no duplicate `fr_id` entries.
2. **Test — aliased trace type dedup**: Create temp-dir spec files where an entity with `inv_id` appears in two arrays (e.g., `invariants[]` and a reference array). Since `inv` normalizes to `invariant`, assert the entity appears once in `entity_index["invariant"]`.
3. **Test — no-dedup false positive**: Create temp-dir spec files with two genuinely different FRs (`fr-login` and `fr-logout`). Assert both appear in the matrix (dedup must not collapse distinct IDs).

> **Test location note**: These tests live in `tests/unit/validation/linters/test_matrix_rules.py` (existing file). They call `build_trace_matrix()` with real temp-dir files — this is the correct pattern for this test suite despite the `unit/` path. The file already mixes direct-call tests with temp-dir fixtures.

> **No mocking**: All tests call `build_trace_matrix()` directly with real temp-dir spec files matching the actual schema structure. No mocking of internal functions (`iter_spec_artifacts`, `normalize_trace_type`, etc.).
>
> **`repo_root` setup**: `build_trace_matrix(repo_root, spec_dir)` requires `repo_root` to resolve `step_order.json` and trace type normalization. In tests, pass the real toolkit directory (e.g., `Path(__file__).resolve().parents[4]` or the project's `devspec_toolkit/` root) as `repo_root`. Only `spec_dir` should point at the temp directory containing the test fixture spec files. Do not create a fake `repo_root` — it will fail on missing `tools/step_order.json`.

---

### Category G — CLI Ergonomics (Low)

#### F21 — canonical-lint positional arg confusion (UX improvement)

**File**: `devspec_toolkit/tools/specdev_tools/canonical/lint.py`, lines 31-80

**Bug**: When user passes `spec/canon/` as the positional `canon_dir` argument with `--repo-root ./devspec_toolkit`, the linter constructs `devspec_toolkit/spec/canon/manifest.json` which doesn't exist, producing a confusing `E520 UNRESOLVED_INPUT` error. The toolkit's canon lives at `devspec_toolkit/canon/`, not `devspec_toolkit/spec/canon/`.

**Root cause**: This is a CLI ergonomics issue, not a logic bug. `spec-check` calls `lint_canon_dirs()` (plural) correctly with separate toolkit and project canon paths. The error only occurs when manually running `canonical-lint` with a wrong positional arg. The existing path resolution logic is correct — only the error message is unhelpful.

**Evidence**: `lint_canon_dir(repo_root="./devspec_toolkit", canon_dir="spec/canon")` resolves to a non-existent path. The error message doesn't suggest the correct path or `--spec-root` usage.

**Fix**: Add an early-exit check in `lint_canon_dir()` between lines 38-47 (after `canon_root` is computed, before individual file checks). Use the existing `canon_root` variable — do not introduce a new `canon_path`:
```python
# Insert after line 38: canon_root = root / canon_dir
if not canon_root.exists():
    return [make_error("E520", f"UNRESOLVED_INPUT canon directory not found: {canon_root}. "
                        f"Expected 'canon' (toolkit core) or use --spec-root for project canon. "
                        f"For submodule deployments: specdev canonical-lint canon --repo-root ./devspec_toolkit --spec-root ./spec")]
```

**Test** (add to `tests/unit/canonical/test_canonical_lint.py`):

1. **Test — non-existent canon directory returns actionable E520**: Create a temp directory (no `canon/` subdirectory inside). Call `lint_canon_dir(repo_root=tmp, canon_dir="nonexistent")`. Assert result contains exactly 1 error with code `E520`. Assert the error message contains `"--spec-root"` (actionable submodule guidance). Assert no additional errors are returned — the early-exit check must prevent file-level lint errors on a missing directory.

---

### Category H — Prompt Usability (Low)

#### F22 — No atomicity decision rule for task decomposition

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, line 93

**Bug**: The prompt says "Each User Story must be broken down into specific, unambiguous, atomic sub-tasks" but provides no decision rule for when a task is too broad.

**Fix**: Add to Best Practices:
```markdown
- **Atomicity Test**: If a task description contains 'and' connecting two independent work items, split it into two tasks. If a task cannot be merged or demoed independently, split it further. Target: each task completable in 1-3 days by one developer.
```

#### F23 — No trace matrix CLI reference in prompt

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`

**Bug**: The prompt never references the `specdev matrix` CLI command. Authors don't know how to validate their roadmap's traceability coverage.

**Fix**: Add to Best Practices or Cross-Step Synthesis:
```markdown
- **Trace Validation**: After emitting the roadmap artifact, run `specdev matrix spec/ --repo-root ./devspec_toolkit` to generate the cross-artifact traceability matrix. Verify that `fr_with_fixture > 0`, `fr_with_nfr > 0`, and `fr_with_threat > 0` in the coverage summary.
```

---

### Category I — Pre-Existing Prompt Bug (High)

#### F24 — Hallucinated filename `04_functional_requirements.json` across prompts

**File**: `devspec_toolkit/prompts/prompt_14_roadmap.md`, line 89 (and 8 other live prompts)

**Bug**: The Extraction Mandate says:
```
Every FR ID from `04_functional_requirements.json` must appear in ≥1 milestone's `fr_refs`.
```
But the actual artifact filename is `04_fr_list.json` (confirmed by the Extraction Intent section at line 17: `04_fr_list.json`). This is a hallucinated path that could confuse both AI runners and human authors.

**Evidence**: Extraction Intent (line 17) correctly references `04_fr_list.json`. The Extraction Mandate (line 89) incorrectly references `04_functional_requirements.json`. No file named `04_functional_requirements.json` exists in the spec pipeline.

**Systemic scope**: `grep -r "04_functional_requirements.json" devspec_toolkit/prompts/` reveals the same hallucinated path in **9 live prompt files** (not just prompt_14):

| File | Lines |
|---|---|
| `prompts/prompt_05_interface_contracts.md` | 56, 58, 75, 79, 80 |
| `prompts/prompt_06_invariants.md` | 73 |
| `prompts/prompt_07_nfrs.md` | 64, 66 |
| `prompts/prompt_08_fixtures.md` | 49, 67 |
| `prompts/prompt_12_ci_gates.md` | 17 |
| `prompts/prompt_14_roadmap.md` | 89 |
| `prompts/prompt_15_scaffold.md` | 26 |
| `prompts/prompt_16a_impl_planner.md` | 32 |
| `prompts/prompt_16c_impl_reviewer.md` | 174 |

> **Verified**: `prompts/migration/template_frs.md` was originally listed but grep confirms it does NOT contain this hallucinated filename. Removed from scope — 9 files total, not 10.

**Fix**: Global find-and-replace across all 9 files listed above:
```
spec/04_functional_requirements.json → spec/04_fr_list.json
04_functional_requirements.json → 04_fr_list.json
```

> **Note**: Test files (`test_r9_quality_lint.py`, `test_dag_lint_rules.py`) also use this filename for temp fixture filenames. These are test-internal and don't affect runtime, but should be updated for consistency. The prompt file `prompt_04_functional_requirements.md` itself is correctly named — it's the *prompt* for step 04, not the artifact. Only references to the *spec artifact* filename need fixing.

---

## 4. Execution Plan

### Phase 1 — Schema & Prompt Hardening (F1-F12, F22-F24)

**Files modified**:
- `devspec_toolkit/prompts/prompt_14_roadmap.md`
- `devspec_toolkit/schema/14_roadmap.schema.json`
- `devspec_toolkit/prompts/prompt_05_interface_contracts.md` (F24 filename fix)
- `devspec_toolkit/prompts/prompt_06_invariants.md` (F24 filename fix)
- `devspec_toolkit/prompts/prompt_07_nfrs.md` (F24 filename fix)
- `devspec_toolkit/prompts/prompt_08_fixtures.md` (F24 filename fix)
- `devspec_toolkit/prompts/prompt_12_ci_gates.md` (F24 filename fix)
- `devspec_toolkit/prompts/prompt_15_scaffold.md` (F24 filename fix)
- `devspec_toolkit/prompts/prompt_16a_impl_planner.md` (F24 filename fix)
- `devspec_toolkit/prompts/prompt_16c_impl_reviewer.md` (F24 filename fix)
- `devspec_toolkit/tests/fixtures/step_14/` (F9 test fixtures)

| Task | Findings | Effort |
|---|---|---|
| Add 5 Coverage Closure items to prompt (fixture, invariant, threat, API, NFR) | F1, F2, F3, F4, F6 | Small |
| Add trace population guidance to Cross-Step Synthesis section | F5 | Small |
| Add 2 Negative Constraints to prompt | F7, F8 | Small |
| Add `invariant_refs` field to task schema (inside `properties` block — `additionalProperties: false` is set) | F9 | Small |
| Add valid/invalid test fixtures for `invariant_refs` field | F9 | Small |
| Update `fixture_ref` description in schema | F10 | Trivial |
| Add conditional requirement guidance to schema/prompt | F11 | Small |
| Update trace array description in schema | F12 | Small |
| Add atomicity rule and trace matrix reference to prompt | F22, F23 | Trivial |
| Fix hallucinated filename `04_functional_requirements.json` → `04_fr_list.json` across 9 prompt files | F24 | Small |

**Validation**:
1. `specdev prompt-sync spec --repo-root ./devspec_toolkit` (verify prompt-schema alignment across ALL steps, including F24-affected prompts 05/06/07/08/12/14/15/16a/16c)
2. `specdev spec-check spec/ --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` (regression test on project specs)
3. `pytest tests/ -v` (verify schema changes don't break existing validation tests — includes new F9 `invariant_refs` fixtures)
4. `grep -r "04_functional_requirements.json" devspec_toolkit/prompts/` (verify no remaining hallucinated path references in live prompts)

**F9 schema test plan** (add to `tests/fixtures/step_14/`):
- Add a valid fixture variant that includes a task with `"invariant_refs": ["inv-no-duplicate-sessions"]` — must pass validation.
- Add an invalid fixture variant with `"invariant_refs": ["INVALID_UPPER_CASE"]` — must fail validation (violates `kebabId` pattern).
- Existing fixtures without `invariant_refs` must continue to pass (field is optional).

### Phase 2 — Cross-Step Synthesis & Shared Expectations (F13-F19)

**Files modified**:
- `devspec_toolkit/prompts/prompt_14_roadmap.md`
- `devspec_toolkit/docs/prompts/shared_expectations.md`

| Task | Findings | Effort |
|---|---|---|
| Add capability closure item | F13 | Trivial |
| Add invariant-fixture cross-check guidance | F14 | Small |
| Add AC refinement decision rules | F15 | Small |
| Add governance/CI gate binding guidance | F16 | Small |
| Add downstream consumer validation | F17 | Small |
| Add namespace resolution section to shared_expectations | F18 | Small |
| Add fixture completeness rule to shared_expectations | F19 | Trivial |

> **F18 dependency note**: The `canon-accept --namespace` and `--owner` flags referenced in F18's fix are documented in `$TOOLKIT_ROOT/CLAUDE.md` § Canon management. Verified: `cli.py:356` registers `--namespace` (default `cn:project:`) and `cli.py:359` registers `--owner`.

**Validation**:
1. `specdev extraction-intent-check --repo-root ./devspec_toolkit` (verify extraction intent consistency)
2. `specdev prompt-sync spec --repo-root ./devspec_toolkit` (verify shared_expectations changes don't break prompt-schema alignment)
3. `specdev spec-check spec/ --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` (regression test on project specs)
4. `specdev canonical-lint canon --repo-root ./devspec_toolkit` (verify `cn:core` entries referenced in F18 guidance actually exist in toolkit canon)
5. `specdev canonical-lint spec/canon --repo-root ./devspec_toolkit --spec-root ./spec` (verify project-tier canon lint works in submodule mode — confirms F18 namespace guidance is actionable)

### Phase 3 — Tooling Fixes (F20, F21)

**Files modified**:
- `devspec_toolkit/tools/specdev_tools/validation/matrix.py`
- `devspec_toolkit/tools/specdev_tools/canonical/lint.py`
- `devspec_toolkit/tests/unit/validation/linters/test_matrix_rules.py`
- `devspec_toolkit/tests/unit/canonical/test_canonical_lint.py`

| Task | Findings | Effort |
|---|---|---|
| Add inline `seen_entities` dedup to entity collection loop in matrix.py (3 lines, no new imports) | F20 | Small |
| Add integration test: duplicate FR across `functional_requirements` and `out_of_scope` arrays | F20 | Small |
| Add integration test: aliased trace type dedup (`inv_id` → `invariant`) | F20 | Small |
| Add integration test: distinct FRs not falsely deduplicated | F20 | Small |
| Improve error message in canonical-lint for non-existent canon dir (use existing `canon_root` var) | F21 | Small |
| Add test case for non-existent canon directory error message | F21 | Small |

**Validation**:
1. `pytest tests/ -v` (full test suite including new tests)
2. `specdev matrix spec/ --repo-root ./devspec_toolkit` (verify dedup on project with known duplicates — note: `--spec-root` is parsed but unused by the matrix command)
3. `specdev spec-check spec/ --repo-root ./devspec_toolkit --spec-root ./spec --git-root .` (regression test on project specs)

---

## 5. Schema Compatibility

Schema changes in Phase 1 (F9, F10, F12) are **backwards-compatible**: all additions are optional fields or description-only updates. Existing valid roadmap artifacts will continue to pass validation without modification. No `$id` URI version bump or `registry_version` update is required.

If a future phase adds required fields or breaking changes, the schema `$id` must be versioned (e.g., `vc:14-roadmap-v2`) and a migration path documented.

---

## 6. Dependencies & Ordering

```
Phase 1 (Schema/Prompt) ─── no prerequisites
Phase 2 (Cross-Step)    ─── depends on Phase 1 (prompt changes must be coherent)
Phase 3 (Tooling)       ─── code changes independent of Phases 1-2 (can run in parallel)
                             validation: Phase 3's `spec-check` regression test should
                             run after Phase 1 schema changes are committed to avoid
                             false positives from schema/artifact mismatch
```

Phase 3 (F20 matrix bug) can be done independently and first if desired, since it's a standalone code fix with a clear test case.

---

## 7. Out of Scope

- **Project-specific fixes** to `spec/14_roadmap.json` — those were already applied in the review session (39 fixture refs added, 63 invariant traces added, PUT→POST fixed, cn:core entries created).
- **Matrix tool enhancement** to auto-populate api/fixture/threat linkages per FR — this is a feature request, not a bug fix. The matrix tool currently only populates NFR linkages. Tracked separately.
- **Matrix `--spec-root` wiring** — the matrix CLI parses `--spec-root` and `--git-root` but does not pass them to `build_trace_matrix()`. This is a pre-existing gap, not introduced by this plan. Tracked separately.
- **Other step prompts** (08, 09, 11) — they may have similar Coverage Closure gaps but are not in scope here. Each step should get its own review.
- **Schema `if/then` conditionals** for conditional requirements (F11) — prompt-level enforcement for now. Follow-up: dedicated `roadmap_lint.py` rule to enforce on existing artifacts.
- **Test fixture filename cleanup** — `test_r9_quality_lint.py` and `test_dag_lint_rules.py` use `04_functional_requirements.json` as temp fixture filenames. These don't affect runtime. Update for consistency as a low-priority follow-up.

---

## 8. Risk Assessment

| Risk | Probability | Mitigation |
|---|---|---|
| Prompt changes break existing valid roadmap artifacts | Low | Run `specdev validate` on existing project artifacts before and after |
| Schema `invariant_refs` field addition causes validation failures on existing specs | Low | Field is optional; existing specs without it will pass |
| Matrix dedup fix masks legitimate duplicate references | Low | Dedup only by `(trace_type, id_value)` tuple; integration test verifies distinct IDs are preserved |
| Shared expectations changes affect other step prompts | Medium | Review shared_expectations consumers before merge; changes are additive (new sections, not modifications) |
| F24 filename fix across 9 prompts may break existing AI runner caches or prompt hashes | Low | The fix corrects a hallucinated path — any cache referencing `04_functional_requirements.json` was already broken. Run `specdev prompt-sync spec --repo-root ./devspec_toolkit` after to verify prompt-schema alignment across all affected steps |
| F24 test fixture filenames (`test_r9_quality_lint.py`) use `04_functional_requirements.json` | Low | These are temp fixture filenames, not runtime paths. Update for consistency but no runtime impact if missed |
| F11 prompt-level rules not enforced on existing artifacts | Medium | Documented as follow-up lint rule. Prompt rules provide immediate coverage for new generation |
