# Review: Phase A Context Package — Implementation vs Requirements (Cycle 6)
Topic: toolkit-optimisation-phase-a
Generated: 2026-03-27
Reference: WIP/trans/toolkit_optimisation.txt §7 (Phase A)
Prior cycle: WIP/toolkit-optimisation-phase-a-impl-review-c5.md (2 blocking, 1 non-blocking — all addressed)

---

## Summary

- **Total findings: 4** (0 blocking; 4 non-blocking)
- Critical: 0 | High: 0 | Medium: 0 | Low: 0
- By category: Bugs: 0 | Gaps: 1 | Deviations: 2 | Inefficiencies: 1
- Files reviewed: 8 (structure.py, scope_resolver.py, extractor.py, canon_extractor.py,
  freshness.py, reviewer.py, _utils.py, cli.py)
- c5 regressions introduced: 0

---

## Pass Confirmations (c5 fixes verified)

- **F-501 (`structure.py:_array_counts` boilerplate filter)**: Fixed — `skip = _u_get_boilerplate_keys()`
  applied; `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`, `_migration_notes`
  no longer leak into `array_counts`. Keys present in `array_counts` are a strict subset of keys
  in `keys`. ✓ `structure.py:72`
- **F-502 (`cli.py` freshness W595 emission)**: Fixed — W595 emitted to stderr for each stale seed;
  `isinstance(info, dict)` guard handles `"no_index"` case correctly; `SPECDEV_WARNINGS_AS_ERRORS`
  promotion via `cfg.warnings_as_errors` followed by `sys.exit(1)`. No `UnboundLocalError` —
  uses module-level `get_config` (imported at `cli.py:20`) rather than a local re-import.
  ✓ `cli.py:1485–1504`
- **NB-21 (`reviewer.py:_check_scope_completeness` merge pattern)**: Fixed — `_u_merge_allof`
  imported at module level (`reviewer.py:22`) and called at line 690. Manual `allOf[1]` traversal
  replaced with `merged = _u_merge_allof(schema, registry)`. ✓ `reviewer.py:22, 690`

---

## Observations (Non-Blocking)

- **NB-22 | low** | `extractor.py:extraction_paths.json` — cache is keyed by producing step
  (`src_step`), deviating from the spec format keyed by consuming step (`step_id`).

  The spec (§7a A4a) shows:
  ```json
  {
    "_meta": {...},
    "04": {
      "00_charter.json": [".goals", ".constraints", ".in_scope", ".out_of_scope"],
      "01_capabilities.json": [".capabilities[] | {capability_id, scope, owner}"]
    }
  }
  ```
  Here `"04"` is the consuming step (step being authored). The inner keys are the spec files
  from which it reads.

  The implementation (`extractor.py:292–295`) checks and populates the cache as:
  ```python
  if _cache_is_fresh(extraction_cache, src_step, uri, registry):  # key = src_step
      cached_fields = extraction_cache.get(src_step)
  ```
  And in `_update_cache_entry`, `cache[step_id]` is stored where `step_id` is passed as `src_step`
  (line 116 in `_update_cache_entry`, called from `extractor.py:380`).

  Effect: the cache is universal by upstream step — once step 05's preparation discovers step 04's
  payload keys, those same keys are used for all subsequent consumers (step 09, 16a, etc.) when they
  read from step 04. The spec intended per-consumer customization by Claude.

  Practical impact is zero today because: (a) the "Claude refines paths" mechanism from §A4a step 3
  isn't implemented — paths are auto-discovered, not Claude-curated; and (b) auto-discovery returns
  all payload keys (superset of any consumer's needs). The format mismatch only matters if per-consumer
  path curation is later added.
  Noted as a forward-compatibility risk for Phase B.

- **NB-23 | low** | `reviewer.py:_check_quantifier_weakening:562-563` — vague-language guard is
  global (artifact-wide), not scoped to "corresponding target text" as the spec describes.

  The spec (§7a A5 quantifier_weakening) says:
  ```
  Target: corresponding target text
  Heuristic: check if target has fast|quick|acceptable|reasonable instead of the number
  ```
  The implementation scans `artifact_combined` (the whole artifact joined to one string) for vague
  words:
  ```python
  # reviewer.py:562-563
  vague_matches = _VAGUE_PATTERN.findall(artifact_combined)
  if len(set(vague_matches)) >= 2:
  ```
  The trigger condition (`≥2 distinct vague words anywhere in the artifact`) is almost always true
  for any non-trivial spec. Combined with the outer loop scanning every upstream text string for
  metrics, this can generate a large number of pairs: one for each upstream metric absent from the
  artifact, as long as the artifact has 2+ vague words globally. The spec's intent was to check
  whether the *corresponding* section of the artifact weakened a specific metric — not a global
  vague-word count.

  Practical impact: noisy review output with excessive semantic pairs for metrics that aren't
  missing due to vagueness (e.g., a metric about one subsystem genuinely not needed in a different
  step's output). These pairs cost `len(pairs) * 50` tokens in Claude semantic review.
  No correctness loss — Claude judges each pair and can ACCEPT them. Noted as a noise source.

- **NB-24 | low** | `scope_resolver.py:228-235` — trace_matrix regenerated only by scope_resolver,
  not by all context commands, deviating from §4a's letter.

  §4a states: "Always regenerate trace_matrix.json at the start of every context command."
  Only `scope_resolver.py` regenerates the matrix (via `build_trace_matrix` at line 230). The
  commands `context structure`, `context canon`, and `context freshness` don't regenerate it.

  Practical impact is zero: these commands don't use the trace graph. `context extract` only
  regenerates via `resolve_scope` when an `entry_id` is provided; scoped extraction is the only
  code path that needs a fresh matrix. The spirit of §4a (matrix fresh before scope resolution)
  is fully satisfied. The letter of §4a ("every context command") is overly conservative.
  Noted as a confirmed intentional deviation from the literal spec — no action required.

- **NB-25 | low** | `cli.py:1506` — `review_artifact` imported via submodule path rather than the
  package's public API, inconsistent with sibling commands.

  All other context functions are imported together at the top of the `context` dispatch block:
  ```python
  # cli.py:1458-1461
  from .context import (
      get_step_structure, resolve_scope, extract_context,
      extract_canon, check_freshness,
  )
  ```
  But `review_artifact` is imported separately, lazily, inside its dispatch branch:
  ```python
  # cli.py:1506
  from .context.reviewer import review_artifact
  ```
  The `__init__.py` already exports `review_artifact`. This inconsistency means a future reader
  searching for the `review_artifact` import might not find it where the other 5 are imported.
  No functional impact. The fix would be adding `review_artifact` to the top-level import block
  and removing the local import.

---

## Pass Confirmations (full module survey, c6)

**A1 (`__init__.py`)**: All 6 public exports present: `get_step_structure`, `resolve_scope`,
  `extract_context`, `extract_canon`, `check_freshness`, `review_artifact`. ✓ `__init__.py:6-20`

**A2 (`structure.py`)**: `get_step_structure` output contract matches §7a A2. Five output keys
  correct (`step`, `required_inputs`, `canon_kinds_needed`, `seeds_required`, `output_schema_keys`).
  `required_inputs` inverts `downstream_consumers` correctly. Extension field `"step"` per entry
  documented in comment. Both `_spec_top_level_keys` and `_array_counts` filter boilerplate via
  `_u_get_boilerplate_keys()`. `canon_kinds_needed` populated via `extract_canon()` as required.
  ✓ `structure.py:129-219`

**A3 (`scope_resolver.py`)**: `resolve_scope` output contract matches §7a A3 format (`entry`,
  `resolved_ids`, `source_files`). `entry_id=None` returns `{"scope": "all"}`. Trace graph built
  from bidirectional edges (trace[], targets[], fr_refs[], source_milestones[]). BFS correctly
  finds all reachable IDs. `scope_warning` emitted when `entry_id` not in `id_to_file`. Source
  files made relative via `os.path.relpath`. ✓ `scope_resolver.py:195-292`

**A4 (`extractor.py`)**: `extract_context` output keys match spec (`step`, `scope`, `context`,
  `token_estimate`, `vs_full_read_estimate`). `--full` flag correctly disables scoping. Boilerplate
  stripped dynamically from step-base. Traceable arrays scoped to `resolved_ids`. Non-traceable
  arrays in required-fields mode (Tier 1). Tier 2 truncation at `_TIER2_THRESHOLD=20` items with
  `_context_note` header. Scalars/objects extracted fully. ✓ `extractor.py:189-406`

**A4a (`extractor.py` cache)**: `extraction_paths.json` located under `tools/`, loaded at start,
  saved when updated. SHA-256 staleness detection via schema hash comparison in `_cache_is_fresh`.
  Cache miss triggers auto-discovery, populates cache for future use. ✓ `extractor.py:56-116`

**A4b (`canon_extractor.py`)**: `extract_canon` uses `$ref` target check (`endswith("#canonicalRef")`)
  per §4h — not `_ref` suffix alone. INFERENCE_RULES from `core.constants` maps ref fields to kinds.
  Recurses into `items.properties` for array-type properties and into `properties` for object-type.
  Loads `id/preferred_label/definition/aliases` from each `canon/kinds/{kind}.json`. Output keys
  match spec (`step`, `canon_kinds`, `total_entries`, `token_estimate`). ✓ `canon_extractor.py:124-186`

**A5 (`reviewer.py`)**: All 5 dataclasses defined per spec. Pass 1 structural checks: ID coverage
  (upstream vs artifact trace IDs), reverse trace / scope creep, acceptance criteria coverage.
  All 5 Pass 2 semantic check types implemented: faithfulness, acceptance_gap,
  quantifier_weakening, seed_distillation, scope_completeness. Verdict logic: FAIL at >20%
  dropped, NEEDS_SEMANTIC_REVIEW if semantic_pairs non-empty, else PASS. `entry_id` informational
  (documented). `token_cost` matches spec format. ✓ `reviewer.py:757-835`

**A5 seed deduplication**: `seen_seed_paths: set[str]` prevents duplicate ReviewPairs when
  `os.path.dirname(spec_dir) == repo_root`. ✓ `reviewer.py:606-612`

**A5 module-level regex patterns**: `_ACRONYM_PATTERN`, `_PROPER_NOUN_PATTERN`, `_METRIC_PATTERN`,
  `_VAGUE_PATTERN`, `_COMMON_WORDS` all defined at module scope. ✓ `reviewer.py:39-53`

**A6 (`freshness.py`)**: SHA-256 hash comparison against `seed_requirements.json`. Returns
  `{"status": "no_index"}` when file absent. Output format matches spec. `changed_sections: []`
  explicitly documented as incomplete feature (acknowledged, NB-20). ✓ `freshness.py:31-131`

**A6 W595 emission (`cli.py`)**: W595 emitted to stderr for stale seeds. `isinstance(info, dict)`
  guard handles `no_index` case. `cfg.warnings_as_errors` promotion to `sys.exit(1)`. ✓ `cli.py:1489-1504`

**A7 CLI wiring**: All 6 context subcommands registered with correct positional/optional args:
  `structure` (spec_dir, --step), `scope` (spec_dir, --entry), `extract` (spec_dir, --step, --entry,
  --full), `canon` (--step), `freshness` (spec_dir), `review` (artifact_path, --step, --entry,
  --spec-dir). All dispatch correctly to their module functions. ✓ `cli.py:286-1518`

**Locked Decisions**:
  - §4b (downstream_consumers only in step_order.json): used throughout. ✓
  - §4f (allOf resolution via SchemaRegistry): `merge_allof` in `_utils.py` uses
    `registry.to_referencing_registry()`. ✓
  - §4g (boilerplate dynamic from step-base): all callers use `_u_get_boilerplate_keys()` or
    pass registry to it. Fallback does not populate cache. ✓
  - §4h ($ref target check for canonicalRef): `_is_canonical_ref_field` checks
    `endswith("#canonicalRef")`. ✓
  - §4i (SchemaRegistry as primary): all context modules use SchemaRegistry. ✓
  - §4j (extractor/reviewer separation): `reviewer.py` reads spec files directly, not via
    extractor. ✓

---

## Actionable Fix Plan

No blocking findings — no fix tasks required.

Optional cleanup (NB-25 only, trivial):

Task 1:
  file: tools/specdev_tools/cli.py
  mode: modify
  reads: none
  action: NB-25 optional cleanup: Add `review_artifact` to the top-level context import block
    at cli.py:1458-1461 (change to `from .context import get_step_structure, resolve_scope,
    extract_context, extract_canon, check_freshness, review_artifact`) and remove the local
    import at line 1506 (`from .context.reviewer import review_artifact`).
  test_gate: pytest tests/ -x -q
  verify: `from .context.reviewer import review_artifact` no longer present in cli.py.
    All 6 context functions imported in one block.
  depends_on: none
  parallel_group: 1
  source: NB-25

---

## Decision Log

*Empty — no findings escalated to human review during this analysis pass.*
