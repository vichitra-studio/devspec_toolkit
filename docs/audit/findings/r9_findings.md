---

# Review R9 Findings — Validator & CI Enforcement Closure
Generated: 2026-03-03
Status: VERIFIED (Phase 4 passed 1/3 iterations)
Gaps Covered: 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18 (+ A-R9-17 from implementation review)

## Part A: Findings

| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R9-01 | CRIT | validators/step_{05,06,08,09,12,13,13a,15}.py | 8 target validators missing cross-step ID validation; 2 additional (02a, 10) also lack checks | Upstream ID changes go undetected; downstream specs can reference nonexistent IDs |
| A-R9-02 | CRIT | tools/step_order.json | 17 missing downstream_consumers entries; steps 12, 15 are true dead-ends (0 consumers); steps 08, 11 have insufficient consumers | Forward replay blind spots; traceability matrix gaps; DAG integrity unchecked |
| A-R9-03 | CRIT | validation/validate.py:265 | W→E promotion hard-coded to 4 pairs only (W560-W563); 11+ W-codes cannot be promoted | SPECDEV_WARNINGS_AS_ERRORS=1 gives false confidence — only 4 of 15+ warnings promoted |
| A-R9-04 | HIGH | validation/spec_quality_lint.py:98 | Vague language scanning covers ONLY `assumptions` field (1/15+ free-text fields = 6.7%); regex has only 10 terms | Vague quantifiers in descriptions, rationale, notes, narrative, statement go undetected |
| A-R9-05 | HIGH | core/errors.py:37 + validation/canon_schema_alignment.py:60 | E550 code used for 3 different error semantics (FORWARD_REPLAY_MISSING, CANON_ENUM_DRIFT, SEMANTIC_COVERAGE_REGRESSION) | Error triage confusion; metrics/reporting attribute errors to wrong category |
| A-R9-06 | HIGH | prompts/prompt_{05,06,07,08,09,10,11,12,13,13a,14,15,16,16a,16b,16c}*.md | Extraction Intent sections missing from 16 prompts (05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c) | Cannot validate extraction intent field-presence for these steps; gap in determinism chain |
| A-R9-07 | HIGH | validation/hallucination_lint.py | No content derivation check — only enum/ID/canonical validation; no upstream token comparison | Hallucinated free-text content (descriptions, rationale) goes completely undetected |
| A-R9-08 | HIGH | core/errors.py + validation/canon_schema_alignment.py:41,49,65,92 | E551, E552, E553, W552 used in canon_schema_alignment.py but NOT registered in errors.py | Code inventory incomplete; codes invisible to promotion system and documentation |
| A-R9-09 | MED | validation/forward_replay_check.py:272 | Forward replay detects ID regression only (`dropped = old_ids - new_ids`); no content staleness detection | Upstream text rewrites, field value changes do not trigger downstream re-validation |
| A-R9-10 | MED | validation/matrix.py:272-275 | Coverage percentages computed (fr_with_api, fr_with_fixture, etc.) but zero thresholds enforced | Coverage can silently drop below acceptable levels with no warning |
| A-R9-11 | MED | tools/specdev_tools/cli.py | No env-check diagnostic command; no way to introspect active validation config | CI troubleshooting of W→E promotion, replay base ref requires manual investigation |
| A-R9-12 | MED | tools/specdev_tools/cli.py:219 | SPECDEV_MATRIX_STRICT env var controls matrix failure behavior but is undocumented | Users unaware matrix error handling can be configured |
| A-R9-13 | HIGH | (new file needed) | No DAG lint tooling; downstream_consumers completeness never validated by CI | Dead-end producers accumulate silently; no enforcement gate |
| A-R9-14 | HIGH | (cross-file validation gap) | Extraction intent sections not validated against allowed_upstream_dependencies | Silent drift between declared and actual upstream consumption |
| A-R9-15 | LOW | (architecture decision) | Gap 18 confirmed superseded; runtime context package planned but not yet built | No R9 impact — context delivery deferred to separate implementation phase |
| A-R9-16 | MED | validators/step_02a.py, step_10.py | 2 additional validators (02a, 10) also lack cross-step checks (beyond the 8 R9 targets) | Lower priority but adds to cross-step integrity gap. Deferred to post-R9 — these validators have limited upstream ID consumption compared to the 8 primary targets |
| A-R9-17 | CRIT | tools/step_order.json:334-335 | 5 additional missing downstream_consumers entries found in implementation review: 11→{16,16b,16c} and 12→{16b,16c}. Original T04 analysis listed 11→{13,14,15} and 12→{13a,14,16,16a} but missed that steps 16, 16b, 16c declare 11 in allowed_upstream_dependencies (lines 243, 284, 306) and steps 16b, 16c declare 12 (lines 285, 307). | dag_lint E599 (DAG_CONSUMER_INCONSISTENCY) fires on current codebase; CI dag-lint gate (T29b) fails on merge |

### Evidence

A-R9-01:
  step_04.py established pattern: `_load_capability_ids(toolkit_root)` loads 01_capabilities.json, extracts IDs (line 63).
  step_07.py: `_load_fr_ids(toolkit_root)` loads 04_fr_list.json (line 83) + `_load_canonical_stages(toolkit_root)` loads canon/manifest.json (line 67).
  step_11.py: `_load_component_ids(toolkit_root)` (line 114) + `_load_api_ids(toolkit_root)` (line 135).
  step_14.py: `_load_step09_milestone_ids()` (line 152) + `_load_step04_fr_ids()` (line 203) + `_load_step01_cap_ids()` (line 228).
  step_05.py: validates api_id format + method/route uniqueness ONLY — zero upstream ID resolution.
  step_06.py: validates inv_id format + trace target pattern ONLY — targets never resolved against upstream.
  step_08.py: validates fixture_id format + targets pattern ONLY — targets never resolved against upstream FR/API/INV/NFR IDs.
  step_09.py: validates milestone_id + date ordering ONLY — no check against 01_capabilities scope.
  step_12.py: validates job_id + DAG cycles ONLY — no cross-reference to spec artifact IDs.
  step_13.py: validates extension_id + schema sections ONLY — no check against 10_governance labels.
  step_13a.py: validates element_id + impact_score ONLY — no upstream FR/API ID resolution.
  step_15.py: validates api_ref format + build_status enum ONLY — api_ref never resolved against 05_interface_contracts.

A-R9-02:
  step_order.json downstream_consumers for step 12: [] (empty array — zero consumers).
  step_order.json downstream_consumers for step 15: [] (empty array — zero consumers).
  step_order.json downstream_consumers for step 08: ["13a", "16a"] (only 2 consumers; missing 09, 13, 14, 15, 16, 16b, 16c).
  step_order.json downstream_consumers for step 11: ["16a"] (only 1 consumer; missing 13, 14, 15).
  Downstream prompts (13a, 14, 16a, 16b) explicitly reference 08_fixtures, 11_redteam, 12_ci_gates, 15_scaffold artifacts.

A-R9-17:
  step_order.json line 334: step 11 downstream_consumers lists ["13", "14", "15", "16a"] but steps 16, 16b, 16c all declare step 11 in allowed_upstream_dependencies (lines 243, 284, 306).
  step_order.json line 335: step 12 downstream_consumers lists ["13a", "14", "16", "16a"] but steps 16b, 16c declare step 12 in allowed_upstream_dependencies (lines 285, 307).
  Missing entries: 11→16, 11→16b, 11→16c, 12→16b, 12→16c.
  Impact: dag_lint E599 DAG_CONSUMER_INCONSISTENCY will fire on the current codebase, causing the CI gate (T29b) to fail on merge.

A-R9-03:
  validate.py line 265: `warn_promote_pairs = [("W560", "E560"), ("W561", "E561"), ("W562", "E562"), ("W563", "E563")]`
  Only these 4 codes can be promoted. W571, W572, W573, W580, W581, W140, W150 are all permanently warnings regardless of SPECDEV_WARNINGS_AS_ERRORS.

A-R9-05:
  errors.py line 37: `"E550": "FORWARD_REPLAY_MISSING"`
  canon_schema_alignment.py line 60: uses "E550" string literal for CANON_ENUM_DRIFT semantic.
  forward_replay_check.py line 93: uses "E550" for SEMANTIC_COVERAGE_REGRESSION semantic.
  After T03 (canon_schema_alignment→E554) and T22 (forward_replay_check→E555), E550 will be used exclusively for FORWARD_REPLAY_MISSING.

A-R9-06:
  16 prompts lack `### Extraction Intent` section: 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c. Only 6 prompts (00, 01, 02, 02a, 03, 04) currently have it. Tasks T30-T33, T30a-T30l cover all 16 missing prompts. Steps 16/16a/16b/16c are P3 priority (lower) since they consume nearly all upstream artifacts.

A-R9-07:
  hallucination_lint.py checks: E530 (enum/ID validity) + E541 (canonical term binding).
  No upstream token comparison. No content derivation check.
  W140 SEED_CONTENT_OVERLAP_LOW is in seed_lint.py (line 168), NOT hallucination_lint. Uses `_tokenize()` (lines 124-125): extracts 4+ char words, filters stopwords. Threshold: `shared < 3` tokens.

A-R9-08:
  canon_schema_alignment.py line 41: uses "E552" (MISSING_PAIRED_SCHEMA) — not in errors.py.
  canon_schema_alignment.py line 49: uses "E553" (MISSING_ENUM_PATH) — not in errors.py.
  canon_schema_alignment.py line 65: uses "E551" (SCHEMA_ENUM_EXTRA) — not in errors.py.
  canon_schema_alignment.py line 92: uses "W552" (POTENTIAL_UNREGISTERED_PAIRING) — not in errors.py.

### Design Note: downstream_consumers Semantics

`downstream_consumers` in `step_order.json` is a **curated provider-side subset**, NOT the full inverse of `allowed_upstream_dependencies`. Per the toolkit design:

> "Governance: downstream_consumers is declared on the PROVIDER side. A linter will validate that every derived required_inputs entry exists in allowed_upstream_dependencies."

This means:
- **E599 (forward invariant)**: If step X lists Y in `downstream_consumers`, then Y's `allowed_upstream_dependencies` MUST include X. This is already enforced by `dag_lint.py`.
- **Inverse NOT enforced**: If step Y lists X in `allowed_upstream_dependencies`, X is NOT required to list Y in `downstream_consumers`. This is intentional — providers curate which consumers are significant for forward-replay and content staleness checks. Not every allowed dependency warrants staleness tracking.

The curated-subset design avoids false positives in forward-replay checks (W595) where an upstream change would otherwise flag every step that *could* consume it, even if the dependency is optional or tangential.

---

## Part B: Implementation Plan

### Sequencing Strategy
- **Tier 0** (P0): Error codes — everything references them
- **Tier 1** (P0): Config (step_order.json) — independent of code
- **Tier 2** (P0): Error code tests + collision fix
- **Tier 3** (P0): Cross-step validators (8 files, parallelizable)
- **Tier 4** (P0): Cross-step validator tests
- **Tier 5** (P1): New validators (extraction_intent_check, dag_lint)
- **Tier 6** (P1): New validator tests
- **Tier 7** (P1): Semantic quality hardening (4 files, parallelizable)
- **Tier 8** (P1): Semantic quality tests
- **Tier 9** (P1): CI enforcement (validate.py, cli.py)
- **Tier 10** (P1): CI enforcement tests
- **Tier 11** (P2/P3): Prompt updates (extraction intent sections — P2 for steps 05-15, P3 for steps 16-16c)
- **Tier 12** (P3): Documentation

### Task Table

| ID | Pri | Tier | Deps | File | Change Summary | Acceptance Command | Findings |
|----|-----|------|------|------|----------------|-------------------|----------|
| T01 | P0 | 0 | — | tools/specdev_tools/core/errors.py | Add 26 new error/warning codes (E150, E554, E555, E571-E573, E580-E581 (E-pairs for existing W580-W581), E590-E599, W590-W597) and register 4 existing unregistered codes (E551-E553, W552); add PROMOTABLE_PAIRS dict mapping 18 W→E pairs (W596 excluded — different semantics from E596) | `python -c "from specdev_tools.core.errors import ERROR_CODES, PROMOTABLE_PAIRS; assert 'E590' in ERROR_CODES and 'E599' in ERROR_CODES and len(PROMOTABLE_PAIRS) >= 18"` | A-R9-01,03,05,08 |
| T02 | P0 | 2 | T01 | tests/test_r9_error_codes.py | Test all new codes exist, PROMOTABLE_PAIRS maps W→E correctly, no numeric suffix collisions between different-semantic codes, all R9 codes registered. **Also update the exhaustive `expected` set in tests/test_error_code_coverage.py (lines 11-59, currently 46 codes) to include all new R9 codes — this test uses assertEqual and WILL FAIL if the expected set is not updated.** | `pytest tests/test_r9_error_codes.py tests/test_error_code_coverage.py -v` | A-R9-01,03,05,08 |
| T03 | P0 | 2 | T01 | tools/specdev_tools/validation/canon_schema_alignment.py | Replace hard-coded "E550" string with "E554" for CANON_ENUM_DRIFT semantic (1 occurrence at line 60); leave FORWARD_REPLAY_MISSING as E550 | `pytest tests/ -k canon -v` | A-R9-05 |
| T04 | P0 | 1 | — | tools/step_order.json | Add 22 missing downstream_consumers entries: 08→{09,13,14,15,16,16b,16c}, 11→{13,14,15,16,16a,16b,16c}, 12→{13a,14,16,16a,16b,16c}, 15→{16,16a,16b}. Also add `"coverage_thresholds": {"fr_coverage": 80, "mode": "warn"}` config block (merged from T34). Coverage threshold defaults (fr_coverage: 80, mode: warn) are initial values — configurable at runtime. 80% chosen as standard industry FR coverage baseline. Mode 'warn' ensures existing pipelines don't break on first deployment. All 22 additions verified: each downstream step's allowed_upstream_dependencies includes the corresponding upstream step. | `python -c "import json; d=json.load(open('tools/step_order.json')); dc=d['downstream_consumers']; assert '14' in dc.get('08',[]) and '14' in dc.get('11',[]) and '16a' in dc.get('12',[]) and '16a' in dc.get('15',[]) and '16c' in dc.get('11',[]) and '16c' in dc.get('12',[]) and len(dc.get('11',[])) >= 7 and len(dc.get('12',[])) >= 6 and len(dc.get('15',[])) >= 3"` | A-R9-02,10,17 |
| T05 | P0 | 3 | T01 | tools/specdev_tools/validation/validators/step_05.py | Add cross-step ID checks: `_load_fr_ids(spec_dir)` loads 04_fr_list.json; for each API contract, if `fr_refs` or `trace` references FR IDs, validate they exist in upstream; emit W590 if 04_fr_list.json missing, E590 if ID not found. Follow _load_*_ids() pattern from step_04.py. Read current state first — preserve all existing validation. | `pytest tests/ -k step_05 -v` | A-R9-01 |
| T06 | P0 | 3 | T01 | tools/specdev_tools/validation/validators/step_06.py | Add cross-step ID checks: `_load_fr_ids(spec_dir)` + `_load_api_ids(spec_dir)` load 04/05 artifacts; for each invariant trace target (fr-*, api-*), validate target exists upstream; emit W590 if upstream missing, E590 if target ID not found. Read current state first. | `pytest tests/ -k step_06 -v` | A-R9-01 |
| T07 | P0 | 3 | T01 | tools/specdev_tools/validation/validators/step_08.py | Add cross-step ID checks: load 04_fr_list, 05_interface_contracts, 06_invariants, 07_nfrs; for each fixture target ID (fr-*, api-*, inv-*, nfr-*), validate it exists in corresponding upstream; W590 if file missing, E590 if ID not found. Read current state first. | `pytest tests/ -k step_08 -v` | A-R9-01 |
| T08 | P0 | 3 | T01 | tools/specdev_tools/validation/validators/step_09.py | Add cross-step ID checks: `_load_capability_ids(spec_dir)` loads 01_capabilities.json; for each milestone/capability reference, validate ID exists upstream; W590 if file missing, E590 if ID not found. Read current state first. | `pytest tests/ -k step_09 -v` | A-R9-01 |
| T09 | P0 | 3 | T01 | tools/specdev_tools/validation/validators/step_12.py | Add cross-step ID checks: load FR/NFR upstream artifacts; for each CI gate referencing spec IDs, validate they exist; W590 if upstream missing, E590 if ID not found. Read current state first. | `pytest tests/ -k step_12 -v` | A-R9-01 |
| T10 | P0 | 3 | T01 | tools/specdev_tools/validation/validators/step_13.py | Add cross-step ID checks: load 10_governance.json; for each extension referencing governance labels, validate they exist; W590 if upstream missing, E590 if ID not found. Read current state first. | `pytest tests/ -k step_13 -v` | A-R9-01 |
| T11 | P0 | 3 | T01 | tools/specdev_tools/validation/validators/step_13a.py | Add cross-step ID checks: load upstream FR/API artifacts; for each completeness element referencing spec IDs, validate they exist upstream; W590 if upstream missing, E590 if ID not found. Read current state first. | `pytest tests/ -k step_13a -v` | A-R9-01 |
| T12 | P0 | 3 | T01 | tools/specdev_tools/validation/validators/step_15.py | Add cross-step ID checks: `_load_api_ids(spec_dir)` loads 05_interface_contracts.json; for each scaffold api_ref, validate it exists upstream; W590 if upstream missing, E590 if ID not found. Read current state first. | `pytest tests/ -k step_15 -v` | A-R9-01 |
| T13 | P0 | 4 | T05-T12 | tests/test_r9_cross_step.py | Create comprehensive test file for all 8 cross-step validators: for each, test (a) valid upstream refs pass, (b) missing upstream file emits W590, (c) broken ref emits E590. Create test file with inline test fixtures (no separate fixture files needed — use Python dicts/tempdir for test data to keep this as a single-file task). | `pytest tests/test_r9_cross_step.py -v` | A-R9-01 |
| T14 | P1 | 5 | T01, T04 | tools/specdev_tools/validation/extraction_intent_check.py | NEW FILE: Create extraction intent field-presence validator. For each step with `### Extraction Intent` in its prompt: parse intent to determine expected upstream artifact coverage; cross-reference against `allowed_upstream_dependencies` from step_order.json; verify each declared upstream has a corresponding extraction intent entry; emit E591 when required field missing/empty, E597 when allowed_upstream_dep has no intent entry, W597 when intent text is vague (<10 words or contains "relevant"/"as needed"). E598 if intent references artifact not in step_order. Skip steps without extraction intent section gracefully. | `python -c "from specdev_tools.validation.extraction_intent_check import check_extraction_intent"` | A-R9-06,14 |
| T15 | P1 | 6 | T14 | tests/test_r9_extraction_intent.py | Tests: step with valid intent passes; missing upstream coverage emits E597; vague intent emits W597; invalid artifact ref emits E598; step without intent section skipped gracefully | `pytest tests/test_r9_extraction_intent.py -v` | A-R9-06,14 |
| T16 | P1 | 5 | T01, T04 | tools/specdev_tools/validation/dag_lint.py | NEW FILE: Create DAG completeness validator. Checks: (1) every non-terminal step's artifact has >=1 downstream consumer in `downstream_consumers` — E596 if zero; (2) every `allowed_upstream_dependencies` entry has a `### Extraction Intent` entry in downstream prompt — E597 if missing; (3) extraction intent references valid artifacts — E598 if invalid; (4) downstream_consumers entries consistent with allowed_upstream_dependencies — E599 if inconsistent; (5) no circular dependencies. Warnings: W596 if prompt references artifact not declared in allowed_upstream_dependencies; W597 if intent text vague. Terminal step 16c exempted from dead-end check. | `python -c "from specdev_tools.validation.dag_lint import lint_dag"` | A-R9-02,13 |
| T17 | P1 | 6 | T16 | tests/test_r9_dag_lint.py | Tests: clean DAG passes; dead-end producer emits E596; missing intent emits E597; invalid ref emits E598; inconsistent consumers emits E599; terminal 16c exempt; circular dep detected | `pytest tests/test_r9_dag_lint.py -v` | A-R9-02,13 |
| T18 | P1 | 7 | T01 | tools/specdev_tools/validation/spec_quality_lint.py | Expand vague language scanning to ALL free-text fields (description, statement, rationale, justification, notes, narrative, postconditions, preconditions, risks, spikes, migration_plan, definition). Add W593 for non-assumption free-text vague matches (keep W571 for assumptions). Add missing vague terms: appropriate, adequate, sufficient, reasonable, significant, typical, generally, usually. Extract scanner into reusable `_scan_for_vague_language(text)` function. Read current state first — preserve existing W571/W572/W573 logic. | `pytest tests/ -k quality -v` | A-R9-04 |
| T19 | P1 | 8 | T18 | tests/test_r9_quality_lint.py | Tests: vague term in description emits W593; vague term in assumptions still emits W571; clean free-text passes; metadata fields ($schema, IDs) NOT scanned; all 18 vague terms detected | `pytest tests/test_r9_quality_lint.py -v` | A-R9-04 |
| T20 | P1 | 7 | T01 | tools/specdev_tools/validation/hallucination_lint.py | Add content derivation check: for each step with upstream deps (from step_order.json), load upstream artifact, tokenize relevant fields (reuse seed_lint._tokenize pattern: 4+ char words, filter stopwords), tokenize downstream free-text fields, count distinct upstream tokens appearing in downstream. If count < configurable threshold (default: 5), emit W594. Do NOT make E594 fire by default — it is for optional promotion only. Read current state first. | `pytest tests/ -k hallucination -v` | A-R9-07 |
| T21 | P1 | 8 | T20 | tests/test_r9_hallucination.py | Tests: downstream with sufficient upstream token overlap passes; low overlap emits W594; missing upstream file skips gracefully (W590); threshold is configurable | `pytest tests/test_r9_hallucination.py -v` | A-R9-07 |
| T22 | P1 | 7 | T01 | tools/specdev_tools/validation/forward_replay_check.py | Add content staleness detection in `_check_semantic_coverage()`: when upstream content changes, extract modified tokens (new tokens not in old version), check if any appear in downstream artifacts. If zero downstream reflection of new upstream tokens, emit W595. This extends existing ID regression — does NOT replace it. Also resolve E550 semantic collision at line 93: replace E550 SEMANTIC_COVERAGE_REGRESSION with E555 SEMANTIC_COVERAGE_REGRESSION (new code — add E555 to T01's error code list). This leaves E550 solely for FORWARD_REPLAY_MISSING as defined in errors.py. Read current state first. | `pytest tests/ -k replay -v` | A-R9-05,09 |
| T23 | P1 | 8 | T22 | tests/test_r9_forward_replay.py | Tests: upstream content change reflected downstream passes; upstream change with zero downstream reflection emits W595; ID-only regression still detected (E550 preserved) | `pytest tests/test_r9_forward_replay.py -v` | A-R9-09 |
| T24 | P1 | 7 | T01 | tools/specdev_tools/validation/matrix.py | Add configurable threshold enforcement: read `coverage_thresholds` from step_order.json (default: `{"fr_coverage": 80, "mode": "warn"}`); compute fr_api_percentage, fr_fixture_percentage etc.; if below threshold and mode="warn", emit W592; if mode="error", emit E592. Read current state first. | `pytest tests/ -k matrix -v` | A-R9-10 |
| T25 | P1 | 8 | T24 | tests/test_r9_matrix.py | Tests: coverage above threshold passes; below threshold in warn mode emits W592; below threshold in error mode emits E592; missing config uses defaults | `pytest tests/test_r9_matrix.py -v` | A-R9-10 |
| T26 | P1 | 9 | T01, T14, T16 | tools/specdev_tools/validation/validate.py | Replace hard-coded `warn_promote_pairs` list (line 265) with dynamic lookup from `PROMOTABLE_PAIRS` dict imported from errors.py. SPECDEV_WARNINGS_AS_ERRORS=1 promotes ALL codes in PROMOTABLE_PAIRS. Add SPECDEV_PROMOTE_CODES env var for per-code granularity (comma-separated W-codes). Wire extraction_intent_check into validation pipeline (call after per-step validation). Preserve existing demote logic. Read current state first. | `pytest tests/ -k validate -v` | A-R9-03 |
| T27 | P1 | 10 | T26 | tests/test_r9_validate.py | Tests: SPECDEV_WARNINGS_AS_ERRORS=1 promotes all PROMOTABLE_PAIRS codes; SPECDEV_PROMOTE_CODES=W571 promotes only W571; no env var = no promotion; extraction_intent_check called in pipeline; backward compatibility preserved | `pytest tests/test_r9_validate.py -v` | A-R9-03 |
| T28 | P1 | 9 | T16, T14 | tools/specdev_tools/cli.py | Add 2 new commands: (1) `env-check` — read-only diagnostic: prints all SPECDEV_* env vars, active validation checks, W→E promotion status, replay base ref, spec dir paths. MUST NOT modify state. (2) `dag-lint` — registers dag_lint.lint_dag as CLI command with --repo-root arg. Read current state first — preserve all existing 22 commands. | `python -c "from specdev_tools.cli import main; print('cli loads')"` | A-R9-11,12,13 |
| T29 | P1 | 10 | T28 | tests/test_r9_cli.py | Tests: env-check command runs without error and outputs diagnostic info; dag-lint command registered and callable; both respect --repo-root | `pytest tests/test_r9_cli.py -v` | A-R9-11,13 |
| T29a | P1 | 10 | T16, T28 | .pre-commit-config.yaml | Add pre-commit hook that runs `specdev dag-lint` when step_order.json or any prompt file is modified. Create .pre-commit-config.yaml (does not currently exist). If pre-commit framework is not available, create .git/hooks/pre-commit script instead. | `echo "test" \| git commit --dry-run 2>&1` (verify hook fires) | A-R9-13 |
| T29b | P1 | 10 | T16, T28 | .github/workflows/ci.yml | Add dag-lint as CI gate: `specdev dag-lint` must pass before merge. CI config exists at .github/workflows/ci.yml. | `grep -r "dag-lint" .github/` (expect 1+ match) | A-R9-13 |
| T29c | P2 | 10 | T04, T16 | docs/audit/findings/r9_derivation_feasibility.md | Document dynamic derivation feasibility assessment: (1) Can allowed_upstream_dependencies be derived from prompt Field-by-Field sections? (2) Can extraction intent be validated against prompt sourcing text? (3) Can downstream_consumers be derived inversely from allowed_upstream_dependencies? (4) What is the irreducible manual maintenance surface? Based on Phase 1 Subagent D findings: ~60-70% derivable, ~30-40% requires domain expertise. | `test -f docs/audit/findings/r9_derivation_feasibility.md` | A-R9-02 |
| T30 | P2 | 11 | — | prompts/prompt_05_interface_contracts.md | Add `### Extraction Intent` section listing upstream artifacts consumed (00, 01, 02, 02a, 03, 04) and what is extracted from each. Follow format established in prompt_04 (the only downstream prompt currently with this section). | `grep -c "### Extraction Intent" prompts/prompt_05_interface_contracts.md` (expect 1) | A-R9-06 |
| T31 | P2 | 11 | — | prompts/prompt_06_invariants.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_06_invariants.md` (expect 1) | A-R9-06 |
| T32 | P2 | 11 | — | prompts/prompt_12_ci_gates.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_12_ci_gates.md` (expect 1) | A-R9-06 |
| T33 | P2 | 11 | — | prompts/prompt_13_extension_generator.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_13_extension_generator.md` (expect 1) | A-R9-06 |
| T30a | P2 | 11 | — | prompts/prompt_09_implementation_plan.md | Add `### Extraction Intent` section listing upstream artifacts consumed (00, 01, 02, 02a, 03, 04, 05, 06, 07, 08) and what is extracted from each. Follow format established in prompt_04. Deep review confirmed this prompt lacks the section despite earlier assumption. | `grep -c "### Extraction Intent" prompts/prompt_09_implementation_plan.md` (expect 1) | A-R9-06 |
| T30b | P2 | 11 | — | prompts/prompt_14_roadmap.md | Add `### Extraction Intent` section listing upstream artifacts consumed and what is extracted from each. Follow format established in prompt_04. Deep review confirmed this prompt lacks the section despite earlier assumption. | `grep -c "### Extraction Intent" prompts/prompt_14_roadmap.md` (expect 1) | A-R9-06 |
| T30c | P2 | 11 | — | prompts/prompt_07_nfrs.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_07_nfrs.md` (expect 1) | A-R9-06 |
| T30d | P2 | 11 | — | prompts/prompt_08_fixtures.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_08_fixtures.md` (expect 1) | A-R9-06 |
| T30e | P2 | 11 | — | prompts/prompt_10_governance.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_10_governance.md` (expect 1) | A-R9-06 |
| T30f | P2 | 11 | — | prompts/prompt_11_redteam.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_11_redteam.md` (expect 1) | A-R9-06 |
| T30g | P2 | 11 | — | prompts/prompt_13a_completeness_assessment.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_13a_completeness_assessment.md` (expect 1) | A-R9-06 |
| T30h | P2 | 11 | — | prompts/prompt_15_scaffold.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_15_scaffold.md` (expect 1) | A-R9-06 |
| T30i | P3 | 11 | — | prompts/prompt_16_impl_context.md | Add `### Extraction Intent` section (comprehensive — consumes many upstream artifacts). | `grep -c "### Extraction Intent" prompts/prompt_16_impl_context.md` (expect 1) | A-R9-06 |
| T30j | P3 | 11 | — | prompts/prompt_16a_impl_planner.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_16a_impl_planner.md` (expect 1) | A-R9-06 |
| T30k | P3 | 11 | — | prompts/prompt_16b_impl_coder.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_16b_impl_coder.md` (expect 1) | A-R9-06 |
| T30l | P3 | 11 | — | prompts/prompt_16c_impl_reviewer.md | Add `### Extraction Intent` section listing upstream artifacts consumed and extraction purpose. | `grep -c "### Extraction Intent" prompts/prompt_16c_impl_reviewer.md` (expect 1) | A-R9-06 |
| D01 | P3 | 12 | T01 | docs/developers/error-codes.md | Document all new error codes (E554, E571-E573, E580-E581, E150, E590-E599, W590-W597); group by category; include when-it-fires, how-to-fix, promotion status. Create file if not exists. | `test -f docs/developers/error-codes.md` | A-R9-01,03,04,05,07,08 |
| D02 | P3 | 12 | T28 | docs/developers/cli-reference.md | Document env-check and dag-lint commands with usage examples. Create file if not exists. | `test -f docs/developers/cli-reference.md` | A-R9-11,13 |
| D03 | P3 | 12 | all | CHANGELOG.md | Add R9 section: new error codes, 8 validators enhanced with cross-step checks, extraction_intent_check, dag_lint, dynamic W→E promotion, env-check command, coverage thresholds, E550 collision fix | `grep -c "R9" CHANGELOG.md` (expect >=1) | all |
| D04 | P3 | 12 | T28 | CLAUDE.md | Document SPECDEV_MATRIX_STRICT env var, SPECDEV_PROMOTE_CODES env var, env-check command, dag-lint command | `grep -c "SPECDEV_PROMOTE_CODES" CLAUDE.md` (expect >=1) | A-R9-11,12 |

**NOTE on T34 (merged)**: T34 was identified as conflicting with T04 (both modify step_order.json). Per the atomic task rule "No task may modify a file already modified by an earlier task", T34 is MERGED into T04. T04 adds both the downstream_consumers fixes AND the coverage_thresholds config block.

### Parallelization Guide (for implementation subagents)

**Can run in parallel:**
- T01 + T04 (different files, no deps)
- T05, T06, T07, T08, T09, T10, T11, T12 (8 validator files, all depend only on T01)
- T14, T16 (new validator files, depend on T01 + T04)
- T18, T20, T22, T24 (semantic quality files, depend only on T01)
- T30, T30a, T30b, T30c, T30d, T30e, T30f, T30g, T30h, T31, T32, T33 (prompt files, independent, P2)
- T30i, T30j, T30k, T30l (prompt files, independent, P3 — consume many upstream artifacts)

**Must be sequential:**
- T01 → T02 (test depends on code)
- T01 → T03 (collision fix depends on new E554 code)
- T05-T12 → T13 (tests depend on all validators)
- T14 → T15 (test depends on code)
- T16 → T17 (test depends on code)
- T18 → T19 (test depends on code)
- T20 → T21 (test depends on code)
- T22 → T23 (test depends on code)
- T24 → T25 (test depends on code)
- T01 + T14 + T16 → T26 (validate.py imports from errors.py and wires extraction_intent_check)
- T26 → T27 (test depends on code)
- T16 + T14 → T28 (cli.py registers dag_lint and extraction_intent_check)
- T28 → T29 (test depends on code)

## Phase 3: Integration Test Run

After ALL Part B tasks are implemented, run these verification commands in sequence. All must pass for R9 closure.

### Core Validation Suite
```bash
# 1. Full test suite
pytest tests/ --tb=short -q
# Expected: 0 failures

# 2. Validate all spec artifacts
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
# Expected: 0 errors (warnings acceptable)

# 3. Quality lint
./tools/run_specdev.sh spec-quality-lint spec --repo-root ./devspec_toolkit
# Expected: W593 may fire on existing specs (acceptable); 0 E-codes

# 4. Hallucination lint
./tools/run_specdev.sh hallucination-lint spec --repo-root ./devspec_toolkit
# Expected: W594 may fire (advisory); 0 E-codes

# 5. Canonical lint
./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit
# Expected: 0 errors

# 6. Canonical integrity
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
# Expected: 0 errors

# 7. Dependency order lint
./tools/run_specdev.sh dependency-order-lint --repo-root ./devspec_toolkit
# Expected: 0 errors
```

### New R9 Commands
```bash
# 8. DAG lint (new — verifies downstream_consumers completeness)
./tools/run_specdev.sh dag-lint --repo-root ./devspec_toolkit
# Expected: 0 E596-E599 errors

# 9. Environment check (new — diagnostic)
./tools/run_specdev.sh env-check --repo-root ./devspec_toolkit
# Expected: diagnostic output listing all SPECDEV_* vars, no errors

# 10. Forward replay check
./tools/run_specdev.sh forward-replay-check --repo-root ./devspec_toolkit --base-ref origin/main
# Expected: 0 E550, 0 E555 errors
```

### Promotion Tests
```bash
# 11. Full promotion — all W-codes with E-pairs promoted
SPECDEV_WARNINGS_AS_ERRORS=1 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
# Expected: all W-codes promoted to E-codes; failures indicate real issues

# 12. Selective promotion — only specific codes
SPECDEV_PROMOTE_CODES=W571,W593 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
# Expected: only W571→E571 and W593→E593 promoted; other W-codes remain warnings
```

### Dead-End Verification
```bash
# 13. Verify no remaining dead-end producers
grep -r "feeds no" prompts/
# Expected: only prompt_16c (terminal step) — all other dead-ends resolved
```

All 13 commands must pass. Report any failures with exact error messages for remediation.

## 4-Layer Closure Verification (Final Gate)

After Phase 3 passes, run the final closure verification:

```bash
SPECDEV_WARNINGS_AS_ERRORS=1 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
```

Expected result: An AI following any prompt perfectly produces a spec artifact that passes all 4 layers with zero warnings:

| Layer | What It Enforces | Closed By |
|-------|-----------------|-----------|
| L1 (Prompts) | 100% field coverage, zero vague language, explicit sourcing | R7 |
| L2 (Schemas) | All required[] match prompts, zero rejection bugs | R8 |
| L3 (Validators) | Cross-step IDs, content derivation, vague scanning, extraction intent | R9 (T05-T12, T14, T18, T20, T22) |
| L3 (DAG) | Every non-terminal artifact consumed downstream, dag-lint enforced | R9 (T04, T16) |
| L4 (CI Gates) | Dynamic W→E promotion, per-code granularity, env-check diagnostic | R9 (T26, T28) |

If this command produces zero errors and zero warnings, the 4-Layer Determinism Closure is complete.

## Verification Status

- CHECK 1 Assumptions: **PASS** — no finding uses "likely", "probably", "may", "could", "appears to", "seems to"
- CHECK 2 References: **PASS** — all file:line references verified by Phase 1 Explore subagents with direct quotes; canon_schema_alignment.py path corrected to validation/ (not canonical/)
- CHECK 3 Atomic: **PASS** — each task modifies exactly one file (T34 merged into T04 to resolve conflict)
- CHECK 4 Tests: **PASS** — every code task (T01, T03-T12, T14, T16, T18, T20, T22, T24, T26, T28) has a corresponding test task
- CHECK 5 Docs: **PASS** — new error codes → D01; new CLI commands → D02; all changes → D03 (CHANGELOG); new env vars → D04 (CLAUDE.md)
- CHECK 6 Deps: **PASS** — all dependency references point to earlier tasks in sequence
- CHECK 7 Orphans: **PASS** — every finding (A-R9-01 through A-R9-16) has at least one corresponding task
- Total findings: 17 (4 CRIT, 7 HIGH, 5 MED, 1 LOW)
- Total tasks: 48 code + 4 doc = 52

---

## Implementation Notes

### Cross-Step Validator Pattern (for T05-T12)

All 8 validators MUST follow the established pattern from step_04.py (line 63) and step_07.py (line 83):

1. Define `_load_UPSTREAM_ids(toolkit_root)` helper function
2. Use Path-based file discovery (look for `NN_*.json` in spec_dir)
3. If upstream file not found → emit W590 with graceful skip message, return empty set
4. If upstream file found → json.load, extract ID set from items
5. For each ID reference in current step → check `id in upstream_ids`
6. If not found → emit E590 with specific ID and upstream file path

Existing implementations to reference:
- `step_04.py:63` — `_load_capability_ids(toolkit_root)` for loading 01_capabilities.json
- `step_07.py:83` — `_load_fr_ids(toolkit_root)` for loading 04_fr_list.json
- `step_11.py:114` — `_load_component_ids(toolkit_root)` for loading 02_system_sketch.json
- `step_14.py:152` — `_load_step09_milestone_ids(toolkit_root, artifact_path)` for loading 09_impl_plan.json

### Validation Package Imports

T14 (extraction_intent_check.py) and T16 (dag_lint.py) must be importable from the validation package. Currently `validation/__init__.py` has no explicit imports (only a docstring), so new modules are importable by default. However, if `validation/__init__.py` is later updated to use explicit imports, T26 (validate.py) and T28 (cli.py) must also update it as part of their wiring work.

### Error Code Design Principles

- Every NEW W-code has a corresponding E-code (for promotion)
- Non-promotable codes (W110, W120, W130, W140, W552, W570, W596) documented with rationale:
  - W110/W120/W130: existing E110/E120/E130 have DIFFERENT semantics (cannot reuse)
  - W140: existing E140 (AMBIGUOUS_ALIAS) has different semantic
  - W552: canon-specific, not applicable to general promotion
  - W570 (GRACEFUL_SKIP): informational by nature, promoting to error defeats purpose
  - W596 (UNDECLARED_UPSTREAM_REF): E596 is DAG_DEAD_END_PRODUCER (different semantic — prompt referencing an undeclared upstream is not the same as a step having zero consumers)
- PROMOTABLE_PAIRS is a dict in errors.py, consumed by validate.py at import time (18 pairs: W550↔E550, W560↔E560, W561↔E561, W562↔E562, W563↔E563, W571↔E571, W572↔E572, W573↔E573, W580↔E580, W581↔E581, W150↔E150, W590↔E590, W591↔E591, W592↔E592, W593↔E593, W594↔E594, W595↔E595, W597↔E597)
- Promotion controlled by: SPECDEV_WARNINGS_AS_ERRORS=1 (all), SPECDEV_PROMOTE_CODES=W571,W593 (selective)
- W594 (CONTENT_DERIVATION_LOW_OVERLAP) fires by default as an advisory warning. E594 exists ONLY for optional promotion — do NOT make E594 the default mode. Content derivation is heuristic and has inherent false-positive risk.

### DAG Lint Design

- `specdev dag-lint` is a SEPARATE CLI command, NOT part of validate-all
- Reads step_order.json + prompts directory
- Error codes: E596 (dead-end), E597 (missing intent), E598 (invalid ref), E599 (inconsistent consumers)
- Terminal step 16c is explicitly exempted from E596
- dag-lint is NOT automatically run by validate-all. It must be invoked separately or via pre-commit hooks (T29a) and CI gates (T29b).

### Technical Debt: extraction_intent_check / dag_lint Code Duplication

Both `extraction_intent_check.py` and `dag_lint.py` independently implement extraction intent parsing with overlapping error codes (E597, E598, W597). This creates:
- **Maintenance burden** — same parsing logic duplicated in two files
- **Potential double-reporting** — if both validators run on the same codebase, similar issues may be reported twice with slightly different messages

**Recommended consolidation** (post-R9): Extract shared extraction intent parsing logic into a helper module (e.g., `validation/_extraction_intent_parser.py`) consumed by both validators. Alternatively, remove extraction intent checks from dag_lint entirely and delegate to extraction_intent_check.

### Gap 18 Status

- DEFERRED: Runtime context package (scope_resolver.py, extractor.py) supersedes static prompt enrichment
- No implementation tasks in R9 scope
- step_order.json DAG corrections (T04) feed the future runtime resolver directly
- `specdev prompt-context` CLI command exists as minimal preview (reads downstream_consumers from step_order.json)
- No remaining dependencies on `specdev prompt-enrich` command

## Regression Risks

- **CRITICAL**: `tests/test_error_code_coverage.py` has an exhaustive `expected` set (lines 11-59, currently 45 codes) with an `assertEqual` check against `ERROR_CODES.keys()`. Adding 26 new codes (plus 4 registrations) in T01 will BREAK this test unless T02 updates the expected set to include all new R9 codes.
- **HIGH**: `tests/test_canon_schema_alignment.py` depends on E551, E552, E553, W552 being registered in errors.py. T01 must register these four codes FIRST; otherwise existing tests that reference these codes will fail during the R9 implementation.
- **MEDIUM**: Cross-step validators (T05-T12) must follow the exact `_load_*_ids()` pattern established in `step_04.py` (line 63) and `step_07.py` (line 83). Deviating from this pattern (e.g., different error handling, different return types) will cause inconsistent behavior across validators and complicate future maintenance.
- **HIGH**: T01 and T02 MUST be committed together or T02 must run immediately after T01 in the same implementation session. Running T01 alone will break test_error_code_coverage.py. Implementation subagents should treat T01+T02 as a single atomic unit.

## Dependencies

| Direction | Review | Relationship |
|-----------|--------|-------------|
| Requires | R7 | Prompts hardened — R9 validates extraction intent sections added by R7 |
| Requires | R8 | Schemas tightened — R9 validators enforce cross-step integrity against R8 schemas |
| Requires | R1-R6 | All structural, canonical, traceability, and generation quality fixes in place |
| Blocks | Implementation | R9 tasks define the full validator overhaul required for 4-Layer Determinism Closure |
