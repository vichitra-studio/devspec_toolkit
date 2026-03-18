# Review: Group 2 (P1-B1 + P1-B2)

Reviewed against: `WIP/tool_audit/p0-ground-truth-FINAL.md`
Date: 2026-03-17

---

## p1-prompt-dry-validators.md

### Issues Found

1. **MUST_FIX** -- `_load_fr_ids` count says "5 copies" but lists 6 files (step_05, step_06, step_07, step_08, step_12, step_13a). Line 71 reads: `_load_fr_ids: 5 copies (step_05, step_06, step_07, step_08, step_12, step_13a -- 6 counting step_13a)`. The parenthetical tries to correct itself but the leading number is wrong and the phrasing "6 counting step_13a" implies step_13a was somehow excluded from "5" despite being listed. Ground truth section 4.3 confirms 6 instances. Fix: change to `_load_fr_ids: 6 copies (step_05, step_06, step_07, step_08, step_12, step_13a)`.

2. **MUST_FIX** -- `_load_api_ids` count says "4 copies" but lists 5 files (step_06, step_08, step_11, step_13a, step_15). Ground truth section 4.3 confirms 5 instances. Fix: change to `_load_api_ids: 5 copies (step_06, step_08, step_11, step_13a, step_15)`.

3. **MINOR** -- Line 83 section heading says "from ground truth section 4.5" but the ground truth section for `_load_fr_ids` body comparison is numbered 4.5. This is correct. No issue. (Verified.)

### Clean

- The complete `_load_*` function table (lines 44-68) matches ground truth section 4.3 exactly: all 23 functions, all file names, all line numbers, all signatures.
- All 21 validator file LOC counts match ground truth section 2.1 line by line.
- The `_load_fr_ids` body comparison (lines 86-91) matches ground truth section 4.5 exactly: step_05 inline conditional, step_06 separate guard with `item`/`items` variables, step_07 inline conditional with `set[str] | None` syntax.
- step_14 variant signature difference (`toolkit_root, artifact_path`) is correctly flagged with appropriate warning.
- Grouping of singleton functions (`_load_inv_ids`, `_load_component_ids`, `_load_canonical_stages`, `_load_governance_labels`) is accurate.
- Scope exclusion is unambiguous: "Do NOT audit linters, canonical modules, generation modules, migration modules, or test files."
- Question set (12 questions) is well-scoped and does not leak into P1-B2 territory.
- Output path `WIP/tool_audit/p1-out-dry-validators.md` is distinct from P1-B2's output path.

---

## p1-prompt-dry-soc.md

### Issues Found

4. **SHOULD_FIX** -- `core/trace_types.py` (question 5, line 115) states "imported by 5 validation modules." This is true within P1-B2's scope (cross_artifact_checks, fixtures_lint, hallucination_lint, matrix, traceability_closure), but ground truth section 5.2 shows 4 additional imports from validator files (step_01, step_02, step_10, step_11) -- totaling 9 consumers. The executing agent may conclude trace_types is lightly used and recommend moving it, when in reality it has 9 dependents across the codebase. Fix: add a note like "also imported by 4 validator modules (out of scope for this prompt)."

5. **SHOULD_FIX** -- Layer direction summary (line 104) states `core/ <- canonical/ <- validation/; core/ <- generation/ <- validation/`. This notation implies a strict linear chain where validation depends on canonical, which depends on core. While technically not wrong, it omits that validation depends on core *directly* (not just transitively through canonical). Ground truth section 5.6 is more explicit: "validation/ <- depends on core/, canonical/, generation/". The executing agent could misinterpret the layer model. Fix: rewrite as `core/ <- canonical/; core/ <- generation/; core/, canonical/, generation/ <- validation/; core/, generation/ <- migration/` or use the ground truth's explicit notation.

6. **MINOR** -- The file lists `migration/scripts/strip_generation_quality.py` (66 LOC) in the migration section but does not include `migration/__init__.py` (18 LOC) or `migration/scripts/__init__.py` (0 LOC). This is consistent with P1-B1's approach of omitting `__init__.py` files, but P1-B2's objective includes auditing "separation of concerns" and `migration/__init__.py` has 18 LOC of actual content (not just empty). The executing agent may miss imports or re-exports in that init file. Consider adding it.

7. **MINOR** -- The scope exclusion says "Do NOT assess error flow or error code consistency -- P1-E covers that." and "Do NOT assess registry consistency or CLI wiring -- P1-A covers those." These cross-references to P1-E and P1-A are helpful but the executing agent has no way to verify those prompts exist or what they cover. Not actionable, just a documentation gap.

### Clean

- All LOC counts across all 4 package tables (validation non-validators: 17 files, canonical: 4 files, generation: 3 files, migration: 3 files) match ground truth section 2.1 exactly.
- The complete import graph (lines 68-102) for validation/, canonical/, generation/, and migration/ matches ground truth sections 5.2-5.5 exactly, with the correct exclusion of validator-specific imports (which belong to P1-B1's scope).
- `schema_differ.py` correctly identified as largest module (1331 LOC) per ground truth.
- `cli.py` LOC (757) correctly cited in question 3.
- Scope separation is explicit and non-overlapping with P1-B1: "Do NOT audit validators/*.py -- P1-B1 covers those exclusively."
- Question set (16 questions) is well-structured with clear category groupings (SoC, DRY, Generation, Migration).
- Output path `WIP/tool_audit/p1-out-soc-linters.md` is distinct from P1-B1's output path.
- No hallucinated files, functions, or line numbers detected.

---

## Summary

- Total issues: 7 (MUST_FIX: 2, SHOULD_FIX: 2, MINOR: 3)

| # | File | Severity | Description |
|---|------|----------|-------------|
| 1 | p1-prompt-dry-validators.md | MUST_FIX | `_load_fr_ids` count says 5, should be 6 |
| 2 | p1-prompt-dry-validators.md | MUST_FIX | `_load_api_ids` count says 4, should be 5 |
| 4 | p1-prompt-dry-soc.md | SHOULD_FIX | trace_types import count understated (5 vs 9 total) |
| 5 | p1-prompt-dry-soc.md | SHOULD_FIX | Layer direction notation is imprecise |
| 6 | p1-prompt-dry-soc.md | MINOR | migration/__init__.py (18 LOC) omitted from file list |
| 7 | p1-prompt-dry-soc.md | MINOR | Cross-references to P1-E and P1-A are unverifiable |
| 3 | p1-prompt-dry-validators.md | MINOR | (False alarm -- verified correct) |
