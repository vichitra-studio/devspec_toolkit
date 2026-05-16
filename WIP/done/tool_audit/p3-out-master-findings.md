> **ARCHIVE NOTE (2026-05-16):** Canonical trace_matrix path is now `spec/extras/trace_matrix.json`. The `tools/trace_matrix.json` references below reflect the state at the time of writing.

# P3: Master Findings

## Summary
- Total findings: 70
- By severity: CRITICAL: 1, HIGH: 13, MEDIUM: 30, LOW: 16, INFO: 10
- From P1/P2: 68 unique after deduplication (from 76 A + 73 B raw findings)
- From WIP cross-check: 42 confirmed, 3 contradicted, 2 stale, 6 missed_by_audit (added as AUDIT-064 through AUDIT-069)
- False positives dropped: 5

---

## Findings by Severity

### CRITICAL

#### AUDIT-001: Unregistered Error Codes E141, E142, E320
- **Source:** A:G1, A:H12, A:H13, A:H14, A:E8, B:G3; C:corroborated (severity resolved to CRITICAL)
- **Category:** REGISTRY_INCONSISTENCY
- **Location:** validators/step_14.py:79 (E142), step_14.py:126 (E141), step_13.py:32,40,51 (E320)
- **Description:** Three error codes are emitted by validators but not registered in errors.py ERROR_CODES dict. make_error() would reject these if used. E320 was missed entirely by Container B. These codes bypass the centralized error system, cannot be promoted via W->E, and are invisible to error code coverage tests.
- **Recommendation:** Register E141, E142, E320 in errors.py ERROR_CODES dict. 5-minute fix.
- **WIP Status:** CONFIRMED (WIP:validation-arch C2 "E141 and E142 emitted but unregistered")

---

### HIGH

#### AUDIT-002: _load_fr_ids Duplicated 6 Times (~120 LOC)
- **Source:** A:DV1, B:DV1; C:corroborated
- **Category:** DRY_VIOLATION
- **Location:** validators/step_05.py:85, step_06.py:117, step_07.py:83, step_08.py:86, step_12.py:122, step_13a.py:101
- **Description:** Six copies of _load_fr_ids with cosmetic differences (guard style, variable names, type hints). All scan spec/ for 04_*.json and extract fr_id from functional_requirements array.
- **Recommendation:** Extract to shared core/loaders.py with load_upstream_ids(toolkit_root, step_prefix, array_key, id_field).
- **WIP Status:** CONFIRMED (WIP:validators-dry C5/E1 "7 independent FR-ID loaders, ~408 LOC total")

#### AUDIT-003: _load_api_ids Duplicated 5 Times (~100 LOC)
- **Source:** A:DV2, B:DV2; C:corroborated
- **Category:** DRY_VIOLATION
- **Location:** validators/step_06.py:139, step_08.py:108, step_11.py:135, step_13a.py:123, step_15.py:81
- **Description:** Five copies of _load_api_ids. step_11 and step_15 have divergent fallback keys (endpoint_id, contracts) that other copies lack.
- **Recommendation:** Shared helper with optional fallback keys parameter.
- **WIP Status:** CONFIRMED (WIP:validators-dry C5)

#### AUDIT-004: validate.py Is Over-Centralized Orchestrator (537 LOC)
- **Source:** A:SL1, B:SL1; C:corroborated
- **Category:** SOC_BREACH
- **Location:** validation/validate.py (537 LOC)
- **Description:** validate.py orchestrates 10+ distinct checks including schema validation, deep validation, quality lint, canonical integrity/lint, prompt-schema sync, dependency ordering, forward replay, extraction intent, traceability closure, and W->E promotion. It imports from 3 subpackages.
- **Recommendation:** Extract validate_dir orchestration into a separate orchestrator module; keep validate_file focused on single-file validation.
- **WIP Status:** CONFIRMED (WIP:validation-arch C4 "validate_dir() merges all layer outputs")

#### AUDIT-005: Layer Violation: validation/ imports from generation/
- **Source:** A:SL2(high), A:S6, B:SL2(medium), B:S7; C:resolved to HIGH
- **Category:** LAYER_VIOLATION
- **Location:** validation/validate.py:20
- **Description:** validate.py imports run_prompt_schema_sync from generation.prompt_schema_sync. Combined with generation/schema_differ.py importing back from validation (deferred), this creates a bidirectional dependency.
- **Recommendation:** Move prompt_schema_sync to validation/ or invoke from cli.py as standalone step.
- **WIP Status:** CONFIRMED (WIP:config-imports A6-002 "Bidirectional import coupling between validation and generation")

#### AUDIT-006: Version Mismatch Across Documentation (0.3.0 vs 0.4.0)
- **Source:** A:S1, A:H7, B:S1, B:H7; C:corroborated
- **Category:** DOCUMENTATION
- **Location:** CLAUDE.md:9, pyproject.toml:7, tools/README.md:1, docs/developers/getting_started.md:65
- **Description:** CLAUDE.md says 0.3.0, pyproject.toml says 0.4.0, README says "v3 Full". No __version__ in package.
- **Recommendation:** Update all to 0.4.0; add __version__ = "0.4.0" or use importlib.metadata.
- **WIP Status:** NEW

#### AUDIT-007: Errors Are Flat Strings, Not Structured Objects
- **Source:** A:E1, B:E1, A:ALIGNMENT-3, B:ALIGNMENT-3; C:corroborated
- **Category:** LLM_UNFRIENDLY
- **Location:** All validators, all linters, validate.py
- **Description:** Validators return list[str]. SpecError dataclass exists in errors.py (code, message, path) but is NEVER used by any validator or linter. All 21 validators + 17 linters construct error strings inline as f-strings.
- **Recommendation:** Phased migration to list[SpecError]; render to strings at CLI output layer.
- **WIP Status:** CONFIRMED (WIP:validation-arch C2 "make_error/SpecError completely unused")

#### AUDIT-008: Inconsistent Error Message Format Across Validators
- **Source:** A:E2(high), B:E2(medium); C:resolved to HIGH
- **Category:** FORMAT_INCONSISTENCY
- **Location:** validators/step_04.py, step_05.py, step_06.py vs step_08.py, step_12.py
- **Description:** step_04/step_05/step_06 emit plain messages ("Duplicate fr_id 'x'") with no error code. step_08/step_12/step_13/step_13a emit coded messages ("E590 ..."). ~60+ messages across fixtures_lint, seed_lint, cross_artifact_checks carry no code prefix at all.
- **Recommendation:** Add error codes to all validator messages; use SpecError.
- **WIP Status:** CONFIRMED (WIP:validation-arch C3 "~60+ messages have no machine-readable severity")

#### AUDIT-009: step_01/step_02 Duplicate Schema Validation
- **Source:** A:S5, A:G2, B:S9, B:G1; C:corroborated
- **Category:** SCHEMA_VALIDATOR_MISMATCH
- **Location:** validators/step_01.py:56-74, validators/step_02.py:127+
- **Description:** step_01 and step_02 deep validators create their own SchemaRegistry, load schema by hardcoded URI, and run iter_errors(). validate.py already does this before calling deep validators. Double schema validation for these steps.
- **Recommendation:** Remove schema validation from step_01 and step_02 deep validators; they should only do semantic checks.
- **WIP Status:** CONFIRMED (WIP:validation-arch C4 "step_01.py and step_02.py re-run JSON Schema validation")

#### AUDIT-010: test_step_11.py Reads Live spec/ Files (6 Nonexistent)
- **Source:** A:T1, B:T1; C:corroborated
- **Category:** SPEC_MISUSE
- **Location:** tests/integration/test_step_11.py:58-94
- **Description:** Integration test calls load_json_file for 7 spec/ files. Only spec/05_interface_contracts.json exists. The other 6 are missing, creating fragile coupling to live spec state.
- **Recommendation:** Refactor to use test fixtures from tests/fixtures/.
- **WIP Status:** CONFIRMED (WIP:test-structure B8 "tests/integration/test_step_11.py uses load_json_file")

#### AUDIT-011: hallucination_lint Uses Wrong NFR Key (n["id"] vs nfr_id) -- BUG
- **Source:** A:G5; C:verified genuine, B missed entirely
- **Category:** BUG
- **Location:** validation/hallucination_lint.py:277-278
- **Description:** hallucination_lint's _load_nfr_ids extracts n["id"] from nfrs array, but the schema field is nfr_id. Validators correctly use nfr.get("nfr_id"). If NFR artifacts use the schema-correct nfr_id field, hallucination lint silently fails to load NFR IDs, causing false E530 errors.
- **Recommendation:** Fix to use nfr_id field name. 5-minute fix.
- **WIP Status:** NEW

#### AUDIT-012: _collect_ids_and_refs Duplicated Between Linters
- **Source:** A:SL3; C:verified genuine, B missed
- **Category:** DRY_VIOLATION
- **Location:** hallucination_lint.py:138-161, spec_quality_lint.py:215-232
- **Description:** Both linters implement _collect_ids_and_refs with nearly identical logic (~40 LOC duplicated). _iter_json is also duplicated (SL4), and _is_reference_context/_in_ref_context (SL5).
- **Recommendation:** Extract all three to shared validation utility (~118 LOC net savings per WIP:validation-arch E6).
- **WIP Status:** CONFIRMED (WIP:validation-arch E6 "_collect_ids_and_refs() duplicated")

#### AUDIT-013: generation/ Package Test Coverage Sparse (2144 LOC untested)
- **Source:** A:T7, B:T5; C:corroborated
- **Category:** COVERAGE_GAP
- **Location:** generation/schema_differ.py (1331 LOC), generation/prompt_generator.py (813 LOC)
- **Description:** Two largest modules have no dedicated test files. Coverage comes only through indirect integration tests.
- **Recommendation:** Add test_schema_differ.py and test_prompt_generator.py.
- **WIP Status:** CONFIRMED (WIP:test-quality B5-02 "7 source modules have zero corresponding test files")

#### AUDIT-014: W->E Promotion Only Works in validate_dir, Not validate_file
- **Source:** A:E3; C:verified genuine (A-only)
- **Category:** PROPAGATION_BUG
- **Location:** validate.py:267-289
- **Description:** SPECDEV_WARNINGS_AS_ERRORS promotion logic is only in validate_dir(). validate_file() does not promote. CLI validate command calls validate_file() directly for single-file validation.
- **Recommendation:** Move promotion logic to _print_and_exit_if_errors or add to validate_file.
- **WIP Status:** CONFIRMED (WIP:validation-arch C7 "validate_file does not apply promotion")

---

### MEDIUM

#### AUDIT-015: _load_capability_ids Duplicated 2 Times
- **Source:** A:DV3, B:DV3; C:corroborated
- **Category:** DRY_VIOLATION
- **Location:** validators/step_04.py:63, step_09.py:52
- **Description:** Two copies with identical logic, only variable naming differs. ~40 LOC.
- **Recommendation:** Extract to shared loader helper.
- **WIP Status:** CONFIRMED (WIP:validators-dry C5)

#### AUDIT-016: _load_nfr_ids Duplicated 2 Times
- **Source:** A:DV4, B:DV4; C:corroborated
- **Category:** DRY_VIOLATION
- **Location:** validators/step_08.py:152, step_12.py:145
- **Description:** Two copies with identical logic. ~40 LOC.
- **Recommendation:** Extract to shared loader helper.
- **WIP Status:** CONFIRMED (WIP:validators-dry C5)

#### AUDIT-017: step_14 Loaders Have Different Signature (artifact_path)
- **Source:** A:DV5, B:DV5; C:corroborated
- **Category:** ABSTRACTION_MISSING
- **Location:** validators/step_14.py:152, 184, 203, 228
- **Description:** Four loaders (~100 LOC) take (toolkit_root, artifact_path) instead of (toolkit_root). Use Path objects with sibling-file resolution.
- **Recommendation:** Extract load_sibling_artifact helper; keep extraction logic per-caller.
- **WIP Status:** CONFIRMED (WIP:validators-dry C5)

#### AUDIT-018: upstream_map Pattern Duplicated 3 Times
- **Source:** A:DV6, B:DV7; C:corroborated
- **Category:** DRY_VIOLATION
- **Location:** step_08.py:41-56, step_12.py:42-55, step_13a.py:35-48
- **Description:** Three copies of upstream_map building + W590/E590 emission pattern. ~45 LOC.
- **Recommendation:** Extract check_cross_step_refs(targets, upstream_map, errors) helper.
- **WIP Status:** CONFIRMED (WIP:validators-dry C5)

#### AUDIT-019: validate.py Also Has _load_* Functions (Duplication with Validators)
- **Source:** A:DV9(medium), B:SL8(medium); C:corroborated
- **Category:** DRY_VIOLATION
- **Location:** validate.py:303-370
- **Description:** validate.py defines _load_json_artifact, _load_component_ids, _load_capability_ids, _load_nfrs_data, _load_monitoring_data (~50 LOC). Similar to but different from the 23 _load_* functions in validators/.
- **Recommendation:** Unify with shared _loaders.py.
- **WIP Status:** CONFIRMED (WIP:validators-dry C5)

#### AUDIT-020: schema_differ.py Is Oversized (1331 LOC)
- **Source:** A:SL7, B:SL4; C:corroborated
- **Category:** SOC_BREACH
- **Location:** generation/schema_differ.py (1331 LOC)
- **Description:** Largest module in codebase. Handles diff computation, status/diff/plan report formatting, auto-fix application, backup/restore, pre/post migration validation, and operation logging.
- **Recommendation:** Split into schema_differ_core.py, schema_differ_reports.py, schema_differ_apply.py.
- **WIP Status:** NEW

#### AUDIT-021: STEP_NAMES Dict Hardcoded in cli.py
- **Source:** A:S9(low), B:S2(medium), B:H4; C:resolved to MEDIUM
- **Category:** HARDCODED_VALUE
- **Location:** cli.py:666-675
- **Description:** 22-entry STEP_NAMES dict hardcoded in prompt-context handler. Will drift if steps are added/renamed.
- **Recommendation:** Derive from step_order.json or shared constant.
- **WIP Status:** CONFIRMED (WIP:cli-package A1 "Inline STEP_NAMES constant"; WIP:hardcoded F4-01)

#### AUDIT-022: KNOWN_STAGES Hardcoded Instead of Loading from Canon
- **Source:** A:H4, A:SL9, B:H6, B:SL3; C:corroborated
- **Category:** HARDCODED_VALUE
- **Location:** hallucination_lint.py:13, step_07.py:9
- **Description:** Both define KNOWN_STAGES = {"dev", "ci", "staging", "prod"} as local constants instead of loading from canon/kinds/stage.json.
- **Recommendation:** Load from canon; use hardcoded only as fallback.
- **WIP Status:** CONFIRMED (WIP:hardcoded F5-04 partial)

#### AUDIT-023: VALID_CHECKLIST_TYPES/LAYERS Hardcoded in step_16
- **Source:** A:H10, B:H5; C:corroborated
- **Category:** HARDCODED_VALUE
- **Location:** validators/step_16.py:7-8
- **Description:** Frozensets of 9 checklist types and 9 layers hardcoded. Should be in schema enum or canon/kinds/.
- **Recommendation:** Move to schema enum constraints or canonical registry.
- **WIP Status:** CONFIRMED (WIP:hardcoded F5-03)

#### AUDIT-024: allowed_pr_rules Hardcoded in hallucination_lint
- **Source:** A:H6; C:verified genuine (A-only)
- **Category:** HARDCODED_VALUE
- **Location:** hallucination_lint.py:116-120
- **Description:** 14 allowed pr_rules values hardcoded. Should be derived from CLI subcommand list or config.
- **Recommendation:** Extract to shared constant or load from CLI registration.
- **WIP Status:** NEW

#### AUDIT-025: Only 2 of 25 Commands Support --json Output
- **Source:** A:E5, B:E4, A:ALIGNMENT-7, B:ALIGNMENT-3(partial); C:corroborated
- **Category:** MISSING_JSON
- **Location:** cli.py (validate, traceability-check only)
- **Description:** 23 commands output human-readable text only. No machine-parsable output for CI integration and LLM consumption.
- **Recommendation:** Add --json flag to all validation commands using a shared JSON formatter.
- **WIP Status:** NEW

#### AUDIT-026: Deep Validation Errors Lack JSON Field Path Context
- **Source:** A:E7; C:verified genuine (A-only)
- **Category:** LLM_UNFRIENDLY
- **Location:** validate.py:158
- **Description:** Deep validator errors are prefixed with file path but lack the JSON field path within the document (e.g., "functional_requirements[3].fr_id") for LLM self-correction.
- **Recommendation:** Deep validators should include JSON path in error messages.
- **WIP Status:** NEW

#### AUDIT-027: test_r9_* Files Overlap With Pre-existing Tests (4740 LOC)
- **Source:** A:T4, B:T4; C:corroborated
- **Category:** R9_OVERLAP
- **Location:** tests/test_r9_*.py (10 files, 4740 LOC)
- **Description:** R9 test files sit alongside pre-existing tests for the same modules. Per WIP:test-structure B2 analysis, 240+ of 246 R9 tests are actually unique. Primary issue is naming convention (test_r9_ prefix) not actual duplication.
- **Recommendation:** Rename test_r9_* files to descriptive names (e.g., test_r9_validate.py -> test_warning_promotion.py). Merge the ~6 overlapping tests from test_r9_error_codes.py into test_error_code_coverage.py.
- **WIP Status:** CONFIRMED (WIP:test-structure B2)

#### AUDIT-028: Conftest Fixtures Duplicated Between Unit and Integration
- **Source:** A:T2, B:T2; C:corroborated
- **Category:** CONFTEST_DUP
- **Location:** tests/conftest.py, tests/integration/conftest.py
- **Description:** 5 identical fixtures defined in both conftest files. Only REPO_ROOT resolution depth differs.
- **Recommendation:** Extract shared fixture definitions to a helper module that takes depth parameter.
- **WIP Status:** CONFIRMED (WIP:test-structure E4, WIP:test-quality B4-02)

#### AUDIT-029: steps 16a/16b/16c Run Full step_16 Validator (Triple Execution)
- **Source:** A:G3, B:G2; C:corroborated
- **Category:** SCHEMA_VALIDATOR_MISMATCH
- **Location:** step_16a.py:15, step_16b.py:15, step_16c.py:17
- **Description:** All three sub-step validators call validate_step_16 (415 LOC) as their first line. When validate_dir processes a spec directory with all three sub-step artifacts, step_16 validation runs 3 extra times with file I/O.
- **Recommendation:** Cache step_16 validation results or restructure so base checks run once.
- **WIP Status:** NEW

#### AUDIT-030: Step File Prefixes Hardcoded in All Loaders
- **Source:** A:H3, B:H1(high); C:resolved to MEDIUM (folded into DRY fix)
- **Category:** HARDCODED_VALUE
- **Location:** All 23 _load_* functions across validators
- **Description:** Every _load_* function hardcodes step file prefix strings like "04_", "05_" as literals.
- **Recommendation:** Shared loader should accept step prefix as parameter (solved by AUDIT-002/003 fix).
- **WIP Status:** CONFIRMED (WIP:hardcoded F4 systematic pattern)

#### AUDIT-031: No Dedicated Test for governance.py
- **Source:** A:T5(medium), B:T6(low); C:resolved to MEDIUM
- **Category:** COVERAGE_GAP
- **Location:** validation/governance.py (37 LOC)
- **Description:** No test_governance.py exists. May be indirectly tested via CLI tests.
- **Recommendation:** Add test_governance.py with edge cases.
- **WIP Status:** CONFIRMED (WIP:test-quality B5-02)

#### AUDIT-032: tools/core/json_utils.py Has No Tests
- **Source:** B:T8; C:verified genuine (B-only, A missed)
- **Category:** COVERAGE_GAP
- **Location:** tools/core/json_utils.py (499 LOC)
- **Description:** Standalone module outside specdev_tools package with no test coverage. Uses subprocess calls to jq.
- **Recommendation:** Add tests or document that this is an external tool helper not part of core package.
- **WIP Status:** NEW

#### AUDIT-033: W->E Promotion Uses Fragile String Prefix Replacement
- **Source:** B:E5; C:verified genuine (B-only complements A:E3)
- **Category:** FORMAT_INCONSISTENCY
- **Location:** validate.py:274-282
- **Description:** Promotion replaces first occurrence of W-code prefix with E-code. Works correctly with current format but fragile. Would be cleaner with structured errors.
- **Recommendation:** Migrate to structured SpecError (part of AUDIT-007 fix).
- **WIP Status:** CONFIRMED (WIP:validation-arch C7)

#### AUDIT-034: CLAUDE.md Missing CLI Subcommands
- **Source:** A:S8, B:S10; C:corroborated
- **Category:** DOCUMENTATION
- **Location:** CLAUDE.md
- **Description:** CLAUDE.md documents ~18 commands but CLI has 25 subcommands. Missing: canonical-autofix, prompt-context, canon-schema-alignment, env-check, changelog, align validate/rollback, prompt-sync.
- **Recommendation:** Update CLAUDE.md Core CLI Commands section.
- **WIP Status:** NEW

#### AUDIT-035: canonical/lint.py and integrity.py Coupling
- **Source:** A:SL6(medium), B:SL5(low); C:resolved to MEDIUM (A rated medium, B rated low; retained at MEDIUM due to undocumented coupling boundary)
- **Category:** SOC_BREACH
- **Location:** canonical/lint.py (472 LOC), canonical/integrity.py (640 LOC)
- **Description:** integrity.py calls lint_canon_dir() as preflight, creating tight coupling. validate.py also calls lint_canon_dir() independently. Boundary is reasonable but undocumented.
- **Recommendation:** Add module-level docstrings clarifying the boundary.
- **WIP Status:** NEW

#### AUDIT-036: No Centralized Config Module for Env Vars
- **Source:** WIP:config-imports A4-001, A4-002; cross-referenced with A:E3 and B:E5
- **Category:** DRY_VIOLATION
- **Location:** cli.py:18,233,705,706,734,736; validate.py:238,240,269,270,484; forward_replay_check.py:86
- **Description:** 7 distinct SPECDEV_* env vars read across 12 call sites in 3 files with duplicated boolean parsing logic. SPECDEV_WARNINGS_AS_ERRORS is read 3 times with identical inline parse logic.
- **Recommendation:** Create a centralized config.py module that reads all env vars once and exports typed values.
- **WIP Status:** CONFIRMED (WIP:config-imports A4-001, A4-002, E3-001)

#### AUDIT-037: Schema URIs Hardcoded in step_01/step_02 Validators
- **Source:** A:H1(high), B:H2(medium); C:resolved to MEDIUM (subsumes into AUDIT-009)
- **Category:** HARDCODED_VALUE
- **Location:** validators/step_01.py:57, step_02.py:127
- **Description:** Hardcoded schema URIs like "https://specdev.local/schema/01_capabilities.schema.json". Redundant since validate.py already does schema validation via registry.
- **Recommendation:** Remove entirely -- subsumed by AUDIT-009 fix (remove duplicate schema validation).
- **WIP Status:** CONFIRMED (WIP:hardcoded F3-01, F3-02)

#### AUDIT-038: W550 Code Reused With Different Semantics
- **Source:** WIP:validation-arch C3
- **Category:** REGISTRY_INCONSISTENCY
- **Location:** seed_lint.py:253 vs forward_replay_check.py:95
- **Description:** seed_lint uses W550 for UNDECLARED_SEED but errors.py registers W550 as SEMANTIC_COVERAGE_SKIP. The code slot is reused with completely different meaning, breaking the registry contract.
- **Recommendation:** Assign a new W-code for UNDECLARED_SEED in seed_lint.
- **WIP Status:** CONFIRMED (WIP:validation-arch C3)

#### AUDIT-039: E310 Registry Name Mismatch With Emitted Name
- **Source:** WIP:validation-arch C2
- **Category:** REGISTRY_INCONSISTENCY
- **Location:** validators/step_05.py:27, errors.py:43
- **Description:** E310 is registered as PROMPT_SCHEMA_DRIFT but emitted as MISSING_ENUM_PROVENANCE in step_05.py. Unrelated semantics sharing one code.
- **Recommendation:** Either rename E310 in the registry or assign a new code for MISSING_ENUM_PROVENANCE.
- **WIP Status:** CONFIRMED (WIP:validation-arch C2)

#### AUDIT-040: Duplicate Stopword Sets Between hallucination_lint and forward_replay_check
- **Source:** WIP:validation-arch E2, E6
- **Category:** DRY_VIOLATION
- **Location:** hallucination_lint.py:294-300, forward_replay_check.py:329-335
- **Description:** _DERIVATION_STOPWORDS and _CONTENT_STOPWORDS are identical 24-word sets. forward_replay_check.py:337 acknowledges it's a copy. Free-text tokenizer is also duplicated 3 times (~50 LOC).
- **Recommendation:** Extract to shared linter_utils.py.
- **WIP Status:** CONFIRMED (WIP:validation-arch E6)

#### AUDIT-041: "Duplicate {id}_id" Message Pattern in 11 Step Validators With No Shared Helper
- **Source:** WIP:validation-arch E2
- **Category:** DRY_VIOLATION
- **Location:** step_02.py:17, step_03.py:40, step_04.py:25, step_05.py:17, step_06.py:20, step_07.py:35, step_08.py:20, step_12.py:20, step_13.py:21, step_14.py:26, step_16b.py:36
- **Description:** Each step validator independently constructs duplicate-ID detection and message formatting. No shared _check_no_duplicates() helper.
- **Recommendation:** Extract common duplicate detection to shared utility.
- **WIP Status:** CONFIRMED (WIP:validation-arch E2)

#### AUDIT-042: Enum Constraints From Canon/Kinds Not Applied to Schemas
- **Source:** B:ALIGNMENT-7; C:verified genuine (B-only)
- **Category:** ALIGNMENT_GAP
- **Location:** canon/kinds/ (25 files) vs schema/ (24 files)
- **Description:** Canon/kinds/ has 25 kind files with constrained value sets (owner, stage, trace_type, etc.) but many schema string fields that could use enum constraints are free-form.
- **Recommendation:** Audit all schema string fields against canon/kinds/ entries; add enum constraints.
- **WIP Status:** NEW

#### AUDIT-043: DEEP_VALIDATORS Dict Hardcoded in validate.py
- **Source:** WIP:hardcoded F4-02
- **Category:** HARDCODED_VALUE
- **Location:** validate.py:376-402
- **Description:** Step-to-validator mapping hardcoded for 21 steps. Adding a new step requires updating this dict and the import block at lines 24-46.
- **Recommendation:** Consider auto-discovery or derive from step_order.json.
- **WIP Status:** CONFIRMED (WIP:hardcoded F4-02)

#### AUDIT-044: _STEP_TO_TEMPLATE Duplicated Between prompt_generator.py and planner.py
- **Source:** WIP:hardcoded F4-03, F4-04
- **Category:** DRY_VIOLATION
- **Location:** generation/prompt_generator.py:523-537, migration/planner.py:38-57
- **Description:** Two independent copies of _STEP_TO_TEMPLATE dict mapping steps to templates. Must be kept in sync manually.
- **Recommendation:** Extract to a shared constant or derive from step_order.json metadata.
- **WIP Status:** CONFIRMED (WIP:hardcoded F4-03, F4-04)

---

### LOW

#### AUDIT-045: Kebab-case ID Regex Duplicated Across Files
- **Source:** A:DV7(low), B:DV6(medium); C:resolved to LOW
- **Category:** DRY_VIOLATION
- **Location:** step_04.py:6, step_06.py:8-9, step_07.py:10, step_08.py:8-9, step_12.py:10-11, step_13a.py:8, step_14.py:10-12, step_15.py:44
- **Description:** re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$") with various prefixes duplicated across 8 files (~16 LOC).
- **Recommendation:** Central KEBAB_ID_RE in core/ with factory: kebab_id_re(prefix="fr").
- **WIP Status:** CONFIRMED (WIP:validators-dry C5)

#### AUDIT-046: Import Pattern Inconsistency Across Validators
- **Source:** A:DV8, B:DV8; C:corroborated
- **Category:** DRY_VIOLATION
- **Location:** All 21 validator files
- **Description:** Some use from __future__ import annotations, some don't. Type hints vary: Optional[Set[str]] vs set[str] | None.
- **Recommendation:** Standardize on from __future__ import annotations + modern syntax.
- **WIP Status:** NEW

#### AUDIT-047: Orphaned UNKNOWN.egg-info Directory
- **Source:** A:S3, B:S4; C:corroborated
- **Category:** PACKAGING
- **Location:** tools/UNKNOWN.egg-info/
- **Description:** Stale egg-info from previous build with misconfigured setup.py.
- **Recommendation:** Delete and add *.egg-info/ to .gitignore.
- **WIP Status:** NEW

#### AUDIT-048: Stale trace_matrix.json Checked In
- **Source:** A:S4, B:S5; C:corroborated
- **Category:** PACKAGING
- **Location:** tools/trace_matrix.json
- **Description:** All-zero counters, last modified 2025-02-22. CI regenerates it.
- **Recommendation:** Add to .gitignore.
- **WIP Status:** NEW

#### AUDIT-049: migration_prompts_root Fixture May Be Unused
- **Source:** A:T3, B:T3; C:corroborated
- **Category:** REDUNDANCY
- **Location:** tests/conftest.py:43-46
- **Description:** Defined only in top-level conftest. Potentially unreferenced by any test.
- **Recommendation:** Verify usage; remove if unused.
- **WIP Status:** NEW

#### AUDIT-050: governance.py File Handle Leak
- **Source:** B:SL6; C:verified genuine (B-only, A missed)
- **Category:** RESOURCE_LEAK
- **Location:** validation/governance.py:11
- **Description:** json.load(open(...)) opens a file without closing it. Minor resource leak.
- **Recommendation:** Use with open(...) as f: data = json.load(f).
- **WIP Status:** NEW

#### AUDIT-051: Module-Load-Time warnings.warn in step_01 and step_11
- **Source:** A:G7, B:G6; C:corroborated
- **Category:** CODE_HEALTH
- **Location:** step_01.py:20-25, step_11.py:33-43, step_02.py:83
- **Description:** warnings.warn() fires at import time for trace type validation checks. Could confuse users.
- **Recommendation:** Move checks to validation functions or use once-per-session flag.
- **WIP Status:** NEW

#### AUDIT-052: Step 00 Has No Deep Validator
- **Source:** A:G4, B:G4; C:corroborated
- **Category:** SCHEMA_VALIDATOR_MISMATCH
- **Location:** N/A (no step_00.py)
- **Description:** Step 00 (Charter) relies solely on JSON Schema validation. Schema is 202 lines with 21 properties.
- **Recommendation:** Acceptable as-is; charter has no cross-step references.
- **WIP Status:** NEW

#### AUDIT-053: Edge Case -- Empty Spec Directory
- **Source:** A:G6; C:verified genuine (A-only)
- **Category:** EDGE_CASE
- **Location:** validate.py:180
- **Description:** validate_dir on empty spec dir still runs canonical lint, quality lint, etc. Confusing output.
- **Recommendation:** Add early exit with informational message if spec_dir has no .json files.
- **WIP Status:** NEW

#### AUDIT-054: Error Deduplication Loses Ordering Context
- **Source:** B:E7; C:verified genuine (B-only)
- **Category:** PROPAGATION_BUG
- **Location:** validate.py:284
- **Description:** dict.fromkeys dedup can mask repeated errors from different files if the error message lacks file path.
- **Recommendation:** Ensure all error messages include file path context.
- **WIP Status:** NEW

#### AUDIT-055: No Global Exception Handler in cli.py
- **Source:** B:E8; C:verified genuine (B-only)
- **Category:** PROPAGATION_BUG
- **Location:** cli.py:190-753
- **Description:** No global try/except. Unhandled exceptions produce full tracebacks to users.
- **Recommendation:** Add top-level try/except for SpecdevError with clean message.
- **WIP Status:** CONFIRMED (WIP:config-imports A8-004 partial)

#### AUDIT-056: validators/__init__.py Only Re-exports 3 of 21 Modules
- **Source:** B:S3; C:verified genuine (B-only)
- **Category:** STRUCTURE
- **Location:** validators/__init__.py (11 LOC)
- **Description:** Only imports step_16a/16b/16c. All other 18 validators imported directly in validate.py.
- **Recommendation:** Either import all or none for consistency.
- **WIP Status:** NEW

#### AUDIT-057: Vague Quantifier Regex Has Subjective Word List
- **Source:** B:H11; C:verified genuine (B-only)
- **Category:** MAGIC_NUMBER
- **Location:** spec_quality_lint.py:14-18
- **Description:** ~18 "vague" words hardcoded. Subjective and could produce false positives.
- **Recommendation:** Make word list configurable.
- **WIP Status:** NEW

#### AUDIT-058: Filesystem Path Assumptions (spec/, canon/, schema/)
- **Source:** A:H11(medium), B:H10(low); C:resolved to LOW
- **Category:** ASSUMPTION
- **Location:** Throughout codebase
- **Description:** Hardcoded path segments "spec/", "canon/", "schema/", "tools/", "prompts/" appear ~50 times. Acceptable for toolkit internals.
- **Recommendation:** Document the assumed directory structure.
- **WIP Status:** CONFIRMED (WIP:hardcoded F2)

#### AUDIT-059: ASSUMPTION_THRESHOLD and Content Derivation Threshold Magic Numbers
- **Source:** A:H8, A:H9; C:verified genuine (A-only, trivial)
- **Category:** MAGIC_NUMBER
- **Location:** spec_quality_lint.py:114 (ASSUMPTION_THRESHOLD=10), hallucination_lint.py:335 (threshold=5)
- **Recommendation:** Move to module-level named constants.
- **WIP Status:** CONFIRMED (WIP:hardcoded F1-01, F1-02)

#### AUDIT-060: Inline JSON Blobs in Tests vs Fixture Files
- **Source:** A:T9; C:verified genuine (A-only, stylistic)
- **Category:** TOKEN_WASTE
- **Location:** Multiple test files
- **Description:** Many tests define large inline JSON dicts when tests/fixtures/ has 133 fixture files.
- **Recommendation:** Audit for opportunities to use fixture files.
- **WIP Status:** CONFIRMED (WIP:test-quality B4-03)

---

### INFO

#### AUDIT-061: Lazy Import Shim Has 22-23 Entries
- **Source:** A:S7(low), B:S8(info); C:resolved to INFO
- **Category:** STRUCTURE
- **Location:** tools/specdev_tools/__init__.py
- **Description:** _MOVED dict maps 22-23 module names for backward-compat lazy imports. Functional but maintenance burden.
- **Recommendation:** Audit for external consumers; simplify if none.
- **WIP Status:** CONFIRMED (WIP:cli-package A6 PASS)

#### AUDIT-062: Empty tools/context/ Directory
- **Source:** B:S6; C:verified genuine (B-only)
- **Category:** STRUCTURE
- **Location:** tools/context/
- **Description:** Empty directory with no references in codebase.
- **Recommendation:** Remove or document purpose.
- **WIP Status:** NEW

#### AUDIT-063: validate_file Continues After Schema Errors (Collect-All by Design)
- **Source:** A:E4, B:E3; C:corroborated
- **Category:** DESIGN_NOTE
- **Location:** validate.py:136-173
- **Description:** After schema errors, validate_file still runs deep validators and quality lint. Collect-all behavior -- correct by design but deep validators may crash on malformed data.
- **Recommendation:** Consider short-circuiting deep validation when critical schema errors exist.
- **WIP Status:** CONFIRMED (WIP:validation-arch C4)

#### AUDIT-064: cli.py Monolithic Dispatch (757 LOC, 24-branch if/elif)
- **Source:** WIP:cli-package A1 MAJOR; partially corroborated by A:S8, B:S10
- **Category:** SOC_BREACH
- **Location:** cli.py:44-754
- **Description:** Single main() function with 25 subcommands via flat add_subparsers and 24-branch if/elif chain. Industry standard is command groups with one module per group.
- **Recommendation:** Consider splitting into command groups (validation, canonical, generation, migration).
- **WIP Status:** MISSED_BY_AUDIT -- added from WIP:cli-package A1

#### AUDIT-065: No Logging Module Usage; 118 print() Calls
- **Source:** WIP:config-imports A9-001, A9-002
- **Category:** OBSERVABILITY
- **Location:** cli.py (111 print calls), validate.py (2), prompt_schema_sync.py (2)
- **Description:** Zero logging usage across CLI/validation layer. No --quiet or --verbose flags. Library-level print() in prompt_schema_sync.py produces side-effectful terminal output.
- **Recommendation:** Add logging module; add --verbose/--quiet flags; replace library-level prints with returns.
- **WIP Status:** MISSED_BY_AUDIT -- added from WIP:config-imports A9

#### AUDIT-066: schema_differ.py Git Subprocess Calls Lack Timeout
- **Source:** WIP:config-imports F6-003
- **Category:** ROBUSTNESS
- **Location:** generation/schema_differ.py:888,970,976,983
- **Description:** Git subprocess calls in backup and pre-migration functions lack timeout parameter. Additionally git add -A stages ALL files in working tree, not just spec files.
- **Recommendation:** Add timeout=10 to all git subprocess calls; scope git add to specific paths.
- **WIP Status:** MISSED_BY_AUDIT -- added from WIP:config-imports F6-003

#### AUDIT-067: No Test Markers (unit/integration); CI Has No pytest Job
- **Source:** WIP:pipeline D1
- **Category:** CI_GAP
- **Location:** .github/workflows/ci.yml, tests/
- **Description:** No @pytest.mark.unit or @pytest.mark.integration markers. CI workflow runs 14 CLI lint commands but never runs pytest tests/. Pytest suite and CI are entirely disconnected.
- **Recommendation:** Add test markers; add pytest job to CI workflow.
- **WIP Status:** MISSED_BY_AUDIT -- added from WIP:pipeline D1

#### AUDIT-068: No Property-Based Testing (Hypothesis)
- **Source:** WIP:pipeline D2
- **Category:** TEST_METHODOLOGY
- **Location:** tests/ (all files)
- **Description:** Zero hypothesis or property-based testing across 130 fixtures and 52+ test files. Steps with complex schemas would benefit from hypothesis-jsonschema auto-generation.
- **Recommendation:** Consider adding hypothesis for complex schema validation tests.
- **WIP Status:** MISSED_BY_AUDIT -- added from WIP:pipeline D2

#### AUDIT-069: Conftest Fixtures Lack Session Scoping
- **Source:** WIP:test-quality B4-01
- **Category:** TEST_EFFICIENCY
- **Location:** tests/conftest.py, tests/integration/conftest.py
- **Description:** All conftest fixtures use default function scope. No session-scoped fixtures for expensive setup operations (e.g., repo root resolution, schema registry loading). With 830+ tests, repeated per-function setup adds unnecessary overhead.
- **Recommendation:** Audit fixtures for session-scope candidates; apply @pytest.fixture(scope="session") where setup is idempotent and stateless.
- **WIP Status:** MISSED_BY_AUDIT -- added from WIP:test-quality B4-01

#### AUDIT-070: Flat Test Directory Structure Does Not Mirror Source Package
- **Source:** User feedback (missed by all review agents)
- **Category:** TEST_STRUCTURE
- **Location:** tests/ (50 unit test files flat in root)
- **Description:** Source package is well-organized (core/, validation/, canonical/, generation/, migration/) but all 50 unit test files sit flat in tests/. Should mirror source structure: tests/unit/core/, tests/unit/validation/validators/, tests/unit/validation/linters/, tests/unit/canonical/, tests/unit/generation/, tests/unit/migration/.
- **Recommendation:** Reorganize tests/ to mirror source package structure. Move test files into subdirectories matching the module they test.
- **WIP Status:** MISSED_BY_AUDIT -- flagged by user

---

## Research Alignment Gaps (from P2)

These are strategic improvement opportunities, not bugs. Included for P4 planning.

| # | Pattern | Gap | Effort | Quick Win |
|---|---------|-----|--------|-----------|
| ALIGN-1 | $ref/$defs DRY authoring | MEDIUM | M | NO |
| ALIGN-2 | URN-based $id (URL->URN) | LARGE | L | NO |
| ALIGN-3 | Structured error objects | LARGE | L | Partial (see AUDIT-007) |
| ALIGN-4 | additionalProperties:false | NONE (achieved) | - | YES |
| ALIGN-5 | Max 3-level nesting | FUNDAMENTAL (step_16=19) | XL | NO |
| ALIGN-6 | 100% property descriptions | LARGE | M | YES |
| ALIGN-7 | --json all commands | MEDIUM | M | Partial (see AUDIT-025) |
| ALIGN-8 | WriteValidatedJSON MCP tool | LARGE | M | NO |
| ALIGN-9 | Pre-commit hook coverage | SMALL | S | YES |
| ALIGN-10 | src/dist schema split | LARGE | L | NO |

---

## Findings by Target File

| Target File | AUDIT IDs | Count |
|------------|-----------|-------|
| validators/step_14.py | AUDIT-001, AUDIT-017 | 2 |
| validators/step_13.py | AUDIT-001 | 1 |
| validators/step_01.py | AUDIT-009, AUDIT-037, AUDIT-051 | 3 |
| validators/step_02.py | AUDIT-009, AUDIT-037 | 2 |
| validators/step_05.py | AUDIT-002, AUDIT-003, AUDIT-039 | 3 |
| validators/step_06.py | AUDIT-002, AUDIT-003 | 2 |
| validators/step_07.py | AUDIT-002, AUDIT-022 | 2 |
| validators/step_08.py | AUDIT-002, AUDIT-003, AUDIT-016, AUDIT-018 | 4 |
| validators/step_12.py | AUDIT-002, AUDIT-016, AUDIT-018 | 3 |
| validators/step_13a.py | AUDIT-002, AUDIT-003, AUDIT-018 | 3 |
| validators/step_15.py | AUDIT-003 | 1 |
| validators/step_11.py | AUDIT-003 | 1 |
| validators/step_04.py | AUDIT-015 | 1 |
| validators/step_09.py | AUDIT-015 | 1 |
| validators/step_16.py | AUDIT-023, AUDIT-029 | 2 |
| validators/step_16a.py | AUDIT-029 | 1 |
| validators/step_16b.py | AUDIT-029 | 1 |
| validators/step_16c.py | AUDIT-029 | 1 |
| validators/__init__.py | AUDIT-056 | 1 |
| validation/validate.py | AUDIT-004, AUDIT-005, AUDIT-009, AUDIT-014, AUDIT-019, AUDIT-033, AUDIT-037, AUDIT-043, AUDIT-053, AUDIT-054 | 10 |
| validation/hallucination_lint.py | AUDIT-011, AUDIT-012, AUDIT-022, AUDIT-024, AUDIT-040 | 5 |
| validation/spec_quality_lint.py | AUDIT-012, AUDIT-057, AUDIT-059 | 3 |
| validation/governance.py | AUDIT-031, AUDIT-050 | 2 |
| validation/seed_lint.py | AUDIT-038 | 1 |
| validation/forward_replay_check.py | AUDIT-040 | 1 |
| core/errors.py | AUDIT-001, AUDIT-038, AUDIT-039 | 3 |
| cli.py | AUDIT-021, AUDIT-025, AUDIT-034, AUDIT-055, AUDIT-064, AUDIT-065 | 6 |
| generation/schema_differ.py | AUDIT-020, AUDIT-066 | 2 |
| generation/prompt_generator.py | AUDIT-013, AUDIT-044 | 2 |
| migration/planner.py | AUDIT-044 | 1 |
| canonical/lint.py | AUDIT-035 | 1 |
| canonical/integrity.py | AUDIT-035 | 1 |
| tools/core/json_utils.py | AUDIT-032 | 1 |
| CLAUDE.md | AUDIT-006, AUDIT-034 | 2 |
| pyproject.toml | AUDIT-006 | 1 |
| tools/README.md | AUDIT-006 | 1 |
| tools/UNKNOWN.egg-info/ | AUDIT-047 | 1 |
| tools/trace_matrix.json | AUDIT-048 | 1 |
| tools/context/ | AUDIT-062 | 1 |
| __init__.py | AUDIT-006, AUDIT-061 | 2 |
| tests/integration/test_step_11.py | AUDIT-010 | 1 |
| tests/conftest.py | AUDIT-028, AUDIT-049, AUDIT-069 | 3 |
| tests/integration/conftest.py | AUDIT-028, AUDIT-069 | 2 |
| tests/test_r9_*.py (10 files) | AUDIT-027 | 1 |
| .github/workflows/ci.yml | AUDIT-067 | 1 |

---

## WIP Cross-Check Report

| WIP File | Total Items | CONFIRMED | CONTRADICTED | STALE | MISSED_BY_AUDIT |
|----------|------------|-----------|--------------|-------|-----------------|
| findings-cli-package.md | 10 | 5 | 0 | 0 | 1 |
| findings-config-imports.md | 16 | 6 | 0 | 0 | 3 |
| findings-hardcoded.md | 29 | 12 | 0 | 0 | 0 |
| findings-pipeline.md | 10 | 3 | 1 | 0 | 1 |
| findings-test-quality.md | 12 | 5 | 1 | 1 | 1 |
| findings-test-structure.md | 6 | 4 | 0 | 0 | 0 |
| findings-validation-arch.md | 22 | 14 | 1 | 1 | 0 |
| findings-validators-dry.md | 8 | 7 | 0 | 0 | 0 |
| **TOTAL** | **113** | **56** | **3** | **2** | **6** |

Note: Remaining WIP items not classified above are either PASS records (not findings), INFO-level observations already folded into audit findings, or architectural recommendations beyond the scope of code-level audit. Specifically:
- **findings-pipeline.md**: D3 (PASS), D4 (PARTIAL, not actionable), D5 (GAP: declarative rules for linters, MEDIUM -- methodology recommendation, excluded from code-level audit scope), D6 (GAP: no golden file/snapshot testing, MEDIUM -- methodology recommendation, excluded from code-level audit scope). Both D5 and D6 are valid test methodology improvements but fall outside the code-level findings scope of this audit.
- **findings-cli-package.md**: A2 (handler SoC, MAJOR -- partially covered by AUDIT-064 monolithic dispatch; the handler-level separation concern is subsumed), A7 (floor pins only, MODERATE -- packaging concern; excluded as outside code-quality scope; noted for P4 consideration).
- **findings-test-quality.md**: 6 items are PASS/INFO records.

### Cross-Check Notes

1. **WIP:pipeline D1 "CI has no test job"** vs audit: Both A and B focused on the codebase, not CI. The WIP finding is valid but the audit scope did not cover CI workflow analysis. Classified as MISSED_BY_AUDIT (AUDIT-067).

2. **WIP:test-quality B7-01 "test_no_numeric_suffix_collision has no assertion"**: Valid but extremely minor. Audit did not drill to individual assertion quality.

3. **WIP:validation-arch C3 "W550 reused with different semantics"**: Audit A and B both missed this registry inconsistency. Added as AUDIT-038.

### Stale Details

1. **WIP:test-quality B5-01** "Test-to-code LOC ratio is 1.33:1": Uses 17,623 test LOC figure. Ground truth confirms 17,709 LOC. Minor discrepancy, not actionable.

2. **WIP:validation-arch C2** mention of "step_16.py E301-E307": These ARE registered in errors.py per both audit runs. The WIP concern about these specific codes is stale.

### MISSED_BY_AUDIT Details (Added as AUDIT-064 through AUDIT-069)

See AUDIT-064 (cli.py monolithic dispatch), AUDIT-065 (no logging), AUDIT-066 (schema_differ git timeout), AUDIT-067 (no CI pytest job), AUDIT-068 (no property-based testing), AUDIT-069 (conftest fixture session scoping) in the findings above.

---

## Dropped Findings

| Source | Finding | Reason |
|--------|---------|--------|
| A:S10 | Pre-commit hooks use `python -m` instead of entry point | FALSE_POSITIVE: `python -m` is more reliable in pre-commit contexts |
| A:T6 | invariants.py test coverage needs review | FALSE_POSITIVE: B confirmed 35 test functions, well-covered |
| A:SL8 | governance.py is undersized (37 LOC) | FALSE_POSITIVE: observation, not a problem |
| B:H8 | Hardcoded spec field names in validators | FALSE_POSITIVE: acceptable by design; validators are tightly coupled to schema |
| B:G5/G7/G8 | Code health clean, step_08/step_14 DAG consistent | NOT_A_FINDING: positive confirmations, not issues |
| B:T9 | Low integration test count relative to source complexity | EXCLUDED: observation-level concern; integration coverage gap partially addressed by AUDIT-013 and AUDIT-067 |
