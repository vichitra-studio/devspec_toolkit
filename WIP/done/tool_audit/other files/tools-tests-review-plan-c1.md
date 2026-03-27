# Implementation Plan: Exhaustive audit of tools/ and tests/ directories

Topic: tools-tests-review
Generated: 2026-03-11
Source: WIP/tools-tests-review-goal.md

## Goal

Produce a structured findings report covering structural deficiencies, DRY violations, hardcoded values, redundancy, bugs, gaps, and deviations from industry standards across the devspec_toolkit `tools/` (~53 modules across 5 subpackages, ~13,228 LOC) and `tests/` (73 files, ~17,709 LOC) directories. Output uses the `/vc-review` FINDING format and is consumable by subsequent fix-phase goal docs.

## Scope

- Files to modify: 0 (audit produces new findings files only)
- Files to create: 9 (8 category findings files + 1 consolidated report)
- Estimated tasks: 9
- Parallel groups: 2

## Reference Patterns

- FINDING record format: `FINDING | class | location | severity | category | description | evidence | bucket | tier | status | source | requirement_id | fix`
- PASS record format: `PASS | class | location | category | description | evidence | source | requirement_id`
- Audit criteria: 42 requirements across 6 categories (A1-A9, B1-B8, C1-C7, D1-D6, E1-E6, F1-F6) defined in the goal document
- Codebase structure: tools/specdev_tools/ organized into core/, validation/, generation/, canonical/, migration/ subpackages

## Tasks

### Group 1 — Parallel audit tasks (all independent)

#### T-tools-tests-review-001 — Audit CLI structure, package layout, and dependency management

Task 001:
  file: WIP/tools-tests-review-findings-cli-package.md
  reads: tools/specdev_tools/cli.py, tools/pyproject.toml, tools/setup.py, tools/requirements.txt, tools/specdev_tools/__init__.py, scripts/templates/run_specdev.sh, scripts/init_project.py, scripts/setup_devspec_env.sh, scripts/analyze_schema_usage.py, scripts/generate_fixtures_02a.py
  action: |
    Create a findings file analyzing the CLI and packaging layer against criteria A1, A2, A3, A5, A7.

    **A1 — Command dispatch**: cli.py is 757 LOC with 25 subcommands. Check if all subcommands are defined in a single file. Industry standard is command groups with lazy loading or add_command(), one module per group. Count the number of @cli.command() or @cli.group() decorators. Identify any command grouping structure.

    **A2 — Separation of concerns**: Check if cli.py mixes argument parsing, validation logic, and output formatting. Industry standard is thin CLI layer (parse args) → service layer (orchestration) → domain (pure logic). Identify functions that do more than argument parsing — look for inline validation logic, direct file I/O, or output formatting within click command handlers.

    **A3 — Package layout**: Check if validation/ is flat with 17+ linter modules at the same level. Check if there is a clear core/service/CLI split. Check generation/ (3 modules, 2,646 LOC), canonical/ (4 modules, 1,828 LOC), migration/ (3 modules, 804 LOC) for appropriate organization.

    **A5 — Entry point & wrapper**: Check if run_specdev.sh at scripts/templates/ is a template that self-locates. Check if pyproject.toml defines a console_scripts entry point. Check how init_project.py wires the wrapper to host repos.

    **A7 — Dependency management**: Check requirements.txt for pinned versions. Check if dual setup.py + pyproject.toml configuration is justified. Check for reproducible installs.

    Output each finding as a FINDING record in the `/vc-review` format. Use PASS records for criteria that are satisfied. Include file:line references for all findings.
  verify: |
    1. File WIP/tools-tests-review-findings-cli-package.md exists
    2. Contains FINDING or PASS records for each of A1, A2, A3, A5, A7
    3. All findings include file:line references
    4. Uses correct pipe-delimited FINDING format
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: T-tools-tests-review-001

#### T-tools-tests-review-002 — Audit configuration scatter, environment handling, logging, and imports

Task 002:
  file: WIP/tools-tests-review-findings-config-imports.md
  reads: tools/specdev_tools/__init__.py, tools/specdev_tools/core/errors.py, tools/specdev_tools/cli.py, tools/specdev_tools/validation/validate.py
  action: |
    Create a findings file analyzing configuration, environment, logging, and import patterns against criteria A4, A6, A8, A9, E3, F6.

    **A4 & E3 — Configuration centralization**: grep across all files in tools/specdev_tools/ for `os.getenv` calls. Count occurrences per file. Industry standard is all env vars read in one config module. List every SPECDEV_* env var and where it's read.

    **A6 — Import hygiene**: Read tools/specdev_tools/__init__.py. Count re-exports and deprecation warnings. Check for circular import risks — look for cross-package imports (e.g., validation importing from generation). Check if lazy imports are used for performance.

    **A8 — Error handling & propagation**: Check tools/specdev_tools/core/errors.py for custom exception hierarchy. grep across validators and linters for try/except patterns. Check if exceptions are caught and re-raised consistently. Trace error propagation from validators through validate.py to cli.py.

    **A9 — Logging**: grep across tools/specdev_tools/ for `print(` calls and `import logging` / `logging.` usage. Count per file. Industry standard is logging module with configurable levels, not scattered print().

    **F6 — Environment assumptions**: grep for code that assumes CI environment, git repo presence, or venv activation without runtime checking. Look for bare subprocess calls to git, unchecked os.path assumptions.

    Output each finding as a FINDING or PASS record. Include file:line references.
  verify: |
    1. File WIP/tools-tests-review-findings-config-imports.md exists
    2. Contains FINDING or PASS records for each of A4, A6, A8, A9, E3, F6
    3. os.getenv() scatter is quantified with per-file counts
    4. print() vs logging usage is quantified with per-file counts
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: T-tools-tests-review-002

#### T-tools-tests-review-003 — Audit validation architecture, error system, and linter patterns

Task 003:
  file: WIP/tools-tests-review-findings-validation-arch.md
  reads: tools/specdev_tools/validation/validate.py, tools/specdev_tools/core/errors.py, tools/specdev_tools/validation/hallucination_lint.py, tools/specdev_tools/validation/forward_replay_check.py, tools/specdev_tools/validation/fixtures_lint.py, tools/specdev_tools/validation/seed_lint.py, tools/specdev_tools/validation/spec_quality_lint.py
  action: |
    Create a findings file analyzing validation architecture and error system against criteria C1, C2, C3, C4, C7, E2, E6.

    **C1 — Error collection**: Check each validator and linter for use of jsonschema `validate()` (fail-fast) vs `iter_errors()` (collect-all). Industry standard is collect-all universal (ruff, ESLint, pylint, mypy). List which modules use which pattern. Check validate.py (537 LOC) for orchestration approach.

    **C2 — Error code registry**: Read core/errors.py (186 LOC). Count total E-codes and W-codes. Check if all error messages are defined centrally. grep across validation/ for hardcoded error message strings that bypass the registry.

    **C3 — Severity system**: Check W/E code consistency. Identify any codes without clear severity assignment. Check if severity is consistently applied across all validators.

    **C4 — Layered validation**: Check if schema validation (JSON Schema), semantic validation (cross-reference checks), and business rules are clearly separated or mixed within individual validators.

    **C7 — W→E promotion**: Check PROMOTABLE_PAIRS in errors.py. Verify all 18 pairs are defined. Check if promotion logic is centralized or scattered across modules. Verify SPECDEV_WARNINGS_AS_ERRORS and SPECDEV_PROMOTE_CODES handling.

    **E2 — Error message duplication**: grep for common error message substrings across validation/ modules. Identify string literals that appear in multiple files.

    **E6 — Linter pattern duplication**: Compare hallucination_lint.py (440 LOC), forward_replay_check.py (385 LOC), seed_lint.py (310 LOC), spec_quality_lint.py (257 LOC), fixtures_lint.py (109 LOC) for shared patterns: file walking, error collection, reporting structure. Identify extractable base patterns.

    Output each finding as a FINDING or PASS record. Include file:line references.
  verify: |
    1. File WIP/tools-tests-review-findings-validation-arch.md exists
    2. Contains FINDING or PASS records for each of C1, C2, C3, C4, C7, E2, E6
    3. Error code counts are specific (N E-codes, M W-codes)
    4. Linter comparison identifies concrete shared patterns with LOC estimates
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: T-tools-tests-review-003

#### T-tools-tests-review-004 — Audit cross-step validator DRY and schema loading duplication

Task 004:
  file: WIP/tools-tests-review-findings-validators-dry.md
  reads: tools/specdev_tools/validation/validators/step_01.py, tools/specdev_tools/validation/validators/step_02.py, tools/specdev_tools/validation/validators/step_02a.py, tools/specdev_tools/validation/validators/step_03.py, tools/specdev_tools/validation/validators/step_04.py, tools/specdev_tools/validation/validators/step_05.py, tools/specdev_tools/validation/validators/step_06.py, tools/specdev_tools/validation/validators/step_07.py, tools/specdev_tools/validation/validators/step_08.py, tools/specdev_tools/validation/validators/step_09.py, tools/specdev_tools/validation/validators/step_10.py, tools/specdev_tools/validation/validators/step_11.py, tools/specdev_tools/validation/validators/step_12.py, tools/specdev_tools/validation/validators/step_13.py, tools/specdev_tools/validation/validators/step_13a.py, tools/specdev_tools/validation/validators/step_14.py, tools/specdev_tools/validation/validators/step_15.py, tools/specdev_tools/validation/validators/step_16.py, tools/specdev_tools/validation/validators/step_16a.py, tools/specdev_tools/validation/validators/step_16b.py, tools/specdev_tools/validation/validators/step_16c.py, tools/specdev_tools/core/registry.py
  action: |
    Create a findings file analyzing cross-step validator duplication against criteria C5, C6, E1, E5.

    **C5 & E1 — Cross-step ID resolution duplication**: Read all 21 step validators in tools/specdev_tools/validation/validators/. For each validator that loads upstream spec files to extract IDs (e.g., loading step_04 FRs to validate step_05 API refs), identify the specific code pattern used. Count how many validators independently implement `load spec → extract IDs` logic. Quantify duplicated LOC. Industry standard is a shared utility for upstream ID resolution.

    **C6 — Determinism**: Check if any validator output depends on execution order, file system traversal order, or environment variables in a way that could produce non-deterministic results. Look for dict iteration without sorting, glob without sort, set operations that affect output order.

    **E5 — Schema loading duplication**: Check if multiple modules load JSON schemas independently (direct file reads, json.load) vs through core/registry.py (85 LOC). Count modules that bypass the registry.

    For the ID resolution analysis, read each step validator and extract the specific lines that perform upstream spec loading. Create a comparison table showing the pattern in each validator.

    Output each finding as a FINDING or PASS record. Include file:line references for every duplicated pattern instance.
  verify: |
    1. File WIP/tools-tests-review-findings-validators-dry.md exists
    2. Contains FINDING or PASS records for each of C5, C6, E1, E5
    3. ID resolution comparison covers all validators that perform cross-step lookups
    4. Duplicated LOC is quantified
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: T-tools-tests-review-004

#### T-tools-tests-review-005 — Audit hardcoded values, magic numbers, and hallucinated references

Task 005:
  file: WIP/tools-tests-review-findings-hardcoded.md
  reads: tools/specdev_tools/cli.py, tools/specdev_tools/validation/validate.py, tools/specdev_tools/generation/schema_differ.py, tools/step_order.json, tools/schema_registry.json
  action: |
    Create a findings file analyzing hardcoded values and assumptions against criteria F1, F2, F3, F4, F5.

    **F1 — Magic numbers**: grep across tools/specdev_tools/ for numeric literals. Focus on step counts (e.g., hardcoded 22, 17, 16), threshold values, array size assumptions. Distinguish intentional constants from problematic magic numbers. Check schema_differ.py (1,331 LOC — largest module) closely.

    **F2 — Path assumptions**: grep for hardcoded paths that would break in different deployment contexts. Look for absolute paths, paths that assume toolkit is at a specific location, paths that don't use --repo-root resolution. Check scripts/ for path assumptions in init_project.py (438 LOC).

    **F3 — Schema URI assumptions**: Check if schema URIs are hardcoded as strings vs resolved through schema_registry.json. grep for `$schema` string literals in tools/ code. Verify that schema references use the registry.

    **F4 — Step ordering assumptions**: Find code that assumes step order (e.g., hardcoded step lists, numeric comparisons of step numbers) instead of reading step_order.json. Check cli.py and validate.py for step enumeration patterns.

    **F5 — Hallucinated references**: Cross-check IDs, field names, and enum values used in tools/ and tests/ against actual schema definitions in schema/. Look for references to IDs that don't exist, field names not in schemas, enum values not in allowed lists. Note: some R1-R9 additions may be intentional — flag but note the distinction.

    Output each finding as a FINDING or PASS record. Include file:line references.
  verify: |
    1. File WIP/tools-tests-review-findings-hardcoded.md exists
    2. Contains FINDING or PASS records for each of F1, F2, F3, F4, F5
    3. Magic numbers are categorized as intentional vs problematic
    4. Path assumptions include deployment context analysis
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: T-tools-tests-review-005

#### T-tools-tests-review-006 — Audit test structure, R9 duplication, markers, and spec/ references

Task 006:
  file: WIP/tools-tests-review-findings-test-structure.md
  reads: tests/conftest.py, tests/integration/conftest.py, tests/test_r9_validate.py, tests/test_r9_cross_step.py
  action: |
    Create a findings file analyzing test structure and organization against criteria B1, B2, B6, B8, E4.

    **B1 — Directory structure**: List all files in tests/ root (count) and tests/integration/ (count). Check if the test directory is flat with 50+ files at root level. Industry standard is nested by type then feature: tests/unit/, tests/integration/. Identify any subdirectory organization beyond integration/.

    **B2 — R9 test duplication**: Identify all test_r9_*.py files (discover via grep/glob — there may be more than the two listed in reads). For each, find the corresponding non-R9 test file (e.g., test_r9_validate.py → test_validate.py). Compare: do R9 files add unique assertions not present in the base file, or do they duplicate existing tests? Quantify: how many test functions are truly unique vs duplicated? Recommend merge or keep for each pair. Note: also discover and read all test_r9_*.py files via grep/glob beyond those listed in reads.

    **B6 — Test markers**: grep across tests/ for @pytest.mark usage. Check if @pytest.mark.unit, @pytest.mark.integration, or other markers exist for CI tiering. Can fast unit tests be run separately from slow integration tests?

    **B8 — spec/ as test data**: grep across tests/ for references to `spec/` directory (imports, file paths, fixture loading). List every test file that references spec/ directly. Identify what would break if spec/ contents were relocated to tests/fixtures/. Check if spec/ contains only test artifacts (05_interface_contracts.json, .gitkeep, common/seed_manifest.json).

    **E4 — Test helper duplication**: Check conftest.py hierarchy (root + integration). Identify helper functions, fixtures, and utilities. grep across test files for duplicated helper patterns (e.g., repeated fixture loading, common assertion helpers) that could be extracted to conftest.

    Output each finding as a FINDING or PASS record. Include file:line references.
  verify: |
    1. File WIP/tools-tests-review-findings-test-structure.md exists
    2. Contains FINDING or PASS records for each of B1, B2, B6, B8, E4
    3. R9 duplication analysis covers every test_r9_*.py file with specific comparison
    4. spec/ references are enumerated with breakage analysis
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: T-tools-tests-review-006

#### T-tools-tests-review-007 — Audit test quality and fixture management

Task 007:
  file: WIP/tools-tests-review-findings-test-quality.md
  reads: tests/conftest.py, tests/test_validate.py, tests/test_canonical_integrity.py, tests/test_hallucination_lint.py, tests/test_seed_lint.py
  action: |
    Create a findings file analyzing test quality and fixture management against criteria B3, B4, B5, B7.

    **Note**: The declared reads above are representative starting points. The agent must also grep/glob across all of tests/ beyond these declared reads to discover parametrization patterns, coverage gaps, and assertion quality issues. Do not limit analysis to the listed files.

    **B3 — Parametrization**: grep across tests/ for `def test_` functions. Identify clusters of similar test functions that test valid/invalid variants of the same feature and could be consolidated into a single @pytest.mark.parametrize function. Quantify: how many test functions could be reduced through parametrization?

    **B4 — Fixture management**: Read tests/conftest.py. Check fixture scopes (session, module, function). Check if expensive operations (loading JSON files, parsing schemas) use session or module scope. Check if fixtures/ (~130 JSON files) are loaded efficiently. Check conftest hierarchy (root + integration).

    **B5 — Test-to-code ratio**: Current ratio is ~1.3:1 (830 tests for ~14,087 LOC). Identify which test files have the highest test density. Identify which tools/ modules lack corresponding tests. Flag truly redundant tests (same assertion, same code path, different test name).

    **B7 — Assertion quality**: Scan test files for tests with no assertions (missing assert), tests that only check `is not None`, and tests with overly broad assertions (e.g., `assert isinstance(result, dict)` without checking contents).

    Output each finding as a FINDING or PASS record. Include file:line references.
  verify: |
    1. File WIP/tools-tests-review-findings-test-quality.md exists
    2. Contains FINDING or PASS records for each of B3, B4, B5, B7
    3. Parametrization opportunities are quantified
    4. Test-to-code ratio analysis identifies specific coverage gaps
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: T-tools-tests-review-007

#### T-tools-tests-review-008 — Audit AI pipeline testing patterns

Task 008:
  file: WIP/tools-tests-review-findings-pipeline.md
  reads: tests/conftest.py, tests/test_validate.py, tests/integration/conftest.py, tools/specdev_tools/validation/fixtures_lint.py, tools/specdev_tools/validation/hallucination_lint.py
  action: |
    Create a findings file analyzing AI pipeline testing patterns against criteria D1, D2, D3, D4, D5, D6.

    **Note**: The declared reads above are representative starting points. The agent must also grep/glob across all of tests/ and tools/specdev_tools/validation/ beyond declared reads to discover tier separation, expensive tests, and golden file patterns. Do not limit analysis to the listed files.

    **D1 — Two-tier testing**: Check if schema validation tests (deterministic, every commit) and semantic tests (expensive, real cost) are separated. Can they run independently?

    **D2 — Property-based fixtures**: Evaluate whether hand-crafted fixtures (~130 JSON files) could be supplemented with hypothesis-jsonschema for auto-generated valid/invalid instances. Identify which fixture directories are most amenable.

    **D3 — Token efficiency**: Check for tests that make external calls, spawn subprocesses, or are unnecessarily expensive. Check for VCR cassettes or mocking patterns.

    **D4 — Spec drift detection**: Check if drift detection is layered (schema validation fast + contract testing semantic).

    **D5 — Declarative rules**: Evaluate which Python linters in validation/ could be expressed as declarative rule configs (Spectral-style YAML) instead of imperative Python.

    **D6 — Golden file testing**: Check for regression tests with known-good output snapshots (versioned input/output pairs).

    Output each finding as a FINDING or PASS record. Include file:line references.
  verify: |
    1. File WIP/tools-tests-review-findings-pipeline.md exists
    2. Contains FINDING or PASS records for each of D1, D2, D3, D4, D5, D6
    3. Property-based fixture analysis identifies specific amenable directories
    4. Token efficiency analysis identifies specific expensive tests
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: T-tools-tests-review-008

### Group 2 — Report assembly (depends on all Group 1 tasks)

#### T-tools-tests-review-009 — Assemble consolidated findings report

Task 009:
  file: WIP/tools-tests-review-review-c1.md
  reads: WIP/tools-tests-review-findings-cli-package.md, WIP/tools-tests-review-findings-config-imports.md, WIP/tools-tests-review-findings-validation-arch.md, WIP/tools-tests-review-findings-validators-dry.md, WIP/tools-tests-review-findings-hardcoded.md, WIP/tools-tests-review-findings-test-structure.md, WIP/tools-tests-review-findings-test-quality.md, WIP/tools-tests-review-findings-pipeline.md
  action: |
    Create the consolidated findings report by reading all 8 category findings files and merging them into a single structured document.

    The report must follow this structure:

    1. **Header**: Title, topic, date, source goal doc, audit scope summary
    2. **Executive Summary**: Total finding counts by severity (critical/high/medium/low) and by category (A-F). Key themes. Top 5 most impactful findings.
    3. **Critical Findings**: All critical and high severity findings, organized by theme (not by original category letter). Each finding in full FINDING record format.
    4. **All Findings**: Complete listing of every FINDING and PASS record from all 8 files, organized by category (A through F). Deduplicate any findings that overlap across audit domains (same file:line, same issue). Preserve the original requirement_id (A1, B2, etc.) in each record.
    5. **Actionable Fix Plan**: Group findings into recommended fix phases based on dependency order and impact. Phase 1: quick wins (hardcoded values, magic numbers). Phase 2: DRY refactoring (validator dedup, linter patterns). Phase 3: structural changes (CLI split, test reorganization). Phase 4: advanced improvements (property-based testing, declarative rules).
    6. **Observations**: Patterns noted during audit that are informational, not actionable findings.
    7. **Decision Log**: Empty (no prior decisions).

    When merging, preserve all file:line references from the source findings. Do not summarize or lose specificity. The report must be directly consumable by a subsequent /vc-plan invocation for the fix phase.
  verify: |
    1. File WIP/tools-tests-review-review-c1.md exists
    2. Contains Executive Summary with severity counts
    3. Every requirement_id (A1-A9, B1-B8, C1-C7, D1-D6, E1-E6, F1-F6) has at least one FINDING or PASS record
    4. Actionable Fix Plan section exists with phased grouping
    5. All file:line references from source findings are preserved
  test_gate: none
  depends_on: 1, 2, 3, 4, 5, 6, 7, 8
  parallel_group: 2
  source: T-tools-tests-review-009

## Test Strategy

- Per-task gates: none (audit produces findings documents, not code changes)
- Full suite: `pytest tests/` (830 tests collected — audit should not break any)
- Expected test count after implementation: 830 (unchanged — no code modifications in this phase)

## Risks & Assumptions

1. **Scope per agent**: Each audit task covers 5-10 criteria and reads 5-15 source files. Agents may need to grep broadly across directories beyond the explicit reads list to fully satisfy criteria (e.g., E3 requires grepping all modules for os.getenv).
2. **R9 test comparison depth**: Task 006 (B2) requires comparing test_r9_*.py with base test files function-by-function. If the comparison is too shallow, some duplication may be missed. The goal doc notes 10 R9 test files.
3. **Hallucination detection scope** (F5): Cross-checking IDs against schemas requires reading schema/ directory files not explicitly listed in reads. Agents should read schema_registry.json to discover relevant schemas.
4. **Intentional vs accidental hardcoding**: The goal doc warns that some hardcoded values are intentional R1-R9 design decisions. Agents should flag all instances but distinguish bugs from deliberate choices based on surrounding context (comments, variable names, proximity to configuration).
5. **Generation/canonical modules**: The goal doc lists generation/ and canonical/ in scope but no specific audit criteria target them individually. They are covered indirectly through A3 (package layout), E5 (schema loading), and E6 (linter patterns). A dedicated generation/canonical audit task was omitted to stay within scope — add one if coverage proves insufficient.
6. **No test runner configured for findings**: Audit tasks produce markdown documents. There is no automated way to verify findings quality beyond structural checks in verify: fields.
7. **Single-phase justification**: 9 tasks exceeds the >8 mandatory threshold. All 8 audit tasks follow the same uniform pattern (read source → analyze → write findings) and are fully independent. Per the loop-determinism guard for uniform tasks, single-phase is correct — splitting would create unnecessary coordination overhead with no determinism benefit since every task produces a structurally identical findings document.
8. **tools/context/ empty directory**: The goal doc mentions this as a possible incomplete feature or dead code. No specific criterion targets it, but it should be noted in findings if discovered during audit.

## Observations

1 | low | Scope parenthetical described as "7+1 split" instead of "8 category findings" — cosmetic, fixed in this cycle
2 | medium | Tasks 002, 006, 007, 008 have reads fields narrower than their action scope; agents must grep/glob beyond declared reads (Risk 1 applies)
3 | low | No task explicitly audits tools/context/ empty directory — noted in Risk 8; agents should flag if encountered
4 | low | tools/command_prefixes.json not in any task's reads field — covered implicitly by A1 CLI structure audit
5 | low | spec/ artifact relocation documentation (goal line 21) partially covered by B8 in Task 006; full relocation deferred to Phase 2

## Decision Log
