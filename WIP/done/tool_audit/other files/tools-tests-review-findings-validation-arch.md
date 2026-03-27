# Validation Architecture Findings

SOURCE: T-tools-tests-review-003
REVIEWED_FILES: tools/specdev_tools/validation/validate.py, tools/specdev_tools/core/errors.py, tools/specdev_tools/validation/hallucination_lint.py, tools/specdev_tools/validation/forward_replay_check.py, tools/specdev_tools/validation/fixtures_lint.py, tools/specdev_tools/validation/seed_lint.py, tools/specdev_tools/validation/spec_quality_lint.py

---

## C1 — Error collection (fail-fast vs collect-all)

FINDING | C1 | INFO | validate.py uses iter_errors (collect-all) for JSON Schema validation | tools/specdev_tools/validation/validate.py:136 | `errors = sorted(v.iter_errors(data_for_validation), key=lambda e: e.path)` — correct collect-all pattern
FINDING | C1 | INFO | step_01.py uses iter_errors (collect-all) for sub-schema validation | tools/specdev_tools/validation/validators/step_01.py:72 | `for err in validator.iter_errors(data_for_validation):` — correct collect-all pattern
FINDING | C1 | INFO | step_02.py uses iter_errors (collect-all) for sub-schema validation | tools/specdev_tools/validation/validators/step_02.py:142 | `for err in validator.iter_errors(data_for_validation):` — correct collect-all pattern
FINDING | C1 | INFO | No validator or linter uses jsonschema validate() (fail-fast) | tools/specdev_tools/validation/ | All schema validation uses iter_errors — grep for `\.validate(` returns zero matches across the validation package
FINDING | C1 | INFO | All linters use list-append pattern for error collection | tools/specdev_tools/validation/hallucination_lint.py:33 | All linters (hallucination_lint, seed_lint, spec_quality_lint, fixtures_lint, forward_replay_check) initialize `errors: list[str] = []` and append errors as discovered — this is functionally collect-all
PASS | C1 | All validators and linters use collect-all error gathering (iter_errors or list-append). No fail-fast jsonschema.validate() calls exist in the validation package.

---

## C2 — Error code registry

FINDING | C2 | INFO | errors.py defines 52 E-codes and 25 W-codes (ERROR_CODES dict has 77 total entries) plus a make_error() factory | tools/specdev_tools/core/errors.py:19-103 | E-codes: E110-E150 (6), E210-E211 (2), E301-E310 (8), E410-E420 (2), E510-E599 (34) = 52. W-codes: W110-W150 (5), W550-W581 (12), W590-W597 (8) = 25. Grand total 77 registered codes.
FINDING | C2 | HIGH | make_error() and SpecError are NEVER used by any validator or linter | tools/specdev_tools/validation/ | grep for `make_error` and `SpecError` across validation/ returns zero matches. All modules construct error strings inline as f-strings, completely bypassing the centralized error registry. The `make_error()` guard (errors.py:139: `if code not in ERROR_CODES: raise ValueError`) is dead code for validation purposes.
FINDING | C2 | HIGH | E141 and E142 are emitted by step_14.py but NOT registered in ERROR_CODES | tools/specdev_tools/validation/validators/step_14.py:79,126 | `f"E142 TECH_STACK_MISMATCH: roadmap uses tech '{name}'..."` (line 79) and `f"E141 TASK_DEPENDENCY_CYCLE: circular dependency..."` (line 126) — neither E141 nor E142 appear anywhere in errors.py ERROR_CODES dict. These are phantom codes that bypass all registry validation.
FINDING | C2 | MODERATE | E310 is registered as PROMPT_SCHEMA_DRIFT but emitted as MISSING_ENUM_PROVENANCE in step_05.py | tools/specdev_tools/validation/validators/step_05.py:27 | `f"E310 MISSING_ENUM_PROVENANCE api '{api_id or i}' has enum values..."` vs errors.py:43 `"E310": "PROMPT_SCHEMA_DRIFT"` — the symbolic name in the registry is different from the name used in emitted messages. These are unrelated semantics sharing one code.
FINDING | C2 | HIGH | All error messages across validation/ are hardcoded f-strings, not sourced from the registry | tools/specdev_tools/validation/ | Every linter and validator constructs error strings like `f"E530 INVENTED_ENUM_OR_ID {rel}:{p}={value}"` directly. The ERROR_CODES registry is decorative — it maps codes to symbolic names but no module references it for message construction. The symbolic-name values (e.g. "UNRESOLVED_INPUT") are never used programmatically.
FINDING | C2 | MODERATE | ~60+ error messages in fixtures_lint.py, seed_lint.py, cross_artifact_checks.py, and step validators carry no error code prefix at all | tools/specdev_tools/validation/fixtures_lint.py:64-108, seed_lint.py:23-301, validators/step_14.py:26-88 | Examples: `f"{fid}: missing targets"`, `f"Missing seed manifest: {manifest_path}"`, `f"Duplicate milestone_id '{mid}' at index {i}"` — unclassified by severity or code.

---

## C3 — Severity system (W/E code consistency)

FINDING | C3 | HIGH | W550 in seed_lint.py has different semantics than W550 in forward_replay_check.py | tools/specdev_tools/validation/seed_lint.py:253 vs tools/specdev_tools/validation/forward_replay_check.py:95 | seed_lint uses `W550 UNDECLARED_SEED` but errors.py:72 registers W550 as `SEMANTIC_COVERAGE_SKIP`. seed_lint reuses the W550 code slot with a completely different meaning, breaking the registry contract.
FINDING | C3 | LOW | W150 in seed_lint.py uses non-standard colon-separated format | tools/specdev_tools/validation/seed_lint.py:84 | `"W150: seed_manifest not provided — skipping prompt seed-section checks"` includes a colon after the code, inconsistent with all other error emissions which use space-separated format `"W150 SEED_MANIFEST_NOT_PROVIDED ..."`.
FINDING | C3 | LOW | forward_replay_check.py hardcodes an E560→W560 severity demotion inline | tools/specdev_tools/validation/forward_replay_check.py:108-110 | `errors.append(err.replace("E560", "W560", 1))` — severity demotion is hardcoded in the linter rather than driven by registry metadata or a central policy.
FINDING | C3 | MODERATE | validate.py silently drops all W-prefixed traceability errors without consulting PROMOTABLE_PAIRS | tools/specdev_tools/validation/validate.py:229 | `failures.extend(e for e in tc_errors if not e.startswith("W"))` — all W-codes from traceability_closure are discarded unconditionally, regardless of whether SPECDEV_WARNINGS_AS_ERRORS is set.
FINDING | C3 | MODERATE | ~60+ messages from fixtures_lint, seed_lint, step validators, cross_artifact_checks, docs_lint, and matrix.py have no code prefix, making severity machine-undetectable | tools/specdev_tools/validation/fixtures_lint.py:64-108 | These messages cannot be filtered, promoted, or counted by severity by any downstream tooling.
FINDING | C3 | INFO | All 52 E-codes and 25 W-codes in the registry carry severity as a prefix character; no ambiguous severity in the registry itself | tools/specdev_tools/core/errors.py:19-103 | The registry-level severity assignment is consistent; the gap is at emission time.

---

## C4 — Layered validation (schema vs semantic vs business)

FINDING | C4 | INFO | validate.py implements clear four-layer separation in validate_file() | tools/specdev_tools/validation/validate.py:86-174 | Layer 1: JSON Schema via `iter_errors` (line 136); Layer 2: deep semantic validation via `_run_deep_validation` (line 156); Layer 3: quality lint (line 161); Layer 4: canonical integrity (line 165). Layers are invoked sequentially and independently.
FINDING | C4 | LOW | step_01.py and step_02.py re-run JSON Schema validation inside deep validator functions | tools/specdev_tools/validation/validators/step_01.py:72 and step_02.py:142 | Both create a new `Draft202012Validator` and call `iter_errors()` inside their respective `validate_step_*()` functions. Since `validate_file()` already ran JSON Schema at the outer layer (line 136), this causes duplicate schema evaluation for steps 01 and 02.
FINDING | C4 | MODERATE | seed_lint.py calls validate_file() (all four layers) from inside the seed linter itself | tools/specdev_tools/validation/seed_lint.py:26 | `schema_errors = validate_file(repo_root, manifest_path)` — the seed linter recursively invokes the full validator (including quality lint and canonical integrity) on the seed manifest. This creates a nested validation call that re-executes all layers for one file.
FINDING | C4 | LOW | Individual step validators mix ID-format business rules with semantic cross-reference lookups in single functions with no internal separation | tools/specdev_tools/validation/validators/step_04.py, step_06.py, step_08.py, step_11.py, step_14.py | ID-format checks (`fr_id` regex), duplicate detection, and cross-artifact ID lookups (capability refs, FR refs, milestone refs) are co-located without layer tagging.
FINDING | C4 | LOW | validate_dir() merges all layer outputs into a single flat list with no layer metadata | tools/specdev_tools/validation/validate.py:180-291 | Outputs from JSON Schema, deep validators, quality lint, canonical integrity, hallucination lint, traceability, forward-replay, prompt-schema sync, and extraction-intent are all concatenated into one `failures: list[str]` without any layer tag or category.

---

## C7 — W-to-E promotion

PASS | C7 | PROMOTABLE_PAIRS is centrally defined in errors.py (lines 110-135) with exactly 18 W-to-E mappings: W550, W560, W561, W562, W563, W571, W572, W573, W580, W581, W150, W590, W591, W592, W593, W594, W595, W597.
PASS | C7 | Promotion logic is centralized exclusively in validate_dir() at validate.py:267-289 — the single location that reads SPECDEV_WARNINGS_AS_ERRORS and SPECDEV_PROMOTE_CODES env vars and applies PROMOTABLE_PAIRS.
FINDING | C7 | INFO | Non-promotable W-codes (W110, W120, W130, W140, W552, W570) are explicitly excluded with rationale comment at errors.py:108-109. W596 is also absent from PROMOTABLE_PAIRS with no documented exclusion rationale | tools/specdev_tools/core/errors.py:108-109,103 | W596 UNDECLARED_UPSTREAM_REF is a registered W-code not in PROMOTABLE_PAIRS; the omission appears intentional but lacks documentation.
FINDING | C7 | LOW | Post-promotion deduplication silently suppresses W-codes that have natural E-code equivalents | tools/specdev_tools/validation/validate.py:286-289 | When neither env var is set, the code removes W-codes whose text matches a corresponding E-code. This undocumented dedup could mask warnings that are legitimately distinct from their E-counterpart.
FINDING | C7 | LOW | validate_file() (single-file path) does not apply promotion, causing env-var semantic divergence | tools/specdev_tools/validation/validate.py:86-178 | When called directly (e.g., from seed_lint.py:26), validate_file() returns raw W-codes even when SPECDEV_WARNINGS_AS_ERRORS is set. Only validate_dir() activates promotion.

---

## E2 — Error message duplication

FINDING | E2 | MODERATE | "Missing seed manifest" / "Failed to read seed manifest" messages are duplicated across seed_lint.py and docs_lint.py | tools/specdev_tools/validation/seed_lint.py:23,34 and tools/specdev_tools/validation/docs_lint.py:15,21 | Identical string templates in two separate modules: `f"Missing seed manifest: {manifest_path}"` and `f"Failed to read seed manifest: {manifest_path} ({e})"`.
FINDING | E2 | MODERATE | "Duplicate {id_type}_id '{id}' at index {i}" pattern appears in 11 step validators with no shared helper | tools/specdev_tools/validation/validators/step_02.py:17, step_03.py:40, step_04.py:25, step_05.py:17, step_06.py:20, step_07.py:35, step_08.py:20, step_12.py:20, step_13.py:21, step_14.py:26, step_16b.py:36 | Each step validator independently constructs its own variant of the duplicate-ID message string. No shared `_check_no_duplicates()` helper exists.
FINDING | E2 | LOW | "Schema Error: {err.message}" template is duplicated in step_01.py and step_02.py | tools/specdev_tools/validation/validators/step_01.py:74 and step_02.py:143 | Identical `errors.append(f"Schema Error: {err.message}")` in both iter_errors loops.
FINDING | E2 | LOW | "Invalid target_date" and "Milestone target_date values are not ordered" messages are duplicated between step_09.py and step_14.py | tools/specdev_tools/validation/validators/step_09.py:24,26 and step_14.py:35,69 | `f"Invalid target_date '{target_date}' in milestone '{milestone_id}'"` and `"Milestone target_date values are not ordered"` — identical strings in both validators.
FINDING | E2 | MODERATE | Stopword sets are duplicated with near-identical content across hallucination_lint.py and forward_replay_check.py | tools/specdev_tools/validation/hallucination_lint.py:294-300 and tools/specdev_tools/validation/forward_replay_check.py:329-335 | `_DERIVATION_STOPWORDS` (24 words) and `_CONTENT_STOPWORDS` (24 words, identical). forward_replay_check.py:337 includes comment "Stopword set aligned with hallucination_lint._DERIVATION_STOPWORDS" — explicitly acknowledged as a copy with no shared constant.
FINDING | E2 | MODERATE | "W590 CROSS_STEP_UPSTREAM_MISSING" prefix string appears independently in 5+ validator files | tools/specdev_tools/validation/hallucination_lint.py:387, validators/step_05.py:35, step_08.py:53, step_09.py:32, step_13a.py:45, step_15.py:68 | Each constructs the identical code+label prefix independently with no shared factory.
FINDING | E2 | MODERATE | "E590 CROSS_STEP_ID_NOT_FOUND" prefix string appears in 4+ validator files | tools/specdev_tools/validation/validators/step_05.py:45, step_08.py:77, step_09.py:44, step_13a.py:61, step_15.py:76 | Same pattern as W590 — no shared factory for cross-step error construction.

---

## E6 — Linter pattern duplication

FINDING | E6 | HIGH | `_iter_json()` is defined identically in hallucination_lint.py and spec_quality_lint.py; fixtures_lint, seed_lint, validate.py inline the same os.walk loop | tools/specdev_tools/validation/hallucination_lint.py:131-135 and spec_quality_lint.py:243-247 | Both define `def _iter_json(spec_dir: str)` with identical 5-line body: `for root, _, files in os.walk(spec_dir): for fn in files: if fn.endswith(".json"): yield`. fixtures_lint.py:34-35, seed_lint.py:138-139 and 275-276, validate.py:193-195 inline the same logic. 5 independent implementations (~50 LOC total extractable to ~10 LOC).
FINDING | E6 | HIGH | `_collect_ids_and_refs()` is duplicated with near-identical logic in hallucination_lint.py and spec_quality_lint.py | tools/specdev_tools/validation/hallucination_lint.py:138-161 and spec_quality_lint.py:215-232 | Both implement recursive traversal collecting IDs (keys ending `_id`) and refs (keys ending `_ref` / `_refs`). hallucination_lint adds handling for `requires` list; spec_quality_lint adds `target_id` in reference context. Different function names (`_collect_ids_and_refs` vs `_collect_ids_and_refs`) but same signature and ~40 LOC of duplicated logic.
FINDING | E6 | HIGH | `_in_ref_context()` / `_is_reference_context()` are duplicated in hallucination_lint.py and spec_quality_lint.py | tools/specdev_tools/validation/hallucination_lint.py:164-167 and spec_quality_lint.py:235-240 | Both check if a JSON path includes context segments like `"trace"`, `"targets"`, `"target_ids"`, `"mitigations"`, `"dependencies"`. Different names, ~8 LOC each.
FINDING | E6 | HIGH | Free-text tokenizer with stopword filtering is implemented 3 times with overlapping but divergent implementations | tools/specdev_tools/validation/hallucination_lint.py:307-312 and forward_replay_check.py:344-372 and seed_lint.py:124-125 | hallucination_lint: regex `[a-z][a-z0-9_-]{3,}` with 24-word stopset; forward_replay: same 24-word stopset (acknowledged copy); seed_lint: regex `[a-z0-9]{4,}` with a different 24-word stopset. Three independent implementations totaling ~50 LOC.
FINDING | E6 | HIGH | Free-text field sets are duplicated across 4 modules with overlapping but non-identical membership | tools/specdev_tools/validation/hallucination_lint.py:201,301 and forward_replay_check.py:338 and spec_quality_lint.py:20 | `_FREE_TEXT_FIELDS` (5 fields: name/description/rationale/justification/definition), `_DERIVATION_FREE_TEXT_FIELDS` (9 fields), `_CONTENT_FREE_TEXT_FIELDS` (9 fields, identical to derivation), `_VAGUE_SCAN_FIELDS` (11 fields, superset). No shared base constant.
FINDING | E6 | MODERATE | JSON load with OSError/JSONDecodeError guard is repeated independently in every file-walking linter | tools/specdev_tools/validation/hallucination_lint.py:59-64, spec_quality_lint.py:39-43, fixtures_lint.py:39-42, seed_lint.py:143-147, forward_replay_check.py:353-355 | Five implementations of the same `try: open+json.load except (OSError, JSONDecodeError)` pattern (~5 LOC each, ~25 LOC total extractable to ~5 LOC).
FINDING | E6 | MODERATE | Content token extraction is duplicated between hallucination_lint._extract_free_text_tokens and forward_replay_check._extract_content_tokens | tools/specdev_tools/validation/hallucination_lint.py:315-327 and forward_replay_check.py:344-372 | Both recursively crawl dicts checking field names against a free-text field set and extract regex tokens. forward_replay_check.py:337 comment confirms "aligned with hallucination_lint._DERIVATION_FREE_TEXT_FIELDS".

### LOC estimate for extractable base patterns

| Pattern | Occurrences | LOC per occurrence | Extractable savings |
|---|---|---|---|
| `_iter_json` / os.walk JSON filter | 5 | ~10 | ~40 LOC |
| JSON load guard | 5 | ~5 | ~20 LOC |
| Free-text tokenizer + stopwords | 3 | ~15-20 | ~40 LOC |
| `_collect_ids_and_refs` traversal | 2 | ~20 | ~20 LOC |
| `_in_ref_context` predicate | 2 | ~8 | ~8 LOC |
| Free-text field set constant | 4 | ~5 | ~15 LOC |
| **Total extractable** | | | **~143 LOC** |

A shared `linter_utils.py` module could consolidate these patterns into ~25 LOC, saving ~118 LOC net.

---

## Summary

| Criterion | Status | Severity | Key Finding |
|---|---|---|---|
| C1 Error collection | PASS | — | iter_errors() used universally (3/3 jsonschema sites); all linters are collect-all |
| C2 Error code registry | FINDING | HIGH | 52 E-codes, 25 W-codes defined; make_error/SpecError completely unused; E141/E142 emitted but unregistered; ~60+ messages have no code prefix |
| C3 Severity system | FINDING | HIGH | W550 code reused with different semantics in seed_lint; ~60+ messages have no machine-readable severity; E→W demotion hardcoded inline; W-codes silently dropped in validate_dir |
| C4 Layered validation | FINDING | LOW | Clean 4-layer orchestration in validate.py; step_01/step_02 duplicate schema validation inside deep validators; seed_lint calls validate_file() recursively |
| C7 W→E promotion | PASS | — | 18 pairs confirmed; promotion centralized in validate_dir(); both env vars handled correctly; minor gap: validate_file() does not apply promotion |
| E2 Message duplication | FINDING | MODERATE | 7 duplicate message categories identified; duplicate-ID pattern across 11 validators; stopword sets explicitly copied with comment |
| E6 Linter pattern duplication | FINDING | HIGH | ~143 LOC of shared infrastructure duplicated across 5 linters; net savings ~118 LOC via shared linter_utils.py |
