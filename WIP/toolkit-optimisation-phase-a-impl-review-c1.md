# Review: Phase A Context Package — Implementation vs Requirements
Topic: toolkit-optimisation-phase-a
Generated: 2026-03-27
Reference: WIP/trans/toolkit_optimisation.txt §7 (Phase A)

---

## Summary

- **Total findings: 16** (10 blocking; 6 non-blocking)
- Critical: 2 | High: 4 | Medium: 4 | Low: 0
- By category: Bugs: 4 | Gaps: 5 | Deviations: 3 | Assumptions: 2 | Hallucinations: 2
- Files reviewed: 7 (structure.py, scope_resolver.py, extractor.py, canon_extractor.py, freshness.py, __init__.py, cli.py)
- Recommendation: Fix bugs first (F-001, F-002, F-003), then gaps.

---

## Critical Findings

### F-001 — freshness.py: `seeds` is a list, iterated as a dict
- **File**: `tools/specdev_tools/context/freshness.py:86`
- **Severity**: critical
- **Category**: bug
- **Reference**: §7 A6 — `check_freshness` must read seed file paths from `seed_manifest.json`
- **Evidence**:
  ```python
  for seed_id, seed_meta in manifest.get("seeds", {}).items():
  ```
  But `seed_manifest.json` has `seeds` as a **list**, not a dict:
  ```json
  "seeds": [{"seed_id": "seed-overview", "path": "docs/seed/seed_overview.md", ...}, ...]
  ```
- **Detail**: Calling `.items()` on a list raises `AttributeError: 'list' object has no attribute 'items'`. The function silently swallows this via the `except (OSError, json.JSONDecodeError)` block — no, actually the except block only catches `OSError` and `json.JSONDecodeError`, so `AttributeError` would propagate up. The freshness check will crash whenever a `seed_requirements.json` exists alongside a `seed_manifest.json`.
- **Fix**: Replace the iteration with a list comprehension: `for seed in manifest.get("seeds", []): seed_file_map[seed["seed_id"]] = seed.get("path") or seed.get("file")`.

### F-002 — A5 (`reviewer.py`) not implemented; CLI `context review` subcommand missing
- **File**: `tools/specdev_tools/context/` (missing file); `tools/specdev_tools/cli.py:287–319` (missing subparser)
- **Severity**: critical
- **Category**: gap
- **Reference**: §7 A5 — `reviewer.py` with `review_artifact()`, full class hierarchy; §7 A7 — `specdev context review <artifact_path> --step <NN>`
- **Evidence**: `ls tools/specdev_tools/context/reviewer.py` → file not found. CLI `ctx_sub` has no `"review"` subparser. `__init__.py` does not export `review_artifact`.
- **Detail**: A5 is the most complex deliverable in Phase A. It implements the two-pass structural + semantic review gate described in §3c step 8 and §3d. Without it, the `/specdev-step` skill (Phase B) cannot run step 8 of its flow. The entire review mechanism is absent.
- **Fix**: Implement `reviewer.py` with `SourceRef`, `TargetRef`, `ReviewPair`, `StructuralReview`, `ReviewResult` dataclasses and `review_artifact()` per §7 A5. Wire `specdev context review` in cli.py. Export `review_artifact` from `__init__.py`.

---

## High Findings

### F-003 — canon_extractor uses `_ref` suffix alone, not `$ref` target check (violates locked decision 4h)
- **File**: `tools/specdev_tools/context/canon_extractor.py:61–75`
- **Severity**: high
- **Category**: deviation from locked decision
- **Reference**: §4 locked decision 4h — "Identify canonicalRef fields ($ref target check, NOT _ref suffix alone) ~15% of _ref fields (14 of 91) are non-canonicalRef"
- **Evidence**:
  ```python
  def _collect_ref_fields(properties: dict[str, Any]) -> set[str]:
      for field_name, field_schema in properties.items():
          if field_name.endswith("_ref"):
              found.add(field_name)
  ```
  Confirmed non-canonical `_ref` fields in schemas:
  - `fixture_ref` → `$ref: vc:core:atoms#kebabId` (step 04, 14, 16)
  - `interface_ref` → `$ref: vc:core:atoms#kebabId` (step 15) — **this one IS in `_REF_TO_KIND`**, causing a false canon lookup for step 15
  - `spec_ref`, `nfr_ref` → non-canonicalRef (steps 16)
- **Detail**: Step 15's `interface_ref` is a kebab-case atom (a plain string ID), not a canonicalRef. Because `interface_ref` is in `INFERENCE_RULES`, `canon_extractor` will incorrectly include "interface" kind vocabulary for step 15 even though no canonical `interface_ref` is used there. The correct identification is: field schema has `$ref` pointing to `vc:core:collections#canonicalRef`.
- **Fix**: In `_collect_ref_fields`, check `field_schema.get("$ref", "") == "vc:core:collections#canonicalRef"` (or ends with `#canonicalRef`) rather than using the `_ref` suffix alone.

### F-004 — A3 scope_resolver never calls `build_trace_matrix`; violates locked decision 4a
- **File**: `tools/specdev_tools/context/scope_resolver.py:160–173`
- **Severity**: high
- **Category**: deviation from locked decision
- **Reference**: §4 locked decision 4a — "Always regenerate trace_matrix.json at the start of every context command. No staleness checks, no mtime comparisons." §7 A3 — "depends on: trace_matrix (regenerated on demand — A3 must call `specdev matrix` first)"
- **Evidence**: `scope_resolver.py` has zero imports from `validation.matrix`. It builds its own in-memory graph by walking spec files directly, never writing or reading `trace_matrix.json`.
- **Detail**: The locked decision is explicit: `trace_matrix.json` must be regenerated on every context command invocation. The implementation bypasses this entirely. While the in-memory graph likely produces similar traversal results, it diverges from the specified architecture and means `trace_matrix.json` is never kept fresh by context commands.
- **Fix**: At the top of `resolve_scope()`, call `build_trace_matrix(repo_root, spec_dir)` from `..validation.matrix` and write the result to `tools/trace_matrix.json`. The existing in-memory traversal can remain as the actual scoping engine — the matrix call satisfies the locked decision's freshness requirement.

### F-005 — A4a (`extraction_paths.json` hybrid cache) not implemented
- **File**: `tools/specdev_tools/context/extractor.py` (missing cache logic)
- **Severity**: high
- **Category**: gap
- **Reference**: §7 A4a — hybrid cache of concrete jq paths per step/entry; schema hash staleness detection; first-invocation trigger mechanism
- **Evidence**: `grep -n "extraction_paths\|cache\|schema_hash\|sha256" extractor.py` → no matches.
- **Detail**: A4a is described as a distinct sub-item within A4 with its own format specification including `_meta.schema_hashes`, per-step jq path arrays, and SHA-256 staleness detection. It is entirely absent. The dependency graph in §7d shows A4a as a sibling to A4, not optional.
- **Fix**: Implement the cache layer per §7 A4a: create `extraction_paths.json` management logic in extractor.py (check cache, compare schema hashes, use cached paths when fresh, trigger path discovery on miss).

### F-006 — Tier 2 truncation (item count > 20) not implemented in extractor
- **File**: `tools/specdev_tools/context/extractor.py:254–266`
- **Severity**: high
- **Category**: gap
- **Reference**: §7 A4 — "Tier 2 — if item count > threshold (default 20), include `_context_note` header and truncate. Escape hatch: `specdev context extract --step N --full` to override."
- **Evidence**: No threshold check, no `_context_note` header insertion, no truncation in the non-traceable array branch. The `--full` flag is wired in CLI but only controls the traceable scope filter, not Tier 2 truncation.
- **Detail**: Without Tier 2 truncation, large non-traceable arrays (e.g., a 50-item glossary) are included in full even without `--full`. This is the primary token-reduction mechanism for mid-steps and defeats the optimisation goal.
- **Fix**: After `_strip_to_required`, check `len(stripped) > 20` (or configurable threshold). If exceeded and not `full`, truncate to 20 items and prepend `{"_context_note": "truncated to 20 of N items; use --full to see all"}`.

---

## Medium Findings

### F-007 — scope_resolver: entry not found in graph returns entry_id in `frs` bucket (incorrect)
- **File**: `tools/specdev_tools/context/scope_resolver.py:233–252`
- **Severity**: medium
- **Category**: bug
- **Reference**: §7 A3 output format — resolved_ids grouped by trace_type; BFS from entry_id
- **Evidence**:
  ```python
  reachable = _bfs_reachable(entry_id, adjacency)
  # If entry_id not in adjacency, BFS returns {entry_id}
  # _id_to_bucket("fr-nonexistent") → "frs"
  # resolved_ids: {"frs": ["fr-nonexistent"]}
  ```
  Verified: `resolve_scope("fr-nonexistent", "spec", ".")` returns `{"resolved_ids": {"frs": ["fr-nonexistent"]}}`.
- **Detail**: When `entry_id` is not found in any spec file, BFS returns a singleton `{entry_id}`. This gets classified into a bucket based on ID prefix and returned as if it were a real resolved entity. The extractor then filters arrays for this non-existent ID and returns empty context — silently, with no indication that the scope anchor was invalid.
- **Fix**: After `_bfs_reachable`, check if `entry_id in id_to_file`. If not, return a result with `"scope_warning": "entry_id not found in spec files"` (and optionally `resolved_ids: {}`).

### F-008 — `_SEED_STEPS` in structure.py includes steps 03 and 04 which are not in seed_manifest
- **File**: `tools/specdev_tools/context/structure.py:34–35`
- **Severity**: medium
- **Category**: assumption / hallucination
- **Reference**: §6 decision D1 — "Seeds feed Steps 00-04 only." But actual `seed_manifest.json` `step_requirements` only covers `00`, `01`, `02`, `02a`. Steps 03 and 04 have no seed requirements.
- **Evidence**:
  ```python
  _SEED_STEPS: frozenset[str] = frozenset(["00", "01", "02", "02a", "03", "04"])
  ```
  Actual manifest: `step_requirements` keys = `["00", "01", "02", "02a"]`. Steps 03 and 04 return `[]` correctly (because `step_requirements.get("03", [])` → `[]`), but the guard in `_seeds_required` still tries to open the manifest file for steps 03 and 04 unnecessarily.
- **Detail**: Not a crash, but misleading. The guard's intent is "skip manifest lookup for late steps (05+)" but the constant implies 03/04 have seeds when they don't. If the manifest is extended in future to add step 03 seed requirements, this is fine. If not, it's dead code that creates confusion.
- **Fix**: Change `_SEED_STEPS` to match actual manifest keys, or rename it to `_POSSIBLE_SEED_STEPS` to signal it's an upper bound. Document why 03/04 are included.

### F-009 — `required_inputs` output has extra `"step"` key not in spec's output format
- **File**: `tools/specdev_tools/context/structure.py:196–201`
- **Severity**: medium
- **Category**: deviation from spec output contract
- **Reference**: §7 A2 output format — `required_inputs: [{"file": "00_charter.json", "keys": [...], "array_counts": {...}}]`
- **Evidence**:
  ```python
  entry: dict[str, Any] = {
      "step": src_step,   # ← not in spec output format
      "file": None,
      "keys": [],
      "array_counts": {},
  }
  ```
  Spec output shows `file` as the first key, with no `step` field inside each entry.
- **Detail**: The `step` field is useful contextual information for consumers of the JSON output, but it's not in the spec contract and may break downstream tooling (Phase B `/specdev-step` skill) if it parses the output by exact structure. Minor, but a contract deviation.
- **Fix**: Either remove the `"step"` key from each entry (match spec contract exactly) or explicitly add it to the spec as an extension. Decision needed.

### F-010 — `_merge_allof` in extractor/canon_extractor uses `registry.load()` for `$ref` resolution but spec requires `to_referencing_registry()`
- **File**: `tools/specdev_tools/context/extractor.py:73–87`, `tools/specdev_tools/context/canon_extractor.py:41–55`
- **Severity**: medium
- **Category**: deviation from locked decision
- **Reference**: §4 locked decision 4f — "$ref resolution (URN → schema contents): Use `SchemaRegistry.to_referencing_registry()` — reuses the referencing.Registry the validation pipeline already depends on."
- **Evidence**:
  ```python
  def _merge_allof(schema: dict, registry: SchemaRegistry) -> dict:
      for branch in schema["allOf"]:
          if "$ref" in branch:
              branch = registry.load(branch["$ref"])  # ← uses load(), not to_referencing_registry()
  ```
- **Detail**: `SchemaRegistry.load()` only handles top-level URIs registered in `schema_registry.json`. `to_referencing_registry()` builds a `referencing.Registry` that can resolve anchor-based `$ref`s (e.g., `vc:core:collections#canonicalRef`). Currently, `allOf[0].$ref: "vc:core:step-base"` is a top-level URI and works fine with `load()`. But if any schema branch uses anchor-based `$ref`s, `load()` will fail (FileNotFoundError). This is fragile.
- **Fix**: Implement allOf merging using `to_referencing_registry()` per spec. Or at minimum add a note that `load()` is an intentional simplification with known limitation.

---

## Low Findings

*(none)*

---

## Pass Confirmations

- **A2 `structure.py` core function**: `get_step_structure()` correctly inverts `downstream_consumers`, finds spec files by `{step_id}_` prefix, extracts top-level keys and array counts, loads output schema keys from `allOf[1].properties`, reads seed requirements from manifest. ✓ `structure.py:157–245`
- **A3 `scope_resolver.py` BFS graph**: Bidirectional adjacency graph correctly collects `trace`, `targets`, `fr_refs`, `source_milestones` edges. BFS from entry_id correctly reaches all connected entities. ✓ `scope_resolver.py:83–188`
- **A3 ID bucketing**: `_id_to_bucket()` correctly classifies `fr-*`, `api-*`, `fix-*`, `fixture-*`, `nfr-*`, `threat-*`, `cap-*`, `inv-*`, `milestone-*`, `task-*`. ✓ `scope_resolver.py:49–54`
- **A4 extractor traceable array filtering**: Correctly detects traceable arrays by `_id` field + `is_valid_trace_type()`, filters to `resolved_id_set`, strips boilerplate keys. ✓ `extractor.py:97–115`, `240–253`
- **A4 extractor non-traceable arrays**: Required-fields mode using `item_schema.get("required", [])`. ✓ `extractor.py:254–266`
- **A4 extractor scalars/objects**: Always included fully, no boilerplate stripping applied (correct — boilerplate stripping is for array items). ✓ `extractor.py:276–278`
- **A4 extractor token estimates**: `len(json.dumps(context)) // 4` and `sum(file_sizes) // 4`. ✓ `extractor.py:283–292`
- **A4b canon_extractor schema walk**: Merges allOf, recurses into array `items.properties` and object `properties` for nested `_ref` fields. ✓ `canon_extractor.py:58–75`
- **A4b canon_extractor kind loading**: Correctly handles both list format and `{"entries": [...]}` dict format in canon kind files. ✓ `canon_extractor.py:94–112`
- **INFERENCE_RULES promoted to `core/constants.py`**: ✓ `core/constants.py:45–74`
- **autofix.py updated to import from core/constants**: ✓ `canonical/autofix.py:16`
- **A6 freshness.py hash mechanism**: SHA-256 computation, stale detection, returns `{"status": "no_index"}` when no index exists. ✓ `freshness.py:22–64`
- **A7 CLI structure/scope/extract/canon/freshness subcommands**: All five wired, correct argument sets, `--full` flag, `--entry` flag. ✓ `cli.py:287–319`, `1455–1488`
- **A1 `__init__.py` public exports**: All five public functions exported via `__all__`. ✓ `context/__init__.py`
- **`_merge_allof` handles allOf[2] if/then branches**: Branches with `if`/`then` but no `properties` yield empty props and are safely skipped. ✓ `extractor.py:73–87`
- **Duplicate INFERENCE_RULES entries are harmless**: `acronym_ref`, `environment_ref`, `risk_category_ref` have duplicate rules that map to the same kind — last-write-wins produces correct output. ✓

---

## Observations (Non-Blocking)

- **NB-01 | medium** | `cap-` key in `_PREFIX_TO_BUCKET` is redundant — `"cap"` already handles `cap-*` via `entity_id.startswith("cap-")`. Remove `"cap-"` entry. `scope_resolver.py:32`
- **NB-02 | medium** | `scope_resolver.py` accepts `repo_root` parameter but doesn't use it (documented with `_ = repo_root`). This is correct per spec ("accepted for API consistency — future use") but Pyright still flags it. Consider typing it as `repo_root: str = ""` with a default or using `# noqa` annotation.
- **NB-03 | medium** | No tests exist for any of the 5 new context modules. All 1510 existing tests pass, but there is zero coverage of the new package. A `tests/test_context_*.py` suite should be added.
- **NB-04 | low** | `_find_spec_file` is duplicated in both `structure.py` and `extractor.py` (identical implementations). Extract to a shared `_utils.py` or `core/loaders.py`.
- **NB-05 | low** | `_load_step_order` is also duplicated in both `structure.py` and `extractor.py`. Same fix as NB-04.
- **NB-06 | low** | `_merge_allof` is duplicated in both `extractor.py` and `canon_extractor.py`. Extract to shared location.

---

## Actionable Fix Plan

### Batch 1 — Critical bugs (independent)

Task 1:
  file: tools/specdev_tools/context/freshness.py
  mode: modify
  reads: spec/common/seed_manifest.json
  action: Fix F-001: Replace `manifest.get("seeds", {}).items()` with iteration over the list format: `for seed in manifest.get("seeds", [])`, using `seed["seed_id"]` as the key and `seed.get("path") or seed.get("file")` as the path value.
  test_gate: pytest tests/ -x -q
  verify: `check_freshness` does not raise AttributeError when seed_manifest.json has seeds as a list
  depends_on: none
  parallel_group: 1
  source: F-001

Task 2:
  file: tools/specdev_tools/context/canon_extractor.py
  mode: modify
  reads: schema/core/collections.schema.json, tools/schema_registry.json
  action: Fix F-003: In `_collect_ref_fields`, replace the `field_name.endswith("_ref")` check with a $ref target check — include field only if `field_schema.get("$ref", "").endswith("#canonicalRef")`. This matches the canonicalRef anchor in vc:core:collections.
  test_gate: pytest tests/ -x -q
  verify: Step 15 `extract_canon` no longer includes "interface" kind (since step 15 interface_ref is kebabId, not canonicalRef)
  depends_on: none
  parallel_group: 1
  source: F-003

### Batch 2 — High gaps (can run after Batch 1)

Task 3:
  file: tools/specdev_tools/context/scope_resolver.py
  mode: modify
  reads: tools/specdev_tools/validation/matrix.py, WIP/trans/toolkit_optimisation.txt §4a
  action: Fix F-004: At the start of `resolve_scope()` (when entry_id is not None), call `build_trace_matrix(repo_root, spec_dir)` from `..validation.matrix` and write the result to `{repo_root}/tools/trace_matrix.json`. Keep the existing in-memory BFS as the scoping engine. Also fix F-007: after `_bfs_reachable`, check if `entry_id in id_to_file`; if not found, add `"scope_warning": "entry_id '{entry_id}' not found in any spec file"` to the return dict.
  test_gate: pytest tests/ -x -q
  verify: After calling `resolve_scope("fr-anything", ...)`, tools/trace_matrix.json mtime is updated; calling with non-existent ID returns scope_warning key
  depends_on: none
  parallel_group: 2
  source: F-004, F-007

Task 4:
  file: tools/specdev_tools/context/extractor.py
  mode: modify
  reads: WIP/trans/toolkit_optimisation.txt §7 A4a, §7 A4
  action: Fix F-005 and F-006: (a) Add Tier 2 truncation — after `_strip_to_required`, if `len(stripped) > 20` and not `full`, truncate to 20 items and prepend `{"_context_note": f"truncated to 20 of {len(value)} items; use --full to see all"}`. (b) Implement A4a extraction_paths.json cache: check `{repo_root}/tools/extraction_paths.json` for a cached entry for `src_step`; compare schema hash via SHA-256 of the schema file; if cache is fresh, use the cached jq paths to filter fields instead of including all payload properties; if stale or missing, populate the cache entry after extraction.
  test_gate: pytest tests/ -x -q
  verify: Extracting a step with >20 items in a non-traceable array returns exactly 21 entries (20 items + _context_note) unless --full is passed
  depends_on: none
  parallel_group: 2
  source: F-005, F-006

### Batch 3 — A5 reviewer (depends on nothing, but large)

Task 5:
  file: tools/specdev_tools/context/reviewer.py
  mode: create
  reads: WIP/trans/toolkit_optimisation.txt §7 A5, tools/specdev_tools/context/scope_resolver.py, tools/specdev_tools/context/extractor.py
  action: Fix F-002 (part 1): Implement reviewer.py per §7 A5. Create dataclasses SourceRef, TargetRef, ReviewPair, StructuralReview, ReviewResult. Implement review_artifact(artifact_path, step_id, spec_dir, repo_root, entry_id=None) -> ReviewResult. Pass 1 (structural): ID coverage check (upstream IDs vs emitted trace IDs), reverse trace check (output IDs not in scope → scope creep), acceptance criteria coverage. Pass 2 (semantic pairs): generate ReviewPair records for the 5 check types (faithfulness, acceptance_gap, seed_distillation, quantifier_weakening, scope_completeness) using heuristic detection. Return ReviewResult with verdict PASS | NEEDS_SEMANTIC_REVIEW | FAIL.
  test_gate: pytest tests/ -x -q
  verify: review_artifact returns a ReviewResult with structural.upstream_coverage, semantic_pairs, and verdict fields
  depends_on: none
  parallel_group: 3
  source: F-002

Task 6:
  file: tools/specdev_tools/context/__init__.py
  mode: modify
  reads: tools/specdev_tools/context/reviewer.py
  action: Fix F-002 (part 2): Add `from .reviewer import review_artifact` import and add "review_artifact" to `__all__`.
  test_gate: pytest tests/ -x -q
  depends_on: 5
  parallel_group: 3
  source: F-002

Task 7:
  file: tools/specdev_tools/cli.py
  mode: modify
  reads: tools/specdev_tools/context/reviewer.py, WIP/trans/toolkit_optimisation.txt §7 A7
  action: Fix F-002 (part 3): Add `ctx_review = ctx_sub.add_parser("review")` subparser with arguments `artifact_path` (positional), `--step` (required), `--entry` (optional), `--repo-root` (default "."), `--json`. Add `elif context_cmd == "review":` dispatch block importing `review_artifact` and calling it with parsed args.
  test_gate: pytest tests/ -x -q
  verify: `specdev context review spec/05_interface_contracts.json --step 05 --repo-root .` runs without error
  depends_on: 5, 6
  parallel_group: 3
  source: F-002

### Batch 4 — Medium contract/design issues

Task 8:
  file: tools/specdev_tools/context/structure.py
  mode: modify
  reads: spec/common/seed_manifest.json, WIP/trans/toolkit_optimisation.txt §6 D1
  action: Fix F-008: Rename `_SEED_STEPS` to `_POSSIBLE_SEED_STEPS` and add a comment explaining that steps 03/04 are included as an upper bound but actual requirements come from seed_manifest.step_requirements. Resolve F-009 as a decision: if keeping `"step"` in required_inputs entries, add a comment noting it's an extension of the spec output contract.
  test_gate: pytest tests/ -x -q
  depends_on: none
  parallel_group: 4
  source: F-008, F-009

---

## Decision Log

*Empty — no findings escalated to human review during this analysis pass.*
