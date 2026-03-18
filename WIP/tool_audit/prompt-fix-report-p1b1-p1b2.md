# Fix Report: P1-B1 and P1-B2 Prompt Reviews

## P1-B1 (p1-prompt-dry-validators.md)

### MUST_FIX
None identified by reviewer.

### SHOULD_FIX — All 3 Applied

**SF-1: Missing step_00 exclusion note** — APPLIED
- Added "(note: no `step_00.py` validator exists — Step 00 has no deep validator)" to the file listing header.

**SF-2: Incomplete _load_fr_ids body comparison** — APPLIED
- Added note: "The remaining 3 copies (step_08, step_12, step_13a) are not compared here — question 2 asks you to compare all 6."

**SF-3: step_14 return types not fully specified** — APPLIED
- Added return type detail to step_14 variants entry: "`_load_step09_milestone_ids` returns `tuple[set[str], str | None]` (a tuple), not `Optional[Set[str]]` like the standard loaders."

### MINOR — Skipped
- M-1 (validators `__init__.py` omission): Out of scope for this prompt's exclusive focus.
- M-2 (validators importing from core/): Not relevant to DRY within validators themselves.
- M-3 (200-line limit): Acknowledged but no change needed.

---

## P1-B2 (p1-prompt-dry-soc.md)

### MUST_FIX — Both Applied

**MF-1: Missing circular dependency (schema_differ.py -> validation/)** — APPLIED
- Verified against live codebase:
  - `schema_differ.py:1256`: `from ..validation.validate import validate_dir`
  - `schema_differ.py:1267`: `from ..validation.matrix import validate_trace_integrity`
- Added both lazy imports to the generation/ import graph section.
- Added WARNING block explaining the circular dependency path.
- Updated the layer direction summary to include `generation/ <- validation/` with CIRCULAR annotation.
- Updated the cross-cutting import description to cover both directions.

**MF-2: prompt_generator.py -> schema_differ import omitted** — APPLIED
- Verified against live codebase:
  - `prompt_generator.py:38`: `from .schema_differ import (`
- Added `prompt_generator.py -> generation.schema_differ (intra-package)` to the generation/ import graph.

### SHOULD_FIX — All 4 Applied

**SF-1: migration/__init__.py omitted from scope table** — APPLIED
- Added `migration/__init__.py` (18 LOC) to the migration/ scope table with note about re-exported public API.

**SF-2: validate.py intra-package imports not shown** — APPLIED
- Verified against live codebase (validate.py imports from 6 intra-package modules + validators).
- Added all intra-package imports to the import graph: dependency_order_lint, forward_replay_check, extraction_intent_check, hallucination_lint, spec_quality_lint, traceability_closure, validators.

**SF-3: matrix.py -> cross_artifact_checks import not shown** — APPLIED
- Verified against live codebase: `matrix.py:7`: `from .cross_artifact_checks import ...`
- Added to import graph as intra-package dependency.

**SF-4: runner.py -> planner.py import not shown** — APPLIED
- Verified against live codebase: `runner.py:23`: `from .planner import MigrationPlan, MigrationStep`
- Added to migration/ import graph as intra-package dependency.

### MINOR — Skipped
- M-1 (file count totals): Low value-add.
- M-2 (runner.py lazy import): Edge case, not material.
- M-3 (200-line limit): Acknowledged but no change needed.

---

## Verification Summary

All MUST_FIX and SHOULD_FIX claims were verified against the live codebase before applying:
- `schema_differ.py` lines 1256 and 1267: confirmed lazy imports into validation/
- `prompt_generator.py` line 38: confirmed import from schema_differ
- `runner.py` line 23: confirmed import from planner
- `matrix.py` line 7: confirmed import from cross_artifact_checks
- `validate.py` lines 14-24: confirmed 6 intra-package imports + validators
- `migration/__init__.py`: confirmed 18 LOC with re-exports

Total fixes applied: 9 (0 MUST_FIX + 3 SHOULD_FIX for P1-B1, 2 MUST_FIX + 4 SHOULD_FIX for P1-B2)
