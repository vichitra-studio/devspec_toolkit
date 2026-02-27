<review_prompt id="R9" layer="L3+L4" gaps="8,9,10,11,12,13,14,15" runs_after="R7,R8" priority="P0-critical">
# Review R9: Validator & CI Enforcement Closure

## Scope
**Prior reviews completed**: R1-R8. All prompts are hardened (R7), all schemas tightened to match (R8). The generation side (L1+L2) is closed.

This review is the **third and final layer** of the 4-Layer Determinism Closure. It closes all semantic validation gaps that schemas cannot enforce structurally: cross-step ID resolution, content propagation, extraction_intent activation, quality scanning, hallucination detection, coverage enforcement, forward replay, and W→E promotion.

### Gaps Closed

| # | Gap | Severity | Layer |
|---|-----|----------|-------|
| 8 | 8 of 16 validators have zero cross-step ID validation | CRITICAL | L3 |
| 9 | Content propagation absent — zero checks downstream content relates to upstream | CRITICAL | L3 |
| 10 | `extraction_intent` in step_order.json is inert — no validator reads it | HIGH | L3 |
| 11 | Vague language scanning only covers `assumptions`, not free-text fields | HIGH | L3 |
| 12 | hallucination_lint checks enum/ID only, not content derivation | HIGH | L3 |
| 13 | Forward replay is ID-only, no downstream content staleness detection | MED | L3 |
| 14 | FR coverage metrics computed but no thresholds enforced | MED | L3 |
| 15 | W→E promotion covers only 4 of ~15+ warning codes | MED | L4 |

### Why R9 Runs Last

Validators and CI gates are the **enforcement layer** — they catch what schemas can't enforce structurally. They must build against final prompts (R7) and final schemas (R8). If we built validators first, every prompt or schema change would break them. R9 builds once, against stable targets. Zero rework.

---

## Files Under Review

| Category | Files |
|----------|-------|
| Error codes | `tools/specdev_tools/core/errors.py` |
| Step validators (8 gap targets) | `tools/specdev_tools/validation/validators/step_05.py`, `step_06.py`, `step_08.py`, `step_09.py`, `step_12.py`, `step_13.py`, `step_13a.py`, `step_15.py` |
| Step validators (reference, have cross-step checks) | `step_04.py`, `step_07.py` (established `_load_*_ids()` pattern) |
| Quality linter | `tools/specdev_tools/validation/spec_quality_lint.py` |
| Hallucination linter | `tools/specdev_tools/validation/hallucination_lint.py` |
| Forward replay | `tools/specdev_tools/validation/forward_replay_check.py` |
| Traceability matrix | `tools/specdev_tools/validation/matrix.py` |
| Main validator | `tools/specdev_tools/validation/validate.py` |
| CLI entry point | `tools/specdev_tools/cli.py` |
| Step order config | `tools/step_order.json` |
| Tests | `tests/` (new + existing) |

---

## What R7+R8 Leave Open

After R7 (prompts hardened) and R8 (schemas tightened), these semantic gaps remain because they cannot be enforced by schema structure alone:

| Gap | Why Schema Can't Enforce It | Validator Solution |
|-----|----------------------------|--------------------|
| Cross-step ID references | Schema validates structure, not cross-file references | Load upstream file, resolve IDs |
| Content propagation | Schema validates types, not semantic derivation | Token co-occurrence check |
| extraction_intent | Metadata in step_order.json, not in schema | New validator reads intent metadata |
| Vague language in free-text | Schema validates string type, not content quality | Regex scan on all free-text fields |
| Content-based hallucination | Schema validates enum/ID, not content origin | Token overlap with upstream |
| Downstream staleness | Schema is per-file, not cross-file temporal | Forward replay extension |
| Coverage thresholds | Schema validates structure of matrix, not percentages | Threshold enforcement in matrix.py |
| W→E promotion | Orthogonal to schema validation | Dynamic code pairing in validate.py |

---

## Subagent Protocol (MANDATORY)

### Main Agent Rules
- **FORBIDDEN in main agent**: Read, Edit, Write, Grep, Glob, Bash for file content
- **All investigation MUST be delegated to subagents — no exceptions**
- Main agent: receive summaries, synthesize findings table, create task list, final report
- Token budget: < 5K tokens total for main agent across all phases

### Subagent Assignment

#### Phase 1 — Investigation (3 Explore subagents, launch together)

**Subagent A** (`Explore`, no isolation) — Cross-Step Integrity Audit:
```
Audit all 16 step validators for cross-step ID checking capability.

1. For each validator in tools/specdev_tools/validation/validators/step_*.py:
   a. Does it load any upstream file? (look for open(), json.load, _load_*_ids patterns)
   b. Does it resolve IDs against upstream? (look for "id" in, id_set, reference checks)
   c. What error codes does it emit? (look for E***, W*** patterns)

2. Classify each validator:
   - HAS cross-step checks (e.g., step_04.py, step_07.py)
   - MISSING cross-step checks (the 8 gap validators)
   - N/A (step has no upstream ID dependencies per step_order.json)

3. Read tools/step_order.json → step_metadata section:
   a. For each step, list extraction_intent entries
   b. Classify each extraction_intent as: ID-resolution | field-presence | semantic
   c. For step 00: note it may have empty extraction_intent — flag if so

4. Read tools/specdev_tools/validation/matrix.py:
   a. Does it compute coverage percentages?
   b. Does it enforce any thresholds?
   c. What would a configurable threshold look like?

Produce tables:
- Validator cross-step status: | Step | Has Cross-Step? | Upstream Files | IDs Checked | Error Codes |
- extraction_intent classification: | Step | Intent | Classification |
- matrix.py: coverage computation status, threshold feasibility
```

**Subagent B** (`Explore`, no isolation) — Semantic Quality Audit:
```
Audit semantic quality checking capabilities across the codebase.

1. VAGUE LANGUAGE SCANNING:
   a. Read tools/specdev_tools/validation/spec_quality_lint.py
   b. What fields does W571 scan? (expected: only `assumptions`)
   c. How is the vague pattern defined? (regex? word list?)
   d. List ALL free-text fields across spec/ artifacts that SHOULD be scanned
      (descriptions, rationale, notes, narrative fields — NOT metadata like $schema, IDs)

2. CONTENT DERIVATION:
   a. Read tools/specdev_tools/validation/hallucination_lint.py
   b. What does it currently check? (expected: enum/ID validity only)
   c. Does it load upstream files for comparison?
   d. Is there a token co-occurrence algorithm already? (R4 may have added W140)

3. FORWARD REPLAY:
   a. Read tools/specdev_tools/validation/forward_replay_check.py
   b. What does it currently detect? (expected: ID-only changes)
   c. Does it have extension points for content staleness?
   d. What upstream token comparison would look like

4. Count vague quantifiers in actual spec/ artifacts:
   Search for: "several", "various", "multiple", "some", "appropriate", "adequate",
   "sufficient", "reasonable", "significant", "typical", "generally", "usually"
   in free-text fields across spec/*.json

Report: per-tool capability summary, extension feasibility, vague quantifier counts.
```

**Subagent C** (`Explore`, no isolation) — Enforcement Completeness Audit:
```
Audit the complete W-code and E-code inventory for promotion coverage.

1. Read tools/specdev_tools/core/errors.py:
   a. List ALL W-codes (W***) with their names — known existing: W110, W120, W130, W140,
      W550, W560, W570 (GRACEFUL_SKIP), W571, W572, W573, W580, W581, W561, W562, W563
   b. List ALL E-codes (E***) with their names
   c. For each W-code, does a matching E-code exist? (same suffix)
   d. Which W-codes are currently promotable via SPECDEV_WARNINGS_AS_ERRORS?
   e. What is the HIGHEST used code number? (needed for Subagent D to pick safe new codes)

2. Read tools/specdev_tools/validation/validate.py:
   a. How does W→E promotion currently work?
   b. Is it hard-coded to specific codes or dynamic?
   c. What environment variables control promotion?

3. ENVIRONMENT VARIABLE INVENTORY:
   Search for ALL os.getenv() or os.environ calls in tools/specdev_tools/:
   a. List every env var name
   b. Document what each controls
   c. Are there undocumented env vars?

4. Read tools/specdev_tools/cli.py:
   a. What commands are registered?
   b. Is there an `env-check` or diagnostic command?
   c. Where would a new `env-check` command be added?

Report:
- W-code inventory: | Code | Name | Has E-pair? | Promotable? |
- E-code inventory: | Code | Name | Source |
- Env var inventory: | Var | File | Purpose | Documented? |
- CLI command inventory: | Command | Handler | Description |
```

#### Phase 2 — Implementation (after Phase 1, sequential by dependency)

**P0 — Error Codes First (everything else references them)**

**Subagent D** (`general-purpose`, isolation: `worktree`) — New error codes:
```
Add new error/warning codes to tools/specdev_tools/core/errors.py.

CRITICAL: Before adding codes, verify the CURRENT state of errors.py. Known existing codes
in the E/W 570 range that MUST NOT be redefined:
- W570 = GRACEFUL_SKIP (already exists — generic graceful skip warning)
- W571 = ASSUMPTION_VAGUE_QUANTIFIER (already exists)
- W572 = ASSUMPTION_COUNT_HIGH (already exists)
- W573 = ASSUMPTION_UNBOUND_ID (already exists)
- W580 = SUBSTEP_DRIFT (already exists)
- W581 = MILESTONE_REF_MISSING (already exists)
- E582 = MILESTONE_REF_MISMATCH (already exists)
- W140 = SEED_CONTENT_OVERLAP_LOW (already exists — token co-occurrence pattern from R4)

New codes to add (using AVAILABLE code numbers — verify no conflicts):
- E590 / W590: CROSS_STEP_REF_UNRESOLVED — cross-step ID reference cannot be resolved
  E590: upstream file exists but referenced ID not found (hard error)
  W590: upstream file is missing — graceful skip (reuses W570 GRACEFUL_SKIP semantics
        but W590 is specific to cross-step refs for independent promotion control)
- E591 / W591: EXTRACTION_INTENT_VIOLATION — field required by extraction_intent is missing or empty
- E592 / W592: COVERAGE_THRESHOLD_BELOW — FR coverage metric below configured threshold
- E593 / W593: VAGUE_QUANTIFIER_IN_FREE_TEXT — vague quantifier found in non-assumption free-text field
  (separate from W571 which covers assumptions — allows independent promotion control)
- E594 / W594: CONTENT_DERIVATION_WEAK — insufficient token overlap with upstream content
  (heuristic check — W594 by default, E594 exists for optional promotion)
- E595 / W595: DOWNSTREAM_STALE — upstream content changed but downstream doesn't reflect changes
  (advisory — W595 by default, E595 exists for optional promotion)

EVERY new W-code MUST have a corresponding E-code to enable dynamic W→E promotion.
Even heuristic checks (W594, W595) get E-code pairs — the E-code exists for promotion,
not because it fires directly. This ensures "ALL W-codes promotable" goal is met.

Follow the existing ERROR_CODES dict pattern in errors.py.

After changes: pytest tests/ -k error -v (or relevant error code tests)
```

**P0 — Cross-Step Referential Integrity (8 validators)**

**Subagent E** (`general-purpose`, isolation: `worktree`) — Cross-step checks for steps 05, 06, 08, 09:
```
Add cross-step ID validation to 4 validators that currently have none.

Use the established pattern from step_04.py and step_07.py:
1. Define a _load_*_ids(spec_dir) helper that loads the upstream file and extracts valid IDs
2. For each ID reference field in the current step, check it exists in upstream
3. Emit W590 when upstream file is missing (graceful skip — don't block validation)
4. Emit E590 when upstream file exists but referenced ID is not found

For each validator, determine upstream dependencies from tools/step_order.json:

- step_05.py (interface_contracts): references FR IDs from step 04
- step_06.py (invariants): references FR IDs from step 04
- step_08.py (fixtures): references FR IDs, API IDs, NFR IDs, invariant IDs
- step_09.py (impl_plan): references capability IDs from step 01, FR IDs from step 04

Read each validator's CURRENT state first (R1-R6 may have modified them).
Add cross-step checks WITHOUT removing existing validation logic.

After changes: pytest tests/ -k "step_05 or step_06 or step_08 or step_09" -v
```

**Subagent F** (`general-purpose`, isolation: `worktree`) — Cross-step checks for steps 12, 13, 13a, 15:
```
Add cross-step ID validation to 4 more validators.

Same pattern as Subagent E:

- step_12.py (ci_gates): references FR IDs, NFR IDs from upstream steps
- step_13.py (extension_generator): references governance labels from step 10
- step_13a.py (completeness): performs traceability verification — checks FR-to-API and
  API-to-fixture coverage against upstream. NOTE: step_13a's extraction_intent in
  step_order.json says "Verify FR-to-API traceability" and "Verify all capabilities" —
  this is VERIFICATION, not direct ID extraction. The cross-step check here should verify
  that referenced IDs exist upstream, but the primary function is coverage/completeness
  assessment. Use the same _load_*_ids() pattern for ID resolution, but be aware the
  step's purpose is broader (traceability verification, not just ID presence).
- step_15.py (scaffold): references API IDs from step 05, FR IDs from step 04

Read each validator's CURRENT state first.
W590 for missing upstream files, E590 for unresolved IDs.

After changes: pytest tests/ -k "step_12 or step_13 or step_13a or step_15" -v
```

**Subagent G** (`general-purpose`, isolation: `worktree`) — extraction_intent validator:
```
Create a new extraction_intent field-presence validator.

1. Read tools/step_order.json → step_metadata → extraction_intent for each step
2. Create tools/specdev_tools/validation/extraction_intent_check.py:
   - For each step with extraction_intent entries:
     a. Parse the intent to determine which fields should be present
     b. Load the step's artifact from spec/
     c. Check that the expected fields exist and are non-empty
     d. Emit E591 when a required field (per extraction_intent) is missing or empty
   - This is FIELD-PRESENCE only — not semantic matching
   - Deterministic, zero false positives

3. Wire into tools/specdev_tools/validation/validate.py:
   - Add extraction_intent_check to the validation pipeline
   - Make it optional (skip if step_order.json doesn't have extraction_intent for the step)

4. Populate step 00's extraction_intent in step_order.json if empty

After changes: pytest tests/ -v (create new test file tests/test_extraction_intent.py)
```

**P1 — Semantic Quality Hardening**

**Subagent H** (`general-purpose`, isolation: `worktree`) — Vague language scanner expansion:
```
Expand spec_quality_lint.py to scan ALL free-text fields, not just assumptions.

1. Read tools/specdev_tools/validation/spec_quality_lint.py (current state)
2. Extract the vague language scanner into a reusable function:
   _scan_for_vague_language(text: str) → list[str]
3. Apply to ALL free-text fields in spec artifacts:
   - descriptions, rationale, notes, narrative, summary fields
   - NOT metadata fields ($schema, spec_version, IDs, enums, generation_quality)
4. Emit W593 (VAGUE_QUANTIFIER_IN_FREE_TEXT) for matches in non-assumption fields
   - Keep W571 for assumption-specific vague language (separate promotion control)
5. Add vague quantifier patterns: "several", "various", "multiple", "some", "appropriate",
   "adequate", "sufficient", "reasonable", "significant", "typical", "generally", "usually"

After changes: pytest tests/ -k quality -v
```

**Subagent I** (`general-purpose`, isolation: `worktree`) — Content derivation check:
```
Add content derivation checking to hallucination_lint.py.

1. Read tools/specdev_tools/validation/hallucination_lint.py (current state)
2. Add a token co-occurrence check:
   - For each step with declared upstream dependencies (from step_order.json):
     a. Load the upstream artifact
     b. Tokenize relevant upstream fields (simple whitespace + lowercase split)
     c. Tokenize the downstream free-text fields
     d. Count distinct upstream tokens that appear in downstream
     e. If count < threshold (default: 5 distinct tokens), emit W594
   - This is the same algorithm pattern as R4's W140 (SEED_CONTENT_OVERLAP_LOW, already in errors.py).
     Reuse the tokenization logic from W140's implementation if available.
3. Add configuration to step_order.json:
   `"content_derivation": {"min_token_overlap": 5, "enabled": true}`
4. W594 is a WARNING by default (heuristic). E594 exists for optional promotion but should
   NOT be the default mode — content derivation is approximate.

After changes: pytest tests/ -k hallucination -v
```

**Subagent J** (`general-purpose`, isolation: `worktree`) — Forward replay staleness detection:
```
Extend forward_replay_check.py to detect downstream content staleness.

1. Read tools/specdev_tools/validation/forward_replay_check.py (current state)
2. Add downstream staleness detection:
   - When an upstream file changes, extract new/modified tokens
   - Check if those tokens appear somewhere in downstream artifacts
   - If new upstream content has zero downstream reflection, emit W595
3. This is an extension of existing forward replay — not a replacement
4. W595 is advisory — it flags potential staleness, not definite errors

After changes: pytest tests/ -k replay -v
```

**Subagent K** (`general-purpose`, isolation: `worktree`) — Coverage threshold enforcement:
```
Add configurable threshold enforcement to matrix.py.

1. Read tools/specdev_tools/validation/matrix.py (current state)
2. Add threshold configuration:
   - Read from step_order.json: `"coverage_thresholds": {"fr_coverage": 80, "mode": "warn"}`
   - If mode is "warn": emit W592 when coverage < threshold
   - If mode is "error": emit E592 when coverage < threshold
   - Default: mode="warn", threshold=80%
3. Add the `coverage_thresholds` config to step_order.json

After changes: pytest tests/ -k matrix -v
```

**P1 — CI Enforcement Closure**

**Subagent L** (`general-purpose`, isolation: `worktree`) — Dynamic W→E promotion:
```
Generalize W→E promotion in validate.py.

1. Read tools/specdev_tools/validation/validate.py (current state)
2. Replace hard-coded W→E promotion with dynamic pairing:
   - Any W-code that has a matching E-code (same numeric suffix) is automatically promotable
   - SPECDEV_WARNINGS_AS_ERRORS=1 promotes ALL W-codes with E-code pairs
   - Add SPECDEV_PROMOTE_CODES env var for per-code granularity:
     SPECDEV_PROMOTE_CODES=W571,W593 → only promote those specific codes
3. Ensure backwards compatibility:
   - Existing SPECDEV_WARNINGS_AS_ERRORS=1 behavior is preserved (promotes everything)
   - New SPECDEV_PROMOTE_CODES is additive granularity

After changes: pytest tests/ -k validate -v
```

**Subagent M** (`general-purpose`, isolation: `worktree`) — env-check diagnostic command:
```
Add a read-only `specdev env-check` diagnostic command.

1. Read tools/specdev_tools/cli.py (current state)
2. Add `env-check` command that reports:
   - All SPECDEV_* environment variables and their current values
   - Active validation checks (which are enabled/disabled)
   - Replay base ref resolution (what ref would be used)
   - W→E promotion status (which codes are promoted)
   - Spec directory and repo root paths
3. This command is READ-ONLY — it MUST NOT modify any state
4. Output is human-readable diagnostic information

After changes: run the command to verify output, pytest tests/ -k cli -v
```

**P2 — Documentation**

**Subagent N** (`general-purpose`, isolation: `worktree`) — Error code documentation:
```
Create/update docs/developers/error-codes.md with complete error code documentation.

1. Read tools/specdev_tools/core/errors.py (current state, including R9 additions)
2. Document every error code:
   - Code (E/W number)
   - Name
   - Description
   - When it fires
   - How to fix
   - Promotion status (W→E pair exists?)
3. Group by category:
   - Cross-step integrity (E590/W590, E591/W591)
   - Quality (W571 assumptions, W592 coverage, W593 free-text vague)
   - Content derivation (W594/E594)
   - Staleness (W595/E595)
   - Existing codes (preserve current documentation for E110-E582, W110-W581, W140)

After changes: verify no broken links
```

**Subagent O** (`general-purpose`, isolation: `worktree`) — Instruction coverage map:
```
Create docs/instruction_coverage_map.md documenting the L1→L2→L3 enforcement chain.

For high-impact steps (04, 05, 09, 16a, 16c at minimum):
| Prompt Instruction | Schema Constraint | Validator Check | Error Code |
|--------------------|-------------------|-----------------|------------|
| "MUST include trace" | trace in required[] | step_04 cross-ref | E590 |
| ... | ... | ... | ... |

This is the traceability artifact showing which prompt instruction is enforced by which
schema constraint and which validator check. It closes the 4-layer model by documenting
the enforcement chain.
```

#### Phase 3 — Integration Test Run

**Subagent P** (`general-purpose`, no isolation) — Full integration verification:
```
Run the complete validation suite:

1. pytest tests/ -v
2. ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
3. ./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit
4. ./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit
5. ./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit
6. ./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
7. ./tools/run_specdev.sh dependency-order-lint --repo-root ./devspec_toolkit

Test with promotion:
8. SPECDEV_WARNINGS_AS_ERRORS=1 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
   (expect: all W-codes promoted to E-codes where pairs exist)
9. SPECDEV_PROMOTE_CODES=W571,W593 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
   (expect: only W571 promoted to E571, and W593 promoted to E593)

10. ./tools/run_specdev.sh env-check --repo-root ./devspec_toolkit
    (expect: diagnostic output, no errors)

All must pass (except promotion tests which may show expected warnings-as-errors).
Report any failures with exact error messages.
```

#### Phase 4 — Self-Verification

**Subagent Q** (`Explore`, no isolation) — Verify R9 goals met:
```
After all implementation is complete, verify measurable goals:

1. Count validators with cross-step ID checks:
   Read each step_*.py validator. Target: 16/16 (or all that have upstream dependencies).

2. Count promotable W-codes:
   Read errors.py. For each W-code, check if matching E-code exists.
   Target: ALL W-codes have E-code pairs (dynamic promotion covers them).

3. Verify free-text field scanning:
   Read spec_quality_lint.py. Does W593 scan ALL free-text fields?
   Target: yes (not just assumptions).

4. Verify content derivation:
   Read hallucination_lint.py. Does it check token co-occurrence?
   Target: yes, with configurable threshold.

5. Verify SPECDEV_WARNINGS_AS_ERRORS=1 coverage:
   Read validate.py. Is promotion dynamic (any W with matching E)?
   Target: yes, 100% coverage.

6. Verify env-check command exists:
   Read cli.py. Is env-check registered?
   Target: yes, read-only.

Report: per-goal pass/fail.
```

#### Phase 5 — Findings Report

**Subagent R** (`general-purpose`, no isolation) — Write findings:
```
Write findings to docs/audit/findings/r9_findings.md using compact table format.

Include:
- Part A: Findings table (all validator/CI gaps found, with severity and resolution status)
- Part B: Implementation summary (new error codes, validators enhanced, CI changes)
- Part C: New capabilities added (extraction_intent, content derivation, dynamic promotion, env-check)
- Part D: Measurable goals verification (from Phase 4)
- Part E: Residual issues (if any, with rationale)

Also update docs/audit/review_index.md to add R9 entry.
Update CHANGELOG with all R9 additions (new error codes, validator enhancements, env-check command, dynamic promotion).

Include a FINAL CLOSURE SUMMARY:
"After R7→R8→R9, the 4-Layer Determinism Closure is complete:
- L1 (Prompts): 100% field coverage, zero vague language, explicit sourcing
- L2 (Schemas): All required[] match prompts, zero rejection bugs
- L3 (Validators): Cross-step IDs, content derivation, vague scanning, extraction_intent
- L4 (CI Gates): Dynamic W→E promotion, per-code granularity, env-check diagnostic"
```

---

## Key Design Decisions

- Cross-step checks: **W590** (upstream missing, graceful skip) vs **E590** (upstream exists, ID unresolved). Does NOT redefine existing W570 (GRACEFUL_SKIP) which is a generic skip warning.
- extraction_intent: **field-presence only** (not semantic matching) — deterministic, zero false positives. Uses E591/W591.
- Content derivation: **token co-occurrence** (deterministic but approximate) — proven pattern from W140 (SEED_CONTENT_OVERLAP_LOW). Uses W594; E594 exists for optional promotion.
- Vague language: **W593** for free-text (separate from W571 for assumptions) — independent promotion control
- All new checks are **warnings by default** — user controls promotion via `SPECDEV_WARNINGS_AS_ERRORS`
- W→E promotion: **dynamic pairing** — any W-code with matching E-code suffix is auto-promotable
- `SPECDEV_PROMOTE_CODES`: per-code granularity for selective promotion
- Coverage thresholds: default `mode: "warn"` with configurable percentages
- `env-check` is **read-only** — it MUST NOT modify any state

---

## Measurable Goals

| Metric | Before R9 | After R9 |
|--------|-----------|----------|
| Validators with cross-step ID checks | 4/16 | **16/16** (all with upstream deps) |
| Promotable W-codes | 4 | **ALL** (dynamic pairing) |
| Free-text fields scanned for vague language | `assumptions` only | **all free-text fields** |
| Content derivation checks | 0 | **active on all linked steps** |
| `SPECDEV_WARNINGS_AS_ERRORS=1` coverage | partial | **100%** |
| `env-check` diagnostic command | absent | **present** |
| Instruction coverage map | absent | **documented for high-impact steps** |

---

## Anti-Patterns

- Do NOT hard-error when upstream file is missing — graceful skip with W590
- Do NOT use embeddings/NLP — simple tokenization is deterministic and reproducible
- Do NOT make content derivation a hard error — it's heuristic (W594 by default; E594 exists for promotion but should not be the default)
- Do NOT scan metadata fields ($schema, spec_version, generation_quality, seed_refs) for vague language
- `env-check` MUST NOT modify any state — read-only diagnostic only
- Do NOT break existing validation behavior — all new checks are additive warnings
- Do NOT duplicate cross-step logic already in step_04.py and step_07.py — reuse the `_load_*_ids()` pattern

---

## Dependencies

| Direction | Review | Relationship |
|-----------|--------|-------------|
| Requires | R7 | Validators reference R7-hardened prompt requirements |
| Requires | R8 | Validators enforce R8-tightened schema constraints |
| Requires | R1-R6 | All structural fixes must be in place |
| Completes | 4-Layer Closure | R9 is the final review in the determinism closure |

---

## 4-Layer Closure Verification (Final Gate)

After R9 completes, the entire 4-layer model must be verified:

```
1. L1 (Prompts):  Every prompt covers 100% of schema fields with sourcing ✓ (R7)
2. L2 (Schemas):  Every required[] matches prompts, zero rejection bugs ✓ (R8)
3. L3 (Validators): Cross-step IDs, content derivation, vague scanning ✓ (R9)
4. L4 (CI Gates): Dynamic W→E promotion, 100% coverage ✓ (R9)

Final command:
SPECDEV_WARNINGS_AS_ERRORS=1 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit

Expected: catches every semantic violation. An AI following any prompt perfectly
produces a spec artifact that passes all 4 layers with zero warnings.
```
</review_prompt>
