# Prompt Review: P1-B2 (p1-prompt-dry-soc.md)

## Claims Verified

| Claim | Source Line | Verified Against | Match? |
|-------|-----------|-----------------|--------|
| validate.py = 537 LOC | Line 22 | `wc -l` | YES |
| _extraction_intent_parser.py = 124 LOC | Line 23 | `wc -l` | YES |
| canon_schema_alignment.py = 128 LOC | Line 24 | `wc -l` | YES |
| cross_artifact_checks.py = 307 LOC | Line 25 | `wc -l` | YES |
| dag_lint.py = 195 LOC | Line 26 | `wc -l` | YES |
| dependency_order_lint.py = 94 LOC | Line 27 | `wc -l` | YES |
| docs_lint.py = 119 LOC | Line 28 | `wc -l` | YES |
| extraction_intent_check.py = 118 LOC | Line 29 | `wc -l` | YES |
| fixtures_lint.py = 109 LOC | Line 30 | `wc -l` | YES |
| forward_replay_check.py = 385 LOC | Line 31 | `wc -l` | YES |
| governance.py = 37 LOC | Line 32 | `wc -l` | YES |
| hallucination_lint.py = 440 LOC | Line 33 | `wc -l` | YES |
| invariants.py = 86 LOC | Line 34 | `wc -l` | YES |
| matrix.py = 353 LOC | Line 35 | `wc -l` | YES |
| seed_lint.py = 310 LOC | Line 36 | `wc -l` | YES |
| spec_quality_lint.py = 257 LOC | Line 37 | `wc -l` | YES |
| traceability_closure.py = 152 LOC | Line 38 | `wc -l` | YES |
| canonical/autofix.py = 397 LOC | Line 44 | `wc -l` | YES |
| canonical/integrity.py = 640 LOC | Line 45 | `wc -l` | YES |
| canonical/lint.py = 472 LOC | Line 46 | `wc -l` | YES |
| canonical/registry.py = 318 LOC | Line 47 | `wc -l` | YES |
| generation/prompt_generator.py = 813 LOC | Line 53 | `wc -l` | YES |
| generation/prompt_schema_sync.py = 501 LOC | Line 54 | `wc -l` | YES |
| generation/schema_differ.py = 1331 LOC | Line 55 | `wc -l` | YES |
| migration/planner.py = 335 LOC | Line 61 | `wc -l` | YES |
| migration/runner.py = 385 LOC | Line 62 | `wc -l` | YES |
| migration/scripts/strip_generation_quality.py = 66 LOC | Line 63 | `wc -l` | YES |
| schema_differ.py is "largest module in entire codebase" | Line 55 | Ground truth section 2.1 (max LOC = 1331) | YES |
| Import: canon_schema_alignment -> canonical.registry | Line 69 | `grep` on actual file | YES |
| Import: cross_artifact_checks -> core.trace_types | Line 70 | `grep` on actual file | YES |
| Import: fixtures_lint -> core.trace_types | Line 71 | `grep` on actual file | YES |
| Import: hallucination_lint -> canonical.lint, canonical.registry, core.trace_types | Lines 72-74 | `grep` on actual file | YES |
| Import: matrix -> core.trace_types | Line 75 | `grep` on actual file | YES |
| Import: traceability_closure -> core.trace_types | Line 76 | `grep` on actual file | YES |
| Import: validate.py -> canonical.integrity, canonical.lint, generation.prompt_schema_sync, core.errors, core.registry | Lines 77-81 | `grep` on actual file | YES |
| Import: canonical/autofix.py -> core.registry.SchemaRegistry | Line 86 | `grep` on actual file | YES |
| Import: canonical/integrity.py -> core.registry.SchemaRegistry | Line 87 | `grep` on actual file | YES |
| Import: canonical/lint.py -> core.registry.SchemaRegistry | Line 88 | `grep` on actual file | YES |
| Import: prompt_generator.py -> core.changelog_parser | Line 93 | `grep` on actual file | YES |
| Import: prompt_schema_sync.py -> core.registry.SchemaRegistry | Line 94 | `grep` on actual file | YES |
| Import: schema_differ.py -> core.changelog_parser | Line 95 | `grep` on actual file | YES |
| Import: planner.py -> generation.schema_differ, core.changelog_parser | Line 100 | `grep` on actual file | YES |
| Import: runner.py -> generation.schema_differ | Line 101 | `grep` on actual file | YES |
| Layer direction: core <- canonical, core <- generation, core/canonical/generation <- validation, core/generation <- migration | Lines 106-109 | Full import analysis | YES |
| "Key cross-cutting import is validate.py -> generation.prompt_schema_sync" | Line 111 | `grep` on validate.py | YES |
| cli.py = 757 LOC | Line 119 | `wc -l` | YES |
| core/trace_types.py = 53 LOC | Line 121 | Ground truth section 2.1 | YES |
| trace_types imported by 5 validation modules | Line 121 | `grep -rl` | YES (cross_artifact_checks, fixtures_lint, hallucination_lint, matrix, traceability_closure) |
| trace_types imported by 4 validator modules | Line 121 | `grep` on validators/ | YES (step_01, step_02, step_10, step_11) |

**All 27 LOC counts verified: 27/27 correct.**
**All import graph edges verified: all correct.**

## Issues Found

### MUST_FIX

**MF-1: Missing critical back-import from generation/ -> validation/ (potential circular dependency)**
`schema_differ.py` (generation/) contains lazy imports back into `validation/`:
- Line 1256: `from ..validation.validate import validate_dir`
- Line 1267: `from ..validation.matrix import validate_trace_integrity`

This creates a dependency path `validation/ -> generation/ -> validation/` (circular at the package level, though deferred at runtime via lazy imports). The prompt's import graph (lines 91-96) lists `generation/ -> core/` only. The layer direction summary (lines 104-110) states generation depends only on core, which is incomplete.

This is a significant SoC concern that the prompt should surface to the agent as known context, especially since question 2 asks about the `validate.py -> generation.prompt_schema_sync` layer violation, but the reverse direction (generation -> validation) is arguably worse and is not mentioned.

**MF-2: prompt_generator.py -> schema_differ import omitted from graph**
`prompt_generator.py` imports from `generation.schema_differ` (line 38 of the source). The prompt's import graph for generation/ (lines 91-96) only shows `prompt_generator.py -> core.changelog_parser`. The intra-package dependency `prompt_generator -> schema_differ` is missing. While this is intra-package, it matters for SoC analysis (question 13 about splitting schema_differ.py).

### SHOULD_FIX

**SF-1: migration/__init__.py (18 LOC) omitted from scope table**
The migration/ table lists 3 files (planner.py, runner.py, strip_generation_quality.py) but omits `migration/__init__.py` (18 LOC), which defines the package's public API via re-exports. This is relevant to SoC analysis since it establishes the contract between migration/ and its consumers. The canonical/ and generation/ `__init__.py` files are trivial (1 LOC each) and their omission is fine, but migration's is non-trivial.

**SF-2: validate.py intra-package imports not shown**
`validate.py` also imports from 6 other validation/ modules (dependency_order_lint, forward_replay_check, extraction_intent_check, hallucination_lint, spec_quality_lint, traceability_closure). While these are intra-package, they're relevant to question 1 ("Is validate.py doing too much?"). Showing these would help the agent understand validate.py's role as an orchestrator.

**SF-3: matrix.py -> cross_artifact_checks import not shown**
`matrix.py` imports from `cross_artifact_checks` (line 7 of matrix.py: `from .cross_artifact_checks import ...`). This intra-package dependency is relevant to question 9 about overlap between these two modules.

**SF-4: runner.py -> planner.py import not shown**
`runner.py` imports from `planner.py` (line 23: `from .planner import MigrationPlan, MigrationStep`). This intra-package dependency is relevant to question 15 about runner.py's responsibilities.

### MINOR

**M-1: File count context could be more explicit**
The prompt lists files per package without stating total counts. For quick reference: validation/ (non-validator) = 17 substantive files + 1 `__init__.py`; canonical/ = 4 + 1; generation/ = 3 + 1; migration/ = 3 + 2 `__init__.py`. Stating these totals would help the agent scope their work.

**M-2: No mention of runner.py lazy import**
`runner.py` has a lazy import at line 132: `from ..generation.schema_differ import MigrationAction`. This is in addition to the top-level import, suggesting some symbols are imported lazily to avoid circular issues.

**M-3: Output limit of 200 lines may be tight for 16 questions across 4 packages**
With 16 questions spanning validation/, canonical/, generation/, and migration/, plus the required finding format and a PASS section, 200 lines is a challenging constraint.

## Verdict: APPROVED_WITH_FIXES

The prompt has excellent factual accuracy -- all 27 LOC counts and all explicitly listed import edges are correct. However, the import graph has two significant omissions (MF-1: schema_differ.py -> validation/ back-imports creating a circular dependency path, and MF-2: prompt_generator -> schema_differ intra-package import). MF-1 in particular is a material gap because it represents a more severe layer violation than the one the prompt asks about in question 2, and an agent running this prompt would miss it unless they discover it independently. After fixing MF-1 and MF-2, the prompt is ready for use.
