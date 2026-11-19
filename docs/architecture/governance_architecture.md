# Governance Architecture

Developer reference for the enforcement and traceability subsystems that keep spec artifacts consistent.

---

## Canon-Backed Trace Types

`tools/specdev_tools/core/trace_types.py` provides the single source of truth for valid trace type labels used across the toolkit.

**Loading path:** `_load_from_canon()` resolves the toolkit root via `Path(__file__).resolve().parents[3]`, instantiates `CanonicalRegistry.load(toolkit_root)`, and iterates all entries where `entry.kind == "trace_type"`. It collects each entry's `preferred_label` into the `TRACE_TYPES` tuple and builds a `CANONICAL_TRACE_TYPE` alias map from each entry's `aliases` list.

**Canonical source:** `canon/kinds/trace_type.json` -- 11 registered types:

| preferred_label | aliases |
|---|---|
| `fr` | -- |
| `api` | -- |
| `nfr` | -- |
| `invariant` | `inv` |
| `fixture` | -- |
| `doc` | -- |
| `capability` | -- |
| `component` | -- |
| `threat` | -- |
| `charter-goal` | -- |
| `glossary` | -- |

**Fallback behavior:** If the import of `CanonicalRegistry` fails or `canon/kinds/trace_type.json` is missing/corrupt, `_load_from_canon()` catches any `Exception` and returns `_FALLBACK_TYPES` (a hardcoded 11-tuple) and `_FALLBACK_ALIASES` (`{"inv": "invariant"}`). This guarantees offline validation never crashes.

**Alias resolution:** `normalize_trace_type(value)` strips whitespace and checks `CANONICAL_TRACE_TYPE`; if the value is a known alias (e.g., `"inv"`), it returns the canonical label (`"invariant"`). `is_valid_trace_type(value)` normalizes first, then checks membership in `TRACE_TYPES`.

**Consumers (5 modules):**

| Module | Imports used |
|---|---|
| `validation/matrix.py` | `normalize_trace_type`, `is_valid_trace_type` |
| `validation/cross_artifact_checks.py` | `normalize_trace_type`, `is_valid_trace_type` |
| `validation/hallucination_lint.py` | `is_valid_trace_type` |
| `validation/traceability_closure.py` | `normalize_trace_type`, `is_valid_trace_type` |
| `core/__init__.py` | re-exports `normalize_trace_type`, `is_valid_trace_type` |

**Business-rule constant pattern (OPT-003):** Each validation module that depends on specific trace types declares them as module-level constants (e.g., `_TRACE_TYPE_FR = "fr"`). These constants are guarded by a `warnings.warn()` call at import time that fires if the value is not present in the canon registry, providing early detection of canon drift without crashing at runtime.

All paths route through `core/trace_types.py` -- there is a single loading path and a single module-level cache (`TRACE_TYPES`, `CANONICAL_TRACE_TYPE` are computed once at import time).

---

## Dynamic Entity Indexing

`tools/specdev_tools/validation/matrix.py` (`_legacy_scan_data`) implements schema-agnostic entity discovery for the trace matrix. It is the fallback, used when `tools/entry_key_registry.json` is absent and for a file the registry does not know; for every other file the matrix lists entities from the registry's entry keys.

**Algorithm:**

1. Walk every loaded artifact's top-level keys. For each key whose value is a `list`, iterate the items.
2. For each `dict` item, scan its fields for any field ending in `_id` whose value is a `str`.
3. Strip the `_id` suffix from the field name (e.g., `fr_id` -> `fr`, `api_id` -> `api`).
4. Normalize the prefix via `normalize_trace_type()` (resolves aliases).
5. Validate via `is_valid_trace_type()` -- only canon-registered types are indexed.
6. Append the item to `entity_index[normalized_type]`. Break after the first matching `_id` field per object (one entity type per object).

**Result:** `entity_index` is a `defaultdict(list)` keyed by canonical trace type. The matrix builder then bridges to named variables (`frs = entity_index.get("fr", [])`, etc.) for backward compatibility with the link-building logic.

**What this replaced:** Prior versions hardcoded schema-path checks like `if "04_fr_list" in schema` to decide which entities to extract. The dynamic approach discovers entities from any spec file -- including extension artifacts -- without code changes when new entity types are added to the canon.

### Cross-Artifact Checks (OPT-002)

`tools/specdev_tools/validation/cross_artifact_checks.py` contains step-specific integrity checks extracted from `validate_trace_integrity()` in `matrix.py`. This module exports:

- `collect_capability_ids(artifacts)` -- gathers capability IDs from step 01
- `collect_glossary_term_ids(artifacts)` -- gathers glossary term IDs from step 03
- `check_step_02_integrity(artifacts, capability_ids)` -- validates step 02 cross-references
- `check_step_03_integrity(artifacts)` -- validates step 03 cross-references
- `check_step_04_integrity(artifacts, glossary_term_ids, capability_ids)` -- validates step 04 cross-references

`validate_trace_integrity()` in `matrix.py` now delegates to these functions for step-specific logic while retaining generic broken-reference scanning (`collect_definitions_and_references()`) in matrix.py itself.

---

## Step Dependency DAG

Defined in `tools/step_order.json`.

**Structure:**

- `steps`: ordered list of 22 step IDs: `00 01 02 02a 03 04 05 06 07 08 09 10 11 12 13 13a 14 15 16 16a 16b 16c`
- `step_metadata[<step>].required_spec_inputs`: the steps whose artifacts this step reads.
- `downstream_consumers`: declared on the **provider** side. Each step lists which later steps directly consume its output.

**Policy flags:**

```json
{
  "mode": "strict_waterfall",
  "allow_self_dependency": false,
  "allow_forward_dependency": false,
  "require_full_forward_replay_on_change": true
}
```

`require_full_forward_replay_on_change` no longer decides whether replay is required. Replay is the set of suspect links in the trace lock (`spec/extras/trace.lock.json`, E763); `spec-check` and `validate-all` report them whatever this flag says (checked on the worked example with the flag set to `false`: 21 E763 findings from each). `validate-all` still reads the flag: only while it is true does it run the base-ref check for id regressions (E555, W598, W550). Run on a copy of the worked example kept as its own git repository, whose last commit dropped one FR and its two criteria, with the copy itself as `--repo-root` (its `schema/`, `tools/` and `canon/` taken from the toolkit) and `SPECDEV_REPLAY_BASE_REF=HEAD~1`, `validate-all` reported E555 and three W598 with the flag true, and neither with it false. With the toolkit as `--repo-root` (the form CLAUDE.md gives), `validate-all` reported none of them, with `--git-root .` as well as without it, because the base ref is read from the repository of `--repo-root`; `forward-replay-check --repo-root <toolkit> --spec-root ./spec --git-root .` run from the copy reported the same E555 and three W598, and without `--git-root` it reported none. File-level forward replay (the old requirement that every step after a changed step has a changed file) is retired; see [reference.md](../developers/reference.md#trace-lock-replay-and-attest).

**Generated, not hand-kept:** `specdev registry-generate` derives `step_metadata` and `downstream_consumers` from the `x-link` declarations of the step schemas and from the hand-kept `declared_edges` pairs; the two keys are each other's inverse (E543 otherwise). Only `version`, `steps`, `policy`, `coverage_thresholds` and `declared_edges` are edited by hand.

**Reading the inputs of a step:** `step_metadata["05"].required_spec_inputs` is `["00", "02", "04"]`, and `downstream_consumers["00"]`, `["02"]` and `["04"]` each contain `"05"`. `specdev prompt-context <step>` prints the consumers of a step.

**Fan-out:** steps `00` (Charter), `04` (FRs) and `05` (APIs) have the most consumers; step `14` (Roadmap) feeds the Trinity Loop (`16`, `16a`, `16b`, `16c`). Steps `03` (Glossary: its terms are used by label, not by link) and `16c` have no consumer.

---

## Seed Propagation Boundary

Defined in `spec/common/seed_manifest.json`.

**Routing is manifest-driven:** `spec/common/seed_manifest.json` is the single authoritative source for which seeds apply to which steps and where they live. The `step_requirements` map in the manifest defines per-step seed requirements; the `seeds[]` array defines each seed's `path` and metadata. Any step — across the full 00–16c waterfall — may declare seed requirements via `step_requirements[NN]`. Steps not listed (or with an empty array) require no seeds; `global_seed_order` governs only the read order of step-required seeds. The `seed-lint` command validates that all referenced seed IDs are declared in the manifest and that each step's usage is consistent with its manifest entry.

---

## Prompt Architecture (Post-Sanitization)

Prompts no longer contain "Context To Ingest" sections. This was a deliberate sanitization to enforce a clean separation:

- **Prompts** define output contracts (JSON schema URI, required fields, validation rules) and operating flows (Clarify/Emit protocol, self-audit gates).
- **Orchestration layer** is responsible for assembling and delivering context (upstream artifacts, seed docs, canon entries) to the AI runner.

This means prompts are portable across orchestration implementations. An orchestration layer reads `step_order.json` to determine which upstream artifacts to inject, and `seed_manifest.json` to determine which seeds to include.

---

## Enforcement Tiers

Validation operates at three levels of dynamism:

### Tier 1: JSON Schema (Static)

- Enums are self-contained in `schema/` files (e.g., `owner` enum in `schema/core/atoms.schema.json`).
- Works fully offline with no canon dependency.
- Validates structure, required fields, types, patterns.

### Tier 2: Hallucination Lint (Dynamic)

- `hallucination_lint.py` loads the canon registry at runtime via `is_valid_trace_type()`.
- Detects fabricated trace types, unknown entity references, and invalid enum values that JSON Schema cannot catch because the allowed set is externally managed.
- Falls back to `_FALLBACK_TYPES` if canon is unavailable.

### Tier 3: Canonical Integrity (Fully Dynamic)

- `canonical-integrity` and `canonical-lint` commands operate entirely against the live canon registry.
- Validates that spec artifacts reference only active (non-deprecated) canon entries.
- Checks alias consistency, lifecycle status, and cross-kind reference validity.
- No fallback -- requires a functioning `canon/` directory.

---

## Validation Ritual

The required sequence after any spec edit:

```
1. validate          -- JSON Schema validation of the changed artifact
2. seed-lint         -- verify seed usage matches seed_manifest step_requirements
3. matrix            -- regenerate spec/extras/trace_matrix.json (if traceability changed)
4. fixtures-lint     -- check that each fixture has input and expected (see the note below)
```

`fixtures-lint` recognises a step 08 file by a `$schema` that ends in `/08_fixtures.schema.json`. A file that carries the registry id `vc:08-fixtures`, which is what the step 08 prompt writes, is not read and the command prints `OK` (DEVSPEC-237).

**When to run each check:**

| Trigger | Required checks |
|---|---|
| Any spec file edit | `validate`, `seed-lint` |
| Trace field changed on a 1.1.1-shaped spec (`trace`, `targets`, `_ref`) | Add `matrix` |
| Fixture `input` or `expected` changed | Add `fixtures-lint` (reads no `vc:08-fixtures` file, see the note above) |
| New canon entry added | `canonical-lint`, `canonical-integrity` |
| Commit | `governance-check` against commit message |
| Upstream step changed | `stale` to list the suspect links, `attest` once each is read, then `spec-check` (`forward-replay-check` is a deprecated alias) |
| Schema enum modified | `hallucination-lint` to verify specs still conform |
