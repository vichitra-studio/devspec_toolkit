# Review: Phase A Context Package — Implementation vs Requirements (Cycle 5)
Topic: toolkit-optimisation-phase-a
Generated: 2026-03-27
Reference: WIP/trans/toolkit_optimisation.txt §7 (Phase A)
Prior cycle: WIP/toolkit-optimisation-phase-a-impl-review-c4.md (3 findings, all addressed)

---

## Summary

- **Total findings: 3** (2 blocking; 1 non-blocking)
- Critical: 0 | High: 0 | Medium: 2 | Low: 0
- By category: Bugs: 1 | Gaps: 1 | Deviations: 1 | Inefficiencies: 0
- Files reviewed: 8 (structure.py, scope_resolver.py, extractor.py, canon_extractor.py,
  freshness.py, reviewer.py, _utils.py, cli.py)
- c4 regressions introduced: 0

---

## Medium Findings

### F-501 — structure.py: `_array_counts` leaks boilerplate arrays — §4g violation parallel to F-301
- **File**: `tools/specdev_tools/context/structure.py:69–71`
- **Severity**: medium
- **Category**: bug + deviation from locked decision
- **Reference**: §4g — "Boilerplate = vc:core:step-base property keys, loaded dynamically via
  SchemaRegistry. Self-maintaining: new step-base fields are automatically boilerplate."
- **Evidence**:
  ```python
  # structure.py:69-71
  def _array_counts(data: dict) -> dict[str, int]:
      """Return a mapping of key -> len for every top-level array in *data*."""
      return {k: len(v) for k, v in data.items() if isinstance(v, list)}
  ```
  Verification against `spec/05_interface_contracts.json`:
  ```
  keys  (from _spec_top_level_keys, filtered): ['apis']
  array_counts (from _array_counts, unfiltered):
    {'apis': 3, 'canonical_refs_used': 3, 'canonical_proposals': 0, 'canonical_conflicts': 0}
  ```
  Three boilerplate keys (`canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`)
  appear in `array_counts` but NOT in `keys`. Any spec file that has non-empty
  `canonical_refs_used` (the majority of late-step specs) will emit this inconsistency.
- **Detail**: F-301 (c4) fixed `_spec_top_level_keys` to use `_u_get_boilerplate_keys()`. The
  parallel call `_array_counts(data)` was not updated. In `get_step_structure`, both are called
  on the same `data` dict:
  ```python
  # structure.py:177-179
  entry["keys"] = _spec_top_level_keys(data)    # ← boilerplate excluded ✓
  entry["array_counts"] = _array_counts(data)   # ← boilerplate NOT excluded ✗
  ```
  This means consumers see `canonical_refs_used` in `array_counts` but not in `keys` — the
  §4g self-maintaining invariant is broken for `_array_counts` for the same reason it was
  broken in `_spec_top_level_keys` prior to F-301.
- **Fix**: Apply the same boilerplate filter in `_array_counts`. Minimal change: add a `boilerplate`
  parameter (frozenset, default `None`) and filter the result:
  ```python
  def _array_counts(data: dict, boilerplate: frozenset[str] | None = None) -> dict[str, int]:
      """Return a mapping of key -> len for every top-level array in *data*
      (excluding boilerplate fields)."""
      skip = boilerplate or _u_get_boilerplate_keys()
      return {k: len(v) for k, v in data.items() if isinstance(v, list) and k not in skip}
  ```
  Then update the call site in `get_step_structure` to pass the boilerplate set that is already
  loaded for `_spec_top_level_keys`. Alternatively (smallest change, no caller update needed):
  replace the one-liner body directly with the filter applied:
  ```python
  def _array_counts(data: dict) -> dict[str, int]:
      """Return a mapping of key -> len for every top-level array in *data*
      (excluding boilerplate fields)."""
      skip = _u_get_boilerplate_keys()
      return {k: len(v) for k, v in data.items() if isinstance(v, list) and k not in skip}
  ```
  Either approach is acceptable. The second is a one-line change, consistent with the F-301 fix
  pattern.

---

### F-502 — cli.py: `context freshness` dispatch doesn't emit W595 for stale seeds (Phase A gap)
- **File**: `tools/specdev_tools/cli.py:1485–1488`
- **Severity**: medium
- **Category**: gap
- **Reference**: §7 A6 — "When stale: emit warning W595 (or error if SPECDEV_WARNINGS_AS_ERRORS=1).
  The /specdev-step skill can then prompt Claude to re-index the changed seed sections."
- **Evidence**:
  ```python
  # cli.py:1485-1488
  elif context_cmd == "freshness":
      spec_dir = os.path.abspath(args.spec_dir)
      result = check_freshness(spec_dir, repo_root)
      print(json.dumps(result, indent=2))
  ```
  W595 ("CONTENT_STALENESS") is defined in `tools/specdev_tools/core/errors.py:127` but is
  never emitted by the freshness dispatch. When one or more seeds are stale, the command prints
  the result dict (containing `stale: true`) and exits with code 0 — no warning signal is
  propagated to the caller.
- **Detail**: The spec explicitly assigns W595 emission to Phase A (A6). The `/specdev-step`
  skill (Phase B) is designed to react to this warning. Without the W595 emission, Phase B
  skills consuming the freshness command have no standard mechanism to detect staleness via exit
  code or stderr; they must parse the JSON output themselves, which is fragile and bypasses the
  standard `SPECDEV_WARNINGS_AS_ERRORS` promotion path.
- **Fix**: After `result = check_freshness(spec_dir, repo_root)`, check for stale seeds and
  emit W595 to stderr before printing the JSON. Minimal implementation:
  ```python
  elif context_cmd == "freshness":
      spec_dir = os.path.abspath(args.spec_dir)
      result = check_freshness(spec_dir, repo_root)
      print(json.dumps(result, indent=2))
      # Emit W595 for any stale seed (§A6)
      stale_seeds = [
          sid for sid, info in result.items()
          if isinstance(info, dict) and info.get("stale")
      ]
      if stale_seeds:
          import sys
          from .core.config import get_config
          cfg = get_config()
          warn_or_error = "error" if cfg.warnings_as_errors else "warning"
          for sid in stale_seeds:
              print(
                  f"specdev: {warn_or_error} W595: seed '{sid}' is stale — "
                  "re-index with /specdev-step (CONTENT_STALENESS)",
                  file=sys.stderr,
              )
          if cfg.warnings_as_errors:
              sys.exit(1)
  ```
  The W595 lines go to stderr so they don't corrupt the JSON stdout consumed by scripts.
  The `SPECDEV_WARNINGS_AS_ERRORS` path causes a non-zero exit consistent with existing CLI
  behavior.
  Note: `"status": "no_index"` should not trigger W595 — only `stale: true` dict entries.
  The guard `isinstance(info, dict)` handles the `no_index` case correctly.

---

## Pass Confirmations (c4 fixes verified)

- **F-301 (`structure.py:_spec_top_level_keys`)**: Fixed — `skip = _u_get_boilerplate_keys()`
  returns the 8-key fallback frozenset; all 8 boilerplate keys excluded from `keys` output.
  ✓ `structure.py:65`
- **NB-18 (`reviewer.py` module-level patterns)**: Fixed — `_ACRONYM_PATTERN` and
  `_PROPER_NOUN_PATTERN` compiled at module level (lines 51–52). Both correctly referenced
  inside `_check_seed_distillation` at lines 626–627. ✓ `reviewer.py:51-52`
- **NB-19 (`seed_files` deduplication)**: Fixed — `seen_seed_paths: set[str]` prevents
  duplicate `ReviewPair` entries when `os.path.dirname(spec_dir) == repo_root`.
  ✓ `reviewer.py:604-611`

---

## Observations (Non-Blocking)

- **NB-20 | low** | `freshness.py:128` — `changed_sections` is always `[]`. The spec output
  format shows populated section names (e.g. `["Performance", "Compliance"]`). The code
  comment documents this explicitly: `# section detection not implemented yet`. This is an
  acknowledged incomplete feature. No action required for Phase A correctness; noted as a
  known gap for future implementation.

- **NB-21 | low** | `reviewer.py:690–702` — `_check_scope_completeness` accesses `allOf[1]`
  directly without calling `_u_merge_allof`, deviating from the pattern used in `extractor.py`
  (lines 283–284), `structure.py` (line 99), and `canon_extractor.py` (line 149). The
  deviation is safe today because `allOf[1]` is always an inline schema (no `$ref` to resolve
  in the step-specific branch). However, if any future schema adds a `$ref` in `allOf[1]`,
  `_check_scope_completeness` would silently return zero `required_keys` — a latent regression
  risk. Optional improvement: replace the direct `all_of[1].get("properties", {})` access with
  `_u_merge_allof(schema, registry).get("properties", {})` (already imported in the file via
  `from ._utils import find_step_schema_uri as _u_find_step_schema_uri`, which could be
  extended to import `merge_allof as _u_merge_allof`).

---

## Actionable Fix Plan

### Batch 1 — Bug fix (standalone)

Task 1:
  file: tools/specdev_tools/context/structure.py
  mode: modify
  reads: none
  action: Fix F-501: In `_array_counts`, apply the same boilerplate filter as
    `_spec_top_level_keys`. Replace the function body with:
    `skip = _u_get_boilerplate_keys(); return {k: len(v) for k, v in data.items() if isinstance(v, list) and k not in skip}`.
    No change needed to callers. Docstring update: "excluding boilerplate fields".
  test_gate: pytest tests/ -x -q
  verify: `get_step_structure` output `required_inputs[].array_counts` does not contain
    any of `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`,
    `_migration_notes`. Keys present in `array_counts` are a strict subset of keys
    present in `keys`.
  depends_on: none
  parallel_group: 1
  source: F-501

### Batch 2 — CLI gap (standalone)

Task 2:
  file: tools/specdev_tools/cli.py
  mode: modify
  reads: tools/specdev_tools/core/config.py
  action: Fix F-502: After `print(json.dumps(result, indent=2))` in the `context freshness`
    dispatch branch, add W595 emission for stale seeds. Filter `result` entries to those
    where `isinstance(info, dict) and info.get("stale")`. For each stale seed, print
    `W595: seed '{sid}' is stale — re-index with /specdev-step (CONTENT_STALENESS)` to
    stderr. If `cfg.warnings_as_errors` is True, call `sys.exit(1)`. Guard against the
    `{"status": "no_index"}` response (no stale seeds possible in that case, the
    `isinstance(info, dict)` check handles it since `"no_index"` is a str value).
  test_gate: pytest tests/ -x -q
  verify: Running `specdev context freshness <spec_dir>` with a stale seed prints a line
    matching `W595` to stderr. Running with `SPECDEV_WARNINGS_AS_ERRORS=1` exits non-zero.
    Running with no stale seeds exits zero with no W595 output.
  depends_on: none
  parallel_group: 2
  source: F-502

---

## Decision Log

*Empty — no findings escalated to human review during this analysis pass.*
