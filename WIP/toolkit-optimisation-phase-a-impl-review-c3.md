# Review: Phase A Context Package — Implementation vs Requirements (Cycle 3)
Topic: toolkit-optimisation-phase-a
Generated: 2026-03-27
Reference: WIP/trans/toolkit_optimisation.txt §7 (Phase A)
Prior cycle: WIP/toolkit-optimisation-phase-a-impl-review-c2.md (11 findings, all addressed)

---

## Summary

- **Total findings: 7** (2 blocking; 5 non-blocking)
- Critical: 0 | High: 1 | Medium: 1 | Low: 0
- By category: Bugs: 2 | Gaps: 0 | Deviations: 2 | Inefficiencies: 3
- Files reviewed: 8 (structure.py, scope_resolver.py, extractor.py, canon_extractor.py,
  freshness.py, reviewer.py, _utils.py, cli.py)
- c2 regressions introduced: 0

---

## High Findings

### F-201 — _utils.py: `get_boilerplate_keys` permanently caches fallback on first call (defeats §4g self-maintaining goal)
- **File**: `tools/specdev_tools/context/_utils.py:117–137` and `extractor.py:36`
- **Severity**: high
- **Category**: bug + deviation from locked decision
- **Reference**: §4g — "Boilerplate = vc:core:step-base property keys, loaded dynamically via
  SchemaRegistry. Self-maintaining: new step-base fields are automatically boilerplate."
- **Evidence**:
  ```python
  # _utils.py:125-136
  def get_boilerplate_keys(registry=None):
      global _boilerplate_keys_cache
      if _boilerplate_keys_cache is not None:
          return _boilerplate_keys_cache   # ← early exit on any cached value
      if registry is not None:
          ...  # loads from registry, caches
      _boilerplate_keys_cache = _BOILERPLATE_KEYS_FALLBACK  # ← caches fallback too!
      return _boilerplate_keys_cache

  # extractor.py:36 (module-level, runs at import time):
  _BOILERPLATE_KEYS: frozenset[str] = _u_get_boilerplate_keys()
  # ← no registry at import time → calls get_boilerplate_keys(None) →
  #   sets _boilerplate_keys_cache = _BOILERPLATE_KEYS_FALLBACK
  # All subsequent calls (even with registry) hit the cache early-exit.
  ```
  Verified by runtime test: calling `get_boilerplate_keys(SchemaRegistry('.'))` after module
  import returns the fallback frozenset — the registry argument is ignored because the cache
  is already populated with the fallback.
- **Detail**: The F-103 fix correctly added dynamic loading via `vc:core:step-base`. But the
  module-level call in `extractor.py:36` (`_u_get_boilerplate_keys()` with no registry) runs at
  import time, sets the module-level cache to `_BOILERPLATE_KEYS_FALLBACK`, and permanently
  blocks the registry-backed path. Every subsequent `get_boilerplate_keys(registry)` call from
  `extract_context`, `_output_schema_keys`, `_check_scope_completeness` returns the fallback
  without consulting the registry. Today the fallback matches the actual step-base properties
  (both are the same 8 keys), so there's no current behavioral regression. But the §4g
  "self-maintaining" invariant is broken: if `step_base.schema.json` gains a 9th property,
  the fallback won't update and the new field will not be stripped as boilerplate.
- **Fix**: In `_utils.py`, do NOT cache the fallback path. Only set `_boilerplate_keys_cache`
  when successfully loaded from the registry. Change the final two lines of `get_boilerplate_keys`:
  ```python
  # Don't set _boilerplate_keys_cache here — allow future calls with a registry to populate it.
  return _BOILERPLATE_KEYS_FALLBACK
  ```
  This makes fallback calls stateless (no persistent side-effect) and allows the first call
  with a registry to populate the cache. Additionally, remove the module-level
  `_BOILERPLATE_KEYS: frozenset[str] = _u_get_boilerplate_keys()` line from `extractor.py`
  (line 36) — it serves no purpose since `extract_context` already refreshes `_BOILERPLATE_KEYS`
  at runtime via `global _BOILERPLATE_KEYS; _BOILERPLATE_KEYS = _u_get_boilerplate_keys(registry)`.

---

## Medium Findings

### F-202 — cli.py: `context review` uses `os.path.dirname(artifact_path)` as spec_dir with no override
- **File**: `tools/specdev_tools/cli.py:1501`
- **Severity**: medium
- **Category**: assumption / usability gap
- **Reference**: §7 A7 — `specdev context review <artifact_path> --step <NN> [--entry <id>] [--repo-root .]`
  (no `spec_dir` argument defined in spec)
- **Evidence**:
  ```python
  # cli.py:1497-1505
  artifact_path = os.path.abspath(args.artifact_path)
  result = review_artifact(
      artifact_path,
      args.step,
      os.path.dirname(artifact_path),   # ← spec_dir derived from artifact location
      repo_root,
      entry_id=getattr(args, "entry", None),
  )
  ```
  `review_artifact` needs `spec_dir` to load upstream spec files for Pass 1 (ID coverage) and
  Pass 2 (semantic checks). `os.path.dirname(artifact_path)` assumes the artifact lives in the
  spec directory. Typical usage (`spec/04_fr_list.json`) works correctly. Edge cases fail silently:
  - `specdev context review ./04_fr_list.json --step 04` → spec_dir = "." → no upstream specs found
  - `specdev context review /tmp/staging/04_fr_list.json --step 04` → same failure
  In both cases, `_load_upstream_specs` returns `[]` and the review returns PASS with no
  structural/semantic checks performed (silent false-negative).
- **Fix**: Add a `--spec-dir` optional argument to `ctx_review` parser (defaulting to
  `os.path.dirname(artifact_path)` when absent). In the dispatch block, use
  `getattr(args, 'spec_dir', None) or os.path.dirname(artifact_path)` as spec_dir. This
  maintains backward compatibility for the typical usage pattern while enabling correct
  behavior when artifacts are staged outside spec/.

---

## Pass Confirmations (c2 fixes verified)

- **F-101 (extractor.py cache miss key bug)**: Fixed — `keys_before = set(context.keys())`
  snapshot before inner loop; `new_keys = set(context.keys()) - keys_before` used in cache
  write. ✓ `extractor.py:312, 376`
- **F-102 (reviewer.py hardcoded schema URI map)**: Fixed — `_STEP_SCHEMA_URI_MAP` removed;
  `_u_find_step_schema_uri(step_id, registry)` used dynamically; `$schema` fallback added.
  ✓ `reviewer.py:674-684`
- **F-103 (boilerplate not dynamic)**: F-103 correctly added `get_boilerplate_keys` to `_utils.py`
  and updated all 3 callers. The cache-not-populated-from-fallback bug (F-201) is a
  consequence of the extractor module-level call introduced in the same fix — not a regression
  in the fix's design intent. ✓ `_utils.py:117-137`
- **F-104 (quantifier_weakening over-fires)**: Fixed — `len(set(vague_matches)) >= 2` threshold.
  ✓ `reviewer.py:556-557`
- **F-105 (scope_resolver recurses into spec/common/)**: Fixed — `os.walk` replaced with
  `os.listdir`; `os.path.isfile` check excludes subdirectories. ✓ `scope_resolver.py:61-76`
- **NB-08 (duplicate _extract_text_strings)**: Fixed — `_extract_all_strings` at module level;
  duplicate local functions removed from both check functions. ✓ `reviewer.py:41-52`
- **NB-09 (dead artifact_path param)**: Fixed — `_ = artifact_path` in `_run_structural_pass`.
  ✓ `reviewer.py:249`
- **NB-10 (stale structure.py docstring)**: Fixed — "populated via canon_extractor.extract_canon()".
  ✓ `structure.py:5-7`
- **NB-11 (unused top_props)**: Fixed — `top_props = schema.get(...)` line removed. ✓ `reviewer.py`
- **NB-12 (entry_id undocumented)**: Fixed — `_ = entry_id  # currently informational`. ✓ `reviewer.py:787`

---

## Observations (Non-Blocking)

- **NB-13 | medium** | `reviewer.py:274-275` — `reverse_trace` dict assigns `"scope_creep": unjustified`
  where `unjustified` is the same list object as `"unjustified"`. Python aliasing means mutating
  one mutates both. Should be `"scope_creep": list(unjustified)` (a copy). Comment says
  "same set, aliased per spec" but spec §7 A5 lists them as separate fields. Low risk since
  neither is currently mutated after assignment, but fragile.

- **NB-14 | low** | `cli.py:294,300,308,313,318,325` — `--json` flag is parsed for all context
  subcommands but never read in the dispatch block. All context commands unconditionally output
  JSON (`print(json.dumps(...))`). The flag is dead code. The spec says "--json flag (default
  for context commands)" — the current behavior (always JSON) matches the intent, but the flag
  is misleading. Either remove it or make it conditional.

- **NB-15 | low** | `reviewer.py:530-537` — `_METRIC_PATTERN` and `_VAGUE_PATTERN` are compiled
  with `re.compile()` inside `_check_quantifier_weakening` on every invocation. Move to
  module-level constants (like `_STOPWORDS`) to compile once.

- **NB-16 | low** | `reviewer.py:627-631` — `_COMMON_WORDS` frozenset is rebuilt on every
  iteration of the `for seed_path in seed_files:` loop inside `_check_seed_distillation`.
  Should be a module-level constant.

- **NB-17 | low** | `reviewer.py:251,812` — `_load_upstream_specs(step_id, spec_dir, repo_root)`
  is called once inside `_run_structural_pass` (line 251) and again directly in `review_artifact`
  (line 812). Upstream specs are read from disk twice per `review_artifact` call. Refactor:
  load once in `review_artifact` and pass the list to `_run_structural_pass`.

---

## Actionable Fix Plan

### Batch 1 — High bug (standalone)

Task 1:
  file: tools/specdev_tools/context/_utils.py
  mode: modify
  reads: none
  action: Fix F-201: In `get_boilerplate_keys`, remove `_boilerplate_keys_cache = _BOILERPLATE_KEYS_FALLBACK` and replace with a bare `return _BOILERPLATE_KEYS_FALLBACK` (no assignment). This prevents the fallback from locking the cache. The next call that provides a registry will populate the cache from step-base. Also fix NB-15 and NB-16: move `_METRIC_PATTERN`, `_VAGUE_PATTERN` (from reviewer.py `_check_quantifier_weakening`), and `_COMMON_WORDS` (from `_check_seed_distillation`) to module-level constants in reviewer.py.
  test_gate: pytest tests/ -x -q
  verify: After fix, calling `get_boilerplate_keys()` (no registry) returns fallback without caching; calling `get_boilerplate_keys(SchemaRegistry('.'))` immediately after returns the registry-loaded frozenset and populates cache.
  depends_on: none
  parallel_group: 1
  source: F-201

Task 2:
  file: tools/specdev_tools/context/extractor.py
  mode: modify
  reads: none
  action: Fix F-201 (extractor side): Remove the module-level `_BOILERPLATE_KEYS: frozenset[str] = _u_get_boilerplate_keys()` line (line 36). The module-level variable is still set inside `extract_context` via `global _BOILERPLATE_KEYS; _BOILERPLATE_KEYS = _u_get_boilerplate_keys(registry)`, which is sufficient. Without the import-time call, the cache is no longer poisoned with the fallback.
  test_gate: pytest tests/ -x -q
  verify: `_BOILERPLATE_KEYS` is only set inside `extract_context` function body, not at module load.
  depends_on: none
  parallel_group: 1
  source: F-201

### Batch 2 — Medium gap + remaining non-blocking

Task 3:
  file: tools/specdev_tools/cli.py
  mode: modify
  reads: none
  action: Fix F-202: Add `--spec-dir` optional argument to `ctx_review` parser (default None). In the review dispatch block, compute `spec_dir = os.path.abspath(args.spec_dir) if getattr(args, 'spec_dir', None) else os.path.dirname(artifact_path)`. Also fix NB-14: remove the `--json` / `json_output` argument from all 6 context subparsers since it is dead code (context commands always output JSON unconditionally).
  test_gate: pytest tests/ -x -q
  verify: `specdev context review /some/path/04.json --step 04 --spec-dir spec/` uses "spec/" as spec_dir rather than "/some/path/"
  depends_on: none
  parallel_group: 2
  source: F-202, NB-14

Task 4:
  file: tools/specdev_tools/context/reviewer.py
  mode: modify
  reads: none
  action: Fix NB-13: Change `"scope_creep": unjustified` to `"scope_creep": list(unjustified)` in `_run_structural_pass` reverse_trace dict. Fix NB-17: In `review_artifact`, load upstream_specs once before `_run_structural_pass`, pass it as a parameter to `_run_structural_pass` (add `upstream_specs` parameter), and remove the internal `_load_upstream_specs` call from within `_run_structural_pass`.
  test_gate: pytest tests/ -x -q
  verify: `reverse_trace["unjustified"] is not reverse_trace["scope_creep"]` evaluates True (separate list objects). Upstream specs are only read from disk once per `review_artifact` call.
  depends_on: none
  parallel_group: 2
  source: NB-13, NB-17

---

## Decision Log

*Empty — no findings escalated to human review during this analysis pass.*
