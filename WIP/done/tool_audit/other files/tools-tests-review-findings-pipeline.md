# Findings: AI Pipeline Testing Patterns

SOURCE: T-tools-tests-review-008
AGENT: pipeline-analysis
DATE: 2026-03-11

---

## D1 — Two-tier testing (schema validation vs semantic tests)

FINDING | D1 | GAP | No formal two-tier separation exists between deterministic schema tests and expensive semantic tests | CI runs all linters sequentially in a single `validate` job (.github/workflows/ci.yml:20-82). There are no pytest markers (slow, integration, expensive) defined in pyproject.toml:26-30 or any conftest.py. The `tests/integration/` directory exists with 22 test files but is not gated separately — `testpaths = ["tests"]` (tools/pyproject.toml:27) runs everything in one pass. Integration tests that spawn `subprocess.run` with real git repos (tests/test_forward_replay_check_integration.py:103) run alongside pure-Python unit tests with no marker-based selection. | tests/conftest.py:1-47 | HIGH

FINDING | D1 | GAP | CI workflow has no test job — only runs CLI lint commands | The CI workflow (.github/workflows/ci.yml) runs 14 separate CLI lint/validate commands but never runs `pytest tests/`. The pytest suite and CI validation pipeline are entirely disconnected. Unit tests and integration tests cannot be run independently in CI because they are not invoked at all. | .github/workflows/ci.yml:19-82 | HIGH

## D2 — Property-based fixtures

FINDING | D2 | GAP | No property-based testing or hypothesis usage exists anywhere in the test suite | Zero occurrences of `hypothesis`, `from_schema`, or `property.based` across all 130 JSON fixtures and 52 test files. All fixtures are hand-crafted JSON files following a valid_*/invalid_* naming convention (e.g., tests/fixtures/step_03/ has 9 hand-crafted files, tests/fixtures/step_08/valid/ and tests/fixtures/step_08/invalid/ show the clearest valid/invalid split). Steps with complex schemas (step_03 glossary, step_05 APIs, step_08 fixtures, step_11 redteam) would benefit most from hypothesis-jsonschema auto-generation since their schemas have rich enum constraints, cross-reference rules, and nested object structures. | tests/fixtures/ (130 files across 26 directories) | MEDIUM

## D3 — Token efficiency (external calls, subprocess, mocking)

FINDING | D3 | PARTIAL | Subprocess calls are properly mocked in unit tests but integration tests use real subprocess | Forward-replay unit tests mock subprocess.run via `patch("subprocess.run")` (tests/test_forward_replay_check.py:147,164,181). Submodule validation tests mock subprocess similarly (tests/test_validate_submodule.py:20,29,36). However, integration tests spawn real git repos in temp directories with `subprocess.run(cmd, cwd=root, check=True)` (tests/test_forward_replay_check_integration.py:103) and CLI invocations via `subprocess.run([sys.executable, "-m", ...]` (tests/integration/test_step_04.py:32, tests/integration/test_step_05.py:30, tests/integration/test_step_06.py:35). These are genuinely expensive but appropriately isolated to the integration directory. | tests/test_forward_replay_check.py:147 | MEDIUM

FINDING | D3 | PASS | No external HTTP calls or VCR cassettes needed | Zero occurrences of `vcr`, `cassette`, `responses.activate`, `httpretty`, or `requests_mock` across the test suite. All validation logic operates on local JSON files and schemas — no network calls exist in the validation pipeline. This is a correct design for a schema-first toolkit. | tests/ (all files) | LOW

## D4 — Spec drift detection (layered: fast schema + semantic contract)

FINDING | D4 | PARTIAL | Drift detection exists but is not layered into fast/slow tiers | Schema validation (jsonschema Draft202012Validator in tools/specdev_tools/validation/validate.py:130-138) runs first per-file, then deep validators run per-step (validate.py:376-403), then semantic linters (hallucination, quality, canonical integrity) run in validate_dir (validate.py:207-228). The canon_schema_alignment.py:11-17 provides a declarative enum-drift check (_ENUM_CANON_PAIRINGS). Forward-replay check (validate.py:249-259) adds git-diff-based drift. However, all of this runs in a single monolithic validate_dir call — there is no fast-path that runs only schema validation separate from semantic checks. The CI workflow mirrors this: all checks run sequentially in one job. | tools/specdev_tools/validation/validate.py:180-291 | MEDIUM

FINDING | D4 | PASS | Content derivation overlap check provides semantic drift detection | The hallucination_lint.py:330-401 implements _check_content_derivation which tokenizes downstream artifacts, compares against upstream artifacts using step_order.json DAG, and fires W594 CONTENT_DERIVATION_LOW_OVERLAP when overlap drops below threshold. This is a meaningful semantic drift layer beyond schema validation. | tools/specdev_tools/validation/hallucination_lint.py:330-401 | LOW

## D5 — Declarative rules (Spectral-style YAML vs imperative Python)

FINDING | D5 | GAP | Multiple linters implement pattern-matching rules in imperative Python that could be declarative | The following linters are strong candidates for declarative rule configs: (1) governance.py:24-37 — commit message regex matching against a JSON-stored pattern, already partially declarative via spec/10_governance.json but the check logic is imperative; (2) docs_lint.py:37-119 — README presence checks driven by seed_manifest docs_policy, already config-driven but with imperative traversal; (3) spec_quality_lint.py:9-28 — regex patterns (PLACEHOLDER_RE, VAGUE_QUANTIFIER_RE, STEP_SCHEMA_URI_RE) and field sets (_VAGUE_SCAN_FIELDS, CRITICAL_ARRAY_KEYS) are hardcoded constants that could be YAML rule definitions; (4) hallucination_lint.py:13-23 — KNOWN_STAGES, DEFAULT_COMMAND_PREFIXES, KNOWN_UNITS are hardcoded enum-like sets that could be externalized. The canon_schema_alignment.py:13-17 _ENUM_CANON_PAIRINGS is already partially declarative (list of tuples) and shows the pattern to follow. | tools/specdev_tools/validation/spec_quality_lint.py:9-28 | MEDIUM

FINDING | D5 | PASS | Canon-schema alignment already uses declarative pairing table | canon_schema_alignment.py:11-17 defines _ENUM_CANON_PAIRINGS as a declarative list of (schema_path, json_path, canon_kind) tuples. This is the closest existing pattern to a Spectral-style declarative rule system and could serve as the template for migrating other linters. | tools/specdev_tools/validation/canon_schema_alignment.py:11-17 | LOW

## D6 — Golden file testing (known-good output snapshots)

FINDING | D6 | GAP | No golden file or snapshot testing pattern exists | Zero occurrences of `snapshot`, `golden`, `expected_output`, or `approve` in the test suite. Tests assert against inline expected values or error code patterns (e.g., checking for "E530" or "E520" substrings) rather than comparing against versioned known-good output files. The 130 fixture JSONs serve as test inputs only — there are no corresponding expected-output files stored alongside them. The trace_matrix.json is generated (tools/trace_matrix.json) and uploaded as a CI artifact (.github/workflows/ci.yml:78-82) but never compared against a known-good baseline. This means regressions in linter output format or error message wording go undetected. | tests/ (all files), .github/workflows/ci.yml:78-82 | MEDIUM

---

## Summary

| Criterion | Status | Severity |
|-----------|--------|----------|
| D1 — Two-tier testing | GAP | HIGH |
| D2 — Property-based fixtures | GAP | MEDIUM |
| D3 — Token efficiency | PARTIAL | MEDIUM |
| D4 — Spec drift detection | PARTIAL | MEDIUM |
| D5 — Declarative rules | GAP | MEDIUM |
| D6 — Golden file testing | GAP | MEDIUM |
