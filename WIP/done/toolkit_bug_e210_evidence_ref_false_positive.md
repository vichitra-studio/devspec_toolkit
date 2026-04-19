# Toolkit bug — `canonical-integrity` E210 false positive on string-typed `_ref` siblings (`evidence` / `evidence_ref`)

**Discovered**: 2026-04-19 while running `spec-check` against `ms-bootstrap-local-ghost` after Step 16b execution data was authored at scale.

**Severity**: P1 — blocks 16b/16c artifact commits in any host repo that populates the documented `evidence` / `evidence_ref` pair on `execution.execution_results[]`. There is no per-field suppression for E210 and stripping `evidence` content defeats the purpose of populating Step 16b execution receipts. Workaround is `git commit --no-verify`.

**Affected toolkit version**: `0.5.1` (`devspec_toolkit/tools/pyproject.toml:9`).

**Affected commits**: every commit reachable from the introduction of `_expected_ref_key` / `_collect_unresolved_candidates` in `eedf5fdbb34c5d65c8b3afc512fd319ee468e430` (2026-02-26 — `fix(review): address RFC canonical drift findings & close untracked assets`; verified via `git -C devspec_toolkit log -S '_expected_ref_key' -- tools/specdev_tools/canonical/integrity.py` and `git -C devspec_toolkit log -S '_FALLBACK_DIRECT_FIELDS' -- tools/specdev_tools/canonical/integrity.py` — both report `eedf5fd` as the sole introducing commit). Verified the same buggy logic block is structurally unchanged at `3930532` (parent of `b7ba008` per `git rev-parse`) and at the current `b7ba008` HEAD; `b7ba008` did not touch `tools/specdev_tools/canonical/integrity.py`. It only surfaces now because `ms-bootstrap-local-ghost` is the first milestone to author 14 populated `execution.execution_results[].evidence` strings.

**Affected environments**: toolkit submodule deployment (`devspec_toolkit/` vendored inside a host repo, host spec at `./spec/`). Reproduction commands are run from the host repo root (`/Users/vichitracollective/vc-code/vc_wesbite/`) with `source dev_env/bin/activate`.

---

## Symptom

Running `canonical-integrity` (or its parent `spec-check`) against the host repo produces 14 identically shaped errors, one per populated `evidence` entry in `spec/impl_context/ms_bootstrap_local_ghost_plan.json`:

```
E210 CROSS_ARTIFACT_DRIFT unresolved_canonical_semantic ../spec/impl_context/ms_bootstrap_local_ghost_plan.json field=execution.execution_results[0].evidence kind=evidence value='$ npm audit --prefix theme --audit-level=high\nqs <6.14.1 — moderate (via request→node-loggly-bulk→gscan); tough-cookie <4.1.3 — moderate\n8 moderate severity vulnerabilities\nEXIT=0 — passed (0 high, 0 critical)'
…
E210 CROSS_ARTIFACT_DRIFT unresolved_canonical_semantic ../spec/impl_context/ms_bootstrap_local_ghost_plan.json field=execution.execution_results[13].evidence kind=evidence value='$ bash theme/scripts/publish-latency-probe.sh\n14 PASSED P95=16ms threshold=3000ms samples=10 …'
```

Every entry has `evidence_ref` correctly populated as a URI string (per the schema), yet the integrity walker still flags the `evidence` string as an unresolved canonical semantic of `kind=evidence`.

## Reproduction

From the host repo root, against the working tree:

```bash
cd /Users/vichitracollective/vc-code/vc_wesbite
source dev_env/bin/activate

./tools/run_specdev.sh canonical-integrity spec \
  --repo-root ./devspec_toolkit \
  --spec-root ./spec \
  --git-root .
# 14 × E210 unresolved_canonical_semantic on
#   spec/impl_context/ms_bootstrap_local_ghost_plan.json
#   field=execution.execution_results[N].evidence
#   kind=evidence
#   for N in 0..13
```

Same errors surface via `spec-check spec …` (which calls canonical-integrity internally) and via per-file `validate spec/impl_context/ms_bootstrap_local_ghost_plan.json …`. The artifact at fault is the only currently authored `spec/impl_context/<milestone>_plan.json` file in this repo; any future plan that populates `execution.execution_results[*].evidence` will reproduce identically.

Minimal synthetic reproduction (does not require the bootstrap plan):

```python
# Any object pair {"evidence": "<≥20 chars>", "evidence_ref": "<URI>"} placed
# under execution.execution_results[] in a vc:16-impl-context document trips the check.
```

## Expected behavior

`evidence` is a free-form description string. The schema (`devspec_toolkit/schema/16_impl_context.schema.json:1653-1656`) defines it as:

```json
"evidence": {
  "type": "string",
  "minLength": 20,
  "description": "Concrete evidence supporting this execution result. Should contain raw command output, test runner output, or observable system behavior — not assertions. …"
}
```

`evidence_ref` (`schema/16_impl_context.schema.json:1658-1661`) is a plain URI string, **not** a `vc:core:collections#canonicalRef`:

```json
"evidence_ref": {
  "type": "string",
  "description": "External reference or URI pointing to the evidence source."
}
```

There is no `evidence` canon kind — re-verified by listing `devspec_toolkit/canon/kinds/` (25 files: acronym, action, capability, command, completeness_dimension, dependency, entity, environment, event, governance_label, id_pattern, interface, metric, nfr_category, owner, policy, risk_category, role, stage, status, tag, tech_stack, term, trace_type, unit) and `spec/canon/kinds/` (10 files: acronym, action, capability, command, entity, policy, risk_category, role, status, term). Neither contains `evidence.json`. (Re-verified independently of the prior agent.)

Expected outcome:
- `evidence` / `evidence_ref` pairs **must not** trigger E210 `unresolved_canonical_semantic`.
- Genuine canonicalRef pairs (e.g. `status` / `status_ref`, `command` / `command_ref`, `unit` / `unit_ref`) where the `_ref` sibling **is** schema-typed as `vc:core:collections#canonicalRef` and the value is missing or non-`cn:` **must continue to** trigger E210.

## Root cause

File: `devspec_toolkit/tools/specdev_tools/canonical/integrity.py`. The unresolved-candidate walker treats **any** string field whose sibling key is `<name>_ref` as a candidate canonical reference, regardless of how the `_ref` sibling is schema-typed.

Verified call chain:

1. `_validate_unresolved_candidates` (line 300) iterates the result of `_collect_unresolved_candidates` and emits the E210 error template at line 326:
   ```python
   make_error("E210", f"CROSS_ARTIFACT_DRIFT unresolved_canonical_semantic {rel} field={field_path} kind={kind} value={value!r}")
   ```
2. `_collect_unresolved_candidates` (line 331) walks every dict key. At line 354 it iterates `obj.items()`; for each non-`_ref` key whose value is a string (line 358), it computes `ref_key = _expected_ref_key(key, schema_props, allow_fallback=…)` (line 359), looks up `obj.get(ref_key)`, and if `_is_resolved_ref(ref_value)` is False **and** `_kind_for_ref_key(ref_key)` returns a non-empty kind, it appends `(next_path, kind, value)` (line 365).
3. `_expected_ref_key` (line 417) inspects `schema_props` only for the **presence** of `f"{key}_ref"` — it does not look at the sibling's schema entry to verify it is a canonicalRef:
   ```python
   def _expected_ref_key(key, schema_props, allow_fallback):
       if not schema_props:
           if not allow_fallback: return None
           if key in _FALLBACK_DIRECT_FIELDS: return f"{key}_ref"
           return None
       direct = f"{key}_ref"
       if direct in schema_props:        # <-- presence-only check
           return direct
       mapped = _ALIASED_SOURCE_FIELDS.get(key)
       if mapped and mapped in schema_props:
           return mapped
       return None
   ```
4. `_is_resolved_ref` (line 433) demands the sibling value be a dict with `id` starting with `cn:`:
   ```python
   def _is_resolved_ref(value):
       if not isinstance(value, dict): return False
       cid = value.get("id")
       return isinstance(cid, str) and cid.startswith("cn:")
   ```
   A plain URI string can never satisfy this.
5. `_kind_for_ref_key` (line 440) then returns `ref_key[:-len("_ref")]` — i.e. it derives `kind="evidence"` from `evidence_ref` without checking whether such a canon kind exists.

For `evidence` / `evidence_ref`, the `_ref` sibling **is** present in `schema_props` (so `_expected_ref_key` returns `"evidence_ref"`), but it is schema-typed `string`, not `canonicalRef`. The walker doesn't notice the type, sees the string-valued sibling fail the `cn:`-id check, and emits E210 with a synthesised `kind=evidence` that has no canon entry.

Result: every populated `execution.execution_results[].evidence` entry trips E210 even when `evidence_ref` carries the prescribed URI form.

### Interaction with `_FALLBACK_DIRECT_FIELDS` and `_ALIASED_SOURCE_FIELDS`

- `_FALLBACK_DIRECT_FIELDS` (line 276) is consulted **only** when `schema_props` is empty (i.e. the doc has no resolvable schema or the walker is in a schema-less subtree). In the bug scenario, the document carries `$schema = vc:16-impl-context` and resolves — so `allow_fallback` is False during the `evidence_ref` decision, and fallback is **not** the trigger here. The fallback set is therefore not implicated in this defect; the defect is in the `direct in schema_props` branch.
- `_ALIASED_SOURCE_FIELDS = {"category": "risk_category_ref"}` (declared at line 272) is the only alias entry today and is unrelated to `evidence`. No interaction.

## Scope of impact

**Schema scan**: every `<field>_ref` property defined under `properties:` across all `devspec_toolkit/schema/**/*.schema.json` was inspected. A `_ref` sibling is *vulnerable* to this defect iff (a) it has a non-`_ref` bare sibling with the same prefix in the same `properties` block, **and** (b) it is **not** a `canonicalRef` (no `vc:core:collections#canonicalRef` reference, direct or via `allOf`).

Result of scan (script-driven, traversing every `properties` block in every schema):

| Schema | Bare field | `_ref` sibling type | Vulnerable? |
|---|---|---|---|
| `16_impl_context.schema.json` (under `execution.execution_results[].items.properties`) | `evidence` | plain `string` (URI) | **YES** |

**No other vulnerable `<field>_ref` pairs exist across the toolkit's schemas.** Every other `<field>_ref` either (a) is a canonicalRef via `$ref: "vc:core:collections#canonicalRef"` (direct or inside `allOf`), or (b) has no bare sibling of the same name in the same properties block (so `_expected_ref_key` returns `None` even today).

**Host artifacts currently affected in this repo**: `spec/impl_context/ms_bootstrap_local_ghost_plan.json` — 14 errors, one per populated `execution.execution_results[N].evidence` for `N ∈ [0, 13]`. No other host artifact authored at this point trips it. Any future `spec/impl_context/<milestone>_plan.json` that populates `execution.execution_results[*].evidence` will reproduce identically.

## Regression scope

- The buggy `_expected_ref_key` / `_is_resolved_ref` / `_collect_unresolved_candidates` chain was **introduced** in commit `eedf5fdbb34c5d65c8b3afc512fd319ee468e430` (`fix(review): address RFC canonical drift findings & close untracked assets`, 2026-02-26).
  Verified via `git log -S '_expected_ref_key' -- tools/specdev_tools/canonical/integrity.py` and `git log -S '_FALLBACK_DIRECT_FIELDS' -- tools/specdev_tools/canonical/integrity.py` — both return `eedf5fd` as the sole introducing commit.
- Verified the same buggy logic block is byte-identical at `3930532` (= `b7ba008^`) by diffing `git show 3930532:tools/specdev_tools/canonical/integrity.py` against the current file at the relevant region. The bug is **not** introduced by `b7ba008`; `b7ba008` did not touch the integrity walker.
- The `evidence` / `evidence_ref` schema fields (`schema/16_impl_context.schema.json:1653-1661`) predate the defect surfacing only because no host artifact populated them at scale until Step 16b execution authoring on `ms-bootstrap-local-ghost`.

## Proposed fix

Tighten `_expected_ref_key` (and its fallback companion) so that a `<field>_ref` sibling is only treated as an expected canonicalRef when its schema entry **is** a canonicalRef. Concretely:

### Canonical-ref schema shape (verified)

`canonicalRef` is defined in `devspec_toolkit/schema/core/collections.schema.json:106-143`:

```json
"canonicalRef": {
  "$anchor": "canonicalRef",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "id":   { "type": "string", "pattern": "^cn:[a-z0-9.]+:[a-z_][a-z0-9_]*:[a-z0-9-]+$" },
    "kind": { "type": "string", "pattern": "^[a-z_][a-z0-9_]*$" },
    "version": { "type": "string" },
    "label":   { "type": "string" },
    "alias_used": { "type": "string" },
    "note":    { "type": "string" }
  },
  "required": ["id", "kind"]
}
```

In schemas, `<field>_ref` properties reference it either directly (`{"$ref": "vc:core:collections#canonicalRef"}`) or wrapped in `allOf` with a `kind` const (e.g. `command_ref` at `schema/16_impl_context.schema.json:1687-1701`):

```json
"command_ref": {
  "description": "…",
  "allOf": [
    { "$ref": "vc:core:collections#canonicalRef" },
    { "properties": { "kind": { "const": "command" } } }
  ]
}
```

### Detection rule

A `_ref` sibling schema is a canonicalRef iff **any** of the following hold (evaluated on the literal `properties[<key>_ref]` node only — no `$ref` chain following beyond what `_is_canonical_ref_schema` does inline):

1. `node["$ref"]` is a string containing the substring `"canonicalRef"` (covers both the absolute form `vc:core:collections#canonicalRef` and a relative `#canonicalRef` anchor), **or**
2. any subschema in `node["allOf"]` / `node["anyOf"]` / `node["oneOf"]` matches rule (1) or (3) recursively (depth-bounded to 6 to prevent pathological recursion on cyclic schemas), **or**
3. `node["properties"]["id"]["pattern"]` starts with `^cn:` — defensive case for inline canonicalRef object definitions. Independently scanned every `properties` block in `devspec_toolkit/schema/**/*.schema.json` (script in §"Scope of impact"); zero inline canonicalRef definitions exist today, but adding the rule costs nothing and future-proofs the detector.

**Explicit non-coverage** (deliberately out of scope; the only known vulnerable pair is `evidence`/`evidence_ref` and it is `type: string` flat):

- `_ref` declared via a `$ref` to a `$defs` entry that itself has `$ref: ".../canonicalRef"` (chained `$ref`). The proposed rule does **not** follow `$ref` chains. Verified by re-running the schema scan: no `<field>_ref` in any toolkit schema uses chained `$ref` to canonicalRef — every canonicalRef use is either a direct `$ref` or wrapped in `allOf`. If a future schema adds chained-`$ref` canonicalRefs, the detector will mis-classify them as non-canonical and silently drop the E210 emission for that pair (false negative, not a regression vs. today's behaviour for canonical pairs because those still emit via the `$ref` substring rule).
- `_ref` typed as `type: string` with `format: uri` or an explicit `pattern`. The detector treats these the same as the `evidence_ref` case (i.e., NOT a canonicalRef), which is the desired behaviour — they are explicit non-canonical refs.

The proposed `_is_canonical_ref_schema` predicate intentionally accepts only the three positive shapes above; everything else (including `type: string` siblings, `oneOf`/`anyOf` shapes whose branches do not contain a canonicalRef `$ref`, and bare object schemas without an `id.pattern` of `^cn:`) is treated as non-canonical and therefore does not trigger E210.

### Diff sketch

```python
# integrity.py (additions / changes)

def _is_canonical_ref_schema(node: Any) -> bool:
    """True iff `node` describes a canonicalRef (directly or via allOf/anyOf/oneOf)."""
    if not isinstance(node, dict):
        return False
    ref = node.get("$ref")
    if isinstance(ref, str) and ("canonicalRef" in ref):
        return True
    id_prop = node.get("properties", {}).get("id", {}) if isinstance(node.get("properties"), dict) else {}
    if isinstance(id_prop, dict) and isinstance(id_prop.get("pattern"), str) and id_prop["pattern"].startswith("^cn:"):
        return True
    for combinator in ("allOf", "anyOf", "oneOf"):
        for sub in node.get(combinator, []) or []:
            if _is_canonical_ref_schema(sub):
                return True
    return False


def _expected_ref_key(key: str, schema_props: dict[str, Any], allow_fallback: bool) -> str | None:
    if not schema_props:
        if not allow_fallback:
            return None
        if key in _FALLBACK_DIRECT_FIELDS:
            return f"{key}_ref"
        return None
    direct = f"{key}_ref"
    if direct in schema_props and _is_canonical_ref_schema(schema_props[direct]):   # <-- new guard
        return direct
    mapped = _ALIASED_SOURCE_FIELDS.get(key)
    if mapped and mapped in schema_props and _is_canonical_ref_schema(schema_props[mapped]):  # <-- new guard
        return mapped
    return None
```

### Should `_FALLBACK_DIRECT_FIELDS` change?

No. Every entry in the current set (`stage`, `environment`, `status`, `term`, `acronym`, `capability`, `action`, `entity`, `event`, `interface`, `metric`, `unit`, `role`, `policy`, `command`, `tag`, `risk_category`, `governance_label`, `id_pattern`, `completeness_dimension`) corresponds to an existing canon kind under `devspec_toolkit/canon/kinds/` (verified by listing the directory; all 20 names are present). Fallback only fires when no schema is resolved; in that mode the assumption "if it's named `<canon-kind>` it must want a canonicalRef sibling" is the best signal available. Leave the set as-is.

## Test plan

Tests live under `devspec_toolkit/tests/unit/canonical/test_canonical_integrity.py` (existing helpers: `validate_canonical_integrity`, `validate_canonical_integrity_file`; existing pattern of building a synthetic temp repo with `canon/manifest.json` + `tools/schema_registry.json` + a synthetic `schema/*.schema.json` + a `spec/*.json` artifact — see `test_external_schema_ref_does_not_trigger_false_unresolved_semantics` at line 191 for the closest precedent).

Verified that none of the three proposed test names exist today in `tests/unit/canonical/test_canonical_integrity.py` (grepped — zero matches). All three are inline-dict tests in the style of the existing precedents (no separate fixture file needed); they construct the schema and spec dicts in-process, write them to a `tempfile.TemporaryDirectory()`, and call `validate_canonical_integrity` directly.

Add three tests in the same file (place after `test_file_mode_can_skip_unresolved_semantic_enforcement`):

1. **`test_string_typed_ref_sibling_does_not_trigger_e210`** (negative — the regression case)
   - Schema (inline) — keys mirror precedent at line 191:
     ```json
     {
       "$schema": "https://json-schema.org/draft/2020-12/schema",
       "$id": "vc:test",
       "type": "object",
       "properties": {
         "evidence": {"type": "string", "minLength": 20},
         "evidence_ref": {"type": "string"},
         "canonical_refs_used": {"type": "array"},
         "canonical_proposals": {"type": "array"},
         "canonical_conflicts": {"type": "array"}
       },
       "required": ["evidence", "evidence_ref", "canonical_refs_used", "canonical_proposals", "canonical_conflicts"]
     }
     ```
   - Spec doc (inline):
     ```json
     {
       "$schema": "vc:test",
       "evidence": "command output captured here >=20 chars",
       "evidence_ref": "https://example/log",
       "canonical_refs_used": [],
       "canonical_proposals": [],
       "canonical_conflicts": []
     }
     ```
   - Assert: `not any("unresolved_canonical_semantic" in e.render() for e in errs)` AND `not any("kind=evidence" in e.render() for e in errs)`.

2. **`test_canonical_ref_typed_sibling_still_flags_e210_when_unresolved`** (positive — must not regress)
   - Schema (inline) — `status_ref` declared as a true canonicalRef via `allOf`:
     ```json
     {
       "$schema": "https://json-schema.org/draft/2020-12/schema",
       "$id": "vc:test",
       "type": "object",
       "properties": {
         "status": {"type": "string"},
         "status_ref": {
           "allOf": [
             {"$ref": "vc:core:collections#canonicalRef"},
             {"properties": {"kind": {"const": "status"}}}
           ]
         },
         "canonical_refs_used": {"type": "array"},
         "canonical_proposals": {"type": "array"},
         "canonical_conflicts": {"type": "array"}
       },
       "required": ["status", "canonical_refs_used", "canonical_proposals", "canonical_conflicts"]
     }
     ```
   - Spec doc has `status: "passed"` and **no** `status_ref` key. (The `vc:core:collections` schema must be registered in `tools/schema_registry.json` and physically copied into the temp `schema/` dir, mirroring `test_file_mode_can_skip_unresolved_semantic_enforcement` at lines 285-292.)
   - Assert: at least one error matches `unresolved_canonical_semantic` with `field=status` and `kind=status` in the rendered string.

3. **`test_evidence_evidence_ref_regression_fixture_for_step_16`** (regression fixture against the real schema)
   - Mirror `test_file_mode_can_skip_unresolved_semantic_enforcement` (line 260) for the schema-copy plumbing, but copy `16_impl_context.schema.json` plus its dependencies (`atoms.schema.json`, `collections.schema.json`) into the temp `schema/` directory.
   - Spec doc: minimal valid `vc:16-impl-context` artifact with `plan` populated to satisfy the schema's `required: ["plan"]`, plus one `execution.execution_results[]` entry with `status: "passed"`, `outcome_description`, `reasoning`, `command`, `evidence: "<≥20 chars>"`, `evidence_ref: "https://example/log"`, and a valid `evidence_binding` (the schema requires `timestamp`, `sha256`, `exit_code` when present; `evidence_binding` itself is required when status is "passed" per `prompts/migration/template_impl_coder.md:17`).
   - Assert: `not any("unresolved_canonical_semantic" in e.render() and "kind=evidence" in e.render() for e in errs)`.

Run locally:

```bash
source dev_env/bin/activate
cd devspec_toolkit
pytest tests/unit/canonical/test_canonical_integrity.py -v
```

## Side effects

- Tightening `_expected_ref_key` only **removes** false-positive emissions; it cannot create new ones because the new guard is strictly more restrictive.
- All currently-flagged cases that *should* fire (i.e. real `<field>` strings whose `<field>_ref` sibling is a canonicalRef but unpopulated/non-`cn:`) continue to fire because their sibling schema entries do match `_is_canonical_ref_schema`. Confirmed by inspecting representative pairs: `status`/`status_ref` (`16_impl_context.schema.json:1709`), `command`/`command_ref` (`16_impl_context.schema.json:1687`), `unit`/`unit_ref` (canon-driven across multiple schemas) — all use `$ref: vc:core:collections#canonicalRef` either directly or under `allOf`.
- `_FALLBACK_DIRECT_FIELDS` behaviour is unchanged when schema resolution fails (no behavioural change for the schema-less branch).

## Verification steps (post-fix)

```bash
cd /Users/vichitracollective/vc-code/vc_wesbite
source dev_env/bin/activate

# 1. Targeted: the artifact that produced the 14 false positives
./tools/run_specdev.sh validate spec/impl_context/ms_bootstrap_local_ghost_plan.json \
  --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
# Expect: zero E210 unresolved_canonical_semantic errors with kind=evidence.

# 2. canonical-integrity across the host spec dir
./tools/run_specdev.sh canonical-integrity spec \
  --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
# Expect: zero E210 unresolved_canonical_semantic errors with kind=evidence;
# any pre-existing E210 entries unrelated to evidence remain.

# 3. Full spec-check (what pre-commit runs)
./tools/run_specdev.sh spec-check spec \
  --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
# Expect: same — no kind=evidence errors; other lints unchanged.

# 4. Toolkit unit tests
cd devspec_toolkit
pytest tests/unit/canonical/test_canonical_integrity.py -v
# Expect: existing tests still pass; three new tests pass.
```

Concrete before/after counts (measured on this branch's working tree, `2026-04-19`):

| Surface | Before fix | After fix (expected) |
|---|---|---|
| `canonical-integrity spec` — total `E210` lines (`grep -c E210`) | **14** | **0** |
| `canonical-integrity spec` — `kind=evidence` lines (`grep -c "kind=evidence"`) | **14** | **0** |
| `spec-check spec` — error codes by code (`grep -E '^E[0-9]' \| awk '{print $1}' \| sort \| uniq -c`) | `14 E210` | (none from this surface) |

Pass criteria: the table above holds; existing positive integrity tests (`test_unknown_id_detected` line 16, `test_external_schema_ref_does_not_trigger_false_unresolved_semantics` line 191, `test_file_mode_can_skip_unresolved_semantic_enforcement` line 260) continue to pass; three new tests pass.

## Schema-authoring rationale (why `evidence_ref` is `type: string`, not a canonicalRef)

`evidence_ref` is documented as a free-form URI in `prompts/migration/template_impl_coder.md:17` (verbatim quote below) and re-stated in paraphrased form at `:60-61` ("…the schema also requires `evidence_ref` and `evidence_binding` (`timestamp`, `sha256`, `exit_code`)."):

> "When `status == "passed"`, `evidence_ref` and `evidence_binding` are also required."

The 16b coder prompt (`prompts/prompt_16b_impl_coder.md:104-105`) frames `evidence_binding` as the structured (cryptographic) anchor:

> "**`execution.execution_results[].evidence_binding`**: Use this object to attach structured evidence metadata (timestamp, sha256, exit_code)."

So the design split is intentional: `evidence` carries raw output, `evidence_ref` is a free-form URI pointer to the source (log file URL, S3 key, etc.), and `evidence_binding` is the structured cryptographic record. Promoting `evidence_ref` to a canonicalRef would force every evidence URI through the canon registry, which has no `evidence` kind defined and is not a meaningful semantic vocabulary for log URLs. The schema is correct; the lint is wrong.

## User impact

- Any host repo that vendors `devspec_toolkit ≥ 0.5.1` (introduction commit `eedf5fd`) and authors a `spec/impl_context/<milestone>_plan.json` with populated `execution.execution_results[*].evidence` cannot pass `canonical-integrity` / `spec-check` without `--no-verify`. Pre-commit hooks block on this; CI gates that run `spec-check` will block on this.
- Concretely on this repo: 16b execution authoring for `ms-bootstrap-local-ghost` is complete (14 entries, all `status: "passed"`, all carrying populated `evidence` + `evidence_ref` + `evidence_binding`). Every commit since 16b authoring is blocked unless `--no-verify` is used. 16c review cannot generate a clean lint baseline.

## Workaround (until fix lands)

Two tiers, depending on user appetite:

1. **Bypass the hook**: `git commit --no-verify` for milestone artifacts that populate `execution.execution_results[*].evidence`. Stripping the `evidence` field is **not** a workable workaround because (a) it violates the 16b prompt contract and (b) the schema requires `minLength: 20` on `evidence` when present.

2. **Suppress per-entry via `canonical_conflicts`** (no-`--no-verify` path): The `_validate_unresolved_candidates` walker (`integrity.py:320-322`) skips any `(field_path, normalized_value)` pair listed in the document's `canonical_conflicts` array. The 16 schema's root has `unevaluatedProperties: false` (verified) but inherits `canonical_refs_used` / `canonical_proposals` / `canonical_conflicts` via `allOf: [{"$ref": "vc:core:step-base"}]` (see `schema/core/step_base.schema.json:34`), so `canonical_conflicts` is an *evaluated* property and a top-level `canonical_conflicts: [...]` on `<milestone>_plan.json` validates cleanly. End-to-end suppression verified: injecting one entry into the live artifact reduced `canonical-integrity` E210 count from 14 → 13 with `execution.execution_results[0].evidence` removed from the error list.

   ```json
   "canonical_conflicts": [
     {
       "field_path": "execution.execution_results[0].evidence",
       "input_value": "<paste the same evidence string here>"
     }
   ]
   ```

   The `field_path` must match exactly (including the `[N]` index); `input_value` is normalised by `_norm_semantic` (lowercase, whitespace-collapsed) before comparison. This is verified working against `_conflict_index` at `integrity.py:461`. It is a tedious workaround (one entry per row) and visually noisy in the artifact, so use only if `--no-verify` is unacceptable.

The `canonical_proposals` array is **not** a viable suppression path here: `_proposal_index` (`integrity.py:446`) keys on `(source_field, kind, normalized_label)` and would require `kind="evidence"`, but no such canon kind exists — adding the proposal entry would itself fail downstream canonical-lint coherence checks even though it would suppress the E210.

## Documentation status

E210 is documented in `docs/audit/r3_canonical_drift.md:70` and `docs/audit/findings/r3_findings.md:14, 28-29` (audit / RFC context only — not in any user-facing changelog or guide). There is no published user-facing description of E210's trigger conditions or remediation today. Consider adding a one-paragraph entry to the toolkit changelog when this fix ships.

## Release / rollout

The toolkit uses a multi-file changelog (`devspec_toolkit/CHANGELOG.md` is the manifest; per-version files live in `devspec_toolkit/changelog/vX.Y.Z.{md,yaml}`). Current released version is `0.5.1` (`tools/pyproject.toml:9`); `changelog/unreleased.md` is open. This is a pure bugfix with no schema, prompt, or output-contract change, so it qualifies as a `0.5.2` patch:

1. Bump `tools/pyproject.toml` `version = "0.5.2"`.
2. Add `changelog/v0.5.2.md` (human) and `changelog/v0.5.2.yaml` (machine, even if `migrations: []`) per the manifest's contribution guide; link from `CHANGELOG.md`'s version index.
3. No `specdev align` migration entries are needed — no schema fields renamed/added/removed.

## Related lint codes / shared mechanism

`grep "make_error(\"E2|make_error(\"W" devspec_toolkit/tools/specdev_tools/canonical/integrity.py` returns three call sites: `E210` (canonical_refs_used_missing) at `integrity.py:184`, `E210` (canonical_refs_used_extra) at `:191`, `E210` (unresolved_canonical_semantic) at `:326`, and `E211` (PARTIAL_DRIFT) at `:84` and `:135`. Only the `:326` call site flows through `_collect_unresolved_candidates`. `E211` uses the independent `_collect_observed_semantics` walker (`integrity.py:241`) which keys off `_ref` siblings whose `id` starts with `cn:` — the bug does **not** affect E211 because E211 ignores `_ref` siblings that aren't dicts with valid `cn:` ids. The other two `E210` sites scan `canonical_refs_used` declarations and don't touch `_expected_ref_key`. Therefore the fix is local: only one call site benefits, and no other code/W-code sees collateral changes.

## Backwards compatibility

- **Host repos that worked around this with `canonical_conflicts` entries** (per the documented workaround): the fix renders those entries inert (the `(field_path, label)` lookup at `integrity.py:321` becomes unreachable for the `evidence` pair because no candidate is collected anymore). Inert entries are **not** flagged by the schema — `canonical_conflicts` items have no required cross-reference. Hosts can leave them in place or delete them; either way no errors surface.
- **Host repos that used `--no-verify`**: no action required; pre-commit / CI starts passing once the toolkit submodule is updated.
- **Stale `evidence_ref` URIs** (e.g. broken/relative URLs the host populated assuming the bug was a feature): nothing else in the toolkit lints `evidence_ref` content. The schema only enforces `type: string`. After the fix, no E210/W-code fires on `evidence_ref` content; if URI hygiene matters to a host, that's net-new functionality outside this bug's scope.

## Trade-off (acknowledged false-negative surface)

The proposed `_is_canonical_ref_schema` predicate is intentionally narrow (direct `$ref` substring match, `allOf`/`anyOf`/`oneOf` shallow recursion, inline `id.pattern ^cn:`). It does **not** chase `$ref` chains through `$defs` to a canonicalRef leaf. If a future toolkit schema declares `<field>_ref` as `{"$ref": "#/$defs/myRef"}` where `$defs.myRef` itself `$ref`s `vc:core:collections#canonicalRef`, the detector will mis-classify it as non-canonical and silently drop the E210 emission for that field (false negative — the schema validator and canonical-lint registry checks still flag mismatched `kind`/`id` content via different code paths). Today's schema set has zero such chained refs (verified by the §"Scope of impact" scan); add a follow-up issue if a future schema introduces one.

## Cross-reference: prior reports

`grep "_collect_unresolved_candidates\|_expected_ref_key\|_FALLBACK_DIRECT_FIELDS" devspec_toolkit/WIP/done/*.md` returns no matches. No prior closed bug report touched this code path. The closest neighbour is `WIP/done/toolkit_bug_w576_task_id_schema_mismatch.md` (linter assumption diverged from schema authority — same diagnostic class, different module).

---

## Related prior reports

- `WIP/toolkit_bugs_16c_review_blockers.md` — Bug 7 (`canonical_refs_used_extra/_missing`) is the adjacent papercut on the same surface (canonical-integrity), different defect.
- `WIP/done/toolkit_bug_w576_task_id_schema_mismatch.md` — same class of defect (validator/lint assumes a field shape the schema does not actually impose). The W576 case reads `task_id` from `execution_results[]` though the schema forbids it; this E210 case treats `evidence_ref` as a canonicalRef though the schema types it as a string. Pattern: tooling assumption diverged from schema authority.
- `WIP/done/matrix_py_bug_report.md` — different surface (trace matrix), but same diagnostic discipline (verify against source, name exact lines, sketch the diff).
