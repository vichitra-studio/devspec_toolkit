# Review: Phase A Context Package — Implementation vs Requirements (Cycle 2)
Topic: toolkit-optimisation-phase-a
Generated: 2026-03-27
Reference: WIP/trans/toolkit_optimisation.txt §7 (Phase A)
Prior cycle: WIP/toolkit-optimisation-phase-a-impl-review-c1.md (16 findings, all addressed)

---

## Summary

- **Total findings: 11** (5 blocking; 6 non-blocking)
- Critical: 0 | High: 2 | Medium: 3 | Low: 0
- By category: Bugs: 2 | Gaps: 2 | Deviations: 2 | Assumptions: 2 | False-Positives: 3
- Files reviewed: 8 (structure.py, scope_resolver.py, extractor.py, canon_extractor.py, freshness.py, reviewer.py, _utils.py, cli.py)
- c1 regressions introduced: 1 (F-101)

---

## High Findings

### F-101 — extractor.py: A4a cache miss path records ALL context keys, not just the current src_step's
- **File**: `tools/specdev_tools/context/extractor.py:374–383`
- **Severity**: high
- **Category**: bug (regression introduced in c1 fix)
- **Reference**: §7 A4a — cache format: `"04": {"00_charter.json": [".goals", ...], "01_capabilities.json": [...]}`
- **Evidence**:
  ```python
  # Line 374: this block is inside 'for src_step in upstream_step_ids:' but
  # 'context' is accumulated across ALL src_steps, not reset per-step.
  if registry is not None and uri and cached_fields is None:
      schema_path = registry.resolve(uri)
      if schema_path:
          discovered: dict[str, list[str]] = {}
          for key in context:      # ← BUG: context includes keys from ALL prev src_steps
              discovered[os.path.basename(spec_path)] = ...
  ```
  When processing src_step "05" (second iteration), `context` already contains keys from src_step "04" (first iteration). The cache entry written for "05" would incorrectly claim that "04"'s keys (e.g., `functional_requirements`) belong to the "05" spec file.
- **Detail**: The cache entry per the spec format should be `{"04": {"00_charter.json": [".goals", ...], "03_glossary.json": [".terms", ...]}}` — mapping upstream spec filenames to their extracted paths. Because `context` is accumulated, the discovered paths for any src_step after the first will include keys from all prior iterations. On subsequent runs, the cache will permit keys from wrong source files, causing cross-step data leakage.
- **Fix**: Track keys added per `src_step` separately. Before the `for key in keys_to_process:` loop, snapshot the existing context keys: `keys_before = set(context.keys())`. After the loop: `new_keys = set(context.keys()) - keys_before`. Then use `new_keys` instead of `context` in the cache-write block.

### F-102 — reviewer.py: `_STEP_SCHEMA_URI_MAP` missing steps 16a/16b/16c; uses hardcoded map instead of `find_step_schema_uri`
- **File**: `tools/specdev_tools/context/reviewer.py:46–66`
- **Severity**: high
- **Category**: gap + deviation
- **Reference**: §3c step 8 — `specdev context review --step NN` for all 22 steps; §4i — `SchemaRegistry` is the primary resolution path.
- **Evidence**:
  ```python
  _STEP_SCHEMA_URI_MAP: dict[str, str] = {
      ...
      "16": "vc:16-impl-context",
      # 16a, 16b, 16c are MISSING
  }
  ```
  Confirmed: `grep '^vc:16' tools/schema_registry.json` returns only `vc:16-impl-context`. Steps 16a, 16b, 16c have no entries in `schema_registry.json` and are not mapped here either. The `_check_scope_completeness` check returns `[]` silently for any step not in this map.

  Additionally, `_utils.find_step_schema_uri` already performs dynamic schema URI lookup (the pattern `vc:{step_id}-`), yet `_check_scope_completeness` duplicates this logic with a static incomplete map that will diverge as schemas evolve.
- **Detail**: Steps 16a (impl planner), 16b (code generator), and 16c (reviewer) are the most common targets of `context review` in Phase B. Their `scope_completeness` check is silently disabled. The existing `find_step_schema_uri` from `_utils.py` already solves this.
- **Fix**: Remove `_STEP_SCHEMA_URI_MAP` entirely. In `_check_scope_completeness`, replace the map lookup with `from .._utils import find_step_schema_uri` and call `schema_uri = find_step_schema_uri(step_id, registry)`. Import `SchemaRegistry` is already present. Additionally, add a fallback: if `schema_uri` is None, attempt to load the artifact's own `$schema` field value as the URI (§7b step 1).

---

## Medium Findings

### F-103 — extractor.py, structure.py, reviewer.py: boilerplate not loaded dynamically from vc:core:step-base (violates §4g)
- **File**: `tools/specdev_tools/context/extractor.py:33–42`, `structure.py:29–40`, `reviewer.py:32–41`
- **Severity**: medium
- **Category**: deviation from locked decision
- **Reference**: §4g — "Boilerplate = vc:core:step-base property keys, loaded dynamically via SchemaRegistry. Self-maintaining: new step-base fields are automatically boilerplate."
- **Evidence**: All three files hardcode an identical 8-key frozenset `{"$schema", "id", "owner", "created_at", "canonical_refs_used", "canonical_proposals", "canonical_conflicts", "_migration_notes"}`. None of them call `SchemaRegistry.load("vc:core:step-base")`.
- **Detail**: The spec's intent is that `_BOILERPLATE_KEYS` is a cache populated once from `vc:core:step-base`. If a 9th field is added to step-base (e.g., `_spec_version`), none of the 3 files will strip it automatically. The `_utils.py` module is the natural place to implement a shared `get_boilerplate_keys(registry)` loader.
- **Fix**: Add `get_boilerplate_keys(registry: SchemaRegistry) -> frozenset[str]` to `_utils.py` that calls `registry.load("vc:core:step-base")["properties"].keys()`, with a hardcoded fallback for when the registry is unavailable. Replace the three hardcoded frozensets with calls to this loader (cached as a module-level variable after first call).

### F-104 — reviewer.py: `_check_quantifier_weakening` over-fires — vague-word check against entire artifact
- **File**: `tools/specdev_tools/context/reviewer.py:570–610`
- **Severity**: medium
- **Category**: bug (high false-positive rate)
- **Reference**: §7 A5 — quantifier_weakening heuristic: "check if target has fast|quick|acceptable|reasonable instead of the number"
- **Evidence**:
  ```python
  artifact_combined = " ".join(artifact_texts)  # entire artifact as one string
  ...
  if not re.search(number + unit, artifact_combined):
      if _VAGUE_PATTERN.search(artifact_combined):  # ANY vague word anywhere
          pairs.append(...)
  ```
  A 500-item spec artifact that has a single `"acceptable latency"` in an unrelated NFR section will trigger this check for EVERY upstream metric (e.g., all 8 metrics from a seed doc). Result: 8 false-positive pairs instead of 0.
- **Detail**: The heuristic needs a proximity constraint: the vague language should appear near where the metric should be, not anywhere in the document. Without this, any nontrivial spec artifact will always produce quantifier_weakening pairs.
- **Fix**: Instead of scanning `artifact_combined`, extract individual text snippets from the artifact that are contextually related to the upstream metric source (e.g., the same array item, or items that reference the same FR). At minimum, add a guard: only flag if the metric appears >0 times in the artifact source (i.e., it was known at authoring time) but is absent AND vague language appears within 200 chars of where the metric should be. As a pragmatic interim fix, increase the vague-pattern check threshold: only trigger if >2 different vague words appear in the artifact (reducing accidental single-word matches).

### F-105 — scope_resolver.py: `_iter_spec_files` recurses into `spec/common/` and picks up seed_manifest.json IDs
- **File**: `tools/specdev_tools/context/scope_resolver.py:62–75`
- **Severity**: medium
- **Category**: bug
- **Reference**: §7 A3 — "Walk spec files to build trace graph" (implied: only step spec files, not metadata files)
- **Evidence**:
  ```python
  for root, _, files in os.walk(spec_dir_abs):  # ← recursive, includes common/
  ```
  `spec/common/seed_manifest.json` contains `{"seed_manifest_id": "seed-manifest-core", "seeds": [{"seed_id": "seed-overview"}, {"seed_id": "seed-tech-stack"}]}`. The BFS graph will register `seed-manifest-core`, `seed-overview`, `seed-tech-stack` as entity IDs. These have no trace edges so BFS won't traverse them, but they pollute `id_to_file` and `resolved_ids`. More critically, if a user passes `--entry seed-overview`, the resolver will return it as a found entity (no `scope_warning`) when it should return an empty result.
- **Fix**: In `_iter_spec_files`, either (a) skip files in subdirectories (`root == spec_dir_abs` only — no recursion), or (b) skip files in `common/` specifically. Option (a) is simpler and matches the spec convention that step files are at the top level of spec_dir.

---

## Pass Confirmations (c1 fixes verified)

- **F-001 (freshness.py seeds list)**: Fixed — `seed_manifest.get("seeds", [])` iteration now correct. ✓ `freshness.py:86–101`
- **F-002 (reviewer.py A5)**: Implemented — all 5 dataclasses, 2-pass review, 5 check types, verdict logic. ✓ `reviewer.py`
- **F-003 (canon_extractor $ref target check)**: Fixed — `_is_canonical_ref_field()` checks `$ref.endswith("#canonicalRef")`. ✓ `canon_extractor.py:49–58`
- **F-004 (scope_resolver calls build_trace_matrix)**: Fixed — best-effort call at start of `resolve_scope()`. ✓ `scope_resolver.py:225–234`
- **F-005 (A4a cache)**: Implemented — `extraction_paths.json` write/read/stale-detect logic present. ✓ `extractor.py:52–124`
- **F-006 (Tier 2 truncation)**: Implemented — threshold 20, `_context_note` header, respects `--full`. ✓ `extractor.py:350–360`
- **F-007 (unknown entry_id warning)**: Fixed — `scope_warning` key added to result. ✓ `scope_resolver.py:246–290`
- **F-008 (_SEED_STEPS rename)**: Fixed — `_POSSIBLE_SEED_STEPS` with explanatory comment. ✓ `structure.py:42–47`
- **F-009 ("step" key extension)**: Documented with comment. ✓ `structure.py:183–185`
- **F-010 (_merge_allof uses to_referencing_registry)**: Fixed — `_utils.merge_allof` uses `ref_registry.contents()` with `registry.load()` fallback. ✓ `_utils.py:55–85`. Verified `referencing.Registry.contents()` exists at runtime.
- **NB-01 (redundant cap- prefix)**: Removed. ✓ `scope_resolver.py:21–32`
- **NB-04/05/06 (shared utils)**: `_utils.py` created; `structure.py`, `extractor.py`, `canon_extractor.py` delegate to it. ✓

---

## Observations (Non-Blocking)

- **NB-07 | medium** | `reviewer.py` line 6 docstring still says "Phase A of the context package" (accurate) but should note it depends on `_utils.find_step_schema_uri` once F-102 is fixed. Minor documentation debt.
- **NB-08 | medium** | `reviewer.py:_check_seed_distillation` and `_check_quantifier_weakening` each define an identical `_extract_text_strings` local function. Extract to a module-level helper to eliminate duplication. `reviewer.py:557–568`, `642–652`
- **NB-09 | medium** | `reviewer.py:_run_structural_pass` accepts `artifact_path` parameter (line 262) but never uses it within the function. Either use it (pass to `_load_upstream_specs`) or remove it. Currently a dead parameter.
- **NB-10 | low** | `structure.py` module docstring (lines 5–7) says "canon_kinds_needed is stubbed as an empty list — it will be populated once canon_extractor.py (Phase A3/A4) exists." This is now stale — canon_extractor.py exists and is called. Update the docstring.
- **NB-11 | low** | `reviewer.py:744` — `top_props` is assigned (`schema.get("properties", {})`) but never used. The fallback block only reads `top_required`. Remove the unused assignment.
- **NB-12 | low** | `reviewer.py:810` — `entry_id` parameter is accepted but not used. Spec says "currently informational" — add `_ = entry_id` or a comment noting the planned future use (scope-filtering the structural pass).

---

## Actionable Fix Plan

### Batch 1 — High bugs (independent)

Task 1:
  file: tools/specdev_tools/context/extractor.py
  mode: modify
  reads: WIP/trans/toolkit_optimisation.txt §7 A4a
  action: Fix F-101: Before the 'for key in keys_to_process:' loop, snapshot existing context keys: `keys_before = set(context.keys())`. After the loop ends (at the same indent as the cache-miss block), compute `new_keys = {k for k in context if k not in keys_before}`. In the cache-write block, replace `for key in context:` with `for key in new_keys:`.
  test_gate: pytest tests/ -x -q
  verify: Cache entry for each src_step only contains keys from that src_step's spec file, not accumulated cross-step keys
  depends_on: none
  parallel_group: 1
  source: F-101

Task 2:
  file: tools/specdev_tools/context/reviewer.py
  mode: modify
  reads: tools/specdev_tools/context/_utils.py, tools/schema_registry.json
  action: Fix F-102: (a) Remove _STEP_SCHEMA_URI_MAP entirely. (b) In _check_scope_completeness, import SchemaRegistry and use find_step_schema_uri from _utils.py instead of the map lookup. (c) Add a fallback: if find_step_schema_uri returns None, try loading artifact["$schema"] directly. (d) Also fix NB-11: remove the unused `top_props` variable on line 744. Fix NB-12: add `_ = entry_id` comment at top of review_artifact.
  test_gate: pytest tests/ -x -q
  verify: `review_artifact("spec/05_interface_contracts.json", "05", "spec", ".")` scope_completeness check finds the schema URI dynamically; review_artifact for step "16a" (if schema exists) no longer silently skips scope_completeness
  depends_on: none
  parallel_group: 1
  source: F-102, NB-11, NB-12

### Batch 2 — Medium bugs (independent)

Task 3:
  file: tools/specdev_tools/context/scope_resolver.py
  mode: modify
  reads: none
  action: Fix F-105: In _iter_spec_files, replace os.walk with os.listdir to avoid recursing into subdirectories. Change the walk to only list files directly in spec_dir_abs: `for fname in os.listdir(spec_dir_abs): if fname.endswith(".json"): full_path = os.path.join(spec_dir_abs, fname)`.
  test_gate: pytest tests/ -x -q
  verify: Resolving a scope no longer registers seed-manifest-core or seed-overview from spec/common/
  depends_on: none
  parallel_group: 2
  source: F-105

Task 4:
  file: tools/specdev_tools/context/_utils.py
  mode: modify
  reads: tools/specdev_tools/core/registry.py, schema/step_base.schema.json
  action: Fix F-103: Add `get_boilerplate_keys(registry: SchemaRegistry) -> frozenset[str]` function that loads vc:core:step-base via registry.load(), extracts its properties keys as a frozenset, and caches the result in a module-level `_boilerplate_keys_cache: frozenset | None = None` variable. Include a hardcoded fallback frozenset for when registry load fails. Update structure.py, extractor.py, and reviewer.py to import and use `get_boilerplate_keys` instead of their hardcoded frozensets.
  test_gate: pytest tests/ -x -q
  verify: `get_boilerplate_keys(SchemaRegistry("."))` returns a frozenset containing at least the known 8 keys
  depends_on: none
  parallel_group: 2
  source: F-103

Task 5:
  file: tools/specdev_tools/context/reviewer.py
  mode: modify
  reads: none
  action: Fix F-104: In _check_quantifier_weakening, replace the single check `if _VAGUE_PATTERN.search(artifact_combined):` with a count-based threshold: `vague_matches = _VAGUE_PATTERN.findall(artifact_combined); if len(set(vague_matches)) >= 2:` — require at least 2 distinct vague words before flagging. Also fix NB-08: extract the shared _extract_text_strings logic to a module-level helper `_extract_all_strings(obj)` and remove the duplicate local definitions in both check functions.
  test_gate: pytest tests/ -x -q
  verify: A spec artifact with a single occurrence of "reasonable" in an unrelated section does not trigger quantifier_weakening pairs
  depends_on: none
  parallel_group: 2
  source: F-104, NB-08

### Batch 3 — Documentation cleanup

Task 6:
  file: tools/specdev_tools/context/structure.py
  mode: modify
  reads: none
  action: Fix NB-10: Update the module docstring (lines 5-7) to remove the stale "canon_kinds_needed is stubbed" note — it is now populated via canon_extractor.py. Fix NB-09: In reviewer.py (wrong file noted above — this is structure.py only), update docstring only.
  test_gate: none
  depends_on: none
  parallel_group: 3
  source: NB-10

---

## Decision Log

*Empty — no findings escalated to human review during this analysis pass.*
