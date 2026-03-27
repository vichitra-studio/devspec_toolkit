# Findings: Cross-Step Validator Duplication (DRY / Determinism)

**Source**: T-tools-tests-review-004
**Criteria examined**: C5, C6, E1, E5
**Scope**: All 21 step validators in `tools/specdev_tools/validation/validators/`
**Date**: 2026-03-11

---

## Summary

| Criterion | Status | Severity | Key Metric |
|-----------|--------|----------|------------|
| C5 — Cross-step ID resolution duplication | FINDING | HIGH | 24 `_load_*` functions across 14 files; 7 independent FR-ID loaders |
| E1 — Cross-step ID resolution duplicated LOC | FINDING | HIGH | ~408 LOC of copy-pasted boilerplate; 0 shared utility exists |
| C6 — Determinism (traversal order) | FINDING | LOW | 18 unsorted `os.listdir` sites; non-deterministic if multiple prefix matches |
| E5 — Schema loading bypass | FINDING | LOW | Not a schema-registry bypass; 26 direct `json.load` calls load spec data (not schemas); distinct issue from E1 |

---

## FINDING C5 — Cross-Step ID Resolution Duplication

**Criterion**: Count how many validators independently implement `load spec → extract IDs` logic. Industry standard is a shared utility for upstream ID resolution.

### Canonical Pattern (13-line body, repeated with cosmetic variation)

```python
def _load_fr_ids(toolkit_root: str) -> Optional[Set[str]]:
    spec_dir = os.path.join(toolkit_root, "spec")        # line A: build path
    if not os.path.isdir(spec_dir):                      # line B: dir guard
        return None
    for fn in os.listdir(spec_dir):                      # line C: unsorted traversal
        if fn.startswith("04_") and fn.endswith(".json"):# line D: prefix match
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:  # line E: open
                    data = json.load(f)                        # line F: parse
                return {                                        # line G: extract
                    fr.get("fr_id")
                    for fr in data.get("functional_requirements", [])
                    if isinstance(fr, dict) and fr.get("fr_id")
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
```

Only the step prefix (`"04_"`), array key (`"functional_requirements"`), and ID field (`"fr_id"`) change across instances. The structural body is identical.

### Complete Inventory of `_load_*` Functions

| File | Function | Upstream Step | File prefix | Extract key | LOC | Line range |
|------|----------|---------------|-------------|-------------|-----|------------|
| `step_04.py` | `_load_capability_ids` | 01 | `01_` | `capability_id` from `capabilities[]` | 17 | 63–82 |
| `step_05.py` | `_load_fr_ids` | 04 | `04_` | `fr_id` from `functional_requirements[]` | 15 | 85–104 |
| `step_06.py` | `_load_fr_ids` | 04 | `04_` | `fr_id` from `functional_requirements[]` | 17 | 117–136 |
| `step_06.py` | `_load_api_ids` | 05 | `05_` | `api_id` from `apis[]` | 17 | 139–158 |
| `step_07.py` | `_load_fr_ids` | 04 | `04_` | `fr_id` from `functional_requirements[]` | 14 | 83–99 |
| `step_08.py` | `_load_fr_ids` | 04 | `04_` | `fr_id` from `functional_requirements[]` | 17 | 86–105 |
| `step_08.py` | `_load_api_ids` | 05 | `05_` | `api_id` from `apis[]` | 17 | 108–127 |
| `step_08.py` | `_load_inv_ids` | 06 | `06_` | `inv_id` from `rules[]` | 17 | 130–149 |
| `step_08.py` | `_load_nfr_ids` | 07 | `07_` | `nfr_id` from `nfrs[]` | 17 | 152–171 |
| `step_09.py` | `_load_capability_ids` | 01 | `01_` | `capability_id` from `capabilities[]` | 17 | 52–71 |
| `step_11.py` | `_load_component_ids` | 02 | `02_*` (non-02a) | `component_id` from `components[]` | 17 | 114–132 |
| `step_11.py` | `_load_api_ids` | 05 | `05_` | `api_id`/`endpoint_id` from `apis[]` | 17 | 135–154 |
| `step_12.py` | `_load_fr_ids` | 04 | `04_` | `fr_id` from `functional_requirements[]` | 17 | 122–142 |
| `step_12.py` | `_load_nfr_ids` | 07 | `07_` | `nfr_id` from `nfrs[]` | 17 | 145–164 |
| `step_13.py` | `_load_governance_labels` | 10 | `10_` | governance `id` from `canonical_refs_used[]` where `kind=="governance_label"` | 30 | 78–112 |
| `step_13a.py` | `_load_fr_ids` | 04 | `04_` | `fr_id` from `functional_requirements[]` | 17 | 101–120 |
| `step_13a.py` | `_load_api_ids` | 05 | `05_` | `api_id` from `apis[]` | 17 | 123–142 |
| `step_14.py` | `_load_step09_milestone_ids` | 09 | fixed path | `milestone_id` from `milestones[]` | 28 | 152–181 |
| `step_14.py` | `_load_step09_tech_stack_names` | 09 | fixed path | tech names from `tech_stack{}` | 15 | 184–200 |
| `step_14.py` | `_load_step04_fr_ids` | 04 | fixed path | `fr_id`/`id` from `functional_requirements[]` | 20 | 203–225 |
| `step_14.py` | `_load_step01_cap_ids` | 01 | fixed path | `capability_id`/`id` from `capabilities[]` | 20 | 228–250 |
| `step_15.py` | `_load_api_ids` | 05 | `05_` | `api_id` from `apis[]`/`contracts[]` | 18 | 81–102 |
| `step_16.py` | inline FR load (E306) | 04 | fixed path | `fr_id` from `functional_requirements[]` | 10 | 396–414 |
| `step_07.py` | `_load_canonical_stages` | canon/manifest | fixed path | stage `id` values from `stages.values[]` | 13 | 67–80 |

**Total**: 24 private loader functions across 14 validator files.

### Duplication Counts by Target Step

| Upstream step | Data loaded | Independent loaders | Files |
|---------------|-------------|---------------------|-------|
| Step 04 (FR IDs) | `functional_requirements[].fr_id` | **7** (+1 inline in step_16) | step_05, step_06, step_07, step_08, step_12, step_13a, step_14 |
| Step 05 (API IDs) | `apis[].api_id` | **5** | step_06, step_08, step_11, step_13a, step_15 |
| Step 01 (capability IDs) | `capabilities[].capability_id` | **3** | step_04, step_09, step_14 |
| Step 07 (NFR IDs) | `nfrs[].nfr_id` | **2** | step_08, step_12 |
| Step 09 (milestone IDs) | `milestones[].milestone_id` | **1 file, 2 functions** | step_14 |
| Step 06 (invariant IDs) | `rules[].inv_id` | **1** | step_08 |
| Step 02 (component IDs) | `components[].component_id` | **1** | step_11 |
| Step 10 (governance labels) | `canonical_refs_used[].id` | **1** | step_13 |

---

## FINDING E1 — Duplicated LOC Quantification

**Criterion**: Quantify duplicated LOC for the ID resolution analysis.

The 24 `_load_*` functions total approximately **408 LOC** (sum of the "LOC" column above). Every function implements the identical 5-step algorithm (path build, dir guard, listdir loop, json.load, set comprehension). A single parameterised utility would require approximately **25 LOC**:

```python
def load_upstream_ids(
    toolkit_root: str,
    step_prefix: str,
    array_key: str,
    id_field: str,
    exclude_prefix: str = "",
) -> Optional[Set[str]]:
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None
    for fn in sorted(os.listdir(spec_dir)):
        if fn.startswith(step_prefix) and fn.endswith(".json"):
            if exclude_prefix and fn.startswith(exclude_prefix):
                continue
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    item.get(id_field)
                    for item in data.get(array_key, [])
                    if isinstance(item, dict) and item.get(id_field)
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
```

**Net saving: ~383 LOC** (408 duplicate − 25 utility).

### Structural Divergence Points (Latent Bugs from Copy-Paste Drift)

| File | Function | Divergence vs canonical |
|------|----------|------------------------|
| `step_05.py:91` | `_load_fr_ids` | Dir guard is inline: `for fn in os.listdir(spec_dir) if os.path.isdir(spec_dir) else []` instead of pre-loop check |
| `step_07.py:86` | `_load_fr_ids` | Same inline guard pattern as step_05 |
| `step_11.py:135` | `_load_api_ids` | Adds endpoint_id fallback: `a.get("api_id", a.get("endpoint_id", ""))` and set minus `{""}` — not present in other API loaders (step_06, step_08, step_13a, step_15) |
| `step_15.py:94` | `_load_api_ids` | Adds contracts fallback: `data.get("apis", data.get("contracts", []))` — not present in step_06/step_08/step_13a |
| `step_14.py:152–250` | All 4 loaders | Uses `pathlib.Path` with `artifact_path` directory candidate tried first, then `toolkit_root/spec/` fallback — entirely different resolution strategy from all other validators |
| `step_16.py:396–414` | Inline FR load | Not extracted into a function at all; embedded directly inside the validator body |

These divergences show that maintenance over time has caused the API ID loaders specifically to become inconsistent: endpoints/contracts fallbacks are present in 2 of 5 copies but absent from 3. If the schema adds another alias key, all 5 copies must be updated independently.

---

## FINDING C6 — Determinism: Unsorted `os.listdir` Traversal

**Criterion**: Check if any validator output depends on execution order, file system traversal order, or environment variables in a way that could produce non-deterministic results.

### Unsorted `os.listdir` Sites

`os.listdir()` returns filenames in filesystem-defined order (POSIX does not guarantee any ordering). All 18 call sites below use a `for fn in os.listdir(spec_dir)` loop and return on the **first matching file**. If the spec directory ever contains two files matching the same prefix pattern (e.g., `04_fr_list.json` and `04_fr_list_backup.json`), the file loaded is non-deterministic across OS/filesystem combinations.

| File | Line | Call |
|------|------|------|
| `step_04.py` | 69 | `for fn in os.listdir(spec_dir)` |
| `step_05.py` | 91 | `for fn in os.listdir(spec_dir) if os.path.isdir(spec_dir) else []` |
| `step_06.py` | 122 | `for fn in os.listdir(spec_dir)` |
| `step_06.py` | 144 | `for fn in os.listdir(spec_dir)` |
| `step_07.py` | 86 | `for fn in os.listdir(spec_dir) if os.path.isdir(spec_dir) else []` |
| `step_08.py` | 92 | `for fn in os.listdir(spec_dir)` |
| `step_08.py` | 114 | `for fn in os.listdir(spec_dir)` |
| `step_08.py` | 136 | `for fn in os.listdir(spec_dir)` |
| `step_08.py` | 158 | `for fn in os.listdir(spec_dir)` |
| `step_09.py` | 58 | `for fn in os.listdir(spec_dir)` |
| `step_11.py` | 119 | `for fn in os.listdir(spec_dir)` |
| `step_11.py` | 140 | `for fn in os.listdir(spec_dir)` |
| `step_12.py` | 128 | `for fn in os.listdir(spec_dir)` |
| `step_12.py` | 151 | `for fn in os.listdir(spec_dir)` |
| `step_13.py` | 93 | `for fn in os.listdir(spec_dir)` |
| `step_13a.py` | 107 | `for fn in os.listdir(spec_dir)` |
| `step_13a.py` | 129 | `for fn in os.listdir(spec_dir)` |
| `step_15.py` | 87 | `for fn in os.listdir(spec_dir)` |

**Total**: 18 unsorted traversal sites across 11 files.

Fix is one token: `for fn in sorted(os.listdir(spec_dir))`.

### Secondary Determinism Notes

- **`step_12.py:185`** `_collect_refs_from_value` returns `set[str]` and the caller iterates it without sorting. CPython set iteration order is not guaranteed across interpreter restarts. Effect: non-deterministic ordering of error messages only (not incorrect detection). Low severity.
- **`step_16.py:313, :380`**: Both call `sorted()` before iterating — this is correct and confirms the author was aware of ordering. The `os.listdir` sites in other files did not apply the same discipline.
- **Environment variables**: None of the 21 validators read `SPECDEV_*` env vars. Those are consumed at CLI/runner level. No env-var-dependent output variance in validators.

---

## FINDING E5 — Schema Loading: Bypass vs Registry

**Criterion**: Check if multiple modules load JSON schemas independently (direct file reads, `json.load`) vs through `core/registry.py` (85 LOC). Count modules that bypass the registry.

### Registry Usage (Correct)

Only **2 of 21** validators use `SchemaRegistry` for JSON Schema loading:

| File | Lines | Usage |
|------|-------|-------|
| `step_01.py:56–57` | `registry = SchemaRegistry(repo_root)` then `registry.load(uri)` | Schema validation via `Draft202012Validator` |
| `step_02.py:126–127` | `registry = SchemaRegistry(repo_root)` then `registry.load(uri)` | Schema validation via `Draft202012Validator` |

### Direct `json.load` for Spec Data (Not Registry-Eligible)

**13 of 21** validators use `json.load(f)` directly. However, these calls load **upstream spec artifacts** (files in `spec/`), not JSON Schema files. The `tools/schema_registry.json` registry maps schema URIs to schema paths only — spec artifact paths are not registered in it.

| File | Direct `json.load` sites | Spec files loaded |
|------|--------------------------|-------------------|
| `step_04.py` | 1 (line 74) | `01_*.json` |
| `step_05.py` | 1 (line 95) | `04_*.json` |
| `step_06.py` | 2 (lines 127, 148) | `04_*.json`, `05_*.json` |
| `step_07.py` | 2 (lines 72, 92) | `canon/manifest.json`, `04_*.json` |
| `step_08.py` | 4 (lines 97, 119, 141, 163) | `04_*.json`, `05_*.json`, `06_*.json`, `07_*.json` |
| `step_09.py` | 1 (line 63) | `01_*.json` |
| `step_11.py` | 2 (lines 124, 143) | `02_*.json`, `05_*.json` |
| `step_12.py` | 2 (lines 133, 155) | `04_*.json`, `07_*.json` |
| `step_13.py` | 1 (line 98) | `10_*.json` |
| `step_13a.py` | 2 (lines 111, 132) | `04_*.json`, `05_*.json` |
| `step_14.py` | 4 (lines 165, 195, 214, 239) | `09_impl_plan.json`, `04_fr_list.json`, `01_capabilities.json` |
| `step_15.py` | 1 (line 94) | `05_*.json` |
| `step_16.py` | 3 (lines 164, 298, 398) | `seed_manifest.json`, `14_roadmap.json`, `04_fr_list.json` |

**Total**: 26 direct `json.load` sites across 13 files loading spec artifacts.

### Assessment

The `SchemaRegistry` is **not bypassed for schema loading** — the two validators that do schema validation (step_01, step_02) both correctly use the registry. No validator loads a JSON Schema file via bare `json.load`.

The 26 direct `json.load` calls load spec data for cross-step ID resolution. This is **not a schema registry bypass** issue; it is the same **spec-data-loading duplication** documented under C5/E1. There is no equivalent of `SchemaRegistry` for spec artifact loading — each validator independently implements open+parse. A spec-artifact loader utility (equivalent to what `SchemaRegistry` provides for schemas) is the missing abstraction.

---

## PASS Records

PASS | C6 | Error list output ordering is deterministic | Validators append errors sequentially as they iterate input arrays (JSON-defined order). No unguarded set or dict iteration affects error output ordering. The `sorted()` calls in `step_02.py:95,109`, `step_16.py:313,380` further confirm deterministic output for set-derived data.

PASS | C6 | No environment-variable-dependent variance in validators | None of the 21 step validators read `SPECDEV_*` or any other environment variables. Env var consumption is at CLI/runner level only.

PASS | E5 | SchemaRegistry not bypassed for JSON Schema loading | The two validators that perform schema validation (step_01, step_02) both use `SchemaRegistry` from `core/registry.py`. No validator loads a JSON Schema file via direct `json.load` bypassing the registry.

---

## ID Resolution Comparison Table

This table covers every validator that performs cross-step spec-file loading, showing the exact file/line of the open call and the extraction expression. All non-loading validators (step_01, step_02, step_02a, step_03, step_10, step_16a, step_16b, step_16c) are omitted — they contain no upstream spec loading.

| Validator | Upstream file loaded | Open location | Extraction expression |
|-----------|---------------------|---------------|-----------------------|
| `step_04.py:73` | `01_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `cap.get("capability_id")` from `capabilities[]` |
| `step_05.py:94` | `04_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `fr.get("fr_id")` from `functional_requirements[]` |
| `step_06.py:126` | `04_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `item.get("fr_id")` from `functional_requirements[]` |
| `step_06.py:147` | `05_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `item.get("api_id")` from `apis[]` |
| `step_07.py:71` | `canon/manifest.json` | `with open(manifest_path, "r", encoding="utf-8") as f:` | `v.get("id")` from `stages.values[]` |
| `step_07.py:90` | `04_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `fr.get("fr_id")` from `functional_requirements[]` |
| `step_08.py:96` | `04_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `req.get("fr_id")` from `functional_requirements[]` |
| `step_08.py:118` | `05_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `api.get("api_id")` from `apis[]` |
| `step_08.py:140` | `06_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `rule.get("inv_id")` from `rules[]` |
| `step_08.py:162` | `07_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `nfr.get("nfr_id")` from `nfrs[]` |
| `step_09.py:62` | `01_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `cap.get("capability_id")` from `capabilities[]` |
| `step_11.py:123` | `02_*.json` (non-02a) | `with open(path, "r", encoding="utf-8") as f:` | `c.get("component_id")` from `components[]` |
| `step_11.py:142` | `05_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `a.get("api_id", a.get("endpoint_id",""))` from `apis[]` |
| `step_12.py:132` | `04_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `req.get("fr_id")` from `functional_requirements[]` |
| `step_12.py:154` | `07_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `nfr.get("nfr_id")` from `nfrs[]` |
| `step_13.py:97` | `10_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `ref.get("id")` from `canonical_refs_used[]` where `kind=="governance_label"` |
| `step_13a.py:110` | `04_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `req.get("fr_id")` from `functional_requirements[]` |
| `step_13a.py:131` | `05_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `api.get("api_id")` from `apis[]` |
| `step_14.py:163` | `09_impl_plan.json` | `with path.open("r", encoding="utf-8") as f:` | `milestone.get("milestone_id")` from `milestones[]` |
| `step_14.py:194` | `09_impl_plan.json` | `with path.open("r", encoding="utf-8") as f:` | tech names via `_collect_tech_names(data.get("tech_stack", {}))` |
| `step_14.py:213` | `04_fr_list.json` | `with path.open("r", encoding="utf-8") as f:` | `fr.get("fr_id") or fr.get("id")` from `functional_requirements[]` |
| `step_14.py:238` | `01_capabilities.json` | `with path.open("r", encoding="utf-8") as f:` | `cap.get("capability_id") or cap.get("id")` from `capabilities[]` |
| `step_15.py:93` | `05_*.json` | `with open(path, "r", encoding="utf-8") as f:` | `item.get("api_id")` from `apis[]`/`contracts[]` |
| `step_16.py:164` | `seed_manifest.json` | `with open(manifest_path, "r", encoding="utf-8") as f:` | `docs_policy.doc_paths[]` |
| `step_16.py:298` | `14_roadmap.json` | `json.loads(roadmap_path.read_text())` | `task["task_id"]` from each milestone's tasks |
| `step_16.py:398` | `04_fr_list.json` | `json.loads(fr_list_path.read_text())` | `fr.get("fr_id")` from `functional_requirements[]` |

---

## Recommended Remediation

### R1 — Shared upstream ID loader utility (C5, E1)

Create `tools/specdev_tools/validation/upstream_loader.py` (~25 LOC):

```python
def load_upstream_ids(
    toolkit_root: str,
    step_prefix: str,
    array_key: str,
    id_field: str,
    exclude_prefix: str = "",
) -> Optional[Set[str]]:
    spec_dir = os.path.join(toolkit_root, "spec")
    if not os.path.isdir(spec_dir):
        return None
    for fn in sorted(os.listdir(spec_dir)):        # sorted: fixes C6 simultaneously
        if fn.startswith(step_prefix) and fn.endswith(".json"):
            if exclude_prefix and fn.startswith(exclude_prefix):
                continue
            path = os.path.join(spec_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    item.get(id_field)
                    for item in data.get(array_key, [])
                    if isinstance(item, dict) and item.get(id_field)
                }
            except (OSError, json.JSONDecodeError):
                pass
    return None
```

Net saving: ~383 LOC. Eliminates the 5 structural divergence points documented above.

### R2 — Sorted directory traversal (C6)

If R1 is not applied immediately, wrap all 18 `os.listdir(spec_dir)` calls with `sorted()`:
`for fn in sorted(os.listdir(spec_dir)):`
This is a one-token change per site.

### R3 — Consistent dir guard placement (C6, code quality)

Replace the 2 inline `if os.path.isdir(spec_dir) else []` patterns (step_05:91, step_07:86) with the standard pre-loop check used by all other loaders.

### R4 — Spec-artifact loader cache (E5)

Introduce a lightweight `SpecArtifactCache` in `core/` mirroring `SchemaRegistry` for spec artifact loading. This prevents repeated disk reads when multiple validators load the same file (e.g., `04_fr_list.json` is loaded 7 times when validating a full pipeline).
