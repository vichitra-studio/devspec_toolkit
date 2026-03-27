# Review: Phase A Context Package — Implementation vs Requirements (Cycle 4)
Topic: toolkit-optimisation-phase-a
Generated: 2026-03-27
Reference: WIP/trans/toolkit_optimisation.txt §7 (Phase A)
Prior cycle: WIP/toolkit-optimisation-phase-a-impl-review-c3.md (7 findings, all addressed)

---

## Summary

- **Total findings: 3** (1 blocking; 2 non-blocking)
- Critical: 0 | High: 0 | Medium: 1 | Low: 0
- By category: Bugs: 1 | Gaps: 0 | Deviations: 1 | Inefficiencies: 1
- Files reviewed: 8 (structure.py, scope_resolver.py, extractor.py, canon_extractor.py,
  freshness.py, reviewer.py, _utils.py, cli.py)
- c3 regressions introduced: 0

---

## Medium Findings

### F-301 — structure.py: `_spec_top_level_keys` hardcoded 4-key skip set violates §4g self-maintaining invariant
- **File**: `tools/specdev_tools/context/structure.py:64–67`
- **Severity**: medium
- **Category**: bug + deviation from locked decision
- **Reference**: §4g — "Boilerplate = vc:core:step-base property keys, loaded dynamically via
  SchemaRegistry. Self-maintaining: new step-base fields are automatically boilerplate."
- **Evidence**:
  ```python
  # structure.py:63-67
  def _spec_top_level_keys(data: dict) -> list[str]:
      """Return the top-level keys of a spec JSON document (excluding meta fields)."""
      skip = {"$schema", "id", "owner", "created_at"}   # ← only 4 of 8 boilerplate keys
      return [k for k in data.keys() if k not in skip]
  ```
  The full boilerplate set from `_BOILERPLATE_KEYS_FALLBACK` in `_utils.py` is 8 keys:
  `$schema`, `id`, `owner`, `created_at`, `canonical_refs_used`, `canonical_proposals`,
  `canonical_conflicts`, `_migration_notes`.
  The missing 4 (`canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`,
  `_migration_notes`) will appear in the `required_inputs[].keys` field of
  `get_step_structure()` output — e.g.:
  ```json
  {"file": "04_fr_list.json", "keys": ["functional_requirements",
    "canonical_refs_used", "canonical_proposals", ...], ...}
  ```
  Consumers (the /specdev-step skill and Claude) see `canonical_refs_used` etc. as available
  data keys and may attempt to ingest them as context, despite the extractor stripping them.
  This also means adding a new step-base field would NOT be automatically excluded —
  the §4g self-maintaining invariant is broken for this function.
- **Detail**: All other callers of `_u_get_boilerplate_keys()` in the context package use it
  correctly (`extractor.py:254`, `structure.py:102` in `_output_schema_keys`,
  `reviewer.py:685`). Only `_spec_top_level_keys` uses a hardcoded partial set, making it
  the single stale caller.
- **Fix**: Refactor `_spec_top_level_keys` to accept an optional `boilerplate` parameter
  (frozenset), falling back to `_u_get_boilerplate_keys()` when not supplied. In
  `get_step_structure`, create the SchemaRegistry before the upstream-steps loop (move the
  try/except from lines 191–195 to before line 163), then pass `_u_get_boilerplate_keys(registry)`
  to `_spec_top_level_keys`. This satisfies §4g for all callers.
  Minimal change if registry creation order is not desired: replace the hardcoded `skip`
  with `_u_get_boilerplate_keys()` (registry=None → returns 8-key fallback, no caching
  side-effect). Either approach is acceptable; the second is smaller.

---

## Pass Confirmations (c3 fixes verified)

- **F-201 (`_utils.py` fallback caches permanently)**: Fixed — `get_boilerplate_keys` returns
  fallback without caching; only registry-loaded value populates `_boilerplate_keys_cache`.
  ✓ `_utils.py:136-137`
- **F-201 (`extractor.py` import-time call)**: Fixed — module-level declaration is
  `_BOILERPLATE_KEYS: frozenset[str] = frozenset()`, not a call to `_u_get_boilerplate_keys()`.
  Cache is never poisoned at import time. ✓ `extractor.py:34`
- **F-202 (`cli.py` spec_dir derivation)**: Fixed — `--spec-dir` arg added to `ctx_review`;
  dispatch uses `os.path.abspath(args.spec_dir) if getattr(args, 'spec_dir', None) else
  os.path.dirname(artifact_path)`. ✓ `cli.py:319,1496`
- **NB-13 (`scope_creep` alias)**: Fixed — `"scope_creep": list(unjustified)` is an
  independent copy. ✓ `reviewer.py:287`
- **NB-14 (dead `--json` flags)**: Fixed — all 6 context subparsers no longer register
  `--json`. ✓ `cli.py:290–320`
- **NB-15 (`_METRIC_PATTERN`, `_VAGUE_PATTERN` inside function)**: Fixed — both compiled
  at module level. ✓ `reviewer.py:39–46`
- **NB-16 (`_COMMON_WORDS` rebuilt per loop iteration)**: Fixed — module-level frozenset.
  ✓ `reviewer.py:47–51`
- **NB-17 (upstream specs read twice)**: Fixed — `_run_structural_pass` accepts
  `upstream_specs: list[tuple[str, dict]]`; `review_artifact` loads once and passes to both
  passes. ✓ `reviewer.py:257–261, 801–808`

---

## Observations (Non-Blocking)

- **NB-18 | low** | `reviewer.py:612–613` — `_ACRONYM_PATTERN` and `_PROPER_NOUN_PATTERN`
  are compiled inside `_check_seed_distillation` on every invocation (`re.compile(…)` inside
  the function body). These were overlooked when NB-15/16 moved `_METRIC_PATTERN`,
  `_VAGUE_PATTERN`, and `_COMMON_WORDS` to module level. Same fix: move both to module-level
  constants.

- **NB-19 | low** | `reviewer.py:603–607` — `seed_files` list is built without deduplication.
  Candidate dirs are `[spec_dir, os.path.dirname(spec_dir), repo_root]`. When `spec_dir` is a
  direct child of `repo_root` (e.g., `spec_dir="/repo/spec"`, `repo_root="/repo"`),
  `os.path.dirname(spec_dir) == repo_root`. A seed file at `repo_root/seed_overview.md` is
  then appended twice, generating two identical `ReviewPair` entries for the same concern.
  Fix: collect candidates into a `set[str]` (de-duplicated by path) before iterating:
  ```python
  seen_paths: set[str] = set()
  for candidate_dir in [spec_dir, os.path.dirname(spec_dir), repo_root]:
      for seed_name in ["seed_overview.md", "seed_tech_stack.md"]:
          seed_path = os.path.join(candidate_dir, seed_name)
          if os.path.isfile(seed_path) and seed_path not in seen_paths:
              seen_paths.add(seed_path)
              seed_files.append(seed_path)
  ```

---

## Actionable Fix Plan

### Batch 1 — Medium bug (standalone)

Task 1:
  file: tools/specdev_tools/context/structure.py
  mode: modify
  reads: none
  action: Fix F-301: Replace the hardcoded `skip = {"$schema", "id", "owner", "created_at"}`
    in `_spec_top_level_keys` with a call to `_u_get_boilerplate_keys()` (no registry arg — the
    8-key fallback is sufficient for display purposes and avoids registry coupling). Change the
    function signature to: `def _spec_top_level_keys(data: dict) -> list[str]:` and replace the
    body: `skip = _u_get_boilerplate_keys(); return [k for k in data.keys() if k not in skip]`.
    No change needed to callers.
  test_gate: pytest tests/ -x -q
  verify: `get_step_structure` output `required_inputs[].keys` does not contain any of
    `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`, `_migration_notes`.
  depends_on: none
  parallel_group: 1
  source: F-301

### Batch 2 — Low non-blocking cleanup

Task 2:
  file: tools/specdev_tools/context/reviewer.py
  mode: modify
  reads: none
  action: Fix NB-18: Move `_ACRONYM_PATTERN = re.compile(r'\b[A-Z]{2,}\b')` and
    `_PROPER_NOUN_PATTERN = re.compile(r'\b[A-Z][a-z]{2,}\b')` from inside
    `_check_seed_distillation` (lines 612–613) to module level (after `_COMMON_WORDS`).
    Fix NB-19: Deduplicate the `seed_files` list in `_check_seed_distillation` by tracking
    seen paths in a local set before appending, to prevent duplicate ReviewPair entries when
    `os.path.dirname(spec_dir) == repo_root`.
  test_gate: pytest tests/ -x -q
  verify: `_ACRONYM_PATTERN` and `_PROPER_NOUN_PATTERN` are defined at module scope, not
    inside the function. `seed_files` contains at most one entry per unique absolute path.
  depends_on: none
  parallel_group: 2
  source: NB-18, NB-19

---

## Decision Log

*Empty — no findings escalated to human review during this analysis pass.*
